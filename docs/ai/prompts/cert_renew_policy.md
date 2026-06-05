# cert_renew Policy

作成日: 2026-06-05
版: v1.0
対象: homelab 環境のTLS証明書自動更新（cert_renew role）

---

## 1. 目的

homelab内の管理系Web UIのTLS証明書を自動更新する。
ブラウザの証明書警告を解消し、短命証明書（45日）運用を維持する。

---

## 2. 対象サービス

| ホスト | サービス | Playbook |
|---|---|---|
| `ansy` | Semaphore | `cert_renew.yml`（Semaphoreから実行） |
| `quory` | Semaphore | `cert_renew_quory.yml`（systemd timerから実行） |
| `pve1` | pveproxy | `cert_renew.yml` |
| `pve2` | pveproxy | `cert_renew.yml` |
| `monnie` | Grafana | `cert_renew.yml` |

---

## 3. Playbook分離の理由

`cert_renew_quory.yml` を独立したPlaybookとして分離している理由:

- `cert_renew.yml` はSemaphoreから実行する
- quoryのSemaphore証明書を `cert_renew.yml` で更新すると、更新処理の途中でSemaphore自身が再起動される
- これにより実行中のPlaybookが中断される
- quoryのSemaphore証明書はsystemd timerから独立したPlaybookで更新する

---

## 4. CA鍵の取得方式

### 4.1 方式: ファイルコピー方式

CA証明書・CA秘密鍵は quory 上の永続ファイルから取得する。

```
/home/yoshi/.cert/radius_ca.crt
/home/yoshi/.cert/radius_ca.key
```

これらのファイルを実行時に `/run/semaphore-ca/`（tmpfs）へコピーし、処理後に削除する。

Playbookは実行前にソースファイルの存在確認とCA秘密鍵のmode 0600チェックを行い、
条件を満たさない場合はfailする。

### 4.2 設計変更の経緯

初回要求仕様（`2026-06-03_001_requirement.md`）では Semaphore Variables（Secrets）の
環境変数 `homelab-ca-crt` / `homelab-ca-key` から取得する方式を採用していた。

ファイルコピー方式に変更した理由:
- Semaphore Secrets経由の環境変数は base64エンコード + PEM改行変換が必要だった（`fix_pem.py`）
- ファイルコピー方式はそのまま使えるため実装がシンプルになる
- `cert_renew_quory.yml`（systemd timerから実行）はSemaphoreの環境変数を使えないため、
  両PlaybookでCA取得方式を統一するためにファイルコピー方式を採用した

### 4.3 CA秘密鍵の保管

| 項目 | 内容 |
|---|---|
| 保管場所 | quory の `/home/yoshi/.cert/radius_ca.key` |
| 権限 | `chmod 600`（必須。Playbookが実行前に検証する） |
| 所有者 | `yoshi`（推奨。root で読める限りPlaybookの動作は可能） |
| Git管理 | しない（`.gitignore` で `.cert/` を除外） |
| バックアップ | quory OS再インストール時に手動で再配置が必要 |
| 復旧手順 | CA秘密鍵のバックアップから `/home/yoshi/.cert/` に配置し `chmod 600` する |

### 4.4 CA秘密鍵の所有者チェックについて

Playbookはmode 0600のみを検証し、ownerは検証しない。

理由:
- Playbookは `become: true` で実行するためrootとして動作し、ownerに関係なく読める
- mode 0600であれば世界から読まれるリスクは排除されている
- ownerをhardcodeすると環境変更時に壊れる

---

## 5. CA証明書の一時展開とcleanup

```
処理前:  /home/yoshi/.cert/radius_ca.{crt,key}（永続）
         ↓ コピー
実行中:  /run/semaphore-ca/ca.{crt,key}（tmpfs、処理後に削除）
         ↓ cleanup
処理後:  /run/semaphore-ca/ ディレクトリごと削除
```

cleanup失敗は `cert_cleanup_status` ファクトで記録し、最終的にPlaybookがfailする。

---

## 6. 失敗検知

| Playbook | 失敗検知方法 |
|---|---|
| `cert_renew.yml` | 完了メールを送る（メール送信失敗は `ignore_errors: true` で無視）。cleanup失敗などPlaybook本体の失敗は fail タスクで検知する。 |
| `cert_renew_quory.yml` | 完了メールを送る（`cert_renew.yml` と同様）。cleanup失敗はメール送信後に fail する。メール送信失敗は `ignore_errors: true` で無視する。加えて systemd unitのexitコードでも検知できる（journalctl / OnFailure=）。 |

### 6.1 cert_renew_quory.yml の通知実行環境要件

`cert_renew_quory.yml` は systemd timer から実行するため、以下が実行環境に必要になる。

- `ansible.cfg` の `vault_password_file` が設定されていること（`inventories/vars/mail.yml` は Vault 暗号化済み）
- `inventories/vars/mail.yml` が読み取れること

これらが欠けている場合、notification play の `Load mail variables` タスクで fail する。

---

## 7. 証明書仕様

| 項目 | 値 |
|---|---|
| 有効期間 | 45日 |
| 更新条件 | 残日数 15日以下（または `force_renew: true`） |
| 鍵アルゴリズム | EC secp384r1 |
| SAN | DNS + IPv4（発行時に CA ホストで `getent ahostsv4` により動的取得） |
