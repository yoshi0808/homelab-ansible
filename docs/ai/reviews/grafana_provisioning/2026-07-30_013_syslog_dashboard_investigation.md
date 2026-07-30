# test_result: syslogダッシュボードの現況調査(U5、read-only)

作成: 2026-07-30 / Tester(独立subagent)
対象: `docs/ai/reviews/grafana_provisioning/2026-07-30_004_plan.md` §4 U5
参照: `2026-07-30_001_requirement.md` R10・R3判定表、`2026-07-30_008_test_result_step1.md`(Grafana 13.1構造・後日追記部分)、`2026-07-30_012_classic_export_infra_syslog.json`(Yoshinobu提供のclassic export)
対象ホスト: monnie(接続identity `ann`。特権read-onlyは`ansible monnie -b`、Coordinator承認済みの範囲)

**本調査はread-onlyであり、配備・変更は一切行っていない。** `grafana.db`への接続はすべて`sqlite3?mode=ro`のURIオープン(`ansible.builtin.script`モジュールでpython3スクリプトを一時実行、実行後はansibleが自動削除)。ファイル追加/変更/削除、DB書込、provisioning reload、`grafana-server`のrestart/reloadは一切発生していない。`/var/lib/grafana/dashboards/`への書き込みも行っていない。

## 総括

| 項目 | 結論 |
|---|---|
| 1. 現在のfolder | **`''`(空文字列)= Grafanaの root(General相当)folder。DBの実データで確定。** |
| 2. 同一uidをfile provisioningが引き取れるか | **不明。** 公式ドキュメントはdashboardのUID一致時に「DBの当該dashboardを更新する」と一般論を書くのみで、「UI作成→provisioning初回引き取り」の個別挙動を明記しない。ただし間接的な傍証は「引き取り」寄り(下記参照) |
| 3-a. resourceテーブル上の現在の姿 | `apiVersion: dashboard.grafana.app/v2`、`generation: 6`、`managedBy`/`managerId`注釈は**存在しない**(確認済み)、folder注釈は空文字列 |
| 3-b. classic exportとの意味的差分 | **無い。** PromQL/LogQL、panel型、grid配置、変数定義、閾値相当の設定は全て一致。UniFi 7枚で見られたpanel型書き換え(graph→timeseries等)は発生していない |

---

## 1. folderの確定

### DBの実データ

`resource`テーブル(`resource='dashboards'`)を全件確認した。

```
name                          folder          action  resource_version
4Yo8IZ-Wk                      dfn83173h89oge  2       ...
9WaGWZaZk                      dfn83173h89oge  2       ...
FsfxpWaZz                      dfn83173h89oge  2       ...
feeyvd8ay2ku8b                 dfn83173h89oge  2       ...
g5wFWqxZk                      dfn83173h89oge  2       ...
infra-syslog-all-nodes-v1      (空文字列)      2       1785028694576990
jMfvAjxWz                      dfn83173h89oge  2       ...
w3usaHLZk                      dfn83173h89oge  2       ...
```

UniFi 7枚は全て`dfn83173h89oge`。syslogダッシュボードだけ`folder`列が空文字列。

### `folder`テーブル(専用テーブル)

`resource='folders'`のレコードは**`dfn83173h89oge`(title: `"UniFi"`)の1件のみ**。他に一切folder resourceが存在しない。つまりこのGrafanaインスタンスには「UniFi」という1個のfolderしか作られておらず、**root(General)folderはresourceとして実体化されていない**(Grafanaの仕様上、rootは暗黙のfolderであり、resourceテーブルに行を持たない)。

`dfn83173h89oge`自体の`metadata.annotations`:
```
grafana.app/createdBy: access-policy:service
grafana.app/managedBy: classic-file-provisioning
grafana.app/managerId: unifi
```
このfolder自体も、現行`unifi.yaml`の`folder: 'UniFi'`を根拠にdashboard providerが作成したものである(folderの`title`が"UniFi"と一致)。

