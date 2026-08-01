# review: 移設後の規範の成立確認(AC5検証を兼ねる)

日付: 2026-08-02 (JST) / 実施: Reviewer(独立subagent、`003`とは別セッション)

## 自分に与えられた役割定義(冒頭で渡されたブロック、一字一句そのまま転記)

役割の正本は次の2つで、この定義へ複製しない。着手時に必ず読むこと。

- `docs/ai/core.md`(全Role共通原則・安全境界。「subagentが共通して守ること」を含む)
- `docs/ai/roles/reviewer.md`(責任・権限・成果物・禁止事項・必須Skill)

出力フォーマットは`skills/code-review/SKILL.md`、観点は`skills/duplication-reuse-check/SKILL.md`と`skills/ansible-security-review/SKILL.md`を参照する。規範文書の変更をレビューするときは`skills/document-norm-review/SKILL.md`を併用する。

あなたはCoordinatorが起動したsubagentである。会話の過程は永続しないので、**findingsと確認範囲は案件のreview記録ファイル(計画査読ならplan_review記録)へ書き切る**。

---

## 着手時に読んだファイル(読んだ順)

1. Skill `document-norm-review`(本文全体)
2. Skill `code-review`(本文全体)
3. `git show 8b9544b --stat` / `git show 8b9544b`(diff全文をファイルへ保存して取得)
4. `docs/ai/core.md`(全文)
5. `docs/ai/roles/reviewer.md`(全文)
6. diff全文(保存したファイルを通読)
7. `docs/ai/role-routing-index.md`(全文)
8. `docs/ai/roles/implementer.md`(全文)
9. `docs/ai/roles/tester.md`(全文)
10. `docs/ai/roles/coordinator.md`(該当箇所をgrepしたのち全文)
11. `.claude/agents/implementer.md` / `.claude/agents/reviewer.md` / `.claude/agents/tester.md` / `.claude/agents/auditor.md`(現物、`cat -n`)
12. `docs/ai/policies/ansible_test_safety_policy.md`(`tester_mode` / `skip_notifications` / `TS-031`関連箇所をgrep)
13. リポジトリ全体を対象に、host名残存・宙ぶらりん参照(`実ホスト検証の安全ゲート` / `subagentとしての事情`)・`AGENTS.md` / `CLAUDE.md`の該当語を機械的にgrep
14. `roles/` `playbooks/` `inventories/` に対する`tester_mode` / `skip_notifications`の実コード使用状況をgrep(Policy文言との突合用)

---

## Critical Issues

### 1. 「Testerが実ホストへ到達してよい唯一のRoleである」が、同一Roleセット内のCoordinator自身の権限と矛盾する

`docs/ai/role-routing-index.md`の今回diffで追加された行(Tester行):

> **実ホストへ到達してよい唯一のRoleである** — Implementer / Reviewer / Auditorは実ホストへansibleを実行しない。

