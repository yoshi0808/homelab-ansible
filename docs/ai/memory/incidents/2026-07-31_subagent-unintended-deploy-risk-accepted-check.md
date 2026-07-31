# Incident: `--check` が効かないplaybookを「dry run のつもり」でsubagentが実配備した

日付: 2026-07-31
状態: 解決済み(事象は封じ込め・復旧済み。**再発防止は未実施** — 下記「申し送り」)
対象: `playbooks/incident_inspect_setup.yml`(新規)、Implementer subagent(U1)、ansy
種別: 未遂
原因分類: #運用考慮ミス #テスト不足

## 症状

案件「障害の一次調査の自動化」のU1実装中、Implementer subagentが自己検証のために
`playbooks/incident_inspect_setup.yml` を **decoy inventory + `--check`** で実行した。
**本人はdry runのつもりだった。** 実際にはansy上で次が本当に作られた。

- ユーザー `incident-inspect`(home、`.codex/`、config)
- `/usr/local/bin/codex-investigate-wrapper`
- `/var/lib/incident-inspect/workspace`
- `/etc/sudoers.d/incident-inspect`
- `/home/yoshi`・`/var/lib/semaphore`・`semaphore.db` へのACLエントリ

Coordinatorの依頼文は「**実ホストへ配備された状態**」を到達してはならない状態として明示していた
(手段ではなく結果で書いてあった)。**それでも防げなかった。**

## 原因

`playbooks/incident_inspect_setup.yml` は既存の `recovery_exec_setup.yml` /
`recovery_io_setup.yml` と同じ `# tester-gate: risk-accepted` の型を踏襲しており、
**`check_mode: false` を明示して `--check` を無効化する**。これはこのクラスのplaybookでは
意図された設計である(`docs/ai/policies/ansible_test_safety_policy.md`)。

一方、このリポジトリで安全な検証手段として定着している「**decoy inventory**」は、
**`--check` が効くことを暗黙の前提にしていない**にもかかわらず、両者を組み合わせれば安全だと
読める状態にあった。`ansible_connection: local` のdecoyは「接続先を偽装する」だけであり、
**実行主体(ansy自身)への副作用は一切防がない。** `risk-accepted` と組み合わせると、
decoyは安全装置として何も働かない。

つまり原因は個人の不注意ではなく、**検証手段の適用条件が文書化されていないこと**である。

## 修正内容

1. **即時復旧(subagentが自ら実施)。** ACLエントリを外科的に除去(既存の `recovery-exec` エントリは温存)、
   sudoers・wrapper・workspaceを削除、`userdel -r`。
2. **Coordinatorによる独立確認。** `getent passwd`(該当ユーザー無し)、4パスの不在、
   `getfacl` で `/home/yoshi`(`user:recovery-exec:--x`)・`/var/lib/semaphore`(同 `--x`)・
   `semaphore.db`(同 `r--`)が残存し `incident-inspect` のエントリが無いことを確認。
   `reports/` 配下に成果物は作られていない。
3. **本番(quory)には一切及んでいない。** 実行はansy上のみ。

## 申し送り(未実施)

**再発防止はしていない。** 候補は次の2つで、`docs/ai/status.md` Next に置いた。

- **`--check` の意味の多重定義を解くこと(構造の修正。文書化では解けない)。** 2026-07-31の実測で、
  `check-mode-native` 19本では `--check` は「シミュレート」を意味する一方、`risk-accepted` 18本のうち
  **6本**が `skip_notifications: "{{ ansible_check_mode }}"` として「**本適用はするが通知は抑止する**」の
  意味で使っていることが分かった。**同じフラグが逆の意味を持つため、「`risk-accepted` は `--check` で
  停止させる」という単純な修正はその6本を壊す。** 通知抑止を `ansible_check_mode` から切り離してから
  でなければ着手できない。**原因は踏む側の注意力ではなくフラグの多重定義である**(2026-07-31 Yoshinobu指摘。
  「`--check` を付けたから安全と思うな、は無理がある。環境が悪い」)
- subagentへ渡す依頼文の限界の再確認。**結果で書いた禁止も、実行者が「これは該当しない」と
  解釈すれば越えられる**(`docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`
  の「型が塞がないもの」がまさにこれを予告していた)。今回は**ansyという非保護ホストであり、
  Coordinator権限では承認不要の操作**だったため実害が出なかっただけである。同じ経路が
  quoryを向いていた場合の結果は違う。

## 確認方法

復旧の確認は上記2のコマンド群で行った。**再発防止の確認方法は、対策が決まっていないため未定。**

## 参照

- `docs/ai/reviews/incident_auto_investigation/2026-07-31_004_u1_implement.md` §0(実行者による一次記録)
- `docs/ai/policies/ansible_test_safety_policy.md`(`risk-accepted` の定義)
- `docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`
- 過去の同クラス: `docs/ai/memory/incidents/` および auto-memory の「subagentのscope creep 2件(2026-07-26 / 2026-07-28)」