### 結論

**`folder`列が空文字列であることは「未設定」ではなく「root(General)への確定した所属」を意味する。** 根拠は二重。(a) DB上に空文字列以外の値としてrootを表す行が存在しない(rootはそもそも行を持たない設計)。(b) Grafana公式ドキュメントが明示している:「Grafana installs dashboards at the root level if you don't set the `folder` field.」(folderフィールドを設定しなければrootへ配置される)。

**U6でのprovider `folder:`設定への含意**: 新設するprovider yaml(`dashboards-provider-infra-syslog.yml`)は、**`folder: ''`を明示するか、`folder`キー自体を省略する**(公式ドキュメントの一般的な書式は`folder: ''`)。既存の`unifi.yaml`が`folder: 'UniFi'`のような文字列を持つのと対称的に、こちらは空文字列 = root を明示すればよい。「別のfolder名を確認する必要がある」という計画上の未決定事項は、**「folder名を確認する」ではなく「root(空)であることを確認する」という形で解消した**。

---

## 2. 同一uidのfile provisioning引き取り可否

### 現状(前提の確認)

syslogダッシュボードの`metadata.annotations`を確認した。

```json
{
  "grafana.app/createdBy": "user:ffn82u6q7ka9se",
  "grafana.app/folder": "",
  "grafana.app/saved-from-ui": "Grafana v13.1.0 (b309c9bb3b)",
  "grafana.app/updatedBy": "user:ffn82u6q7ka9se",
  "grafana.app/updatedTimestamp": "2026-07-26T01:18:14Z"
}
```

**`managedBy` / `managerId` キーは存在しない。** UniFi 7枚(例: `w3usaHLZk`)の同じannotationsには`grafana.app/managedBy: classic-file-provisioning`と`grafana.app/managerId: unifi`が明記されており、対比すると差は明白。**依頼文が想定した前提(「UI import由来でprovisioning annotationsを持たない」)は実データで確認できた。**

### 公式ドキュメントの調査

`https://grafana.com/docs/grafana/latest/administration/provisioning/` のdashboard provisioning節を確認した。関連する記述(verbatim):

- 「If the dashboard in the JSON file contains a UID, Grafana updates that the dashboard with that UID in the database.」(JSONファイルにUIDが含まれる場合、Grafanaはそのuidを持つDB上のdashboardを更新する)
- 「You can overwrite existing dashboards with provisioning. Be careful not to reuse the same `title` multiple times within a folder or `uid` within the same Grafana instance to avoid inconsistent behavior.」(provisioningで既存dashboardを上書きできる。同一instance内でtitleやuidを重複させないよう注意)
- 「If you save a provisioned dashboard in the UI and then later update the provisioning source, Grafana always overwrites the database dashboard with the one from the provisioning file.」(provisioned dashboardをUIで保存した後にprovisioning側を更新すると、常にファイル側で上書きする)
- 「Grafana ignores the `version` property in the JSON file, even if it's lower than the dashboard in the database.」

**`managedBy` / `managerId` / `provenance` / `ownership`という語はdashboard provisioning節に一切現れない。** (`provenance`はalerting節に1箇所だけ現れるが、dashboardには関係しない。)alert ruleのprovenance保護(UI編集不可・衝突検知)に相当する概念は、dashboardのprovisioningドキュメントには文書化されていない。

**「UI作成 → 後からfile provisioningで同一uidを配る」という今回の個別ケースそのものへの言及は無い。** ドキュメントが書いているのは「provisioning済みdashboardをUIで編集した後にファイル側を更新した場合」の挙動(ファイル側が常に勝つ)であり、「今まで一度もprovisionされたことのないUI dashboardに、初めてファイルが同一uidで現れた場合」がここに含まれるかどうかは明記されていない。

### 判定

**不明。** ただし次の非対称な傍証がある。

