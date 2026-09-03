#!/usr/bin/env bash
# scripts/oprc-submit.sh の回帰テスト。
#
# 見ているのは「登録と通知がセットで成立するか」と「片方だけ起きたときに
# 黙って成功しないか」の2点である。本番の spool は append-only で削除手段が
# 無いため、**試験用の OPREQ を実際に登録しない。** client と agmsg の
# スクリプトをスタブへ差し替えて呼び出しを記録する。
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
target="$repo_root/scripts/oprc-submit.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fail=0
pass=0

# 形式契約(roles/operator_request_channel/files/oprc/ids.py)に適合する値。
VALID_ID='req-20260902T090000+0900-abcdef0123456789'

# --- スタブ ---------------------------------------------------------------
mkdir -p "$work/bin" "$work/agmsg"
cat > "$work/bin/stub-client" <<'EOF'
#!/usr/bin/env bash
cat > /dev/null
echo "submit" >> "$STUB_LOG"
printf '%s' "${SUBMIT_OUT:-}"
exit "${SUBMIT_RC:-0}"
EOF
cat > "$work/agmsg/send.sh" <<'EOF'
#!/usr/bin/env bash
echo "send" >> "$STUB_LOG"
printf '%s\n' "$4" > "$STUB_BODY"
exit "${SEND_RC:-0}"
EOF
# team.sh は実物と同じ体裁を返す(先頭2スペース + 名前)。
cat > "$work/agmsg/team.sh" <<'EOF'
#!/usr/bin/env bash
if [ "${TEAM_RC:-0}" != "0" ]; then
  echo "Team not found: $1"
  exit 1
fi
printf 'Team: %s\n\n%s\n\n2 member(s)\n' "$1" "${ROSTER:-  coordinator (claude-code) — /repo
  operator (remote — no local registration)}"
EOF
# remote.sh は「engine が動いているか」と「最後に成功した同期」の2つを出す。
# SYNC_MODE で ok / stale(engine死亡)/ old(古い同期)/ nosync(同期行なし)を切り替える。
cat > "$work/agmsg/remote.sh" <<'EOF'
#!/usr/bin/env bash
case "${SYNC_MODE:-ok}" in
  stale) echo "$2	connected (engine stale — pidfile 999 points at a dead or foreign process)"; exit 0 ;;
  nosync) echo "$2	connected (engine running, pid 1)"; exit 0 ;;
  old)  echo "$2	connected (engine running, pid 1)"
        echo "		cycles: last successful sync 2026-08-29T00:04:05.810Z"; exit 0 ;;
  fail) exit 1 ;;
  *)    echo "$2	connected (engine running, pid 1)"
        echo "		cycles: last successful sync $(date -u +%Y-%m-%dT%H:%M:%S).000Z"; exit 0 ;;
esac
EOF
chmod +x "$work/bin/stub-client" "$work/agmsg/send.sh" "$work/agmsg/team.sh" "$work/agmsg/remote.sh"

export OPRC_CLIENT="$work/bin/stub-client"
export AGMSG_SCRIPTS_DIR="$work/agmsg"
export STUB_LOG="$work/log"
export STUB_BODY="$work/body"

good_payload="$work/payload.json"
printf '{"type":"OPREQ","purpose":"x"}' > "$good_payload"
good_notice="$work/notice.txt"
printf 'monnie の unpoller の設定を読んで確定してほしい。read-only のみ。\n' > "$good_notice"

run() {  # run <payload> <notice> ; 結果は rc / STUB_LOG / STUB_BODY
  : > "$STUB_LOG"; : > "$STUB_BODY"
  "$target" "$1" "$2" > "$work/out" 2> "$work/err"
  rc=$?
}

check() {  # check <説明> <条件の真偽値>
  if [ "$2" = "0" ]; then
    pass=$((pass + 1))
  else
    echo "FAIL: $1"
    [ -s "$work/err" ] && sed 's/^/      stderr: /' "$work/err"
    fail=$((fail + 1))
  fi
}

# --- submit より前に落ちること -------------------------------------------

# 1. 要旨が空
printf '   \n\t\n' > "$work/empty-notice.txt"
run "$good_payload" "$work/empty-notice.txt"
[ "$rc" = "2" ] && ! grep -q submit "$STUB_LOG"; check "要旨が空: submit せず exit 2" $?

# 2. payload が JSON でない
printf 'not json' > "$work/bad.json"
run "$work/bad.json" "$good_notice"
[ "$rc" = "2" ] && ! grep -q submit "$STUB_LOG"; check "payload 不正: submit せず exit 2" $?

