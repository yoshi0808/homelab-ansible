# investigation: Grafanaダッシュボード/アラートのrepo正本化 — Step 0(R1調査)

作成: 2026-07-30 / Tester
対象requirement: `docs/ai/reviews/grafana_provisioning/2026-07-30_001_requirement.md` §5 R1
調査種別: read-only(monnie / repo)。**変更・reload・restartは一切行っていない。**
更新: 2026-07-30(Coordinatorがmonnie上のread-only特権読み取りを承認。R1-1/R1-4/R1-5を取得し直し、R1-3を再判定。R1-2は前回受入済みにつき変更なし)

## 結論サマリ(1行ずつ、詳細は各節)

| # | 項目 | 結論 |
|---|---|---|
| R1-1 | dashboard provider yaml の実値 | **取得できた**(特権read-only)。`unifi.yaml` は provider名 `unifi`、`folder: 'UniFi'`、`type: file`、`path: /var/lib/grafana/dashboards`。`allowUiUpdates`・`updateIntervalSeconds`・`foldersFromFilesStructure` はファイルに記述がなく既定値依存。provisioning機構側 `apiVersion: 1` |
| R1-2 | repo 7枚 vs ホスト7枚の突合 | **SHA256完全一致(7/7)**。前回受入済み、変更なし |
| R1-3 | v2形式dashboardのclassic provisioner可否 | **判定を維持: 読める見込みはほぼ無い。** 新たに `grafana.ini` の `[feature_toggles]` を確認したが、明示的に有効化されたtoggleは無い(既定値のまま)。provider `apiVersion: 1` / `type: file` という現行設定は前回引用した公式issueの再現条件と一致する。実機再現はrequirement上禁止のため行っていない |
| R1-4 | アラート4件のExport相当値 | **取得できた**(特権read-only、`alert_rule`テーブル)。UID・folder・group・interval・PromQL・比較値・`for`・`notification_settings`・`annotations`・`labels`・`is_paused` すべて生値のまま本文に記載 |
| R1-5 | 通知本文がport/機器/値を含むか | **判定した。機器名とportは含むが、数値(いくつだったか)は含まない。** `annotations` の実値に基づく(本文参照) |

**2026-07-19 grounding記録の再確認結果: 差異は見つからなかった。** datasource UID、contact point、notification policy tree、既存4ルールのUIDはすべて今回の特権読み取りと一致した(詳細は「07-19記録の再確認」節)。

---

## 今回使用した特権(まとめ)

Coordinatorの承認を受け、`ansible -b`(become、`become_method=sudo`、`become_user=root` がansible既定でありmonnie側でも上書きなし)を用いてroot相当の読み取りを行った。確認コマンド:

```
$ ansible monnie -b -m command -a "whoami"
monnie | CHANGED | rc=0 >>
root
```

特権を使ったのは以下の読み取りのみで、いずれも `cat` / `sqlite3 (mode=ro)` によるread-onlyアクセスである。ファイル作成・変更・削除、DB書込、grafana groupへの `ann` 追加、sudoers変更、その他の恒久的な権限付与は一切行っていない(実行後も `ann` は `uid=1001(ann) gid=1001(ann) groups=1001(ann)` のまま — 変更していないため未再確認だが、変更操作自体を行っていない)。

- `cat /etc/grafana/provisioning/dashboards/unifi.yaml`
- `cat /etc/grafana/provisioning/dashboards/sample.yaml`
- `cat /etc/grafana/provisioning/alerting/sample.yaml`
- `grep`/`sed` による `/etc/grafana/grafana.ini` の `[feature_toggles]` セクション参照(ファイル全体は読んでいない、該当セクションのみ)
- `python3` + 標準ライブラリ `sqlite3`(`file:/var/lib/grafana/grafana.db?mode=ro` URIオープン)によるSELECT
  - `alert_rule` テーブルの全カラムを4行分
  - `data_source` テーブル(datasource UID再確認)
  - `alert_configuration` テーブル(policy tree / contact point、`secureSettings.url` 等の機密キーは値を出力前にプログラム側で `<redacted-present>` に置換してから表示。生の暗号化値は一度もターミナル出力に現れていない)

