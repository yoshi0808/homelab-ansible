# Ubuntu VM Patch System Context

## 位置づけ

本書はUbuntu patch運用に関係するnode、service、reboot管理の非規範な現状を記録する。許可、禁止、停止条件、判断軸は [`ubuntu_vm_patch_policy.md`](../../policies/ubuntu_vm_patch_policy.md) が正本であり、競合時はPolicyを優先する。IP、VLAN ID、VM ID、認証情報、秘密情報の実値は記載せず、inventory、vars、codeを正本とする。

## 対象nodeと役割

| Node | Inventory group | 旧Policy記録上の種別 | System上の役割 | Patch運用上の位置づけと影響 |
|---|---|---|---|---|
| `authy` | `radius_servers` | VM | FreeRADIUSによる認証基盤 | Policyの方針1。停止が家庭内Wi-Fi認証断につながるため、計画rebootと専用healthcheckを持つ |
| `monnie` | `monitoring_servers` | VM | Prometheus、Grafana、Loki等の監視基盤 | Policyの方針1。停止すると障害検知が機能しないため、計画rebootと専用healthcheckを持つ |
| `ansy` | `dev_nodes` | VM | Ansible開発環境 | Policyの方針2。再構築可能でcodeとVM backupを持つ前提から自動rebootに任せる |
| `quory` | `control_nodes` | 物理node | 本番Ansible / Semaphore実行基盤、Proxmox QDevice | Policyの方針2。実行基盤自身なので固定時刻の自動rebootを使う |

group所属は [`inventory-map.md`](../ansible/inventory-map.md)、認証基盤の依存は [`radius.md`](radius.md)、監視基盤の依存は [`monitoring.md`](monitoring.md)、開発 / 本番実行基盤の分離は [`overview.md`](overview.md) を参照する。nodeの仮想 / 物理種別や実際の配置は固定せず、inventoryと実行時の事実を正本とする。

## Ubuntu Proとreboot管理

- Ubuntu Proとunattended-upgradesがsecurity / ESM系の定常更新を担う。
- 方針1の`authy` / `monnie`はunattended-upgradesによる自動rebootを無効化し、Ansibleがreboot要否とpost-checkを扱うPolicy契約を持つ。
- 方針2の`ansy` / `quory`は自動rebootを使い、`ubuntu_nightly.yml`の対象にしないPolicy契約を持つ。
- `quory`は本番Ansible実行基盤であり、自身のrebootは進行中のAnsible jobと同一sessionで待機する方式に依存しない。

旧Policyの2026-05-27時点snapshotには、`authy` / `monnie`のAutomatic-Rebootがfalse、`quory`がtrueかつ固定時刻と記録されていた。これは移行時点の証跡であり、現在値を保証しない。現在の設定値は対象host上のunattended-upgrades設定を正本とし、本件では実機確認を行っていない。

## Service依存

- `authy`のpost-checkはFreeRADIUS serviceとRADIUS待受を対象にする。
- `monnie`のpost-checkはPrometheus、Grafana、Lokiの待受を対象にする。
- `monnie`のPrometheusはnon-aptでmanual installされた対象としてregistryに登録されている。
- `authy` / `monnie`のpatchまたはreboot中はautonomous recoveryとの競合を避けるため、該当playbookがtarget別muteを利用する。

具体的なservice名、port、registry、mute値、report pathはPolicyとcodeを参照する。本Contextから実行許可を導かない。
