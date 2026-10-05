#!/usr/bin/env python3
"""Offline checks for Operator-specific recovery investigation keys."""

import base64
import os
import pathlib
import stat
import subprocess
import tempfile
import unittest

import jinja2


ROLE_DIR = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROLE_DIR / "templates"

RECOVERY_KEY = "/home/recovery-exec/.ssh/id_recovery_investigate"
RECOVERY_PVE_KEY = "/home/recovery-exec/.ssh/id_recovery_investigate_pve"
RECOVERY_KNOWN = "/home/recovery-exec/.ssh/known_hosts"
OPERATOR_KEY = "/home/yoshi/.ssh/id_operator_investigate"
OPERATOR_PVE_KEY = "/home/yoshi/.ssh/id_operator_investigate_pve"
OPERATOR_KNOWN = "/home/yoshi/.ssh/known_hosts"


def _template_environment():
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))
    environment.filters["b64decode"] = lambda value: base64.b64decode(value).decode("utf-8")
    environment.globals["lookup"] = lambda kind, name: "ssh-ed25519 CLAUDE-KEY"
    return environment


def _render_wrapper(template_name):
    return _template_environment().get_template(template_name).render(
        target={
            "name": "fixture",
            "host": "fixture.internal",
            "investigate_services": [],
            "investigate_extra": [],
        },
        recovery_exec_investigate_key=RECOVERY_KEY,
        recovery_exec_investigate_pve_key=RECOVERY_PVE_KEY,
        recovery_exec_ssh_dir="/home/recovery-exec/.ssh",
        recovery_exec_operator_user="yoshi",
        recovery_exec_operator_investigate_key=OPERATOR_KEY,
        recovery_exec_operator_investigate_pve_key=OPERATOR_PVE_KEY,
        recovery_exec_operator_ssh_dir="/home/yoshi/.ssh",
    )


