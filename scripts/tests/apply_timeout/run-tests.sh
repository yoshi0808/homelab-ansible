#!/usr/bin/env bash
# apply.yml の apt 実行を包む wrapper が、上限どおりに閉じることの回帰テスト。
#
# **守っているのは1つ** — 上限を超えたとき、**プロセス木ごと閉じて Ansible の
# task が期限内に返る**こと。2026-09-03 に本番(ジョブ #938)が無期限停止し、
# その修正案 `timeout --foreground` は「停止は消えるが子孫が残り、Ansible の
# run_command() が pipe を読み続けて返らない」という別の穴を持っていた。
# 機構と実測は docs/ai/reviews/ubuntu_vm_apply_timeout_sigttou/。
#
# **wrapper は apply.yml から読み取る。** ここへ値を写さない — 写すと
# apply.yml だけが直ったときにテストが素通りする。
#
# 端末(SIGTTOU)の経路は localhost では再現しない(pty が要る)。そちらは
# sandbox での手順として案件記録に残してある。ここで見るのはプロセス木の側。
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
fail=0; pass=0

LIMIT=3; KILL_AFTER=2
# ケースごとに期待が違う。TERM で閉じる経路は上限+余裕、TERM を無視する経路は
# kill-after の分だけ余計にかかるのが正しい(SIG_IGN は exec した子へ継承される
# ため、sleep も TERM を無視して KILL まで生き残る)。
BOUND_TERM=5      # LIMIT + 余裕。--foreground 版は 6.07 秒でここを超える(判別点)
BOUND_KILL=7      # LIMIT + KILL_AFTER + 余裕

# --- apply.yml から wrapper(apt-get より前の argv)を取り出す ---------------
#
# **番兵 `apt-get` が見つからなければ、何も実行せずに落ちる。** 見つからない
# ときに argv 全体を wrapper として採用すると、`-y full-upgrade` を含む本番の
# argv をこのホストで起動しうる(2026-09-03 独立レビュー F2)。判定できない
# ときは通さない。
extract() {  # extract <apply.yml のパス> ; 成功時のみ JSON を stdout へ
  python3 - "$1" "$LIMIT" "$KILL_AFTER" <<'PY'
import sys, yaml, json, re
path, limit, kill_after = sys.argv[1], sys.argv[2], sys.argv[3]
tasks = yaml.safe_load(open(path, encoding="utf-8"))
for t in tasks:
    if isinstance(t, dict) and t.get("name") == "Run apt full-upgrade":
        argv = t["ansible.builtin.command"]["argv"]
        break
else:
    sys.exit("apply.yml に 'Run apt full-upgrade' が見つからない")

SENTINEL = "apt-get"
out, found = [], False
for a in argv:
    a = str(a)
    if a == SENTINEL:
        found = True
        break
    a = a.replace("{{ ubuntu_vm_full_upgrade_apply_timeout_seconds }}", limit)
    a = a.replace("{{ ubuntu_vm_full_upgrade_apply_kill_after_seconds }}", kill_after)
    if re.search(r"\{\{", a):
        sys.exit("未解決の変数が残っている: " + a)
    out.append(a)

if not found:
    sys.exit("番兵 %r が argv に無い。実装側が名前や絶対パスを変えた可能性がある。"
             "何も実行せずに停止する(本番argvをこのホストで動かさないため)" % SENTINEL)
if not out:
    sys.exit("wrapper が空。%s が argv の先頭にある" % SENTINEL)
# 二重の歯止め: 取り出した wrapper に apt 系の語が混じっていたら実行しない
for a in out:
    if "apt" in a.lower() or "upgrade" in a.lower():
        sys.exit("wrapper に本番コマンドらしき要素が混じっている: " + a)
print(json.dumps(out, ensure_ascii=False))
PY
}

