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


class OprcReceiveTestCase(unittest.TestCase):
    """Base fixture: a fresh spool + a real (repo) schema/ruleset, config.json
    patched via CONFIG_PATH, `config.assert_time_synced` patched to a no-op
    success so the time-sync gate (plan §2.11) passes by default -- tests
    that need it to fail use `helpers.patch_time_synced(oprc_config,
    synced=False)` instead (see that helper's docstring for why this is not
    done via CHRONYC_PATH)."""

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

        self.module = helpers.load_entrypoint("oprc-receive")
        self._synced_patch = helpers.patch_time_synced(oprc_config, synced=True)
        self._synced_patch.start()
        self.addCleanup(self._synced_patch.stop)
        self._config_patch = mock.patch.object(self.module, "CONFIG_PATH", self.config_path)
        self._config_patch.start()
        self.addCleanup(self._config_patch.stop)

    def _submit(self, payload_dict):
        return helpers.run_main(self.module, ["oprc-receive", "submit"], json.dumps(payload_dict).encode("utf-8"))

    def _valid_opreq(self, **overrides):
        doc = {
            "schema_version": 1,
            "conversation_id": ids.generate_conversation_id(),
            "type": "OPREQ",
            "purpose": _fixtures.benign_prose(),
            "target_names": ["quory"],
        }
        doc.update(overrides)
        return doc


class SubmitTests(OprcReceiveTestCase):
    def test_valid_opreq_is_accepted_and_stored(self):
        result = self._submit(self._valid_opreq())
        self.assertEqual(result.exit_code, 0, result.stderr)
        body = result.json()
        self.assertTrue(ids.is_valid_request_id(body["request_id"]))
        # stored, immutable, with a submitted event
        from oprc import store

        message, meta, state = store.read_message(self.spool_dir, "inbox", body["request_id"])
        self.assertEqual(message["source"], "coordinator")
        self.assertEqual(message["type"], "OPREQ")
        self.assertEqual(state, "submitted")
        self.assertEqual(meta["content_sha256"], canonical.content_hash(message))

    def test_client_supplied_request_id_is_rejected(self):
        result = self._submit(self._valid_opreq(request_id="req-20260808T000000+0900-" + "0" * 16))
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("denied:", result.stderr)

    def test_client_supplied_source_is_rejected(self):
        result = self._submit(self._valid_opreq(source="coordinator"))
        self.assertNotEqual(result.exit_code, 0)

    def test_client_supplied_created_at_is_rejected(self):
        result = self._submit(self._valid_opreq(created_at="2026-08-08T00:00:00+0900"))
        self.assertNotEqual(result.exit_code, 0)

    def test_opres_type_from_ansy_is_rejected(self):
        # requirement §4.2 allow-matrix: coordinator (this entry point) may
        # only create OPREQ.
        result = self._submit(self._valid_opreq(type="OPRES", in_reply_to=None))
        self.assertNotEqual(result.exit_code, 0)

    def test_devreq_type_from_ansy_is_rejected(self):
        result = self._submit(self._valid_opreq(type="DEVREQ"))
        self.assertNotEqual(result.exit_code, 0)

    def test_dlp_blocked_payload_is_rejected_without_leaking_the_secret(self):
        secret = _fixtures.slack_bot_token()
        result = self._submit(self._valid_opreq(purpose=secret))
        self.assertNotEqual(result.exit_code, 0)
        self.assertNotIn(secret, result.stdout)
        self.assertNotIn(secret, result.stderr)
        with open(self.audit_log, encoding="utf-8") as f:
            audit_text = f.read()
        self.assertNotIn(secret, audit_text)

    def test_expires_at_beyond_max_ttl_is_rejected(self):
        far_future = (datetime.now(JST) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S%z")
        result = self._submit(self._valid_opreq(expires_at=far_future))
        self.assertNotEqual(result.exit_code, 0)

    def test_expires_at_omitted_gets_default_ttl(self):
        result = self._submit(self._valid_opreq())
        self.assertEqual(result.exit_code, 0, result.stderr)
        from oprc import store

        message, _meta, _state = store.read_message(self.spool_dir, "inbox", result.json()["request_id"])
        self.assertIn("expires_at", message)

    def test_time_not_synchronised_blocks_submit(self):
        with helpers.patch_time_synced(oprc_config, synced=False):
            result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)
        from oprc import store

        self.assertEqual(store.count_and_size(self.spool_dir, "inbox")[0], 0)

    def test_configured_max_clock_offset_seconds_reaches_assert_time_synced(self):
        # review 2026-08-08_006 Suggestion 1: config.json's
        # max_clock_offset_seconds must actually be threaded through to
        # config.assert_time_synced(), not silently ignored in favor of
        # its own function default. Mocking assert_time_synced itself
        # (rather than chronyc) is deliberate: assert_time_synced's
        # `chronyc_path` parameter default is frozen at function-definition
        # time (see helpers.patch_time_synced's docstring for the exact
        # mechanism), so patching CHRONYC_PATH after the fact would not
        # reliably control it here either -- inspecting the call arguments
        # is what actually proves the wiring. That the max_offset_seconds
        # argument genuinely gates the outcome is already proven at the
        # library layer by test_config.py's TimeSyncTests.
        doc = json.load(open(self.config_path, encoding="utf-8"))
        doc["max_clock_offset_seconds"] = 12.5
        helpers.write_config(self.config_path, **doc)
        with mock.patch.object(oprc_config, "assert_time_synced", return_value=None) as mock_synced:
            result = self._submit(self._valid_opreq())
        self.assertEqual(result.exit_code, 0, result.stderr)
        mock_synced.assert_called_once()
        _args, kwargs = mock_synced.call_args
        self.assertEqual(kwargs.get("max_offset_seconds"), 12.5)

    def test_channel_disabled_blocks_submit(self):
        helpers.write_config(
            self.config_path,
            **{**json.load(open(self.config_path, encoding="utf-8")), "channel_enabled": False},
        )
        result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("denied:", result.stderr)

    def test_capacity_exceeded_blocks_submit(self):
        with mock.patch.object(store, "check_capacity", side_effect=store.StoreCapacityExceeded("full")):
            result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)

    def test_extra_argument_to_submit_is_denied(self):
        result = helpers.run_main(self.module, ["oprc-receive", "submit", "extra"])
        self.assertNotEqual(result.exit_code, 0)

    def test_malformed_json_is_denied(self):
        result = helpers.run_main(self.module, ["oprc-receive", "submit"], b"{not json")
        self.assertNotEqual(result.exit_code, 0)

    def test_oversized_payload_is_denied(self):
        big = self._valid_opreq(purpose="x" * 200000)
        result = self._submit(big)
        self.assertNotEqual(result.exit_code, 0)


