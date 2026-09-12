import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = load('oprc-sync-check')
receive = load('oprc-replies')
REQUEST = 'req-20260911T170033+0900-5eadffb4d1a941ed'
REPLY = 'req-20260911T171216+0900-45d070d1570eb0c0'


class Helpers(unittest.TestCase):
    def test_sync_classification(self):
        now = datetime.datetime(2026, 9, 12, tzinfo=datetime.timezone.utc)
        for text, expected in [
            ('engine stale — dead or foreign process', 4), ('unknown output', 4),
            ('engine stopped', 2), ('engine running', 4),
            ('engine running last successful sync 2026-09-11T23:59:59Z', 0),
            ('engine running last successful sync 2026-09-11T00:00:00Z', 2),
            ('engine running last successful sync 2026-09-13T00:00:00Z', 4),
            ('engine running last successful sync 2026-99-99T00:00:00Z', 4),
        ]:
            with self.subTest(text=text):
                self.assertEqual(sync.check(text, 1800, now)[0], expected)

    def test_prepare_then_validate_without_server_fields(self):
        with tempfile.TemporaryDirectory() as work:
            source, output = Path(work) / 'body.json', Path(work) / 'request.json'
            source.write_text(json.dumps({'purpose': 'fixture request'}))
            command = ['python3', str(ROOT / 'scripts/oprc-prepare.py'), str(source)]
            result = subprocess.run(command + ['--output', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(output.read_text())
            self.assertEqual(value, {'purpose': 'fixture request', 'type': 'OPREQ', 'schema_version': 1})
            self.assertEqual(subprocess.run(command + ['--output', str(output)], capture_output=True).returncode, 2)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(subprocess.run(command[:-1] + [str(output)], capture_output=True).returncode, 0)

    def test_invalid_or_secret_request_never_creates_output(self):
        for payload in [[], {'type': 'OPRES', 'purpose': 'x'},
                        {'purpose': 'x', 'source': 'coordinator'},
                        {'purpose': 'x', 'unknown': True},
                        {'purpose': '-----BEGIN PRIVATE KEY-----'}]:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as work:
                source, output = Path(work) / 'body.json', Path(work) / 'out.json'
                source.write_text(json.dumps(payload))
                result = subprocess.run(['python3', str(ROOT / 'scripts/oprc-prepare.py'), str(source),
                                         '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(output.exists())
                self.assertNotIn('BEGIN PRIVATE KEY', result.stdout + result.stderr)
                if payload == {'purpose': '-----BEGIN PRIVATE KEY-----'}:
                    self.assertIn(' at /purpose', result.stderr)

    def test_read_already_submitted_reply_across_pages(self):
        item = {'request_id': REPLY, 'in_reply_to': REQUEST}
        response = {'message': item, 'state': 'submitted'}
        pages = [{'items': [], 'next_cursor': REQUEST, 'excluded_count': 0},
                 {'items': [item], 'next_cursor': None, 'excluded_count': 0}, response]
        with patch.object(receive, 'run', side_effect=[json.dumps(x) for x in pages]) as run:
            self.assertEqual(receive.replies('client', {REQUEST}), [response])
            self.assertEqual(run.call_args_list[-1].args[0], ['client', 'get', REPLY])

    def test_excluded_results_are_not_unanswered(self):
        with patch.object(receive, 'run', return_value=json.dumps({'excluded_count': 1})):
            with self.assertRaises(ValueError):
                receive.replies('client', {REQUEST})

    def test_both_inboxes_checked_even_after_failure(self):
        with patch('sys.argv', ['oprc-replies.py']), patch.object(receive, 'run', side_effect=[
                subprocess.CalledProcessError(1, 'inbox'), 'No new messages.']) as run:
            self.assertEqual(receive.main(), 2)
            self.assertEqual([c.args[0][1] for c in run.call_args_list], ['homelab', 'homelab-ops'])


if __name__ == '__main__':
    unittest.main()
