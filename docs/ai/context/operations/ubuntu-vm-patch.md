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

Prometheusのmanual updateとrollbackは`prometheus_update_check.yml`を人間が明示実行することで行う(Policy §7 UV-035〜UV-039、2026-07-25更新)。実行判断は人間が行い、artifactのdownload・backup・binary差し替え・restart・health確認はplaybookが一括して行う。

## 既知の落とし穴: monnie の grafana 更新

**grafana パッケージを更新するときは、事前に `/var/lib/grafana/plugins-bundled` を退避する。** 退避しないと `dpkg` の設定処理が必ず失敗し、パッケージが `iF`(設定失敗)で止まる。

```bash
sudo mv /var/lib/grafana/plugins-bundled /var/lib/grafana/plugins-bundled.$(date +%Y%m%d)
# 更新後、問題なければ退避分は削除してよい
```

理由は grafana の `postinst` にある(2026-08-01に `.deb` 同梱のスクリプトと導入済みスクリプトを `diff` して、パッケージ由来かつ改変なしであることを確認済み)。

```sh
# postinst:27-28 — 条件が付いていない
mv $GRAFANA_HOME/data/plugins-bundled $DATA_DIR   # = /usr/share/grafana/data/... → /var/lib/grafana
```

`mv` は移動先の同名ディレクトリが空でないと失敗する。移動先は `/var/lib`(データ領域)なのでパッケージは消さず、`preinst` は存在せず、`prerm`/`postinst` にも削除処理は無い。**したがって一度成功すると、以後の更新は必ず失敗する。** `postinst` は `set -e` なので、この1行で以降(権限設定・provisioningディレクトリ・サービス再起動)がすべて止まる。

**復旧手順**(既に `iF` になっている場合):

```bash
sudo mv /var/lib/grafana/plugins-bundled /var/lib/grafana/plugins-bundled.<日付>
sudo dpkg --configure -a        # RESTART_ON_UPGRADE=true なので grafana-server も再起動される
dpkg -l grafana | tail -1       # ii になること
curl -sk https://localhost:3000/api/health   # Grafana は HTTPS。database:ok と version を確認
```

**この落とし穴が次回も再現するかは分からない。** upstream が直せば再現しない。初出は2026-08-01の `ubuntu_vm_full_upgrade`(monnie、13.1.0 → 13.1.1)で、一次調査の成果物は `reports/incidents/_investigations/semaphore-512.*`。

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

| 入口 | 実行基盤 |
|---|---|
| `ubuntu_nightly.yml`(`authy`のnightly reboot判定) | Semaphore UI schedule。旧`ansible-authy-reboot-if-required.timer`(`quory`上のsystemd timer、毎日03:30)から移行済み |
| `radius_healthcheck.yml`(`authy`のhealthcheck) | Semaphore UI schedule。旧`ansible-authy-healthcheck.timer`(`quory`上のsystemd timer、毎日05:30)から移行済み |
| `monitoring_healthcheck.yml`(monitoring healthcheck) | Semaphore UI schedule。旧`ansible-monitoring-healthcheck.timer`(`quory`上のsystemd timer、毎日05:35)から移行済み |

移行済みの根拠は`roles/systemd_timers/defaults/main.yml`のコメント化されたentry(「以下のエントリはSemaphore UIスケジュールに移行済み」)。現在唯一有効なsystemd timerは`cert-renew-quory`(`quory`上、`cert_renew_quory.yml`、月初00:35)である。正確な時刻とschedule有効性はSemaphore UIを正本とし、UI設定はリポジトリ外で変化し得るため本書は複製・保証しない。

## 障害時の確認

- healthcheckがcriticalならapt処理や後続変更へ進めず、service / resource / reportを調査する。
- apt update / check / simulationが失敗した結果に基づいてapplyしない。
- rebootまたはpost-checkが失敗した場合は通知とreportを確認し、自動反復せず人間が復旧方法を判断する。
- Slack通知障害はpatch / reboot処理の成否と分離し、caller結果とreportから確認する。
- muteが残った場合は対象healthを確認し、autonomous recoveryのOperations Contextに従って明示解除する。

2026-07-24の構造移行、旧Policy snapshot、既知不一致の凍結記録は [`2026-07-24_013_investigation_ubuntu_vm_patch_policy_rewrite.md`](../../reviews/policy_standardization/2026-07-24_013_investigation_ubuntu_vm_patch_policy_rewrite.md) を参照する。
