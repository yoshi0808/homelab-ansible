# Grafana 13.1 更新後の UniFi dashboard エラー調査

- 日付: 2026-07-12
- 担当: tester
- 対象: monnie / Grafana 13.0.2 -> 13.1.0（Semaphore task 325）
- 調査境界: **read-only のみ**
- 実施していないこと: service restart、設定変更、dashboard変更、復旧操作

## 結論

**unpoller -> Prometheus のデータ経路は生存しており、原因層は Grafana
dashboard/panel 互換性が最有力。**

2026-07-12 17:47 JST 時点で、Prometheus の unifi-poller targetは `up`、
`lastError=""`、scrapeは15秒間隔で更新。unpollerは再起動8秒後から UniFi
controllerのデータを `Err: 0` で継続出力し、代表 PromQL も値を返す。

一方、Techno Tim 系の provisioned dashboard JSON は古いschemaと大量の
legacy panel ID を保持している。集計で `graph` 330件、`singlestat` 13件、
`table-old` 9件、`piechart` 8件、その他 `grafana-clock-panel` 1件。
`grafana-cli plugins ls` は `no installed plugins found` で、少なくとも
`grafana-clock-panel` は別途install済みとは確認できない。

Grafana 13.1 起動ログでは React 19 / dynamic dashboard系の feature が有効で、
Grafana公式によれば v13 では旧dashboardが開かれた際に新schemaへ移行される。
しかし本環境の source of truth は 2026-05-26 の古いファイルprovisioning
JSONであり、自動移行は保存しない限り次回load時に再実行される。
この「古い provisioned JSON + legacy panel + Grafana 13.1 の自動移行/新UI」の
境界でpanelレンダリングエラーが起きた仮説が、時系列と証拠に最も合う。

ただし、panel のフロントエンド例外は Grafana server journal に必ずしも出ない。
今回のjournalに `Panel plugin not found` 等の直接エラーはなく、
UIに表示される正確なエラー文言/対象panelが未取得のため、個別panel IDまでの
断定はできない。

## 仮説の優先順位

| 順位 | 仮説 | 評価 | 根拠 |
| ---: | --- | --- | --- |
| 1 | ③ Grafana 13.1 と旧dashboard/panelの互換性 | **高** | エラー発生とGrafana更新/再起動が同時。データ経路は健全。古いschemaとlegacy panelが多数 |
| 2 | ④ その他：provisioned dashboard と v13 unified storage/dynamic dashboard 移行の境界 | **中〜高** | v13で旧SQL dashboardをunified storageへ自動移行。本dashboardは旧JSONから毎回provision |
| 3 | ① unpoller再起動後のUniFi接続失敗 | **低** | restart後8秒でcontrollerを発見、以後15秒ごとに`Err: 0`、controller_up=1 |
| 4 | ② Prometheus scrape断 | **非常に低い** | target=`up`、lastError空、2189 series、最新timestampが現在時刻に追従 |

補足:

- ③の中でも、`graph` / `singlestat` / `table-old` は Grafana が自動移行対象と
  しているcore panel。したがって「legacy IDがあるから必ず破損」ではなく、
  **provisioned JSONの自動移行結果と新UIの組み合わせ**を疑う。
- `grafana-clock-panel` は外部panel IDであり、plugin未導入ならそのpanelは
  直接的にエラー候補。ただし参照は `UniFi Access Points` 内の1件だけで、
  dashboard全体のエラーを単独で説明するかはUI文言が必要。
- 13.0.2でも旧panelはすでに旧式だったため、「13.1でAngularが初めて削除」
  という説明は不正確。Angular完全削除はv12。疑うべきは13.1起動時の
  migration/React 19/dynamic dashboard 経路または欠落plugin。

## A. データ経路

### Prometheus target

Prometheus の実configは systemd unit より `/opt/prometheus/prometheus.yml`。
UniFi scrape target:

```text
job: unifi-poller
scrapeUrl: http://localhost:9130/metrics
health: up
lastError: ""
scrapeInterval: 15s
lastScrape: 2026-07-12 17:33:49 JST（初回調査時）
```

`curl -fsS http://localhost:9130/metrics` は成功し、unpoller/process metricに加え
UniFi metricも出力している。

### Prometheus query

