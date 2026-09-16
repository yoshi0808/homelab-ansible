# Phase 2 implementation: semaphore_reconcile_daily_sync

実装日: 2026-09-16
対象: requirement §5 P0-5〜P0-15 / §6 AC9〜AC19
改訂: 2026-09-16(差分レビュー `_013_diff_review.md` Critical 1 / Major 1 / Suggestion 2 / dead code 1、および受入検証 `_015_test_result.md` Critical 1 / Minor 2 を反映)

## 実装結果

- canonical接続先では既存scheduleの`active`をdiff対象から除き、PUT直前のfresh GET値をpayloadとverifyへ使う。新規scheduleはカタログ値を使う。非canonical接続先では新規・既存とも`active: false`を実効値とし、更新payloadとverifyを揃えた。
- template / schedule双方のwrite-setをtemplate apply前に計画し、更新合算上限4件を判定する。新規template参照は計画時だけ仮IDで解決し、POST後の通常readで実IDに置き換える。解決不能参照は書き込み前に失敗する。
- runごとの不変reportと成功markerを分離し、report公開後にのみmarkerを原子的に差し替える。失敗回はmarkerを更新しない。通知は既存common_slack経路へ固定情報だけを渡す。
- orphan baseline差分、金曜(JST)のinactive一覧、latest-successの24時間鮮度findingを追加した。`semaphore_template` findingは撤去し、probe errorとchecked countは維持した。
- canonical URLはfilter pluginの定数を唯一の正本とし、Ansible variableをdefaultsと外部設定allowlistから撤去した。System Context 2文書のactive契約も更新した。
- 差分レビュー後、最終schedule diffに対する更新合算上限の再検証を追加し、非canonical PUTでは実際に送るpayloadの`active is false`を直前assertするようにした。接続先URL欠落は非canonicalへ倒す。token-scrub済みの失敗詳細は診断情報として再送出・schedule reportへ戻し、System Contextへ「EXEC-052の到達不能からschedule非発火は導けない」を追記した。
- 受入検証後、canonical URLは定数との完全一致、証明書検証値は文字列`"true"`のみをenvironment preflightで受理するよう制約した。run report / latest-successの成功publish後に一時ファイルをbest-effort削除し、stale findingは経過秒数か判定不能理由を`actual`へ出す。

## ACと検証の対応

| AC | 対応する実装・テスト | 状態 / 未確認事項 |
|---|---|---|
| AC9 | `test_desired_and_diff.py`のcanonical既存active保持、`schedules_apply_item.yml`のfresh GET→payload→verify分岐 | filter fixtureは通過。APIのGET/PUT競合を含むreadbackはTesterへ回す |
| AC9a | 同fixtureのactive単独差分0件ケース、`schedules_diff.yml`のchanged計算 | fixtureで確認済み |
| AC9b | fresh inactiveを保持するfixture、apply itemのverify対象 | filter fixtureは通過。API書込み後のreadbackはTesterへ回す |
| AC10 | `test_phase2_helpers.py`の金曜JST/停止あり・なし/金曜以外の分岐 | fixtureで確認済み。common_slackの実include/evidence/送信はTesterへ回す |
| AC11 | `test_phase2_helpers.py`の4件許可、templateのみ5件、scheduleのみ5件、混在5件、明示override。`main.yml`は`schedules_plan.yml`をtemplate apply前に実行。scenario Iは実際のplan filterで4件を許可後、最終diff 5件を作って実際の`schedules_update_cap_final.yml`をimport | 計画時上限内・最終diff超過のtask-flowで非ゼロ停止を確認。最終検査はtemplate apply後のため、その場合はtemplate適用済みとなりrun reportはpartialを記録する。事前のtemplate-only書込み防止は既存上限task-flowで確認 |
| AC11a | pending template用仮IDでschedule preflightが通るfixture。実装ではtemplate apply後に通常のschedule readで実IDを解決 | 仮ID計画はfixtureで確認済み。POST→実ID紐付けと超過時双方ゼロのAPI統合確認はTesterへ回す |
| AC12 | `reconcile_finalize.yml`のnotify条件と成功時のrun report/marker分岐 | **該当するfixtureなし（Testerへ回す）**。通知なし・両成果物更新の実行確認が必要 |
| AC13 | `reconcile_finalize.yml`のfailure/partial判定、report・marker publish順と失敗rescue | 7ケースを実行するfixtureなし（Testerへ回す）。evidence/Slack失敗を含む状態表の実証は未実施 |
| AC13a | marker失敗rescueは旧markerを保持し、report成功を維持して最後に非ゼロ終了する構造 | **該当する故障注入fixtureなし（Testerへ回す）**。鮮度findingとの連携確認も未実施 |
| AC13b | `reconcile_finalize.yml`でrun reportを先に原子的publishし、その後markerをpublish | task順は確認済み。実ファイル故障注入でのmarker参照整合fixtureなし（Testerへ回す） |
| AC14 | `main.yml`のtoken-scrub済み失敗詳細の再送出、`schedules_report.yml`のscrub済み`failed_msg`、finalizer通知 | raw token/API失敗値を使わず、既存のscrub済み診断文を維持。fixture全体でのAPI失敗各出力面横断確認はなし（Testerへ回す） |
| AC15 | `test_phase2_helpers.py`の正規化key、追加/除去/同数入替/重複/並び順/不正baseline | fixtureで確認済み |
| AC16 | `test_phase2_helpers.py`の20h40 fresh、24h/44h40 stale、欠落/非通常ファイル/不正JSON/未来時刻 | helper fixtureで確認済み。stat/slurp実タスクの権限・読取失敗fixtureなし（Testerへ回す） |
| AC17 | `roles/deployment_drift_check/tasks/semaphore_probe.yml`でtemplate findingを削除し、probe error/countを維持、staleを追加 | task分岐を確認。deployment_drift_check role全体のfixtureなし（Testerへ回す） |
| AC18 | P0-14のカタログ行を追加。Coordinatorから転送されたTester観測では、schedule起動taskのenvironmentへsurvey既定値はマージされず、カタログ外template参照は作成・readback可能。`CurrentCatalogPreflightTests.test_every_checked_in_schedule_catalog_entry_passes_preflight`で現行全カタログを`semaphore_schedules_preflight` | bootstrapの2値は固定許可契約で受理し、他URL/`validate_certs`値は拒否。現行25行のカタログfixtureでerrors=0を確認。新schedule API readbackと初回04:00 runは未実施（Yoshinobuの操作待ち） |
| AC19 | `test_desired_and_diff.py`のcanonical/noncanonical active実効値、`test_phase2_helpers.py`のcanonical environment値、task-flow scenario Hのretired `-e`拒否と通常設定通過。`schedules_apply_item.yml`はPUT bodyを先にfreezeし、非canonical時にそのpayloadの`active is false`をassert | fixtureで確認済み。ansy APIの6ケースreadbackは実施せずTesterへ回す |

