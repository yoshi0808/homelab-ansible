# Ansible Inventory Map

現行inventoryの正本は `inventories/homelab/hosts.yml`、既定の選択は `ansible.cfg` である。この地図はgroupとホスト名の所属だけを示し、`ansible_host`、接続方式、認証、その他の接続値は複製しない。

## Groupから探す

| Inventory group | 所属ホスト名 | 主な対象領域 | 値の参照先 |
| --- | --- | --- | --- |
| `proxmox` | `pve1`, `pve2` | Proxmoxクラスタ、ノード、VM/CT管理 | `inventories/homelab/hosts.yml`, `inventories/homelab/group_vars/`, `inventories/homelab/host_vars/` |
| `radius_servers` | `authy` | RADIUS基盤、Ubuntu VM保守 | 同上 |
| `monitoring_servers` | `monnie` | 監視・ログ基盤、Ubuntu VM保守 | 同上 |
| `control_nodes` | `quory` | Ansible本番実行基盤、自動化・復旧基盤 | 同上 |
| `dev_nodes` | `ansy` | Ansible開発基盤 | 同上 |
| `semaphore_servers` | `ansy`, `quory` | Semaphoreを持つノードの横断指定 | 同上 |
| `sophos` | `sophos-fw` | Firewallの確認・限定保守 | 同上 |
| `cloudkey_devices` | `cloudkey` | CloudKeyの識別。接続方法は処理ごとに異なる | 同上 |
| `local` | `localhost` | controller上の検証、前処理、通知、オーケストレーション | 同上 |

`all` はAnsible組込みgroupで、このinventoryでは上記childrenを明示的に束ねる。

## ホストから探す

| ホスト名 | 所属group |
| --- | --- |
| `pve1` | `proxmox` |
| `pve2` | `proxmox` |
| `authy` | `radius_servers` |
| `monnie` | `monitoring_servers` |
| `quory` | `control_nodes`, `semaphore_servers` |
| `ansy` | `dev_nodes`, `semaphore_servers` |
| `sophos-fw` | `sophos` |
| `cloudkey` | `cloudkey_devices` |
| `localhost` | `local` |

## Playbookで現れる対象指定

- `ansy`, `quory`, `monnie`, `pve1`, `pve2` のようにホスト名を直接指定する入口がある。
- `ansy:quory:authy` のようなcolon区切りは複数のhost patternを束ねる。
- `target_node`、`target_hosts` のような変数指定は、実行時入力をinventory上の既知対象へ解決する。許可値と停止条件は対象playbookとPolicyを確認する。
- `brv_restore_targets` のような一時groupはplaybook実行中に作成され、静的inventoryには存在しない。
- CloudKeyを扱う処理には、`cloudkey_devices` を直接対象にせず、別ホストまたは `localhost` から接続する入口もある。接続値は関連varsとPolicyを参照する。
