# serial-getty mask テスト結果

- 実施日: 2026-07-17 (JST)
- 対象 playbook: `playbooks/serial_getty_mask.yml`
- 実施判定: **PASS（fail-closed により quory は APPLY 対象外）**
- mute: 未使用
- Ansible local temp: `/tmp/codex-ansible-local`

## 1. 結論

事前確認で `quory` の `/proc/tty/driver/serial` に実 UART (`uart:16550A`) を検出した。
要件の「実 serial console 利用の可能性がある node は除外」に従い、`quory` は fail-closed で
APPLY から除外した。したがって、文字どおりの「4 node を masked」にする操作は実施していない。

`ansy`、`monnie`、`authy` の 3 node は dry-run 成功後に APPLY し、
`serial-getty@ttyS0.service` が `masked` かつ `inactive`、ttyS0 の agetty が不在であることを確認した。
`quory` は変更されず、元の `disabled` かつ `inactive` を維持している。

APPLY 後 5 分以上の観測で、Loki の対象 4 host に実 agetty の
`failed to get terminal attributes` は 0 件だった。

## 2. 事前確認

| node | unit の事前状態 | UART | ttyS0 agetty | ttyS0 login/session | 判定 |
|---|---|---|---|---|---|
| ansy | loaded / active / running / enabled-runtime | `uart:unknown` | あり | 0 / 0 | APPLY 対象 |
| monnie | loaded / active / running / enabled-runtime | `uart:unknown` | あり | 0 / 0 | APPLY 対象 |
| authy | loaded / inactive / dead / disabled | `uart:unknown` | なし | 0 / 0 | APPLY 対象 |
| quory | loaded / inactive / dead / disabled | `uart:16550A` | なし | 0 / 0 | **除外** |

追加確認:

- Proxmox の VM 一覧から VMID を動的に特定し、`qm config` を確認した。
- `ansy`、`monnie`、`authy` に `serial0` および `vga: serial` 設定はなかった。
- VM の console は serial0 依存ではなく、Web/default VGA 経路を利用できる。
- `quory` では kernel command line の serial console 指定、稼働中の ttyS0 agetty、
  ttyS0 login/session、IPMI device、リポジトリ内の SOL 依存 runbook は確認されなかった。
  ただし、実 UART を認識しているため安全側に倒して除外した。

## 3. dry-run

実行前 syntax check:

```text
ANSIBLE_LOCAL_TEMP=/tmp/codex-ansible-local ansible-playbook --syntax-check playbooks/serial_getty_mask.yml
exit=0
```

dry-run:

```text
ANSIBLE_LOCAL_TEMP=/tmp/codex-ansible-local scripts/safe-ansible-check.sh \
  playbooks/serial_getty_mask.yml --check --diff --limit 'ansy:monnie:authy'
```

結果:

| node | ok | changed | unreachable | failed | skipped |
|---|---:|---:|---:|---:|---:|
| ansy | 4 | 0 | 0 | 0 | 1 |
| monnie | 4 | 0 | 0 | 0 | 1 |
| authy | 4 | 0 | 0 | 0 | 1 |

destructive block は check mode で skip され、failure はなかった。

## 4. APPLY

APPLY 開始基準 epoch は `1784288090`、APPLY 後の観測基準 epoch は `1784288126`。

```text
ANSIBLE_LOCAL_TEMP=/tmp/codex-ansible-local ansible-playbook \
  playbooks/serial_getty_mask.yml --limit 'ansy:monnie:authy'
```

結果:

| node | ok | changed | unreachable | failed | skipped |
|---|---:|---:|---:|---:|---:|
| ansy | 4 | 1 | 0 | 0 | 1 |
| monnie | 4 | 1 | 0 | 0 | 1 |
| authy | 4 | 1 | 0 | 0 | 1 |

`quory` は limit に含めず、変更していない。

## 5. APPLY 後確認

| node | LoadState | ActiveState | SubState | UnitFileState | MainPID | ttyS0 agetty |
|---|---|---|---|---|---:|---|
| ansy | masked | inactive | dead | masked | 0 | なし |
| monnie | masked | inactive | dead | masked | 0 | なし |
| authy | masked | inactive | dead | masked | 0 | なし |
| quory | loaded | inactive | dead | disabled | 0 | なし |

対象 3 node では `/etc/systemd/system/serial-getty@ttyS0.service -> /dev/null` も確認した。
`quory` に mask link はなく、事前状態を維持している。

`journalctl -u serial-getty@ttyS0.service --since @1784288126` は、APPLY 対象 3 node とも
`No entries` だった。最終確認時点 epoch `1784288445` まで約 5 分 19 秒観測し、
unit 状態と agetty 不在が維持された。

Loki は `monnie` 上の local endpoint に対して次の selector を APPLY 後 epoch から検索した。

```logql
{job="ubuntu-nodes", host=~"ansy|monnie|quory|authy"}
  |= "failed to get terminal attributes"
```

Ansible の診断コマンド文字列および Loki 自身の query log にも検索語が現れるため、
結果を `unit="serial-getty@ttyS0.service"` または実 `agetty[PID]` 行に限定して判定した。

```text
terminal_errors=0 hosts=
```

APPLY 前の同じ確認では ansy と monnie の実 agetty error が約 10 秒間隔で取得できており、
収集経路と抽出条件が機能していることも確認済み。

## 6. 非対象への影響

- `ssh`、`rsyslog`、`systemd-journald` は 4 node とも `active`。
- playbook に GRUB 変更 task はなく、GRUB を更新していない。
- `ansy` と `monnie` の `/etc/default/grub.d/50-cloudimg-settings.cfg` は APPLY より前の
  mtime (`1776789105`) のままで、`GRUB_CMDLINE_LINUX_DEFAULT="console=tty1 console=ttyS0"` も不変。
- `authy` と `quory` には同名の cloud image 設定ファイルがなく、新規作成されていない。
- rollback は対象 node で `systemctl unmask serial-getty@ttyS0.service` を実行し、
  serial console が必要な場合のみ `systemctl start serial-getty@ttyS0.service` とする。

## 7. 判定

- dry-run: PASS
- APPLY（安全確認を通過した 3 node）: PASS
- post-state / agetty 消失: PASS
- Loki の APPLY 後実 terminal attribute error: PASS（0 件）
- quory safety exclusion / unchanged: PASS
- 4 node 全数 mask: **未実施（実 UART 検出による fail-closed の意図的例外）**