# 3. 通知先の team が無い(送信時にしか分からないものを事前に落とす)
TEAM_RC=1 run "$good_payload" "$good_notice"
[ "$rc" = "2" ] && ! grep -q submit "$STUB_LOG"; check "team が無い: submit せず exit 2" $?

# 4. team はあるが identity が roster に無い
ROSTER='  coordinator (claude-code) — /repo' run "$good_payload" "$good_notice"
[ "$rc" = "2" ] && ! grep -q submit "$STUB_LOG"; check "宛先 identity が無い: submit せず exit 2" $?

# 5. 送信元 identity が roster に無い
ROSTER='  operator (remote — no local registration)' run "$good_payload" "$good_notice"
[ "$rc" = "2" ] && ! grep -q submit "$STUB_LOG"; check "送信元 identity が無い: submit せず exit 2" $?

# 6〜9. 通知がホストから出られない状態(sync engine)
#
# **send.sh の成功はローカルstoreへ書いたことしか意味しない。** remote team では
# engine がサーバへ運ぶまでが送信であり、engine が死んでいてもエラーは出ない。
for mode in stale old nosync fail; do
  SYNC_MODE="$mode" run "$good_payload" "$good_notice"
  [ "$rc" = "2" ] && ! grep -q submit "$STUB_LOG"
  check "sync が成立していない($mode): submit せず exit 2" $?
done

# --- submit 後の失敗を黙って成功にしないこと ------------------------------

# 10. submit 失敗なら通知を送らない
SUBMIT_RC=1 SUBMIT_OUT='' run "$good_payload" "$good_notice"
[ "$rc" != "0" ] && grep -q submit "$STUB_LOG" && ! grep -q send "$STUB_LOG"
check "submit 失敗: 通知を送らない" $?

# 11〜16. 応答の request_id が契約に適合しないとき、通知せず失敗する
#
# **末尾LFの1件は JSON escape のまま渡す。** 生LFを埋めると JSON 自体が壊れて
# json.load の失敗経路へ落ち、本体の `value != value.strip()` を一度も通らない
# (Python の `$` は末尾LFの手前で一致するため、この検査が無いと素通りする)。
# 生LF版は「応答がJSONとして読めない」経路として別に置く。
for bad in '{"conversation_id":"cnv-x"}' \
           '{"request_id":{"a":1}}' \
           '{"request_id":"req-20260902T090000+0900-abcdef0123456789\n"}' \
           '{"request_id":"req-20260902T090000+0900-abcdef0123456789 "}' \
           '{"request_id":"not-an-id"}' \
           '["req-20260902T090000+0900-abcdef0123456789"]'; do
  SUBMIT_RC=0 SUBMIT_OUT="$bad" run "$good_payload" "$good_notice"
  [ "$rc" != "0" ] && ! grep -q send "$STUB_LOG" && grep -q '登録された可能性' "$work/err"
  check "request_id が契約に適合しない($bad): 通知を送らず失敗" $?
done

# 17. 応答が JSON として読めない(本文に生LFが入る)
SUBMIT_RC=0 SUBMIT_OUT="$(printf '{"request_id":"%s\nEVIL"}' "$VALID_ID")" \
  run "$good_payload" "$good_notice"
[ "$rc" != "0" ] && ! grep -q send "$STUB_LOG" && grep -q '登録された可能性' "$work/err"
check "応答が JSON として読めない: 通知を送らず失敗" $?

# 18. 通知の送信に失敗したら「登録済み・未通知」を明示して失敗
SUBMIT_RC=0 SUBMIT_OUT="{\"request_id\":\"$VALID_ID\",\"conversation_id\":\"cnv-x\"}" \
  SEND_RC=1 run "$good_payload" "$good_notice"
[ "$rc" != "0" ] && grep -q send "$STUB_LOG" \
  && grep -q '登録済み' "$work/err" && grep -q '未送' "$work/err"
check "通知失敗: 登録済み・未送を明示して失敗" $?

# --- 正常系 ---------------------------------------------------------------

# 19. 登録し、request_id と要旨を載せて通知し、両方を報告する
SUBMIT_RC=0 SUBMIT_OUT="{\"request_id\":\"$VALID_ID\",\"conversation_id\":\"cnv-x\"}" \
  run "$good_payload" "$good_notice"
[ "$rc" = "0" ] \
  && grep -q submit "$STUB_LOG" && grep -q send "$STUB_LOG" \
  && grep -q "$VALID_ID" "$STUB_BODY" \
  && grep -q 'unpoller' "$STUB_BODY" \
  && grep -q 'show-request' "$STUB_BODY" \
  && grep -q "登録: $VALID_ID" "$work/out" \
  && grep -q '通知:' "$work/out"
check "正常系: 登録と通知が成立し、両方を報告する" $?

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" = "0" ]
