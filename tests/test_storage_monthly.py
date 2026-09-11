"""Offline fixtures only: no production hosts, storage commands or HTTP."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import itertools
import locale
import os
import yaml
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'roles/proxmox_storage_monthly'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


logic = load('ansible.module_utils.storage_monthly', ROOT / 'module_utils/storage_monthly.py')
files = load('ansible.module_utils.storage_files', ROOT / 'module_utils/storage_files.py')
archive = load('storage_archive', ROOT / 'library/storage_archive.py')
notion = load('storage_notion', ROOT / 'library/storage_notion.py')


def observation(count=239, serial='fixture-serial'):
    return {'schema_version': 1, 'zpool': {'rc': 0, 'stdout': '''  pool: fixturepool
 state: ONLINE
  scan: scrub repaired 0B in 00:01:00 with 0 errors on Sun Sep 13 00:25:00 2026
config:

        NAME                STATE     READ WRITE CKSUM
        fixturepool         ONLINE       0     0     0
          /dev/nvme0n1p3    ONLINE       0     0     0

errors: No known data errors
'''}, 'devices': [{'vdev': '/dev/nvme0n1p3', 'namespace': '/dev/nvme0n1',
                     'identity': {'rc': 0, 'json': {'sn': serial, 'mn': 'fixture-model'}},
                     'health': {'rc': 0, 'json': {'critical_warning': 0, 'temperature': 323,
                       'avail_spare': 100, 'spare_thresh': 10, 'percent_used': 1,
                       'media_errors': 0, 'num_err_log_entries': count}}}]}


def report(count=239, baseline=None, **kwargs):
    return logic.build_report({'fixture-node': observation(count)}, 'fixture-report',
                              '2026-09-15T08:00:00+09:00', baseline, **kwargs)


class FakeClient:
    def __init__(self):
        self.posts, self.patches, self.pages = 0, [], {}
        self.lose_create = False

    def call(self, method, path, body=None):
        if method == 'POST':
            self.posts += 1
            rows = copy.deepcopy(body['children'])
            for i, block in enumerate(rows):
                block['id'] = 'block-' + str(i)
            self.pages['page'] = rows
            if self.lose_create:
                raise notion.PublishError('response_unknown')
            return {'id': 'page'}
        self.patches.append((path, body))
        return {}

    def children(self, page):
        if page == 'parent':
            return [{'id': 'page', 'child_page': {'title': 'ストレージ月次点検 2026-09'}}] if self.pages else []
        return self.pages[page]


class ReportTests(unittest.TestCase):
    def test_scan_timestamp_ignores_process_locale(self):
        previous = locale.setlocale(locale.LC_TIME)
        try:
            for setting in ('C', 'ja_JP.UTF-8'):
                locale.setlocale(locale.LC_TIME, setting)
                stamp = logic.scan_timestamp('Sun Aug  9 00:25:00 2026')
                self.assertEqual(stamp.isoformat(), '2026-08-09T00:25:00+09:00')
                self.assertEqual(locale.setlocale(locale.LC_TIME), setting)
            with self.assertRaises(ValueError):
                logic.scan_timestamp('Sun Xxx 09 00:25:00 2026')
            with self.assertRaises(ValueError):
                logic.scan_timestamp('Sun Feb 31 00:25:00 2026')
        finally:
            locale.setlocale(locale.LC_TIME, previous)

    def test_actual_report_suppression_expression(self):
        tasks = yaml.safe_load((ROOT / 'tasks/report.yml').read_text())
        block = next(t['block'] for t in tasks if t.get('name') == 'Save or preview formal report')
        expression = next(t['storage_notion']['suppress'] for t in block if 'storage_notion' in t)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'expression.json'
            for agent, check in itertools.product((False, True), repeat=2):
                cases = [{'skip': skip, 'force': force, 'slack': slack,
                          'expected': check or skip or (agent and not force)}
                         for skip, force, slack in itertools.product((False, True), repeat=3)]
                play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                         'tasks': [{'name': 'Evaluate production suppression expression',
                                    'ansible.builtin.assert': {'that': ['actual == item.expected']},
                                    'vars': {'actual': expression, 'skip_notifications': '{{ item.skip }}',
                                             'proxmox_storage_monthly_notion_force_send': '{{ item.force }}',
                                             'slack_force_send': '{{ item.slack }}'}, 'loop': cases}]}]
                path.write_text(json.dumps(play))
                command = ['ansible-playbook', str(path), '-i', 'localhost,'] + (['--check'] if check else [])
                result = subprocess.run(command, capture_output=True, text=True, timeout=60,
                                        env={**os.environ, 'CLAUDECODE': 'fixture' if agent else ''})
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_prune_boundaries_and_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = []
            for index, (month, kind) in enumerate([
                    ('2025-07', 'delete'), ('2025-08', 'boundary'), ('2025-09', 'recent'),
                    ('2025-07', 'baseline'), ('2025-07', 'unpublished'),
                    ('2025-07', 'symlink'), ('2025-07', 'directory')]):
                key = '20250701T000000000000+0900-' + format(index, '032x')
                history.append({'month': month, 'report_id': key})
                files.save_json(root / (key + '.json'), history[-1])
                (root / (key + '.md')).write_text(kind)
                if kind != 'unpublished':
                    files.save_json(root / (key + '.published.json'), {'report_id': key})
                if kind == 'baseline':
                    files.save_json(root / '2026-09.baseline.json', {'hosts': {'fixture': {'devices': [
                        {'comparison_source': {'report_id': key}}]}}})
                if kind in ('symlink', 'directory'):
                    (root / (key + '.md')).unlink()
                    if kind == 'symlink':
                        (root / 'outside.txt').write_text('preserve')
                        (root / (key + '.md')).symlink_to(root / 'outside.txt')
                    else:
                        (root / (key + '.md')).mkdir()
            archive.prune(root, history, '2026-09')
            for index, entry in enumerate(history):
                self.assertEqual((root / (entry['report_id'] + '.json')).exists(), index != 0)
            self.assertEqual((root / 'outside.txt').read_text(), 'preserve')

    def test_token_file_defenses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fake-token'
            path.write_text('fixture-not-a-real-token')
            path.chmod(0o644)
            with self.assertRaisesRegex(notion.PublishError, '^token_permissions$'):
                notion.Client(str(path))
            path.chmod(0o600)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                notion.Client(str(link))
            path.write_text('')
            with self.assertRaisesRegex(notion.PublishError, '^token_empty$'):
                notion.Client(str(path))

    def test_ansible_controller_collect_check_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = observation()
            raw['zpool']['stdout'] = raw['zpool']['stdout'].replace('Sun Sep 13 00:25:00 2026', 'Sun Aug 09 00:25:00 2026')
            inventory = {'all': {'hosts': {'localhost': {'ansible_connection': 'local'}}, 'children': {'proxmox': {'hosts': {
                'storage-fixture': {'ansible_connection': 'local', 'storage_monthly_observation': raw}}}},
                'vars': {'reports_base_dir': str(root / 'reports')}}}
            inventory_path = root / 'inventory.json'
            inventory_path.write_text(json.dumps(inventory))
            command = ['ansible-playbook', 'playbooks/proxmox_storage_monthly.yml',
                       '-i', str(inventory_path), '--limit', 'localhost',
                       '-e', '{"skip_notifications":true}']
            result = subprocess.run(command + ['--check'], cwd=ROOT.parents[1], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((root / 'reports').exists())
            result = subprocess.run(command, cwd=ROOT.parents[1], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reports = [p for p in (root / 'reports/proxmox-storage-monthly').glob('*.json') if files.REPORT_ID.fullmatch(p.stem)]
            self.assertEqual(len(reports), 1)
            result = subprocess.run(command + ['-e', json.dumps({
                'proxmox_storage_monthly_operation': 'replay',
                'proxmox_storage_monthly_report_id': reports[0].stem})],
                cwd=ROOT.parents[1], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('レポート公開=suppressed', result.stdout)

    def test_archive_freezes_same_month_baseline(self):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 9, 15, 8, 0, tzinfo=tz)
        with tempfile.TemporaryDirectory() as directory, patch.object(archive, 'datetime', Clock):
            first, _ = archive.archive(directory, {'fixture-node': observation(239)}, {})
            second, _ = archive.archive(directory, {'fixture-node': observation(240)}, {})
            third, _ = archive.archive(directory, {'fixture-node': observation(240)}, {})
            for value in (second, third):
                device = value['hosts']['fixture-node']['devices'][0]
                self.assertEqual(device['delta']['num_err_log_entries'], 1)
                self.assertEqual(device['comparison_source']['report_id'], first['report_id'])

    def test_notion_module_suppresses_before_io(self):
        class Done(Exception):
            pass
        class Module:
            def __init__(self, check, suppress):
                self.check_mode = check
                self.params = {'suppress': suppress}
            def exit_json(self, **result):
                self.result = result
                raise Done()
        for check, suppress in ((True, False), (True, True), (False, True)):
            module = Module(check, suppress)
            with patch.object(notion, 'AnsibleModule', return_value=module), \
                 patch.object(notion, 'Client') as client, patch.object(notion, 'locked') as lock:
                with self.assertRaises(Done):
                    notion.main()
                client.assert_not_called()
                lock.assert_not_called()
                self.assertEqual(module.result['publication'], 'suppressed')

    def test_baseline_and_delta(self):
        baseline = report()
        self.assertEqual(baseline['health'], 'OK')
        self.assertEqual(report(239, baseline)['hosts']['fixture-node']['devices'][0]['delta']['num_err_log_entries'], 0)
        self.assertEqual(report(240, baseline)['health'], 'WARNING')
        self.assertEqual(report(10, baseline)['hosts']['fixture-node']['devices'][0]['comparison'], 'reset_suspected')

    def test_human_readable_normal_report(self):
        result = report()
        body = logic.markdown(result)
        self.assertIn('異常は見つかりませんでした', body)
        self.assertIn('初回点検のため前回比較はありません', body)
        self.assertIn('最終scrub: 2026-09-13 00:25 JST（2日前）', body)
        self.assertIn('温度: 49.85 °C', body)
        self.assertIn('エラーログ累積: 239件', body)
        self.assertIn('初回基準値として記録', body)
        self.assertNotIn('"values": {', body)

    def test_human_readable_warning_report_and_summary(self):
        baseline = report()
        result = report(240, baseline)
        body = logic.markdown(result)
        summary = logic.short_summary(result)
        self.assertIn('確認が必要です（要確認）', summary)
        self.assertIn('NVMe error-logの累積数が増加しました', summary)
        self.assertIn('error-log +1', body)
        self.assertIn('fixture-node', body)

    def test_human_summary_prioritizes_unknown_and_critical(self):
        result = report()
        result['health'] = 'UNKNOWN'
        result['issues'] = [
            ['WARNING', 'warning one'],
            ['WARNING', 'warning two'],
            ['WARNING', 'warning three'],
            ['CRITICAL', 'ZFS data errors reported'],
            ['UNKNOWN', 'history corrupt; comparison unavailable'],
        ]
        summary = logic.short_summary(result)
        body = logic.markdown(result)
        self.assertIn('判定不能：保存履歴が壊れているため前回比較できません', summary)
        self.assertIn('異常：ZFSがデータエラーを報告しています', summary)
        self.assertNotIn('warning three', summary)
        self.assertLess(body.index('[判定不能]'), body.index('[異常]'))
        self.assertLess(body.index('[異常]'), body.index('[要確認]'))

    def test_missing_and_corruption(self):
        result = logic.build_report({'fixture-node': {}}, 'x', '2026-09-15T08:00:00+09:00')
        self.assertEqual(result['collection'], 'error')
        self.assertEqual(report(history_error=True)['health'], 'UNKNOWN')

    def test_future_scrub_rejected(self):
        result = logic.build_report({'fixture-node': observation()}, 'x', '2026-09-10T08:00:00+09:00')
        self.assertEqual(result['collection'], 'error')

    def test_bad_counter_not_zero(self):
        raw = observation()
        raw['devices'][0]['health']['json']['media_errors'] = False
        result = logic.build_report({'fixture-node': raw}, 'x', '2026-09-15T08:00:00+09:00')
        self.assertEqual(result['collection'], 'error')

    def test_publish_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            notion.publish(Path(directory), report(), 'parent', client)
            notion.publish(Path(directory), report(240), 'parent', client)
            self.assertEqual(client.posts, 1)

    def test_unknown_creation_reconciles_without_post(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            client.lose_create = True
            with self.assertRaises(notion.PublishError):
                notion.publish(Path(directory), report(), 'parent', client)
            notion.publish(Path(directory), report(), 'parent', client)
            self.assertEqual(client.posts, 1)

    def test_unknown_no_match_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            files.save_json(Path(directory) / '2026-09.publication.json', {'phase': 'creating'})
            client = FakeClient()
            with self.assertRaises(notion.PublishError):
                notion.publish(Path(directory), report(), 'parent', client)
            self.assertEqual(client.posts, 0)

    def test_path_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                files.report_path(Path(directory), '../escape')
            path = Path(directory) / 'link'
            path.symlink_to('/tmp')
            with self.assertRaises(ValueError):
                with files.locked(path):
                    pass


if __name__ == '__main__':
    unittest.main()
