#!/usr/bin/env python3
"""Fixtures for the v2 page contract; no host, Slack, or Notion I/O."""
import importlib.util
import gzip
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import warnings
from pathlib import Path


ROLE = Path(__file__).resolve().parents[1]
warnings.filterwarnings("ignore", category=ResourceWarning)
sys.path.insert(0, str(ROLE / "module_utils"))
import proxmox_running_versions as page
sys.modules["ansible.module_utils.proxmox_running_versions"] = page

collect_spec = importlib.util.spec_from_file_location("collect", ROLE / "files" / "collect.py")
collect = importlib.util.module_from_spec(collect_spec)
collect_spec.loader.exec_module(collect)
notion_spec = importlib.util.spec_from_file_location("proxmox_running_versions_notion", ROLE / "library" / "proxmox_running_versions_notion.py")
notion = importlib.util.module_from_spec(notion_spec)
notion_spec.loader.exec_module(notion)

ROLES = {"pve1": "pve", "pve2": "pve", "quory": "qdevice", "authy": "radius", "monnie": "monitoring"}


def observation(node):
    pve = node in page.PVE_NODES
    packages = [
        {"name": "pve-manager", "installed": "9.0.1", "candidate": "9.0.2", "proxmox_origin": True},
        {"name": "libpve-common-perl", "installed": "9.0.1", "candidate": "9.0.1", "proxmox_origin": True},
        {"name": "proxmox-kernel-6.14.0-2-pve", "installed": "6.14.0-2", "candidate": "6.14.0-2", "proxmox_origin": True},
        {"name": "proxmox-default-kernel", "installed": "1.0", "candidate": "1.0", "proxmox_origin": True},
        {"name": "proxmox-kernel-7.0", "installed": "7.0", "candidate": "7.0", "proxmox_origin": True},
        {"name": "debian-only", "installed": "1", "candidate": "2", "proxmox_origin": False},
        {"name": "apt", "installed": "3.0", "candidate": "3.0", "proxmox_origin": False},
        {"name": "linux-image-generic", "installed": "6.8", "candidate": "6.9", "proxmox_origin": False},
    ]
    values = {
        "os": "debian-13" if pve else "ubuntu-26.04",
        "kernel_running": "6.14.0-1-pve", "kernel_installed": "6.14.0-2",
        "kernel_reboot_required": "true", "packages": packages,
        "services": [{"library": "/usr/lib/libz.so", "processes": ["pveproxy"]}],
        "collected_at": "2026-11-14T07:00:00+0900",
    }
    if pve:
        values.update({"repo": "no-subscription", "pve_manager": "9.0.1", "vms_on_old_qemu": "2 (101,105)",
                       "apt_history": "Start-Date: 2026-11-14  07:01:00\nUpgrade: pve-manager:amd64 (9.0.1, 9.0.2)\n"})
    return {"ok": True, "values": values}