```bash
curl -fsSG http://localhost:9090/api/v1/query \
  --data-urlencode 'query=count({job="unifi-poller"})'
```

```text
series count: 2189
```

metricの最新sample timestamp:

```text
unpoller_controller_up:         2026-07-12 17:47:19 JST
unpoller_site_aps:              2026-07-12 17:47:19 JST
unpoller_client_uptime_seconds: 2026-07-12 17:47:19 JST
```

16:32 以降も更新継続中。代表query:

```text
unpoller_controller_up = 1
sum(unpoller_site_aps) = 2
count(unpoller_client_uptime_seconds) = 34
```

dashboard内で使われる代表式もPrometheus APIでsuccess/valueあり。

## B. service / journal

### unpoller

apt transactionは `unpoller 3.3.1+git -> 3.3.1+git` を含み、16:33:10 JST に
serviceがrestartした。

```text
16:33:10 UniFi Poller v3.3.1 Starting Up
16:33:10 Found 1 site(s) on controller
16:33:10 controller version 10.4.57
16:33:11 Prometheus exported at http://0.0.0.0:9130/
16:33:19 UniFi Measurements Exported ... Metric: 2147 ... Err: 0
```

以後15秒ごとに出力が継続。認証失敗、connection refused、timeoutなし。

### Prometheus

Prometheusは2026-07-05から稼働継続で、task 325 でrestartしていない。
targetは unpoller restart後に自動復帰し、現在up。

### Grafana

Grafanaは16:32:57に正常shutdown/restartし、同時刻に13.1.0が起動。

```text
Starting Grafana version=13.1.0
HTTP Server Listen address=[::]:3000 protocol=https
```

startup migrationは成功し、致命的なplugin/provisioning errorは見つからない。
shutdown時の `context canceled`、session token rotate warning、Loki alerting APIの400は観測したが、
UniFi Prometheus dashboardの原因を直接示す証拠ではない。

## C. Grafana dashboard / plugin

### plugin

```text
grafana-cli plugins ls
no installed plugins found
```

Grafana起動後に zipkin / lokiexplore / elasticsearch 等のbackground install/updateログは
あるが、UniFi dashboardが参照する `grafana-clock-panel` のinstall証跡はない。

### provisioned dashboard

source:

```text
/etc/grafana/provisioning/dashboards/unifi.yaml
/var/lib/grafana/dashboards/unifi-*.json
```

7 dashboardのうち6個はschemaVersion 22〜39。`UniFi PDU` のみ現代的な
`timeseries/stat/table/gauge` 構成。他はlegacy panelを大量に含む。

| panel type | 件数 |
| --- | ---: |
| `graph` | 330 |
| `singlestat` | 13 |
| `table-old` | 9 |
| `piechart` | 8 |
| `grafana-clock-panel` | 1 |
| modern `timeseries` | 4 |

dashboard内のPromQLは `unpoller_*` metricを参照し、代表metricは現在も
Prometheusに存在し値を返す。

## 公式情報との突合

