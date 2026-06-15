# UniFi Backup Fetch Policy v1.0

作成日: 2026-06-15
版: v1.0
対象: CloudKey Gen2 Plus (UniFi OS) のシステムバックアップ週次取得（unifi_backup_fetch role / playbook）

参照:

- docs/ai/prompts/core.md
- docs/ai/prompts/cert_renew_cloudkey_policy.md（CloudKey への非公開 API 認証方式を共有）
- docs/ai/reviews/unifi_backup_fetch/（要求仕様・実装・レビュー一式）

---

## 変更履歴

| 版 | 日付 | 変更内容 |
|---|---|---|
| v1.0 | 2026-06-15 | 初版。UniFi OS システムバックアップを週次取得し Synology NFS へ保存する方式を定義。pve1 実機で E2E 検証済み。 |

---

## 1. 位置づけ（cert_renew_cloudkey_policy.md との関係）

本ポリシーは CloudKey へ「書き込む」cert デプロイとは独立した「取得」系である。
認証方式（UniFi OS 非公開 API ログイン）は cloudkey_cert_deploy と共有するが、
実行ホスト・目的・保存先が異なる。両者は障害を分離しており、片方が壊れても
もう片方には影響しない。

| 項目 | cloudkey_cert_deploy | unifi_backup_fetch（本ポリシー） |
|---|---|---|
| 目的 | Web UI TLS 証明書の配備 | システムバックアップの取得・保管 |
| 実行ホスト | localhost（quory / ansy） | **pve1**（NFS マウント保有ホスト） |
| 認証 | UniFi OS 非公開 API ログイン | 同左（ローカルアカウント） |
| 主な変更先 | CloudKey 上の証明書 | CloudKey 上で新規バックアップ生成 + Synology へ書込/削除 |
| 安全度 | 変更系 | 変更系（CloudKey 設定は変えない） |

---

## 2. 目的

CloudKey Gen2 Plus の UniFi OS システムバックアップ（`.unifi`）を週次で自動取得し、
Synology NAS に世代保管する。

- `/api/backup/download` は呼び出した瞬間に新規バックアップを生成して返すため、
  毎回「取得時点の最新」が保証される。
- 「設定が飛んだのに直近バックアップが無い／壊れていた」を避け、復旧の足場を常備する。

Network アプリ単体バックアップ（`.unf`）は取得しない。OS バックアップで十分とする。

---

## 3. 対象と実行

| 項目 | 内容 |
|---|---|
| 取得元 | CloudKey Gen2 Plus（`cloudkey.internal`、私設 CA = Home-TLS-CA） |
| 保存先 | `/mnt/pve/Synology-nfs/user-backup/unifi/`（pve1 上の既存 NFS マウント） |
| 実行ホスト | **pve1**（`connection: local` は使わず、pve1 上で `become: true`/root で実行） |
| 実行元 | quory（本番・週次）/ ansy（開発・CLI） |
| 安全度 | 変更系（CloudKey 上でバックアップ生成、Synology へ書込/削除） |

pve1 で root 実行する理由は、NFS のアクセス権が root に絞られているため。
CloudKey へは必ずホスト名で接続する（私設 CA + `Origin` ヘッダ必須。IP 直叩き禁止）。

---

## 4. ライフサイクル（block / rescue / always）

```text
Phase 0  失敗時の always が参照する値を play スコープ fact として初期化する
Phase 1  POST /api/auth/login → TOKEN(Cookie, JWT) と CSRF を取得する
Phase 2  GET /api/backup/download → バックアップ生成 + 一時ファイルへ DL（数秒）
Phase 3  ファイル名のタイムスタンプで鮮度ガード（現在時刻との差が閾値以内）
Phase 4  同一 FS 内の原子的 rename で Synology の最終パスへ確定（毎回上書き）
Phase 5  世代数を超える古いファイルを古い順に削除してローテーションする
rescue   失敗を捕捉する（unifi_backup_failed / error を記録）
always   一時ファイル掃除 → サマリ生成 → Slack 通知 → 失敗時のみ再 fail
```

