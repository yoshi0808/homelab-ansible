# homelab-ansible

## 概要

自宅環境（Proxmox / Ubuntu VM）の構成管理・運用自動化を目的とした Ansible リポジトリ。

主な用途：

- Proxmoxノードの状態確認
- Ubuntuサーバの共通設定管理
- 監視サーバ（quory）の構築
- 将来的な自動化・復旧の基盤

---

## 構成

```
ansy（Ansible制御ノード）
  ↓
pve1 / pve2（Proxmox）
  ↓
各VM（Ubuntuなど）
```

---

## ディレクトリ構成

```
homelab-ansible/
├── README.md
├── ansible.cfg
├── inventories/
│   ├── homelab/
│   │   ├── hosts.yml
│   │   ├── group_vars/
│   │   └── host_vars/
│   └── vars/
├── playbooks/
│   └── radius_healthcheck.yml
├── roles/
│   └── radius_healthcheck/
│       ├── defaults/
│       ├── files/
│       └── tasks/
├── scripts/
├── reports/
│   └── radius-health/
├── cloudinit/
└── docs/
    └── ai/
        ├── prompts/
        └── reviews/
```

---

## inventory

Inventory は `inventories/homelab/hosts.yml` を正とする。

```yaml
all:
  children:
    proxmox:
      hosts:
        pve1:
          ansible_host: pve1.internal
        pve2:
          ansible_host: pve2.internal
    radius_servers:
      hosts:
        authy:
          ansible_host: authy.internal
    control_nodes:
      hosts:
        quory:
          ansible_host: quory.internal
    dev_nodes:
      hosts:
        ansy:
          ansible_host: ansy.internal
    local:
      hosts:
        localhost:
          ansible_connection: local
```

---

## ansible.cfg

```
[defaults]
inventory = inventories/homelab/hosts.yml
roles_path = roles
host_key_checking = True
interpreter_python = /usr/bin/python3
retry_files_enabled = False
```

---

## 動作確認

```
ansible proxmox -m ping
ansible-inventory --graph
ansible-playbook playbooks/radius_healthcheck.yml --check
```

---

## 運用方針

- 変更前に必ず dry-run / check を実施
- 初期は read-only（状態確認）中心
- 破壊的変更は playbook を分離
- 設定はコードとして管理（Git）

---

## フェーズ

### Phase 1（現在）

- ansy構築
- Ansible疎通確認
- 基本構成作成

### Phase 2

- healthcheck playbook
- Ubuntu共通設定

### Phase 3

- quory（監視・quorum）構築
- Autoinstall導入

### Phase 4

- qdevice構成
- 監視通知

---

## セキュリティ

- SSH鍵は用途ごとに分離
  - id_ansible（インフラ用）
  - id_ed25519（GitHub用）
- ansyは内部ネットワーク限定
- Ubuntu Pro + unattended-upgrades適用

---

## 備考

- Cloud-initは初期構成のみ使用
- 本格的な設定はAnsibleで管理
- すべて再構築可能な状態を維持する
