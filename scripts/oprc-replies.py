#!/usr/bin/env python3
"""Read both coordinator inboxes and retrieve replies to known pending OPREQ IDs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'roles/operator_request_channel/files'))
from oprc import ids  # noqa: E402


def run(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=60).stdout


def replies(client, pending):
    cursor, seen, found = None, set(), []
    while True:
        page = json.loads(run([client, 'list'] + ([cursor] if cursor else [])))
        if page['excluded_count'] != 0:
            raise ValueError('outbound list excludes entries')
        for item in page['items']:
            if item.get('in_reply_to') in pending:
                reply_id = item['request_id']
                if not ids.is_valid_request_id(reply_id):
                    raise ValueError('invalid reply ID')
                value = json.loads(run([client, 'get', reply_id]))
                message = value['message']
                if message['request_id'] != reply_id or message['in_reply_to'] != item['in_reply_to']:
                    raise ValueError('reply relationship mismatch')
                found.append(value)
        cursor = page['next_cursor']
        if cursor is None:
            return found
        if not ids.is_valid_request_id(cursor) or cursor in seen:
            raise ValueError('invalid or repeated cursor')
        seen.add(cursor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request_ids', nargs='*', help='Pending OPREQ IDs from status or case record')
    args = parser.parse_args()
    if any(not ids.is_valid_request_id(key) for key in args.request_ids):
        parser.error('invalid OPREQ ID')
    scripts = Path(os.environ.get('AGMSG_SCRIPTS_DIR', str(Path.home() / '.agents/skills/agmsg/scripts')))
    failed = False
    for team in ('homelab', 'homelab-ops'):
        try:
            print(team + ':\n' + run([str(scripts / 'inbox.sh'), team, 'coordinator']), flush=True)
        except (OSError, subprocess.SubprocessError):
            print(team + ': inbox unavailable', file=sys.stderr)
            failed = True
    if args.request_ids:
        try:
            values = replies(os.environ.get('OPRC_CLIENT', 'operator-channel-client'), set(args.request_ids))
            for value in values:
                print(json.dumps(value, ensure_ascii=False))
            answered = {value['message']['in_reply_to'] for value in values}
            for key in sorted(set(args.request_ids) - answered):
                print(key + ': 一覧に対応回答なし（未回答の断定ではない）')
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            print('OPRES reconciliation incomplete; do not report unanswered', file=sys.stderr)
            failed = True
    return 2 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
