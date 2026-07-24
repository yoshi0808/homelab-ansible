# Autonomous Recovery Repository Context

## 位置づけ

本書は自律復旧の複数playbook / role、key、forced command、wrapper、execpolicy、ACL、入出力の横断契約を説明する非規範Contextである。許可・禁止・停止条件は [`autonomous_recovery_policy.md`](../../policies/autonomous_recovery_policy.md) が正本であり、競合時はPolicyを優先する。単一taskの実装はコード、target / 数値VM ID等の実値はinventory / vars / codeを正本とする。

## 入口とrole連携

| Playbook | 主role / task入口 | 横断上の責務 |
|---|---|---|
| `recovery_probe_setup.yml` | `recovery_probe`、`recovery_mute` | probe daemon、config、mute CLIを配備する |
| `recovery_exec_setup.yml` | `recovery_exec` | execution account、key、wrapper、dispatch、ACLを配備する |
| `recovery_io_setup.yml` | `recovery_io` | Slack I/O bridgeと起動環境を配備する |
| `recovery_push_setup.yml` | `recovery_push` | OnFailure trigger、push key、dispatchを配備する |
| `recovery_push_drill_setup.yml` | `recovery_push/tasks/drill_setup.yml` | 手動発火用drill unitだけを配備する |
| `recovery_ha_failover.yml` | `recovery_ha_failover` | target検証後にHA relocationと復旧確認を行う |
| `recovery_service_restart.yml` | `recovery_service_restart` | target / tag / state検証後に許可serviceをrestartする |
| `recovery_vm_reboot.yml` | `recovery_vm_reboot` | target / tag検証後にVM停止・起動と復旧確認を行う |
| `recovery_probe_notify.yml` | `common_slack/tasks/notify.yml` | probe queueの通知入力を共通通知へ渡す |

setup、action、notificationは同じ実行許可を表さない。tester-gateは各playbook先頭、role構成の概要は `playbook-map.md` と `role-map.md` を正本とする。

## Keyとforced-command経路

| 経路 | Keyの分離 | 横断契約 |
|---|---|---|
| investigate | target調査用 | quory wrapperとtarget dispatchが同じallowlistを検証する |
| action | target復旧用 | 引数を受け取らず、targetの許可service一式だけを扱う |
| push | targetごと | targetからquoryの固定dispatchへだけ着地する |
| Proxmox investigate | 他target調査keyと分離 | 両Proxmox nodeのread-only named checkだけを扱う |
| regular automation | `ann`所有 | recovery execution planeへ流用しない |

target investigate keyは`id_recovery_investigate`、action keyは`id_recovery_action`、Proxmox investigateは専用の`id_recovery_investigate_pve`として分離される。target側`authorized_keys`、ownership、mode、配布元guardの具体実装は`recovery_exec` / `recovery_push` roleを正本とする。秘密鍵や認証実値は文書化しない。

## Wrapper、dispatch、execpolicy

- `recovery_exec_targets`はtarget調査wrapperとdispatchの共通allowlist sourceである。
- target investigateはquory wrapperで早期filterし、target forced-command dispatchで独立に再検証する。
- Proxmox investigateもwrapperを一次filter、forced-command dispatchを権限gateとする。dispatchがcheck名、arity、parameter、固定read-only argvを検証する。
- report調査は外側wrapperと内側helperでpath segmentを再検証する。
- Semaphore調査は固定query名を固定SQLへ対応させ、read-only engine modeで実行する。
- Codex execpolicyはdefault denyで、target investigate、Proxmox investigate、report、Semaphore query、target recover、monitoring controlの限定wrapper群だけを対象とする。
- VM rebootとHA failoverはCodex wrapperではなく、pull daemonからtarget固定playbookとして呼び出される。
- Codex起動wrapperはworkspaceとCLI optionを内部で固定する。

具体的なnamed check、regex、parameter範囲、command argv、wrapper名はrole defaults / template / filesを正本とする。Policy §7のallowlist、二段検証、書込み禁止をこの一覧から拡張してはならない。