- Grafana v12 でAngular supportは完全削除され、core Angular panelは新panelへ
  自動移行対象となった。[Grafana: Removal of Angular](https://grafana.com/whats-new/2025-05-05-removal-of-angular/)
- 公式の移行表は Graph(old)->Time series/Bar chart等、Singlestat->Stat、
  Table(old)->Table を自動移行対象とするが、保存しなければloadごとに
  migrationが再実行されると注意している。[Grafana: AngularJS removal guidance](https://grafana.com/blog/angularjs-support-will-be-removed-in-grafana-12-what-you-need-to-know/)
- Grafana v13はReact 19を使い、旧dashboardをunified storageへ自動移行する。
  [Grafana v13 upgrade guide](https://grafana.com/docs/grafana/latest/upgrade-guide/upgrade-v13.0/)
- Grafana v13でdynamic dashboardsが既定となり、既存dashboardは開くと新schemaへ
  自動移行される。[Grafana v13 what's new](https://grafana.com/docs/grafana/latest/whatsnew/whats-new-in-v13-0/)

これらは「古いprovisioned dashboardの互換性」を強く疑う根拠だが、
Grafana 13.1.0 の既知不具合または特定panelの例外を単独で立証するものではない。

## 次に必要な確認（本調査では未実施）

復旧操作ではなく、原因を確定するための追加観測候補:

1. UIの正確なエラー文言、dashboard名/UID、panel title/type、browser console stackを取得。
2. `UniFi PDU`（modern panelのみ）と `UniFi Access Points`（legacy panel多数）の
   表示差を比較。PDUだけ正常ならlegacy migration仮説が強まる。
3. Access Points のエラーがclock panelのみか確認。
   `Panel plugin not found: grafana-clock-panel` ならplugin欠落が直接原因。
4. Grafana UIの Explore から代表 PromQL を実行し、datasource経路と
   dashboard frontend を分離。

上記は追加観測の提案のみで、今回は実施していない。

## 追記: UIエラー文言と復元DBによる絞り込み

Yoshinobu の UI 目視で正確な症状が得られた。

```text
Data source prometheus not found
Plugin grafana-clock-panel not found
```

Loki datasource を使う自作dashboardは正常。この追加情報により、
原因は「Grafana全体の故障」ではなく **UniFi dashboardの datasource/plugin
参照解決** に絞られた。

### datasource参照の事実

VM復元後（Grafana 13.0.2）の `/var/lib/grafana/grafana.db` を immutable/read-only
で確認した。ホストに `sqlite3` CLI がないため、Python標準の sqlite3 を
`mode=ro` で使用した。

```text
id=1  uid=ffn83gysyghs0c  name=prometheus  type=prometheus  url=http://localhost:9090
id=2  uid=ffn86ietu7jeoc  name=loki        type=loki        url=http://localhost:3100
```

Prometheus datasourceの実nameは小文字 `prometheus`、実UIDは
`ffn83gysyghs0c`。これに対して provisioned UniFi JSON の参照は次の通り。

| dashboard | datasource参照 |
| --- | --- |
| Access Points | 旧式文字列 `"Prometheus"` 34件 |
| Clients | 旧式文字列 `"Prometheus"` 27件 |
| DPI | 旧式文字列 `"Prometheus"` 278件 |
| Gateway | 旧式文字列 `"Prometheus"` 22件 + `${DS_UNIFI_POLLER}` 2件 |
| Sites | 旧式文字列 `"Prometheus"` 15件 |
| Switches | 旧式文字列 `"Prometheus"` 22件 |
| PDU | 新式object `{"type":"prometheus","uid":"Prometheus"}` 37件 |

どちらもDBの実値と一致しない。

- name: `Prometheus` != `prometheus`（case差）
- UID: `Prometheus` != `ffn83gysyghs0c`

一方、正常なLoki経路のGrafana logは `dsUID=ffn86ietu7jeoc`と、
DBの実UIDでqueryして HTTP 200 を受けている。

VM復元後の Grafana 13.0.2 では同じ UniFi JSON の表示が回復したため、
13.0.2 は旧式文字列参照に対し、nameのcase差または従来fallbackで
datasourceを解決できていた。Grafana 13.1.0 ではこの参照が
`Data source prometheus not found` となった。

### plugin参照の事実

`/var/lib/grafana/plugins` に `grafana-clock-panel` directory/plugin.json は存在しない。
UniFi Access Points JSON は `grafana-clock-panel` を1件参照しており、
UIの `Plugin grafana-clock-panel not found` と完全に一致する。

これは少なくともclock panelについては直接原因が確定。ただし、
datasource参照エラーとは別件であり、全panelの赤エラーは後者で説明できる。

### 起動ログ / package境界

Grafana 13.1起動ログでは plugin scan、DB migration、provisioning の致命的エラーは
なかった。したがって「datasource row消失」や「dashboard import失敗」よりも、
frontend/load時の参照解決振る舞い変化と整合する。

Debian packageの `dpkg -L grafana` で `/var/lib/grafana` 配下の個別fileは所有されず、
`/etc/grafana` directoryのみが表示された。apt/dpkg logはpackage交換を示すが、
dashboard JSON / grafana.db / plugin directoryを削除した証跡はない。

### 更新後の原因判定

1. **全UniFi panelの主原因（高確度）**:
   Grafana 13.1.0 で旧式 datasource 文字列 `"Prometheus"` から、
   実name=`prometheus` / 実UID=`ffn83gysyghs0c` へのcase-insensitive/従来fallback
   解決が機能しなくなった。正確に仕様廃止か13.1 regressionかは、
   Grafanaのコード/既知issue確認が必要。
2. **Access Points内clock panelの別原因（確定）**:
   JSONが参照する `grafana-clock-panel` が未導入。
3. unpoller / Prometheus / Loki / Grafana server全体の停止は否定。

本追記で、当初の「古いdashboard/panel互換性」仮説を、
**datasource参照形式/大文字小文字/UID不一致** まで絞り込んだ。

## 解決記録（claude 追記、実施者: Yoshinobu、2026-07-12）

### 追加確定事実（tester 追加調査）

- 実 datasource: `name=prometheus`（小文字）、`uid=ffn83gysyghs0c`
- UniFi 系 JSON は旧式文字列 `"Prometheus"`（大文字）を参照。唯一 modern な
  UniFi PDU も object 形式ながら `uid` に実UIDでなく文字列 `"Prometheus"`。
  一部パネルは `${DS_UNIFI_POLLER}` / `${DS_PROMETHEUS}` の import 入力
  プレースホルダを未解決のまま保持
- 正常表示を維持した Loki ダッシュボード（自作）は実UIDを正しく参照
- 結論: **13.0.2 までの name ベース（大文字小文字非依存）の datasource
  fallback 解決が 13.1 で廃止/退行**し、全パネルが
  `Data source prometheus not found` となった。`grafana-clock-panel` は
  プラグイン自体が未インストールで、当該1パネルは更新前から不表示
  （今回の障害とは独立の既存事象）

### 実施した復旧（時系列）

1. Proxmox VM バックアップ（apply 前 16時台取得）から monnie を復元
   → grafana 13.0.2 に戻り表示回復（復元前に quory で
   `homelab-mute set monnie 60` を手動設定、ladder 非発火）
2. monnie で `sudo apt-mark hold grafana`（再発防止）
3. grafana hold 下で monnie 再 apply（Semaphore task 326、22件適用、
   検証合格 → 2026-07-12_027_test_result.md）
4. **恒久対応: datasource 参照の UID 置換**。7つの provisioned JSON
   （/var/lib/grafana/dashboards/unifi-*.json）内の legacy 参照
   （`"Prometheus"` / `"prometheus"` / `${DS_PROMETHEUS}` /
   `${DS_UNIFI_POLLER}` / object 内 uid 誤り / `-- Grafana --`）を
   jq walk で `{"type":"prometheus","uid":"ffn83gysyghs0c"}`
   （`-- Grafana --` は `{"type":"datasource","uid":"grafana"}`）へ機械置換。
   置換前バックアップ: `/var/lib/grafana/dashboards-backup-<timestamp>`
5. 置換後の残存 legacy 文字列参照 0 件を grep で確認、13.0.2 上で
   ダッシュボード表示に変化がないことを Yoshinobu が目視確認

### 残タスク

- 次回月次のタイミングで `sudo apt-mark unhold grafana` → 13.1+ へ更新し、
  UID 参照化されたダッシュボードが 13.1 で表示されることを最終確認
  （core legacy panel（graph 等）の自動移行は公式サポート範囲）
- 任意: `grafana-clock-panel` の導入（未導入のままなら該当1パネルは不表示のまま）
- 任意: 上流リポ（timothystewart6/unpoller-unifi）への issue 報告
- Techno Tim が上流を修正した場合、再適用前に参照形式（UID か name か）を確認する

### 最終検証（2026-07-12 夜、Yoshinobu実施）

UID置換後の検証として grafana を unhold し 13.1 系へ再更新
（`grafana.db` は事前退避）。結果:

- UniFi ダッシュボード7枚すべて正常描画（Switches / Access Points 含む）
- Loki 自作ダッシュボードも正常
- Alert rules は登録済み・Normal 状態を確認（発火なし=正常）
- clock-panel も表示（プラグイン導入済みのため）

**インシデントクローズ。** grafana は unhold のまま運用に復帰し、
以後の月次 full-upgrade で通常どおり更新対象となる。

長期メモ: provisioned JSON には legacy panel 型（graph 等）自体は残って
おり、現状は Grafana の自動移行で描画されている。将来のメジャー更新で
この自動移行が廃止された場合は再発しうるため、上流
（timothystewart6/unpoller-unifi）の modern 化、または Export ベースの
JSON 全面更新が長期課題として残る。
