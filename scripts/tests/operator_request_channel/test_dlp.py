import json
import time
import unittest

import _path_setup  # noqa: F401
import _fixtures as fx

from oprc import dlp


def _load_real_ruleset():
    with open(_path_setup.DLP_RULES_PATH, "r", encoding="utf-8") as f:
        return dlp.parse_ruleset(f.read())


def _message(**overrides):
    msg = {
        "schema_version": 1,
        "type": "OPREQ",
        "purpose": fx.benign_prose(),
        "observed_facts": [fx.benign_prose()],
        "requested_information": fx.benign_prose(),
        "expected_result": fx.benign_prose(),
        "unconfirmed": [fx.benign_prose()],
        "target_names": ["quory"],
        "request_id": "req-20260808T120000+0900-0123456789abcdef",
        "conversation_id": "cnv-20260808T120000+0900-0123456789abcdef",
        "repo_commit": "0123456789abcdef0123456789abcdef01234567",
    }
    msg.update(overrides)
    return msg


class ParseRulesetTests(unittest.TestCase):
    def test_real_ruleset_parses(self):
        ruleset = _load_real_ruleset()
        self.assertEqual(ruleset["engine_version"], dlp.ENGINE_VERSION)
        self.assertGreater(len(ruleset["rules"]), 0)
        self.assertIsNotNone(ruleset["entropy"])

    def test_real_ruleset_has_all_required_categories(self):
        # requirement §9.3's 12 minimum detection targets.
        expected_categories = {
            "pem_private_key",
            "slack_credential",
            "semaphore_api_token",
            "bearer_or_jwt",
            "generic_secret_keyvalue",
            "vault_plaintext",
            "credential_url",
            "env_dump",
            "proc_environ",
            "private_ipv4",
            "ipv6_ula_link_local",
            "high_entropy",
        }
        ruleset = _load_real_ruleset()
        found = {rule["category"] for rule in ruleset["rules"]}
        found.add(ruleset["entropy"]["category"])
        self.assertEqual(expected_categories, found)

    def test_wrong_engine_version_is_rejected(self):
        doc = json.dumps({"engine_version": "999", "rules": [{"id": "r", "category": "c", "pattern": "x"}]})
        with self.assertRaises(dlp.RulesetError):
            dlp.parse_ruleset(doc)

    def test_no_rules_is_rejected(self):
        doc = json.dumps({"engine_version": "1", "rules": []})
        with self.assertRaises(dlp.RulesetError):
            dlp.parse_ruleset(doc)

    def test_malformed_rule_entry_is_rejected(self):
        doc = json.dumps({"engine_version": "1", "rules": [{"id": "r"}]})
        with self.assertRaises(dlp.RulesetError):
            dlp.parse_ruleset(doc)

    def test_duplicate_rule_id_is_rejected(self):
        doc = json.dumps(
            {
                "engine_version": "1",
                "rules": [
                    {"id": "dup", "category": "c1", "pattern": "a"},
                    {"id": "dup", "category": "c2", "pattern": "b"},
                ],
            }
        )
        with self.assertRaises(dlp.RulesetError):
            dlp.parse_ruleset(doc)

    def test_invalid_regex_is_rejected(self):
        doc = json.dumps({"engine_version": "1", "rules": [{"id": "r", "category": "c", "pattern": "("}]})
        with self.assertRaises(dlp.RulesetError):
            dlp.parse_ruleset(doc)

    def test_not_json_is_rejected(self):
        with self.assertRaises(dlp.RulesetError):
            dlp.parse_ruleset("not json at all")

    def test_root_not_object_is_rejected(self):
        with self.assertRaises(dlp.RulesetError):
            dlp.parse_ruleset("[1, 2, 3]")


