# Incident: Semaphore upgrade の独自 dry_run が rollback を停止しない

日付: 2026-09-06
状態: 解決済み
対象: `playbooks/semaphore_upgrade.yml` / `roles/semaphore_upgrade/`
種別: 未遂
原因分類: #要件定義ミス #製造ミス #テスト不足

## 症状

`roles/semaphore_upgrade/tasks/main.yml` は `dry_run` の指定を必須にする一方、
rollback の task include は `ansible_check_mode` と `rollback` だけで判定している。
`semaphore_upgrade_dry_run` は upgrade 経路でしか参照されない。このため Semaphore
UI 自身の Dry Run がオフであれば、rollback template の Survey Variables で
`dry_run=true` を指定しても実 rollback の準備・起動へ進む。

本番でこの組み合わせを実行した事実は確認していない。コード調査中に検出した。

## 原因

独自`dry_run`をrole入口で必須化していた一方、mode分岐は`rollback`と
`ansible_check_mode`だけで決まり、独自値をupgrade側の末尾gateでしか消費して
いなかった。Surveyに同名の値が存在することを「全modeを止める安全条件」と扱い、
rollbackと`dry_run=true`の組合せを受入条件・fixtureに持たなかった。

## 修正内容

- 独自`dry_run`をmode selectorから削除し、Semaphore UI Dry Run / CLI
  `--check`の`ansible_check_mode`へ一本化した。
- 旧`dry_run`が値によらず指定された場合は、role先頭で移行方法を示して拒否する
  fail-closed guardへ置き換えた。
- upgrade/rollbackともread-only診断を通常変更処理から分離し、変更側includeを
  `not ansible_check_mode`と`destructive` tagで隔離した。
- apply/rollback templateのSurvey Variablesから`dry_run`を削除した。

## 確認方法

- decoyで`dry_run=true`/`false`の双方が診断前にrc非ゼロとなることを確認した。
- localhost fixtureでupgrade/rollback × reading path available/unavailableの4経路を
  3周、計12回直列実行し、すべてnative `--check`でrc=0、変更側include未到達、
  禁止path不在、backup generation不増加を確認した。
- ansy自身に対する安全wrapper経由のupgrade/rollback `--check`で、DB、backup/work
  root、result/marker、service MainPIDが前後一致することを確認した。
- 2名の独立Reviewerが最終差分をApproveし、通常upgrade/rollbackの実行経路と変数
  解決を静的に照合した。実templateからSurveyが消える実観測はcatalog reconcile後に
  quory側で行う。
