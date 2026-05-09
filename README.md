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
│   │   │   ├── control_nodes.yml
│   │   │   ├── dev_nodes.yml
│   │   │   ├── proxmox.yml
│   │   │   └── radius_servers.yml
│   │   └── host_vars/
│   │       ├── pve1.yml
│   │       ├── pve2.yml
│   │       └── quory.yml
│   └── vars/
│       ├── mail.yml
│       └── proxmox_vm_home_nodes.yml
├── playbooks/
│   ├── proxmox_healthcheck.yml
│   ├── proxmox_hw_check.yml
│   ├── proxmox_patch_apply_node.yml
│   ├── proxmox_patch_dryrun.yml
│   └── radius_healthcheck.yml
├── roles/
│   ├── proxmox_healthcheck/
│   │   ├── defaults/
│   │   ├── files/
│   │   └── tasks/
│   ├── proxmox_hw_check/
│   │   ├── defaults/
│   │   ├── files/
│   │   └── tasks/
│   ├── proxmox_patch_apply_node/
│   │   ├── defaults/
│   │   ├── files/
│   │   └── tasks/
│   ├── proxmox_patch_dryrun/
│   │   ├── defaults/
│   │   ├── files/
│   │   └── tasks/
│   └── radius_healthcheck/
│       ├── defaults/
│       ├── files/
│       └── tasks/
├── scripts/
│   └── codex-classify.sh
├── reports/
│   ├── proxmox-dryrun/
│   ├── proxmox-hardware/
│   ├── proxmox-health/
│   ├── proxmox-patch/
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

### group_vars

SSHの接続情報を記載（公開鍵認証）

---

### vars/proxmox_vm_home_nodes.yml

VMが本来どのProxmoxノードに存在しているべきかを示すもの

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

## vars/mail.yml (.gitignore)

```
# inventories/homelab/vars/mail.yml（git管理しない）
smtp_host: smtp.gmail.com
smtp_port: 587
smtp_user: username@gmail.com
smtp_password: "xxxx xxxxgp xxxx xxxx"  # アプリパスワード
mail_to: username@gmail.com
```

---