- dashboard provisioningのドキュメントは終始「UID一致 → DBの当該レコードを更新する」という一般論のトーンで書かれており、エラーや衝突を示唆する記述が一切無い。これはalert ruleのprovisioning節が明確に「provisioned resourceの手動編集を拒否する」「provenanceが競合する」という排他的な語彙を持つのと対照的である。
- Step 1実測(`008_test_result_step1.md`後日追記)で確認済みの`managedBy`/`managerId`アノテーションは、file provisioningが「対象resourceに後から書き込む」形で機能していることを示す(provisioning専用の別テーブルへ隔離されているわけではない)。同じ`resource`テーブルの同じ行を上書きする設計であれば、UID一致時に新規作成でなく既存行の更新(=引き取り)になる可能性が高い。

**この傍証は推測であり断定材料にしない。** 依頼文の指示どおり「不明」として返す。Coordinatorが「失敗しても安全か」で判断する材料として、次を付記する。

- **失敗した場合の観測可能な兆候**: alert ruleのQ3で確立した手法(1-6手順5・6)と同型 — 配置後に`resource`テーブルへ`infra-syslog-all-nodes-v1`が期待どおり1行のまま存在し続けるか(重複UIDでの新規行が生じないか)、`grafana-server`のログにprovisioningエラーが出ないかを、実配備時にTesterが確認できる。
- **万一「衝突」側だった場合の代替**: requirement R10が既に用意している(「Yoshinobuが先にUIから削除」、alert ruleのR8と同型)。

---

## 3. 追加確認事項

### 3-a. `resource`テーブル上の現在の姿

```
apiVersion:            dashboard.grafana.app/v2
kind:                   Dashboard
metadata.generation:    6
metadata.resourceVersion: (metadataオブジェクト内には無い。resourceテーブル自体の`resource_version`列は 1785028694576990 — Unified Storageの内部版数で、`generation`とは別物)
metadata.labels:        {"grafana.app/deprecatedInternalID": "1914057286721536"}
metadata.annotations:   grafana.app/folder="", grafana.app/saved-from-ui="Grafana v13.1.0 (b309c9bb3b)"、managedBy/managerId無し
spec top-level keys:    annotations, cursorSync, editable, elements, layout, links, liveNow, preload, tags, timeSettings, title, variables
status:                 {}(空)
```

**schema形式はv2。** Step 0調査(`002_investigation.md`)がrepoの`roles/alloy/dashboards/infra_syslog_all_nodes.json`について推測していた「v2形式」は、DB内部の実データでも確認された(`apiVersion: dashboard.grafana.app/v2`、`spec.elements`/`spec.layout`/`spec.variables`という同型の構造)。

`metadata.labels`の`grafana.app/deprecatedInternalID: "1914057286721536"`は、`012_classic_export_infra_syslog.json`の`"id": 1914057286721536`と一致する。**classic exportの`id`フィールドは、内部の非推奨numeric IDをそのまま出力したものである。** これがU6でrepoへコミットするファイルに残ったまま配備した場合の挙動は未検証(公式ドキュメントは「JSON内の`version`は無視する」とだけ書いており、`id`フィールドの扱いへの直接言及は無い)。**U6実装時に検討すべき論点として記録するに留め、本調査では判定しない。**

### 3-b. classic exportと内部版の差分

`012_classic_export_infra_syslog.json`(classic export)と、repoに現存する`roles/alloy/dashboards/infra_syslog_all_nodes.json`(v2形式)を突合した。**両者はschema形式そのものが違う**(classic = `panels[]`/`templating.list`/`schemaVersion`、v2 = `spec.elements`/`spec.layout`/`spec.variables`)ため、UniFiのときのような「同一schema内でのバイト単位diff」はできない。**意味(セマンティクス)を対応させて突合した。**

