import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import _entrypoint_helpers as helpers
import _fixtures
import _path_setup  # noqa: F401

from oprc import canonical, dlp, ids

JST = timezone(timedelta(hours=9))


class OperatorChannelClientTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_path = os.path.join(self.tmp.name, "config.json")

        with open(_path_setup.SCHEMA_PATH, "rb") as f:
            self.schema_hash = canonical.sha256_hex(f.read())
        with open(_path_setup.DLP_RULES_PATH, "rb") as f:
            self.ruleset_hash = canonical.sha256_hex(f.read())

        helpers.write_config(
            self.config_path,
            config_version=1,
            role="coordinator",
            channel_enabled=True,
            libexec_dir=_path_setup._OPRC_FILES_DIR,
            schema_path=_path_setup.SCHEMA_PATH,
            dlp_rules_path=_path_setup.DLP_RULES_PATH,
            expected_schema_sha256=self.schema_hash,
            expected_dlp_engine_version=dlp.ENGINE_VERSION,
            expected_dlp_ruleset_sha256=self.ruleset_hash,
            max_payload_bytes=65536,
            dlp_timeout_seconds=5,
            ssh_destination="quory-investigate-test",
            ssh_connect_timeout_seconds=1,
        )

        self.module = helpers.load_entrypoint("operator-channel-client")
        self._config_patch = mock.patch.object(self.module, "CONFIG_PATH", self.config_path)
        self._config_patch.start()
        self.addCleanup(self._config_patch.stop)

    def _run(self, argv, stdin_bytes=b""):
        return helpers.run_main(self.module, ["operator-channel-client"] + argv, stdin_bytes)

    def _valid_opreq_body(self, **overrides):
        # No conversation_id here on purpose -- cmd_submit generates its
        # own for a fresh OPREQ (§6.2); a test that wants to verify the
        # client refuses a caller-supplied one can pass it via overrides.
        doc = {
            "schema_version": 1,
            "type": "OPREQ",
            "purpose": _fixtures.benign_prose(),
            "target_names": ["quory"],
        }
        doc.update(overrides)
        return json.dumps(doc).encode("utf-8")

    def _sample_outbox_message(self, request_id=None, purpose=None):
        request_id = request_id or ids.generate_request_id()
        message = {
            "schema_version": 1,
            "request_id": request_id,
            "conversation_id": ids.generate_conversation_id(),
            "type": "OPRES",
            "source": "operator",
            "created_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "expires_at": (datetime.now(JST) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "purpose": purpose or _fixtures.benign_prose(),
        }
        meta = {
            "content_sha256": canonical.content_hash(message),
            "dlp_engine_version": dlp.ENGINE_VERSION,
            "dlp_ruleset_sha256": self.ruleset_hash,
            "received_at": message["created_at"],
        }
        return message, meta


class SubmitTests(OperatorChannelClientTestCase):
    def test_submit_calls_ssh_with_expected_remote_argv(self):
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps({"request_id": "req-x"}).encode("utf-8")) as mock_ssh:
            result = self._run(["submit"], self._valid_opreq_body())
        self.assertEqual(result.exit_code, 0, result.stderr)
        mock_ssh.assert_called_once()
        args, kwargs = mock_ssh.call_args
        self.assertEqual(args[1], ["operator-request-submit"])
        self.assertIn("stdin_bytes", kwargs)

    def test_submit_never_sends_server_assigned_fields(self):
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps({"request_id": "req-x"}).encode("utf-8")) as mock_ssh:
            self._run(["submit"], self._valid_opreq_body())
        sent_bytes = mock_ssh.call_args.kwargs["stdin_bytes"]
        sent = json.loads(sent_bytes)
        self.assertNotIn("request_id", sent)
        self.assertNotIn("source", sent)
        self.assertNotIn("created_at", sent)

    def test_submit_rejects_client_supplied_request_id_before_calling_ssh(self):
        with mock.patch.object(self.module, "_run_ssh") as mock_ssh:
            result = self._run(["submit"], self._valid_opreq_body(request_id="req-forged"))
        self.assertNotEqual(result.exit_code, 0)
        mock_ssh.assert_not_called()

    def test_submit_rejects_non_opreq_type_before_calling_ssh(self):
        with mock.patch.object(self.module, "_run_ssh") as mock_ssh:
            result = self._run(["submit"], self._valid_opreq_body(type="OPRES"))
        self.assertNotEqual(result.exit_code, 0)
        mock_ssh.assert_not_called()

    def test_submit_dlp_blocks_secret_before_calling_ssh(self):
        secret = _fixtures.credential_url_text()
        with mock.patch.object(self.module, "_run_ssh") as mock_ssh:
            result = self._run(["submit"], self._valid_opreq_body(purpose=secret))
        self.assertNotEqual(result.exit_code, 0)
        mock_ssh.assert_not_called()
        self.assertNotIn(secret, result.stdout)
        self.assertNotIn(secret, result.stderr)

    def test_submit_shape_error_is_caught_locally_before_calling_ssh(self):
        # purpose exceeds request-schema-v1.json's maxLength (4096)
        with mock.patch.object(self.module, "_run_ssh") as mock_ssh:
            result = self._run(["submit"], self._valid_opreq_body(purpose="x" * 5000))
        self.assertNotEqual(result.exit_code, 0)
        mock_ssh.assert_not_called()

    def test_submit_generates_its_own_conversation_id(self):
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps({"request_id": "req-x"}).encode("utf-8")) as mock_ssh:
            self._run(["submit"], self._valid_opreq_body())
        sent = json.loads(mock_ssh.call_args.kwargs["stdin_bytes"])
        self.assertTrue(ids.is_valid_conversation_id(sent["conversation_id"]))