この文は「唯一の」と述べながら、除外列挙には`Implementer / Reviewer / Auditor`の3つしか挙げておらず、同じ表の1行目に載っている`Coordinator`を対象から外している。しかし`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」(このdiffの対象外・既存文書)は、Coordinator自身が実ホストへ到達することを明文で認めている。

- 41行目: 「**状態を変えない操作(見るだけの確認)は、保護対象ホストであっても確認不要である。**…**これは意図された許可であり、実host ad-hoc禁止を撤廃したことの副作用ではない**」— Coordinatorは`pve1`等保護対象ホストへも状態を変えない確認を行える。
- 71行目: 「**事実の収集(状態を変えない確認)はCoordinatorが行ってよい**」。
- 35行目・37行目: `monnie` / `quory` / `ansy`への非冪等操作、systemd timer/serviceの有効化・無効化等は「Coordinatorが判断し実施」— 承認だけでなく実施主体もCoordinatorである。

`CLAUDE.md`もこの承認境界節を「Claude Code固有の実行許可・禁止」の正本として参照しており、Coordinator(Claude Code対話セッション)自身が実ホストへ到達する経路を追認している。

したがって「Testerが唯一」という主張は、除外列挙にCoordinatorを含めていない書き方と、Coordinator自身の既存の実ホスト到達権限との間で両立しない。読み手が「Tester以外は誰も実ホストに触れない」と字義通り受け取ると、Coordinator自身の確立済み権限(状態を変えない確認、非保護ホストへの非冪等操作の直接実施)と衝突する。書き手の意図は「subagent 4種のうちTesterだけ」だと推測できるが、文は`Role`という語をCoordinatorも含む単位で使っており(同じ表の1行目がCoordinator)、限定が効いていない。

対象: `docs/ai/role-routing-index.md` 16行目。`.claude/agents/tester.md` frontmatterの`description`(「実ホスト検証を担う唯一のRole。」)も同根の表現だが、今回のdiffの対象外(frontmatterはrequirement記録がscope外と明記)のため参考記載に留める。

---

## Suggestions

### 2. `tester_mode=true`の案内が、同じPolicy内の「廃止済み」記述と並置されると読み手を混乱させる

`docs/ai/roles/tester.md`の新設文(このdiffで追加):

> 通知経路を含むplaybookを`--check`なしで実行するときは、`skip_notifications=true`(または`tester_mode=true`)を付与する。

実コード(`roles/common_slack/tasks/notify.yml` 28〜45行目)は`tester_mode`を`skip_notifications`と並ぶ有効な抑止フラグとして今も受け付けており、この文自体は実装と矛盾しない。

一方、`docs/ai/policies/ansible_test_safety_policy.md` 16行目は「`tester_mode`変数と`tester_gate` roleは2026-07-06〜07に廃止済みであり」と述べている。実際には`recovery_vm_reboot.yml`等の一部playbookで`tester_mode`を明示的に拒否(deprecated assert)する一方、`common_slack`の通知抑止としては現役という**二重の意味**が同じ変数名に乗っている。今回追加された`tester.md`の文はTester役が必須で読むSkill/Policyの一つ(`docs/ai/policies/ansible_test_safety_policy.md`、`.claude/agents/tester.md`が新たに正本として指定)と並べて読むと、「廃止済みのはずの変数を使えと書いてある」ように見え、規範間の整合性チェックで引っかかる。実害は小さい(実装は`tester.md`の記述どおりに動く)が、Policy側の「廃止済み」という言い切りを`tester_mode`のnotify抑止用法にも及ぶものと誤読されないよう、どちらかの文書で用途を書き分けた方がよい。

対象: `docs/ai/roles/tester.md` 37行目、`docs/ai/policies/ansible_test_safety_policy.md` 16行目(このdiffの対象外)。

---

## What Looks Good(変わっていないこと・意味が保たれていることを確認できた項目)

- **移設後の参照の実在**: `docs/ai/roles/implementer.md`・`docs/ai/roles/reviewer.md`が指す`docs/ai/core.md`「Ansible変更の共通ゲート」、`docs/ai/roles/tester.md`が指す`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」は、いずれも見出しを含めて実在し、引用内容とも整合する。
- **host名の残存**: `.claude/agents/*.md`、`docs/ai/roles/{implementer,reviewer,tester}.md`、`docs/ai/core.md`、`docs/ai/role-routing-index.md`を対象に`pve1|pve2|authy|sophos-fw|cloudkey|monnie|quory`で機械的に再掃引した。`docs/ai/core.md`の`quory`3件のみヒットしたが、いずれも「開発と本番の境界」節の既存記述(承認境界の列挙ではない)であり、AC3の主張(実ホスト名の列挙は`.claude/settings.json`と`docs/ai/roles/coordinator.md`の2箇所)と矛盾しない。
- **宙ぶらりん参照なし**: `実ホスト検証の安全ゲート` / `subagentとしての事情`をリポジトリ全体(`.md`)で再検索し、`docs/ai/reviews/`配下の記録以外への残存はゼロだった。
- **`AGENTS.md` / `CLAUDE.md`との整合**: `CLAUDE.md`は`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」を実行許可・禁止の参照先として明示しており、今回の`core.md` / `role-routing-index.md`の変更内容と競合しない(Critical #1で述べたCoordinatorの権限自体は`CLAUDE.md`側の記述と整合している——矛盾しているのは`role-routing-index.md`内の「唯一」表現そのもの)。
- **指示以外の記述(経緯・日付つき履歴・reviews/lessons参照)**: 今回diffで新設・改訂された文言自体(`core.md`のdecoy inventory定義、「subagentが共通して守ること」の2項目追加、`roles/{implementer,reviewer,tester}.md`の新設文、`.claude/agents/*.md`の縮退後body)には、日付つき経緯・事故説明・`docs/ai/reviews/`や`docs/ai/memory/lessons/`への参照は含まれていない。2026-08-01方針に沿っている。
  - ただし**既存部分**(このdiffが触っていない箇所)には残存がある。列挙のみ行い、修正はしない。
    - `docs/ai/role-routing-index.md` 13行目: 「`(2026-07-31、Yoshinobu明示)`」
    - `docs/ai/role-routing-index.md` 27・30行目: 「モデル・effort配分」の`medium`確定根拠として、日付つき経緯と`incident_investigate_trigger`案件の事故説明(`chmod 000`したファイルへの`stat`の挙動等)が数文にわたり残っている。
    - `docs/ai/role-routing-index.md` 48行目: `docs/ai/memory/lessons/claude-code-unattended-session-confinement.md`への参照。
    - `docs/ai/role-routing-index.md` 63・75・84行目: `docs/ai/reviews/<target>/`への参照(ただしこれらは「証跡はここに置く」という運用上のポインタであり、経緯説明ではないため、他の3件とは性質が異なる——document-norm-reviewが問題視するのは経緯・事故説明の残存であり、成果物置き場を指すポインタそのものは対象外と判断した)。

---

## Verdict

**Request Changes**(Critical 1件)。Suggestionsは1件、実害は小さいが規範間の読み合わせで混乱を招く。「指示以外のもの」の既存残存は今回diffの範囲外であり列挙のみ。

---

## Coordinatorによる照合と対応(2026-08-02)

### AC5 — 満たされた

このReviewerは、依頼文で `docs/ai/core.md` と `docs/ai/roles/reviewer.md` を読めと**指示していない**状態で起動した。結果:

- 冒頭に転記された定義本文は、作業ツリーの `.claude/agents/reviewer.md` の縮退後body(4段)と**一字一句一致**する。
- 「着手時に読んだファイル」の4番目が `docs/ai/core.md`、5番目が `docs/ai/roles/reviewer.md`。**4行の定義に導かれて正本を読んでいる。**

したがって AC5(縮退後の定義で起動したsubagentが `docs/ai/core.md` と自分のRole文書を実際に読んでから作業に入る)は満たされた。`2026-08-02_003_review.md` の Critical 1 はこれで解消する。

### agent定義の変更が効くタイミング

`003_review.md` が観測した「編集前の定義が渡っていた」事象との差分は、**セッションが変わったこと**である。編集とcommitを行ったセッションは `2f04d8ae`、本検証を行ったセッションは `020b0f98` で別物である(`~/.claude/projects/-home-yoshi-homelab-ansible/*.jsonl` の更新時刻で確認)。`/clear` そのものが効いたのではなく、`/clear` が新しいセッションを開始したことが効いている。

規範として `docs/ai/role-routing-index.md`「Agent定義との関係」へ1文で反映した(経緯・日付は書かない)。

### findingsの対応

| # | 対応 |
|---|---|
| Critical 1(「唯一のRole」がCoordinatorと矛盾) | **是正した。** `docs/ai/role-routing-index.md` L16 を「**subagentのうち、**実ホストへ到達してよい唯一のRoleである」へ改め、Coordinator自身の到達範囲は `docs/ai/roles/coordinator.md` が定める旨を併記した。指摘のとおり、書き手の意図は「subagent 4種のうちTesterだけ」であり、限定語が落ちていた |
| Suggestion 2(`tester_mode` の二重の意味) | **部分的に是正した。** `docs/ai/roles/tester.md` から `(または`tester_mode=true`)` を削除し、規範が案内する抑止フラグを `skip_notifications` の1つに寄せた。**残る不整合は規範側ではなくコード側にある** — `roles/common_slack/tasks/notify.yml` は `tester_mode` を今も有効な抑止フラグとして受け付けており(28〜45行、Coordinatorが現物で確認)、`docs/ai/policies/ansible_test_safety_policy.md` TS-003 の「`tester_mode`変数…は廃止済み」という言い切りと食い違う。Policy本文の改訂とコードからの削除はいずれも本案件のscope外であり、Yoshinobuへ判断を上げた |
| 既存部分に残る経緯・lessons参照の列挙(What Looks Good 末尾) | **本案件では修正しない。** 規範文書から経緯・根拠・`docs/ai/reviews/` / `docs/ai/memory/lessons/` 参照を落とす見直しは、2026-08-02にYoshinobuが独立したフェーズとして立てる方針を示した。この列挙はその入力として残す |
