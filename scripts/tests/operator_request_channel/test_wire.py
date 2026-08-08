import unittest

import _path_setup  # noqa: F401

from oprc import wire


class WireParsePayloadTests(unittest.TestCase):
    def test_valid_payload_parses(self):
        raw = b'{"a": 1, "b": [1, 2, 3], "c": {"d": "e"}}'
        obj = wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(obj, {"a": 1, "b": [1, 2, 3], "c": {"d": "e"}})

    def test_rejects_non_bytes(self):
        with self.assertRaises(TypeError):
            wire.parse_payload("not bytes", max_bytes=65536)  # type: ignore[arg-type]

    def test_rejects_empty_payload(self):
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(b"", max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "empty_payload")

    def test_rejects_payload_over_max_bytes(self):
        raw = b'{"a": "' + b"x" * 100 + b'"}'
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=10)
        self.assertEqual(ctx.exception.reason, "payload_too_large")

    def test_rejects_invalid_utf8(self):
        raw = b'{"a": "\xff\xfe"}'
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "invalid_utf8")

    def test_rejects_lone_surrogate_escape(self):
        # \ud800 is a valid JSON escape token that decodes into a Python
        # str containing a lone surrogate -- not valid Unicode text.
        raw = '{"a": "\\ud800"}'.encode("utf-8")
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "invalid_unicode")

    def test_rejects_duplicate_top_level_key(self):
        raw = b'{"a": 1, "a": 2}'
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "duplicate_key")

    def test_rejects_duplicate_nested_key(self):
        raw = b'{"a": {"b": 1, "b": 2}}'
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "duplicate_key")

    def test_rejects_nan(self):
        raw = b'{"a": NaN}'
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "non_finite_number")

    def test_rejects_infinity(self):
        raw = b'{"a": Infinity}'
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "non_finite_number")

    def test_rejects_negative_infinity(self):
        raw = b'{"a": -Infinity}'
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "non_finite_number")

    def test_rejects_invalid_json(self):
        raw = b'{"a": '
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "invalid_json")

    def test_rejects_non_object_root_array(self):
        raw = b"[1, 2, 3]"
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "not_an_object")

    def test_rejects_non_object_root_string(self):
        raw = b'"just a string"'
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "not_an_object")

    def test_rejects_excessive_nesting(self):
        depth = wire.MAX_DEPTH + 5
        raw = (b'{"a": ' * depth) + b"1" + (b"}" * depth)
        with self.assertRaises(wire.WireError) as ctx:
            wire.parse_payload(raw, max_bytes=65536)
        self.assertEqual(ctx.exception.reason, "nesting_too_deep")

    def test_allows_nesting_within_bound(self):
        depth = wire.MAX_DEPTH - 2
        raw = (b'{"a": ' * depth) + b"1" + (b"}" * depth)
        # Must not raise.
        wire.parse_payload(raw, max_bytes=65536)


if __name__ == "__main__":
    unittest.main()
