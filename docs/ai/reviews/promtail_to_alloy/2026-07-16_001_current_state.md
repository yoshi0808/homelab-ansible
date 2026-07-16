# Promtail → Grafana Alloy 移行前の現状調査

- 日付: 2026-07-16
- 担当: `tester`
- 対象: `monnie`, `cloudkey`
- 実施範囲: read-only 採取のみ

## 結論

現在の UniFi syslog → Loki 経路は、Promtail が syslog socket を直接受ける構成ではない。

```text
UniFi controller / adopted devices
  -> UDP 514 on monnie (rsyslog imudp)
  -> /var/log/unifi.log または /var/log/unifi-devices.log
  -> Promtail file tail
  -> http://localhost:3100/loki/api/v1/push
  -> Loki
```

Promtail は apt で導入された v3.6.11 の native systemd service で、Docker 併用は無い。
active config は `/etc/promtail/config.yml`、positions は
`/var/lib/promtail/positions.yaml`、実行 user は `promtail`。

CloudKey の UniFi `ace.setting` には、site-scoped の `rsyslogd` document があり、
remote syslog は enabled、送信先は monnie の IPv4 address、port 514 である。
送信先 address と CloudKey 上での `monnie.internal` の解決結果は一致した。

IP address は本ファイルですべてマスクした。token / password は config と採取結果に
存在しなかった。書込、設定変更、再起動、パッケージ操作は一切実施していない。

## monnie: インストール方式と version

### パッケージ

```text
dpkg status: ii
package: promtail
installed: 3.6.11
candidate: 3.6.11
architecture: amd64
origin: https://apt.grafana.com stable/main
binary: /usr/bin/promtail
```

`promtail --version`:

```text
promtail, version 3.6.11
branch: release-3.6.x
revision: f7a4aa99
platform: linux/amd64
tags: promtail_journal_enabled
```

Grafana Labs apt repository:

```text
/etc/apt/sources.list.d/grafana.list
deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main
```

`docker` command は未導入であり、Promtail の container 併用は無い。

## monnie: systemd service

Unit file: `/etc/systemd/system/promtail.service`

```ini
[Unit]
Description=Promtail service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=promtail
ExecStart=/usr/bin/promtail -config.file /etc/promtail/config.yml
TimeoutSec = 60
Restart = on-failure
RestartSec = 2

[Install]
WantedBy=multi-user.target
```

採取時の状態:

- `systemctl is-enabled promtail`: `enabled`
- `ActiveState`: `active`
- `SubState`: `running`
- 実行 user: `promtail`
- 明示 `Group=`: 無し（service user の default group）
- command: `/usr/bin/promtail -config.file /etc/promtail/config.yml`
- status log は `/var/log/unifi.log` の tail routine 起動を示していた。

## monnie: active Promtail config

Config path は unit の `ExecStart` から `/etc/promtail/config.yml` と特定した。
採取時 metadata は `root:root`, mode `0664`。

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/lib/promtail/positions.yaml

clients:
  - url: http://localhost:3100/loki/api/v1/push

scrape_configs:
  # UniFi controller logs written by rsyslog
  - job_name: unifi
    static_configs:
      - targets: [localhost]
        labels:
          job: "unifi"
          host: "uckg2"
          __path__: /var/log/unifi.log

  # monnie systemd journal
  - job_name: monnie
    journal:
      max_age: 12h
      labels:
        job: "system"
        host: "monnie"
    relabel_configs:
      - source_labels: [__journal__systemd_unit]
        target_label: unit

  # switch / AP logs written by rsyslog
  - job_name: network-devices
    static_configs:
      - targets: [localhost]
        labels:
          job: "network-devices"
          __path__: /var/log/unifi-devices.log
    pipeline_stages:
      - regex:
          expression: '^\S+ (?P<host>\S+) '
      - labels:
          host:
```

確認事項:

- `syslog` receiver block: 無し
- syslog `listen_address` / `listen_port`: 無し
- syslog transport (`tcp` / `udp`) 設定: 無し
- `idle_timeout`: 無し
- `label_structured_metadata`: 無し
- `__syslog_*` label の `relabel_configs`: 無し
- `relabel_configs` は journal の `__journal__systemd_unit` → `unit` のみ
- UniFi device pipeline は log line の2番目の token を `host` label にする regex + labels
- client は local Loki の `/loki/api/v1/push`。credential / token 無し

Positions:

```text
/var/lib/promtail/positions.yaml
owner: promtail:nogroup
mode: 0600
```

## monnie: syslog listener と rsyslog handoff

`ss -ltnup` の採取結果:

| process | transport | port | 用途 |
| --- | --- | --- | --- |
| `rsyslogd` | UDP | 514 | UniFi syslog receiver。IPv4/IPv6 wildcard bind |
| `promtail` | TCP | 9080 | Promtail HTTP server |
| `promtail` | TCP | dynamic port | config の `grpc_listen_port: 0` に対応する process socket。syslog receiver ではない |
| `loki` | TCP | 3100 | local Loki HTTP endpoint |

Promtail process が UDP 514 を listen している事実は無い。syslog receiver は rsyslog。

`/etc/rsyslog.d/10-unifi.conf` の構造:

```text
module(load="imudp")
input(type="imudp" port="514")

