# 月次ストレージ点検 retest_result(009再現条件 + 008未実施D1〜D8 + 007指摘の再検証)

対象: 006実装記録以降の現在の差分(locale修正、`test_scan_timestamp_ignores_process_locale` / `test_actual_report_suppression_expression` / `test_prune_boundaries_and_protection` / `test_token_file_defenses`の追加、`roles/semaphore_templates/defaults/main.yml`のcatalog/schedule追加)。008計画のD1〜D8はすべて`/tmp`scratchで実施し、検証後に削除した。実ホスト・quory・本番Notion/Slackへは一切接続していない。すべての通常実行に`skip_notifications=true`を付与した。

## 009再現条件(locale依存バグ)の再現性確認

- 現在のシェルlocale(`LANG=ja_JP.UTF-8`)で`python3 -m unittest discover -s tests -p test_storage_monthly.py -v`: **15件成功**(009時点の11件から新規4件増、うち1件が今回のlocale回帰テスト)。
- `LC_ALL=C.UTF-8 LANG=C.UTF-8`(英語UTF-8ロケール)でも同スイート: **15件成功**。
- `LC_ALL=C LANG=C`(非UTF-8)はAnsible自体が`Ansible requires the locale encoding to be UTF-8`で拒否するため対象外(Ansibleの一般要件であり本件の欠陥ではない)。
- `roles/proxmox_storage_monthly/module_utils/storage_monthly.py`の`scan_timestamp()`が`datetime.strptime`の`%a`/`%b`をやめ、固定の英語月名テーブルと正規表現で解析する実装に変わっていることを確認した。**Verdict: 009の欠陥は解消。日本語ロケール下でのcollection失敗を再現できなくなった。**

## D1〜D8(008計画の未実施分、fixture/decoyで独立実施)

すべて`/tmp`のscratch inventory・report dirを使用し、既存`tests/test_storage_monthly.py`の手法(hostvarへ`storage_monthly_observation`を直接注入し`--limit localhost`で`storage_monthly_targets`play自体を起こさない)を踏襲した箇所と、実際のloopback閉ポート/`ansible_connection: local`decoyで`storage_monthly_targets`playを本当に実行させた箇所の両方を用いた。

| ID | 対象AC | 方法 | 結果 |
|---|---|---|---|
| D1 | AC2/AC7 | 同月内で239→240の2回実行(hostvar注入) | PASS: 2回目の`comparison=compared`、`delta.num_err_log_entries=1`、`comparison_source`が1回目のreport_idを指す。月baselineは1回目の239のまま固定(health WARNING/OK含め仕様どおり) |
| D2 | AC5 | (a)`proxmox`グループに実到達不能host(`ansible_port:1`のloopback閉ポート、真のUNREACHABLE)+`ansible_connection:local`hostの実playを両方通す。(b)hostvar注入で1台ok/1台未注入の混在 | PASS: (a)両host個別に`collection error`が記録され最終rc=2。(b)`ok-fixture`は`collection:ok`でdeviceを保持、`missing-fixture`は`collection:error`のまま、全体`collection:error`→最終assert失敗でrc=2(片方OKを全体OKにしない) |
| D3 | AC3 | 月baseline(`2026-09.baseline.json`)を不正JSONへ破損させて再実行 | PASS: `history_error:true`、対象deviceの`comparison:history_corrupt`、`health:UNKNOWN`、最終rc=2。壊れたbaselineファイルは書き換えられず、既存reportファイルも保全されたまま(件数が減らない) |
| D4 | AC3 | 同月内でserial違いのdeviceを2回目に投入(独立python呼出、`archive.archive()`を2回) | PASS: `comparison:replacement_or_added`、`issues`に`device replacement/addition`のWARNING |
| D5 | AC4 | `zfs()`へDEGRADED pool、READ/WRITE/CKSUM非ゼロ、`errors: N data errors`、scrub in progress、`none requested`の5バリエーションを直接投入 | PASS: 状態/IOエラー/データエラーはCRITICAL、進行中・履歴なしはWARNINGに正しく分類 |
| D6 | AC6 | `storage_notion.publish()`を独立呼出。既存より新しい`collected_at`で先に公開後、古い`collected_at`のreportで再送 | PASS: `PublishError: older_report_refused`で拒否、POST回数は増えない |
| D7 | AC8 | `tasks/report.yml`から`suppress:`のJinja式を実ファイルからYAML解析で抽出し、独立の使い捨てplaybook(検証後削除)で4通り(skip+force+check=false/skip=false・force=false・claudecode設定/force=trueで解除/slack_force_sendが無関係)をassert | PASS: 抽出した式は要件どおり — `skip_notifications`/`ansible_check_mode`はforceで解除不可、AIセッション検出単独はforce trueで解除可、`slack_force_send`は無関係 |
| D8 | AC9 | report_dirのパーミッションを000にして実行 | PASS: `storage_archive`が静的メッセージ(`Storage report archive failed; inspect local storage and schema`、実データ非含有)で`fail_json`、rescueで`_storage_pipeline_error`、最終rc=2。ディレクトリ内にファイルは残らない(部分書込みなし) |

