# ansy / monnie terminal attributes error investigation

- 実施日: 2026-07-17
- 対象: ansy、monnie
- 調査種別: read-only
- 変更、service操作、restart: なし

## 結論

`failed to get terminal attributes: Input/output error` の発生元はcron、systemd timer、`stty`、`tset`、
`script`、`expect` ではない。両nodeとも次の同一原因だった。

1. cloud imageのGRUB設定がkernel command lineへ `console=ttyS0` を追加する。
2. `systemd-getty-generator` がboot時に `serial-getty@ttyS0.service` をruntime enableする。
3. unitは `/dev/ttyS0` をTTYとして `/usr/sbin/agetty` を起動する。
4. device node / systemd device unitは存在するが、kernel serial driverは該当portを `uart:unknown` と認識している。
5. agettyがterminal name / attributesを取得できず、EINVAL / EIOを記録する。
6. unitの `Restart=always` により約10.25秒周期で別PIDのagettyが再起動される。

したがって、実体のあるserial console backendが認識されていないのに、guest OSがttyS0 console/gettyを要求している
構成不一致がroot causeである。

## 1. journal structured fields

両nodeで該当eventのfieldは同一だった。

| field | value |
|---|---|
| `SYSLOG_IDENTIFIER` | `agetty` |
| `_COMM` | `agetty` |
| `_EXE` | `/usr/sbin/agetty` |
| `_SYSTEMD_UNIT` | `serial-getty@ttyS0.service` |
| `_UID` | root |
| unit template | `/usr/lib/systemd/system/serial-getty@.service` |

実行command contract:

```text
/usr/sbin/agetty --noreset --noclear --issue-file=... --keep-baud 115200,57600,38400,9600 - vt220
```

PIDはeventごとに変化し、同一long-running processの周期logではなく、process restartの反復だった。

## 2. 発生件数と間隔

24時間windowの集計:

| node | events | first | last | avg interval | min | max |
|---|---:|---|---|---:|---:|---:|
| ansy | 8427 | 2026-07-16 20:22:48 JST | 2026-07-17 20:22:42 JST | 10.253 s | 10.114 s | 15.252 s |
| monnie | 8428 | 2026-07-16 20:22:50 JST | 2026-07-17 20:22:41 JST | 10.252 s | 10.115 s | 15.250 s |

通常時は約351 events/hour、約5.85 events/min。calendar境界やcron scheduleではなく、常時ほぼ一定の
restart cadenceである。

## 3. unit lifecycle

`serial-getty@ttyS0.service` の主要contract:

```ini
[Service]
ExecStart=-/usr/sbin/agetty ...
Restart=always
StandardInput=tty
StandardOutput=tty
TTYPath=/dev/ttyS0
TTYReset=yes
TTYVHangup=yes
```

unitはloaded、active/running、`WantedBy=getty.target`、`enabled-runtime`。`RestartUSec=100ms`。
実測約10.25秒にはagetty processの約10秒の生存時間が含まれ、その後systemdがrestartする。

12秒差の2点観測では両nodeとも次が成立した。

- `NRestarts`: +1
- `MainPID`: 別PIDへ更新
- `ExecMainStartTimestamp`: 約10秒後へ更新

直近の実journal sequence:

```text
Started serial-getty@ttyS0.service
agetty: could not get terminal name: -22
agetty: failed to get terminal attributes: Input/output error
Deactivated successfully
Scheduled restart job
Started serial-getty@ttyS0.service
```

monnieのrestart counterは調査時点で約42,965、ansyは約46,649。boot後から継続するrestart loopである。

## 4. 起動元

両nodeの永続設定元:

```text
/etc/default/grub.d/50-cloudimg-settings.cfg
GRUB_CMDLINE_LINUX_DEFAULT="console=tty1 console=ttyS0"
```

実際のkernel command lineにも `console=tty1` と `console=ttyS0` がある。この指定を受けて
`systemd-getty-generator` が次のruntime linkを生成している。

```text
/run/systemd/generator/getty.target.wants/serial-getty@ttyS0.service
  -> /usr/lib/systemd/system/serial-getty@.service
```

`getty.target` dependencyにも `serial-getty@ttyS0.service` が含まれる。

該当名を持つsystemd timerは0件。cron directories / crontabにも `agetty`、`ttyS0`、該当error stringの
entryは0件。前後ログにもcron/timer起動の痕跡はなく、unit自身のrestart jobが直接の再起動元である。

## 5. ttyS0側の手掛かり

両nodeで `/dev/ttyS0` はcharacter deviceとして存在し、`dev-ttyS0.device` もactive/plugged。
sysfs pathはplatform `serial8250` 配下にある。

しかし `/proc/tty/driver/serial` の該当entryは次の状態だった。

```text
uart:unknown
```

kernel boot logはttyS0をlegacy consoleとして有効化し、systemdもdeviceを待機しているが、serial driverは
利用可能なUART種別を認識していない。device nodeの存在だけではagettyがterminal ioctlを正常実行できず、
terminal attributes取得時のEIOと整合する。

## 6. 仮説評価

| hypothesis | 判定 | 根拠 |
|---|---|---|
| cron内のTTY要求command | 棄却 | cron entryなし、10秒周期、unit fieldがserial-getty |
| systemd timer内のTTY要求command | 棄却 | timerなし、TriggeredByなし |
| `stty` / `tset` / `script` / `expect` | 棄却 | `_EXE` / `_COMM` はagetty、command lineにも無し |
| agettyのterminal ioctl failure | 確定 | structured field、前後log、PID restartを直接確認 |
| serial backendとguest console設定の不一致 | 強く支持 | `console=ttyS0` + generated getty + `uart:unknown` + EIO |

## 7. 対応選択肢（未実施）

調査では変更していない。対応はserial consoleの必要性で選ぶ。

### serial consoleが必要

hypervisor / VM側でguest ttyS0に対応するserial device/backendを正しく接続し、guestのserial driverが
UARTを認識することを確認する。その後、agetty error、restart counter増加、console接続を再検証する。

### serial consoleが不要

管理されたbootloader設定から `console=ttyS0` を外し、runtime-generated serial gettyが次回bootで生成されない
構成にする。あるいは意図を明確にしたsystemd mask/drop-inで該当instanceを抑止する。boot/recovery accessへの
影響があるため、実施には別の人間承認とrollback手順が必要。

## 8. 最終判定

- 発生process: `/usr/sbin/agetty`
- 発生unit: `serial-getty@ttyS0.service`
- 起動元: kernel `console=ttyS0` → systemd-getty-generator
- 発生周期: 約10.25秒、常時restart loop
- cron / timer: 無関係
- 直接原因: ttyS0 terminal attributes ioctlのEIO
- 構成原因: ttyS0 console/getty要求に対しserial driverが `uart:unknown`
- 調査中の変更: なし

IP address literal、root device identifier、secretは本調査文書に記録していない。
