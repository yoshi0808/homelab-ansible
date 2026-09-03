#!/usr/bin/env bash
# OPREQ の登録と、Operator への agmsg 通知を1操作にする。
#
# **登録は通知ではない。** Operator セッションは自動起動せず、起動するのは
# Yoshinobu である。気づかせるのはメッセージの送り手である Coordinator であり、
# その手段は agmsg しかない。登録と通知を別々のコマンドで行うと、片方だけを
# 実行しても何も咎めず、request は誰にも気づかれないまま滞留する。
# 規範は docs/ai/roles/coordinator.md、経路は
# docs/ai/context/operations/operator-request-channel.md が正本。
#
# **登録は取り消せない**(spool は append-only で削除手段が無い)。したがって
# 事前に判定できるものは、すべて submit より前に落とす。
#
# Usage: scripts/oprc-submit.sh <payload.json> <notice.txt>
#
#   payload.json : operator-channel-client submit へ渡す OPREQ 本文
#   notice.txt   : agmsg で送る要旨。**本文は載せない**(agmsg は DLP を通らない)
#
# 環境変数(試験用):
#   AGMSG_SCRIPTS_DIR   send.sh / team.sh / remote.sh の置き場(既定 ~/.agents/skills/agmsg/scripts)
#   OPRC_CLIENT         client の名前(既定 operator-channel-client、PATH解決)
#   SYNC_MAX_AGE_SECONDS  同期がこの秒数より古ければ登録しない(既定 1800)
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGMSG_SCRIPTS_DIR="${AGMSG_SCRIPTS_DIR:-$HOME/.agents/skills/agmsg/scripts}"
OPRC_CLIENT="${OPRC_CLIENT:-operator-channel-client}"

# 相手先は docs/ai/context/operations/agent-messaging.md §7 の identity。
TEAM="homelab-ops"
FROM="coordinator"
TO="operator"

# request_id の形式契約は roles/operator_request_channel/files/oprc/ids.py が
# 正本である。ここへ正規表現を写さない。
OPRC_LIB="$repo_root/roles/operator_request_channel/files"

die() { echo "oprc-submit: $*" >&2; exit 2; }

payload="${1:-}"
notice="${2:-}"
[ -n "$payload" ] && [ -n "$notice" ] || die "Usage: oprc-submit.sh <payload.json> <notice.txt>"
[ -f "$payload" ] || die "payload が読めない: $payload"
[ -f "$notice" ] || die "要旨ファイルが読めない: $notice"

# --- submit より前に落とすもの -------------------------------------------
# 通知できない状態、および登録後に id を検証できない状態で登録しない。

notice_body="$(cat "$notice")"
[ -n "$(printf '%s' "$notice_body" | tr -d '[:space:]')" ] || \
  die "要旨が空である。通知できない依頼を登録しない"

python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$payload" 2>/dev/null || \
  die "payload が JSON として読めない: $payload"

send_sh="$AGMSG_SCRIPTS_DIR/send.sh"
team_sh="$AGMSG_SCRIPTS_DIR/team.sh"
remote_sh="$AGMSG_SCRIPTS_DIR/remote.sh"
[ -x "$send_sh" ] || die "send.sh が無い: $send_sh (通知経路が無い状態で登録しない)"
[ -x "$team_sh" ] || die "team.sh が無い: $team_sh (通知先を確かめられない状態で登録しない)"
[ -x "$remote_sh" ] || die "remote.sh が無い: $remote_sh (同期の成立を確かめられない状態で登録しない)"

# team と両identityの登録は送信時にしか検査されない。事前に確かめられるので
# 事前に確かめる — ここを通さないと、不可逆な submit のあとで初めて
# 「送れない」が分かる。
roster="$("$team_sh" "$TEAM" 2>/dev/null)" || \
  die "agmsg team '$TEAM' が無い(通知先が無い状態で登録しない)"
for who in "$FROM" "$TO"; do
  printf '%s\n' "$roster" | grep -q "^  ${who}\( \|$\)" || \
    die "agmsg team '$TEAM' に '${who}' が登録されていない(通知できない状態で登録しない)"
done