class ScanCategoryTests(unittest.TestCase):
    """requirement §9.3 x 12, plan T-C: each category is detected via the
    real, shipped ruleset, and the finding never carries the matched
    value."""

    def setUp(self):
        self.ruleset = _load_real_ruleset()

    def _assert_category_detected(self, field, value, expected_category):
        msg = _message(**{field: value})
        result = dlp.scan(msg, self.ruleset, timeout_seconds=5)
        self.assertTrue(result.blocked, "expected a finding for category {}".format(expected_category))
        categories = {f.category for f in result.findings}
        self.assertIn(expected_category, categories)
        # No finding may carry the matched text -- only category/rule_id/pointer.
        dumped = json.dumps([f.to_dict() for f in result.findings])
        self.assertNotIn(value, dumped)

    def test_pem_private_key(self):
        self._assert_category_detected("purpose", fx.pem_private_key_block(), "pem_private_key")

    def test_slack_token(self):
        self._assert_category_detected("purpose", fx.slack_bot_token(), "slack_credential")

    def test_slack_webhook_url(self):
        self._assert_category_detected("purpose", fx.slack_webhook_url(), "slack_credential")

    def test_semaphore_api_token(self):
        self._assert_category_detected("purpose", fx.semaphore_api_token_text(), "semaphore_api_token")

    def test_bearer_token(self):
        self._assert_category_detected("purpose", fx.bearer_token_text(), "bearer_or_jwt")

    def test_jwt(self):
        self._assert_category_detected("purpose", fx.jwt_text(), "bearer_or_jwt")

    def test_generic_secret_keyvalue(self):
        self._assert_category_detected("purpose", fx.password_keyvalue_text(), "generic_secret_keyvalue")

    def test_vault_plaintext(self):
        self._assert_category_detected("purpose", fx.vault_plaintext_text(), "vault_plaintext")

    def test_credential_url(self):
        self._assert_category_detected("purpose", fx.credential_url_text(), "credential_url")

    def test_env_dump(self):
        self._assert_category_detected("purpose", fx.env_dump_text(), "env_dump")

    def test_proc_environ(self):
        self._assert_category_detected("purpose", fx.proc_environ_text(), "proc_environ")

    def test_private_ipv4(self):
        self._assert_category_detected("purpose", fx.private_ipv4_text(), "private_ipv4")

    def test_ipv6_ula(self):
        self._assert_category_detected("purpose", fx.ipv6_ula_text(), "ipv6_ula_link_local")

    def test_ipv6_link_local(self):
        self._assert_category_detected("purpose", fx.ipv6_link_local_text(), "ipv6_ula_link_local")

    def test_high_entropy_in_freeform_field(self):
        self._assert_category_detected("purpose", "reference token: " + fx.high_entropy_text(), "high_entropy")

    def test_high_entropy_in_observed_facts_array_element(self):
        msg = _message(observed_facts=[fx.benign_prose(), fx.high_entropy_text()])
        result = dlp.scan(msg, self.ruleset, timeout_seconds=5)
        self.assertTrue(result.blocked)
        pointers = [f.pointer for f in result.findings]
        self.assertTrue(any(p.startswith("/observed_facts/") for p in pointers))


class NoFalsePositiveTests(unittest.TestCase):
    """requirement §9.3 (末尾): commit hash / request ID / conversation ID
    / content hash must not be flagged by high entropy just because they
    are structured, high-entropy-looking values in their own dedicated
    fields."""

    def setUp(self):
        self.ruleset = _load_real_ruleset()

    def test_benign_message_has_no_findings(self):
        result = dlp.scan(_message(), self.ruleset, timeout_seconds=5)
        self.assertFalse(result.blocked)
        self.assertEqual(result.findings, [])

    def test_request_id_field_not_flagged(self):
        msg = _message(request_id="req-20260808T120000+0900-" + "abcdef0123456789")
        result = dlp.scan(msg, self.ruleset, timeout_seconds=5)
        pointers = [f.pointer for f in result.findings]
        self.assertNotIn("/request_id", pointers)

    def test_conversation_id_field_not_flagged(self):
        msg = _message(conversation_id="cnv-20260808T120000+0900-" + "abcdef0123456789")
        result = dlp.scan(msg, self.ruleset, timeout_seconds=5)
        pointers = [f.pointer for f in result.findings]
        self.assertNotIn("/conversation_id", pointers)

    def test_repo_commit_field_not_flagged(self):
        msg = _message(repo_commit="a" * 40)
        result = dlp.scan(msg, self.ruleset, timeout_seconds=5)
        pointers = [f.pointer for f in result.findings]
        self.assertNotIn("/repo_commit", pointers)


