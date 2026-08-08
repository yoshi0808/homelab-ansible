import hashlib
import unittest

import _path_setup  # noqa: F401

from oprc import canonical


class CanonicalBytesTests(unittest.TestCase):
    def test_key_order_does_not_affect_output(self):
        a = {"b": 1, "a": 2, "c": 3}
        b = {"a": 2, "c": 3, "b": 1}
        self.assertEqual(canonical.canonical_bytes(a), canonical.canonical_bytes(b))

    def test_whitespace_is_not_significant(self):
        # Two logically identical structures built differently must
        # produce byte-identical canonical output.
        a = {"x": [1, 2, 3], "y": {"z": "value"}}
        b = {"y": {"z": "value"}, "x": [1, 2, 3]}
        self.assertEqual(canonical.canonical_bytes(a), canonical.canonical_bytes(b))

    def test_output_has_no_insignificant_whitespace(self):
        data = canonical.canonical_bytes({"a": 1, "b": [1, 2]})
        self.assertNotIn(b" ", data)
        self.assertNotIn(b"\n", data)

    def test_non_ascii_is_emitted_literally_not_escaped(self):
        data = canonical.canonical_bytes({"a": "日本語"})
        self.assertIn("日本語".encode("utf-8"), data)
        self.assertNotIn(b"\\u", data)

    def test_rejects_non_finite_float(self):
        with self.assertRaises(ValueError):
            canonical.canonical_bytes({"a": float("nan")})
        with self.assertRaises(ValueError):
            canonical.canonical_bytes({"a": float("inf")})

    def test_content_hash_is_deterministic_across_key_order(self):
        a = {"schema_version": 1, "purpose": "check disk", "type": "OPREQ"}
        b = {"type": "OPREQ", "schema_version": 1, "purpose": "check disk"}
        self.assertEqual(canonical.content_hash(a), canonical.content_hash(b))

    def test_content_hash_changes_with_content(self):
        a = {"purpose": "check disk"}
        b = {"purpose": "check disk usage"}
        self.assertNotEqual(canonical.content_hash(a), canonical.content_hash(b))

    def test_content_hash_matches_manual_sha256(self):
        obj = {"a": 1}
        expected = hashlib.sha256(b'{"a":1}').hexdigest()
        self.assertEqual(canonical.content_hash(obj), expected)

    def test_sha256_hex_known_vector(self):
        # sha256("") is a well-known constant.
        self.assertEqual(
            canonical.sha256_hex(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )


if __name__ == "__main__":
    unittest.main()
