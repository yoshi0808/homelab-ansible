# Alloy Phase 2: pve syslog read-only reconnaissance

- 実施日: 2026-07-17
- 測定時刻: 2026-07-17T07:44:59+09:00
- 対象: `pve1`, `pve2`
- 実施者: tester
- 制約: read-only。package install、設定変更、service 操作は実施しない。

## 結論

1. `pve1` / `pve2` ともに **rsyslog は未導入**。`rsyslog.service` も存在しない。
   したがって、journald から rsyslog 経由で転送する設計には rsyslog package の新規導入が必要。
2. `/etc/systemd/journald.conf` の `ForwardToSyslog` と `MaxLevelSyslog` は双方とも
   コメントアウトされた既定値のまま。drop-in directory は存在しない。
3. `syslog.socket` unit file は存在するが inactive (dead) で、現在 listen していない。
4. `rsyslog` と `systemd-journal-remote` は双方とも標準 Debian / Proxmox の既存
   repository から candidate を取得できる。repository 追加は不要。
5. 直近 1 時間の journal は `pve1` が 1,147 行、`pve2` が 787 行。warning..err は
   それぞれ 1 行であり、観測時点の全ログ流量は概ね 13--19 行/分。

## 1. rsyslog 導入・service 状態

両ノードで同一結果だった。

| 項目 | pve1 | pve2 |
|---|---|---|
| `dpkg-query` | package not found | package not found |
| `systemctl is-active rsyslog` | inactive | inactive |
| `systemctl is-enabled rsyslog` | not-found | not-found |
| service unit | not found | not found |
| `/etc/rsyslog.conf` | missing | missing |
| `/etc/rsyslog.d` | exists | exists |

`/etc/rsyslog.d` には両ノードとも次のファイルが存在したが、rsyslog package / service
自体は存在しない。

```text
/etc/rsyslog.d/45-frr.conf
/etc/rsyslog.d/postfix.conf
```

このため「既存 rsyslog を設定だけで再利用でき、新規モジュール導入不要」という前提は
成立しない。rsyslog 方式を採用する場合、少なくとも package 導入と service 有効化が
Phase 2 の変更対象になる。

## 2. journald の syslog 転送設定

両ノードの `/etc/systemd/journald.conf` は同一だった。

```ini
#ForwardToSyslog=no
#MaxLevelSyslog=debug
```

- `/etc/systemd/journald.conf.d`: 両ノードとも missing
- 明示 override: なし
- `ForwardToSyslog`: コメントアウト。systemd の既定値 `no` が有効
- `MaxLevelSyslog`: コメントアウト。syslog 転送を有効にした場合の既定上限 `debug`

## 3. syslog.socket

両ノードで unit file は `/usr/lib/systemd/system/syslog.socket` から load されるが、
状態は `inactive (dead)` だった。

```text
Loaded: loaded (.../syslog.socket; static)
Active: inactive (dead)
Triggers: syslog.service
Listen: /run/systemd/journal/syslog (Datagram)
```

`systemctl list-sockets syslog.socket` も `0 sockets listed`。現在は syslog socket による
受け渡しは動作していない。

## 4. 代替 package の在庫

`apt-cache policy` の結果は両ノードで同一だった。`apt update` は実行していないため、
現在のローカル package index に基づく結果である。

| package | installed | candidate | candidate source |
|---|---:|---:|---|
| `rsyslog` | none | `8.2504.0-1` | Debian trixie/main |
| `systemd-journal-remote` | none | `257.13-1~deb13u1` | Debian trixie/main および Proxmox pve-no-subscription |

どちらも既存 repository から導入可能で、package 入手のための repository 追加は不要。
ただし本調査では install を実施していない。

## 5. 直近 journal 流量

測定コマンドは `journalctl --since=-1hour --no-pager | wc -l` と
`journalctl -p warning..err --since=-1hour --no-pager | wc -l`。

| host | 全 priority / 1h | warning..err / 1h | 全 priority の概算平均 |
|---|---:|---:|---:|
| pve1 | 1,147 行 | 1 行 | 19.1 行/分 |
| pve2 | 787 行 | 1 行 | 13.1 行/分 |

これは単一時点・直近 1 時間の目安であり、更新、backup、cluster event などのピーク流量は
含まれない可能性がある。転送容量設計には余裕を持たせる必要がある。

## 6. 既存 rsyslog drop-in と FRR / Postfix の影響

011 review の must-fix 判断材料として追加調査した。以下は pve1 / pve2 で完全に同一だった。

### 6.1 /etc/rsyslog.d/45-frr.conf の完全な内容

~~~text
# The lines below cause all FRR daemons and process to go
# to /var/log/frr/frr.log, then drops the message so it does
# not also go to /var/log/syslog, so the messages are not duplicated

$outchannel frr_log,/var/log/frr/frr.log
if  $programname == 'babeld' or
    $programname == 'bgpd' or
    $programname == 'bfdd' or
    $programname == 'eigrpd' or
    $programname == 'frr' or
    $programname == 'isisd' or
    $programname == 'fabricd' or
    $programname == 'ldpd' or
    $programname == 'mgmtd' or
    $programname == 'nhrpd' or
    $programname == 'ospf6d' or
    $programname == 'ospfd' or
    $programname == 'pimd' or
    $programname == 'pim6d' or
    $programname == 'pathd' or
    $programname == 'pbrd' or
    $programname == 'ripd' or
    $programname == 'ripngd' or
    $programname == 'vrrpd' or
    $programname == 'watchfrr' or
    $programname == 'zebra'
    then :omfile:$frr_log