---

## 5. 認証方式（cloudkey_cert_deploy と共有）

- ログイン: `POST https://cloudkey.internal/api/auth/login`
  - ボディ: `{"username": "{{ cloudkey_api_user }}", "password": "{{ cloudkey_api_password }}"}`
  - 認証情報は `inventories/vars/cloudkey.yml`（Ansible Vault 暗号化済み）から取得する。
  - アカウントは UniFi OS の**ローカルアカウント**（2FA 無効・API 利用可）。
    クラウド SSO / 2FA 有効アカウントは `/api/auth/login` で弾かれる。
- TOKEN: レスポンスの `Set-Cookie` の `TOKEN`（JWT）を Cookie として保持する。
- CSRF（優先順位）: レスポンスヘッダー **`X-CSRF-Token` を最優先**、無ければ
  `X-Updated-CSRF-Token`。**両ヘッダーとも空のときに限り**、JWT ペイロードの
  `csrfToken` をデコードして fallback とする（ヘッダーが有効なら JWT は一切触らない）。
  - 実機（CloudKey Gen2 Plus, 2026-06-15）ではログイン応答に両ヘッダーが返り、
    供給源は `X-CSRF-Token` になる。JWT fallback は CloudKey 側仕様変更時の保険。
- 認証ヘッダー: 状態に関わる要求には `Cookie: TOKEN=<JWT>` / `X-CSRF-Token: <csrf>` /
  `Origin: https://cloudkey.internal` を付与する。
- `validate_certs: false`（私設 CA のため）。
- 秘密情報（認証情報・TOKEN・CSRF・認証ヘッダー）を扱うタスクには `no_log: true` を付ける。

---

## 6. ファイル命名と世代管理

- ファイル名: ダウンロード応答からサーバ提示名をそのまま使う。
  例: `unifi_os_backup_1781526993574_<uuid>.unifi`
  - **実装上の注意**: `/api/backup/download` は `Content-Disposition` を返さない。
    `ansible.builtin.uri` は `dest` 利用時にサーバ提示名を **`filename`** フィールドへ
    格納するため、そこから取得する（`content_disposition` のパースは不可）。
