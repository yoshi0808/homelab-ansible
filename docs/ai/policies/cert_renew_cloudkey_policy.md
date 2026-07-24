# cert_renew CloudKey Policy

本書はCloudKey Web UI certificateの発行、API配備、live verification、旧世代削除に関する許可、禁止、停止条件、判断軸の正本である。実装詳細はcode / mapを参照し、競合時は本Policyを優先する。

## 1. 目的

### cert_renew Policyとの関係

<!-- CCK-001 -->
`cert_renew_policy.md`（cert_renew role）は CloudKey を管轄外としている。
CloudKey は cert_renew とは認証・配送・鍵方式が根本的に異なるため、
本ポリシーで独立して定義する。両者は障害を分離しており、
本仕組みが壊れても cert_renew（pve / monnie / ansy / quory）は影響を受けない。

| 項目 | cert_renew | cloudkey_cert_deploy（本ポリシー） |
|---|---|---|
| 鍵アルゴリズム | EC secp384r1 | RSA 2048 / PKCS#1 |
| 配送 | ファイル配置 + サービス再起動（SSH/become） | UniFi OS 非公開 HTTP API |
| 認証 | SSH（ann鍵 + become） | API ログイン（Vault管理local account） |
| 実行元 | quory のみ | quory（本番）/ ansy（開発） |
| 配布チェーン | リーフ + 中間CA | リーフ + 中間CA + ルートCA（フルチェーン） |

### 目的

<!-- CCK-002 -->
CloudKey Gen2 Plus のローカルWeb UI（https://cloudkey.internal）のTLS証明書を、
Home-TLS-CA（中間CA）署名の短命証明書（45日）で自動更新する。

- CloudKeyを内蔵Let's Encrypt運用から離脱させ、homelab全体の証明書を
  Home-TLS-CA配下の私設運用に統一する。
- Let's Encrypt利用に伴う Certificate Transparency ログへのホスト名露出を解消する。
- ブラウザの証明書警告を解消する。

## 2. 対象と実行範囲

### 対象と実行経路

<!-- CCK-003 -->
| 項目 | 内容 |
|---|---|
| デプロイ先 | CloudKey Gen2 Plus（`cloudkey.internal`） |
| Playbook | `playbooks/cloudkey_cert_deploy.yml`（変更系） |
| role | `roles/cloudkey_cert_deploy/` |
| 実行元（本番） | quory（Semaphore Task Template、月次） |
| 実行元（開発） | ansy（CLI 実行を許可） |

通信先はAnsible管理対象ホスト（ann + SSH）ではなく**外部のCloudKey API**である。
証明書の署名は実行元（quory または ansy）の 実行controller localで行い、CloudKeyへは
API経由でアップロードする。`localhost`（connection: local）で実行する。
冒頭で実行ホストが quory / ansy であることを assert する。

### CA構成

cert_renew と同一のCA階層を使う。

```
Home-RADIUS-CA (ルートCA)
  └── Home-TLS-CA (中間CA) ← 署名CA
        └── リーフ証明書 (CloudKey)
```

| ファイル | 用途 |
|---|---|
| `controller CA directory/home_tls_ca.crt` | 中間CA証明書（署名 + フルチェーン） |
| `controller CA directory/home_tls_ca.key` | 中間CA秘密鍵（署名。mode 0600） |
| `controller CA directory/radius_ca.crt` | ルートCA証明書（フルチェーン構築用） |

<!-- CCK-005 -->
cert_renew がフルチェーンに含めるのは中間CAまでだが、CloudKey（UniFi OS）は
**私設CAではルートCAまで含めないと検証に失敗する**ため、配布証明書は
リーフ + 中間CA + ルートCA の3階層フルチェーンとする。

### 4.1 資材配置（cert_renew との差分）

cert_renew では assert により quory 限定のため ansy に CA は不要と判断し
ansy から CA を削除した。本仕組みは **ansy からの実行も許可する**ため、
quory / ansy 両ホストの `controller CA directory/` に以下を配置する。
用途が異なるため cert_renew_policy.md と矛盾しない。

- 中間CA: 証明書 + 秘密鍵（`home_tls_ca.{crt,key}`）
- ルートCA: 証明書のみ（`radius_ca.crt`）

CA秘密鍵はGit管理しない（`.gitignore` で `.cert/` を除外）。

### certificate specification

