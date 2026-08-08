import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import _entrypoint_helpers as helpers
import _fixtures
import _path_setup  # noqa: F401

from oprc import canonical, config as oprc_config, dlp, ids, lifecycle, store

JST = timezone(timedelta(hours=9))


class OperatorChannelTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool_dir = os.path.join(self.tmp.name, "spool")
        helpers.make_spool(self.spool_dir)
        self.audit_log = os.path.join(self.tmp.name, "audit.jsonl")
        self.config_path = os.path.join(self.tmp.name, "config.json")

        with open(_path_setup.SCHEMA_PATH, "rb") as f:
            schema_hash = canonical.sha256_hex(f.read())
        with open(_path_setup.DLP_RULES_PATH, "rb") as f:
            ruleset_hash = canonical.sha256_hex(f.read())

        helpers.write_config(
            self.config_path,
            config_version=1,
            role="operator_host",
            channel_enabled=True,
            libexec_dir=_path_setup._OPRC_FILES_DIR,
            schema_path=_path_setup.SCHEMA_PATH,
            dlp_rules_path=_path_setup.DLP_RULES_PATH,
            expected_schema_sha256=schema_hash,
            expected_dlp_engine_version=dlp.ENGINE_VERSION,
            expected_dlp_ruleset_sha256=ruleset_hash,
            max_payload_bytes=65536,
            dlp_timeout_seconds=5,
            spool_dir=self.spool_dir,
            audit_log_path=self.audit_log,
            max_ttl_days=14,
            default_ttl_days=7,
            max_messages_per_box=500,
            max_total_bytes=134217728,
            page_size=50,
        )

        self.module = helpers.load_entrypoint("operator-channel")
        self._synced_patch = helpers.patch_time_synced(oprc_config, synced=True)
        self._synced_patch.start()
        self.addCleanup(self._synced_patch.stop)
        self._config_patch = mock.patch.object(self.module, "CONFIG_PATH", self.config_path)
        self._config_patch.start()
        self.addCleanup(self._config_patch.stop)

    def _seed_opreq(self, purpose=None, expires_days=7):
        request_id = ids.generate_request_id()
        conversation_id = ids.generate_conversation_id()
        created_at = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z")
        message = {
            "schema_version": 1,
            "request_id": request_id,
            "conversation_id": conversation_id,
            "type": "OPREQ",
            "source": "coordinator",
            "created_at": created_at,
            "expires_at": (datetime.now(JST) + timedelta(days=expires_days)).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "purpose": purpose or _fixtures.benign_prose(),
        }
        meta = {
            "content_sha256": canonical.content_hash(message),
            "dlp_engine_version": dlp.ENGINE_VERSION,
            "dlp_ruleset_sha256": "irrelevant-for-this-fixture",
            "received_at": created_at,
            "source": "coordinator",
        }
        store.create_message(self.spool_dir, "inbox", request_id, message, meta)
        store.append_event(self.spool_dir, request_id, "submitted", created_at)
        return request_id, message

    def _run(self, argv, stdin_bytes=b""):
        return helpers.run_main(self.module, ["operator-channel"] + argv, stdin_bytes)


class ListPendingAndShowTests(OperatorChannelTestCase):
    def test_list_pending_includes_submitted_opreq(self):
        request_id, _msg = self._seed_opreq()
        result = self._run(["list-pending"])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertIn(request_id, [item["request_id"] for item in result.json()["items"]])

    def test_list_pending_excludes_accepted_opreq(self):
        request_id, _msg = self._seed_opreq()
        self._run(["accept-request", request_id])
        result = self._run(["list-pending"])
        self.assertNotIn(request_id, [item["request_id"] for item in result.json()["items"]])

    def test_list_pending_excludes_and_marks_expired_opreq(self):
        request_id, _msg = self._seed_opreq(expires_days=-1)
        result = self._run(["list-pending"])
        self.assertNotIn(request_id, [item["request_id"] for item in result.json()["items"]])
        _msg2, _meta, state = store.read_message(self.spool_dir, "inbox", request_id)
        self.assertEqual(state, "expired")

    def test_show_request_finds_inbox_item(self):
        request_id, _msg = self._seed_opreq()
        result = self._run(["show-request", request_id])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["box"], "inbox")

    def test_show_request_unknown_id_is_denied(self):
        result = self._run(["show-request", ids.generate_request_id()])
        self.assertNotEqual(result.exit_code, 0)

    def test_show_status_finds_inbox_and_outbox_items(self):
        request_id, _msg = self._seed_opreq()
        result = self._run(["show-status", request_id])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["box"], "inbox")


