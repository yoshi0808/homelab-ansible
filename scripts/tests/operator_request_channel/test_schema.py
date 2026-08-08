import unittest

import _path_setup  # noqa: F401

from oprc import ids, schema


def _base_message(**overrides):
    msg = {
        "schema_version": 1,
        "request_id": ids.generate_request_id(),
        "conversation_id": ids.generate_conversation_id(),
        "type": "OPREQ",
        "source": "coordinator",
        "in_reply_to": None,
        "created_at": "2026-08-08T12:00:00+0900",
        "expires_at": "2026-08-15T12:00:00+0900",
        "repo_commit": "0123456789abcdef0123456789abcdef01234567",
        "purpose": "quory の disk 使用率を確認してほしい",
        "target_names": ["quory", "monnie.internal"],
        "observed_facts": ["disk使用率が90%を超えている"],
        "requested_information": "df -h の出力",
        "evidence_references": [{"kind": "drift_report", "id": "2026-08-08_001"}],
        "expected_result": "現在の使用率と直近の増加傾向",
        "unconfirmed": ["ログローテーションの設定有無"],
    }
    msg.update(overrides)
    return msg


class LoadSchemaTests(unittest.TestCase):
    def test_real_schema_file_loads(self):
        doc = schema.load_schema(_path_setup.SCHEMA_PATH)
        self.assertEqual(doc["type"], "object")
        self.assertFalse(doc.get("additionalProperties"))

    def test_unsupported_keyword_is_rejected(self):
        bad = {"type": "object", "patternProperties": {}}
        with self.assertRaises(schema.SchemaError):
            schema._check_supported(bad, "#")

    def test_unsupported_keyword_nested_in_properties_is_rejected(self):
        bad = {
            "type": "object",
            "properties": {"x": {"type": "string", "if": {}}},
        }
        with self.assertRaises(schema.SchemaError):
            schema._check_supported(bad, "#")


class ValidateAgainstRealSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema_doc = schema.load_schema(_path_setup.SCHEMA_PATH)

    def test_valid_opreq_passes(self):
        schema.validate(_base_message(), self.schema_doc)  # must not raise

    def test_valid_opres_reply_passes(self):
        msg = _base_message(
            type="OPRES",
            source="operator",
            in_reply_to=ids.generate_request_id(),
            repo_commit=None,
        )
        schema.validate(msg, self.schema_doc)

    def test_missing_required_field_is_rejected(self):
        msg = _base_message()
        del msg["purpose"]
        with self.assertRaises(schema.ValidationError) as ctx:
            schema.validate(msg, self.schema_doc)
        pointers = [p for p, _rule in ctx.exception.errors]
        self.assertIn("/purpose", pointers)

    def test_additional_property_is_rejected(self):
        msg = _base_message(password="should-not-be-a-field")
        with self.assertRaises(schema.ValidationError) as ctx:
            schema.validate(msg, self.schema_doc)
        rules = [rule for _p, rule in ctx.exception.errors]
        self.assertIn("additionalProperties", rules)

    def test_bad_type_enum_is_rejected(self):
        msg = _base_message(type="NOT_A_TYPE")
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_bad_source_enum_is_rejected(self):
        msg = _base_message(source="root")
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_request_id_wrong_pattern_is_rejected(self):
        msg = _base_message(request_id="not-a-real-id")
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_target_names_rejects_ipv4_literal(self):
        # Built from separate octet literals (no fixture-file dotted-quad
        # literal) -- same discipline as _fixtures.py, even though this
        # value is not a secret, to avoid an IPv4-shaped literal in the repo.
        ipv4_shaped = ".".join(["10", "20", "30", "40"])
        msg = _base_message(target_names=[ipv4_shaped])
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_target_names_accepts_hostname_with_digits(self):
        msg = _base_message(target_names=["proxmox1.internal"])
        schema.validate(msg, self.schema_doc)

    def test_evidence_reference_bad_kind_is_rejected(self):
        msg = _base_message(evidence_references=[{"kind": "not_a_kind", "id": "abc"}])
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_evidence_reference_additional_property_is_rejected(self):
        msg = _base_message(evidence_references=[{"kind": "drift_report", "id": "abc", "path": "/etc/passwd"}])
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_evidence_reference_id_rejects_path_traversal(self):
        msg = _base_message(evidence_references=[{"kind": "drift_report", "id": "../../etc/passwd"}])
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_too_many_target_names_is_rejected(self):
        msg = _base_message(target_names=["host{}.internal".format(i) for i in range(51)])
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_purpose_too_long_is_rejected(self):
        msg = _base_message(purpose="x" * 5000)
        with self.assertRaises(schema.ValidationError):
            schema.validate(msg, self.schema_doc)

    def test_null_in_reply_to_is_accepted(self):
        msg = _base_message(in_reply_to=None)
        schema.validate(msg, self.schema_doc)

    def test_non_object_root_is_rejected(self):
        with self.assertRaises(schema.ValidationError):
            schema.validate(["not", "an", "object"], self.schema_doc)

    def test_reports_multiple_errors_at_once(self):
        msg = _base_message(type="BOGUS", source="root")
        del msg["purpose"]
        with self.assertRaises(schema.ValidationError) as ctx:
            schema.validate(msg, self.schema_doc)
        self.assertGreaterEqual(len(ctx.exception.errors), 3)