<!-- CCK-006 -->
| 項目 | 値 | 備考 |
|---|---|---|
| 署名CA | Home-TLS-CA（中間CA） | cert_renew と同じ |
| 鍵アルゴリズム | **RSA 2048** | UniFi OSはECDSAを受け付けない |
| 鍵フォーマット | **PKCS#1**（`BEGIN RSA PRIVATE KEY`） | PKCS#8では登録に失敗する |
| 有効期間 | 45日 | cert_renew と統一。force運用（毎回新規発行） |
| SAN | DNS:cloudkey.internal + IPv4（`getent ahostsv4` で動的取得） | IPはハードコードしない |
| keyUsage | critical, digitalSignature, keyEncipherment | |
| extendedKeyUsage | serverAuth | |
| 署名ダイジェスト | sha384 | |
| 配布形態 | フルチェーン（リーフ + Home-TLS-CA + Home-RADIUS-CA） | 3階層 |

リーフの発行は `community.crypto`（openssl_privatekey / openssl_csr /
x509_certificate provider=ownca）で行う。

### 除外対象

<!-- CCK-019 -->
以下は本ポリシー / role の管轄外である。

| 対象 | 理由 |
|---|---|
| cert_renew 本体への統合 | 認証・配送・鍵方式が異なるため独立を維持（`cert_renew_policy.md`） |
| Let's Encrypt 証明書の削除 | 当面残す（観測用）。削除対象は source=uploaded のみ |
| 公式証明書管理API対応 | 提供されていないため |
| 自動化専用ローカル管理者アカウントの分離 | 将来検討 |

## 3. 対応するPlaybook

<!-- CCK-004 -->
| Playbook | 役割 |
|---|---|
| `cloudkey_cert_deploy.yml` | CloudKey Gen2 Plus のWeb UI TLS証明書を、Home-TLS-CA署名の短命証明書で更新する。UniFi OS非公開API経由で配備する（SSH/becomeではない）。 |

本表は関連入口のindexであり、tester-gateと本Policyを満たさない実行を許可しない。

## 4. 判断軸

### certificate name

<!-- CCK-009 -->
世代が分かるユニーク名 `cloudkey-<iso8601_basic_short>`（秒精度タイムスタンプ）。

name / fingerprint はともにユニーク制約があり、同名・同指紋は登録できない
（`USER_CERTIFICATE_DUPLICATE`）。`cloudkey-YYYY-MM` のような月精度名では
同月内の再実行（新規アップロードは旧削除より前に実行される）で衝突するため、
秒精度のタイムスタンプを採用する。

### 旧certificateのdelete条件

<!-- CCK-010 -->
旧証明書の削除は、有効化＋配信検証の**成功後**に証明書一覧を**再取得**し、
以下の全条件を満たすものに限定する。

- `source == uploaded`
- `active == false`（定義済みかつ非アクティブ）
- `id != （新証明書のid）`

<!-- CCK-011 -->
これにより、アクティブ証明書・新証明書・Let's Encrypt証明書
（name: "Yoshi", source: lets_encrypt）を削除対象から除外する。
DELETE直前に assert で上記条件を固定する。
検証が失敗した場合は **DELETEへ進まず、旧証明書を残して fail** する。

### live delivery verification

<!-- CCK-012 -->
机上（連結したPEM）ではなく、**実際にTLSで配信されるチェーン**を検証する。

1. リーフ指紋一致: `community.crypto.get_certificate` で配信リーフの指紋を取得し、
   アップロードAPIレスポンスの fingerprint と正規化照合（有効化直後は再起動途中の
   ことがあるためリトライ。既定6回 × 5秒）。
2. 3階層順序一致: `openssl s_client -showcerts` で配信チェーンを取得（収集のみ）し、
   証明書単位の順序付きリストに分割して、0/1/2番目がそれぞれ
   リーフ / Home-TLS-CA / Home-RADIUS-CA と**位置一致**することを確認する。
   段数が3であることも確認する。

<!-- CCK-013 -->
総合判定 `cloudkey_verify_ok = リーフ指紋一致 and 3階層順序一致`。
`openssl s_client` を使う shell は情報収集のみで、判定と fail 制御は
Ansible tasks 側に置く（core.md §7 / §9 の責務分離）。

## 5. ライフサイクル・処理フロー

### full lifecycle

