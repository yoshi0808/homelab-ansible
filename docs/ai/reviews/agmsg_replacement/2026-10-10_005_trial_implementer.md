# 試行: Implementerを `codex exec` で動かした(2026-10-10)

題材は `docs/ai/reviews/ubuntu_full_upgrade_warning_drop/`(月次full-upgradeでauthy / monnieのhealthcheck WARNINGを捨てない)。

## 呼び出し

`codex exec -m gpt-5.6-terra -c model_reasoning_effort=medium -s workspace-write -C <repo> -o <最終メッセージの出力先> -`(依頼文は標準入力)。session id `01a1258d-03fb-7561-915e-6d80b93b3f0c`。

## 結果

- 2分32秒で終了し、rc=0。モデル・sandboxは指定どおり(`gpt-5.6-terra` / `workspace-write`、approval `never`)。
- repoのファイルを編集できた(`roles/ubuntu_vm_full_upgrade/tasks/healthcheck.yml` と案件フォルダの実装記録)。依頼した範囲の外は変更せず、stage・commit・pushもしなかった。
- 検証用のfixtureは依頼どおり `/tmp` に置き、localhostだけで自己検証した。
- sandboxや承認ルールで拒否されたコマンドは無かった。ただし、ルールに当たるコマンドを今回の作業で使わなかったということであり、**`.codex/rules/default.rules` が `codex exec` で効くことは確かめていない**。
- 差分Reviewer(Claude Code subagent)の判定はApprove。Coordinatorも `--syntax-check` を再実行して通ることを確かめた。

## 計画Reviewerの試行(`_001` 内)と合わせて分かったこと

- 依頼・差し戻し・結果の受け取りがすべてCoordinatorの呼び出しで完結し、seat・ロック・pane・bridgeを使わない。Implementerへ指示できるのはCoordinatorだけになる。
- 新規の呼び出しは毎回freshで、`resume` で同じセッションを続けられる。`resume` はモデルとsandboxを引き継がないため、毎回 `-m` と `-c sandbox_mode=...` を渡す。

## 未確認

- `.codex/rules/default.rules` の禁止・承認ルールが `codex exec`(approval `never`)でどう効くか。
- Implementerの差し戻しを `resume` で続けたとき、作業ツリーの変更を前提に正しく続きを行えるか(計画Reviewerでは会話の継続を確認済み)。
