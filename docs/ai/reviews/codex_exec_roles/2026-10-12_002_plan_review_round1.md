# 計画査読(1回目)

`codex exec -m gpt-5.6-sol -c model_reasoning_effort=medium -s read-only`、session id `01a12ea4-0c93-75f3-93da-40ac7471bb0f`。最終メッセージを原文のまま転記。

## Code Review: codex_exec_roles requirement

### Summary

**Request Changes**です。Critical 1件、Major 5件のblocking findingがあります。特に、ImplementerのGit確定操作を禁止できない現行rule、agmsg shimの残存、Roleを跨いだ`resume`、Auditor入力制限の欠落は、移行後の安全境界と独立性を崩します。

### Blocking findings

1. **Critical — AC4と現行のCodex ruleが正面から矛盾している**

   requirementはImplementerが`git commit`を実行できないことを要求していますが、現行ruleは`git commit`、`git push`、`git add`を明示的に`allow`しています。[requirement:57](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:57) [.codex/rules/default.rules:1](../../../../.codex/rules/default.rules:1) [.codex/rules/default.rules:8](../../../../.codex/rules/default.rules:8)

   しかしR3の変更対象はagmsgとtmuxの許可除去だけです。[requirement:34](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:34) 現行規範では`git add`はCoordinatorのみ、commit/pushもsubagentは禁止です。[core.md:64](../../../../docs/ai/core.md:64) [execution_boundary_policy.md:76](../../../../docs/ai/policies/execution_boundary_policy.md:76)

   R3へGit確定操作の機械的禁止を追加し、AC4は実リポジトリを誤ってcommitしない使い捨て環境で、少なくともadd/commit/pushを検証する必要があります。

2. **Major — 新wrapperがagmsg shimを経由する問題が変更範囲から抜けている**

   現在の`codex`は`/home/yoshi/.agents/bin/codex`、すなわちagmsg shimへ解決されます。Contextも、PATH上でこのshimを実バイナリより先に置く現行構成を明記しています。[agent-messaging.md:36](../../../../docs/ai/context/operations/agent-messaging.md:36) [agent-messaging.md:41](../../../../docs/ai/context/operations/agent-messaging.md:41)

   一方、R5はhookとwritable rootを外すだけで、shim、PATH、delivery mode、またはwrapperから実バイナリを確実に呼ぶ方法を扱っていません。[requirement:45](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:45)

   ローカル確認ではshimがagmsgのrun領域へ書こうとしました。writable root除去後は、新しい唯一の入口自体が失敗する可能性があります。shimの撤去または実バイナリの検証済み解決方法を要求し、R5適用後にAC1/AC5を再実行すべきです。

3. **Major — Role名がCodexへ渡ることと、sessionがRoleへ束縛されることが要求されていない**

   R1はRole名からモデル・effort・sandboxを選ぶだけで、CodexへRole本文を読ませる起動指示を付けることや、session IDを生成元Roleへ束縛することを要求していません。[requirement:21](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:21) [requirement:25](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:25)

   このままでは、例えばImplementerのsession IDを`plan-reviewer --resume`へ渡せます。計画ReviewerとImplementerを別identityにする現行規範を、CLI引数だけで破れます。[coordinator.md:21](../../../../docs/ai/roles/coordinator.md:21) [reviewer.md:26](../../../../docs/ai/roles/reviewer.md:26)

   wrapperがRole起動指示を必ず注入し、session IDとRoleの対応を検証すること、異なるRoleでのresumeをCodex呼び出し前に拒否するnegative ACが必要です。

4. **Major — Auditorが受け取れる入力の制限を新経路で維持できない**

   R1は全Role共通で任意のファイルまたは標準入力を受け取り、resumeも許します。[requirement:25](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:25) しかしAuditorへの依頼文に書けるのは「対象案件」と「読み始める場所」だけで、Coordinatorの説明は禁止されています。[auditor.md:40](../../../../docs/ai/roles/auditor.md:40) [coordinator.md:138](../../../../docs/ai/roles/coordinator.md:138)

   Auditor用入力形式を制限する要求も、その入力を確認するACもありません。resumeで追加説明を渡す経路も未整理です。Auditorは専用の最小入力schemaに限定し、通常の再起動・再監査を許さないか、許す例外を明示する必要があります。

5. **Major — `docs/ai/status.md`が書換え対象から漏れている**

   現在のstatusは、pane 1、`spawn.sh --fresh`、actasロックを現行問題として記録し、「次のresetでも再発する」としています。[status.md:22](../../../../docs/ai/status.md:22) 移行後もこの行が残れば、現在地の正本が廃止経路を現行事実として示します。

   R4はCoordinator Role、agent-messaging Context、ADRだけを列挙しており、statusを含みません。[requirement:39](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:39) `docs/ai/status.md`の更新または完了行除去をscopeへ追加すべきです。

6. **Major — ACがR2～R4の変更を十分に観測できない**

   AC群には、次を確認する条件がありません。

   - `.codex/rules/default.rules`からagmsg・tmux許可が残存ゼロになったこと
   - `session-context.py`から`AGMSG_SPAWNED`分岐が消えたこと
   - live文書からansy内のspawn、pane 1、Codex monitor前提が消えたこと
   - ADR-016がADR-015を正しくsupersedeしたこと
   - consistency checkが3 Roleそれぞれのmodelとeffortの不一致を検出すること

   R3/R4は[requirement:30-43](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:30)にありますが、ACは主に実行結果だけです。[requirement:52](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:52)

   撤回語の機械検索と、Role×model/effortの不一致検査をACへ追加しないと、部分実装でも受入可能です。

### Non-blocking findings

1. **Minor — team `homelab`のReviewer/Auditor登録の扱いが不明**

   現行のactive identityには`reviewer`と`auditor`もあります。[agent-messaging.md:19](../../../../docs/ai/context/operations/agent-messaging.md:19) R5が外すのは`coordinator`と`implementer`だけです。[requirement:48](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:48)

   機能上ただちに新経路を壊すとは限りませんが、廃止したlocal経路の現役登録が残ります。全登録またはteam自体を整理するのか、意図的に残す履歴なのかを明記してください。

### What Looks Good

- ADR-015を歴史記録として変更せず、ADR-016で置き換える方針は妥当です。
- `codex exec resume`が`-s`を持たず、`-m`とconfig overrideの再指定が必要という前提は、ローカルのCodex CLI 0.154.0でも確認できました。
- 計画Reviewer/Auditorをread-only、Implementerをworkspace-writeとする割当は現行Role責務と整合します。
- `homelab-ops`経路を残す切り分けと、execution boundary Policyの変更履歴を残す方針は妥当です。
- ファイル変更は行っていません。返却直前も査読対象のrequirementだけが未追跡でした。

### 未確認

- gitignoredの`new-session.sh`、team roster、`~/.codex/config.toml`、repo外のhooksの現物と変更後状態。
- repo外ホストおよびquoryの状態。接続していません。
- 背景資料に記録された過去の`codex exec`試行そのものの再実行。
- 未実装の`scripts/codex-role.sh`の具体的な引数形式・session ID取得方法。
- upstream agmsg最新版の内容。

### Verdict

**Request Changes** — Critical 1件とMajor 5件の解消後に再査読が必要です。