- ファイル名検証（保存先外への書き出し防止 / 多層防御）:
  - allowlist 正規表現 `^unifi_os_backup_[0-9]+_[0-9A-Za-z-]+\.unifi$`
  - `basename` 一致、`/`・`..`・`\` の不在を確定前に assert する。
- 確定: 一時ファイルは保存先と**同一 FS**（NFS）に置き、原子的 rename（`mv -f`）で確定する。
  同名が既にあっても**毎回上書き**する（取得済みを捨てて成功扱いにしない）。
- 世代数: 既定 **8 世代**。ファイル名のタイムスタンプ昇順（= 文字列昇順、ms は固定桁）で
  ソートし、超過分を古い順に削除する。
- 保存パーミッション: `0640` / root。

---

## 7. 鮮度ガード（Phase 3）

ファイル名に埋め込まれたタイムスタンプ（エポックミリ秒）と**実行ホスト pve1 の現在時刻**
（`date +%s%3N`）を比較し、差の絶対値が **既定 60 秒**を超える場合は fail する。

- 目的: 古いキャッシュや意図しないファイルを「最新」と誤認して保存しないため。
- 前提: pve1 と CloudKey の時刻が NTP 同期していること。大きくずれると Phase 3 で fail する。
- 一時的に緩める場合は extra-vars: `-e unifi_backup_freshness_max_seconds=120`。

---

## 8. 通知方針

`roles/common_slack/tasks/notify.yml` を `include_tasks` で呼ぶ（best-effort、本処理を止めない）。
サマリには `csrf source` / `freshness age` / `kept generations` / `deleted old backups` を含める。

| 状況 | チャンネル | status |
|---|---|---|
| 取得・保存 OK | #info | ok |
| 失敗（認証・DL・保存・鮮度 NG 等） | #alerts | error |

通知失敗（Vault 復号エラー・Webhook 到達不能など）は best-effort として無視する。

---

## 9. 自動実行

`ubuntu_vm_patch_policy.md` の深夜リブートスケジュールと衝突しない時間帯に、quory の
systemd timer で**週次**実行する（Semaphore UI 導入後は Schedule へ移行）。

- Ansible playbook 内で git pull はしない（core.md §11）。
- 未確認コードを timer で自動実行しない（core.md §12 / §17）。確定済みコードのみ。

参考: 深夜帯は 01:00 UniFi Console / 02:00 UniFi Device / 03:00 quory / 03:30 authy・monnie が
稼働するため、本取得はそれらと重ならない週次枠に置く。

---

## 10. 制約・禁止事項

```text
- IP リテラルをファイルに書かない（core.md §3）。cloudkey.internal で接続する。
- 秘密情報（認証情報・TOKEN・CSRF）を扱うタスクには no_log: true を付ける。
- 秘密情報・バックアップ実体をリポジトリにコミットしない。
- CloudKey の設定は変更しない（生成・取得のみ）。
- read-only 系と混ぜず、変更系 playbook として独立させる。
- pve1 が CloudKey へ到達できること・正しい機器であること（TLS subject/issuer）を前提とする。
```

---

## 11. 構成ファイル

| ファイル | 役割 |
|---|---|
| `playbooks/unifi_backup_fetch.yml` | 入口。pve1 / become 実行、block・rescue・always、Slack 通知、再 fail。 |
| `roles/unifi_backup_fetch/tasks/main.yml` | Phase 0〜5 のライフサイクル本体。 |
| `roles/unifi_backup_fetch/defaults/main.yml` | 既定パラメータ（下表）。 |
| `inventories/vars/cloudkey.yml`（Vault） | `cloudkey_api_user` / `cloudkey_api_password`（cloudkey_cert_deploy と共有）。 |

### 既定パラメータ（defaults/main.yml）

| 変数 | 既定値 | 意味 |
|---|---|---|
| `cloudkey_host` | `cloudkey.internal` | 接続先（ホスト名必須） |
| `unifi_backup_login_path` | `/api/auth/login` | ログイン API |
| `unifi_backup_download_path` | `/api/backup/download` | 生成 + DL API |
| `unifi_backup_dest_dir` | `/mnt/pve/Synology-nfs/user-backup/unifi` | 保存先（末尾スラッシュなし） |
| `unifi_backup_tmp_path` | `<dest_dir>/.unifi_backup_fetch.download.tmp` | 同一 FS の一時ファイル |
| `unifi_backup_keep_generations` | `8` | 残す世代数 |
| `unifi_backup_freshness_max_seconds` | `60` | 鮮度ガードの許容秒 |
| `unifi_backup_download_timeout` | `120` | DL タイムアウト秒 |

---

## 12. 実機検証状況（2026-06-15, pve1）

- ログイン 200 / CSRF はヘッダー（`X-CSRF-Token`）から取得（JWT fallback 不発）。
- 取得 → 鮮度ガード通過 → Synology 保存 → ローテーション → Slack 通知（#info）まで
  E2E 成功（`PLAY RECAP: failed=0 rescued=0`）。
- 保存例: `unifi_os_backup_1781526993574_<uuid>.unifi`（約 669KB, `0640` root, 1 世代）。
- 8 世代超の実削除は世代蓄積後に運用で確認する（ロジックはダミーデータ検証済み）。

### 運用メモ

- CloudKey 側パスワードを変更したら、`ansible-vault edit inventories/vars/cloudkey.yml` で
  `cloudkey_api_password` を更新する。無効資格では `/api/auth/login` が
  `403 AUTHENTICATION_FAILED_INVALID_CREDENTIALS` を返す（cloudkey_cert_deploy も同時に失敗する）。
```
