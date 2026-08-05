#!/usr/bin/env bash
# 新しいROOT CA証明書を「配る前に」検証する。
#
# 用途: ROOT CA(Home-RADIUS-CA)を同じ鍵のまま再発行したとき、配布して
#       しまう前に、それが本当に差し替え可能なものかを確かめる。
#       配ってから間違いに気づくと、全ホストの信頼ストアが壊れる。
#
# 使い方:
#   scripts/verify-root-ca.sh <新しいROOT証明書> [現行ROOT証明書] [検証に使うendpoint]
#
#   既定の現行ROOT   : /usr/local/share/ca-certificates/home-tls-root-ca.crt
#   既定のendpoint   : ansy.internal:3000(このホスト自身のSemaphore)
#
# **秘密鍵は一切扱わない。** 引数に鍵を渡さないこと。検証は公開物だけで完結する。
#
# 終了コード: 0 = すべてPASS / 1 = 1つ以上FAIL / 2 = 使い方の誤り
#
# 背景と根拠: docs/ai/reviews/root_ca_keyusage/2026-08-05_001_requirement.md
set -uo pipefail

NEW="${1:-}"
CUR="${2:-/usr/local/share/ca-certificates/home-tls-root-ca.crt}"
ENDPOINT="${3:-ansy.internal:3000}"

if [[ -z "$NEW" || ! -r "$NEW" ]]; then
  echo "usage: $0 <new-root-ca.crt> [current-root-ca.crt] [host:port]" >&2
  exit 2
fi

fails=0

ok()   { echo "  OK   : $*"; }
fail() { echo "  FAIL : $*"; fails=$((fails + 1)); }

field() { openssl x509 -in "$1" -noout -"$2" 2>/dev/null | sed "s/^$2=//"; }
ski()   { openssl x509 -in "$1" -noout -ext subjectKeyIdentifier 2>/dev/null | tail -1 | tr -d ' \t'; }

echo "== 新ROOT証明書の検査 =="
echo "  対象: $NEW"

# 1. subject が現行ROOTと完全一致していること。
#    **DNは構成要素の順序まで含めて一致する必要がある。** 中間CAのissuer欄は
#    現行ROOTのsubjectをそのままコピーしており、順序が違えば別のDNとして扱われて
#    鎖が繋がらない。実際、この環境のROOTは `-subj "/CN=.../O=home/C=JP"` の順で
#    作られており、素直に `/C=JP/O=home/CN=...` と書くと不一致になる(2026-08-05実測)。
#    期待値をハードコードせず、現行ROOTから取るのはそのためである。
s="$(openssl x509 -in "$NEW" -noout -subject -nameopt RFC2253 2>/dev/null | sed 's/^subject=//')"
if [[ -r "$CUR" ]]; then
  es="$(openssl x509 -in "$CUR" -noout -subject -nameopt RFC2253 2>/dev/null | sed 's/^subject=//')"
  [[ "$s" == "$es" ]] && ok "subject が現行と一致 ($s)" \
    || fail "subject が現行と違う — DNの順序も含めて一致させること (現行: $es / 新: $s)"
else
  fail "現行ROOTが読めない ($CUR) — subject の一致を確認できない"
fi

# 2. 自己署名であること
i="$(openssl x509 -in "$NEW" -noout -issuer -nameopt RFC2253 2>/dev/null | sed 's/^issuer=//')"
[[ "$i" == "$s" ]] && ok "自己署名 (issuer == subject)" || fail "自己署名でない (issuer: $i)"

