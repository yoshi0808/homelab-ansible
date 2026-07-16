# CloudKey / UniFi NTP 設定 read-only 調査

- 日付: 2026-07-16
- 担当: `tester`
- 対象: inventory `cloudkey_devices` の `cloudkey`
- 実施範囲: read-only 採取のみ

## 結論

- UniFi controller の `ace.setting` にある adopted device 向け NTP 設定は次のとおり。
  - `ntp_server_1`: `ntp.nict.jp`
  - `ntp_server_2`: `ntp.jst.mfeed.ad.jp`
  - `ntp_server_3`: `quory.internal`
  - `ntp_server_4`: 空
- CloudKey 自身の systemd-timesyncd 設定は上記とは別で、Ubiquiti pool 4件と
  Debian pool 4件を `Servers=` に指定している。
- CloudKey 自身は現在 `0.ubnt.pool.ntp.org` と同期しており、採取時 offset は
  `-221us`。時刻同期は成立している。
- CloudKey 上では `quory.internal` と `ntp.nict.jp` の双方を名前解決できた。
  したがって「AP が `quory.internal` を解決できない」現象は CloudKey 自身では
  再現せず、AP 側の DNS 到達性・名前解決設定・provision 反映状態を次段で確認する
  必要がある。

IP アドレスは本ファイルではすべてマスクしている。秘密情報は記録していない。

## 実行方法

Vault の `cloudkey_ssh_password` を Ansible の SSH 認証にのみ使用した。
CloudKey は `ansible_user=root` で、次の read-only `ansible.builtin.raw` コマンドを
実行した。raw module の表示上は `CHANGED` となるが、実行したコマンドに変更操作は
含まれず、ファイル・DB・サービスの状態は変更していない。

### Mongo client 確認

```bash
command -v mongo
command -v mongosh
```

結果:

- `mongo`: `/usr/bin/mongo`
- `mongosh`: 未導入

### UniFi controller DB

MongoDB の `ace` database / `setting` collection に対し、`key: "ntp"` の document を
`find` と field projection だけで取得した。

```javascript
db.setting.find(
  {key: "ntp"},
  {
    _id: 1,
    key: 1,
    ntp_server_1: 1,
    ntp_server_2: 1,
    ntp_server_3: 1,
    ntp_server_4: 1
  }
).forEach(printjson)
```

結果:

| field | value |
| --- | --- |
| `key` | `ntp` |
| `ntp_server_1` | `ntp.nict.jp` |
| `ntp_server_2` | `ntp.jst.mfeed.ad.jp` |
| `ntp_server_3` | `quory.internal` |
| `ntp_server_4` | 空文字 |

`insert` / `update` / `remove` / `delete` 等の書込操作は使用していない。

### CloudKey 自身の timesyncd

```bash
grep -nE '^[[:space:]#]*(Servers|FallbackNTP)=' /etc/systemd/timesyncd.conf
timedatectl timesync-status
```

`/etc/systemd/timesyncd.conf`:

```text
Servers=0.ubnt.pool.ntp.org 1.ubnt.pool.ntp.org 2.ubnt.pool.ntp.org 3.ubnt.pool.ntp.org 0.debian.pool.ntp.org 1.debian.pool.ntp.org 2.debian.pool.ntp.org 3.debian.pool.ntp.org
```

- `FallbackNTP=`: matching lineなし
- current server: `0.ubnt.pool.ntp.org`（resolved IP は `[MASKED_IP]`）
- offset: `-221us`
- stratum: 2
- root distance: `31.844ms`
- delay: `22.282ms`
- jitter: `823us`

### 名前解決 / resolver

```bash
getent hosts quory.internal
getent hosts ntp.nict.jp
grep -E '^[[:space:]]*nameserver[[:space:]]+' /etc/resolv.conf
```

結果:

| 対象 | 結果 |
| --- | --- |
| `quory.internal` | 解決成功（`[MASKED_PRIVATE_IP]`） |
| `ntp.nict.jp` | 解決成功（採取時は複数の IPv6 address、値はマスク） |
| `/etc/resolv.conf` nameserver | systemd-resolved の loopback stub（`[MASKED_LOOPBACK_IP]`） |

## 一次所見

UniFi controller DB には `quory.internal` が adopted device 向け NTP server 3 として
実在する。一方、CloudKey OS 自身の timesyncd はこの controller 設定を使わず、
Ubiquiti / Debian pool を参照している。

CloudKey から `quory.internal` の名前解決は成功したため、AP の失敗を CloudKey 全体の
DNS 障害とは判断できない。次段では AP が実際に受け取った NTP server / DNS server、
AP から resolver への到達性、最新 provision の反映有無を read-only で確認するのが妥当。

## After: NTP server 3 の IP 直指定後確認

ユーザーが UniFi controller 上で NTP server 3 を hostname から IP 直指定へ変更した後、
同じ `ace.setting` document を read-only の `find` + field projection だけで再取得した。

```javascript
db.setting.find(
  {key: "ntp"},
  {
    _id: 0,
    key: 1,
    ntp_server_1: 1,
    ntp_server_2: 1,
    ntp_server_3: 1,
    ntp_server_4: 1
  }
).forEach(printjson)
```

採取結果:

| field | after value | 判定 |
| --- | --- | --- |
| `ntp_server_1` | `ntp.nict.jp` | 変更なし |
| `ntp_server_2` | `ntp.jst.mfeed.ad.jp` | 変更なし |
| `ntp_server_3` | `[MASKED_QUORY_IPV4]` | IPv4 literal。`quory.internal` ではない |
| `ntp_server_4` | 空文字 | 変更なし |

`ntp_server_3` は IPv4 address の形式で保存されており、hostname 直指定からの変更が
controller DB に反映されたことを確認した。実 IP はリポジトリへ残さずマスクした。
この after 確認でも `insert` / `update` / `remove` / `delete` 等は使用していない。

## 未実施

- adopted AP / switch への SSH・コマンド実行
- AP 側の実配布設定・provision 状態確認
- UniFi GUI 操作
- DB 書込
- 設定ファイル編集
- サービス再起動・reload
- NTP server 変更
