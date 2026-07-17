# Ubuntu nodes Alloy Phase 2 pre-deploy recon

- 実施日: 2026-07-17
- 対象: ansy、quory、authy
- 目的: rsyslog導入方式、forward rule番号、`stop` 有無の確定
- tester操作: read-onlyのみ（書込、設定変更、service操作なし）

## 結論

| node | 現状分類 | forward file | `stop` | 理由 |
|---|---|---|---|---|
| ansy | rsyslog既導入・local syslog稼働中 | `49-monnie-forward.conf` | なし | 既存local loggingを保持 |
| quory | rsyslog既導入・local syslog稼働中 | `49-monnie-forward.conf` | なし | 既存local loggingを保持 |
| authy | rsyslog未導入・local syslogなし | `49-monnie-forward.conf` | あり | 導入後のdefault local log生成を抑止 |

3ノードとも `21-cloudinit.conf` にCloud-init専用のactive `stop` ruleがある。forward fileを49番にすると、
この既存専用ruleを維持しつつ、Ubuntu既定の `50-default.conf` より前で一般ログをforwardできる。

- ansy / quory: forward後も処理を継続し、50番の既存local file出力を保持する
- authy: forward後に `stop` し、rsyslog導入時に50番が追加されても新規local syslog生成を避ける

## 1. package / service

| node | dpkg state | version | active | enabled |
|---|---|---|---|---|
| ansy | `ii` | `8.2512.0-1ubuntu4` | active | enabled |
| quory | `ii` | `8.2512.0-1ubuntu4` | active | enabled |
| authy | `un` | 未導入 | inactive | not-found |

authyの `/etc/rsyslog.d` にはUFW / Cloud-init由来の設定断片があるが、rsyslog package本体とserviceは存在しない。

## 2. rsyslog.d inventoryと性質

### ansy

| file | omfile / local出力 | active `stop` | 性質 |
|---|---|---|---|
| `20-ufw.conf` | `/var/log/ufw.log` | なし（commentのみ） | UFW専用 |
| `21-cloudinit.conf` | `/var/log/cloud-init.log` | あり | Cloud-init専用 |
| `50-default.conf` | syslog、auth、kern、mail系 | なし | Ubuntu default local logging |

`50-default.conf` はpresent。

### quory

| file | omfile / local出力 | active `stop` | 性質 |
|---|---|---|---|
| `20-ufw.conf` | `/var/log/ufw.log` | なし（commentのみ） | UFW専用 |
| `21-cloudinit.conf` | `/var/log/cloud-init.log` | あり | Cloud-init専用 |
| `50-default.conf` | syslog、auth、kern、mail系 | なし | Ubuntu default local logging |

`50-default.conf` はpresent。

### authy

| file | omfile / local出力 | active `stop` | 性質 |
|---|---|---|---|
| `20-ufw.conf` | `/var/log/ufw.log` | なし（commentのみ） | UFW専用 |
| `21-cloudinit.conf` | `/var/log/cloud-init.log` | あり | Cloud-init専用 |

`50-default.conf` はabsent。pveの `45-frr.conf` と同様に、`21-cloudinit.conf` は特定サービスだけを
専用fileへ出して後続処理を止めるruleである。3ノードともこの既存挙動を維持する。

## 3. `/var/log/syslog` 30秒差観測

| node | sample 1 | sample 2 | delta | mtime | 判定 |
|---|---:|---:|---:|---|---|
| ansy | 17814432 bytes | 17815464 bytes | +1032 bytes | 更新 | 稼働中 |
| quory | 3946539 bytes | 3946811 bytes | +272 bytes | 更新 | 稼働中 |
| authy | absent | absent | — | — | 未生成 |

ansy / quoryは30秒の短時間でもsizeとmtimeが更新され、default local syslogが実運用中。ここへ
`stop` を追加すると既存logging contractを破壊するため、forward-without-stopが必要。

authyは両時点ともabsent。fresh rsyslog導入後に一般ログをmonnieへforwardし、49番ruleで止める方式が
pveと同じ副作用最小化contractになる。

## 4. journald

3ノードとも `/etc/systemd/journald.conf` の該当行は同一だった。

```ini
#ForwardToSyslog=no
#MaxLevelSyslog=debug
```

`/etc/systemd/journald.conf.d` は3ノードともabsentで、drop-inはない。現状は明示設定ではなくvendor default。
rsyslog経由forwardを有効化する際は、3ノードとも専用drop-inで `ForwardToSyslog=yes` と
`MaxLevelSyslog=debug` を明示する必要がある。

## 5. AppArmor

| node | AppArmor | rsyslogd profile | mode |
|---|---|---|---|
| ansy | enabled | loaded | enforce |
| quory | enabled | loaded | enforce |
| authy | enabled | absent | — |

authyでprofileがないのはrsyslog package未導入と整合する。導入後はprofile生成 / loadと、forward ruleが
AppArmor denialを起こさないことを確認対象に含める。

## 6. journal volume目安

`journalctl --since -1hour` の採取行数:

| node | lines / hour | 約lines/min |
|---|---:|---:|
| ansy | 1939 | 32.3 |
| quory | 225 | 3.8 |
| authy | 113 | 1.9 |

短時間のtester read-only commandに伴うjournal行も含む概数。capacity planningでは境界値ではなくorderの
把握に用いる。

## 7. deploy contract

### ansy / quory

1. 既存rsyslog package / serviceを維持する。
2. `49-monnie-forward.conf` でmonnieへforwardする。
3. forward action後に `stop` を置かない。
4. `50-default.conf` を変更せず、既存 `/var/log/syslog` 等へのlocal出力を保持する。
5. `21-cloudinit.conf` の専用file + stop挙動を維持する。
6. rsyslogd AppArmor enforceを維持したままsyntax / runtimeを検証する。

### authy

1. rsyslogをfresh installする。
2. `49-monnie-forward.conf` でmonnieへforwardする。
3. forward action後に `stop` を置き、後続default local file出力を抑止する。
4. `20-ufw.conf` / `21-cloudinit.conf` を変更しない。
5. package導入で `50-default.conf` が作成されても、49番の一般ruleで先に止める。
6. 導入後のrsyslogd AppArmor profile / enforce、full `rsyslogd -N1`、local syslog非生成を検証する。

## 8. 最終判定

- ansy: **49番、stopなし**
- quory: **49番、stopなし**
- authy: **49番、stopあり**
- 既存専用rule: 3ノードとも維持
- journald drop-in: 3ノードとも新規追加が必要
- rsyslog AppArmor: ansy / quoryは既存enforce、authyは導入後確認

IP address literalやsecretは本調査文書に記録していない。
