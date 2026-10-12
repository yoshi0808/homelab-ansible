# 計画査読(2回目)

`/usr/bin/codex exec resume 01a12ea4-0c93-75f3-93da-40ac7471bb0f -m gpt-5.6-sol -c model_reasoning_effort=medium -c sandbox_mode="read-only"`(0.162.0。1回目は0.154.0で作ったセッション)。最終メッセージを原文のまま転記。

## Code Review: codex_exec_roles requirement（再査読）

### Summary

前回のCritical 1件、Major 4件、Minor 1件は解消しました。Role/session分離のMajorは大部分が解消しましたが、計画ReviewerのRole文書パスが成立しないため、Major 1件が残ります。

### 前回findingsの状態

| 前回finding | 状態 |
|---|---|
| Git add/commit/pushがallow | 解消 |
| agmsg shimの残存 | 解消 |
| Role指示・sessionのRole束縛 | **一部未解消** |
| Auditor入力制限 | 解消 |
| `status.md`の更新漏れ | 解消 |
| R2～R4を検証するAC不足 | 解消 |
| team `homelab`の残存登録 | 解消 |

### Blocking findings

1. **Major — `plan-reviewer`から実在しないRole文書を組み立てる要求になっている**

   wrapperが受け取るRole名は`plan-reviewer`ですが、起動指示は機械的に`docs/ai/roles/<役>.md`を読む形とされています。[requirement:23](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:23) [requirement:25](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:25)

   これをそのまま展開すると`docs/ai/roles/plan-reviewer.md`になりますが、そのファイルは存在せず、正本は`docs/ai/roles/reviewer.md`です。[reviewer.md:1](../../../../docs/ai/roles/reviewer.md:1) 起動時にRole文書を読ませる義務はCoordinator Roleにもあります。[coordinator.md:15](../../../../docs/ai/roles/coordinator.md:15)

   AC1はmodel・effort・sandboxしか観測しないため、誤ったRole文書を指しても通過します。[requirement:61](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:61)

   `plan-reviewer → docs/ai/roles/reviewer.md`という明示的な対応をR1へ追加し、3 Roleそれぞれについて生成された起動指示が正しいRole文書を指すことをACで確認する必要があります。

### Non-blocking findings

1. **Minor — AC1の継続条件がAuditor禁止と文面上競合する**

   AC1の「3つの役それぞれ」に続く「継続の呼び出しでも同じ値で動く」は、Auditorのresumeも成功させるように読めます。[requirement:61](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:61) 一方、R1とAC4bはAuditorのresumeを明示的に拒否します。[requirement:27](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:27) [requirement:67](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:67)

   AC1を「継続を許すImplementerと計画Reviewer」に限定すると一意になります。あわせて、依頼文をファイルまたはstdinで受け取る規定もAuditorを除く旨を明確にするとよいです。

### What Looks Good

- `git add` / `git commit` / `git push`を`forbidden`にし、使い捨てGitリポジトリで検証する要求になりました。[requirement:40](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:40) [requirement:66](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:66) `forbidden`が現行`/usr/bin/codex execpolicy`で有効なdecisionであることもローカル確認済みです。
- `/usr/bin/codex`を直接呼び、shim・delivery modeも撤去する要求と、R5適用後の再検証が追加されました。[requirement:24](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:24) [requirement:57](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:57) [requirement:68](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:68)
- session IDとRoleの対応記録、Roleを跨ぐresumeの事前拒否が追加され、Implementerと計画Reviewerの別identity要件を機械的に維持できます。[requirement:26](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:26)
- Auditorは専用入力だけを受け取り、自由文とresumeを拒否する形になりました。[requirement:27](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:27)
- `status.md`が変更対象へ追加されました。[requirement:48](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:48)
- Role×model/effort、撤回語の掃引、ADR-016の置換関係がACへ追加されました。[requirement:63](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:63)
- team `homelab`は全登録を外す要求になりました。現物の現在の登録が`coordinator`と`implementer`の2件だけであることも確認済みです。[requirement:54](../../../../docs/ai/reviews/codex_exec_roles/2026-10-12_001_requirement.md:54)
- `/usr/bin/codex`が0.162.0、standaloneが0.154.0であることを確認しました。固定先の事実記述は現物と一致します。

### 未確認

- `scripts/codex-role.sh`は未実装のため、Role起動指示、session ID抽出・記録、出力ファイル処理の実挙動。
- repo外変更後の`new-session.sh`、hooks、config、PATH、delivery modeの最終状態。
- AC1～AC7の実行結果。
- repo外ホストおよびquoryの状態。接続していません。
- `forbidden`構文はローカルCLIで確認しましたが、公式OpenAIドキュメント上の記述は取得できず未確認です。
- ファイルは変更していません。返却時も`_001`と`_002`の2ファイルだけが未追跡です。

### Verdict

**Request Changes** — Major 1件の修正後に再査読が必要です。