class OutboundListAndGetTests(OprcReceiveTestCase):
    def _seed_outbox_message(self, msg_type="OPRES", in_reply_to=None, expires_days=7):
        from oprc import store

        request_id = ids.generate_request_id()
        created_at = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z")
        message = {
            "schema_version": 1,
            "request_id": request_id,
            "conversation_id": ids.generate_conversation_id(),
            "type": msg_type,
            "source": "operator",
            "created_at": created_at,
            "expires_at": (datetime.now(JST) + timedelta(days=expires_days)).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "purpose": _fixtures.benign_prose(),
        }
        if in_reply_to:
            message["in_reply_to"] = in_reply_to
        meta = {
            "content_sha256": canonical.content_hash(message),
            "dlp_engine_version": dlp.ENGINE_VERSION,
            "dlp_ruleset_sha256": "irrelevant-for-this-fixture",
            "received_at": created_at,
            "source": "operator",
        }
        store.create_message(self.spool_dir, "outbox", request_id, message, meta)
        store.append_event(self.spool_dir, request_id, "submitted", created_at)
        return request_id, message

    def test_outbound_list_returns_seeded_message(self):
        request_id, _msg = self._seed_outbox_message()
        result = helpers.run_main(self.module, ["oprc-receive", "outbound-list"])
        self.assertEqual(result.exit_code, 0, result.stderr)
        ids_seen = [item["request_id"] for item in result.json()["items"]]
        self.assertIn(request_id, ids_seen)

    def test_outbound_list_rejects_malformed_cursor(self):
        result = helpers.run_main(self.module, ["oprc-receive", "outbound-list", "not-a-request-id"])
        self.assertNotEqual(result.exit_code, 0)

    def test_message_get_returns_full_body(self):
        request_id, message = self._seed_outbox_message()
        result = helpers.run_main(self.module, ["oprc-receive", "message-get", request_id])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["message"]["request_id"], request_id)

    def test_message_get_for_inbox_only_id_is_not_found(self):
        # OPREQ ansy submitted lives in inbox/, not outbox/; message-get is
        # scoped to outbox (requirement §5.1 "request IDによる OPRES／DEVREQ
        # 取得" -- OPREQ retrieval is not part of ansy's operation set).
        result = self._submit(self._valid_opreq())
        request_id = result.json()["request_id"]
        get_result = helpers.run_main(self.module, ["oprc-receive", "message-get", request_id])
        self.assertNotEqual(get_result.exit_code, 0)

    def test_message_get_rejects_malformed_id(self):
        result = helpers.run_main(self.module, ["oprc-receive", "message-get", "../../etc/passwd"])
        self.assertNotEqual(result.exit_code, 0)

    def test_message_get_marks_expired_message(self):
        request_id, _msg = self._seed_outbox_message(expires_days=-1)
        result = helpers.run_main(self.module, ["oprc-receive", "message-get", request_id])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["state"], "expired")

    def test_request_status_for_outbox_item(self):
        request_id, _msg = self._seed_outbox_message()
        result = helpers.run_main(self.module, ["oprc-receive", "request-status", request_id])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["state"], "submitted")

    def test_request_status_for_inbox_item_uses_event_log_only(self):
        # dev-investigate has no read on inbox/ message bodies (this
        # implementer's ACL design, see roles/operator_request_channel/
        # defaults/main.yml's header comment) -- request-status for an
        # OPREQ ansy itself submitted must still work, via the event log.
        submit_result = self._submit(self._valid_opreq())
        request_id = submit_result.json()["request_id"]
        status_result = helpers.run_main(self.module, ["oprc-receive", "request-status", request_id])
        self.assertEqual(status_result.exit_code, 0, status_result.stderr)
        self.assertEqual(status_result.json()["state"], "submitted")

    def test_request_status_for_unknown_id_is_not_found(self):
        bogus = ids.generate_request_id()
        result = helpers.run_main(self.module, ["oprc-receive", "request-status", bogus])
        self.assertNotEqual(result.exit_code, 0)