class ListStatusTests(OperatorChannelClientTestCase):
    def test_list_passes_cursor_through(self):
        cursor = ids.generate_request_id()
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps({"items": [], "next_cursor": None}).encode("utf-8")) as mock_ssh:
            result = self._run(["list", cursor])
        self.assertEqual(result.exit_code, 0, result.stderr)
        args, _kwargs = mock_ssh.call_args
        self.assertEqual(args[1], ["operator-outbound-list", cursor])

    def test_list_rejects_malformed_cursor_before_calling_ssh(self):
        with mock.patch.object(self.module, "_run_ssh") as mock_ssh:
            result = self._run(["list", "not-a-cursor"])
        self.assertNotEqual(result.exit_code, 0)
        mock_ssh.assert_not_called()

    def test_status_passes_through(self):
        request_id = ids.generate_request_id()
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps({"request_id": request_id, "state": "accepted"}).encode("utf-8")):
            result = self._run(["status", request_id])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["state"], "accepted")


class GetTests(OperatorChannelClientTestCase):
    def test_get_valid_message_is_printed(self):
        message, meta = self._sample_outbox_message()
        response = {"message": message, "meta": meta, "state": "submitted"}
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps(response).encode("utf-8")):
            result = self._run(["get", message["request_id"]])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.json()["message"]["request_id"], message["request_id"])

    def test_get_detects_content_hash_tampering(self):
        message, meta = self._sample_outbox_message()
        tampered = dict(message)
        tampered["purpose"] = "altered in transit"
        response = {"message": tampered, "meta": meta, "state": "submitted"}
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps(response).encode("utf-8")):
            result = self._run(["get", message["request_id"]])
        self.assertNotEqual(result.exit_code, 0)

    def test_get_detects_dlp_ruleset_hash_mismatch(self):
        message, meta = self._sample_outbox_message()
        meta = dict(meta)
        meta["dlp_ruleset_sha256"] = "0" * 64
        response = {"message": message, "meta": meta, "state": "submitted"}
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps(response).encode("utf-8")):
            result = self._run(["get", message["request_id"]])
        self.assertNotEqual(result.exit_code, 0)

    def test_get_detects_dlp_engine_version_mismatch(self):
        message, meta = self._sample_outbox_message()
        meta = dict(meta)
        meta["dlp_engine_version"] = "999"
        response = {"message": message, "meta": meta, "state": "submitted"}
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps(response).encode("utf-8")):
            result = self._run(["get", message["request_id"]])
        self.assertNotEqual(result.exit_code, 0)

    def test_get_dlp_blocks_secret_on_intake(self):
        secret = _fixtures.jwt_text()
        message, meta = self._sample_outbox_message(purpose=secret)
        response = {"message": message, "meta": meta, "state": "submitted"}
        with mock.patch.object(self.module, "_run_ssh", return_value=json.dumps(response).encode("utf-8")):
            result = self._run(["get", message["request_id"]])
        self.assertNotEqual(result.exit_code, 0)
        self.assertNotIn(secret, result.stdout)
        self.assertNotIn(secret, result.stderr)

    def test_get_rejects_malformed_request_id_before_calling_ssh(self):
        with mock.patch.object(self.module, "_run_ssh") as mock_ssh:
            result = self._run(["get", "not-a-request-id"])
        self.assertNotEqual(result.exit_code, 0)
        mock_ssh.assert_not_called()


class RunSshTests(OperatorChannelClientTestCase):
    """Exercises the real `_run_ssh` (not mocked) against a fake `ssh`
    binary standing in on PATH-independent grounds -- subprocess.run itself
    is mocked so no real network/SSH call is made, but the argv-construction
    and error-relay logic runs for real."""

    def _cfg(self):
        return self.module._load_config()

    def test_nonzero_exit_relays_remote_denied_line(self):
        fake_result = mock.Mock(returncode=1, stdout=b"", stderr=b"denied: dlp blocked this payload\n")
        with mock.patch("subprocess.run", return_value=fake_result):
            with self.assertRaises(SystemExit):
                self.module._run_ssh(self._cfg(), ["operator-request-submit"], stdin_bytes=b"{}")

    def test_timeout_is_treated_as_error(self):
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ssh", timeout=1)):
            with self.assertRaises(SystemExit):
                self.module._run_ssh(self._cfg(), ["operator-request-status", ids.generate_request_id()])

    def test_success_returns_stdout_bytes(self):
        fake_result = mock.Mock(returncode=0, stdout=b'{"ok": true}', stderr=b"")
        with mock.patch("subprocess.run", return_value=fake_result) as mock_run:
            out = self.module._run_ssh(self._cfg(), ["operator-outbound-list"])
        self.assertEqual(out, b'{"ok": true}')
        argv = mock_run.call_args.args[0]
        self.assertEqual(argv[0], self.module.SSH_PATH)
        self.assertIn("quory-investigate-test", argv)
        self.assertIn("operator-outbound-list", argv)


if __name__ == "__main__":
    unittest.main()