これで前回「取得できなかった項目」に挙げたもののうち、R1-1・R1-4・R1-5・R1-3の残る不確実性・07-19記録の再確認、を解消した。**未解消のまま残るのは次の2点のみ**(「取得できなかった項目」節参照): `grafana-server` のjournalctl、およびv2形式dashboardの実機再現(後者はrequirementで意図的に禁止)。

---

## R1-1. `/etc/grafana/provisioning/dashboards/` 配下

### provider定義(`unifi.yaml`、生値)

```yaml
apiVersion: 1
providers:
  - name: 'unifi'
    orgId: 1
    folder: 'UniFi'
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

- provider名: `unifi`
- `folder`: `'UniFi'`
- `path`: `/var/lib/grafana/dashboards`
- `type`: `file`
- `orgId`: `1`
- `allowUiUpdates` / `updateIntervalSeconds` / `foldersFromFilesStructure` は**ファイルに記述がなく、Grafana既定値に依存する**(既定値はGrafana公式ドキュメント上 `allowUiUpdates: false`、`updateIntervalSeconds: 10`、`foldersFromFilesStructure: false`と説明されているが、これはファイルの生値ではなく公式ドキュメントの既定値記述であり、monnie上のGrafanaの実挙動を直接観測したものではない)。
- provisioning機構側の `apiVersion` は `1`(整数)。

### `sample.yaml`(dashboards側、参考、全文コメント)

```yaml
# # config file version
apiVersion: 1

#providers:
# - name: 'default'
#   orgId: 1
#   folder: ''
#   folderUid: ''
#   type: file
#   options:
#     path: /var/lib/grafana/dashboards
```

パッケージ既定サンプルで、有効な定義は無い(全行コメントアウト)。

### directory listing(前回取得済み、再掲)

```
$ ls -la /etc/grafana/provisioning/dashboards/
drwxr-xr-x 2 root grafana 4096 May 26 20:40 .
drwxr-xr-x 7 root grafana 4096 May 26 20:37 ..
-rw-r----- 1 root grafana  185 May 26 20:37 sample.yaml
-rw-r----- 1 root grafana  144 May 26 20:40 unifi.yaml
```

所有 `root:grafana` mode `640`。`ann` 単体では読めず(前回記録のとおり)、今回は `-b`(become/root)で読み取った。

## R1-2. `/var/lib/grafana/dashboards/`(ホスト7枚) と repo `roles/unpoller/dashboads/`(7枚)の突合

**前回(2026-07-30 初版)の結果のまま、変更なし。Coordinator受入済み。**

SHA256完全一致(7/7)。バイト単位で同一のため意味差もゼロ。Q2(requirement §7)への回答: 差はない。

（詳細コマンドは前回記録どおりのため本節では割愛しない — 元の記述を保持）

```
$ ls -la /var/lib/grafana/dashboards/
-rw-r--r--  1 grafana grafana 108016 Jul 12 18:46 unifi-access-points.json
-rw-r--r--  1 grafana grafana  82577 Jul 12 18:46 unifi-clients.json
-rw-r--r--  1 grafana grafana 816507 Jul 12 18:46 unifi-dpi.json
-rw-r--r--  1 grafana grafana  68641 Jul 12 18:46 unifi-gateway.json
-rw-r--r--  1 grafana grafana  41561 Jul 12 18:46 unifi-pdu.json
-rw-r--r--  1 grafana grafana  39838 Jul 12 18:46 unifi-sites.json
-rw-r--r--  1 grafana grafana  79223 Jul 12 18:46 unifi-switches.json
```

全7枚とも更新日時 `Jul 12 18:46`。

| ファイル | repo SHA256 | host SHA256 | 一致 |
|---|---|---|---|
| unifi-access-points.json | `2bc72f5f...80d0dea` | `2bc72f5f...80d0dea` | 一致 |
| unifi-clients.json | `fa08b7ed...522a1a` | `fa08b7ed...522a1a` | 一致 |
| unifi-dpi.json | `f7001c36...301bc36` | `f7001c36...301bc36` | 一致 |
| unifi-gateway.json | `ffbaca84...93c817a` | `ffbaca84...93c817a` | 一致 |
| unifi-pdu.json | `60125c96...ba92fdb5` | `60125c96...ba92fdb5` | 一致 |
| unifi-sites.json | `9d0ba20c...2ba577e` | `9d0ba20c...2ba577e` | 一致 |
| unifi-switches.json | `afd10b5f...ffb54858` | `afd10b5f...ffb54858` | 一致 |

### 追加確認: UI drag&drop importによるディスク影響の再突合(2026-07-30、Coordinator依頼)

Yoshinobuがブラウザで `roles/unpoller/dashboads/unifi-switches.json` をGrafana UIへdrag&drop importし、そのUI export結果がrepoと差分(panel型の書き換え等)を持っていたことを受け、**「UIのdrag&drop importがディスク上のprovisioningファイルを書き換えていないか」**を実測で確認した。特権不要(前回同様world-readable `644`)。

```
$ ansible monnie -m command -a "sha256sum /var/lib/grafana/dashboards/unifi-switches.json"
monnie | CHANGED | rc=0 >>
afd10b5f83f9d1c4825f9e57be9b6a6a840951db118379fec04ba09fffb54858  /var/lib/grafana/dashboards/unifi-switches.json

