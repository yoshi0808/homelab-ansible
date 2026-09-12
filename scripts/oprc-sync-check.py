#!/usr/bin/env python3
"""Classify remote.sh status without equating invisible processes with stopped ones."""
import datetime
import os
import re
import sys


def check(text, max_age, now):
    if 'engine stopped' in text or 'engine not running' in text:
        return 2, 'sync_stopped: 通常シェルでengineの起動状態を確認してください。'
    if 'engine running' not in text:
        return 4, ('sync_unobservable: この実行環境ではengineの稼働を確認できません。'
                   '停止とは断定しません。同じremote.sh status homelab-opsを正規の'
                   'sandbox外実行で確認し、稼働・直近同期を確認できたら同じ送信wrapperを再実行してください。')
    match = re.search(r'last successful sync ([0-9T:.\-]+Z)', text)
    if not match:
        return 4, 'sync_unobservable: 同期成功時刻を確認できません。登録していません。'
    try:
        last = datetime.datetime.fromisoformat(match[1].replace('Z', '+00:00'))
        age = (now - last).total_seconds()
    except ValueError:
        return 4, 'sync_unobservable: 同期成功時刻を解釈できません。'
    if age < 0:
        return 4, 'sync_unobservable: 同期時刻が未来です。時計を確認してください。'
    if age > max_age:
        return 2, 'sync_old: 同期成功が古いため登録していません。同期状態を確認してください。'
    return 0, ''


if __name__ == '__main__':
    try:
        limit = int(os.environ.get('SYNC_MAX_AGE_SECONDS', '1800'))
        if limit <= 0:
            raise ValueError()
        code, message = check(sys.stdin.read(), limit, datetime.datetime.now(datetime.timezone.utc))
    except ValueError:
        code, message = 2, 'invalid SYNC_MAX_AGE_SECONDS'
    if message:
        print(message, file=sys.stderr)
    sys.exit(code)