class RetryDoesNotDuplicateOrOverwriteTests(OprcReceiveTestCase):
    """requirement §18.2 "通信切断後の再試行で重複または上書きが起きない
    こと". In this design request_id is always freshly minted server-side
    (never client-supplied), so an ordinary client retry after a dropped
    connection produces a *second, distinct* request rather than literally
    resubmitting the same id -- there is no "retry with the same id" concept
    to test directly. What *is* directly testable, and is the actual
    mechanism this property depends on, is that two submissions that
    happen to mint the same request_id (the pathological case a retry
    racing itself, or a broken id generator, would produce) cannot
    overwrite or duplicate each other -- the second one is rejected, not
    silently merged."""

    def test_colliding_request_id_is_rejected_not_overwritten(self):
        fixed_id = ids.generate_request_id()
        with mock.patch.object(ids, "generate_request_id", return_value=fixed_id):
            first = self._submit(self._valid_opreq(purpose="first submission"))
            self.assertEqual(first.exit_code, 0, first.stderr)
            second = self._submit(self._valid_opreq(purpose="second submission, different content"))
        self.assertNotEqual(second.exit_code, 0)

        stored_message, _meta, _state = store.read_message(self.spool_dir, "inbox", fixed_id)
        self.assertEqual(stored_message["purpose"], "first submission")


class UnknownActionTests(OprcReceiveTestCase):
    def test_unknown_action_is_denied(self):
        result = helpers.run_main(self.module, ["oprc-receive", "totally-bogus"])
        self.assertNotEqual(result.exit_code, 0)

    def test_missing_action_is_denied(self):
        result = helpers.run_main(self.module, ["oprc-receive"])
        self.assertNotEqual(result.exit_code, 0)


