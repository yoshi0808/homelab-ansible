#!/usr/bin/env python3
"""Local fixtures for page rendering and Debian-version selection."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROLE / "module_utils"))
import proxmox_running_versions as page
sys.modules["ansible.module_utils.proxmox_running_versions"] = page

spec = importlib.util.spec_from_file_location("collect", ROLE / "files" / "collect.py")
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)

notion_spec = importlib.util.spec_from_file_location(
    "proxmox_running_versions_notion", ROLE / "library" / "proxmox_running_versions_notion.py"
)
notion = importlib.util.module_from_spec(notion_spec)
notion_spec.loader.exec_module(notion)


class RunningVersionsLogicTest(unittest.TestCase):
    def observation(self, suffix="23"):
        return {"ok": True, "values": {
            "kernel": "6.14.0-1-pve", "kernel_pkg": "7.0.14-" + suffix,
            "kernel_installed": "7.0.14-" + suffix, "pve_manager": "8.3.2",
            "pve_qemu_kvm_installed": "9.2.0", "collected_at": "2026-10-16T07:00:00+0900",
        }}

    def test_kernel_candidates_exclude_meta_and_use_dpkg_order(self):
        rows = "\n".join((
            "ii proxmox-kernel-6.8.12-4-pve 6.8.12-4",
            "ii proxmox-kernel-7.0 7.0.0",
            "ii proxmox-kernel-6.14.11-2-pve-signed 6.14.11-2",
            "rc proxmox-kernel-9.0.0-1-pve 9.0.0-1",
            "ii proxmox-kernel-helper 7.0.0",
            "ii proxmox-kernel-fake-pve 99.0.0",
            "ii proxmox-kernel-6.14.11-2-pve 6.14.11-2~beta1",
        ))
        self.assertEqual("6.14.11-2", collect.installed_kernel_version(rows))

    def test_unreachable_and_error_have_unknown_versions(self):
        nodes, overall, failed = page.normalize(
            {"pve1": {"status": "unreachable"}, "pve2": {"ok": False}}, "/missing"
        )
        self.assertEqual("error", overall)
        self.assertTrue(failed)
        self.assertEqual("unknown", nodes["pve1"]["kernel"])
        self.assertEqual("unknown", nodes["pve2"]["kernel_installed"])

    def test_latest_apply_failed_is_factual_not_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "20261016T070000_pve1_apply.json").write_text(
                '{"run_timestamp":"2026-10-16T07:00:00+0900","result":"FAILED","reboot_done":false}', encoding="utf-8"
            )
            nodes, overall, failed = page.normalize(
                {"pve1": self.observation(), "pve2": self.observation()}, directory
            )
        self.assertEqual("ok", overall)
        self.assertFalse(failed)
        self.assertEqual("FAILED", nodes["pve1"]["last_apply_result"])
        self.assertEqual("unknown", nodes["pve2"]["last_apply_at"])

    def test_complete_document_is_fixed_key_order(self):
        nodes, overall, _ = page.normalize(
            {"pve1": self.observation(), "pve2": self.observation("24")}, "/missing"
        )
        text = page.render_complete(nodes, "2026-10-16T07:00:00+0900", overall)
        self.assertIn("state: complete", text)
        self.assertLess(text.index("node: pve1"), text.index("node: pve2"))
        self.assertIn("last_apply_result: unknown", text)

    def test_second_update_failure_leaves_updating_and_retry_completes(self):
        nodes, overall, _ = page.normalize(
            {"pve1": self.observation(), "pve2": self.observation()}, "/missing"
        )

        class FakeClient:
            def children(self, unused_page):
                return [{"id": value, "type": "code"} for value in ("header", "pve1", "pve2")]

        writes = {}
        fail = [True]
        original_patch = notion.patch_code
        try:
            def patch(client, block_id, text):
                writes[block_id] = text
                if block_id == "pve1" and fail[0]:
                    raise notion.PublishError("fake_second_update_failure")

            notion.patch_code = patch
            with self.assertRaises(notion.PublishError):
                notion.publish(FakeClient(), "page", nodes, "2026-10-16T07:00:00+0900", overall)
            self.assertTrue(writes["header"].startswith("state: updating"))
            fail[0] = False
            notion.publish(FakeClient(), "page", nodes, "2026-10-16T07:00:00+0900", overall)
            self.assertTrue(writes["header"].startswith("state: complete"))
        finally:
            notion.patch_code = original_patch

    def test_empty_paragraph_is_replaced_with_three_managed_code_blocks(self):
        nodes, overall, _ = page.normalize(
            {"pve1": self.observation(), "pve2": self.observation()}, "/missing"
        )

        class FakeClient:
            def __init__(self):
                self.blocks = [{"id": "empty", "type": "paragraph", "has_children": False, "paragraph": {"rich_text": []}}]
                self.contents = {}
                self.calls = []

            def children(self, unused_page):
                return list(self.blocks)

            def call(self, method, path, body=None, retry=True):
                self.calls.append((method, path, retry))
                if method == "DELETE":
                    self.blocks = []
                    return {}
                if path.endswith("/children"):
                    block_id = "block" + str(len(self.blocks))
                    self.blocks.append({"id": block_id, "type": "code"})
                    self.contents[block_id] = body["children"][0]["code"]["rich_text"][0]["text"]["content"]
                    return {"results": [{"id": block_id}]}
                block_id = path.rsplit("/", 1)[-1]
                self.contents[block_id] = body["code"]["rich_text"][0]["text"]["content"]
                return {}

        client = FakeClient()
        notion.publish(client, "page", nodes, "2026-10-16T07:00:00+0900", overall)
        self.assertEqual(["code", "code", "code"], [block["type"] for block in client.blocks])
        self.assertTrue(client.contents["block0"].startswith("state: complete"))
        self.assertEqual([False, False, False], [retry for _, path, retry in client.calls if path.endswith("/children")])

    def test_lost_append_response_recovers_without_duplicate_blocks(self):
        nodes, overall, _ = page.normalize(
            {"pve1": self.observation(), "pve2": self.observation()}, "/missing"
        )

        class FakeClient:
            def __init__(self):
                self.blocks = []
                self.contents = {}
                self.lose_first_append_response = True

            def children(self, unused_page):
                return list(self.blocks)

            def call(self, method, path, body=None, retry=True):
                if path.endswith("/children"):
                    if retry:
                        raise AssertionError("append must not be retried")
                    block_id = "block" + str(len(self.blocks))
                    self.blocks.append({"id": block_id, "type": "code"})
                    self.contents[block_id] = body["children"][0]["code"]["rich_text"][0]["text"]["content"]
                    if self.lose_first_append_response:
                        self.lose_first_append_response = False
                        raise notion.PublishError("response_unknown")
                    return {"results": [{"id": block_id}]}
                block_id = path.rsplit("/", 1)[-1]
                self.contents[block_id] = body["code"]["rich_text"][0]["text"]["content"]
                return {}

        client = FakeClient()
        with self.assertRaisesRegex(notion.PublishError, "response_unknown"):
            notion.publish(client, "page", nodes, "2026-10-16T07:00:00+0900", overall)
        notion.publish(client, "page", nodes, "2026-10-16T07:00:00+0900", overall)
        self.assertEqual(["code", "code", "code"], [block["type"] for block in client.blocks])
        self.assertTrue(client.contents["block0"].startswith("state: complete"))

    def test_nonempty_paragraph_is_refused(self):
        nodes, overall, _ = page.normalize(
            {"pve1": self.observation(), "pve2": self.observation()}, "/missing"
        )

        class FakeClient:
            def children(self, unused_page):
                return [{"id": "note", "type": "paragraph", "paragraph": {
                    "rich_text": [{"plain_text": "operator note"}],
                }}]

        with self.assertRaisesRegex(notion.PublishError, "managed_blocks_invalid"):
            notion.publish(FakeClient(), "page", nodes, "2026-10-16T07:00:00+0900", overall)

    def test_empty_paragraph_with_children_is_refused(self):
        nodes, overall, _ = page.normalize(
            {"pve1": self.observation(), "pve2": self.observation()}, "/missing"
        )

        class FakeClient:
            def children(self, unused_page):
                return [{"id": "empty", "type": "paragraph", "has_children": True,
                         "paragraph": {"rich_text": []}}]

        with self.assertRaisesRegex(notion.PublishError, "managed_blocks_invalid"):
            notion.publish(FakeClient(), "page", nodes, "2026-10-16T07:00:00+0900", overall)

    def test_lock_rejects_concurrent_publisher(self):
        with tempfile.TemporaryDirectory() as directory:
            with notion.page_lock(directory):
                with self.assertRaisesRegex(notion.PublishError, "publication_busy"):
                    with notion.page_lock(directory):
                        pass


if __name__ == "__main__":
    unittest.main()
