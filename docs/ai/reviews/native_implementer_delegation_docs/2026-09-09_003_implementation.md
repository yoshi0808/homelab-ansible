# Implementation: Implementer委任経路の規範を現行化する

## 変更

- `docs/ai/roles/coordinator.md`: ImplementerをCodex native subagentとして案件ごとに委任し、
  agmsg / tmux常駐を使わないと明記。model / effortの指定元をnative delegationとchecking Roleの
  agmsg spawnへ分離した。
- `docs/ai/context/operations/agent-messaging.md`: local teamをCoordinator / Reviewer / Tester /
  Auditorへ現行化し、Implementerを対象外と明記。spawn例をchecking Role用へ限定した。
- `docs/ai/adr/012-role-model-effort-defaults.md`: model / effort値は維持し、Implementerの指定方法を
  native delegationへ変更した。
- `docs/ai/status.md`: 存在しないImplementer monitor確認を削除し、現行体制とdry_run案件で確認済みの
  Codex権限範囲へ更新した。

`new-session.sh`は現状でCoordinatorとchecking Role 3体だけをtmuxへ起動し、コメントでも
Implementerを非residentとしているため変更していない。agmsg本体・team・機能コードも変更していない。

## 自己検証

- `python3 scripts/check-doc-consistency.py`: 3 checks rc=0。
- `git diff --check`: rc=0。
- 現行規範に対する旧経路語の検索では、ヒットは「native Implementerはagmsg対象外」と述べる
  新しい否定文だけであり、agmsg経由 / monitor対象とする断定は0件。

## Reviewer差し戻し対応

- `agent-messaging.md` §7に残っていた移行前の`claude`識別子を除去し、`homelab` /
  `homelab-ops`とも`coordinator`を使う現行状態へ統一した。
- `team.sh homelab`で旧`implementer`登録が残っていることを確認した。active identity表を
  登録roster全体ではなくlauncherが使う経路として明示し、旧登録は存在するが起動・依頼・返信に
  使わないと記録した。team登録の変更は非ゴールのまま維持した。
- 上記の事実に合わせ、requirement P0-2 / AC2を「登録の不在」ではなく「登録とactive経路を
  区別できること」へ明確化した。Implementerをagmsgで使わないゴールは変更していない。

## 未実施

- commit / pushは未実施。Reviewerによる規範レビューは`2026-09-09_004_review.md`で差し戻し、
  対応後の`2026-09-09_005_rereview.md`でApproveまで完了した。

## 計画外事象

最終旧語掃引の検索パターンをダブルクォートでshellへ渡し、バッククォート内の3語をコマンドとして
実行した。2語はnot found、Claude Codeは入力不足で終了し、直後の`git status`で想定外のrepo変更が
無いことを確認した。2026-09-08の同型Incidentの再発であるため、両事例を
`docs/ai/memory/lessons/shell-search-patterns-must-not-be-evaluated.md`へ昇格した。
