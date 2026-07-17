# Ubuntu nodes serial-getty@ttyS0 stop + mask — 実装記録

- 日付: 2026-07-17
- 担当: implementer
- 要件: `docs/ai/reviews/misc/2026-07-17_serial_getty_mask_requirement.md`
- 前提調査: `docs/ai/reviews/misc/2026-07-17_terminal_attr_error_investigate.md`
- 制約順守: commit / push / 実ホスト実行なし。GRUB / kernel cmdline変更なし。

## 実装概要

`playbooks/serial_getty_mask.yml`を新設した。

- 対象: `ansy:monnie:quory:authy`
- 変更対象: `serial-getty@ttyS0.service`のみ
- APPLY: `ansible.builtin.systemd_service`で`state: stopped` + `masked: true`
- `enabled`は変更しない。既存のruntime enable状態を含む他のunit関係には触れず、maskで起動を抑止する。
- `serial: 1`で1 hostずつ処理する。
- 既にstopped + maskedならsystemd moduleは`changed=false`となる冪等構成。
- recovery probeの監視対象serviceではないためmuteは設定しない。
- GRUB、`/proc/cmdline`、getty generator、`getty.target`、device設定は変更しない。

## tester-gate

分類は`check-mode-native`。

- `--check`: `systemctl show`でLoadState / ActiveState / SubState / UnitFileStateをread-only収集し、stop+mask予定を表示する。変更taskは実行しない。
- APPLY: `not ansible_check_mode`の場合だけstop+maskを実行し、`tags: [destructive]`を付与した。
- `risk-accepted`にはしていない。serial-gettyは監視対象外で影響は限定的だが、console access経路を失う可能性があるため、事前確認と人間の明示判断が必要。
- 旧`tester_mode`が渡された場合はfail closedとし、`--check --diff`の使用を案内する。

## pre-deploy確認（tester、read-only）

APPLY前に4 nodeすべてで確認する。調査文書で`uart:unknown`まで確認済みなのはansy / monnieであり、quory / authyを含む全対象をtesterが改めて確認する。

### 1. unitの現在状態

各nodeで次を実行する。

```bash
systemctl show serial-getty@ttyS0.service \
  --property=LoadState \
  --property=ActiveState \
  --property=SubState \
  --property=UnitFileState

systemctl status serial-getty@ttyS0.service --no-pager
pgrep -a agetty || true
```

active / enabled-runtime / masked等の現在値と、agetty restart loopの有無を記録する。

### 2. UARTとboot要求

```bash
grep -E '^[[:space:]]*0:' /proc/tty/driver/serial
cat /proc/cmdline
journalctl -u serial-getty@ttyS0.service -n 30 --no-pager
```

- ttyS0 entryが`uart:unknown`であること。
- `console=ttyS0`によりgettyが生成されていること。
- `failed to get terminal attributes`が反復していること。

読み取り結果が異なり、実UARTが認識されているnodeはmask対象から除外する。

### 3. console利用有無

- ansy / monnie / authy: Proxmox側の対象VM設定と運用手順をread-only確認し、`serial0`をconsole / recovery accessに利用していないこと、通常のconsoleがWeb noVNC / SPICEであることを確認する。VMIDは固定値を推測せず、Proxmox inventoryから特定して`qm config <VMID>`を読む。
- quory: 物理control nodeなのでProxmox VM設定ではなく、物理serial console / IPMI serial-over-LAN / recovery手順がttyS0に依存していないことを確認する。

1 nodeでも実serial console依存があれば、そのnodeをAPPLY対象から除外する。例えば確認済みnodeだけへ明示的にlimitする。

```bash
ansible-playbook playbooks/serial_getty_mask.yml --check --diff \
  --limit 'ansy:monnie'
```

## 実行手順

### 構文確認

```bash
ansible-playbook playbooks/serial_getty_mask.yml --syntax-check
```

### dry-run（必須）

```bash
ansible-playbook playbooks/serial_getty_mask.yml --check --diff
```

全nodeのpre-deploy確認が揃い、YoshinobuがAPPLYを明示承認した後だけ実行する。

```bash
ansible-playbook playbooks/serial_getty_mask.yml
```

対象を除外する必要がある場合は、確認済みnodeだけを`--limit`へ明記する。

## APPLY後の確認

各対象nodeで次を確認する。

```bash
systemctl is-active serial-getty@ttyS0.service
systemctl is-enabled serial-getty@ttyS0.service
systemctl show serial-getty@ttyS0.service \
  --property=ActiveState \
  --property=UnitFileState
pgrep -a agetty || true
journalctl -u serial-getty@ttyS0.service --since '5 minutes ago' --no-pager
```

期待値:

- `is-active`: `inactive`
- `is-enabled`: `masked`
- ttyS0用agetty processが存在しない
- `failed to get terminal attributes`の新規eventが発生しない

Grafana Explore / Lokiでも対象hostの新規errorが止まったことを確認する。

```logql
{job="ubuntu-nodes", host=~"ansy|monnie|quory|authy"}
  |= "failed to get terminal attributes"
```

時間範囲をAPPLY直前から現在までにし、APPLY後の新規eventが無いことを確認する。

## rollback（可逆手順）

serial consoleが必要と判明した場合は、該当nodeでmaskを解除する。

```bash
sudo systemctl unmask serial-getty@ttyS0.service
sudo systemctl start serial-getty@ttyS0.service
systemctl status serial-getty@ttyS0.service --no-pager
```

- 元が停止状態だったnodeは`unmask`だけでよく、必要性を確認した場合だけ`start`する。
- playbookはenabled状態を変更しないため、`unmask`でmask前のenable/runtime生成関係へ戻せる。
- `console=ttyS0`をGRUBから除去・追加する操作は本rollbackにも含めない。

## ローカル検証

| 検証 | 結果 |
|---|---|
| `ansible-playbook playbooks/serial_getty_mask.yml --syntax-check` | PASS |
| `ansible-playbook playbooks/serial_getty_mask.yml --list-hosts` | ansy / monnie / quory / authyの4 host、PASS |
| `ansible-playbook playbooks/serial_getty_mask.yml --list-tasks` | read-only state取得 + plan表示 + destructive stop/maskを確認、PASS |
| `scripts/check-tester-gate.sh` | `[tester-gate-lint] OK (36 playbooks)` |
| `git diff --check` | PASS |
| unit / `state: stopped` / `masked: true` / `when: not ansible_check_mode` / destructive tagの静的確認 | PASS |
| IPv4 literal走査 | 検出なし |

実ホストdry-run / APPLY / Loki確認は未実施。tester工程へ引き継ぐ。
