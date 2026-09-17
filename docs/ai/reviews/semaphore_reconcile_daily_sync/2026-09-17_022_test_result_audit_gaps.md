# Test Result: Audit `_020` が指摘した4項目の実測埋め

対象: `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-17_020_audit.md` の指摘のうち
「受入条件の充足」に分類された4項目(AC10 / AC13残り5ケース / AC14残り / AC17の
`semaphore_probe_error`分岐)。requirement正本は `2026-09-15_001_requirement.md` §6(AC)・
`P0-8a`(§7.2の失敗時状態表)。

**本記録は独立した検証である。** `_015` / `_017` の判定を確認せずに引き継がず、対象コード
(`roles/semaphore_templates/`, `roles/deployment_drift_check/tasks/semaphore_probe.yml`,
`roles/common_slack/tasks/notify.yml`)を自分で読み、実機(ansyのSemaphore、project id=3)で
再現できるものはすべて自分で実行して確認した。`_015`/`_017`の主張のうち、本記録が現物で
再確認しなかった部分(AC9/AC9a/AC9bのfixture代替、AC11/AC11a/AC19、AC13a/AC13bの
latest-success publish失敗ケース)は対象外(依頼のscope外)であり、本記録では判定を出さない
(前回の判定をそのまま引き継ぐわけではなく、単に対象外)。

## 0. 検証環境と安全条件

- 使用したのは ansy のSemaphore(`https://localhost:3000`、project id=3)のみ。quory・本番
  ホストへは一切接続していない。
- role実行はすべて `ansible-playbook` を直接起動する形で行い、Semaphoreの「タスク」としては
  一度も起動していない(§6で開始時・終了時の `GET /project/3/tasks` の件数・max idの一致を
  確認)。
- 接続は `-e ansible_connection=local`(inventory既定の `id_ann` は2026-08-19に削除済みで
  到達不能なため、既存Testerと同じ代替)。
- token: `~/.semaphore-api-token-ansy`(直接API呼び出し確認用、値は出力・記録していない)。
  role本体は `/etc/homelab-recovery/semaphore-templates-api-token` を読む(AC14のtoken
  読取不能ケースでは `-e semaphore_templates_token_path=/nonexistent/...` で代替した)。
- report_dir は毎回 `/tmp` 配下の書き込み可能なpathへ `-e` で上書きした(既定値は
  `ann` 所有でありyoshi実行では書けない)。
- **本番Slackへは一度も到達していない。** 本セッションはClaude Code(`CLAUDECODE`環境変数)
  であり、`roles/common_slack/tasks/notify.yml` のtrigger3(AIエージェントセッション検出)が
  既定で送信を抑止する(`[suppressed]` メッセージで確認)。Slack送信そのものを実測する必要が
  あった1件(§3「evidence生成失敗 / Slack送信失敗」)だけは `slack_force_send=true` と
  併せて `slack_webhook_alerts` をループバックの閉ポート(`https://127.0.0.1:9/...`)へ
  `-e` で上書きし、**本番Webhookへは一度も送っていない**(decoy技法、`docs/ai/core.md`の
  decoy inventoryと同じ原理をwebhook URLへ適用したもの)。
- API到達不能を作る箇所(AC14/AC17)も同様に `semaphore_templates_api_base_url` を
  ループバックの閉ポート(`https://127.0.0.1:9/api`)へ `-e` で上書きした。実ホスト・実DNS名は
  一切使っていない。
- 検証用に作成したSemaphoreオブジェクトは全て `ZZ-TEST:` prefixを付け、検証後に自分で
  削除した(§6)。
- 変更したのは本ファイル1つのみ。実装(`roles/`, `filter_plugins/`)は一切変更していない。

## 1. AC10(金曜の停止一覧)

**要求**: 金曜(Asia/Tokyo)・停止1件以上→一覧通知。金曜・停止0件→通知しない。金曜以外・
停止1件以上でも一覧を出さない。

### 1.1 実行時に曜日を固定する手段の有無(調査結果)