class AcceptRejectTests(OperatorChannelTestCase):
    def test_accept_moves_submitted_to_accepted(self):
        request_id, _msg = self._seed_opreq()
        result = self._run(["accept-request", request_id])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["state"], "accepted")

    def test_accept_twice_is_denied(self):
        request_id, _msg = self._seed_opreq()
        self._run(["accept-request", request_id])
        result = self._run(["accept-request", request_id])
        self.assertNotEqual(result.exit_code, 0)

    def test_reject_moves_submitted_to_rejected(self):
        request_id, _msg = self._seed_opreq()
        result = self._run(["reject-request", request_id])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["state"], "rejected")

    def test_accept_after_reject_is_denied(self):
        request_id, _msg = self._seed_opreq()
        self._run(["reject-request", request_id])
        result = self._run(["accept-request", request_id])
        self.assertNotEqual(result.exit_code, 0)

    def test_accept_expired_request_is_denied(self):
        request_id, _msg = self._seed_opreq(expires_days=-1)
        result = self._run(["accept-request", request_id])
        self.assertNotEqual(result.exit_code, 0)
        _msg2, _meta, state = store.read_message(self.spool_dir, "inbox", request_id)
        self.assertEqual(state, "expired")


class ReplyOpresAndDevreqTests(OperatorChannelTestCase):
    def _reply_body(self, **overrides):
        doc = {"schema_version": 1, "purpose": _fixtures.benign_prose(), "expected_result": "何かの確認結果"}
        doc.update(overrides)
        return json.dumps(doc).encode("utf-8")

    def test_reply_opres_requires_accepted_state(self):
        request_id, _msg = self._seed_opreq()  # still "submitted", not accepted
        result = self._run(["reply-opres", request_id], self._reply_body())
        self.assertNotEqual(result.exit_code, 0)

    def test_reply_opres_after_accept_succeeds_and_marks_opreq_answered(self):
        request_id, _msg = self._seed_opreq()
        self._run(["accept-request", request_id])
        result = self._run(["reply-opres", request_id], self._reply_body())
        self.assertEqual(result.exit_code, 0, result.stderr)
        body = result.json()
        self.assertEqual(body["type"], "OPRES")
        _msg2, meta2, state2 = store.read_message(self.spool_dir, "outbox", body["request_id"])
        self.assertEqual(meta2["source"], "operator")
        self.assertEqual(state2, "submitted")
        # the OPREQ itself is now answered
        _opreq_msg, _opreq_meta, opreq_state = store.read_message(self.spool_dir, "inbox", request_id)
        self.assertEqual(opreq_state, "answered")

    def test_reply_opres_inherits_conversation_id(self):
        request_id, opreq_message = self._seed_opreq()
        self._run(["accept-request", request_id])
        result = self._run(["reply-opres", request_id], self._reply_body())
        self.assertEqual(result.json()["conversation_id"], opreq_message["conversation_id"])

    def test_reply_opres_rejects_client_supplied_source(self):
        request_id, _msg = self._seed_opreq()
        self._run(["accept-request", request_id])
        result = self._run(["reply-opres", request_id], self._reply_body(source="operator"))
        self.assertNotEqual(result.exit_code, 0)

    def test_reply_opres_dlp_blocks_secret_without_leaking_it(self):
        request_id, _msg = self._seed_opreq()
        self._run(["accept-request", request_id])
        secret = _fixtures.pem_private_key_block()
        result = self._run(["reply-opres", request_id], self._reply_body(purpose=secret))
        self.assertNotEqual(result.exit_code, 0)
        self.assertNotIn(secret, result.stdout)
        self.assertNotIn(secret, result.stderr)
        # nothing landed in outbox
        self.assertEqual(store.count_and_size(self.spool_dir, "outbox")[0], 0)

    def test_reply_opres_beyond_max_ttl_is_denied(self):
        request_id, _msg = self._seed_opreq()
        self._run(["accept-request", request_id])
        far_future = (datetime.now(JST) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S%z")
        result = self._run(["reply-opres", request_id], self._reply_body(expires_at=far_future))
        self.assertNotEqual(result.exit_code, 0)

    def test_new_devreq_standalone_creates_its_own_conversation(self):
        result = self._run(["new-devreq"], self._reply_body())
        self.assertEqual(result.exit_code, 0, result.stderr)
        body = result.json()
        self.assertEqual(body["type"], "DEVREQ")
        message, _meta, _state = store.read_message(self.spool_dir, "outbox", body["request_id"])
        self.assertIsNone(message.get("in_reply_to"))
        self.assertTrue(ids.is_valid_conversation_id(message["conversation_id"]))

    def test_new_devreq_reply_requires_accepted_opreq(self):
        request_id, _msg = self._seed_opreq()  # still submitted
        result = self._run(["new-devreq"], self._reply_body(in_reply_to=request_id))
        self.assertNotEqual(result.exit_code, 0)

    def test_new_devreq_reply_after_accept_marks_opreq_answered(self):
        request_id, opreq_message = self._seed_opreq()
        self._run(["accept-request", request_id])
        result = self._run(["new-devreq"], self._reply_body(in_reply_to=request_id))
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["conversation_id"], opreq_message["conversation_id"])
        _opreq_msg, _opreq_meta, opreq_state = store.read_message(self.spool_dir, "inbox", request_id)
        self.assertEqual(opreq_state, "answered")

    def test_new_devreq_with_unknown_in_reply_to_is_denied(self):
        result = self._run(["new-devreq"], self._reply_body(in_reply_to=ids.generate_request_id()))
        self.assertNotEqual(result.exit_code, 0)

    def test_time_not_synchronised_blocks_new_devreq(self):
        with helpers.patch_time_synced(oprc_config, synced=False):
            result = self._run(["new-devreq"], self._reply_body())
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(store.count_and_size(self.spool_dir, "outbox")[0], 0)

    def test_configured_max_clock_offset_seconds_reaches_assert_time_synced(self):
        # review 2026-08-08_006 Suggestion 1 -- see the identical test in
        # test_entrypoint_oprc_receive.py for why assert_time_synced
        # itself is mocked rather than chronyc.
        doc = json.load(open(self.config_path, encoding="utf-8"))
        doc["max_clock_offset_seconds"] = 7.25
        helpers.write_config(self.config_path, **doc)
        with mock.patch.object(oprc_config, "assert_time_synced", return_value=None) as mock_synced:
            result = self._run(["new-devreq"], self._reply_body())
        self.assertEqual(result.exit_code, 0, result.stderr)
        mock_synced.assert_called_once()
        _args, kwargs = mock_synced.call_args
        self.assertEqual(kwargs.get("max_offset_seconds"), 7.25)