class UncaughtExceptionSafetyTests(OprcReceiveTestCase):
    """deploy-verification 2026-08-08_010 item 2: an exception `_dispatch()`
    did not anticipate (the real-world case was a `PermissionError` from
    `store.count_and_size()`, item 1) must not leak a raw traceback -- or
    any fragment of the exception's own message, which could in principle
    echo payload-derived content -- to stdout or stderr. It must become
    the same value-free `error:` line every other failure path in this
    file produces."""

    def test_chain_reports_both_outer_and_wrapped_exception_class_name_and_errno(self):
        # Reproduces the exact production incident (2026-08-08 post-deploy
        # vertical test) at the entry point where a symmetric version of
        # the same bug is reachable: dev-investigate's lazy-expiry check
        # can append "expired" to an events/ file yoshi created for an
        # outbox entry (store.mark_expired_if_needed -> append_event), so
        # this file's entry point can hit the same wrapped-PermissionError
        # shape too. See test_entrypoint_operator_channel.py's identical
        # test for the full incident description. The chain here has
        # exactly two links (StoreError, PermissionError); the
        # control-flow-handler test below covers a three-link chain.
        def raise_wrapped_permission_error(*_args, **_kwargs):
            try:
                raise PermissionError(13, "Permission denied")
            except OSError as exc:
                raise store.StoreError("cannot open event log: {}".format(type(exc).__name__))

        with mock.patch.object(store, "check_capacity", side_effect=raise_wrapped_permission_error):
            result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertIn("StoreError", result.stderr)
        self.assertIn("PermissionError", result.stderr)
        self.assertIn("errno=13", result.stderr)
        self.assertNotIn("Permission denied", combined)
        self.assertNotIn("cannot open event log", combined)
        self.assertNotIn("Traceback", combined)

    def test_intermediate_exception_inside_a_control_flow_except_handler_is_not_hidden(self):
        # See test_entrypoint_operator_channel.py's identical test for the
        # full incident description and rationale (2026-08-08,
        # `_013_review_event_mode.md` follow-up): `store.append_event()`'s
        # `except FileExistsError:` branch is not itself a failure -- it
        # means "someone else already created this file, append instead" --
        # but if the code *inside* that handler then raises, Python's
        # implicit exception chaining links the new exception's
        # `__context__` to the `FileExistsError` being handled at the time.
        # The previous single-innermost-exception walk (`_root_cause()`,
        # since removed) landed on that harmless `FileExistsError` (errno
        # 17, EEXIST) and silently dropped the real failure sitting one
        # link closer to the surface -- exactly the shape of the quory
        # incident this differential reports (`error: unexpected internal
        # failure (StoreError, root=FileExistsError, errno=17)`).
        def raise_from_within_a_control_flow_except_handler(*_args, **_kwargs):
            try:
                raise FileExistsError(17, "File exists")
            except FileExistsError:
                try:
                    raise PermissionError(13, "Permission denied")
                except OSError as exc:
                    raise store.StoreError("cannot open event log: {}".format(type(exc).__name__))

        with mock.patch.object(store, "check_capacity", side_effect=raise_from_within_a_control_flow_except_handler):
            result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertIn("StoreError", result.stderr)  # outer wrapper
        self.assertIn("PermissionError", result.stderr)  # the real failure -- must not be hidden
        self.assertIn("errno=13", result.stderr)
        self.assertIn("FileExistsError", result.stderr)  # the harmless control-flow exception may still appear...
        self.assertIn("errno=17", result.stderr)  # ...but must not be the *only* thing reported
        self.assertNotIn("Permission denied", combined)
        self.assertNotIn("File exists", combined)
        self.assertNotIn("cannot open event log", combined)
        self.assertNotIn("Traceback", combined)

    def test_unexpected_exception_during_submit_does_not_leak_a_traceback(self):
        marker = "SENSITIVE-MARKER-should-never-reach-output"
        with mock.patch.object(store, "check_capacity", side_effect=RuntimeError(marker)):
            result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(marker, combined)
        self.assertNotIn("Traceback", combined)
        self.assertNotIn("cmd_submit", combined)  # no stack frame text at all
        self.assertIn("error:", result.stderr)
        self.assertIn("RuntimeError", result.stderr)  # the exception class name alone is safe

    def test_the_exact_permission_error_observed_in_deploy_verification_does_not_leak_a_traceback(self):
        with mock.patch.object(store, "check_capacity", side_effect=PermissionError(13, "Permission denied")):
            result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn("Traceback", combined)
        self.assertNotIn("os.listdir", combined)
        self.assertIn("PermissionError", result.stderr)

    def test_unexpected_exception_during_message_get_does_not_leak_a_traceback(self):
        marker = "SENSITIVE-MARKER-message-get"
        with mock.patch.object(store, "read_message", side_effect=RuntimeError(marker)):
            result = helpers.run_main(self.module, ["oprc-receive", "message-get", ids.generate_request_id()])
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(marker, combined)
        self.assertNotIn("Traceback", combined)

    def test_exception_message_body_containing_a_pseudo_secret_is_not_leaked(self):
        # Operator review: the earlier tests here only ever checked the
        # exception *class name*'s absence/presence -- none put a
        # secret-shaped string inside the exception's own *message*. An
        # exception raised while processing a payload can plausibly embed
        # a fragment of what it was processing in its own str(); this
        # proves run_entrypoint() drops that message entirely, not just
        # that it drops a generic marker.
        secret = _fixtures.password_keyvalue_text()
        with mock.patch.object(store, "check_capacity", side_effect=RuntimeError("failed handling request: " + secret)):
            result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(secret, combined)
        self.assertNotIn("failed handling request", combined)
        self.assertIn("error:", result.stderr)
        self.assertIn("RuntimeError", result.stderr)

    def test_permission_error_message_body_containing_a_pseudo_secret_is_not_leaked(self):
        secret = _fixtures.slack_bot_token()
        with mock.patch.object(store, "check_capacity", side_effect=PermissionError(13, "denied near " + secret)):
            result = self._submit(self._valid_opreq())
        self.assertNotEqual(result.exit_code, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(secret, combined)
        self.assertIn("PermissionError", result.stderr)

    def test_uses_the_shared_run_entrypoint_safety_net(self):
        # Consolidation check (Operator review): main() must go through
        # oprc.lifecycle.run_entrypoint(), not a locally-defined
        # try/except -- patch run_entrypoint itself and confirm main()
        # actually calls it (rather than merely producing the same
        # observable behavior via a parallel implementation).
        with mock.patch.object(lifecycle, "run_entrypoint") as mock_run:
            helpers.run_main(self.module, ["oprc-receive", "outbound-list"])
        mock_run.assert_called_once()
        args, _kwargs = mock_run.call_args
        self.assertIs(args[0], self.module._dispatch)

    def test_systemexit_from_deny_is_not_swallowed_by_the_catch_all(self):
        # Sanity check on the catch-all's own boundary: normal denied:
        # exits (SystemExit, not a subclass of Exception) must still work
        # exactly as before -- the safety net must not turn every denial
        # into a generic "unexpected internal failure".
        result = helpers.run_main(self.module, ["oprc-receive", "totally-bogus-action"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("denied:", result.stderr)
        self.assertNotIn("unexpected internal failure", result.stderr)


class ReachabilityBoundaryTests(unittest.TestCase):
    """requirement §10.2/§18.2: this forced-command backend must never
    reach Semaphore, systemctl, sudo, Ansible, Git, or an arbitrary path.
    Verified structurally: no subprocess/shell facility appears in the
    file at all, so there is no code path to any external command
    (unlike operator-channel-client, which legitimately shells out to
    `ssh` -- that check lives in that file's own test module)."""

    def test_module_has_no_subprocess_or_shell_usage(self):
        with open(os.path.join(_path_setup._OPRC_FILES_DIR, "bin", "oprc-receive"), encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("subprocess.run(", source)
        self.assertNotIn("subprocess.Popen(", source)
        self.assertNotIn("subprocess.call(", source)
        self.assertNotIn("os.system(", source)
        self.assertNotIn("shell=True", source)


if __name__ == "__main__":
    unittest.main()