`roles/semaphore_templates/tasks/schedules_friday.yml` は
`semaphore_schedules_observed | semaphore_schedules_friday_paused` を無引数で呼ぶ。
filter本体 `semaphore_schedules_friday_paused(observed_schedules, now_iso=None)`
(`roles/semaphore_templates/filter_plugins/semaphore_schedules.py:670-676`)は第2引数
`now_iso` を受け付けるが、**呼び出し側のtaskはこれを渡していない** — playbook実行時に
`-e` で曜日を差し替える経路は実装に無い。

`-e semaphore_schedules_friday_paused=<値>` で直接この事実(=そのtaskがsetする変数)を
上書きする案も試したが、**`schedules_validate_config.yml` のreserved-name guardが
拒否した**(実測、`_021`以前には無い新発見):

```
以下の変数名が、schedule処理の一切のtaskが走る前から既に定義されています:
semaphore_schedules_friday_paused。これらはこの role が内部状態(失敗判定・レポート保存
結果など)として set_fact/register する名前であり、-e等の外部からの事前定義を許可しません
(査読r5 Critical #1)。許可される外部設定は semaphore_schedules_catalog /
semaphore_schedules_closed_world / semaphore_schedules_expected_timezone /
semaphore_schedules_report_dir の4つだけです。
```

つまり「実行時に曜日判定結果を差し替える」経路は**意図的に塞がれている**(reserved-name
guardの設計どおりで、欠陥ではない)。したがって、Friday分岐の完全なend-to-end観測は
「本物の金曜にこのplaybookを実行する」以外に手段が無い。**今日(2026-09-17)は木曜日**
(`TZ=Asia/Tokyo date` で確認)であり、本セッション中に金曜は来ない。

### 1.2 実測した内容(3層構成)

**(a) 曜日判定ロジック自体の直接実行(production moduleを直接import、fixtureではなく
実装コードそのもの)**:

```python
m.semaphore_schedules_friday_paused(observed, "2026-09-18T10:00:00+09:00")  # 金曜10:00 JST
# -> [{'name': 'SAFE: A', ...}, {'name': 'SEMI-SAFE: C', ...}]  (2件のactive:falseのみ抽出)
m.semaphore_schedules_friday_paused(all_active, "2026-09-18T10:00:00+09:00")  # 金曜・停止0件
# -> []
m.semaphore_schedules_friday_paused(observed, "2026-09-17T10:00:00+09:00")  # 木曜
# -> []
m.semaphore_schedules_friday_paused(observed, "2026-09-19T10:00:00+09:00")  # 土曜
# -> []
m.semaphore_schedules_friday_paused(observed, "2026-09-18T23:59:59+09:00")  # 金曜23:59:59
# -> 2件(境界内)
m.semaphore_schedules_friday_paused(observed, "2026-09-19T00:00:01+09:00")  # 土曜00:00:01
# -> []
m.semaphore_schedules_friday_paused(observed, "2026-09-17T16:00:00+00:00")  # UTC木16:00=JST金01:00
# -> 2件(UTC入力でもAsia/Tokyoへ正しく変換して金曜と判定)
```
すべて期待どおり。**曜日判定とactive:falseの抽出ロジック自体はPASS。**

**(b) 実機の非金曜での統合確認(本物の実行、fixtureではない)**: 今日(木曜)、実際に
`active: false` が25件存在する状態(ansyの全schedule)で `playbooks/semaphore_templates_setup.yml`
を通常実行し、run reportの `notification.triggers` に `friday-inactive-schedules` が
含まれないこと、`include_reached: false` であることを確認した(diffが無い回)。**「停止が
多数あっても金曜以外は一覧を出さない」を実機で確認した(PASS、fixtureではなく実測)。**

