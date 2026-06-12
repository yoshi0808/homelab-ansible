# cert_renew Policy

作成日: 2026-06-05
改版日: 2026-06-12
版: v2.0
対象: homelab 環境のTLS証明書自動更新（cert_renew role）

---

## 変更履歴

| 版 | 日付 | 変更内容 |
|---|---|---|
| v1.0 | 2026-06-05 | 初版。ルートCA(Home-RADIUS-CA)直接署名方式。 |
| v2.0 | 2026-06-12 | 中間CA(Home-TLS-CA)署名方式へ移行。フルチェーン配布・中間CA有効期限監視を追加。ルートCA秘密鍵のオフライン保管に伴う変更。 |

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

cert_renew_quory.yml は quory のみを対象とする。ansy の証明書はこのPlaybookには含まれない。

---

## 4. CA構成

### 4.1 CA階層

```
Home-RADIUS-CA (ルートCA)
  └── Home-TLS-CA (中間CA) ← v2.0以降の署名CA
        └── リーフ証明書 (各ホスト)
```

### 4.2 方式: ファイルコピー方式（中間CA署名）

CA証明書・CA秘密鍵は quory 上の永続ファイルから取得する。
両 Playbook とも quory 以外での実行を禁止しているため、ansy への CA 配置は不要である。

```
/home/yoshi/.cert/ca/home_tls_ca.crt
/home/yoshi/.cert/ca/home_tls_ca.key
```

これらのファイルを実行時に `/run/semaphore-ca/`（tmpfs）へコピーし、処理後に削除する。

Playbookは実行前にソースファイルの存在確認とCA秘密鍵のmode 0600チェックを行い、
条件を満たさない場合はfailする。

### 4.3 ルートCA秘密鍵のオフライン保管（v2.0変更点）

ルートCA(Home-RADIUS-CA)の秘密鍵はオフライン保管に移行済みであり、
quory上には存在しない。

- ルートCAは直接TLS証明書を署名しない
- 中間CA(Home-TLS-CA)の証明書・秘密鍵が quory のみに配置される
- 中間CAのみを用いて日常のTLS証明書を署名する

### 4.4 CA秘密鍵の保管

| 項目 | 内容 |
|---|---|
| 保管場所 | **quory のみ** `/home/yoshi/.cert/ca/home_tls_ca.key`（ansy への配置は不要） |
| 権限 | `chmod 600`（必須。Playbookが実行前に検証する） |
| 所有者 | `yoshi`（推奨。root で読める限りPlaybookの動作は可能） |
| Git管理 | しない（`.gitignore` で `.cert/` を除外） |
| バックアップ | quory OS再インストール時に手動で再配置が必要 |
| 復旧手順 | 下記 §10 参照 |

### 4.5 CA秘密鍵の所有者チェックについて

Playbookはmode 0600のみを検証し、ownerは検証しない。

理由:
- Playbookは `become: true` で実行するためrootとして動作し、ownerに関係なく読める
- mode 0600であれば世界から読まれるリスクは排除されている
- ownerをhardcodeすると環境変更時に壊れる

---

## 5. CA証明書の一時展開とcleanup

```
処理前:  /home/yoshi/.cert/ca/home_tls_ca.{crt,key}（永続）
         ↓ コピー
実行中:  /run/semaphore-ca/ca.{crt,key}（tmpfs、処理後に削除）
         ↓ cleanup
処理後:  /run/semaphore-ca/ ディレクトリごと削除
```

cleanup失敗は `cert_cleanup_status` ファクトで記録し、最終的にPlaybookがfailする。

---

## 6. フルチェーン配布（v2.0追加）

中間CAで署名したリーフ証明書を配布する場合、クライアントはルートCAから中間CAへの
チェーンを検証する必要がある。リーフ証明書単体の配布ではクライアント側でチェーン検証が失敗する。

v2.0 以降、配布するサーバー証明書は以下のフルチェーン形式とする。

```
リーフ証明書（各ホスト固有）
+
中間CA証明書（home_tls_ca.crt）
```

生成タイミング: issue.yml の署名タスク直後に quory（tmpfs）上で cat 連結して作成する。

ファイルパス: `{{ cert_renew_ca_dir }}/certs/{{ inventory_hostname }}.fullchain.crt`