class ShowConversationTests(OperatorChannelTestCase):
    def test_show_conversation_groups_opreq_and_opres(self):
        request_id, opreq_message = self._seed_opreq()
        self._run(["accept-request", request_id])
        self._run(["reply-opres", request_id], json.dumps({"schema_version": 1, "purpose": _fixtures.benign_prose()}).encode("utf-8"))
        result = self._run(["show-conversation", opreq_message["conversation_id"]])
        self.assertEqual(result.exit_code, 0, result.stderr)
        boxes = sorted(item["box"] for item in result.json()["items"])
        self.assertEqual(boxes, ["inbox", "outbox"])

    def test_show_conversation_rejects_malformed_id(self):
        result = self._run(["show-conversation", "not-a-conversation-id"])
        self.assertNotEqual(result.exit_code, 0)


class R1BoundaryTests(OperatorChannelTestCase):
    """requirement §11 / plan R-1: this CLI has no command that edits or
    deletes a message body, and no command reachable from here changes
    production state (systemctl/sudo/ansible/git). These are structural
    properties of main()'s fixed command table, verified here by asserting
    the forbidden verbs are not recognized at all."""

    def test_no_delete_command_exists(self):
        for verb in ("delete-request", "delete-message", "remove-request", "edit-request", "update-request"):
            result = self._run([verb])
            self.assertNotEqual(result.exit_code, 0, "verb should not exist: {}".format(verb))
            self.assertIn("denied:", result.stderr)

    def test_module_has_no_subprocess_or_shell_usage(self):
        # A bare substring check for "subprocess" would false-positive on
        # this file's own module docstring, which discusses (and
        # disclaims) subprocess usage in prose -- check for actual usage
        # patterns instead.
        with open(os.path.join(_path_setup._OPRC_FILES_DIR, "bin", "operator-channel"), encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("subprocess.run(", source)
        self.assertNotIn("subprocess.Popen(", source)
        self.assertNotIn("subprocess.call(", source)
        self.assertNotIn("os.system(", source)
        self.assertNotIn("shell=True", source)


class UncaughtExceptionSafetyTests(OperatorChannelTestCase):
    """deploy-verification 2026-08-08_010 item 2 -- see the identical test
    class in test_entrypoint_oprc_receive.py for the full rationale. Any
    exception `_dispatch()` did not anticipate must become the same
    value-free `error:` line every other failure path here produces, never
    a raw traceback."""

    def test_root_cause_class_name_and_errno_survive_a_wrapped_exception(self):
        # Reproduces the exact production incident (2026-08-08 post-deploy
        # vertical test): accept-request failed with `error: unexpected
        # internal failure (StoreError)` -- the *outer* wrapper's class
        # name only -- while the real cause (a PermissionError, errno 13,
        # from the events/ ACL-mask bug) was invisible on either side of
        # the SSH boundary; Coordinator had to ask Operator to run
        # `getfacl` by hand to find it. This raises the exact shape
        # `store.append_event()` itself raises when `os.open()` fails
        # (`except OSError as exc: raise StoreError(...)`, which leaves
        # Python's implicit `__context__` chaining intact) so the test
        # exercises the real chain-walking path, not a synthetic one.
        request_id, _msg = self._seed_opreq()

        def raise_wrapped_permission_error(*_args, **_kwargs):
            try:
                raise PermissionError(13, "Permission denied")
            except OSError as exc:
                raise store.StoreError("cannot open event log: {}".format(type(exc).__name__))

        with mock.patch.object(store, "append_event", side_effect=raise_wrapped_permission_error):
            result = self._run(["accept-request", request_id])
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertIn("StoreError", result.stderr)  # outer class, as before
        self.assertIn("PermissionError", result.stderr)  # root cause class -- this is the fix
        self.assertIn("errno=13", result.stderr)  # errno -- this is the fix
        self.assertNotIn("Permission denied", combined)  # message body still never appears
        self.assertNotIn("cannot open event log", combined)  # nor the wrapper's own message
        self.assertNotIn("Traceback", combined)

    def test_unexpected_exception_during_accept_does_not_leak_a_traceback(self):
        request_id, _msg = self._seed_opreq()
        marker = "SENSITIVE-MARKER-accept-request"
        with mock.patch.object(store, "append_event", side_effect=RuntimeError(marker)):
            result = self._run(["accept-request", request_id])
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(marker, combined)
        self.assertNotIn("Traceback", combined)
        self.assertIn("error:", result.stderr)
        self.assertIn("RuntimeError", result.stderr)

    def test_unexpected_exception_during_reply_opres_does_not_leak_a_traceback(self):
        request_id, _msg = self._seed_opreq()
        self._run(["accept-request", request_id])
        marker = "SENSITIVE-MARKER-reply-opres"
        with mock.patch.object(canonical, "content_hash", side_effect=RuntimeError(marker)):
            result = self._run(
                ["reply-opres", request_id],
                json.dumps({"schema_version": 1, "purpose": _fixtures.benign_prose()}).encode("utf-8"),
            )
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(marker, combined)
        self.assertNotIn("Traceback", combined)

    def test_exception_message_body_containing_a_pseudo_secret_is_not_leaked(self):
        request_id, _msg = self._seed_opreq()
        secret = _fixtures.password_keyvalue_text()
        with mock.patch.object(store, "append_event", side_effect=RuntimeError("failed handling request: " + secret)):
            result = self._run(["accept-request", request_id])
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(secret, combined)
        self.assertNotIn("failed handling request", combined)
        self.assertIn("error:", result.stderr)
        self.assertIn("RuntimeError", result.stderr)

    def test_permission_error_message_body_containing_a_pseudo_secret_is_not_leaked(self):
        request_id, _msg = self._seed_opreq()
        secret = _fixtures.slack_bot_token()
        with mock.patch.object(store, "append_event", side_effect=PermissionError(13, "denied near " + secret)):
            result = self._run(["accept-request", request_id])
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(secret, combined)
        self.assertIn("PermissionError", result.stderr)

    def test_uses_the_shared_run_entrypoint_safety_net(self):
        with mock.patch.object(lifecycle, "run_entrypoint") as mock_run:
            self._run(["list-pending"])
        mock_run.assert_called_once()
        args, _kwargs = mock_run.call_args
        self.assertIs(args[0], self.module._dispatch)

    def test_systemexit_from_deny_is_not_swallowed_by_the_catch_all(self):
        result = self._run(["totally-bogus-command"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("denied:", result.stderr)
        self.assertNotIn("unexpected internal failure", result.stderr)


if __name__ == "__main__":
    unittest.main()
