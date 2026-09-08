# Incident: 新operation keyをschedule preflightが拒否した

日付: 2026-09-09
状態: 解決済み
対象: `roles/semaphore_templates` / Semaphore template catalog reconcile job #1027
種別: 未遂
原因分類: #製造ミス #テスト不足

## 症状

commit `ba98063`配備後のSemaphore template catalog reconcileをnative Dry Runで実行したところ、
template 5件の期待差分を検出した後、schedule preflightが
`ubuntu_vm_full_upgrade_operation`と`prometheus_update_check_operation`を許可されていない
environment keyとして拒否し、job #1027がrc非ゼロで終了した。preflightが書き込み前に
fail-closedしたため、template / schedule APIへの変更は発行されていない。

## 原因

schedule catalogへ2つのnamespaced operation keyを追加した際、同じ値を消費する
`roles/semaphore_templates/filter_plugins/semaphore_schedules.py`のclosed-world environment
key allowlistを更新しなかった。静的catalog shape testはcatalog自身だけを検査し、実際の
schedule preflightへ新しい2 scheduleを入力するconsumer-path testが無かったため、reviewと
localhost testを通過した。

## 修正内容

schedule preflightのenvironment許可契約へ2つのnamespaced operation keyを追加した。
Ubuntuは`inspect|apply`、Prometheusは`inspect|update|rollback`だけを許可し、enum外の値を
fail-closedする。Semaphore native `params`側は従来の許可keyだけを維持し、operation keyの
混入を拒否する。job #1027相当の既存schedule 2件をpreflightからdiffまで通す回帰testと、
未知operation・未知key・軸混入の拒否testを追加した。

## 確認方法

`python3 scripts/tests/semaphore_schedules/run-tests.py`で97 tests、既存task-flow 6 scenarios、
Python構文、doc consistency、`git diff --check`がすべてrc=0となった。別体Reviewerも公開
preflight出力を公開diffへ渡すconsumer pathを確認し、追加のcross-enum・非文字列・native
`params`混入spot-checkを含めてコードとtestを適合と判定した。

commit `33bc03b`配備後、job #1028のnative Dry Runがrc=0となり、template 5件・schedule
2件だけをin-place変更として検出した。job #1029の通常実行で5件・2件を適用し、schedule
2件はPUT直後GETのexact verifyを通過した。forced commandのtemplate API readbackでも5件すべてが
対応するoperation enumを持ち、旧`dry_run` Surveyを持たないことを確認した。job #1030 / #1031の
通常inspectionはrc=0で、変更経路をskipしSlack送信に成功した。