class ServerAssignedFieldTests(unittest.TestCase):
    def test_client_payload_without_server_fields_passes(self):
        raw = {"schema_version": 1, "type": "OPREQ", "purpose": "check disk"}
        schema.reject_server_assigned_fields(raw)  # must not raise

    def test_request_id_in_client_payload_is_rejected(self):
        raw = {"request_id": ids.generate_request_id(), "type": "OPREQ"}
        with self.assertRaises(schema.ValidationError) as ctx:
            schema.reject_server_assigned_fields(raw)
        self.assertIn(("/request_id", "server_assigned_field_in_payload"), ctx.exception.errors)

    def test_source_in_client_payload_is_rejected(self):
        raw = {"source": "coordinator"}
        with self.assertRaises(schema.ValidationError):
            schema.reject_server_assigned_fields(raw)

    def test_created_at_in_client_payload_is_rejected(self):
        raw = {"created_at": "2026-08-08T12:00:00+0900"}
        with self.assertRaises(schema.ValidationError):
            schema.reject_server_assigned_fields(raw)

    def test_all_three_reported_together(self):
        raw = {"request_id": "x", "source": "coordinator", "created_at": "x"}
        with self.assertRaises(schema.ValidationError) as ctx:
            schema.reject_server_assigned_fields(raw)
        self.assertEqual(len(ctx.exception.errors), 3)


class SourceTypeMatrixTests(unittest.TestCase):
    """requirement §4.2's allow matrix."""

    def test_coordinator_may_create_opreq(self):
        schema.validate_source_type_allowed("coordinator", "OPREQ")  # must not raise

    def test_coordinator_may_not_create_opres(self):
        with self.assertRaises(schema.ValidationError):
            schema.validate_source_type_allowed("coordinator", "OPRES")

    def test_coordinator_may_not_create_devreq(self):
        with self.assertRaises(schema.ValidationError):
            schema.validate_source_type_allowed("coordinator", "DEVREQ")

    def test_operator_may_create_opres(self):
        schema.validate_source_type_allowed("operator", "OPRES")

    def test_operator_may_create_devreq(self):
        schema.validate_source_type_allowed("operator", "DEVREQ")

    def test_operator_may_not_create_opreq(self):
        with self.assertRaises(schema.ValidationError):
            schema.validate_source_type_allowed("operator", "OPREQ")

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(schema.ValidationError):
            schema.validate_source_type_allowed("root", "OPREQ")


class LocalRelationshipTests(unittest.TestCase):
    def test_new_opreq_with_empty_in_reply_to_is_ok(self):
        msg = _base_message(type="OPREQ", in_reply_to=None)
        schema.validate_local_relationships(msg)

    def test_opreq_with_in_reply_to_is_rejected(self):
        msg = _base_message(type="OPREQ", in_reply_to=ids.generate_request_id())
        with self.assertRaises(schema.ValidationError):
            schema.validate_local_relationships(msg)

    def test_standalone_devreq_with_empty_in_reply_to_is_ok(self):
        msg = _base_message(type="DEVREQ", source="operator", in_reply_to=None)
        schema.validate_local_relationships(msg)

    def test_reply_opres_with_in_reply_to_is_ok(self):
        msg = _base_message(type="OPRES", source="operator", in_reply_to=ids.generate_request_id())
        schema.validate_local_relationships(msg)


class ReplyTargetTests(unittest.TestCase):
    def test_opres_replying_to_opreq_same_conversation_is_ok(self):
        opreq = _base_message(type="OPREQ")
        opres = _base_message(
            type="OPRES",
            source="operator",
            in_reply_to=opreq["request_id"],
            conversation_id=opreq["conversation_id"],
        )
        schema.validate_reply_target(opres, opreq)

    def test_devreq_replying_to_opreq_is_ok(self):
        opreq = _base_message(type="OPREQ")
        devreq = _base_message(
            type="DEVREQ",
            source="operator",
            in_reply_to=opreq["request_id"],
            conversation_id=opreq["conversation_id"],
        )
        schema.validate_reply_target(devreq, opreq)

    def test_opres_replying_to_opres_is_rejected(self):
        target = _base_message(type="OPRES", source="operator")
        opres = _base_message(
            type="OPRES",
            source="operator",
            in_reply_to=target["request_id"],
            conversation_id=target["conversation_id"],
        )
        with self.assertRaises(schema.ValidationError):
            schema.validate_reply_target(opres, target)

    def test_conversation_mismatch_is_rejected(self):
        opreq = _base_message(type="OPREQ")
        opres = _base_message(
            type="OPRES",
            source="operator",
            in_reply_to=opreq["request_id"],
            conversation_id=ids.generate_conversation_id(),
        )
        with self.assertRaises(schema.ValidationError):
            schema.validate_reply_target(opres, opreq)


if __name__ == "__main__":
    unittest.main()
