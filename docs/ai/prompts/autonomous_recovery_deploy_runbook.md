# 自律復旧パイプライン デプロイ手順書（ansy 開発フェーズ）

対象 policy: `autonomous_recovery_policy.md` v0.5  
対象ロール: `recovery_exec`, `recovery_io`  
最終更新: 2026-06-28

---

## 凡例

| 表記 | 意味 |
|------|------|
| `[controller]` | `ansible-playbook` を叩くノード（ansy またはローカル開発機） |
| `[ansy]` | ansy に SSH してインタラクティブに実行 |

Playbook 内の `delegate_to` により authy/monnie への操作は自動で行われます。

---

## 実行順序まとめ

```
A-1 → A-2 → A-3 → A-4 → A-5 → A-6   （初回のみ、この順番で）
B-1                                     （ansy リブート後のたびに）
C-1                                     （OAuth トークン切れの場合のみ）
C-2                                     （target ノード停止中だった場合のみ）
```

---

## 種別 A: 初回のみ（再実行不要）

### A-1. recovery_exec デプロイ

ノード: `[controller]`

```bash
ansible-playbook playbooks/recovery_exec_setup.yml -l ansy
```

内部で自動実行される内容:

- **ansy**: recovery-exec ユーザー作成 / SSH 鍵 2 本生成 / wrapper スクリプト配置 / Codex config + AGENTS.md 配置
- **authy**: recovery-exec ユーザー作成 / dispatch・action スクリプト配置 / authorized_keys 登録 / sudoers 配置
- **monnie**: 同上

---

### A-2. Codex ブラウザ OAuth 認証

ノード: `[ansy]`（ブラウザが開けるセッションが必要）

```bash
sudo -H -u recovery-exec codex
```

ブラウザが開いたら OAuth フローを完了し、完了後 `Ctrl+C` で抜けます。  
以後、リブートしても `auth.json` にトークンが残るため再実行不要です。

---

### A-3. OS 権限確認

ノード: `[ansy]`

```bash
# auth.json が 0600 owned by recovery-exec であることを確認
sudo stat /home/recovery-exec/.codex/auth.json

# 低権限ユーザーから読めないこと（Permission denied）を確認
sudo -u nobody cat /home/recovery-exec/.codex/auth.json

# SSH 秘密鍵が 0600 であることを確認
sudo stat /home/recovery-exec/.ssh/id_recovery_investigate
sudo stat /home/recovery-exec/.ssh/id_recovery_action
```

期待結果:
- `stat` の出力で `Uid: (recovery-exec)` かつ `Access: (0600/-rw-------)` であること
- `nobody` での `cat` は `Permission denied` であること

---

### A-4. SSH 疎通確認（investigate 鍵）

ノード: `[ansy]`

```bash
# authy への疎通（freeradius / sshd のステータスが返ること）
sudo -u recovery-exec ssh -T \
    -i /home/recovery-exec/.ssh/id_recovery_investigate \
    -o StrictHostKeyChecking=yes \
    recovery-exec@authy.internal status

# monnie への疎通（監視スタックのステータスが返ること）
sudo -u recovery-exec ssh -T \
    -i /home/recovery-exec/.ssh/id_recovery_investigate \
    -o StrictHostKeyChecking=yes \
    recovery-exec@monnie.internal status
```

---

### A-5. recovery_io デプロイ

ノード: `[controller]`

```bash
ansible-playbook playbooks/recovery_io_setup.yml -l ansy
```

内部で自動実行される内容:

- **ansy**: recovery-io ユーザー作成 / Python venv + slack-bolt インストール / listener スクリプト配置 / sudoers 配置 / service unit 配置

> **注意**: サービスは自動起動しません（ansy 開発フェーズは手動起動が原則）。

---

### A-6. Codex 単体スモークテスト（Slack なし）

ノード: `[ansy]`

```bash
sudo -H -u recovery-exec /usr/local/bin/codex-exec-wrapper exec \
    --cd /var/lib/recovery-exec/workspace \
    "authy の freeradius のステータスを確認してください"
```

期待動作: Codex が `homelab-investigate-authy status` を呼び出し、結果を日本語でターミナルに出力する。

---

## 種別 B: ansy リブート後に毎回実行

### B-1. recovery-io サービスを手動起動

ノード: `[ansy]`

```bash
sudo systemctl start recovery-io
sudo systemctl status recovery-io   # Active: active (running) であること
```

> **recovery-exec は常駐プロセスではないため追加操作は不要。**  
> OAuth トークンは auth.json に残るため再認証も不要です。

---

### B-2. Slack から動作確認（任意）

```
@Homelab authy の freeradius を調べてください
```

---

## 種別 C: 必要時のみ（イレギュラー）

### C-1. OAuth トークン期限切れ時の再認証

ノード: `[ansy]`

```bash
sudo -H -u recovery-exec codex
# ブラウザ OAuth フローを完了後 Ctrl+C
```

---

### C-2. target ノードが停止中だった場合の再セットアップ

authy または monnie が A-1 実行時に停止していた場合、復旧後に再実行します。

ノード: `[controller]`

```bash
ansible-playbook playbooks/recovery_exec_setup.yml -l ansy
```

> `recovery_exec_setup_targets` はデフォルト `true` のため、target 側の設定が自動で再適用されます。

---

## quory への移行時（将来対応）

ansy での開発が完了し quory を本番環境にする際の追加手順:

```bash
# 1. quory に recovery_exec デプロイ（SSH 鍵は quory 上で新規生成される）
ansible-playbook playbooks/recovery_exec_setup.yml -l quory

# 2. quory で Codex OAuth 認証
sudo -H -u recovery-exec codex

# 3. quory に recovery_io デプロイ（自動起動 ON）
ansible-playbook playbooks/recovery_io_setup.yml -l quory \
    -e recovery_io_service_enabled=true

# 4. ansy の recovery-io を停止・無効化
sudo systemctl stop recovery-io
sudo systemctl disable recovery-io

# 5. ansy と quory で同時稼働しないことを確認
sudo systemctl is-active recovery-io   # → inactive であること（ansy で実行）
```

> ansy と quory で同時稼働させないこと（§7 禁則）。