<!-- CCK-007 -->
```
1. リーフ証明書を発行（実行元ローカルで署名。毎回新規＝指紋ユニーク）
2. CloudKeyへログイン（POST /api/auth/login）してTOKENを取得
3. 新証明書をアップロード（POST /api/userCertificates。世代名で登録）
4. アップロードした証明書を有効化（PUT /api/userCertificates/{id}/status）
5. 配信中の証明書を検証（指紋一致 + 3階層順序一致）
6. 旧 uploaded 証明書を削除（DELETE /api/userCertificates/{id}）
7. 結果をSlackへ通知
```

「新規アップロード → 有効化 → 検証 → 旧削除」の順とし、切り替わりが確認できる
まで旧を消さない（ダウンタイム・ロールバック可能性の確保）。

### API contract

<!-- CCK-008 -->
| 操作 | メソッド + パス | ボディ |
|---|---|---|
| ログイン | POST /api/auth/login | {username, password} |
| 一覧 | GET /api/userCertificates | － |
| アップロード | POST /api/userCertificates | {name, key, cert} |
| 有効化 | PUT /api/userCertificates/{id}/status | {"active": true} |
| 削除 | DELETE /api/userCertificates/{id} | （204応答） |

認証:

- ログイン応答の `Set-Cookie` の `TOKEN`(JWT、有効2時間) を使う
- CSRFトークンは JWTペイロードの `csrfToken` クレームから抽出する
- 状態変更系（POST/PUT/DELETE）には以下を必ず付与する:
  - `Cookie: TOKEN=<JWT>`
  - `X-CSRF-Token: <csrfToken>`
  - `Origin: https://cloudkey.internal`

接続:

- **必ずホスト名（cloudkey.internal）で接続する。** IP直叩き + Origin欠如の
  組み合わせでは DELETE が 403 Forbidden で拒否される。
- 私設CA証明書のため `validate_certs: false`（接続先はLAN内ホスト名固定）。

### 自動実行

```sh
# 開発（ansy）/ 本番（quory）共通
ansible-playbook -i inventories/homelab/hosts.yml playbooks/cloudkey_cert_deploy.yml
```

<!-- CCK-017 -->
Semaphore から実行する場合は quory の Task Template に登録し、月次スケジュールで
force再発行（毎回新指紋）する。閾値判定は行わず、毎回新規リーフを発行する。

## 6. 通知方針

<!-- CCK-016 -->
`roles/common_slack/tasks/notify.yml` を `include_tasks` で呼び出し、Slack で通知する
（best-effort。通知失敗で呼び出し元 play を止めない）。

| 状況 | チャンネル | status |
|---|---|---|
| 正常完了（デプロイ + 検証 OK） | `info` | ok |
| 失敗（発行/API/検証失敗、検証不一致を含む） | `alerts` | error |

role 全体を playbook の block / rescue / always で囲み、失敗時も Slack 通知後に
fail する。Semaphore / systemd 経路では unit の exit コードでも検知できる。

## 7. 制約・禁止事項

### authentication / private key

<!-- CCK-014 -->
CloudKey local administrator credentialはAnsible Vaultで管理する。leaf private keyは実行controllerのtemporary directoryとAPI bodyだけに存在させ、alwaysで削除しGitへ保存しない。secret、TOKEN、CSRF、authentication body / headerを扱うtaskはno_logとする。

<!-- CCK-020 -->
account名、credential保管path、Vault password fileの実値はPolicyへ記載せず、variable / Vault / Ansible configurationを正本とする。

<!-- CCK-015 -->
現行は既存local administrator accountを使用する。automation専用least-privilege accountへの分離はfuture scopeであり、現行要件として扱わない。

### unofficial API risk

<!-- CCK-018 -->
本仕組みは UniFi OS の**非公開API**（`/api/userCertificates`）を利用する。
公式にサポートされた証明書管理APIではないが、以下を合意のうえで採用する。

- UniFi OS のアップデートにより API の仕様変更・廃止が起こり得る。
- その場合、証明書更新は失敗するが、**UIログインや管理機能自体は失われない**
  （証明書が期限切れになりブラウザ警告が出るだけ）。
- 公式の証明書管理APIが提供される場合は、そちらへの移行を再検討する。
- 本仕組みの失敗は homelab の他サービス（cert_renew）に影響しない。

## 8. 変更履歴

| 版 | 日付 | 変更内容 |
|---|---|---|
| v1.0 | 2026-06-13 | 初版。CloudKeyを内蔵Let's Encrypt運用からHome-TLS-CA配下へ移行。UniFi OS 非公開API経由の証明書デプロイ方式を定義。 |
| v1.1 | 2026-07-25 | 標準8見出しへ再編し、規範の意味を変えず認証実値を正本参照へ置換 |