**(c) 金曜・停止ありの通知統合(未確認)**: 上記(a)+(b)の合成でしか裏付けられない。
`reconcile_finalize.yml` の消費側ロジック(`semaphore_schedules_friday_paused | default([])
| length > 0` で notify_required に加算し、メッセージへ `map(attribute='name') | join`)は
コードを読んで確認したが、**実際に非空のfriday_pausedを持った状態でreconcile_finalize.yml
まで到達させる実行はできなかった**(1.1のreserved-name guardのため)。

### 1.3 判定

| ケース | 判定 | 根拠 |
|---|---|---|
| 金曜・停止1件以上→一覧通知 | **未確認** | 曜日判定ロジック自体は(a)でPASS確認済みだが、その結果がnotifyへ実際に伝播することの統合確認は、実行時の曜日固定手段が無く(1.1)、次の金曜(2026-09-18)を待つ以外に安全な手段が無い |
| 金曜・停止0件→通知しない | **未確認** | 同上 |
| 金曜以外・停止1件以上→一覧を出さない | **PASS(実機)** | §1.2(b)、本物の木曜実行で確認 |

`_020`は「AC10の受入結果が無い」と指摘していたが、本記録により3ケースのうち1件は実機PASS、
残り2件は「なぜ実測できないか」を含めて未確認として明示した。**Coordinatorへの申し送り**:
2026-09-18(金)以降の最初のreconcile実行(手動またはschedule発火後)で、run reportの
`notification.triggers`に`friday-inactive-schedules`が現れるか、および現在の実物
`active:false`スケジュール数(quory側)を突き合わせて確認することを推奨する。

## 2. AC13の残り5ケース(P0-8a)

`_015`が示したのは「全成功・変更あり」と「latest-success publish失敗」の2行のみ。残る5行を
実機で確認した。

### 2.1 全成功・変更なし — **PASS(実機)**

実カタログを2回連続適用(1回目は`SEMI-SAFE: Semaphore reconcile daily`のbootstrap行が
未作成だったため1件のschedule createが発生=「全成功・変更あり」、2回目は完全に一致):

2回目のrun report:
```json
{"actual": {"schedules": {"creates": 0, "updates": 0}, "templates": {"creates": 0, "updates": 0}},
 "notification": {"include_reached": false, "triggers": []},
 "partial_application": {"writes_applied": 0}, "status": "success"}
```
`notify` include未到達(Slack系task列が"skipping")、`status: success`、run report保存済み、
`latest-success.json`のrun_idがこの回のrun_idと一致(marker更新を確認)。**表のとおり
(notify到達=しない/evidence=なし/Slack送信=なし/rc=0/run report=保存/latest-success=更新)。**

### 2.2 template途中失敗 — **PASS(実機、真のHTTP 400による部分適用)**

**手法**: `semaphore_templates_catalog`を3件の合成entry(`ZZ-TEST:`)へ`-e @file.json`で
差し替え、`semaphore_schedules_catalog: []`・`semaphore_schedules_closed_world: false`・
`semaphore_reconcile_max_creates: 5`を同時に上書き(schedule側を完全に無関係化し、template側
だけで部分失敗を起こすための隔離)。3件中1件(`playbook: ""`)は事前にcurlで実測確認した
とおりSemaphore APIが`HTTP 400 {"error":"template playbook can not be empty"}`で拒否する
組み合わせであり、**この値は role側のいずれのpreflight(`semaphore_templates_preflight`)
でも検査されない**(観測側の型検査のみで、catalog側のplaybook非空を見ない)ため、真の
API-levelな部分失敗を安全に作れる。

実測(実行順序は`semaphore_templates_diff.new`の内部順であり、catalog記載順とは一致しない
ことを確認した — 良い方の2件が先に成功し、悪い方が3番目に処理されて失敗した):
```json
{"planned": {"templates": {"creates": 3}}, "actual": {"templates": {"creates": 2}},
 "partial_application": {"failed_task": "Create templates that do not exist yet", "writes_applied": 2},
 "status": "partial",
 "notification": {"include_reached": true, "triggers": ["failure","writes-applied","orphan-set-changed"]}}
```
APIで実物を確認: 成功した2件(id=91,92)が存在し、失敗した1件は作成されていないことを
確認した。rc非ゼロ(fatal)。latest-successはこの回では触られていない(`when: not failed`で
gate、marker publishブロック自体がskip)。**表のとおり
(notify到達=する/evidence=生成試行/Slack送信=試行/rc=非ゼロ/run report=保存status=partial、
適用済み件数明記/latest-success=据え置き)。**