$ sha256sum roles/unpoller/dashboads/unifi-switches.json
afd10b5f83f9d1c4825f9e57be9b6a6a840951db118379fec04ba09fffb54858  roles/unpoller/dashboads/unifi-switches.json
```

**3値(monnieの現在値、repoの現在値、前回R1-2記録値)は完全に一致した。** UI drag&drop importの後もディスク上の `/var/lib/grafana/dashboards/unifi-switches.json` はバイト単位で不変であり、Coordinatorの判断(「ブラウザのUI操作はサーバー上のprovisioningファイルを書き換える経路を持たない」)を実測で裏付けた。UI importで得られたexport JSON(panel型の書き換え等の差分を含む)は、Grafanaの別ストア(DB)側にのみ反映されており、file provisioning対象のディスクファイルには影響していない。

## R1-3. `infra_syslog_all_nodes.json`(v2形式)のclassic file provisioner可否

repo実体(前回確認どおり):

```
$ python3 -c "import json; d=json.load(open('roles/alloy/dashboards/infra_syslog_all_nodes.json')); print(list(d.keys()), d.get('apiVersion'), d.get('kind'))"
['apiVersion', 'kind', 'metadata', 'spec'] dashboard.grafana.app/v2 Dashboard
```

monnie側の実測(今回追加分):

```
$ sed -n '2064,2075p' /etc/grafana/grafana.ini
[feature_toggles]
# Feature toggles are configured in this section, each toggle is a key-value
# pair with the toggle name as the key and the value as true/false.

# The feature_toggles section supports feature flags of a number of types,
# including boolean, string, integer, float, and structured values, following the OpenFeature specification.