class OperatorInvestigateKeyTests(unittest.TestCase):
    def _run_wrapper(self, template_name, caller, arguments):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            script = root / "wrapper"
            script.write_text(
                _render_wrapper(template_name).replace("/usr/bin/id -un", "id -un"), encoding="utf-8"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            (fake_bin / "id").write_text("#!/bin/sh\nprintf '%s\\n' \"$TEST_CALLER\"\n", encoding="utf-8")
            (fake_bin / "ssh").write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
            for path in fake_bin.iterdir():
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
            environment = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}", "TEST_CALLER": caller}
            return subprocess.run([str(script), *arguments], capture_output=True, text=True, env=environment, check=False)

    def _assert_ssh_identity(self, template_name, caller, arguments, expected_key, expected_known):
        result = self._run_wrapper(template_name, caller, arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = result.stdout.splitlines()
        self.assertEqual(argv[argv.index("-i") + 1], expected_key)
        self.assertIn(f"UserKnownHostsFile={expected_known}", argv)
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertNotIn(RECOVERY_KEY, argv if caller == "yoshi" else [])
        self.assertNotIn(RECOVERY_PVE_KEY, argv if caller == "yoshi" else [])

    def test_normal_wrapper_selects_identity_specific_key_and_known_hosts(self):
        self._assert_ssh_identity("homelab-investigate.sh.j2", "recovery-exec", ["status"], RECOVERY_KEY, RECOVERY_KNOWN)
        self._assert_ssh_identity("homelab-investigate.sh.j2", "yoshi", ["status"], OPERATOR_KEY, OPERATOR_KNOWN)

    def test_pve_wrapper_selects_identity_specific_key_and_known_hosts(self):
        self._assert_ssh_identity("homelab-investigate-pve.sh.j2", "recovery-exec", ["cluster-status"], RECOVERY_PVE_KEY, RECOVERY_KNOWN)
        self._assert_ssh_identity("homelab-investigate-pve.sh.j2", "yoshi", ["cluster-status"], OPERATOR_PVE_KEY, OPERATOR_KNOWN)

    def test_wrappers_do_not_accept_key_or_known_hosts_arguments(self):
        for template_name, check in (("homelab-investigate.sh.j2", "status"), ("homelab-investigate-pve.sh.j2", "cluster-status")):
            with self.subTest(template=template_name):
                result = self._run_wrapper(template_name, "yoshi", [check, OPERATOR_KEY])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("denied:", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_authorized_keys_add_only_operator_read_only_entries(self):
        context = {
            "_investigate_pubkey": {"content": base64.b64encode(b"ssh-ed25519 RECOVERY-INVESTIGATE").decode()},
            "_action_pubkey": {"content": base64.b64encode(b"ssh-ed25519 RECOVERY-ACTION").decode()},
            "_investigate_pve_pubkey": {"content": base64.b64encode(b"ssh-ed25519 RECOVERY-PVE").decode()},
            "_operator_investigate_pubkey": {"content": base64.b64encode(b"ssh-ed25519 OPERATOR-INVESTIGATE").decode()},
            "_operator_investigate_pve_pubkey": {"content": base64.b64encode(b"ssh-ed25519 OPERATOR-PVE").decode()},
        }
        environment = _template_environment()
        normal = environment.get_template("authorized_keys.j2").render(**context).splitlines()
        pve = environment.get_template("authorized_keys-pve.j2").render(**context).splitlines()
        restriction = "no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty"
        self.assertEqual(len(normal), 4)
        self.assertEqual(len(pve), 3)
        self.assertEqual(normal[0], f'command="/usr/local/sbin/recovery-investigate-dispatch.sh",{restriction} ssh-ed25519 RECOVERY-INVESTIGATE')
        self.assertEqual(normal[1], f'command="/usr/local/sbin/recovery-action.sh",{restriction} ssh-ed25519 RECOVERY-ACTION')
        self.assertEqual(normal[2], f'command="/usr/local/sbin/recovery-investigate-dispatch.sh",{restriction} ssh-ed25519 CLAUDE-KEY')
        self.assertEqual(normal[3], f'command="/usr/local/sbin/recovery-investigate-dispatch.sh",{restriction} ssh-ed25519 OPERATOR-INVESTIGATE')
        self.assertEqual(pve[0], f'command="/usr/local/sbin/recovery-investigate-dispatch-pve.sh",{restriction} ssh-ed25519 RECOVERY-PVE')
        self.assertEqual(pve[1], f'command="/usr/local/sbin/recovery-investigate-dispatch-pve.sh",{restriction} ssh-ed25519 CLAUDE-KEY')
        self.assertEqual(pve[2], f'command="/usr/local/sbin/recovery-investigate-dispatch-pve.sh",{restriction} ssh-ed25519 OPERATOR-PVE')

    def test_operator_key_tasks_are_check_mode_gated_and_owned_by_yoshi(self):
        tasks = (ROLE_DIR / "tasks" / "main.yml").read_text(encoding="utf-8")
        target_tasks = (ROLE_DIR / "tasks" / "target_setup.yml").read_text(encoding="utf-8")
        self.assertIn("Generate and lock down Operator SSH keys", tasks)
        self.assertIn("inventory_hostname == 'quory'", tasks)
        self.assertIn('mode: "0600"', tasks)
        self.assertIn('owner: "{{ recovery_exec_operator_user }}"', tasks)
        self.assertIn("Slurp Operator investigate public key", target_tasks)
        self.assertIn("Slurp Operator PVE investigate public key", target_tasks)
        self.assertIn("Add target host keys to Operator known_hosts", target_tasks)
        self.assertIn("Add pve target host keys to Operator known_hosts", target_tasks)
        self.assertIn("Set Operator known_hosts ownership", target_tasks)

    def test_key_generation_is_idempotent_and_private_key_mode_is_0600(self):
        with tempfile.TemporaryDirectory() as directory:
            key_path = pathlib.Path(directory) / "id_operator_investigate"
            command = ["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "operator-investigate-fixture", "-f", str(key_path)]
            if not key_path.exists():
                subprocess.run(command, check=True, capture_output=True, text=True)
            first = key_path.read_bytes()
            if not key_path.exists():
                subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(key_path.read_bytes(), first)
            self.assertEqual(stat.S_IMODE(key_path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
