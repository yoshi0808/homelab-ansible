# Grafana Slack alert `source` controller URL 調査

- 実施日: 2026-07-18 (JST)
- 対象: monnie
- 調査方式: read-only
- 判定: `source` は **Unpoller exporter が controller URL から直接付与**

実 IP はすべて `https://<controller-ip>` としてマスクする。

## 1. 結論

Grafana Slack alert に表示される次の label は Prometheus の relabel で追加されたものではない。

```text
source="https://<controller-ip>"
```

Unpoller の controller 定義 `/etc/unpoller/up.conf` にある
`[unifi.defaults].url = "https://<controller-ip>"` が元データであり、Unpoller の
`localhost:9130/metrics` が `source` label として直接公開している。

Prometheus はその label を変更せず取り込む。`unifi-poller` scrape job に
`relabel_configs` / `metric_relabel_configs` はなく、runtime target labels にも `source` はない。

Grafana provisioning には有効な TX Drop alert rule と Slack contact point が存在しない。
実際に発火している alert/contact point は Grafana UI または API 経由で作成され、Grafana 内部 DB に
保存されている管理対象と判断した。依頼範囲どおり DB 直読みと認証付き API 呼び出しは行っていない。

## 2. Prometheus

### unit と実設定パス

`systemctl cat prometheus.service` と `systemctl show` の結果:

```text
unit:        /etc/systemd/system/prometheus.service
binary:      /opt/prometheus/prometheus
config.file: /opt/prometheus/prometheus.yml
tsdb.path:   /var/lib/prometheus
```

### unifi-poller scrape job

disk 上の設定:

```yaml
- job_name: unifi-poller
  static_configs:
    - targets:
        - localhost:9130
```

Prometheus `/api/v1/status/config` の loaded runtime config も同じ static target で、
scrape interval は 15 秒、metrics path は `/metrics`。

この job block には次のどちらも存在しない。

- `relabel_configs`: なし
- `metric_relabel_configs`: なし

`/api/v1/targets` の runtime target labels:

```text
discovered labels:
  __address__=localhost:9130
  __metrics_path__=/metrics
  __scheme__=http
  job=unifi-poller

final target labels:
  instance=localhost:9130
  job=unifi-poller
```

target は `health=up`、`lastError` は空。target relabel 段階に `source` はない。

## 3. Prometheus API の実ラベル

### source label values

read-only label values API:

```text
GET /api/v1/label/source/values
```

取り得る値は 1 件だった。

```text
https://<controller-ip>
```

### TX drop metric names

name values API で確認した TX drop 系 metric:

```text
unpoller_device_port_transmit_dropped_total
unpoller_device_stat_transmit_dropped_total
unpoller_device_switch_transmit_dropped_total
unpoller_device_vap_transmit_dropped_total
```

調査時点の instant vector series 数:

| metric | series |
|---|---:|
| `unpoller_device_port_transmit_dropped_total` | 27 |
| `unpoller_device_stat_transmit_dropped_total` | 4 |
| `unpoller_device_switch_transmit_dropped_total` | 5 |
| `unpoller_device_vap_transmit_dropped_total` | 17 |

### port TX drop の 1 series 全ラベル

instant query:

```promql
unpoller_device_port_transmit_dropped_total
```

取得した 1 series の全 Prometheus label set（識別名はマスク）:

```text
__name__  = unpoller_device_port_transmit_dropped_total
instance  = localhost:9130
job       = unifi-poller
name      = <switch-name>
port_id   = <switch-name> Port 1
port_name = <port-description>
port_num  = 1
site_name = Default (default)
source    = https://<controller-ip>
```

sample value は調査時点で `0`。

## 4. Unpoller

### unit と実設定パス

```text
unit:   /etc/systemd/system/unpoller.service
binary: /usr/bin/unpoller
config: /etc/unpoller/up.conf
```

service は active/running。実行引数は `unpoller -c /etc/unpoller/up.conf`。

### controller 定義

資格情報を除いた現行設定の該当箇所:

```toml
[prometheus]
disable = false
http_listen = "<all-addresses>:9130"
interval = "60s"

[unifi]
dynamic = false

[unifi.defaults]
url = "https://<controller-ip>"
sites = ["all"]
save_sites = true
```

現行設定に `name =` / `source =` の override はない。同梱 TOML/YAML/JSON example にも
controller の `name` / `source` key は見つからなかった。example で確認できる controller identity は
`url` で、複数 controller は `controllers` list の各 `url` で定義する。

site 表示名には `default_site_name_override` の例があるが、controller `source` label の override ではない。

### exporter 生データ

Prometheus を経由する前の `localhost:9130/metrics` に、すでに次の label が存在した。

```text
unpoller_device_port_transmit_dropped_total{
  name="<switch-name>",
  port_id="<switch-name> Port 1",
  port_name="<port-description>",
  port_num="1",
  site_name="Default (default)",
  source="https://<controller-ip>",
  ...
} 0
```

TX drop 系の exporter 生メトリクスで `source` の unique value は
`https://<controller-ip>` の 1 件。これにより `source` は Unpoller 由来と確定できる。

## 5. Grafana alerting / Slack

調査した provisioning path:

```text
/etc/grafana/provisioning/alerting
```

存在する file は `sample.yaml` だけ。非コメントの内容は `apiVersion: 1` のみだった。

- TX Drop / transmit dropped rule: provisioning file 内に該当なし
- Slack receiver/contact point: 有効な定義なし
- contact point template: sample のコメント例のみ、有効な template なし
- webhook/token: 読み出していない

したがって Slack alert の rule、annotation/template、contact point は file provisioning 管理ではない。
Grafana UI/API で作成され内部 DB に保存されている管理対象と判断する。今回の read-only/file-only
範囲では、その alert expression や Slack message template 本文までは取得していない。

## 6. source のデータフロー

```text
/etc/unpoller/up.conf
  [unifi.defaults].url = https://<controller-ip>
        ↓
Unpoller exporter localhost:9130/metrics
  source="https://<controller-ip>"
        ↓
Prometheus job="unifi-poller"
  relabel なしで source を保持
        ↓
Grafana の UI/DB-managed TX Drop alert
        ↓
Slack alert 文面の source
```

## 7. 変更有無

以下は一切実施していない。

- configuration write
- reload / restart
- Prometheus lifecycle API
- Grafana DB 直読み
- 認証付き Grafana API
- commit / push