検証後、id=91・92を`DELETE`で削除済み(§6)。

### 2.3 schedule途中失敗 — **未確認(理由: 意図的な部分失敗を安全に作る手段が見つからなかった)**

template側と同じ手法(preflightを通過するがAPIが拒否する値)を探したが、schedule側の
preflightは著しく厳格で、次のすべてを事前に(書き込み前に)検出して停止することを実測で
確認した:

| 試した値 | 結果 |
|---|---|
| `name: ""` | curl直叩きではHTTP 201(APIは受理する)が、**role側の`schedules_readset_preflight`が「name が空/非文字列」として書き込み前に拒否**(実測、readset_preflight.yml経由) |
| 存在しないtemplate名を参照 | `semaphore_schedules_preflight`の③(template名解決)が「一致件数が0件」で書き込み前に拒否 |
| 不正なcron文字列(`"not-a-cron"`) | curl直叩きではHTTP 400だが、**role側`_cron_is_valid()`がpreflightの④で先に拒否**(cronのbounds検査まで実装されている) |
| 未知の`task_params`キー | ⑦のDLPアローリストが「判定できないものは停止」で拒否(そもそも許可されるキーは`force_renew`/`dry_run`/`debug_level`/`ubuntu_vm_full_upgrade_operation`/`prometheus_update_check_operation`と、今回追加された`environment`内2キーのみ) |
| `repository_id`を不正値に | curl直叩きではHTTP 400だが、**role自体がscheduleのPOST/PUTでこのフィールドを一切送らない**(`semaphore_schedules_create_payload`は5つの管理フィールドのみ)ため、catalogから注入する経路が無い |
| 巨大な`name`文字列 | curl直叩きでHTTP 201(APIが受理するため使えない) |

`semaphore_schedules_catalog=[]`にして空カタログで既存25件との整合を試したところ、
`semaphore_schedules_closed_world`(既定true)のとき「closed-world だが管理外 scheduleが
ある」で全既存schedule分のエラーが出て停止することも確認した(§2.2で`closed_world=false`
に切り替えて回避した理由)。

これらはいずれも「preflightが機能している」という**良い意味の結果**だが、結果として
「preflightを通過しつつAPI側だけが拒否する」schedule向けの合成値を見つけられなかった。
残る理論上の経路(closed-worldの「preflight時点からidentityが変化」= R8/AC22のTOCTOU
分岐、`schedules_apply_item.yml`の「Abort all remaining writes if identity changed since
preflight」)は、**単一のansible-playbook実行の最中に、別プロセスから対象scheduleを削除する
タイミング攻撃でしか再現できない**。これは実行結果を制御できない競合状態であり、
再現性のある実測記録にならないと判断し、あえて実行しなかった(核心は「再現できない」
ではなく「再現させようとするとレース依存になり、記録として信頼できない」)。

**未確認。理由: 実装の入力検証(preflight ①〜⑦・readset_preflight)がAC13の対象とする
「preflightを通過した後のAPI拒否」を許す入力を、templateほど容易に構成できなかった。
これは欠陥ではなくpreflightの堅牢性の証拠として記録する。**

### 2.4 run report保存失敗 — **PASS(実機)**

`reconcile_dir`をあらかじめ`mode 555`(書き込み不可)にして通常のカタログで実行:
```json
"message": "Semaphore reconcile completed with an artifact publish failure. run_id=...; report_save_failed=True; latest_success_publish_failed=False."
```
rc非ゼロ(fatal、"Return non-zero when a required reconcile artifact could not be
published")。`reconcile/`ディレクトリの中身は空のまま(run report自体が保存されなかった
ことを確認)。latest-successの書き込みタスクは`when: not report_save_failed`でgateされ
「skipping」(据え置き、というより「触られてすらいない」)。**表のとおり(notify到達=する/
evidence=生成試行/Slack送信=試行/rc=非ゼロ/run report=無し/latest-success=据え置き)。**