class KnownVocabularyRegressionTests(unittest.TestCase):
    """Pins concrete false-positive examples that came up while deciding
    `entropy.candidate_pattern` (2026-08-23,
    docs/ai/reviews/oprc_dlp_false_positive/), instead of leaving the
    decision only in review prose. Two different outcomes are pinned on
    purpose:

    - The systemd `key=value` lines are the bug this case fixed (R1: `=`
      removed from the candidate class, requirement 2026-08-23). They
      must NOT block. If a future ruleset change makes them block again,
      this is the regression the whole R1/H1 fix exists to prevent.
    - `UNREACHABLE+report` is a *known, accepted* false positive
      (Reviewer Finding 1, 2026-08-23_005_review.md): `+` stays in the
      class because removing it only saves 2 BLOCKed candidates across
      the ~1,760 tracked files requirement §8 measured (`docs/ai/
      reviews/oprc_dlp_false_positive/2026-08-23_001_requirement.md`
      §8; an earlier version of this comment cited a stale "3 hits
      across 1,809 files" figure from before that measurement was
      redone excluding docs/ai/memory/ -- 2026-08-23_009_review.md
      Finding 1) while costing real base64 detection coverage
      (Yoshinobu decision, same date). It is pinned as MUST block, not
      as a bug -- if a future change flips this without a deliberate
      decision to revisit `+`, this test should fail and force that
      decision to be made on purpose again, not slide by unnoticed.
    """

    def setUp(self):
        self.ruleset = _load_real_ruleset()

    def _scan_purpose(self, text):
        return dlp.scan(_message(purpose=text), self.ruleset, timeout_seconds=5)

    def test_systemd_description_reload_not_blocked(self):
        result = self._scan_purpose(
            "Description=Reload nginx after the ansy TLS certificate changed"
        )
        self.assertFalse(result.blocked, [f.to_dict() for f in result.findings])

    def test_systemd_description_monthly_not_blocked(self):
        result = self._scan_purpose("Description=Monthly knowledge review (timer)")
        self.assertFalse(result.blocked, [f.to_dict() for f in result.findings])

    def test_systemd_lock_personality_not_blocked(self):
        result = self._scan_purpose("LockPersonality=yes")
        self.assertFalse(result.blocked, [f.to_dict() for f in result.findings])

    def test_unreachable_plus_report_is_a_known_accepted_false_positive(self):
        result = self._scan_purpose("UNREACHABLE+report")
        self.assertTrue(
            result.blocked,
            "UNREACHABLE+report stopped blocking -- candidate_pattern changed. "
            "If '+' was deliberately removed from the class, update this test "
            "(and the implement record's '+ を外しません' rationale) together; "
            "do not just flip the assertion.",
        )
        categories = {f.category for f in result.findings}
        self.assertIn("high_entropy", categories)


class TimeoutTests(unittest.TestCase):
    def test_alarm_guard_raises_scan_timeout(self):
        with self.assertRaises(dlp.ScanTimeout):
            with dlp._AlarmGuard(0.05):
                time.sleep(0.5)

    def test_alarm_guard_does_not_fire_when_fast_enough(self):
        with dlp._AlarmGuard(2.0):
            pass  # must not raise

    def test_scan_completes_within_generous_timeout(self):
        ruleset = _load_real_ruleset()
        result = dlp.scan(_message(), ruleset, timeout_seconds=5)
        self.assertFalse(result.blocked)


if __name__ == "__main__":
    unittest.main()
