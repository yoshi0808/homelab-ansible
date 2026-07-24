# Autonomous Recovery Operations Context

## 位置づけ

本書はmute、manual layer、調査追加、障害後の復旧・監視再開を扱う非規範runbookである。実行の許可、禁止、停止条件は [`autonomous_recovery_policy.md`](../../policies/autonomous_recovery_policy.md) が正本であり、競合時はPolicyを優先する。数値VM ID、IP、VLAN、認証情報の実値は記載しない。

## Muteとglobal pause

target別muteとglobal pauseを用途で使い分ける。

| 機構 | 粒度 | 解除 | 主な利用場面 |
|---|---|---|---|
| target別mute | target単位 | TTL満了またはclear | patch、migration、target単位の意図した停止 |
| global pause | 全target | 人間または正常flowの明示resume | 複数targetへ影響し得る作業 |

target別muteは`homelab-mute set/status/clear`で操作する。global pauseは`homelab-monitoring-pause` / `homelab-monitoring-resume` / `homelab-monitoring-status`で操作する。state fileの具体pathとJSON schemaはrole filesを正本とする。

運用時は次を確認する。

1. 変更前に対象と影響範囲に合う機構を設定する。
2. statusで有効状態と理由を確認する。
3. 作業後はhealthを確認してからclear / resumeする。
4. global pauseを伴う処理が失敗した場合、原因と全targetの状態を確認し、人間が明示的にresumeする。
5. mute / pause中のprobe skipとcounter reset、pushのmute確認はPolicy §4のgateであり、runbook判断で迂回しない。

自動mute対象とTTLの具体値は各呼出playbook / role varsを正本とする。

現行の横断契約は次のとおりである。

| Playbook | 対象 | TTL |
|---|---|---:|
| `proxmox_evacuate_node.yml` | `authy` / `monnie` / `sophos-fw` | 120分 |
| `proxmox_patch_apply_node.yml` | `authy` / `monnie` / `sophos-fw` | 60分 |
| `proxmox_restore_vm_placement.yml` | `authy` / `monnie` / `sophos-fw` | 90分 |
| `ubuntu_nightly.yml` | reboot対象の`authy` / `monnie` | 30分 |
| `proxmox_patch_weekly_full.yml` | `authy` / `monnie` / `sophos-fw` | 360分 |
| `ubuntu_vm_full_upgrade.yml` | apply対象の`authy` / `monnie` | 45分 |

## Manual layer

systemdがactiveでpingも通るが機能していない等、自動経路が検知できない障害classでは、Semaphoreから必要最小のlayerを選ぶ。

1. 対象と症状を確認し、service restart / VM reboot / HA failoverのうち最小のlayerを選ぶ。
2. Policy §2 / §3のtarget allowlistを確認する。
3. 対応playbookへtarget名を渡して実行する。
4. playbook側のtag、VM存在、稼働状態、HA登録、移行先等のsafety gateを通す。
5. report、復旧確認、Slack通知を確認し、未復旧なら次段を自動反復せず人間判断する。

probeが正常でもmanual layerを選べるが、その発火判断は人間が負う。target allowlistや実装gateを上書きしない。

## Investigate追加

調査追加はread-onlyに限定する。

1. 既存serviceの調査はtargetの`investigate_services`へ追加する。
2. target固有の固定調査は`investigate_extra`へname / commandとして追加する。
3. 必要な場合だけtarget sudoersを同期し、書込みcommandを追加しない。
4. common category追加の場合はwrapper / dispatch双方のcaseと検証を同期する。
5. Codex向け説明を更新し、quoryを対象に正規setup playbookで関連artifactを同時配備する。
6. 配備前 / tester工程でallowlist外拒否、arity、parameter、path、sudoers grammar、forced-command経路を検証する。

具体的なfile、variable、template、named check一覧はRepository Contextとコードを参照する。

## 障害後の復旧と監視再開

1. pushでservice restartが失敗した場合、Codex経路からVM reboot / HA failoverへ進めず人間へescalateする。
2. 独立したpull条件が成立している場合だけpull ladderが動作する。push失敗をpull発火条件として代用しない。
3. manual layerを使う場合は人間が症状と影響を確認して段を選ぶ。
4. flapping判定時は自動ladderを再実行せず、通知と調査へ移る。
5. 復旧後はtarget health、lock、mute / pause、通知queueを確認する。
6. global pauseが残った場合は原因を解消し、全targetの状態を確認してから人間が明示resumeする。

## 調査・通知障害

- Proxmox nodeへ到達できない、VMがnot-found、allowlist外入力、forced-command拒否の場合は変更操作へ進まず記録・通知する。
- Slack通知失敗は復旧処理の結果と分離し、reportまたはnotification queueから後で確認する。
- 実装・導入の時点履歴と2026-07-05のtester教訓は009 investigationを参照する。