### 2.5 evidence生成失敗 / Slack送信失敗 — **PASS(実機、2つを分けて確認)**

**evidence(`capture.yml`)**: 本セッションの全実行を通じて、`capture.yml`内の実タスク
(spool dir解決・作成・書き込み)は毎回「skipping」だった。原因はコードコメント
(`capture.yml`)が明記する「収集器の設定ファイルの存在」ゲートであり、ansyにはこの設定
ファイルが無いため常にno-opになる(**能動的に故障を注入したのではなく、この環境では
構造的に毎回そうなる**という違いを明記する)。この状態でも通知本文の生成やrcには一切
影響しないことを、本記録の他のすべての実行(rc=0の回・rc非ゼロの回の両方)で確認した。
`capture.yml`自身がblock/rescueで囲われており(notify.yml側)、失敗しても`rescue`で吸収
される設計であることはコードで確認済みだが、**能動的にcapture.yml自体を失敗させる注入は
行っていない**(spool dirを書き込み不可にする、程度は可能だが、今回は「常にゲートで
skipされる」実測で十分と判断した)。

**Slack送信失敗**: `-e slack_force_send=true -e slack_webhook_alerts=https://127.0.0.1:9/decoy-alerts`
(ループバック閉ポート、decoy技法)を、report保存失敗を起こす設定(§2.4と同条件)と
組み合わせて実行した。実測:
```
TASK [Send Slack notification] fatal: ... Connection refused
TASK [Slack notification failed (ignored)] ok: "Slack notification failed and was ignored (...)"
```
最終rcは§2.4と同じ非ゼロ(`report_save_failed`起因のrc)のままで、**Slack送信失敗自体が
rcを追加で変えていないこと**を確認した(表の「その回の本来のrc」)。本番Webhookへは一度も
到達していない(送信先はループバック閉ポート)。

## 3. AC14の残り(APIへ到達できないケース)

`_015`はtoken path不存在のみ。本記録は独立にtoken pathケースを再確認し、加えてAPI到達不能
ケースを追加した。

### 3.1 token読めない(独立再確認) — **PASS(実機)**

`-e semaphore_templates_token_path=/nonexistent/path/token`で実行。rc=2、
`failed_task=Fail closed if the token file is missing, not root-owned, or not 0600 (R4/AC6)`。
console log全文を実tokenの値で`grep -c`し、0件を確認した。

### 3.2 APIへ到達できない(新規) — **PASS(実機)**

`-e semaphore_templates_api_base_url=https://127.0.0.1:9/api`(ループバック閉ポート、
decoy技法)で実行。rc=2。実測メッセージ:
```
scrubbed failure detail=Status code was -1 and not [200]: Request failed: <urlopen error [Errno 111] Connection refused>
```
このメッセージが通知本文(reconcile_finalize.ymlのslack_message)には**そもそも含まれない**
(status/counts/failed_task名のみで、詳細文言自体を運ばない設計であることをコードで確認)。
console log・run report・`RD_T`配下の全ファイルをtoken値で`grep -rl`し、0件を確認した。
「生のAPI失敗文」はこのケースでは接続レベルのエラー(`Connection refused`、実際のHTTP
応答本体は存在しない)であり、Authorization値やAPIのレスポンスボディを含まないことを
コード(uriモジュールの`no_log: true`、rescueでのtoken置換)と実測の両方で確認した。

## 4. AC17の`semaphore_probe_error`分岐

`_015`は「意図的な接続断を作っていない」として未確認のままPASSにしていた。本記録は
接続断を実際に作った。