CloudKey source address 1件
  -> /var/log/unifi.log

switch / AP source addresses 6件
  -> /var/log/unifi-devices.log
```

source address literal はマスクしている。実 config は `$fromhost-ip` の allowlist を使い、
match 後に `omfile` へ書いて `stop` する。rsyslog は `active` / `enabled`。

採取時 log file metadata:

```text
/var/log/unifi.log          owner syslog:syslog, mode 0644, non-empty
/var/log/unifi-devices.log  owner syslog:syslog, mode 0644, non-empty
```

## cloudkey: UniFi controller remote syslog setting

MongoDB client は `/usr/bin/mongo`。`ace.setting` を `find` のみで調査した。

最初に setting key / site_id の projection を取得し、`key: "rsyslogd"` が
site_id 付きで存在することを確認した。次に document の field names のみを確認し、
必要 field だけを projection した。

```javascript
db.setting.find(
  {key: "rsyslogd"},
  {
    _id: 0,
    key: 1,
    site_id: 1,
    enabled: 1,
    ip: 1,
    port: 1,
    debug: 1,
    log_all_contents: 1,
    netconsole_enabled: 1,
    netconsole_host: 1,
    netconsole_port: 1,
    this_controller: 1,
    this_controller_encrypted_only: 1
  }
).forEach(printjson)
```

結果:

| field | value |
| --- | --- |
| `key` | `rsyslogd` |
| `site_id` | `[MASKED_SITE_ID]`（non-null） |
| `enabled` | `true` |
| `ip` | `[MASKED_MONNIE_IPV4]` |
| `port` | `514` |
| `log_all_contents` | `true` |
| `this_controller` | `false` |
| `this_controller_encrypted_only` | `false` |
| `debug` | `false` |
| `netconsole_enabled` | `false` |
| `netconsole_host` | 空 |
| `netconsole_port` | `514` |

CloudKey 上の `getent ahostsv4 monnie.internal` 結果と `ip` field は一致した。
したがって controller の remote syslog destination は monnie と確認できる。

`rsyslogd` document に non-null `site_id` があるため、これは少なくとも controller の
site setting であり、単一 device document の個別設定ではない。今回 device collection の
override 有無までは調査していない。

Mongo document 内に transport field は無かった。monnie 側の実 receiver が
`imudp` / UDP 514 で、実 log file が増加済みであることから、現在の実経路は
UDP 514 と判断できる。

## Alloy 移行時に保持すべき現状契約

- UniFi controller の送信先: monnie, port 514
- network transport: UDP（monnie rsyslog `imudp`）
- rsyslog の source-address allowlist と2ファイルへの振り分け
- `/var/log/unifi.log` → `job=unifi`, `host=uckg2`
- `/var/log/unifi-devices.log` → `job=network-devices`
- device log pipeline の host 抽出 regex
- monnie journal → `job=system`, `host=monnie`, systemd unit → `unit`
- positions state の継続方針
- Loki push endpoint: local port 3100 `/loki/api/v1/push`

Alloy が file tail 部分だけを置換する場合、UDP 514 と source routing は rsyslog に残る。
rsyslog も置換対象にする場合は、UDP receiver、source address allowlist、2系統の labels / path
を Alloy 側で明示的に再現する必要がある。

## 実行コマンド概要

monnie（通常 Ansible + become、すべて read-only）:

```bash
dpkg -l promtail
apt-cache policy promtail
command -v promtail
promtail --version
docker ps --no-trunc
grep -RHiE 'grafana|packages\.grafana' /etc/apt/sources.list /etc/apt/sources.list.d
systemctl cat promtail
systemctl show promtail -p FragmentPath -p ExecStart -p User -p Group -p MainPID -p ActiveState -p SubState
systemctl is-enabled promtail
systemctl status promtail --no-pager -l
ss -ltnup
stat /etc/promtail/config.yml /var/lib/promtail/positions.yaml /var/log/unifi.log /var/log/unifi-devices.log
sed -n '1,400p' /etc/promtail/config.yml
grep -RniE 'imudp|imtcp|port=.*514|unifi' /etc/rsyslog.conf /etc/rsyslog.d
systemctl is-active rsyslog
systemctl is-enabled rsyslog
```

cloudkey（Vault password は認証にのみ使用、MongoDB は `find` のみ）:

```text
setting key / site_id projection
rsyslogd document field-name inspection
rsyslogd required-field projection
getent ahostsv4 monnie.internal
```

Ansible `shell` / `raw` module は read-only command でも表示上 `CHANGED` になるが、
対象状態は変更していない。最初の monnie probe は Docker format string の `{{...}}` を
Ansible が Jinja として解釈して controller 側で失敗し、host には到達しなかった。
format 指定を外した `docker ps --no-trunc` へ置き換えて再実行した。

## 未実施

- Grafana Alloy の package / version / config 設計
- Alloy の install / deploy / validate
- Promtail / rsyslog / Loki の restart / reload / stop
- apt update / install / remove
- config / unit / positions / log file の変更
- test syslog の送信
- UniFi controller DB の書込
- UniFi GUI 操作
- device collection の個別 syslog override 調査
