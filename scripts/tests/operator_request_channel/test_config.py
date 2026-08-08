import json
import os
import stat
import tempfile
import textwrap
import unittest

import _path_setup  # noqa: F401

from oprc import canonical, config, dlp


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _make_chronyc_script(path, body):
    _write(path, "#!/bin/sh\n" + body + "\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class LoadConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_valid_coordinator_config_loads(self):
        path = self._path("config.json")
        _write(
            path,
            json.dumps(
                {
                    "config_version": 1,
                    "role": "coordinator",
                    "channel_enabled": True,
                    "libexec_dir": "/usr/local/libexec/operator-request-channel",
                    "schema_path": "/etc/x/schema.json",
                    "dlp_rules_path": "/etc/x/rules.json",
                    "expected_schema_sha256": "a" * 64,
                    "expected_dlp_engine_version": "1",
                    "expected_dlp_ruleset_sha256": "b" * 64,
                    "max_payload_bytes": 65536,
                    "dlp_timeout_seconds": 20,
                    "ssh_destination": "quory-investigate",
                    "ssh_connect_timeout_seconds": 15,
                }
            ),
        )
        cfg = config.load_config(path)
        self.assertEqual(cfg["role"], "coordinator")

    def test_missing_common_key_is_rejected(self):
        path = self._path("config.json")
        _write(path, json.dumps({"config_version": 1, "role": "coordinator"}))
        with self.assertRaises(config.ConfigError):
            config.load_config(path)

    def test_coordinator_missing_ssh_destination_is_rejected(self):
        path = self._path("config.json")
        doc = {
            "config_version": 1,
            "role": "coordinator",
            "channel_enabled": True,
            "libexec_dir": "x",
            "schema_path": "x",
            "dlp_rules_path": "x",
            "expected_schema_sha256": "a" * 64,
            "expected_dlp_engine_version": "1",
            "expected_dlp_ruleset_sha256": "b" * 64,
            "max_payload_bytes": 65536,
            "dlp_timeout_seconds": 20,
        }
        _write(path, json.dumps(doc))
        with self.assertRaises(config.ConfigError):
            config.load_config(path)

    def test_operator_host_requires_spool_dir(self):
        path = self._path("config.json")
        doc = {
            "config_version": 1,
            "role": "operator_host",
            "channel_enabled": True,
            "libexec_dir": "x",
            "schema_path": "x",
            "dlp_rules_path": "x",
            "expected_schema_sha256": "a" * 64,
            "expected_dlp_engine_version": "1",
            "expected_dlp_ruleset_sha256": "b" * 64,
            "max_payload_bytes": 65536,
            "dlp_timeout_seconds": 20,
        }
        _write(path, json.dumps(doc))
        with self.assertRaises(config.ConfigError):
            config.load_config(path)

    def test_unknown_role_is_rejected(self):
        path = self._path("config.json")
        _write(path, json.dumps({"config_version": 1, "role": "root"}))
        with self.assertRaises(config.ConfigError):
            config.load_config(path)

    def test_missing_file_is_rejected(self):
        with self.assertRaises(config.ConfigError):
            config.load_config(self._path("does-not-exist.json"))

    def test_malformed_json_is_rejected(self):
        path = self._path("config.json")
        _write(path, "{not json")
        with self.assertRaises(config.ConfigError):
            config.load_config(path)

    def test_non_object_root_is_rejected(self):
        path = self._path("config.json")
        _write(path, "[1, 2, 3]")
        with self.assertRaises(config.ConfigError):
            config.load_config(path)


class VerifySchemaHashTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_matching_hash_passes(self):
        schema_path = os.path.join(self.tmp.name, "schema.json")
        _write(schema_path, '{"type": "object"}')
        expected = canonical.sha256_hex(b'{"type": "object"}')
        cfg = {"schema_path": schema_path, "expected_schema_sha256": expected}
        config.verify_schema_hash(cfg)  # must not raise

    def test_mismatched_hash_is_rejected(self):
        schema_path = os.path.join(self.tmp.name, "schema.json")
        _write(schema_path, '{"type": "object"}')
        cfg = {"schema_path": schema_path, "expected_schema_sha256": "0" * 64}
        with self.assertRaises(config.ConfigError):
            config.verify_schema_hash(cfg)

    def test_missing_schema_file_is_rejected(self):
        cfg = {
            "schema_path": os.path.join(self.tmp.name, "nope.json"),
            "expected_schema_sha256": "0" * 64,
        }
        with self.assertRaises(config.ConfigError):
            config.verify_schema_hash(cfg)


class LoadAndVerifyDlpRulesetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruleset_text = json.dumps(
            {
                "engine_version": "1",
                "ruleset_version": "test.1",
                "rules": [{"id": "r1", "category": "c1", "pattern": "secret"}],
            }
        )
        self.ruleset_path = os.path.join(self.tmp.name, "rules.json")
        _write(self.ruleset_path, self.ruleset_text)
        self.expected_hash = canonical.sha256_hex(self.ruleset_text.encode("utf-8"))

    def _cfg(self, **overrides):
        cfg = {
            "dlp_rules_path": self.ruleset_path,
            "expected_dlp_engine_version": "1",
            "expected_dlp_ruleset_sha256": self.expected_hash,
        }
        cfg.update(overrides)
        return cfg

    def test_matching_ruleset_loads(self):
        ruleset = config.load_and_verify_dlp_ruleset(self._cfg())
        self.assertEqual(ruleset["engine_version"], "1")
        self.assertEqual(len(ruleset["rules"]), 1)

    def test_hash_mismatch_is_rejected(self):
        with self.assertRaises(config.ConfigError):
            config.load_and_verify_dlp_ruleset(self._cfg(expected_dlp_ruleset_sha256="f" * 64))

    def test_engine_version_mismatch_is_rejected(self):
        with self.assertRaises(config.ConfigError):
            config.load_and_verify_dlp_ruleset(self._cfg(expected_dlp_engine_version="2"))

    def test_real_shipped_ruleset_matches_its_own_hash(self):
        with open(_path_setup.DLP_RULES_PATH, "rb") as f:
            raw = f.read()
        real_hash = canonical.sha256_hex(raw)
        cfg = {
            "dlp_rules_path": _path_setup.DLP_RULES_PATH,
            "expected_dlp_engine_version": dlp.ENGINE_VERSION,
            "expected_dlp_ruleset_sha256": real_hash,
        }
        ruleset = config.load_and_verify_dlp_ruleset(cfg)
        self.assertGreater(len(ruleset["rules"]), 0)
        self.assertIsNotNone(ruleset["entropy"])


class TimeSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _script(self, name, body):
        path = os.path.join(self.tmp.name, name)
        _make_chronyc_script(path, body)
        return path

    def test_synced_in_bounds_passes(self):
        script = self._script(
            "chronyc_ok.sh",
            textwrap.dedent(
                """\
                cat <<'EOF'
                Reference ID    : 00000000 ()
                Stratum         : 3
                System time     : 0.000123456 seconds slow of NTP time
                Leap status     : Normal
                EOF
                exit 0
                """
            ),
        )
        config.assert_time_synced(max_offset_seconds=60, chronyc_path=script)  # must not raise

    def test_not_synchronised_is_rejected(self):
        script = self._script(
            "chronyc_notsync.sh",
            textwrap.dedent(
                """\
                cat <<'EOF'
                System time     : 0.000123456 seconds slow of NTP time
                Leap status     : Not synchronised
                EOF
                exit 0
                """
            ),
        )
        with self.assertRaises(config.TimeSyncError):
            config.assert_time_synced(chronyc_path=script)

    def test_missing_leap_status_line_is_rejected(self):
        script = self._script(
            "chronyc_noleap.sh",
            textwrap.dedent(
                """\
                cat <<'EOF'
                System time     : 0.000123456 seconds slow of NTP time
                EOF
                exit 0
                """
            ),
        )
        with self.assertRaises(config.TimeSyncError):
            config.assert_time_synced(chronyc_path=script)

    def test_offset_beyond_threshold_is_rejected(self):
        script = self._script(
            "chronyc_bigoffset.sh",
            textwrap.dedent(
                """\
                cat <<'EOF'
                System time     : 120.5 seconds slow of NTP time
                Leap status     : Normal
                EOF
                exit 0
                """
            ),
        )
        with self.assertRaises(config.TimeSyncError):
            config.assert_time_synced(max_offset_seconds=60, chronyc_path=script)

    def test_unparseable_offset_is_rejected(self):
        script = self._script(
            "chronyc_badoffset.sh",
            textwrap.dedent(
                """\
                cat <<'EOF'
                System time     : who knows
                Leap status     : Normal
                EOF
                exit 0
                """
            ),
        )
        with self.assertRaises(config.TimeSyncError):
            config.assert_time_synced(chronyc_path=script)

    def test_nonzero_exit_is_rejected(self):
        script = self._script("chronyc_fail.sh", "exit 1\n")
        with self.assertRaises(config.TimeSyncError):
            config.assert_time_synced(chronyc_path=script)

    def test_missing_binary_is_rejected(self):
        with self.assertRaises(config.TimeSyncError):
            config.assert_time_synced(chronyc_path=os.path.join(self.tmp.name, "does-not-exist"))

    def test_timeout_is_rejected(self):
        script = self._script("chronyc_slow.sh", "sleep 5\nexit 0\n")
        with self.assertRaises(config.TimeSyncError):
            config.assert_time_synced(timeout_seconds=0.2, chronyc_path=script)


if __name__ == "__main__":
    unittest.main()