# 3. **同じ鍵であること。** ここが本検査の核心 — SKIが変わると中間CAのAKIと
#    一致しなくなり、中間・leafを全部作り直す羽目になる
if [[ -r "$CUR" ]]; then
  ns="$(ski "$NEW")"; cs="$(ski "$CUR")"
  if [[ -n "$ns" && "$ns" == "$cs" ]]; then
    ok "SKI が現行と一致 = 同じ鍵 ($ns)"
  else
    fail "SKI が現行と違う (現行: ${cs:-なし} / 新: ${ns:-なし}) — 鍵が変わっている。中間CAのAKIと繋がらない"
  fi
  # 4. シリアルは別値であること(同一subject+鍵の2枚目になるため)
  [[ "$(field "$NEW" serial)" != "$(field "$CUR" serial)" ]] \
    && ok "シリアルが現行と異なる" || fail "シリアルが現行と同じ"
else
  fail "現行ROOTが読めない ($CUR) — 同一鍵の確認ができない"
fi

# 5. KeyUsage — これを足すのが今回の目的そのもの
ku="$(openssl x509 -in "$NEW" -noout -ext keyUsage 2>/dev/null)"
if grep -q "Certificate Sign" <<<"$ku" && grep -q "CRL Sign" <<<"$ku"; then
  ok "KeyUsage に Certificate Sign / CRL Sign がある"
  grep -q "critical" <<<"$ku" && ok "KeyUsage が critical" || fail "KeyUsage が critical でない"
else
  fail "KeyUsage が無い、または Certificate Sign / CRL Sign を欠く"
fi

# 6. BasicConstraints
bc="$(openssl x509 -in "$NEW" -noout -ext basicConstraints 2>/dev/null)"
grep -q "CA:TRUE" <<<"$bc" && ok "basicConstraints CA:TRUE" || fail "basicConstraints CA:TRUE でない"
grep -q "critical" <<<"$bc" && ok "basicConstraints が critical" || fail "basicConstraints が critical でない"

# 7. 有効期間が今を含むこと
openssl x509 -in "$NEW" -noout -checkend 0 >/dev/null 2>&1 && ok "有効期限内 ($(field "$NEW" enddate))" \
  || fail "既に期限切れ、または notBefore が未来"

# 8. **実物のチェーンが、この証明書をanchorにして厳格検証を通ること。**
#    1〜7 が全部通っても、実際の中間CAと繋がらなければ意味がない。
#    ここだけは生きているendpointから鎖を取ってきて確かめる
echo "== 実チェーンでの厳格検証 (endpoint: $ENDPOINT) =="
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
if timeout 20 openssl s_client -connect "$ENDPOINT" -showcerts </dev/null 2>/dev/null > "$tmp/chain.txt" \
   && grep -q "BEGIN CERTIFICATE" "$tmp/chain.txt"; then
  awk '/BEGIN CERT/{n++} n==1' "$tmp/chain.txt" | awk '/BEGIN CERT/,/END CERT/' > "$tmp/leaf.pem"
  awk '/BEGIN CERT/{n++} n==2' "$tmp/chain.txt" | awk '/BEGIN CERT/,/END CERT/' > "$tmp/inter.pem"
  if [[ -s "$tmp/inter.pem" ]]; then
    # -no-CApath / -no-CAstore が必須。付けないと openssl は既定の信頼ストアも
    # 参照するため、渡した証明書が無効でも「システムに旧ROOTがある」だけで
    # 通ってしまい、この検査が何も検査していない状態になる(2026-08-05に実測)。
    if out="$(openssl verify -x509_strict -no-CApath -no-CAstore -CAfile "$NEW" -untrusted "$tmp/inter.pem" "$tmp/leaf.pem" 2>&1)"; then
      ok "厳格検証を通った(中間・leafは現行のまま)"
    else
      fail "厳格検証に失敗: $out"
    fi
  else
    fail "endpoint が中間CAを提示しない — 鎖を組めない"
  fi
else
  fail "endpoint へ接続できない ($ENDPOINT) — この検査だけ実施できていない"
fi

echo
if (( fails == 0 )); then
  echo "RESULT: PASS — 配布してよい"
  exit 0
fi
echo "RESULT: FAIL ($fails 件) — **配布しないこと**"
exit 1