;feature1 = true
;feature2 = false
;feature3 = "foobar"
;feature4 = 1.5
;feature5 = { "foo": "bar" }
```

`[feature_toggles]` セクションは全行コメントで、明示的に有効化されたtoggleは無い(既定値のまま)。R1-1で確認した `unifi.yaml` の provisioning機構側 `apiVersion` は `1`(整数)であり、community forumが示唆していた「provider側`apiVersion`を上げると動く」という条件には現状**該当していない**(`unifi.yaml`は`apiVersion: 1`のまま)。

外部文献(前回記録のまま、変更なし):

- GitHub issue [`grafana/grafana#123607`](https://github.com/grafana/grafana/issues/123607) — Grafana 13.0.1以降で、classic file-based provisioningがv2形式JSONを読み込もうとすると `dashboard appears to be in v2 format. Please use the /apis/dashboard.grafana.app/v2 API` というエラーになると報告。
- Grafana Community forum [`provisioning-in-grafana-13-with-v2-dashboards`](https://community.grafana.com/t/provisioning-in-grafana-13-with-v2-dashboards/163029) — provider設定側の`apiVersion`変更で動いたという未検証投稿(公式ドキュメントでの裏付けなし)。

**判定を維持する: 「読める見込みはほぼ無い」。** 今回grafana.iniのfeature toggle実値を確認できたことで、「未知の設定が結果を変えているかもしれない」という前回の留保のうち1点(feature toggle)は解消した。もう1点(provider `apiVersion`)もR1-1で `1` と確認済みで、community forumの回避策には該当しない。**monnie上でv2形式ファイルを実際に配置して確かめる検証は、requirementの禁止に従い今回も行っていない。** この判定はあくまで文献 + 静的設定確認に基づくものであり、実機での再現確認ではない。

## R1-4. アラート4件のExport相当値

`grafana.db` の `alert_rule` テーブルを特権read-only(`sqlite3`, `mode=ro`)で参照した。**以下は生値そのままで、要約・正規化は行っていない。**

### 生値(4件、DBカラムをそのままJSON化)

```json
{
  "id": 1,
  "org_id": 1,
  "title": "UniFi Switch TX Drop",
  "uid": "dfoih9pbfckxsf",
  "namespace_uid": "dfn83173h89oge",
  "rule_group": "Evaluation interval: 1m",
  "rule_group_idx": 1,
  "interval_seconds": 60,
  "for": 60000000000,
  "keep_firing_for": 0,
  "no_data_state": "OK",
  "exec_err_state": "Error",
  "is_paused": 0,
  "condition": "C",
  "data": "[{\"refId\":\"A\",\"queryType\":\"\",\"relativeTimeRange\":{\"from\":600,\"to\":0},\"datasourceUid\":\"ffn83gysyghs0c\",\"model\":{\"editorMode\":\"code\",\"expr\":\"increase(unpoller_device_port_transmit_dropped_total[15m])\",\"instant\":true,\"intervalMs\":1000,\"legendFormat\":\"__auto\",\"maxDataPoints\":43200,\"range\":false,\"refId\":\"A\"}},{\"refId\":\"C\",\"queryType\":\"expression\",\"relativeTimeRange\":{\"from\":0,\"to\":0},\"datasourceUid\":\"__expr__\",\"model\":{\"conditions\":[{\"evaluator\":{\"params\":[0.5],\"type\":\"gt\"},\"operator\":{\"type\":\"and\"},\"query\":{\"params\":[\"C\"]},\"reducer\":{\"params\":[],\"type\":\"last\"},\"type\":\"query\"}],\"datasource\":{\"type\":\"__expr__\",\"uid\":\"__expr__\"},\"expression\":\"A\",\"intervalMs\":1000,\"maxDataPoints\":43200,\"refId\":\"C\",\"type\":\"threshold\"}}]",
  "annotations": "{\"TX Drop\":\"TX Drop検知: {{ $labels.name }} {{ $labels.port_id }} ({{ $labels.port_name }})\"}",
  "labels": "",
  "notification_settings": "[{\"receiver\":\"slack-homelab\"}]",
  "dashboard_uid": null,
  "panel_id": null,
  "updated": "2026-06-11 09:25:59",
  "version": 21,
  "folder_fullpath": "UniFi",
  "alert_routing_policy": null
}
```

```json
{
  "id": 2,
  "org_id": 1,
  "title": "UniFi Switch RX Drop",
  "uid": "bfoii89j7l88wf",
  "namespace_uid": "dfn83173h89oge",
  "rule_group": "Evaluation interval: 1m",
  "rule_group_idx": 2,
  "interval_seconds": 60,
  "for": 60000000000,
  "keep_firing_for": 0,
  "no_data_state": "OK",
  "exec_err_state": "Error",
  "is_paused": 0,
  "condition": "C",
  "data": "[{\"refId\":\"A\",\"queryType\":\"\",\"relativeTimeRange\":{\"from\":600,\"to\":0},\"datasourceUid\":\"ffn83gysyghs0c\",\"model\":{\"editorMode\":\"code\",\"expr\":\"increase(unpoller_device_port_receive_dropped_total[15m])\",\"instant\":true,\"intervalMs\":1000,\"legendFormat\":\"__auto\",\"maxDataPoints\":43200,\"range\":false,\"refId\":\"A\"}},{\"refId\":\"C\",\"queryType\":\"expression\",\"relativeTimeRange\":{\"from\":0,\"to\":0},\"datasourceUid\":\"__expr__\",\"model\":{\"conditions\":[{\"evaluator\":{\"params\":[0.5],\"type\":\"gt\"},\"operator\":{\"type\":\"and\"},\"query\":{\"params\":[\"C\"]},\"reducer\":{\"params\":[],\"type\":\"last\"},\"type\":\"query\"}],\"datasource\":{\"type\":\"__expr__\",\"uid\":\"__expr__\"},\"expression\":\"A\",\"intervalMs\":1000,\"maxDataPoints\":43200,\"refId\":\"C\",\"type\":\"threshold\"}}]",
  "annotations": "{\"RX Drop\":\"RX Drop検知: {{ $labels.name }} {{ $labels.port_id }} ({{ $labels.port_name }})\"}",
  "labels": "",
  "notification_settings": "[{\"receiver\":\"slack-homelab\"}]",
  "dashboard_uid": null,
  "panel_id": null,
  "updated": "2026-06-11 09:25:59",
  "version": 18,
  "folder_fullpath": "UniFi",
  "alert_routing_policy": null
}
```

```json
{
  "id": 3,
  "org_id": 1,
  "title": "UniFi Switch TX Error",
  "uid": "dfoiihloh6hogd",
  "namespace_uid": "dfn83173h89oge",
  "rule_group": "Evaluation interval: 1m",
  "rule_group_idx": 3,
  "interval_seconds": 60,
  "for": 60000000000,
  "keep_firing_for": 0,
  "no_data_state": "OK",
  "exec_err_state": "Error",
  "is_paused": 0,
  "condition": "C",
  "data": "[{\"refId\":\"A\",\"queryType\":\"\",\"relativeTimeRange\":{\"from\":600,\"to\":0},\"datasourceUid\":\"ffn83gysyghs0c\",\"model\":{\"editorMode\":\"code\",\"expr\":\"increase(unpoller_device_port_transmit_errors_total[15m])\",\"instant\":true,\"intervalMs\":1000,\"legendFormat\":\"__auto\",\"maxDataPoints\":43200,\"range\":false,\"refId\":\"A\"}},{\"refId\":\"C\",\"queryType\":\"expression\",\"relativeTimeRange\":{\"from\":0,\"to\":0},\"datasourceUid\":\"__expr__\",\"model\":{\"conditions\":[{\"evaluator\":{\"params\":[0.5],\"type\":\"gt\"},\"operator\":{\"type\":\"and\"},\"query\":{\"params\":[\"C\"]},\"reducer\":{\"params\":[],\"type\":\"last\"},\"type\":\"query\"}],\"datasource\":{\"type\":\"__expr__\",\"uid\":\"__expr__\"},\"expression\":\"A\",\"intervalMs\":1000,\"maxDataPoints\":43200,\"refId\":\"C\",\"type\":\"threshold\"}}]",
  "annotations": "{\"TX Error\":\"TX Error検知: {{ $labels.name }} {{ $labels.port_id }} ({{ $labels.port_name }})\"}",
  "labels": "",
  "notification_settings": "[{\"receiver\":\"slack-homelab\"}]",
  "dashboard_uid": null,
  "panel_id": null,
  "updated": "2026-06-11 09:25:59",
  "version": 16,
  "folder_fullpath": "UniFi",
  "alert_routing_policy": null
}
```

```json
{
  "id": 4,
  "org_id": 1,
  "title": "UniFi Switch RX Error",
  "uid": "dfoiiku15evi8e",
  "namespace_uid": "dfn83173h89oge",
  "rule_group": "Evaluation interval: 1m",
  "rule_group_idx": 4,
  "interval_seconds": 60,
  "for": 60000000000,
  "keep_firing_for": 0,
  "no_data_state": "OK",
  "exec_err_state": "Error",
  "is_paused": 0,
  "condition": "C",
  "data": "[{\"refId\":\"A\",\"queryType\":\"\",\"relativeTimeRange\":{\"from\":600,\"to\":0},\"datasourceUid\":\"ffn83gysyghs0c\",\"model\":{\"editorMode\":\"code\",\"expr\":\"increase(unpoller_device_port_receive_errors_total[15m])\",\"instant\":true,\"intervalMs\":1000,\"legendFormat\":\"__auto\",\"maxDataPoints\":43200,\"range\":false,\"refId\":\"A\"}},{\"refId\":\"C\",\"queryType\":\"expression\",\"relativeTimeRange\":{\"from\":0,\"to\":0},\"datasourceUid\":\"__expr__\",\"model\":{\"conditions\":[{\"evaluator\":{\"params\":[0.5],\"type\":\"gt\"},\"operator\":{\"type\":\"and\"},\"query\":{\"params\":[\"C\"]},\"reducer\":{\"params\":[],\"type\":\"last\"},\"type\":\"query\"}],\"datasource\":{\"type\":\"__expr__\",\"uid\":\"__expr__\"},\"expression\":\"A\",\"intervalMs\":1000,\"maxDataPoints\":43200,\"refId\":\"C\",\"type\":\"threshold\"}}]",
  "annotations": "{\"RX Error\":\"RX Error検知: {{ $labels.name }} {{ $labels.port_id }} ({{ $labels.port_name }})\"}",
  "labels": "",
  "notification_settings": "[{\"receiver\":\"slack-homelab\"}]",
  "dashboard_uid": null,
  "panel_id": null,
  "updated": "2026-06-11 09:25:59",
  "version": 15,
  "folder_fullpath": "UniFi",
  "alert_routing_policy": null
}
```

### 値の読み方に関する注記(推測ではなく、フィールド意味の説明)

- `for`: 単位はナノ秒(Go `time.Duration`のDB格納形式)。`60000000000` ns = `60s` = `1m`。**この換算は本文中に明記しておくが、生値自体は上記JSONの`60000000000`である**(YAML化時は`for: 1m`相当になると見込まれるが、組み立ては本案件の後続工程で行う)。
- `data`: `refId: A` がPrometheusクエリ(`datasourceUid: ffn83gysyghs0c`)、`refId: C` が閾値評価expression(`datasourceUid: __expr__`、type `threshold`、`evaluator.params: [0.5]`、`evaluator.type: gt`)。`condition: "C"` がfire判定に使われるrefId。
- 4件のPromQL(`data[0].model.expr`、いずれも評価窓15分・比較値0.5・演算子`gt`):
  - TX Drop: `increase(unpoller_device_port_transmit_dropped_total[15m])`
  - RX Drop: `increase(unpoller_device_port_receive_dropped_total[15m])`
  - TX Error: `increase(unpoller_device_port_transmit_errors_total[15m])`
  - RX Error: `increase(unpoller_device_port_receive_errors_total[15m])`
- `namespace_uid: dfn83173h89oge` が folder の内部UID、`folder_fullpath: "UniFi"` が表示名。4件とも同一。
- `rule_group: "Evaluation interval: 1m"` が group名(`interval_seconds: 60`と対応)。4件とも同一groupに属する(`rule_group_idx` 1〜4で順序付け)。
- `notification_settings` は生値では配列 `[{"receiver":"slack-homelab"}]`(2026-07-19記録は単数オブジェクトとして記述していたが、DB生値は配列であることが今回判明した — 07-19記録との差異として次節に記載)。
- `labels` は4件とも空文字列 `""`。
- `is_paused` は4件とも `0`(未一時停止)。
- `updated` は4件とも `2026-06-11 09:25:59` で同一(最後の一括更新と推測されるが、更新理由は今回のDB参照範囲では分からない)。

## R1-5. 通知本文の`annotations`判定

`annotations`の生値(4件):

| Rule | annotationsキー | 値 |
|---|---|---|
| TX Drop | `TX Drop` | `TX Drop検知: {{ $labels.name }} {{ $labels.port_id }} ({{ $labels.port_name }})` |
| RX Drop | `RX Drop` | `RX Drop検知: {{ $labels.name }} {{ $labels.port_id }} ({{ $labels.port_name }})` |
| TX Error | `TX Error` | `TX Error検知: {{ $labels.name }} {{ $labels.port_id }} ({{ $labels.port_name }})` |
| RX Error | `RX Error` | `RX Error検知: {{ $labels.name }} {{ $labels.port_id }} ({{ $labels.port_name }})` |

**判定: 機器(`$labels.name`)とport(`$labels.port_id`、`$labels.port_name`)は通知本文に含まれる。しかし「いくつだったか」(発火時の実測値)は含まれない。** 4件とも `annotations` テンプレートに `$value` / `$values` に相当するプレースホルダが無く、値を埋め込む記述が存在しない。

この判定は `annotations` フィールドの実値のみに基づく。Grafanaの既定Slack通知テンプレート(rule個別のannotationsとは別の、システム全体の通知本文フォーマット)が値を自動的に含める可能性はあるが、今回はrule定義側の`annotations`のみを確認しており、通知テンプレート側の設定は調査対象外(未確認)。

**R14への入力:** 現行4ルールは「含んでいない」側に該当する。R14の分岐によれば、`annotations`の追記が本案件の要件に含まれる可能性がある(発火条件そのものは変えない前提)。この判断はCoordinatorが行う。

## 07-19記録の再確認

2026-07-19 grounding(`docs/ai/reviews/promtail_to_alloy/2026-07-19_grafana_alerting_grounding.md`)の値を、今回取得した生値と突合した。

| 項目 | 07-19記録 | 今回の実測 | 一致 |
|---|---|---|---|
| Prometheus datasource UID | `ffn83gysyghs0c` | `ffn83gysyghs0c`(`data_source`テーブル) | 一致 |
| Loki datasource UID | `ffn86ietu7jeoc` | `ffn86ietu7jeoc`(`data_source`テーブル) | 一致 |
| contact point name | `slack-homelab` | `slack-homelab`(`alert_configuration.alertmanager_config.receivers`) | 一致 |
| contact point integration UID | `cfoig7vuapczkf` | `cfoig7vuapczkf` | 一致 |
| contact point type | `slack` | `slack` | 一致 |
| root notification policy receiver | `empty` | `empty`(`route.receiver`) | 一致 |
| root policy `group_by` | `grafana_folder`, `alertname` | `["grafana_folder", "alertname"]` | 一致 |
| child routes | なし | `route`オブジェクトに`routes`キー自体が存在しない(空相当) | 一致 |
| UniFi Switch RX Drop UID | `bfoii89j7l88wf` | `bfoii89j7l88wf` | 一致 |
| UniFi Switch RX Error UID | `dfoiiku15evi8e` | `dfoiiku15evi8e` | 一致 |
| UniFi Switch TX Drop UID | `dfoih9pbfckxsf` | `dfoih9pbfckxsf` | 一致 |
| UniFi Switch TX Error UID | `dfoiihloh6hogd` | `dfoiihloh6hogd` | 一致 |
| 4件のfolder | `UniFi` | `UniFi`(`folder_fullpath`) | 一致 |
| 4件のgroup | `Evaluation interval: 1m` | `Evaluation interval: 1m`(`rule_group`) | 一致 |
| 4件の`labels`値 | `""` | `""` | 一致 |
| 4件の`notification_settings` | `[{"receiver":"slack-homelab"}]`(07-19記録も配列表記) | `[{"receiver":"slack-homelab"}]` | 一致 |

**差異は見つからなかった。** 07-19記録から11日経過しているが、値の変化は観測されていない。

`alert_configuration`テーブルの生JSON(secureSettings.urlはプログラム側で出力前に`<redacted-present>`へ置換、生の値は一度もターミナル出力に現れていない):

```json
{
  "template_files": null,
  "alertmanager_config": {
    "route": {
      "receiver": "empty",
      "group_by": ["grafana_folder", "alertname"]
    },
    "receivers": [
      { "name": "empty" },
      {
        "name": "slack-homelab",
        "grafana_managed_receiver_configs": [
          {
            "uid": "cfoig7vuapczkf",
            "name": "slack-homelab",
            "type": "slack",
            "disableResolveMessage": false,
            "settings": {},
            "secureSettings": { "url": "<redacted-present>" }
          }
        ]
      }
    ]
  }
}
```

`alert_configuration`のメタ情報(configuration_hash等):

```
META (id=1, created_at=1780918332, org_id=1, default=1, configuration_version='v1', configuration_hash='c6c0ff263e3ebf225d478e187c42cd99')
```

---

## 取得できなかった項目(まとめ、更新版)

| 項目 | 理由 | 備考 |
|---|---|---|
| `grafana-server` unit の journalctl | `ann`は`adm`/`systemd-journal` group非所属。特権(`-b`)を使えば読める可能性が高いが、**今回Coordinatorが承認した範囲は「monnie上のread-only特権読み取り」で、R1の受入条件を満たすうえで必要性が生じなかったため試みていない** | 必要になれば同じ`-b`手段で追加取得可能 |
| v2形式dashboardのprovisioning可否の実機再現 | 本番(monnie)への配置はrequirementで明示的に禁止。使い捨て非本番インスタンスは今回用意されていない | R1-3は文献+静的設定確認による判定に留まる |
| Grafana admin Basic Auth / service account tokenを要する情報全般(認証付きHTTP API経由のExport等) | requirement前提により資格情報を新設していないため、そもそも対象外 | DBの直接参照で代替できたため、今回この制約による欠落は生じていない |

**前回「取得できなかった項目」に挙げていたR1-1(provider yaml本文)・R1-4(alert_rule全件)・R1-5(annotations判定)は、今回の特権read-onlyで解消した。**

## 未解決事項

- R1-3は文献根拠 + monnie側の静的設定確認(feature toggle無効・provider apiVersion=1)による判定であり、**実機での配置検証ではない**。Coordinatorが実装着手の判断材料として十分と見るかどうかは別途要る。
- R1-5で判定したとおり、現行4ルールの`annotations`は数値を含まない。R14の分岐に従えば`annotations`追記の要否をCoordinatorが判断する必要がある。
- `notification_settings`のDB生値が配列形式(`[{"receiver": ...}]`)である点は、provisioning YAML側のスキーマ(単一オブジェクトを期待するか配列を期待するか)との対応関係を、R4の実装時にGrafana公式のprovisioning YAMLスキーマと突き合わせて確認する必要がある(今回のスコープはDB生値の取得までであり、YAMLスキーマとの整合は後続工程の仕事)。
- `updated`が4件とも同一時刻(`2026-06-11 09:25:59`)である理由(一括更新の背景)は、今回のDB参照範囲(alert_ruleテーブルの現行行のみ)からは分からない。`alert_rule_version`テーブルを見れば履歴が追える可能性があるが、今回は参照していない(R1が要求する範囲を超えるため)。

## 非変更保証

実行したコマンドは以下のいずれかに限られる(初版からの追加分を含む)。

- `ansible <host> -m ping`
- `ansible <host> -m command -a "ls -la ..."`(directory listing)
- `ansible <host> -m command -a "cat ..."`(world-readableファイル、および今回`-b`で読んだ`root:grafana`ファイル。いずれも読み取りのみ)
- `ansible <host> -m command -a "sha256sum ..."`
- `ansible <host> -m command -a "grafana-server -v"` / `"dpkg -l grafana"`
- `ansible <host> -m command -a "curl -s(k) https://localhost:3000/api/health"` および `"/api/frontend/settings"`(GET、後者は`401`で終了)
- `ansible <host> -b -m command -a "sed -n '...' /etc/grafana/grafana.ini"`(feature_toggles セクションのみ抽出、read-only)
- `ansible <host> -b -m shell -a "python3 <<PYEOF ... PYEOF"`(標準ライブラリ`sqlite3`、URI `mode=ro`でのSELECTのみ。`INSERT`/`UPDATE`/`DELETE`/`PRAGMA journal_mode`変更等は一切実行していない)
- `ansible <host> -b -m command -a "whoami"`(become先identityの確認)
- `ansible <host> -m command -a "journalctl -u grafana-server --no-pager -n 0"`(0件表示、権限ヒントのみ。初版から特権では未試行)

いずれもファイル追加・変更・削除、DB書込、provisioning reload、`grafana-server`のrestart/reload、パッケージ導入、サービス状態変更、group membership/sudoers等の恒久的な権限変更を伴わない。**`become`(sudo)は今回Coordinatorの承認を受けて使用したが、使途はすべて`cat`/`sed`/`sqlite3 SELECT`によるread-onlyアクセスに限られる。** `ann`をgrafana groupへ追加する、sudoers設定を変える、といった恒久的な権限付与は行っていない。

Slack webhookの値(`secureSettings.url`)は、DBから読み出したJSONをプログラム側で出力前に`<redacted-present>`へ置換してから表示しており、生の暗号化値・復号値のいずれも一度もターミナル出力・本書に現れていない。存在の有無(キーが存在すること)のみを記載している。Grafanaの資格情報・tokenは取得していない。

1件、`ansible monnie -m command -a "sh -c 'id ann; groups ann'"`(read-only)がClaude Code auto modeの分類器にブロックされた(初版時点)。すでに別コマンドで`id`(ann自身の呼び出し)の結果を得ていたため、別の形での取得は試みず、この事実のみを記録する。また今回の追加調査でも、`ansible -b -m command -a "id"`単体の呼び出しが1回ブロックされたが、直後に別の具体的な読み取りコマンド(`cat unifi.yaml`)は許可された。ブロックされた`id`の代替として別の形を探すことはせず、実際に必要だった読み取りをそのまま個別に実行した。

repoの作業ツリーへの変更は本ファイル1点のみ。`docs/ai/status.md`の未ステージ変更は本調査開始前から存在していたもので、今回のセッションでは触れていない。`git add` / `commit` / `push`は行っていない。IPアドレスは本書に記載していない。
