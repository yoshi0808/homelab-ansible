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
| Loki横断ログ調査対象 | `monnie` | homelab全体で収集済みの集約ログ(job/host問わず)をLoki経由で参照する起点。target自身のログに限らない(2026-07-29、AR-095〜AR-101) |
| 開発環境 | ansy | 自律復旧action対象外 |

service recoveryの現行対象は、`authy`の`freeradius`と、`monnie`の`prometheus` / `grafana-server` / `loki` / `unpoller`である。`sophos-fw`にはservice recovery経路がない。現行tagは`sophos-fw`と`authy`が`hacritical`、`monnie`が`ops`で、home preference tagもtargetごとに設定されている。targetと数値VM IDの対応、tagの具体値はinventory、role defaults、templateを正本とする。

| Target | Probe契約 |
|---|---|
| `sophos-fw` | icmpと`@sophos-fw.internal`へのDNS問い合わせ |
| `authy` | icmpとtcp port 22 |
| `monnie` | icmpとtcp port 3000 |

各probeの`host` fieldはtargetのFQDNを明示する。

**名前解決はquoryの`/etc/hosts`が担保する。DNSに依存させない。** 内部DNSを提供しているのは`sophos-fw`自身であり、**ラダーの第一の標的でもある**。sophos-fwが停止・再起動・フェイルオーバー中はDNSが引けないため、DNSだけに頼るとラダーは「sophos-fwを直すためにpve1/pve2を名前で引く」ところで詰む。quoryの`/etc/hosts`はこの循環を切るために存在し、pve1 / pve2 / sophos-fw / authy / monnie / ansy / cloudkey / UniFi機器を網羅している。

この`/etc/hosts`は**Ansible管理外の手動状態**である。エントリが古くなっても平常時は症状が出ず、**DNSが引けない障害時にだけ効かなくなる** — いちばん困るときにだけ壊れる形なので、targetを増減したときは同時に更新すること。

## Accountとdaemon

| Identity | 配置 | 現状の責務 |
|---|---|---|
| `ann` | 既存の管理対象 | patch / evacuate / restore等の定常自動化 |
| `recovery-io` | quory | Slack tokenを保持し、認可とI/Oを担当する常駐service |
| `recovery-exec` | quory | 調査keyとaction keyを使い、呼出時だけCodexを起動する |
| `recovery-exec` landing | target hosts | forced commandで限定処理へ着地する |
| probe実行account `(yoshi)` | quory | pull probeを実行し、global pause状態を読むため`recovery-exec` groupに所属する |

account間の権限分離、token / keyの保持禁止、forced command要件はPolicy §7を正本とする。

## 検証用target(`sandbox`)

ラダーを実targetへ当てずに検証するための専用VMとして `sandbox.internal` がある。`recovery_ha_failover.yml` と `recovery_service_restart.yml` は対象の許可リストに `sandbox` を含む。

- probeは**検証用の第2インスタンス**として配備する(`playbooks/recovery_probe_sandbox_setup.yml`、unit `recovery-probe-sandbox`)。daemon本体は本番と共有し、分けるのは `state_dir` だけである — `ladder.lock` がtarget別でないため、共有すると検証中に本番の障害が起きたときラダーが見送られる。muteディレクトリは逆に**共有する**(targetごとに別ファイルで干渉せず、`homelab-mute sandbox <分>` が暴走時の安全弁になる)。
- **既定でenableせず、常設もしない。** 検証したい窓の間だけ `systemctl enable --now recovery-probe-sandbox` で開き、終わったら閉じる。常駐させると週次パッチと衝突する — `proxmox_evacuate_node` は `prefer*` タグを持たない `sandbox` をPhase 6で停止するが、**週次パッチがmuteするのは authy / monnie / sophos-fw の3件だけで `sandbox` は含まれない**ため、probeが5分後にラダーを発火させ、パッチ中のノードでVMを起動しにいく。
- **HAへ `state: ignored` で登録してあり、relocateを発行してもVMは動かない。** そのためprobeのtarget定義は `failover: false` とし、failover段は別テンプレート(`SANDBOX: Recovery ha failover (check)`、`--check`)で個別に検証する。
- 標的が到達不能なまま起動しない。閾値到達のたびにラダーが発火し、flappingエスカレーションに至る。

**AIからは窓を開けられない。** enable / disable も failover段のテンプレート起動も quory 上の操作であり、ansyはquoryへの到達手段を持たない(`docs/ai/core.md`「開発と本番の境界」)。検証にこの窓が要るときは、Coordinator経由でYoshinobuへ回す。

## 依存関係

- pull経路はquoryからProxmox API / SSHと対象probe endpointへ到達する。
- push経路はtargetのsystemd `OnFailure`からquoryのforced-command着地へ到達する。
- Slack経路はrecovery I/Oからquoryの限定Codex wrapperへ到達する。
- notificationは共通Slack通知処理に依存するが、通知障害は復旧処理の成否と分離される。
- Proxmox node上のSSH session内sudoと、quory上Codex sandbox内のprocessは別の実行境界である。

2026-07-05の導入・検証経緯とtester教訓は [`2026-07-24_009_investigation_autonomous_recovery_policy_rewrite.md`](../../reviews/policy_standardization/2026-07-24_009_investigation_autonomous_recovery_policy_rewrite.md) を参照する。本書へ時点依存の検証結果を複製しない。
