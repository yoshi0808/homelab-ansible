#!/usr/bin/env python3
"""Run production cleanup, report, notification, and re-raise tasks locally.

Every package-manager path points at a /tmp double. Only timeout, Python,
Ansible command/async_status, and local report writes execute for real.
"""
import argparse
import copy
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from extract_production_notify import ROLE, final_tasks

REPO = ROLE.parents[1]
PACKAGES = ''.join('ii \tproxmox-kernel-' + version + '-pve-signed\t1\n' for version in
                   ['6.17.13-21', '7.0.14-28', '7.0.14-30', '6.17.2-1', '7.0.2-6'])
PACKAGES += ''.join('ii \t' + name + '\t1\n' for name in
                    ['proxmox-kernel-6.17', 'proxmox-kernel-7.0', 'proxmox-default-kernel', 'proxmox-ve'])
TARGETS = ['proxmox-kernel-6.17.2-1-pve-signed', 'proxmox-kernel-7.0.2-6-pve-signed']


def run_case(mode, check=False, mutate=False):
    with tempfile.TemporaryDirectory(prefix='kernel-cleanup-flow-') as directory:
        root = Path(directory)
        (root / 'disconnect').write_text(mode)
        (root / 'scenario.json').write_text(json.dumps({'mode': mode}))
        packages = PACKAGES
        if mode == 'no_targets':
            packages = '\n'.join(line for line in packages.splitlines() if line.split('\t')[1] not in TARGETS) + '\n'
        if mode == 'version_format':
            packages += 'ii \tproxmox-kernel-7.0.14-rc1-pve-signed\t1\n'
        (root / 'packages').write_text(packages)
        (root / 'stub.py').write_text((ROLE / 'tests/kernel_cleanup_stub.py').read_text())
        (root / 'stub.py').chmod(0o755)
        for name in ['collect', 'dpkg', 'apt-get']:
            (root / name).symlink_to(root / 'stub.py')
        values = yaml.safe_load((ROLE / 'defaults/main.yml').read_text())
        values.update({
            'proxmox_patch_apply_kernel_cleanup_timeout': 1 if mode == 'simulation_timeout' else 5,
            'proxmox_patch_apply_kernel_cleanup_purge_timeout': 1 if mode == 'purge_timeout' else 10,
            'proxmox_patch_apply_kernel_cleanup_collector_path': str(root / 'collect'),
            'proxmox_patch_apply_kernel_cleanup_evaluator_path': str(ROLE / 'files/proxmox-kernel-cleanup-evaluate.py'),
            'proxmox_patch_apply_kernel_cleanup_dpkg_path': str(root / 'dpkg'),
            'proxmox_patch_apply_kernel_cleanup_apt_path': str(root / 'apt-get'),
            'proxmox_patch_apply_report_dir': str(root),
            'ansible_async_dir': str(root / 'async'),
            'skip_notifications': True,
            '_apply_run_ts': '2026-11-28T12:00:00+09:00',
            '_apply_report_filename': 'report.json',
            '_apply_failed': mode in {'apply_failed', 'failed_only'},
            '_apply_abort_type': 'apply_failed' if mode in {'apply_failed', 'abort_only'} else 'none',
            '_apply_error_msg': 'fixture failure', '_apply_failed_task': 'Original apply task',
            '_apply_reboot_done': mode != 'no_reboot',
            '_post_hc_status': 'UNKNOWN' if mode in {'apply_failed', 'abort_only', 'failed_only'} else ('CRITICAL' if mode == 'critical' else 'OK'),
            '_pre_hc_status': 'OK', '_predryrun': {}, '_sim_updates': [], '_sim_removes': [],
            '_download_bytes': 0, '_download_seconds': 0, '_download_cache_hit': False,
            '_download_stderr': '', '_download_log_path': 'download.log',
            '_mirror_selected_address': '', '_mirror_selected_rtt_ms': '',
            '_nas_cache_available': False, '_nas_cache_warnings': [], '_apply_seconds': 0,
            '_apply_log_path': 'apply.log', '_apply_stdout': '', '_apply_collect': {},
            '_apply_package_notes': [], '_new_vs_dryrun': [], '_unchanged_vs_dryrun': [],
        })
        # Main's production include and final tasks are read every time. No
        # result object, notification expression, or re-raise is reimplemented.
        main = yaml.safe_load((ROLE / 'tasks/main.yml').read_text())
        always = next(task['always'] for task in main if 'always' in task)
        cleanup = copy.deepcopy(next(task for task in always if task.get('name') ==
                                     'Clean old kernels after a successful reboot and healthcheck'))
        cleanup['ansible.builtin.include_tasks'] = str(ROLE / 'tasks/kernel_cleanup.yml')
        tasks = [cleanup] + final_tasks(report=True)
        if mutate:
            notify = next(task['ansible.builtin.set_fact'] for task in tasks if task.get('name') == 'Set notification subject and body')
            status = notify['_notify_status']
            match = re.fullmatch(r"\{%\- if (.*?) \-%\}\s*error\s*\{%\- elif (.*?) \-%\}\s*warning\s*(\{%\- else .*?)", status, re.S)
            assert match, status
            notify['_notify_status'] = ("{%- if " + match[2] + " -%} warning {%- elif " +
                                        match[1] + " -%} error " + match[3])
        tasks.append({'ansible.builtin.copy': {'dest': str(root / 'output.json'),
                      'content': "{{ {'cleanup': _apply_kernel_cleanup, 'failed': _apply_failed, "
                                 "'abort': _apply_abort_type, 'failed_task': _apply_failed_task, "
                                 "'subject': _notify_subject, 'status': _notify_status, "
                                 "'channel': _notify_channel, 'body': _notify_body, "
                                 "'job_id': _kernel_cleanup_job.ansible_job_id | default('')} | to_json }}"}, 'check_mode': False})
        tasks.append(copy.deepcopy(next(task for task in always if task.get('name') == 'Re-raise failure to mark play as failed')))
        play = [{'hosts': 'localhost', 'connection': 'kernel_cleanup_local' if mode.endswith('_disconnect') else 'local', 'gather_facts': False, 'vars': values, 'tasks': tasks}]
        play_path = root / 'driver.yml'
        play_path.write_text(yaml.safe_dump(play, allow_unicode=True, sort_keys=False))
        command = ['ansible-playbook', '-i', 'localhost,', str(play_path)]
        if check:
            command.append('--check')
        result = subprocess.run(command, cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env={**os.environ, 'ANSIBLE_NOCOLOR': '1',
                                     'ANSIBLE_CONNECTION_PLUGINS': str(ROLE / 'tests/connection_plugins'),
                                     'KERNEL_CLEANUP_TEST_STATE': str(root)}, timeout=90)
        if not (root / 'output.json').exists():
            raise AssertionError(result.stdout)
        data = json.loads((root / 'output.json').read_text())
        data['report'] = json.loads((root / 'report.json').read_text())
        data['calls'] = (root / 'calls').read_text() if (root / 'calls').exists() else ''
        data['returncode'] = result.returncode
        data['remaining'] = (root / 'packages').read_text()
        if result.returncode not in {0, 2}:
            raise AssertionError(result.stdout)
        # Completed async jobs must have been cleaned by the production task.
        if mode.endswith('_disconnect'):
            assert (root / 'disconnected').exists(), result.stdout
            assert (root / 'completed').exists(), result.stdout
        else:
            assert not list((root / 'async').glob('*')), result.stdout
        return data


