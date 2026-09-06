# Incident: Coordinatorがsubagent走行中にrepoを編集した

日付: 2026-09-07
状態: 解決済み
対象: Semaphore upgrade native check mode案件 / Coordinator工程
種別: 未遂
原因分類: #運用考慮ミス

## 症状

Reviewerが限定再確認を実行中に、Coordinatorが別件のIncidentファイルをrepoへ追加した。`docs/ai/roles/coordinator.md`は、対象パスが重ならなくても、走行中のsubagentがある間はrepoを編集しないと定めている。

Reviewerは返却直前の`git status`で、自分が作成していない新規Incidentを検出して申告した。編集先はReviewer成果物と重ならず、実装diffも変わらなかったため、実際のマージ競合や判定の混入は起きなかった。

## 原因

Coordinatorが`subagent-briefing`の「並行作業では書込先を分ける」という条件を、Coordinator自身にも別パス編集を許す条件だと誤って適用した。より強いCoordinator固有規則である「subagent走行中はrepoを編集しない」を優先しなかった。

## 修正内容

- 走行中だったReviewerとTesterが完了してidleになったことを各tmux paneと完了報告で確認してから、以降のCoordinator編集を再開した。
- 当該Incident追加をReviewerの成果物・実装diffから分離し、Reviewer自身も対象外変更として明示した。
- 次のAuditor起動後はrepoを編集せず、返却を待ってから条件付き指摘の反映要否を判断する。

## 確認方法

- Reviewer・Tester・Implementerの全paneが完了表示で入力待ちになっていることを確認した。
- Reviewerの最終報告が、実装ファイルを変更しておらず、追加Incidentを自分の成果物として扱っていないことを確認した。
- `git diff --check`と対象diffの最終確認は、Coordinator文書更新完了後・Auditor起動前に改めて行う。