| 項目 | v2(現repo) | classic export | 差 |
|---|---|---|---|
| panel数・順序 | panel-1/2/3 | id 1/2/3 | 一致 |
| panel type | `timeseries` / `logs` / `logs`(`vizConfig.group`) | `timeseries` / `logs` / `logs`(`type`) | **一致。書き換え無し** |
| PromQL/LogQL(`expr`) | 3panel×計4クエリ、全文一致確認 | 同左 | **完全一致** |
| gridPos | x0/y0/w24/h6、y6/h20、y26/h14 | 同左 | 一致 |
| fieldConfig(panel-1) | unit=short, min=0, custom{barAlignment:0, barWidthFactor:0.6, drawStyle:bars, fillOpacity:70, lineWidth:0} | 同左 | 一致 |
| 変数(host/level/search) | current値・query文字列とも一致(v2は`__legacyStringValue`でラップ、値は同じ) | — | 一致(表記形式のみ差) |
| tags | 同一リスト・同一順 | 同左 | 一致 |
| refresh/autoRefresh | `autoRefresh: "1m"` | `refresh: "1m"` | 一致(フィールド名のみschema差) |
| cursorSync/graphTooltip | `cursorSync: "Off"` | `graphTooltip: 0` | 一致(schema差のみ、意味は同じ「オフ」) |
| `version`(classicのみ) | (該当フィールド無し) | `6` | DBの`metadata.generation`(=6)と一致。公式ドキュメントが「provisioning時にversionは無視する」と明記しているため無害 |
| `id`(classicのみ) | (該当フィールド無し) | `1914057286721536` | DBの`grafana.app/deprecatedInternalID`と一致。挙動は3-aのとおり未検証 |

**結論: UniFi Switchesで見られた「18枚中15枚のpanel型書き換え」に相当する劣化は発生していない。** 理由は、syslogダッシュボードが元々`timeseries`/`logs`という現行のpanel型で作られており(2026-07-19以降にAlloy移行時に新規作成されたv2ネイティブのダッシュボードであるため)、classic exportへ変換しても型のmigrationが起きる余地が無いこと。**「exportしたものを配り直すと何かが変わるか」という問いへの答えは、この1枚に関しては「意味的な差は無い」である。** `version`/`id`という2つのインスタンス固有フィールドが追加で載る点だけがUniFiのケースと異なる注意点として残る。

---

## 取得できなかった項目・未解決事項

1. **調査項目2(同一uid引き取りの可否)は「不明」のまま。** 公式ドキュメントに明記が無く、実機で試すこと自体が本番適用になるため検証しない(依頼文の禁止事項どおり)。Coordinatorの判断材料として、alert ruleと同型の検出手段(resourceテーブルの重複確認・ログ確認)と代替(UI事前削除)を3-b直下ではなく「2. 判定」節に記載した。
2. **`id`フィールド(内部numeric ID)をclassic exportからrepoへそのまま持ち込んでよいかは未検証。** U6着手時にImplementerが検討すべき論点として記録した(3-aの末尾)。
3. **`folder`テーブルに`General`相当の行が無いことを「rootは行を持たない設計である」と解釈した根拠は、DBの実データ(folder resourceが`UniFi`の1件のみ)と公式ドキュメントの記述の組み合わせであり、Grafana内部実装のソースコードまでは確認していない。**

## 対象パス一覧

- 対象role: `/home/yoshi/homelab-ansible/roles/grafana_provisioning/`(U6で新設予定のファイルはまだ存在しない)
- 参照した既存repoファイル: `/home/yoshi/homelab-ansible/roles/alloy/dashboards/infra_syslog_all_nodes.json`
- 参照したclassic export: `/home/yoshi/homelab-ansible/docs/ai/reviews/grafana_provisioning/2026-07-30_012_classic_export_infra_syslog.json`
- 本ファイル: `/home/yoshi/homelab-ansible/docs/ai/reviews/grafana_provisioning/2026-07-30_013_syslog_dashboard_investigation.md`
- 対象ホスト: monnie(inventory: `/home/yoshi/homelab-ansible/inventories/homelab/hosts.yml`)。`grafana.db`はread-only(`mode=ro`)でのみ参照。
