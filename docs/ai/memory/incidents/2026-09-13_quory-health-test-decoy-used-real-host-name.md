# Incident: quory月次ヘルス検証のdecoy inventoryに実ホスト名を使用

日付: 2026-09-13
状態: 解決済み
対象: playbooks/quory_health_monthly.yml のTester検証
種別: 未遂
原因分類: #テスト不足

## 症状

初版の`docs/ai/reviews/quory_health_monthly/2026-09-13_010_test_plan.md`は実ホスト名を含まないinventoryを約束した。一方、初版`2026-09-13_011_test_result.md`は`control_nodes`に実ホスト名`quory`を置き、`ansible_connection: local`でplaybookを実行したと記録した。これは`docs/ai/core.md`のdecoy条件1「実host名・実IPを書かない」と両立しない。さらに`check-mode-native`なのにTesterが`--check`なしでcollect/replayを実行し、`docs/ai/policies/ansible_test_safety_policy.md` TS-023/024に反した。初版結果はこれらをdecoyと呼び、AC5をPASSとしていた。

Testerの再調査では、Ansibleのtransportはlocalで実行環境自身へ接続し、`/tmp`のfake sudoは渡されたshell commandを実行していた。無効な通常実行は`/tmp`へJSON/Markdown等を保存した。一時inventory・ラッパー・report・baseline・lockは残存する。ログとコードから実quory・本番Notion/Slack/Semaphoreへの接続・副作用は確認されなかったが、外部readbackによる完全な否定はしていない。

## 原因

playbookの入口は`groups['control_nodes'] == ['quory']`を必須とするため、実ホスト名を含まない適法なdecoy inventoryではfull-playbookを完走できない。この制約を初版テスト計画に反映せず、ローカルtransportならdecoyになると誤認して実ホスト名入りinventoryを作成した。通常collect/replayについては通知抑止・local実行を`--check`必須の代わりと誤認した。

## 修正内容

テスト計画と結果を訂正し、境界違反の実行をPASS根拠から外した。AC2〜AC4はfixture限定PASS、AC5はPartial、AC1/AC6とfull-playbook統合はNot Runとした。無効な実行は再試行しない。

## 確認方法

`2026-09-13_010_test_plan.md`と`2026-09-13_011_test_result.md`のdecoy定義、実行記録、AC判定を`docs/ai/core.md`およびTS-023/024と照合した。実環境のreadbackは配備工程へ残す。