**手法**: `playbooks/deployment_drift_check.yml`を
`-e deployment_drift_check_hosts=ansy -e deployment_drift_check_semaphore_probe_host=ansy
-e semaphore_templates_api_base_url=https://127.0.0.1:9/api`(ループバック閉ポート)で実行
(`-l ansy`ではなく`deployment_drift_check_hosts`変数で対象を絞った — `-l`だと集計・
report保存を行う`hosts: localhost`のplayまで一致せずskipされてしまうことを最初の試行で
確認したため、変数側で絞る形に修正した)。

実測結果(保存されたJSONレポート、`/tmp`配下):
```json
{
  "checked_counts": {"ansy": {"semaphore_templates": 0, ...}},
  "findings": [
    {"category": "semaphore_probe_error", "item": "Semaphore API probe", "actual": "失敗",
     "detail": "semaphore_templates probe失敗 (task: GET the list of Semaphore projects): Status code was -1 and not [200]: Request failed: <urlopen error [Errno 111] Connection refused>"},
    {"category": "semaphore_reconcile_stale", "item": "Semaphore daily reconcile", "actual": "markerが欠落", ...}
  ]
}
```

- **`semaphore_probe_error`が実際に生成されることを確認した(PASS)。**
- **`category: semaphore_template`のfindingは1件も無いことを確認した(PASS、この接続断
  ケースでも変わらない)。**
- **`checked_counts.semaphore_templates`は0という値で、キー自体は従来どおり出ることを
  確認した(PASS)。** probe失敗時は0になる設計(コードコメントどおり)であり、キーの
  不在ではない。
- `semaphore_reconcile_stale`も同時に出た(このテスト用report_dirにmarkerが存在しない
  ため、AC16の正常な副作用であり、AC17の対象ではない)。

生成された一時reportファイル(`/tmp`配下)は本記録の一部であり、`/home/yoshi/homelab-ansible/
reports/drift/`配下に誤って書いた1ファイル(初回試行、`.gitignore`対象で追跡外)は削除済み。

**結論: AC17は`_015`が未確認としていた`semaphore_probe_error`分岐を含め、4項目すべてを
実機で確認した。PASS。**

## 5. 判定の一覧(まとめ)

| AC / ケース | 判定 | 備考 |
|---|---|---|
| AC10: 金曜・停止あり→通知 | **未確認** | 実行時に曜日を固定する手段が無く、reserved-name guardが変数注入も拒否する。曜日判定ロジック自体は直接実行でPASS確認済み |
| AC10: 金曜・停止0件→通知しない | **未確認** | 同上 |
| AC10: 金曜以外・停止あり→通知しない | **PASS(実機)** | 本物の木曜、実物25件のactive:falseで確認 |
| AC13: 全成功・変更なし | **PASS(実機)** | |
| AC13: template途中失敗 | **PASS(実機)** | 真のHTTP 400による部分適用(2/3成功) |
| AC13: schedule途中失敗 | **未確認** | preflightが堅牢すぎて、API拒否だがpreflight通過する入力を構成できなかった(欠陥ではなく良い意味の結果) |
| AC13: run report保存失敗 | **PASS(実機)** | |
| AC13: evidence生成失敗/Slack送信失敗 | **PASS(実機)** | evidenceは構造的に毎回スキップ(能動注入はせず)。Slack送信失敗はdecoy webhookで実際に発生させ、rc不変を確認 |
| AC14: token読めない | **PASS(実機、独立再確認)** | |
| AC14: APIへ到達できない | **PASS(実機)** | ループバック閉ポート、token/生の失敗文とも非露出 |
| AC17: `semaphore_probe_error`分岐 | **PASS(実機)** | `_015`が未確認としていたものを解消 |

**`_020`の指摘に対する応答**: 4項目のうち、AC13とAC17は本記録で実機確認により解消した
(AC13のschedule途中失敗を除く)。AC10とAC13のschedule途中失敗は、実測できない技術的理由
(reserved-name guardによる変数注入拒否、preflightの堅牢性)を明示した未確認として残す。
これらはCoordinatorが「未確認のまま受容するか」「別の手段(2026-09-18の実地観測など)で
埋めるか」を判断する材料として提供する。