prefix_json="$(extract "$repo_root/roles/ubuntu_vm_full_upgrade/tasks/apply.yml")" || {
  echo "FAIL: wrapper の抽出に失敗した(上の理由)。テストは何も実行していない"; exit 1; }
echo "wrapper: $prefix_json"

# --- 抽出そのものの negative test(実行を伴わない) --------------------------
neg_extract() {  # neg_extract <説明> <sed式>
  local desc="$1" expr="$2" f="$work/neg.yml"
  sed "$expr" "$repo_root/roles/ubuntu_vm_full_upgrade/tasks/apply.yml" > "$f"
  if extract "$f" >/dev/null 2>&1; then
    echo "FAIL: $desc — 抽出が成功してしまった(fail-closed でない)"; fail=$((fail+1))
  else
    pass=$((pass+1))
  fi
}
neg_extract "番兵を絶対パスへ変えたら停止する" 's|^\( *\)- apt-get$|\1- /usr/bin/apt-get|'
neg_extract "番兵を別名へ変えたら停止する"   's|^\( *\)- apt-get$|\1- apt-fast|'

run_case() {  # run_case <名前> <sh -c へ渡す本文>
  python3 - "$prefix_json" "$2" > "$work/pb.yml" <<'PY'
import sys, json, yaml
prefix = json.loads(sys.argv[1]); body = sys.argv[2]
print(yaml.safe_dump([{
  "hosts": "localhost", "gather_facts": False, "connection": "local",
  "tasks": [
    {"name": "case", "ansible.builtin.command": {"argv": prefix + ["sh", "-c", body]},
     "changed_when": False, "failed_when": False, "register": "r"},
    {"ansible.builtin.debug": {"msg": "RESULT rc={{ r.rc }} delta={{ r.delta }}"}},
  ]}], allow_unicode=True, sort_keys=False))
PY
  out="$(cd "$repo_root" && timeout 60 ansible-playbook "$work/pb.yml" 2>&1)"
  echo "$out" | sed -n 's/.*RESULT rc=\([0-9-]*\) delta=\([0-9:.]*\).*/\1 \2/p' | tail -1
}

check() {  # check <説明> <rc> <経過秒> <上限秒>
  local desc="$1" rc="$2" secs="$3" bound="$4"
  if [ -z "$rc" ]; then echo "FAIL: $desc (結果を読み取れない)"; fail=$((fail+1)); return; fi
  # 上限で閉じたことの証拠: rc が timeout 由来(124 または 137)で、経過が上限内
  if { [ "$rc" = "124" ] || [ "$rc" = "137" ]; } && \
     python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) <= $bound else 1)" "$secs"; then
    pass=$((pass+1))
  else
    echo "FAIL: $desc (rc=$rc, ${secs}s, 上限 ${bound}s)"; fail=$((fail+1))
  fi
}

to_secs() { python3 -c "
import sys
h,m,s = sys.argv[1].split(':'); print(int(h)*3600+int(m)*60+float(s))" "$1"; }

# 1. 子が出力し続ける — --foreground 版はここで超過する
read -r rc d <<<"$(run_case child '( i=0; while [ $i -lt 60 ]; do echo tick; i=$((i+1)); sleep 0.2; done ) & wait')"
check "子が出力し続けても上限で閉じる" "$rc" "$(to_secs "$d")" "$BOUND_TERM"

# 2. 孫が眠り続ける
read -r rc d <<<"$(run_case grandchild '( sleep 60 ) & wait')"
check "孫が残っていても上限で閉じる" "$rc" "$(to_secs "$d")" "$BOUND_TERM"

# 3. TERM を無視する子 — kill-after が効くこと
read -r rc d <<<"$(run_case ignore_term 'trap "" TERM; sleep 60')"
check "TERM を無視しても kill-after で閉じる" "$rc" "$(to_secs "$d")" "$BOUND_KILL"

echo "---"; echo "pass=$pass fail=$fail"
[ "$fail" = "0" ]
