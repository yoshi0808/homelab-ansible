# Incident: 受入工程でcheck-mode fixtureを`--check`なしで起動した

日付: 2026-09-07
状態: 解決済み
対象: `roles/semaphore_upgrade/files/test_native_check_mode.yml` / Reviewer・Tester工程
種別: 未遂
原因分類: #要件定義ミス #運用考慮ミス

## 症状

`semaphore_upgrade`の受入工程で、fixture自身のcheck-mode必須assertを実測する目的で、TesterとReviewerがそれぞれ`ansible-playbook roles/semaphore_upgrade/files/test_native_check_mode.yml`を`--check`なしで起動した。`check-mode-native`を`--check`なしで実行しないというTS-023に、fixture検証を例外とする規定はない。

どちらもfixture先頭のassertが`ok=0`、rc=2で停止したため、fixture準備、role診断、通常upgrade/rollback、通知には到達せず、実害はなかった。最初の逸脱を記録した後にも別Reviewerが同じ実行を行っており、個人の判断ではなく依頼と工程設計の問題として扱う。

## 原因

CoordinatorがTesterへの依頼に「fixture check無し拒否」を検証項目として含め、Reviewerへの再確認でもcheck-only fail-closedの実測と静的確認を明確に分けなかった。このため、複数Roleが「`--check`なしを拒否するguardの実測」をTS-023より優先できるテスト上の例外だと解釈した。加えてfixtureは`playbooks/`配下ではないため、playbook headerのtester-gateを対象にする安全機構ではこの直接起動を拒否できなかった。

## 修正内容

- 当該2実行を受入判定の根拠から除外し、Reviewer・Tester記録へ訂正を追記した。
- check-mode必須の確認根拠を、fixture先頭assertの静的テストと、安全wrapper自身の`--check`欠落拒否へ限定した。
- 以後のfixture実行を`--check`付きかつ安全wrapper経由に限定し、追加コマンドを停止した。

## 確認方法

- 当該2実行のPLAY RECAPが`ok=0`、`changed=0`、`failed=1`で、先頭assert以外へ到達していないことをReviewer・Tester記録で確認した。
- ansyのbackup/work root、result file、Semaphore DB、通知marker、service MainPIDの前後比較が一致し、状態変更がないことを別の`--check`検証で確認した。
- その後の受入マトリクス12回は、他agent停止後に直列化し、すべて安全wrapperと`--check`を使用して完了した。