## 6. 自己検証(検証終了時点)

### schedule 24本すべて`active: false`、自分が作ったものが残っていないこと

```
GET /project/3/schedules
count 24
active_true_count 0
```
24件の名称一覧(全て実カタログの名称と一致):
SAFE: Authy healthcheck daily / SAFE: Monitoring healthcheck daily / SAFE: Proxmox hardware
check daily / SAFE: Proxmox healthcheck daily / SAFE: Semaphore update check monthly /
SAFE: Syslog weekly digest / SAFE: Time sync check / SAFE:Deployment drift check /
SAFE:Prometheus update check / SAFE:Proxmox backup restore verify / SAFE:Proxmox snapshot
check / SAFE:Recovery monitoring check / SEMI-SAFE: Proxmox patch dry-run weekly /
SEMI-SAFE: Proxmox storage monthly / SEMI-SAFE: Quory health monthly / SEMI-SAFE: Semaphore
db backup daily / SEMI-SAFE: Ubuntu nightly reboot if required daily / SEMI-SAFE:Cert_renew
(only on Quory) / SEMI-SAFE:Cloudkey_cert_deploy / SEMI-SAFE:Codex update check(Only on
Quory) / SEMI-SAFE:Sophos trim / SEMI-SAFE:Ubuntu vm full upgrade(dry_run=true) /
SEMI-SAFE:Unifi backup fetch / UN-SAFE:Proxmox Weekly Full Patch

**注記**: 検証の途中、現行カタログをそのまま実適用する回(AC13「全成功・変更あり/なし」の
確認)で、P0-14のbootstrap schedule(`SEMI-SAFE: Semaphore reconcile daily`)が実際に
作成された(id=59、`active: false`、非canonical接続先のため仕様どおり)。これは`ZZ-TEST`
ではなく現行カタログの正規の適用結果だが、**開始時点の基準(24本)と一致させるため、検証
終了時に自分で削除した**(DELETE 204で確認)。

template側もcount=58(検証開始時と同数)、`ZZ-TEST`prefixの残骸なしを確認した(§2.2で
作成したid=91,92および§1準備段階のid=90はいずれも削除済み)。

### 検証中にSemaphoreタスクが1件も作られていないこと

検証開始前と終了後の両方で`GET /project/3/tasks`を実行し、件数・最大idが一致することを
確認した(開始時: 9件・max id=28。終了時: 9件・max id=28)。本レポートの全ての操作は
`ansible-playbook`から直接Semaphore REST APIを呼ぶ形、またはこのAPIへの直接curl呼び出しで
行っており、Semaphoreの「タスク」実行(ジョブキュー経由)は一度も発生していない。

### その他

- `reports/drift/`配下に1回誤って書いた一時ファイルは削除済み、`git status`で確認すると
  リポジトリの追跡対象に変化は無い(`.gitignore`対象)。
- 変更した追跡対象ファイルは本ファイル(`2026-09-17_022_test_result_audit_gaps.md`)のみ。
- 本番Slackへの送信は一度も発生していない(§0)。quory・本番ホストへは一切接続していない。

---

## Coordinatorによる訂正(2026-09-17、再監査 `_023` の指摘1)

**「evidence生成失敗 / Slack送信失敗」をまとめて PASS とした集約は誤りである。正しくは次のとおり。**

| ケース | 判定 |
|---|---|
| **Slack送信失敗** | **PASS(実機)。** decoy webhook(ループバックの閉ポート)への実POST失敗で再現し、最終rcが変わらないことを確認した |
| **evidence生成失敗** | **未確認。** 本文に記載のとおり、ansyでは収集器の設定ファイルが無いため capture task が**構造的にskipされた**だけで、`capture.yml` を能動的に失敗させてはいない。**skipは生成失敗ではない。** |

受容の判断と理由は `_019` §6 に記録した。