class RunningVersionsLogicTest(unittest.TestCase):
    def run_report_fixture(self, fixture_case, check=True, extra_vars=None, extra_env=None):
        command = ["ansible-playbook"]
        if check:
            command.append("--check")
        command += ["-i", "localhost,", "-c", "local", str(ROLE / "tests" / "fixtures" / "report_fixture.yml"),
                    "-e", '{{"fixture_case":"{}"}}'.format(fixture_case)]
        for value in extra_vars or []:
            command += ["-e", value]
        environment = os.environ.copy()
        environment["ANSIBLE_ROLES_PATH"] = "{}:{}".format(ROLE / "tests" / "fake_roles", ROLE.parent)
        environment.update(extra_env or {})
        return subprocess.run(command, cwd=ROLE.parents[1], text=True, capture_output=True, check=False, env=environment)

    def normalized(self, changes=None, directory="/missing"):
        observations = {node: observation(node) for node in page.NODES}
        observations.update(changes or {})
        return page.normalize(observations, directory, ROLES)

    def publication_fixture(self):
        """Build a v2 document with split package blocks for publish tests."""
        nodes, overall, _ = self.normalized()
        nodes["pve1"]["package_lines"] = [
            "fixture-package-{:02d}: {}".format(index, "x" * 90)
            for index in range(40)
        ]
        nodes["pve1"]["package_count"] = len(nodes["pve1"]["package_lines"])
        blocks = page.render_blocks(nodes, "2026-11-14T07:00:01+09:00", overall)
        self.assertGreater(len(page.package_blocks(nodes["pve1"]["package_lines"])), 1)
        self.assertGreater(len(blocks), len(page.NODES) * 2)
        return nodes, overall, blocks

    def test_fixed_roles_and_keys_render_for_all_five_nodes(self):
        nodes, overall, failed = self.normalized()
        self.assertEqual("ok", overall)
        self.assertFalse(failed)
        self.assertEqual(ROLES, {node: nodes[node]["role"] for node in page.NODES})
        self.assertEqual(page.NODE_KEYS, tuple(line.split(":", 1)[0] for line in page.node_block(nodes["pve1"]).splitlines()))
        rendered = page.render_complete(nodes, "2026-11-14T07:00:01+0900", overall)
        self.assertIn("schema_version: 2", rendered)
        self.assertLess(rendered.index("node: pve2"), rendered.index("node: quory"))
        self.assertIn("vms_on_old_qemu: n/a", rendered)
        self.assertEqual("count=1; /usr/lib/libz.so -> pveproxy", nodes["pve1"]["services_restart_required"])

    def test_kernel_candidates_use_dpkg_order_and_exclude_meta(self):
        rows = "\n".join((
            "ii \tproxmox-kernel-6.8.12-4-pve\t6.8.12-4",
            "ii \tproxmox-kernel-7.0\t7.0.0",
            "ii \tproxmox-kernel-6.14.11-2-pve-signed\t6.14.11-2",
            "rc \tproxmox-kernel-9.0.0-1-pve\t9.0.0-1",
            "ii \tproxmox-kernel-helper\t7.0.0",
            "ii \tproxmox-kernel-fake-pve\t99.0.0",
            "ii \tproxmox-kernel-6.14.11-2-pve\t6.14.11-2~beta1",
        ))
        self.assertEqual("6.14.11-2", collect.installed_kernel_version(rows, True))

    def test_raw_policy_fixture_selects_origin_and_excludes_kernel_entity(self):
        policy = """pve-manager:\n  Installed: 9.0.1\n  Candidate: 9.0.2\n  Version table:\n     9.0.2 500\n        500 http://download.proxmox.com/debian/pve trixie/pve-no-subscription\n *** 9.0.1 100\n        100 /var/lib/dpkg/status\nold-pve:\n  Installed: 1\n  Candidate: 2\n  Version table:\n     2 500\n        500 http://download.proxmox.com/debian/pve trixie/pve-no-subscription\ndebian-only:\n  Installed: 1\n  Candidate: 2\n  Version table:\n     2 500\n        500 http://deb.debian.org/debian trixie/main\n"""
        records = collect.parse_policy(policy, [("pve-manager", "9.0.1"), ("old-pve", "1"), ("debian-only", "1")])
        self.assertTrue(next(row for row in records if row["name"] == "pve-manager")["proxmox_origin"])
        self.assertTrue(next(row for row in records if row["name"] == "old-pve")["proxmox_origin"])
        self.assertFalse(next(row for row in records if row["name"] == "debian-only")["proxmox_origin"])
        lines = page.package_lines(observation("pve1")["values"]["packages"], True)
        self.assertIn("pve-manager: 9.0.1 (candidate 9.0.2)", lines)
        self.assertIn("proxmox-default-kernel: 1.0", lines)
        self.assertIn("proxmox-kernel-7.0: 7.0", lines)
        self.assertFalse(any("6.14.0-2-pve" in line for line in lines))
        self.assertFalse(any("debian-only" in line for line in lines))

    def test_apply_trigger_and_history_fixtures(self):
        cases = {"none": "false", "reboot-required-file": "true", "kernel-version-mismatch:6.14": "true", "": "unknown", "unexpected": "unknown"}
        for trigger, expected in cases.items():
            with tempfile.TemporaryDirectory() as directory:
                Path(directory, "20261114T070000_pve1_apply.json").write_text(
                    '{{"run_timestamp":"20261114T070000","result":"SUCCESS","reboot_done":false,"reboot_trigger":"{}"}}'.format(trigger), encoding="utf-8")
                report = page.latest_apply(directory, "pve1")
                self.assertEqual(expected, report["reboot_required"])
                self.assertEqual("2026-11-14T07:00:00+09:00", report["last_apply_at"])
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "20261115T070000_pve1_apply.json").write_text(
                '{"run_timestamp":"20261115T070000","result":"FAILED","reboot_done":false,"reboot_trigger":"none"}', encoding="utf-8")
            report = page.latest_apply(directory, "pve1")
            self.assertEqual("false", report["reboot_required"])
            self.assertEqual("FAILED", report["last_apply_result"])
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "20261115T070000_pve1_apply.json").write_text(
                '{"run_timestamp":"20261115T070000","result":"SUCCESS","reboot_done":false}', encoding="utf-8")
            self.assertEqual("unknown", page.latest_apply(directory, "pve1")["reboot_required"])
        self.assertEqual("pve-manager 9.0.1->9.0.2", page.upgraded_after(
            "Start-Date: 2026-11-14  07:01:00\nUpgrade: pve-manager:amd64 (9.0.1, 9.0.2)\n", "2026-11-14T07:00:00+09:00"))

    def test_history_fixture_uses_current_and_rotated_logs_and_fail_closed_values(self):
        rotated = "Start-Date: 2026-11-14  07:01:00\nUpgrade: apt:amd64 (3.0.0, 3.0.1)\n"
        current = "Start-Date: 2026-11-14  07:02:00\nUpgrade: pve-manager:amd64 (9.0.1, 9.0.2)\n"
        with tempfile.TemporaryDirectory() as directory:
            rotated_path = Path(directory, "history.log.1.gz")
            current_path = Path(directory, "history.log")
            with gzip.open(rotated_path, "wt", encoding="utf-8") as stream:
                stream.write(rotated)
            current_path.write_text(current, encoding="utf-8")
            history = collect.history((rotated_path, current_path))
        rendered = page.upgraded_after(history, "2026-11-14T07:00:00+09:00")
        self.assertEqual("apt 3.0.0->3.0.1, pve-manager 9.0.1->9.0.2", rendered)
        self.assertEqual("none", page.upgraded_after("Start-Date: 2026-11-14  06:59:59\nUpgrade: apt:amd64 (3.0.0, 3.0.1)\n", "2026-11-14T07:00:00+09:00"))
        self.assertEqual("unknown", page.upgraded_after("not an apt history", "2026-11-14T07:00:00+09:00"))

    def test_running_qemu_fixture_counts_replaced_and_current_executables(self):
        qm_list = "VMID NAME STATUS MEM\n101 alpha running 0\n102 beta running 0\n103 stopped stopped 0\n105 gamma running 0\n"
        process_rows = "1001 /usr/bin/kvm -id 101 -name alpha\n1002 /usr/bin/kvm -id 102 -name beta\n1005 /usr/bin/kvm -id 105 -name gamma\n"
        executables = {"1001": "/usr/bin/kvm (deleted)", "1002": "/usr/bin/kvm", "1005": "/usr/bin/kvm (deleted)"}
        self.assertEqual("2 (101,105)", collect.old_qemu_vmids(qm_list, process_rows, executables))
        self.assertEqual("0", collect.old_qemu_vmids(qm_list, process_rows, {key: "/usr/bin/kvm" for key in executables}))
        self.assertEqual("unknown", collect.old_qemu_vmids(qm_list, process_rows, {"1001": "/usr/bin/kvm (deleted)"}))

    def test_pve_collection_consumes_running_qemu_result(self):
        original_run, original_qemu = collect.run, collect.running_qemu_executables
        try:
            collect.run = lambda *argv: "pve-manager/9.0.2\n" if argv[0] == "pveversion" else " 500 http://download.proxmox.com/debian/pve trixie/pve-no-subscription\n"
            collect.running_qemu_executables = lambda: "2 (101,105)"
            self.assertEqual("2 (101,105)", collect.pve_values()["vms_on_old_qemu"])
        finally:
            collect.run, collect.running_qemu_executables = original_run, original_qemu

    def test_qemu_failure_does_not_clear_pve_manager_or_repo(self):
        original_run, original_qemu = collect.run, collect.running_qemu_executables
        try:
            def fixture_run(*argv):
                if argv[0] == "pveversion":
                    return "pve-manager/9.0.2\n"
                return " 500 http://download.proxmox.com/debian/pve trixie/pve-no-subscription\n"
            collect.run = fixture_run
            collect.running_qemu_executables = lambda: (_ for _ in ()).throw(collect.CollectionError("qemu_executable_unreadable"))
            values = collect.pve_values()
            self.assertEqual("9.0.2", values["pve_manager"])
            self.assertEqual("no-subscription", values["repo"])
            self.assertEqual("unknown", values["vms_on_old_qemu"])
        finally:
            collect.run, collect.running_qemu_executables = original_run, original_qemu

    def test_blocks_split_and_count_matches_package_count(self):
        nodes, _, _ = self.normalized()
        nodes["pve1"]["package_lines"] = ["pkg{:03d}: {}".format(index, "x" * 90) for index in range(60)]
        nodes["pve1"]["package_count"] = len(nodes["pve1"]["package_lines"])
        blocks = page.package_blocks(nodes["pve1"]["package_lines"])
        self.assertGreater(len(blocks), 1)
        self.assertEqual(60, sum(len(block.splitlines()) - 1 for block in blocks))
        self.assertTrue(all(len(block) <= page.PACKAGE_BLOCK_LIMIT + 20 for block in blocks))

    def test_node_block_caps_services_and_apply_upgrades_below_notion_limit(self):
        nodes, _, _ = self.normalized()
        nodes["pve1"]["services_restart_required"] = "\n".join(
            "/usr/lib/lib{:02d}.so -> {}".format(index, ", ".join("process{}".format(number) for number in range(10)))
            for index in range(20)
        )
        nodes["pve1"]["last_apply_upgraded"] = ", ".join(
            "package{:02d} {}->{}".format(index, "a" * 30, "b" * 30) for index in range(40)
        )
        block = page.node_block(nodes["pve1"])
        self.assertLessEqual(len(block), page.NODE_BLOCK_LIMIT)
        self.assertIn("(+", block)
        with self.assertRaisesRegex(notion.PublishError, "block_text_too_large"):
            notion.code_block("x" * 2001)

    def test_module_converts_unrenderable_node_block_to_static_failure(self):
        original_module, original_render = notion.AnsibleModule, notion.render_complete
        results = []
        class Exit(Exception):
            pass
        class Module:
            params = {"observations": {node: observation(node) for node in page.NODES}, "apply_report_dir": "/missing",
                      "node_roles": ROLES, "page": "fixture", "token_file": "/must-not-be-read",
                      "lock_directory": "/tmp/fixture", "suppress": True}
            check_mode = True
            def __init__(self, *unused_args, **unused_kwargs):
                pass
            def fail_json(self, **result):
                results.append(result)
                raise Exit()
        try:
            notion.AnsibleModule = Module
            notion.render_complete = lambda *unused: (_ for _ in ()).throw(ValueError("node_block_too_large"))
            with self.assertRaises(Exit):
                notion.main()
        finally:
            notion.AnsibleModule, notion.render_complete = original_module, original_render
        self.assertEqual("render_invalid", results[0]["msg"])

    def test_partial_and_pve_or_all_unreachable_are_errors(self):
        _, overall, failed = self.normalized({"authy": {"status": "unreachable"}})
        self.assertEqual(("partial", False), (overall, failed))
        _, overall, failed = self.normalized({"pve1": {"status": "unreachable"}, "pve2": {"status": "unreachable"}})
        self.assertEqual(("error", True), (overall, failed))

    def test_unreachable_and_required_error_nodes_have_fixed_unknown_shape(self):
        def assert_unknown_node(node, name, status):
            self.assertEqual(name, node["node"])
            self.assertEqual(status, node["status"])
            self.assertEqual(ROLES[name], node["role"])
            self.assertEqual(0, node["package_count"])
            for key in page.NODE_KEYS:
                if key not in ("node", "status", "role", "package_count"):
                    self.assertEqual("unknown", node[key], key)

        nodes, overall, failed = self.normalized({"authy": {"status": "unreachable"}})
        self.assertEqual(("partial", False), (overall, failed))
        assert_unknown_node(nodes["authy"], "authy", "unreachable")

        missing_kernel = observation("pve1")
        missing_kernel["values"].pop("kernel_installed")
        invalid_reboot = observation("pve1")
        invalid_reboot["values"]["kernel_reboot_required"] = "invalid"
        invalid_timestamp = observation("pve1")
        invalid_timestamp["values"]["collected_at"] = "not-an-iso8601-timestamp"
        no_selected_packages = observation("pve1")
        no_selected_packages["values"]["packages"] = []
        cases = (
            {"ok": False},
            missing_kernel,
            invalid_reboot,
            invalid_timestamp,
            no_selected_packages,
        )
        for malformed in cases:
            nodes, overall, failed = self.normalized({"pve1": malformed})
            self.assertEqual(("error", True), (overall, failed))
            assert_unknown_node(nodes["pve1"], "pve1", "error")

    def test_report_fixture_exercises_partial_and_error_rc_and_one_alert(self):
        partial = self.run_report_fixture("partial")
        self.assertEqual(0, partial.returncode, partial.stdout + partial.stderr)
        self.assertIn("status: partial", partial.stdout)
        self.assertNotIn("fixture-alert", partial.stdout)
        for fixture_case in ("pve_unreachable", "all_unreachable", "required_error"):
            result = self.run_report_fixture(fixture_case)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("status: error", result.stdout)
            self.assertEqual(1, result.stdout.count("fixture-alert"))
            self.assertNotIn("/must-not-be-read", result.stdout + result.stderr)
            if fixture_case == "required_error":
                self.assertIn("node: authy", result.stdout)
                self.assertIn("kernel_running: unknown", result.stdout)
                self.assertIn("package_count: 0", result.stdout)

    def test_report_fixture_exercises_all_three_suppression_paths(self):
        cases = (
            (True, [], {}),
            (False, ['{"skip_notifications":true}'], {}),
            (False, [], {"CLAUDECODE": "fixture"}),
        )
        for check, extra_vars, extra_env in cases:
            result = self.run_report_fixture("normal", check, extra_vars, extra_env)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("schema_version: 2", result.stdout)
            self.assertNotIn("/must-not-be-read", result.stdout + result.stderr)
            self.assertNotIn("fixture-alert", result.stdout)
        _, overall, failed = self.normalized({node: {"status": "unreachable"} for node in page.NODES})
        self.assertEqual(("error", True), (overall, failed))

    def test_report_fixture_exercises_fake_notion_401_and_404(self):
        for status in ("401", "404"):
            result = self.run_report_fixture("normal", check=False, extra_env={
                "ANSIBLE_ROLES_PATH": "{}:{}:{}".format(ROLE / "tests" / "fake_notion_roles", ROLE / "tests" / "fake_roles", ROLE.parent),
                "PROXMOX_RUNNING_VERSIONS_FIXTURE_HTTP_STATUS": status,
            })
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(1, result.stdout.count("fixture-alert"))
            self.assertIn("reason=http_{}".format(status), result.stdout)
            self.assertNotIn("/must-not-be-read", result.stdout + result.stderr)

    def test_auxiliary_unknown_does_not_fail_node(self):
        changed = observation("pve1")
        changed["values"].pop("services")
        nodes, overall, failed = self.normalized({"pve1": changed})
        self.assertEqual(("ok", False), (overall, failed))
        self.assertEqual("unknown", nodes["pve1"]["services_restart_required"])

    def test_suppression_gate_precedes_client_and_token_io(self):
        observations = {node: observation(node) for node in page.NODES}
        original_module, original_client = notion.AnsibleModule, notion.Client
        class Exit(Exception):
            pass
        for check_mode, suppress in ((True, False), (False, True), (False, True)):
            class Module:
                params = {"observations": observations, "apply_report_dir": "/missing", "node_roles": ROLES,
                          "page": "fixture", "token_file": "/must-not-be-read", "lock_directory": "/tmp/fixture", "suppress": suppress}
                def __init__(self, *unused_args, **unused_kwargs):
                    self.check_mode = check_mode
                def exit_json(self, **result):
                    self.result = result
                    raise Exit()
            try:
                notion.AnsibleModule = Module
                notion.Client = lambda unused_path: self.fail("suppressed module read its token")
                with self.assertRaises(Exit):
                    notion.main()
            finally:
                notion.AnsibleModule, notion.Client = original_module, original_client
        task = (ROLE / "tasks" / "report.yml").read_text(encoding="utf-8")
        self.assertIn("ansible_check_mode or (skip_notifications", task)
        self.assertIn("lookup('env', 'CLAUDECODE')", task)

    def test_fake_401_and_404_expose_only_static_codes(self):
        class Opener:
            def __init__(self, status):
                self.status = status
            def open(self, unused_request, timeout):
                class FixtureHTTPError(urllib.error.HTTPError):
                    def __del__(self):
                        pass
                error = FixtureHTTPError("https://fixture.invalid", self.status, "error", {}, None)
                error.close()
                raise error
        for status in (401, 404):
            client = object.__new__(notion.Client)
            client.token, client.opener = "fixture-secret", Opener(status)
            with self.assertRaisesRegex(notion.PublishError, "http_{}".format(status)) as caught:
                client.call("PATCH", "/blocks/fake")
            self.assertNotIn("fixture-secret", str(caught.exception))

    def test_fake_body_or_complete_failure_leaves_updating_then_recovers(self):
        nodes, overall, _ = self.normalized()
        class FakeClient:
            def __init__(self):
                self.blocks = [{"id": "header", "type": "code"}, {"id": "body", "type": "code"}]
                self.contents, self.fail_block = {}, "body"
            def children(self, unused_page):
                return list(self.blocks)
            def call(self, method, path, body=None, retry=True):
                if path.endswith("/children"):
                    block_id = "block{}".format(len(self.blocks))
                    self.blocks.append({"id": block_id, "type": "code"})
                    self.contents[block_id] = body["children"][0]["code"]["rich_text"][0]["text"]["content"]
                    return {"results": [{"id": block_id}]}
                block_id = path.rsplit("/", 1)[-1]
                content = body["code"]["rich_text"][0]["text"]["content"]
                if block_id == self.fail_block and (block_id != "header" or content.startswith("schema_version: 2\nstate: complete")):
                    raise notion.PublishError("fake_update_failure")
                self.contents[block_id] = content
                return {}
        client = FakeClient()
        with self.assertRaisesRegex(notion.PublishError, "fake_update_failure"):
            notion.publish(client, "page", nodes, "2026-11-14T07:00:01+0900", overall)
        self.assertIn("state: updating", client.contents["header"])
        client.fail_block = "header"
        with self.assertRaisesRegex(notion.PublishError, "fake_update_failure"):
            notion.publish(client, "page", nodes, "2026-11-14T07:00:01+0900", overall)
        self.assertIn("state: updating", client.contents["header"])
        client.fail_block = ""
        notion.publish(client, "page", nodes, "2026-11-14T07:00:01+0900", overall)
        self.assertIn("state: complete", client.contents["header"])

    def test_empty_placeholder_is_replaced_with_all_v2_managed_blocks(self):
        nodes, overall, desired = self.publication_fixture()

        class FakeClient:
            def __init__(self):
                self.blocks = [{"id": "empty", "type": "paragraph", "has_children": False,
                                "paragraph": {"rich_text": []}}]
                self.contents, self.calls = {}, []

            def children(self, unused_page):
                return list(self.blocks)

            def call(self, method, path, body=None, retry=True):
                self.calls.append((method, path, retry))
                if method == "DELETE":
                    self.blocks = []
                    return {}
                if path.endswith("/children"):
                    block_id = "block{}".format(len(self.blocks))
                    self.blocks.append({"id": block_id, "type": "code"})
                    self.contents[block_id] = body["children"][0]["code"]["rich_text"][0]["text"]["content"]
                    return {"results": [{"id": block_id}]}
                block_id = path.rsplit("/", 1)[-1]
                self.contents[block_id] = body["code"]["rich_text"][0]["text"]["content"]
                return {}

        client = FakeClient()
        notion.publish(client, "page", nodes, "2026-11-14T07:00:01+09:00", overall)
        self.assertEqual(len(desired), len(client.blocks))
        self.assertEqual(["code"] * len(desired), [block["type"] for block in client.blocks])
        self.assertEqual(desired[0], client.contents["block0"])
        self.assertEqual(len(desired), sum(path.endswith("/children") for _, path, _ in client.calls))
        self.assertTrue(all(not retry for _, path, retry in client.calls if path.endswith("/children")))

    def test_lost_v2_append_response_never_replays_or_duplicates_blocks(self):
        nodes, overall, desired = self.publication_fixture()

        class FakeClient:
            def __init__(self):
                self.blocks, self.contents = [], {}
                self.lose_first_append_response = True
                self.append_calls = 0

            def children(self, unused_page):
                return list(self.blocks)

            def call(self, method, path, body=None, retry=True):
                if path.endswith("/children"):
                    self.append_calls += 1
                    if retry:
                        raise AssertionError("append must not be retried")
                    block_id = "block{}".format(len(self.blocks))
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
            notion.publish(client, "page", nodes, "2026-11-14T07:00:01+09:00", overall)
        notion.publish(client, "page", nodes, "2026-11-14T07:00:01+09:00", overall)
        self.assertEqual(len(desired), len(client.blocks))
        self.assertEqual(len(desired), client.append_calls)
        self.assertEqual(desired[0], client.contents["block0"])

    def test_nonempty_human_paragraph_is_not_removed(self):
        nodes, overall, unused_desired = self.publication_fixture()

        class FakeClient:
            def __init__(self):
                self.calls = []

            def children(self, unused_page):
                return [{"id": "note", "type": "paragraph", "has_children": False,
                         "paragraph": {"rich_text": [{"plain_text": "operator note"}]}}]

            def call(self, method, path, body=None, retry=True):
                self.calls.append((method, path))
                return {}

        client = FakeClient()
        with self.assertRaisesRegex(notion.PublishError, "managed_blocks_invalid"):
            notion.publish(client, "page", nodes, "2026-11-14T07:00:01+09:00", overall)
        self.assertEqual([], client.calls)

    def test_empty_human_paragraph_with_children_is_not_removed(self):
        nodes, overall, unused_desired = self.publication_fixture()

        class FakeClient:
            def __init__(self):
                self.calls = []

            def children(self, unused_page):
                return [{"id": "empty", "type": "paragraph", "has_children": True,
                         "paragraph": {"rich_text": []}}]

            def call(self, method, path, body=None, retry=True):
                self.calls.append((method, path))
                return {}

        client = FakeClient()
        with self.assertRaisesRegex(notion.PublishError, "managed_blocks_invalid"):
            notion.publish(client, "page", nodes, "2026-11-14T07:00:01+09:00", overall)
        self.assertEqual([], client.calls)

    def test_page_lock_rejects_concurrent_v2_publisher(self):
        with tempfile.TemporaryDirectory() as directory:
            with notion.page_lock(directory):
                with self.assertRaisesRegex(notion.PublishError, "publication_busy"):
                    with notion.page_lock(directory):
                        pass


if __name__ == "__main__":
    unittest.main()
