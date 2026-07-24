# Ubuntu VM Patch Operations Context

## 位置づけ

本書はUbuntu patchのmonthly判定、manual apply、nightly、healthcheck、scheduleを扱う非規範runbookである。実行の許可、禁止、停止条件、判断軸は [`ubuntu_vm_patch_policy.md`](../../policies/ubuntu_vm_patch_policy.md) が正本であり、競合時はPolicyを優先する。IP、VLAN ID、VM ID、認証情報、秘密情報の実値は記載しない。

## Monthly判定

1. `ubuntu_vm_full_upgrade.yml`をread-only判定modeで起動する。
2. 対象nodeごとのhealthcheck、apt simulation、hold、non-apt結果、Status、reasonを確認する。
3. `BLOCKED` / `MAJOR_UPGRADE_DETECTED`をapply候補にしない。
4. package detail、product impact、non-apt結果を確認し、人間がapply要否を判断する。
5. non-apt Prometheusのupdate表示は人間のmanual作業判断にだけ使い、自動変更の許可と解釈しない。

旧Policyはmonthly dry-runを毎月2日に行う運用としていた。現行scheduleの具体値はscheduler設定を正本とする。判定mode、対象、confirmationの正確なCLI契約はplaybook先頭とrole assertionを正本とし、本Contextはcommand例によってPolicy gateを迂回させない。

## Manual apply

1. 対象nodeと直近のmonthly判定結果を確認する。
2. single nodeの対象入力と、同じnodeを示すconfirmation入力を明示する。
3. healthcheckとsimulationを再実行し、Status gateを通過することを確認する。
4. `dry_run=false`のapt apply経路でnon-apt checkが実行されないことを維持する。
5. apply中のservice restart影響を考慮し、対象となる自律復旧muteが設定されたことを確認する。
6. apply、reboot要否、起動完了、post-check、通知、reportを確認する。

Prometheusのmanual updateはPolicyが指定する人間向けセットアップ手順を使い、本runbookから`prometheus_update_check.yml`の変更機能を許可しない。Policy /実装不一致の解消は別Issueである。

## Nightlyと朝healthcheck

方針1 VMでは次の順序を使う。

1. nightlyがreboot-required fileとneedrestartを確認する。
2. reboot不要ならrebootと通知を行わず終了する。
3. reboot要なら開始通知とrecovery muteの後にrebootする。
4. 起動完了後、対象VMのserviceと疎通を確認する。
5. post-check結果を通知する。
6. 朝の専用healthcheckでservice稼働を再確認する。

healthcheckはmanual standaloneでも使える。異常時はreportと通知を確認し、Policy上の停止条件をrunbook判断で上書きしない。

## Schedule

| Timer | 入口 | 現行schedule方針 | 実行基盤 |
|---|---|---|---|
| `ansible-authy-reboot-if-required.timer` | `ubuntu_nightly.yml` | 毎日03:30 | `quory`上のsystemd timer |
| `ansible-authy-healthcheck.timer` | `radius_healthcheck.yml` | 毎日05:30 | `quory`上のsystemd timer |
| `ansible-monitoring-healthcheck.timer` | `monitoring_healthcheck.yml` | 毎日05:35 | `quory`上のsystemd timer |

timer名と配備値は`systemd_timers` roleのvars / codeを正本とする。Semaphore UI導入後はScheduleへ移行する計画だが、schedulerの変更はpatch / reboot許可を拡張しない。旧Policyの参考用全体scheduleは時点依存情報であり、本書へ他systemの時刻を複製しない。

## 障害時の確認

- healthcheckがcriticalならapt処理や後続変更へ進めず、service / resource / reportを調査する。
- apt update / check / simulationが失敗した結果に基づいてapplyしない。
- rebootまたはpost-checkが失敗した場合は通知とreportを確認し、自動反復せず人間が復旧方法を判断する。
- Slack通知障害はpatch / reboot処理の成否と分離し、caller結果とreportから確認する。
- muteが残った場合は対象healthを確認し、autonomous recoveryのOperations Contextに従って明示解除する。

2026-07-24の構造移行、旧Policy snapshot、既知不一致の凍結記録は [`2026-07-24_013_investigation_ubuntu_vm_patch_policy_rewrite.md`](../../reviews/policy_standardization/2026-07-24_013_investigation_ubuntu_vm_patch_policy_rewrite.md) を参照する。
