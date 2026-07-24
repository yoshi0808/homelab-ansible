# Autonomous Recovery System Context

## 位置づけ

本書は自律復旧を構成するhost、account、daemon、依存関係の非規範な現状を記録する。許可・禁止・停止条件は [`autonomous_recovery_policy.md`](../../policies/autonomous_recovery_policy.md) が正本であり、競合時はPolicyを優先する。IP、VLAN、数値VM ID、認証情報の実値は記載せず、inventory / vars / codeを正本とする。

## 対象と配置

| 要素 | 配置・対象 | 現状の役割 |
|---|---|---|
| pull probe | quory | `authy`、`monnie`、`sophos-fw`を継続probeする |
| recovery I/O | quory | Slack Socket Modeの受付と認可を担当する常駐service |
| recovery execution | quory | 調査・限定復旧の実行plane。常駐daemonではない |
| target landing | `authy`、`monnie`、`pve1`、`pve2` | forced-command専用のSSH着地 |
| service recovery対象 | `authy`、`monnie` | target内の許可serviceを扱う |
| VM recovery対象 | `authy`、`monnie`、`sophos-fw` | target別に許可されたreboot / failoverを扱う |
| Proxmox調査対象 | `pve1`、`pve2` | cluster / HA / replication / VM / task / storage / ZFS / journalのread-only調査 |
| 開発環境 | ansy | 自律復旧action対象外 |

service recoveryの現行対象は、`authy`の`freeradius`と、`monnie`の`prometheus` / `grafana-server` / `loki` / `unpoller`である。`sophos-fw`にはservice recovery経路がない。現行tagは`sophos-fw`と`authy`が`hacritical`、`monnie`が`ops`で、home preference tagもtargetごとに設定されている。targetと数値VM IDの対応、tagの具体値はinventory、role defaults、templateを正本とする。

| Target | Probe契約 |
|---|---|
| `sophos-fw` | icmpと`@sophos-fw.internal`へのDNS問い合わせ |
| `authy` | icmpとtcp port 22 |
| `monnie` | icmpとtcp port 3000 |

各probeの`host` fieldはtargetのFQDNを明示する。

## Accountとdaemon

| Identity | 配置 | 現状の責務 |
|---|---|---|
| `ann` | 既存の管理対象 | patch / evacuate / restore等の定常自動化 |
| `recovery-io` | quory | Slack tokenを保持し、認可とI/Oを担当する常駐service |
| `recovery-exec` | quory | 調査keyとaction keyを使い、呼出時だけCodexを起動する |
| `recovery-exec` landing | target hosts | forced commandで限定処理へ着地する |
| probe実行account `(yoshi)` | quory | pull probeを実行し、global pause状態を読むため`recovery-exec` groupに所属する |

account間の権限分離、token / keyの保持禁止、forced command要件はPolicy §7を正本とする。

## 依存関係

- pull経路はquoryからProxmox API / SSHと対象probe endpointへ到達する。
- push経路はtargetのsystemd `OnFailure`からquoryのforced-command着地へ到達する。
- Slack経路はrecovery I/Oからquoryの限定Codex wrapperへ到達する。
- notificationは共通Slack通知処理に依存するが、通知障害は復旧処理の成否と分離される。
- Proxmox node上のSSH session内sudoと、quory上Codex sandbox内のprocessは別の実行境界である。

2026-07-05の導入・検証経緯とtester教訓は [`2026-07-24_009_investigation_autonomous_recovery_policy_rewrite.md`](../../reviews/policy_standardization/2026-07-24_009_investigation_autonomous_recovery_policy_rewrite.md) を参照する。本書へ時点依存の検証結果を複製しない。
