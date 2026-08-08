import unittest
from datetime import datetime, timedelta, timezone

import _path_setup  # noqa: F401

from oprc import ids


class IdGenerationTests(unittest.TestCase):
    def test_generate_request_id_matches_its_own_regex(self):
        rid = ids.generate_request_id()
        self.assertRegex(rid, ids.REQUEST_ID_RE)
        self.assertTrue(ids.is_valid_request_id(rid))

    def test_generate_conversation_id_matches_its_own_regex(self):
        cid = ids.generate_conversation_id()
        self.assertRegex(cid, ids.CONVERSATION_ID_RE)
        self.assertTrue(ids.is_valid_conversation_id(cid))

    def test_generate_attempt_id_matches_its_own_regex(self):
        aid = ids.generate_attempt_id()
        self.assertRegex(aid, ids.ATTEMPT_ID_RE)
        self.assertTrue(ids.is_valid_attempt_id(aid))

    def test_ids_are_unique_across_calls(self):
        generated = {ids.generate_request_id() for _ in range(20)}
        self.assertEqual(len(generated), 20)

    def test_timestamp_reflects_supplied_moment_in_jst(self):
        # A fixed UTC instant, converted -- not a pasted label. 2026-08-08
        # 00:00:00 UTC is 2026-08-08 09:00:00 JST.
        moment = datetime(2026, 8, 8, 0, 0, 0, tzinfo=timezone.utc)
        rid = ids.generate_request_id(now=moment)
        self.assertTrue(rid.startswith("req-20260808T090000+0900-"))

    def test_non_jst_aware_datetime_is_converted_correctly(self):
        # now= need not already be JST -- a caller passing some other
        # tz-aware instant must still get a correctly *converted* JST
        # timestamp (not the wrong-zone wall-clock time relabeled).
        moment = datetime(2026, 8, 7, 20, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
        # 2026-08-07 20:00 -05:00 == 2026-08-08 01:00 UTC == 2026-08-08 10:00 JST
        rid = ids.generate_request_id(now=moment)
        self.assertTrue(rid.startswith("req-20260808T100000+0900-"))

    def test_is_valid_request_id_rejects_garbage(self):
        for bad in [
            "",
            "req-not-a-real-id",
            "cnv-20260808T090000+0900-0123456789abcdef",  # wrong prefix
            "req-20260808T090000+0900-0123456789ABCDEF",  # uppercase hex
            "req-20260808T090000+0900-0123456789abcde",  # short hex
            "req-20260808T090000+0900-0123456789abcdef/../etc",
            None,
            123,
        ]:
            self.assertFalse(ids.is_valid_request_id(bad))

    def test_is_valid_conversation_id_rejects_request_id(self):
        rid = ids.generate_request_id()
        self.assertFalse(ids.is_valid_conversation_id(rid))

    def test_ids_cannot_spell_path_traversal(self):
        rid = ids.generate_request_id()
        self.assertNotIn("/", rid)
        self.assertNotIn("..", rid)


if __name__ == "__main__":
    unittest.main()