if  $programname == 'babeld' or
    $programname == 'bgpd' or
    $programname == 'bfdd' or
    $programname == 'eigrpd' or
    $programname == 'frr' or
    $programname == 'isisd' or
    $programname == 'fabricd' or
    $programname == 'ldpd' or
    $programname == 'mgmtd' or
    $programname == 'nhrpd' or
    $programname == 'ospf6d' or
    $programname == 'ospfd' or
    $programname == 'pimd' or
    $programname == 'pim6d' or
    $programname == 'pathd' or
    $programname == 'pbrd' or
    $programname == 'ripd' or
    $programname == 'ripngd' or
    $programname == 'vrrpd' or
    $programname == 'watchfrr' or
    $programname == 'zebra'
    then stop
~~~

これは input/module 宣言ではなく、program name による**出力・停止ルール**である。

- 対象: 列挙された FRR daemon の message
- facility selector: なし。facility ではなく $programname で判定
- 出力先: /var/log/frr/frr.log (omfile)
- 後続処理: 同じ program name の message を stop
- 効果: FRR message を専用 fileへ書き、後続の /var/log/syslog 等へ重複させない

rsyslog packageを導入してこの既存 drop-in が読み込まれると、FRR message は上記専用 fileへ
routeされ、後続 ruleや新しい remote-forward ruleの配置順によっては remote転送へ到達しない。
Phase 2 が journald 全体の転送を rsyslog で行う設計なら、既存 stop との順序を明示的に扱う
必要がある。

### 6.2 /etc/rsyslog.d/postfix.conf の完全な内容

~~~text
# Create an additional socket in postfix's chroot in order not to break
# mail logging when rsyslog is restarted.  If the directory is missing,
# rsyslog will silently skip creating the socket.
$AddUnixListenSocket /var/spool/postfix/dev/log
~~~

これは file出力 ruleではなく、Postfix chroot内へ追加 Unix syslog socketを作る**input宣言**である。

- socket: /var/spool/postfix/dev/log
- facility selector / 出力先: このファイル内には無し
- directoryが無い場合: コメント記載どおり rsyslog は socket作成をskip

rsyslog導入・起動時には、この socketが存在すれば chroot内 Postfix processのsyslog messageを
受けるようになる。messageの最終出力先は、このファイルではなく rsyslog の後続 ruleで決まる。

### 6.3 package / service / 現在のログ

| 項目 | pve1 | pve2 |
|---|---|---|
| frr package | installed, 10.6.1-1+pve2 | installed, 10.6.1-1+pve2 |
| frr.service | inactive | inactive |
| journalctl -u frr -n 5 | no entries | no entries |
| /var/log/frr | exists, fileなし | exists, fileなし |
| postfix package | installed, 3.10.12-0+deb13u2 | installed, 3.10.12-0+deb13u2 |
| postfix.service | active | active |
| journalctl -u postfix -n 5 | service停止・起動、master起動を記録 | service停止・起動、master起動を記録 |

観測時点では FRR は停止しており、journal entryも専用 log fileも無い。Postfix は activeで、
journalには systemd の service lifecycle と postfix/master の daemon startが記録されている。
rsyslogは未導入なので、既存2 drop-inはいずれも現在は読み込まれていない。

## 設計判断への示唆

- rsyslog 方式:
  - 既存 repository だけで導入可能。
  - ただし両 pve への package 新規導入、journald forwarding の明示設定、service / socket
    有効化が必要となり、「設定追加のみ」ではない。
  - 既存 45-frr.conf の専用file出力 + stop と、新規 remote-forward ruleの順序を設計する。
  - 既存 postfix.conf による chroot内 Unix socketを前提に、Postfix logの重複・欠落が
    ないことを導入後に確認する。
- `systemd-journal-remote` 方式:
  - package candidate は存在するが未導入。採用時は receiver / upload transport と Loki への
    取り込み経路を別途設計する必要がある。
- ローカル Alloy journal reader 方式:
  - journald→syslog の設定変更は不要で、現在の Phase 2 要件にある
    `loki.source.journal` と整合する。
  - Alloy package source と Loki TCP 3100 firewall の課題は別途残る。

## 実行方法と安全性

Ansible ad-hoc の `command` / `shell` module で read-only command のみ実行した。
`shell` module は表示上 `CHANGED` になるが、対象ホストの package、file、service、socket を
変更していない。

実行対象:

```text
dpkg-query -W rsyslog
systemctl is-active/is-enabled/status rsyslog
ls/find /etc/rsyslog.conf /etc/rsyslog.d
grep ForwardToSyslog/MaxLevelSyslog in journald.conf and drop-ins
systemctl status/list-sockets syslog.socket
apt-cache policy rsyslog systemd-journal-remote
journalctl --since=-1hour (all and warning..err) | wc -l
cat /etc/rsyslog.d/45-frr.conf /etc/rsyslog.d/postfix.conf
dpkg-query -W frr postfix
systemctl is-active frr postfix
journalctl -u frr -u postfix -n 5
ls/find /var/log/frr
```

## 未実施

- `apt update` / package install or removal
- file create / edit / delete
- service start / stop / restart / reload / enable / disable
- socket activation
- journald / rsyslog / Alloy configuration change
- network connection or test log transmission
- monnie 側の変更・再調査

IP address literal は本書に記録していない。
