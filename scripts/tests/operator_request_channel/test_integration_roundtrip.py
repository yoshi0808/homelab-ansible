"""Integration test (plan §6 "integration (ansy内で完結)"): exercises the
three real entry-point scripts together against a single temp-directory
spool, standing in for quory, with no SSH and no real host touched.

The "ansy relay" is a fake `_run_ssh` on the loaded
operator-channel-client module that, instead of shelling out to `ssh`,
calls `oprc-receive`'s own `main()` in-process and returns what it printed
to stdout -- the same bridge technique used throughout this file. This
keeps the client's own code (DLP-before-send, schema shape check,
hash/version reconciliation on receipt) genuinely exercised end to end,
while the transport itself is local.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import _entrypoint_helpers as helpers
import _fixtures
import _path_setup  # noqa: F401

from oprc import canonical, config as oprc_config, dlp, ids, store

JST = timezone(timedelta(hours=9))


class RoundtripTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool_dir = os.path.join(self.tmp.name, "spool")
        helpers.make_spool(self.spool_dir)
        self.audit_log = os.path.join(self.tmp.name, "audit.jsonl")

        with open(_path_setup.SCHEMA_PATH, "rb") as f:
            schema_hash = canonical.sha256_hex(f.read())
        with open(_path_setup.DLP_RULES_PATH, "rb") as f:
            ruleset_hash = canonical.sha256_hex(f.read())

        # Two config.json files sharing one spool -- exactly what
        # tasks/common.yml deploys to ansy and quory respectively from the
        # identical repo-side schema/ruleset (plan §2.1's "byte-identical
        # copy" is what this fixture is standing in for).
        self.server_config_path = os.path.join(self.tmp.name, "server_config.json")
        helpers.write_config(
            self.server_config_path,
            config_version=1, role="operator_host", channel_enabled=True,
            libexec_dir=_path_setup._OPRC_FILES_DIR,
            schema_path=_path_setup.SCHEMA_PATH, dlp_rules_path=_path_setup.DLP_RULES_PATH,
            expected_schema_sha256=schema_hash, expected_dlp_engine_version=dlp.ENGINE_VERSION,
            expected_dlp_ruleset_sha256=ruleset_hash, max_payload_bytes=65536, dlp_timeout_seconds=5,
            spool_dir=self.spool_dir, audit_log_path=self.audit_log,
            max_ttl_days=14, default_ttl_days=7, max_messages_per_box=500,
            max_total_bytes=134217728, page_size=50,
        )
        self.client_config_path = os.path.join(self.tmp.name, "client_config.json")
        helpers.write_config(
            self.client_config_path,
            config_version=1, role="coordinator", channel_enabled=True,
            libexec_dir=_path_setup._OPRC_FILES_DIR,
            schema_path=_path_setup.SCHEMA_PATH, dlp_rules_path=_path_setup.DLP_RULES_PATH,
            expected_schema_sha256=schema_hash, expected_dlp_engine_version=dlp.ENGINE_VERSION,
            expected_dlp_ruleset_sha256=ruleset_hash, max_payload_bytes=65536, dlp_timeout_seconds=5,
            ssh_destination="quory-investigate-test", ssh_connect_timeout_seconds=1,
        )

        self._synced_patch = helpers.patch_time_synced(oprc_config, synced=True)
        self._synced_patch.start()
        self.addCleanup(self._synced_patch.stop)

        self.client = helpers.load_entrypoint("operator-channel-client")
        self.receiver = helpers.load_entrypoint("oprc-receive")
        self.operator_cli = helpers.load_entrypoint("operator-channel")
        for module, path in (
            (self.client, self.client_config_path),
            (self.receiver, self.server_config_path),
            (self.operator_cli, self.server_config_path),
        ):
            patcher = mock.patch.object(module, "CONFIG_PATH", path)
            patcher.start()
            self.addCleanup(patcher.stop)

        # Mirrors the real dispatcher's own translation (roles/dev_investigate/
        # files/recovery-investigate-dispatch-quory.sh's 4 new case arms):
        # the wire-level command name the client sends is not oprc-receive's
        # own action name -- the dispatcher's `exec ... oprc-receive <action>
        # ...` line is what performs that rename. Getting this wrong here
        # would silently test the wrong action.
        dispatch_to_receive_action = {
            "operator-request-submit": "submit",
            "operator-outbound-list": "outbound-list",
            "operator-message-get": "message-get",
            "operator-request-status": "request-status",
        }

        def fake_run_ssh(_cfg, remote_argv, stdin_bytes=b""):
            receive_action = dispatch_to_receive_action[remote_argv[0]]
            receive_argv = ["oprc-receive", receive_action] + list(remote_argv[1:])
            invocation = helpers.run_main(self.receiver, receive_argv, stdin_bytes)
            if invocation.exit_code != 0:
                # Mirror the real _run_ssh: relay the remote denied:/error:
                # line and stop, rather than returning garbage stdout.
                print(invocation.stderr.strip(), file=sys.stderr)
                raise SystemExit(1)
            return invocation.stdout.encode("utf-8")

        self._ssh_patch = mock.patch.object(self.client, "_run_ssh", side_effect=fake_run_ssh)
        self._ssh_patch.start()
        self.addCleanup(self._ssh_patch.stop)

    def _client(self, argv, stdin_bytes=b""):
        return helpers.run_main(self.client, ["operator-channel-client"] + argv, stdin_bytes)

    def _operator(self, argv, stdin_bytes=b""):
        return helpers.run_main(self.operator_cli, ["operator-channel"] + argv, stdin_bytes)


class FullRoundtripTests(RoundtripTestCase):
    def test_submit_accept_reply_pull(self):
        # 1. ansy submits an OPREQ.
        submit = self._client(
            ["submit"],
            json.dumps({
                "schema_version": 1, "type": "OPREQ",
                "purpose": "quoryのdisk使用率を確認してください",
                "target_names": ["quory"],
            }).encode("utf-8"),
        )
        self.assertEqual(submit.exit_code, 0, submit.stderr)
        request_id = submit.json()["request_id"]

        # 2. Operator sees it pending.
        pending = self._operator(["list-pending"])
        self.assertIn(request_id, [i["request_id"] for i in pending.json()["items"]])

        # 3. Operator accepts it.
        accept = self._operator(["accept-request", request_id])
        self.assertEqual(accept.exit_code, 0, accept.stderr)

        # 4. Operator replies with an OPRES.
        reply = self._operator(
            ["reply-opres", request_id],
            json.dumps({"schema_version": 1, "purpose": "確認済み", "expected_result": "disk使用率は72%でした"}).encode("utf-8"),
        )
        self.assertEqual(reply.exit_code, 0, reply.stderr)
        opres_id = reply.json()["request_id"]

        # 5. ansy lists and finds the OPRES addressed to it.
        listing = self._client(["list"])
        self.assertEqual(listing.exit_code, 0, listing.stderr)
        self.assertIn(opres_id, [i["request_id"] for i in listing.json()["items"]])

        # 6. ansy pulls it, with DLP + hash reconciliation happening for real.
        got = self._client(["get", opres_id])
        self.assertEqual(got.exit_code, 0, got.stderr)
        self.assertEqual(got.json()["message"]["in_reply_to"], request_id)
        self.assertEqual(got.json()["message"]["conversation_id"], submit.json()["conversation_id"])

        # 7. Re-fetching returns identical content (requirement §16:
        # deterministic repeat reads).
        got_again = self._client(["get", opres_id])
        self.assertEqual(got.json()["message"], got_again.json()["message"])

    def test_standalone_devreq_reaches_ansy(self):
        devreq = self._operator(
            ["new-devreq"],
            json.dumps({"schema_version": 1, "purpose": "quoryで発見した障害", "observed_facts": ["ディスクが72%"], "unconfirmed": ["原因未確認"]}).encode("utf-8"),
        )
        self.assertEqual(devreq.exit_code, 0, devreq.stderr)
        devreq_id = devreq.json()["request_id"]

        got = self._client(["get", devreq_id])
        self.assertEqual(got.exit_code, 0, got.stderr)
        self.assertEqual(got.json()["message"]["type"], "DEVREQ")
        self.assertIsNone(got.json()["message"].get("in_reply_to"))

    def test_dlp_blocks_the_same_fixture_at_all_four_inspection_points(self):
        secret = _fixtures.password_keyvalue_text()

        # Checkpoint 1: ansy send-before.
        with mock.patch.object(self.client, "_run_ssh") as mock_ssh:
            submit_blocked = self._client(
                ["submit"],
                json.dumps({"schema_version": 1, "type": "OPREQ", "purpose": secret, "target_names": ["quory"]}).encode("utf-8"),
            )
        self.assertNotEqual(submit_blocked.exit_code, 0)
        mock_ssh.assert_not_called()

        # Checkpoint 2: quory accept-before (submit through the real
        # receiver directly, bypassing the client's own checkpoint-1 block
        # so checkpoint 2 is exercised independently).
        submit_direct = helpers.run_main(
            self.receiver, ["oprc-receive", "submit"],
            json.dumps({"schema_version": 1, "type": "OPREQ", "conversation_id": ids.generate_conversation_id(),
                        "purpose": secret, "target_names": ["quory"]}).encode("utf-8"),
        )
        self.assertNotEqual(submit_direct.exit_code, 0)
        self.assertEqual(store.count_and_size(self.spool_dir, "inbox")[0], 0)

        # Checkpoint 3: quory outbound-before (seed a clean OPREQ, accept
        # it, then try to reply with the secret).
        clean_submit = self._client(
            ["submit"],
            json.dumps({"schema_version": 1, "type": "OPREQ", "purpose": "clean", "target_names": ["quory"]}).encode("utf-8"),
        )
        request_id = clean_submit.json()["request_id"]
        self._operator(["accept-request", request_id])
        reply_blocked = self._operator(["reply-opres", request_id], json.dumps({"schema_version": 1, "purpose": secret}).encode("utf-8"))
        self.assertNotEqual(reply_blocked.exit_code, 0)
        self.assertEqual(store.count_and_size(self.spool_dir, "outbox")[0], 0)

        # Checkpoint 4: ansy intake-before. Seed an outbox message directly
        # (bypassing checkpoint 3) so checkpoint 4 is exercised on its own.
        message = {
            "schema_version": 1, "request_id": ids.generate_request_id(),
            "conversation_id": ids.generate_conversation_id(), "type": "OPRES", "source": "operator",
            "created_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "expires_at": (datetime.now(JST) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "purpose": secret,
        }
        meta = {"content_sha256": canonical.content_hash(message), "dlp_engine_version": dlp.ENGINE_VERSION,
                "dlp_ruleset_sha256": ruleset_sha256_for_this_test(), "received_at": message["created_at"]}
        store.create_message(self.spool_dir, "outbox", message["request_id"], message, meta)
        store.append_event(self.spool_dir, message["request_id"], "submitted", message["created_at"])
        get_blocked = self._client(["get", message["request_id"]])
        self.assertNotEqual(get_blocked.exit_code, 0)
        self.assertNotIn(secret, get_blocked.stdout)
        self.assertNotIn(secret, get_blocked.stderr)


def ruleset_sha256_for_this_test():
    with open(_path_setup.DLP_RULES_PATH, "rb") as f:
        return canonical.sha256_hex(f.read())


if __name__ == "__main__":
    unittest.main()
