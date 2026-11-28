#!/usr/bin/env python3
"""AC8 fixtures for the pure old-kernel parser and simulation validator."""
import importlib.util
import pathlib
import re
import unittest

module_path = pathlib.Path(__file__).parents[1] / "files" / "proxmox-kernel-cleanup-evaluate.py"
spec = importlib.util.spec_from_file_location("kernel_cleanup", module_path)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)

BOOT = "Manually selected kernels:\nNone\nAutomatically selected kernels:\n6.17.13-21-pve\n7.0.14-28-pve\n7.0.14-30-pve\n"
PACKAGES = "ii \tproxmox-kernel-6.17.2-1-pve-signed\t6.17.2-1\nrc \tproxmox-kernel-6.17.3-2-pve-signed\t6.17.3-2\nii \tproxmox-kernel-6.17.13-21-pve-signed\t6.17.13-21\nii \tproxmox-kernel-7.0.2-6-pve-signed\t7.0.2-6\nii \tproxmox-kernel-7.0.14-28-pve-signed\t7.0.14-28\nii \tproxmox-kernel-7.0.14-30-pve-signed\t7.0.14-30\nii \tproxmox-kernel-7.0\t7.0.14-30\nii \tproxmox-ve\t9.3.0\n"
MEASURED_OUTPUT = pathlib.Path(__file__).parents[3] / "docs" / "ai" / "reviews" / "proxmox_old_kernel_cleanup" / "2026-11-28_001a_measured_output.md"


def measured_blocks():
    """Read the approved raw-output fixture without copying it into this test."""
    return re.findall(r"```text\n(.*?)\n```", MEASURED_OUTPUT.read_text(), flags=re.DOTALL)


class KernelCleanupEvaluateTest(unittest.TestCase):
    def test_version_order_is_numeric_and_unknown_formats_fail_closed(self):
        self.assertLess(cleanup.version_key('7.0.14-9-pve'), cleanup.version_key('7.0.14-30-pve'))
        for version in ['7.0.14-rc1-pve', '7.a.14-30-pve', '7.0.14-30.1-pve']:
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'unsupported kernel version format'):
                cleanup.version_key(version)

    def test_partial_purge_reports_observed_absences(self):
        targets = ['proxmox-kernel-6.17.2-1-pve-signed', 'proxmox-kernel-6.17.3-2-pve-signed']
        # A config-only rc record still needs purge; un/pn records mean absence.
        result = cleanup.evaluate_post_inventory(PACKAGES.replace('ii \t' + targets[0], 'un \t' + targets[0]), targets)
        self.assertEqual(result['removed'], targets[:1])
        self.assertNotIn('packages', result)

    def test_actual_boot_tool_shape_and_rc_are_parsed(self):
        result = cleanup.evaluate_inventory("7.0.14-30-pve", PACKAGES, BOOT)
        self.assertEqual(result["keep_kernels"], ["6.17.13-21-pve", "7.0.14-28-pve", "7.0.14-30-pve"])
        self.assertEqual(result["targets"], ["proxmox-kernel-6.17.2-1-pve-signed", "proxmox-kernel-6.17.3-2-pve-signed", "proxmox-kernel-7.0.2-6-pve-signed"])

    def test_measured_output_is_used_directly_as_fixture(self):
        pve1_boot, pve2_boot, apt_output, dpkg_output = measured_blocks()
        expected_keep = ["6.17.13-21-pve", "7.0.14-28-pve", "7.0.14-30-pve"]
        self.assertEqual(cleanup.parse_boot_tool(pve1_boot), expected_keep)
        self.assertEqual(cleanup.parse_boot_tool(pve2_boot), expected_keep)
        apt_result = cleanup.validate_simulations(
            ["proxmox-kernel-6.17.13-21-pve-signed"], 0, "dpkg simulation", 0, apt_output)
        self.assertFalse(apt_result["valid"])
        self.assertEqual(apt_result["reason"], "apt simulation proposes installs or configuration")
        dpkg_result = cleanup.validate_simulations(
            ["proxmox-kernel-6.17.13-21-pve-signed"], 1, dpkg_output, 0, apt_output)
        self.assertFalse(dpkg_result["valid"])
        self.assertEqual(dpkg_result["reason"], "dpkg simulation failed or returned empty output")

    def test_running_missing_not_latest_and_pin_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "not an installed"):
            cleanup.evaluate_inventory("7.0.14-31-pve", PACKAGES, BOOT)
        with self.assertRaisesRegex(ValueError, "not the newest"):
            cleanup.evaluate_inventory("7.0.14-28-pve", PACKAGES, BOOT)
        with self.assertRaisesRegex(ValueError, "selected kernel is not installed"):
            cleanup.evaluate_inventory("7.0.14-30-pve", PACKAGES, BOOT.replace("7.0.14-28-pve", "7.0.99-1-pve"))

    def test_simulations_require_exact_purge_set_and_no_replacement(self):
        targets = ["old-a", "old-b"]
        self.assertTrue(cleanup.validate_simulations(targets, 0, "dpkg simulation", 0, "Purg old-a [1]\nRemv old-b [1]")["valid"])
        self.assertFalse(cleanup.validate_simulations(targets, 1, "dependency problems", 0, "Purg old-a\nPurg old-b")["valid"])
        self.assertFalse(cleanup.validate_simulations(targets, 0, "ok", 0, "Purg old-a\nInst unsigned [1]\nConf unsigned (1)")["valid"])
        self.assertFalse(cleanup.validate_simulations(targets, 0, "ok", 0, "Purg other\nPurg old-b")["valid"])
        self.assertFalse(cleanup.validate_simulations(targets, 0, "ok", 0, "")["valid"])


if __name__ == "__main__":
    unittest.main()