class KernelCleanupFlowTest(unittest.TestCase):
    def verify_case(self, mode, expected, check=False, mutate=False):
        data = run_case(mode, check=check, mutate=mutate)
        cleanup = data['cleanup']
        self.assertEqual(cleanup['status'], expected, data)
        broken = expected == 'broken'
        failed = broken or mode in {'apply_failed', 'failed_only'}
        error = failed or mode == 'abort_only'
        self.assertIs(data['failed'], failed)
        self.assertEqual(data['returncode'], 2 if failed else 0)
        self.assertEqual(data['report']['result'], 'FAILED' if failed else 'SUCCESS')
        self.assertEqual(data['report']['kernel_cleanup'], cleanup)
        self.assertEqual(data['status'], 'error' if error else 'warning' if expected == 'aborted' or mode == 'critical' else 'ok')
        self.assertEqual(data['channel'], 'alerts' if error or expected == 'aborted' or mode == 'critical' else 'patches')
        self.assertTrue(data['subject'].startswith('[FAILED]' if error else '[WARNING]' if expected == 'aborted' or mode == 'critical' else '[SUCCESS]'))
        self.assertIn('Phase 6: old kernel cleanup', data['body'])
        self.assertIn('kernel cleanup: ' + expected, data['body'])
        self.assertIsInstance(cleanup['reason'], str)
        self.assertEqual(cleanup['reason'], cleanup['reason'].strip())
        self.assertNotIn('packages', cleanup)
        self.assertNotIn('boot_tool_output', cleanup)
        if cleanup['purge_started']:
            self.assertIsInstance(cleanup['async_job_id'], str)
            self.assertEqual(cleanup['async_job_id'], data['job_id'])
            if mode == 'launch_disconnect':
                self.assertEqual(cleanup['async_job_id'], '')
            else:
                self.assertTrue(cleanup['async_job_id'])
        pending_warning = 'host側のpurgeが継続している可能性があります'
        if mode.endswith('_disconnect'):
            self.assertIn(pending_warning, cleanup['reason'])
            self.assertIn(pending_warning, data['body'])
        else:
            self.assertNotIn(pending_warning, cleanup['reason'])
        if broken:
            self.assertEqual(data['abort'], 'kernel_cleanup_broken')
            self.assertIn('kernel削除後の検証または削除処理に失敗', data['subject'])
            self.assertIn('失敗task: ' + data['failed_task'], data['body'])
            if mode in {'purge_rc', 'partial', 'purge_timeout'}:
                self.assertEqual(data['failed_task'], 'Require successful completion of old-kernel purge')
                self.assertIn('TAIL', cleanup['purge_output'])
                self.assertLessEqual(len(cleanup['purge_output']), 3000)
            if mode in {'purge_rc', 'partial'}:
                self.assertIn('x\nPURGE FAILURE TAIL', cleanup['purge_output'])
                self.assertNotIn(r'x\nPURGE FAILURE TAIL', cleanup['purge_output'])
        if expected == 'removed':
            self.assertEqual(cleanup['removed'], TARGETS)
            self.assertIn('削除件数: 2', data['body'])
            self.assertIn('削除範囲: 6.17.2-1-pve ～ 7.0.2-6-pve', data['body'])
            self.assertIn('残したkernel: 6.17.13-21-pve, 7.0.14-28-pve, 7.0.14-30-pve', data['body'])
        else:
            self.assertIn('理由: ' + cleanup['reason'], data['body'])
        if expected in {'aborted', 'skipped'}:
            self.assertFalse(cleanup['purge_started'])
            self.assertNotIn('dpkg --purge', data['calls'])
            self.assertNotIn('dpkg --audit', data['calls'])
        if mode in {'partial', 'purge_timeout'}:
            self.assertEqual(cleanup['removed'], TARGETS[:1])
            self.assertTrue(cleanup['removal_observed'])
        if check or mode in {'no_reboot', 'critical', 'apply_failed', 'abort_only', 'failed_only'}:
            self.assertEqual(data['calls'], '')
        if mode == 'bad_json':
            self.assertIn('削除着手前', cleanup['reason'])
        if check:
            self.assertEqual(data['remaining'], PACKAGES)
            self.assertEqual(cleanup['reason'], '--check のため削除しません')
        if mode == 'version_format':
            self.assertIn('unsupported kernel version format', cleanup['reason'])
        return data

    def test_production_branches(self):
        for mode, expected in [
            ('happy', 'removed'), ('purge_rc', 'broken'), ('partial', 'broken'),
            ('purge_timeout', 'broken'), ('launch_disconnect', 'broken'), ('poll_disconnect', 'broken'), ('meta_missing', 'broken'), ('audit', 'broken'),
            ('hook', 'broken'), ('boot_changed', 'broken'), ('post_rc', 'broken'),
            ('collect_rc', 'aborted'), ('bad_json', 'aborted'), ('simulation_rc', 'aborted'),
            ('simulation_timeout', 'aborted'), ('apt_rc', 'aborted'), ('apt_empty', 'aborted'),
            ('inst_conf', 'aborted'), ('version_format', 'aborted'), ('no_targets', 'skipped'),
            ('no_reboot', 'skipped'), ('critical', 'skipped'), ('apply_failed', 'skipped'),
            ('abort_only', 'skipped'), ('failed_only', 'skipped')]:
            with self.subTest(mode=mode):
                self.verify_case(mode, expected)
                print(f'{mode}: {expected} PASS', flush=True)

    def test_reordered_production_status_is_detected(self):
        # Mutate only the loaded production task in /tmp; the repo is untouched.
        with self.assertRaisesRegex(AssertionError, "warning.*error"):
            self.verify_case('apply_failed', 'skipped', mutate=True)

    def test_check_gate(self):
        self.verify_case('happy', 'skipped', check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    suite = unittest.TestSuite([KernelCleanupFlowTest('test_check_gate')]) if args.check_only else unittest.defaultTestLoader.loadTestsFromTestCase(KernelCleanupFlowTest)
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