---

## 7. 中間CA有効期限監視（v2.0追加）

prepare_ca.yml の実行時に home_tls_ca.crt の残存日数を確認する。

| 残存日数 | 動作 |
|---|---|
| 90日以上 | 正常（何もしない） |
| 90日未満 | WARNING ログ出力 + `cert_intermediate_ca_warn: true` ファクト設定 |

WARNING が検出された場合、通知の Slack メッセージに以下が追記される。

```
WARNING: Intermediate CA expires in N days!
```

中間CAは有効期間10年である。失効前の再発行が唯一の能動的更新イベントであり、
定期的な目視確認（年1回以上）を推奨する。

---

## 8. 失敗検知

| Playbook | 失敗検知方法 |
|---|---|
| `cert_renew.yml` | 完了Slack通知を送る。cleanup失敗などPlaybook本体の失敗は fail タスクで検知する。 |
| `cert_renew_quory.yml` | 完了Slack通知を送る。cleanup失敗はSlack通知後に fail する。加えて systemd unitのexitコードでも検知できる（journalctl / OnFailure=）。 |

通知チャンネルの選択:
- `alerts`: FAILED または WARNING を含む場合
- `info`: 正常完了の場合

---

## 9. 証明書仕様

| 項目 | 値 |
|---|---|
| 有効期間 | 45日 |
| 更新条件 | 残日数 15日以下（または `force_renew: true`） |
| 鍵アルゴリズム | EC secp384r1 |
| SAN | DNS + IPv4（発行時に CA ホストで `getent ahostsv4` により動的取得） |

---

## 10. CA復旧・移行手順

### 初回 Home-TLS-CA 移行時の実行手順

`cert_renew.yml` は既存証明書の残存日数が 15 日超の場合、発行済みCAの issuer によらず更新をスキップする。
初回移行では全対象を確実に更新するために `force_renew: true` を指定して実行すること。

**cert_renew_quory.yml**（quory の Semaphore 証明書）:
play 内で `force_renew: true` が固定済みのため、通常どおり実行するだけでよい。

```sh
ansible-playbook -i inventories/homelab/hosts.yml playbooks/cert_renew_quory.yml
```

**cert_renew.yml**（ansy / pve1 / pve2 / monnie）:
`force_renew: true` を明示して実行する。

```sh
ansible-playbook -i inventories/homelab/hosts.yml playbooks/cert_renew.yml \
  -e force_renew=true
```

Semaphore から実行する場合は Task Template の Extra Variables に `force_renew: true` を設定する。

`cert_renew_quory.yml` は playbook 内の vars で `force_renew: true` を固定している。

運用は両経路とも force_renew=true の月次強制再発行とする。閾値条件(残15日以下)は、月次実行間隔に対して安全マージンが不足するため運用上は使用しない(forceなし手動実行時のフォールバックとして残置)。

---

### 中間CA秘密鍵の再配置（quory OS再インストール時など）

1. 中間CA秘密鍵バックアップを安全なメディアから取得する
2. **quory 上にのみ** 配置する（ansy への配置は不要）

   ```sh
   mkdir -p /home/yoshi/.cert/ca
   cp home_tls_ca.key /home/yoshi/.cert/ca/home_tls_ca.key
   cp home_tls_ca.crt /home/yoshi/.cert/ca/home_tls_ca.crt
   chmod 600 /home/yoshi/.cert/ca/home_tls_ca.key
   chmod 644 /home/yoshi/.cert/ca/home_tls_ca.crt
   ```

3. Playbookを実行して証明書を再発行する

### 中間CA自体の再発行（有効期限切れ前）

1. オフライン保管のルートCA秘密鍵を使用して新しい中間CA証明書を発行する
2. 新しい `home_tls_ca.{crt,key}` を quory のみの `/home/yoshi/.cert/ca/` に配置する
3. `force_renew: true` で cert_renew.yml / cert_renew_quory.yml を実行して全ホストの証明書を更新する

---

## 11. 除外対象

以下は本roleの管轄外である。

| 対象 | 理由 |
|---|---|
| CloudKey の証明書 | 内蔵 Let's Encrypt で運用継続 |
| authy の EAP-TLS クライアント/サーバー証明書 | ルートCA直下30年、別管理 |