### 現行の限定command契約

この一覧は複数wrapper / dispatch間の対応を追うための現状記録であり、許可の正本ではない。変更時はコードとPolicyを同時に確認する。

- target investigateのcommon checkは`failed` / `disk` / `memory` / `load` / `network` / `ports` / `journal-system` / `dmesg`。serviceごとのstatus / journalと、`1h` / `24h` / `err` / `warn`のjournal variation、target固有`investigate_extra`をdefaultsから展開する。
- report調査は`list-playbooks`、`list-reports <playbook> [target]`、`show-report <playbook> [target] <filename>`。任意の`target`は追加path segmentを1つだけ許可し、各componentは英数字・underscore・hyphenへ限定し、filenameはJSONだけを扱う。
- Semaphore調査は`recent-failed <n>`、`task-errors <id>`、`task-hosts <id>`、`task-output <id>`。`n`は1から200、`id`は整数として検証し、自由SQLを受け付けない。
- Proxmox固定checkは`cluster-status` / `cluster-resources` / `ha-status` / `replication-status` / `replication-list` / `cluster-quorum` / `storage-status` / `zpool-health` / `zfs-list` / `journal-replication` / `journal-system` / `journal-cluster`。
- Proxmox parameter付きcheckは`replication-read` / `vm-status` / `vm-config` / `vm-tasks` / `task-log` / `storage-status-one` / `zfs-list-vm` / `vm-conf-stat` / `journal-unit`。job ID、VM ID、task ID、storage、limit、unit、windowをdispatchで検証する。数値VM IDの実値は記載しない。
- `limit`は整数かつ1から2000、unitは`pvescheduler` / `pvestatd` / `pve-cluster` / `corosync` / `pvedaemon`、windowは`30m` / `1h` / `2h` / `6h` / `12h` / `24h`のallowlistである。journal出力は300行に固定する。
- Proxmoxのnode状態は`cluster-resources`のnode entryで取得し、`zfs-list-vm`は固定read-only `zfs list`結果を非特権filterで絞る。
- Codexが呼べるwrapper群はtarget investigate、Proxmox node別investigate、report、Semaphore query、target recover、monitoring pause / resume / statusである。Proxmox recover wrapperは存在しない。
- Codex起動wrapperは`exec`、`--cd`、固定workspace、message本文の4位置だけを受け、`--sandbox workspace-write`、`approval_policy="never"`、所定execpolicy、`network_access=true`を内部で固定する。Slack I/Oはtarget accountのhomeを使う形でこのwrapperへjobを渡す。

targetやProxmox nodeを含むwrapperの正確なfile名と引数grammarはrole files / templatesを正本とする。

## ACLと権限境界

- quory上のreport / Semaphore読取りは`recovery-exec`自身へのPOSIX ACLで成立し、sudo / setuidによる昇格を必要としない。
- tokenとSSH keyは専用account ownershipとmode `0600`で保護される。
- Proxmox調査のsudoはtargetのSSH session内で完結し、quory上Codex sandboxの`no_new_privileges`経路とは分離される。
- sudoers wildcardだけを権限境界にせず、dispatchのexact arity、parameter検証、固定argvと組み合わせる。

2026-07-05の方式変更、実機確認、tester教訓は009 investigationを参照し、本書へ履歴として複製しない。

## 入出力

| 種別 | 入力 | 出力 |
|---|---|---|
| probe | target別probe設定、mute / pause state | ladder起動、通知queue、状態記録 |
| investigate | allowlist済みnamed checkと検証済みparameter | read-only観測結果 |
| action | allowlist済みtarget | report、復旧判定、best-effort通知 |
| Slack request | 認可済みmessage | 限定Codex jobとthread reply |
| notification | status、title、message、検知時刻 | Slack alert |

report pathやJSON schemaの単一実装詳細は各role / playbookを正本とし、本Contextへ複製しない。