# **`send.sh` が成功しても、それはローカルstoreへ書いたことしか意味しない。**
# remote team では sync engine がサーバへ運ぶまでが送信であり、engine が死んで
# いると**エラーを出さずに溜まるだけ**になる(2026-08-29から2026-09-02まで実際に
# 5日間止まっており、その間の通知は1通も出ていなかった)。engine の生死と
# 「最後に成功した同期」の両方を見る — 前者だけでは足りないことは
# `docs/ai/context/operations/agent-messaging.md` §9 が定めている。
sync_status="$("$remote_sh" status "$TEAM" 2>/dev/null)" || \
  die "agmsg の同期状態を取得できない(通知が出るか確かめられない状態で登録しない)"
printf '%s\n' "$sync_status" | grep -q 'engine running' || \
  die "agmsg の sync engine が動いていない。通知はローカルへ溜まるだけでサーバへ出ない。通常のシェルから 'remote.sh sync start $TEAM' で起動すること(エージェントのツール実行から起動しない)"
printf '%s\n' "$sync_status" | python3 -c "
import re, sys, datetime
text = sys.stdin.read()
m = re.search(r'last successful sync ([0-9T:.\\-]+Z)', text)
if not m:
    sys.exit(1)
last = datetime.datetime.strptime(m.group(1)[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=datetime.timezone.utc)
age = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds()
sys.exit(0 if age <= ${SYNC_MAX_AGE_SECONDS:-1800} else 2)
" || die "agmsg の同期が最近成功していない(engine は起動しているが運べていない)。通知が相手へ出ない状態で登録しない"

# id の検証に使うライブラリを、登録より前に読めることを確かめる。読めない
# まま登録すると、返ってきた id を検証できず fail-closed にしかできない。
python3 -c "
import sys
sys.path.insert(0, '$OPRC_LIB')
from oprc import ids
ids.is_valid_request_id('x')
" 2>/dev/null || die "oprc.ids を読めない: $OPRC_LIB (id を検証できない状態で登録しない)"

# --- ここから先は本番の spool へ書く。登録は取り消せない。 ---------------
if ! response="$("$OPRC_CLIENT" submit < "$payload")"; then
  echo "oprc-submit: submit に失敗した。登録されていないので通知も送っていない。" >&2
  exit 2
fi

# 応答が object であり、request_id が形式契約に適合する文字列であることまで
# 見る。truthy かどうかで通すと、dict や改行入りの文字列をそのまま id として
# 通知し、登録成功として報告してしまう。
request_id="$(printf '%s' "$response" | python3 -c "
import json, sys
sys.path.insert(0, '$OPRC_LIB')
from oprc import ids
try:
    doc = json.load(sys.stdin)
except Exception:
    print(''); raise SystemExit(0)
if not isinstance(doc, dict):
    print(''); raise SystemExit(0)
value = doc.get('request_id')
# 末尾改行だけは正規表現の \$ を素通りするため、明示的に落とす。
if not ids.is_valid_request_id(value) or value != value.strip():
    print(''); raise SystemExit(0)
print(value)
")"

if [ -z "$request_id" ]; then
  # 登録された可能性があるのに id を読めない・形式が契約に適合しない。
  # 黙って成功にしない。
  echo "oprc-submit: submit の応答から、契約に適合する request_id を読めなかった。" >&2
  echo "  応答: $response" >&2
  echo "  **登録された可能性がある。通知は送っていない。**" >&2
  echo "  operator-channel-client list / status で現物を確かめ、通知を手で送ること。" >&2
  exit 3
fi

body="OPREQ を1件登録しました。

request_id: ${request_id}

${notice_body}

本文は spool の request を show-request で読んでください(この経路は DLP を通らないため要旨と ID だけを載せています)。"

if ! "$send_sh" "$TEAM" "$FROM" "$TO" "$body"; then
  echo "oprc-submit: agmsg 通知の送信に失敗した。" >&2
  echo "  **OPREQ ${request_id} は登録済みであり、取り消せない。通知だけが未送である。**" >&2
  echo "  次を手で実行して通知を成立させること:" >&2
  echo "    $send_sh $TEAM $FROM $TO '<要旨と ${request_id}>'" >&2
  exit 3
fi

echo "登録: ${request_id}"
echo "通知: ${TEAM} ${FROM} -> ${TO} へ送信(sync engine の稼働と直近の同期成功を確認済み)"