## 自己検証

- `python3 scripts/tests/semaphore_schedules/run-tests.py -v`: 136 tests passed。
- `python3 -m unittest discover -s scripts/tests/semaphore_schedules -p test_phase2_helpers.py -v`: 20 tests passed。`test_every_checked_in_schedule_catalog_entry_passes_preflight`は現行25行のschedule catalogをsynthetic observed schedule/templateとともに`semaphore_schedules_preflight`へ通し、errors=0を確認。
- Catalog count check output: `current schedule catalog entries: 25`。
- `python3 roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py`: 9 scenarios passed。scenario Iで事前planは上限内、template apply後の最終diffが5件となるfixtureを使い、実際の最終上限assertが停止することを確認。
- `ansible-playbook --syntax-check playbooks/semaphore_templates_setup.yml`: passed。
- `ansible-lint --profile min`を今回変更したrole task/defaults/test-flowファイルへ実行: passed (production profileも通過)。
- 一時ファイル cleanup のtask構造テスト: 両atomic publish後に対応する`.tmp`を`state: absent`で削除する順序と、cleanup失敗をrun結果へ波及させない設定を確認。鮮度formatter fixtureでは24h staleが`86400 seconds`、marker欠落が理由文字列となることを確認。
- リポジトリ全体の`ansible-lint --profile min`は失敗。今回の修正箇所ではない既存playbookの未定義`target_node`、他roleにある`common_slack`等の相対role path欠落に加え、初回実行時はこの実装の`include_tasks`へ不正な`failed_when`を付けた構文エラーも検出した。実装側の構文エラーを修正後、playbook syntax-checkと対象task lintは通過した。全体lintの残件は引き続きrepository baselineとして残る。
- 実ホスト、Semaphore API、ansy Semaphoreへ接続していない。Slack通知も送信していない。

## 判断・残件

P0-14の値はCoordinatorから転送されたTester観測に従った。なお、観測taskはSSH到達不能で終わり、Ansible role defaultへのフォールバック有無は未確認だが、catalog行は明示environmentを渡すためその挙動に依存しない。ansy bootstrap templateの数値IDは環境固有のため実装へ書き込まず、名前解決を維持した。AC12〜AC14等の故障注入・実API readbackは上表のとおりTesterへ回す。

最終schedule diffで上限超過を検出する時点ではtemplate applyが完了済みであり、template-onlyの部分適用は起こり得る。この再検証が保証するのは、超過を検出した後にscheduleを書き込まないことと、部分適用をreport上で観測できることである。事前計画の上限判定も維持し、計画段階の超過では両資源の書き込み前に停止する。

更新上限が保護するのはwrite-setが機械的に膨張した場合であり、単独のcron typoは件数で識別できない。**一つの人手cron typoはcommit reviewでのみ保護される。**