### 追加: 保持削除(prune)の独立fixture(007 Major #2 / coordinator追加依頼)

既存の`test_prune_boundaries_and_protection`(15件中に含まれ独立再実行済み、PASS)とは別に、独立構成で再確認した。13か月境界を跨ぐ2件の同月古いreportのうち、月baselineの`comparison_source`が参照する1件は保護され削除されず、参照されないもう1件は削除されることを確認した(`/tmp`scratchのみ、削除は本Testerが作った使い捨てfixtureに対してのみ実施)。

### 007指摘の再検証(実装側テスト・独立確認の両方)

- Major #1(抑止式の未検証): 新規`test_actual_report_suppression_expression`は`tasks/report.yml`を`yaml.safe_load`で読み実際の`suppress:`式を抽出し、`ansible_check_mode`×`skip`×`force`×`slack_force_send`×AIセッション検出の全組合せ(128通り)を実`ansible-playbook`で評価する設計であることをコードで確認し、独立再実行(15件中)でPASS。上記D7で別実装の抽出・検証でも同じ結論を得た。**Verdict: 解消。**
- Major #2(prune未検証): 新規`test_prune_boundaries_and_protection`は7分岐(削除対象/境界/直近/baseline保護/未公開/symlink/directory)を持ち、独立再実行でPASS。上記の独立追加fixtureでも同じ挙動を確認した。**Verdict: 解消。**
- Suggestion(token defenses): 新規`test_token_file_defenses`(不正パーミッション/symlink/空token)を独立再実行しPASS。

## 静的検証(独立再実行)

- `ansible-playbook playbooks/proxmox_storage_monthly.yml --syntax-check`: rc0(動的group未定義警告のみ、想定どおり)。
- `bash scripts/check-tester-gate.sh`: 61 playbook OK。
- `git diff --check`: rc0。
- `python3 scripts/check-doc-consistency.py`: 3チェックともOK。

## 未確認事項(範囲外/Not Run)

- `roles/semaphore_templates/defaults/main.yml`へのcatalog/schedule追加(今回diffに新規出現)は、`active: false`・cron `0 8 15 * *`・survey enum(`collect`/`replay`)の記載内容を目視確認したのみで、実Semaphoreへの反映・readbackはTester権限外・quory未接続のためNot Run(AC10はYoshinobuのSemaphore起動後の担当)。
- 実pve1/pve2の`zpool status -P -p`/`nvme`実出力との一致(007 Suggestion #2)は実ホスト調査でありNot Run。
- 実Notion API疎通、実Slack送信は権限外でありNot Run(すべてfixture/decoyのみ)。

## Verdict

**PASS(009の欠陥は解消、007 Major #1/#2は解消、008計画D1〜D8はすべて独立再実施でPASS)。** 対象実装は無変更。使い捨てplaybook・fixtureは`/tmp`に閉じ、検証後にすべて削除した。
