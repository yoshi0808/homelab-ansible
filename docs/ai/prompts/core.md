# core.md

このファイルは、`homelab-ansible` リポジトリで AI に作業を依頼するときに毎回共有する共通前提である。

`core.md` は、環境情報・設計方針・禁止事項・AIレビュー運用・ファイル命名ルールをまとめた正本である。

Playbook / Role の要求仕様は、ユーザーと ChatGPT の会話で整理する。Codex には要求仕様の作成を任せず、主に git diff のレビューを依頼する。

---

## 1. リポジトリの目的

このリポジトリは、homelab 環境の Ansible Playbook / role / script を管理する。

主な目的は以下。

- Proxmox ノードの稼働確認
- Proxmox ノードのハードウェア確認
- Proxmox ノードのパッチ前確認
- Proxmox ノードのパッチ適用
- RADIUS / FreeRADIUS サーバー等の稼働確認
- RADIUS / FreeRADIUS サーバー等の再起動
- quory 上での本番 Ansible 実行
- 将来的な Semaphore UI による GUI 実行・自動実行

---

## 2. 主要ノードと役割

| ホスト名    | 種別       | 役割                                                         |
| ----------- | ---------- | ------------------------------------------------------------ |
| `ansy`      | VM         | Ansible 開発環境。VS Code / Claude Code / Codex を使い、実装・レビュー・commit / push を行う。 |
| `quory`     | 物理ノード | QDevice + 本番 Ansible 実行基盤。Git から確定済みソースを取得して実行する。 |
| `pve1`      | 物理ノード | Proxmox メインノード。通常稼働の中心。                       |
| `pve2`      | 物理ノード | Proxmox セカンダリノード。先行検証・縮退運用・フェイルオーバー先。 |
| `authy`     | VM         | RADIUS / FreeRADIUS サーバー。WPA3 Enterprise / EAP-TLS 認証基盤。 |
| `monnie`    | VM         | 監視基盤。Prometheus / Grafana / Loki を稼働させ、homelab の観測・可視化を担う。 |
| `sophos-fw` | VM         | Sophos Firewall。インターネット境界のファイアウォール。      |
| `cloudkey`  | 物理機器   | UniFi CloudKey。UniFi ネットワーク機器の管理コンソール。      |

基本方針は以下。

```text
ansy  = 開発・レビュー・commit/push
Git   = 正本管理
quory = 本番取得・Ansible実行
```

quory 上では、原則として直接コード編集しない。

---

## 3. 名前解決方針

本リポジトリはパブリック GitHub への公開を予定しているため、IP アドレスを
リポジトリ内に直接記載しない。これは inventory に限らず**全ファイル共通**の方針で、
playbook / role / vars / group_vars / host_vars はもちろん、`docs/` 配下の
ドキュメント（要求仕様・実装報告・ポリシー等）や `san_ip` も対象とする。

内部DNS名または `/etc/hosts` による名前解決を使う。

IP が必要な場合（証明書の SAN など）は、ファイルに値を埋め込まず、実行時に
`getent ahostsv4 <ホスト名>` 等で動的に解決して取得する。

| ホスト      | 推奨名               |
| ----------- | -------------------- |
| `pve1`      | `pve1.internal`      |
| `pve2`      | `pve2.internal`      |
| `quory`     | `quory.internal`     |
| `ansy`      | `ansy.internal`      |
| `authy`     | `authy.internal`     |
| `monnie`    | `monnie.internal`    |
| `sophos-fw` | `sophos-fw.internal` |
| `cloudkey`  | `cloudkey.internal`  |

inventory 例:

```yaml
all:
  children:
    proxmox:
      hosts:
        pve1:
          ansible_host: pve1.internal
        pve2:
          ansible_host: pve2.internal

    control_nodes:
      hosts:
        quory:
          ansible_host: quory.internal

    dev_nodes:
      hosts:
        ansy:
          ansible_host: ansy.internal

    radius_servers:
      hosts:
        authy:
          ansible_host: authy.internal

    monitoring_servers:
      hosts:
        monnie:
          ansible_host: monnie.internal

    local:
      hosts:
        localhost:
          ansible_connection: local
```

名前解決は DNS または quory / ansy の `/etc/hosts` で担保する。

---

## 4. 管理対象グループ

| グループ             | 対象           | 用途                                           |
| -------------------- | -------------- | ---------------------------------------------- |
| `proxmox`            | `pve1`, `pve2` | Proxmox VE ノード管理                          |
| `control_nodes`      | `quory`        | Ansible 実行基盤 / Semaphore UI / QDevice 管理 |
| `dev_nodes`          | `ansy`         | Ansible 開発環境管理                           |
| `radius_servers`     | `authy`        | FreeRADIUS / RADIUS サーバー管理               |
| `monitoring_servers` | `monnie`       | 監視基盤（Prometheus / Grafana / Loki）管理    |
| `sophos`             | `sophos-fw`    | Sophos Firewall 管理（SSD Trim 等）            |
| `cloudkey`           | `cloudkey`     | UniFi CloudKey 管理（証明書配信・バックアップ取得・NTP状態確認等） |
| `local`              | `localhost`    | ansy / quory 上でのローカル処理                |

`proxmox_healthcheck.yml` や `proxmox_hw_check.yml` は `proxmox` グループを対象にする。

`radius_healthcheck.yml` や `radius_patch.yml` は `radius_servers` グループを対象にする。

quory を対象にする playbook は、`quory_setup.yml` / `quory_update.yml` のような専用 playbook に限定する。

---

## 5. Ansible 管理ユーザーと SSH 鍵

Ansible 管理対象ホストには、Ansible 管理用ユーザー `ann` を作成する。

対象ホスト:

- `pve1`
- `pve2`
- `authy`
- 必要に応じて将来の管理対象ホスト

各対象ホストでは、`ann` の `authorized_keys` に ansy 側の公開鍵 `id_ann.pub` を登録する。

```text
/home/ann/.ssh/authorized_keys
```

`ann` は Ansible 実行時に `become` できるよう、NOPASSWD sudo を許可する。

```sudoers
ann ALL=(ALL) NOPASSWD: ALL
```

一方、Ansible 実行元である `ansy` では、通常 `yoshi` ユーザーで Ansible を実行する。  
そのため、秘密鍵 `id_ann` は ansy 上の `yoshi` のホームディレクトリに配置する。

```text
/home/yoshi/.ssh/id_ann
/home/yoshi/.ssh/id_ann.pub
```

Ansible inventory / group_vars では以下のように指定する。

```yaml
ansible_user: ann
ansible_ssh_private_key_file: ~/.ssh/id_ann
```

この `~/.ssh/id_ann` は、Ansible を実行しているローカルユーザー、通常は `yoshi`、のホームディレクトリを指す。  
接続先ホストの `/home/ann/.ssh/id_ann` を指すものではない。

`ansible_user: ann` は、接続先ホスト上のユーザー名である。  
ansy 側に `ann` ユーザーを作成する必要はない。

秘密鍵そのもの、秘密鍵の中身、パスフレーズ、認証情報はリポジトリに保存しない。

### ann を使わない例外ホスト

以下のホストは、ベンダー製アプライアンス等の事情により `ann` ユーザーを作成せず、
別の認証方式を使う。

| ホスト | 認証方式 | 備考 |
| --- | --- | --- |
| `sophos-fw` | `admin` ユーザー + RSA鍵（`id_rsa_sophos`） | 通常のシェルではなく Advanced Shell 経由でのみ操作する |
| `cloudkey` | `root` ユーザー + パスワード認証 | 認証情報は Ansible Vault（`inventories/vars/cloudkey.yml`）で管理する |

これらは例外であり、新規ホストを追加する場合は、まず `ann` + SSH鍵方式が使えないか
検討し、使えない場合のみ個別の認証方式を採用する。

AI への禁止事項:

```text
- 秘密鍵ファイルを生成しない
- 秘密鍵の中身を表示しない
- ~/.ssh/id_ann をリポジトリ内にコピーしない
- authorized_keys を勝手に上書きしない
- SSHポートやユーザーを推測して固定しない
- vault / secret / local などの秘密情報ファイルを平文で作成しない
```

---

## 6. Ansible role の基本方針

人間向けには以下のように理解する。

| 人間向けの理解 | 実ファイル                             | 役割                                                         |
| -------------- | -------------------------------------- | ------------------------------------------------------------ |
| playbook       | `playbooks/*.yml`                      | 人間が実行する入口。                                         |
| shell / script | `roles/*/files/*.sh`                   | 対象ホスト上で動く処理本体。check 系では収集と JSON 整形のみを行う。patch / reboot 系では限定的な変更操作を行う場合がある。 |
| Ansible 配管   | `roles/*/tasks/main.yml`               | shell の配置・実行・JSON 読み込み・保存・判定。              |
| 初期設定       | `roles/*/defaults/main.yml`            | role のデフォルト設定。                                      |
| ホスト別設定   | `inventories/homelab/host_vars/*.yml`  | ホスト固有の期待値や差分。                                   |
| グループ別設定 | `inventories/homelab/group_vars/*.yml` | グループ共通の接続情報・期待値・設定。                       |

`playbooks/` は実行入口、`roles/` は処理本体である。

`ping.yml` のように処理が非常に小さいものは、role を作らず playbook 単独でよい。

---

## 7. shell / script の責務

check 系 shell は、対象ホスト上でコマンドを実行し、結果を JSON に整形して標準出力へ返す。

check 系 shell は、原則として **収集と JSON 整形のみ**を行う。

shell が行わないこと:

```text
- 正常 / 異常の判定
- warning / critical の分類
- host_vars との期待値比較
- 実行継続 / 中止の判断
- 通知
- レポート保存
```

これらは Ansible tasks 側で行う。

責務分離は以下とする。

```text
Shell:
  収集とJSON整形のみ

Ansible:
  配置、実行、JSON読込、期待値比較、warning/critical分類、保存、fail制御
```

補足:

- shell が `port_1812_listen: true/false` のような観測値を返すことは許容する。
- shell が `status: critical` や `warnings: [...]` を生成することは許容しない。
- shell は health 判定の主体ではなく、対象ホスト上の情報収集センサーとして扱う。

---

## 8. files と templates の使い分け

check 系 shell は `roles/*/files/*.sh` に置く。

通常は Ansible が `copy` して `/usr/local/sbin/` に配置し、`command` で実行する。

一時実行だけでよい role では `ansible.builtin.script` の利用も許容する。

原則:

```text
roles/*/files/*.sh
  静的 shell。通常はこちらを使う。

roles/*/templates/*.j2
  Ansible変数をファイル内に埋め込む必要がある場合のみ使う。
```

check 系 shell は原則として `templates/*.sh.j2` には置かない。

---

## 9. 変更系 playbook / shell の扱い

`proxmox_patch` / `radius_patch` / 将来の `reboot` / `migrate` などでは、shell が更新・再起動などの変更操作を含む可能性がある。

ただし、変更系 shell は例外扱いとし、以下を守る。

```text
- 読み取り系 role と変更系 role を分ける
- playbook 名で変更系だと分かるようにする
- reboot / patch / migrate などは専用 playbook に分離する
- check 系 shell に変更操作を混ぜない
- 変更系 shell は Ansible tasks 側で明示的に実行条件を制御する
```

---

## 10. playbook 命名方針

playbook は 1 ファイルにまとめず、運用目的ごとに分ける。

### Proxmox 系

| Playbook                  | 目的                      | 変更有無 |
| -------------------------- | ------------------------ | -------- |
| `proxmox_hw_check.yml`    | ハードウェア棚卸し・確認   | 原則なし |
| `proxmox_healthcheck.yml` | 日常ヘルスチェック        | 原則なし |

パッチ適用関連（dry-run / 単一ノード適用 / 週次フル適用 等）は、安全度の判断が
複雑で専用ポリシーがあるため本表には含めない。`proxmox_patch_policy.md`
（下記「個別システムのポリシー文書」）の Playbook 一覧を参照する。

### Ubuntu（VM） 系

| Playbook                     | 目的                                  | 変更有無 |
| ---------------------------- | ------------------------------------- | -------- |
| `radius_healthcheck.yml`     | FreeRADIUS 稼働確認                    | 原則なし |
| `monitoring_healthcheck.yml` | Prometheus / Grafana / Loki 稼働確認   | 原則なし |

深夜 reboot を伴う `ubuntu_nightly.yml` は、`ubuntu_vm_patch_policy.md`
の Playbook 構成を参照する（理由は上記 Proxmox 系と同様）。

### 個別システムのポリシー文書

複数 playbook が連携する複雑なシステム、または変更系で安全度の判断が必要な
システムについては、上記の簡易な表ではなく `docs/ai/prompts/` 配下に専用の
`*_policy.md` を置き、そちらを正本とする。

| ポリシー文書                                  | 対象システム                                             |
| ---------------------------------------------- | -------------------------------------------------------- |
| `proxmox_patch_policy.md`                      | Proxmox ノード（pve1 / pve2）のパッチ適用                |
| `ubuntu_vm_patch_policy.md`                     | Ubuntu VM（authy / monnie 等）のパッチ適用・深夜 reboot   |
| `cert_renew_policy.md`                          | homelab 管理系 Web UI の TLS 証明書自動更新（ansy / pve1 / pve2 / monnie / quory） |
| `cert_renew_cloudkey_policy.md`                 | CloudKey の TLS 証明書自動更新                            |
| `proxmox_backup_restore_verify_policy.md`       | Proxmox バックアップの月次リストア検証                    |
| `unifi_backup_fetch_policy.md`                  | CloudKey の UniFi OS システムバックアップ取得             |

AI は該当システムを扱う際、本書（`core.md`）に加えて、対応する `*_policy.md`
を必ず参照する。

各ポリシー文書には「対応する Playbook」セクションがあり、そのシステムに属する
playbook の一覧と役割を示す。playbook の詳細（処理フロー・安全度分類等）は、
重複・矛盾を避けるため本書では繰り返さず、各ポリシー文書側に一本化する。

---

## 11. Git / quory 反映方針

Git を正本とする。

```text
ansy:
  開発、レビュー、commit、push

quory:
  pull、実行
```

quory 上では原則として commit しない。

quory は Git から pull して実行する。pull は `--ff-only` を使う。

pull 前に working tree が clean であることを確認する。

### Ansible playbook 内で git pull しない

Git pull を Ansible playbook 自身で行うことは避ける。

理由は、実行中の playbook が自分自身を更新する「自己更新問題」が起きるため。

```text
Git更新:
  quory上のAnsible外スクリプト、または将来のSemaphore UI Repository機能

Ansible playbook:
  対象ホストに対する処理だけ
```

---

## 12. 自動実行の考え方

Ansible 自体には「時間になったら自分で起動する」機能はない。Semaphore UIがその処理を担う。

quory 上で リブート動作や、モジュール更新が発生するplaybookについては、`systemd timer` が `ansible-playbook` を起動する。

---

## 13. .gitignore 方針

このリポジトリはpublic GitHub で管理するため、秘密情報をリポジトリに含めない。

通常の inventory / group_vars / host_vars は Git 管理する。  
ただし、実行時生成物、ローカル専用設定、秘密情報を含むファイルは Git 管理しない。

Ansible 接続設定では、秘密鍵そのものではなく、秘密鍵へのパス参照のみを記載する。

例:

```yaml
ansible_user: ann
ansible_ssh_private_key_file: ~/.ssh/id_ann
```

これは秘密鍵本体ではないため Git 管理してよい。

`.gitignore` では主に以下を除外する。

```gitignore
# Runtime reports
reports/**/*.json
reports/**/*.log

# Ansible retry files
*.retry

# Local-only overrides / secrets
*.local.yml
*.secret.yml
*vault*.yml

# Python / tooling
__pycache__/
*.pyc

# Editor / OS
.vscode/
.DS_Store

# Temporary files
*.tmp
```

秘密情報を将来追加する場合は、`vault` / `secret` / `local` を含むファイル名にし、Git 管理対象にしない。

`all.yml.example` は、実際に `all.yml` をローカル専用設定として使う運用になった場合のみ作成する。使わない場合は置かない。

---

## 14. AI を使った構築・レビュー運用

### AI 運用方針

このリポジトリでは、AI を「自動決定主体」ではなく、実装・レビュー・論点整理支援として利用する。

これは AI による完全自動運用ではなく、AI-assisted operations である。

最終的な運用判断、本番実行判断、commit 判断は必ず Yoshinobu が行う。

AI が patch / reboot / migration / inventory 変更などの危険操作を、自律的に本番実行する構成は採用しない。

本番反映、危険操作の実行、運用上の採否判断は Yoshinobu の明示判断を必要とする。

AI の役割分担は以下とする。

```text
要求仕様整理: ChatGPT/Claude
実装: Claude Code
レビュー: Codex
追加実装: Claude Code
再レビュー: Codex
テスト: Codex（tester ロール。dry-run / semi-safe を自律実行。本番適用はしない）
運用判断: Yoshinobu
本番実行判断: Yoshinobu
確定判断: Yoshinobu
コミット: Yoshinobu
```

### prompts/ の考え方

`docs/ai/prompts/` は、AI に毎回渡す共通前提を置く場所である。

設計用テンプレート、Claude Code 実装テンプレート、Codex レビューテンプレートは、原則として置かない。

要求仕様は、ユーザーと ChatGPT の会話で整理する。

Codex レビューの観点も `core.md` にまとめる。レビューで不足が出た場合は、別テンプレートを増やすのではなく、まず `core.md` を改善する。

推奨構成:

```text
docs/ai/prompts/
└── core.md
```

| ファイル  | 役割                                                         |
| --------- | ------------------------------------------------------------ |
| `core.md` | AIに毎回渡す共通前提。環境・運用ルール・禁止事項・要求仕様化の方針・レビュー観点など。 |

---

## 15. Playbook 作成依頼から確定までの運用フロー

Playbook / Role を作成する場合、まずユーザーが ChatGPT と会話しながら、作りたい内容を整理する。

ChatGPT は、ユーザーとの会話を通じて、目的・対象・確認項目・制約・初回除外範囲を整理し、Claude Code に渡せる要求仕様としてまとめる。

要求仕様は、詳細な実装方法ではなく、以下を中心にまとめる。

- 目的
- 対象ホスト / 対象グループ
- 作成・更新対象ファイル
- 確認項目または実施項目
- 制約
- 初回実装で含める範囲
- 初回実装では除外する範囲
- shell と Ansible tasks の責務分離
- 秘密情報を扱わないこと
- read-only / 変更系の区別

要求仕様には、原則として具体的な実装方法論を書きすぎない。

避けるもの:

- awk / sed / grep の詳細
- JSON 生成ロジックの細部
- Ansible task の詳細実装例
- コマンドの細かい組み立て
- 不要に細かい閾値

### ファイル命名ルール

`docs/ai/reviews/<target>/` 配下には、工程ごとに以下のようなファイルを保存する。

```text
YYYY-MM-DD_001_requirement.md
YYYY-MM-DD_002_implement.md
YYYY-MM-DD_003_review.md
YYYY-MM-DD_004_implement.md
YYYY-MM-DD_005_review.md
YYYY-MM-DD_006_test_plan.md
YYYY-MM-DD_007_test_result.md
YYYY-MM-DD_008_final.md
```

ファイル名には、原則として `codex` や `claude` などの AI 名を入れない。

重要なのは、誰が作成したかではなく、そのファイルの役割である。

- `requirement`: 要求仕様
- `implement`: 実装内容、またはレビュー後の追加実装内容
- `review`: レビュー結果
- `test_plan`: テスト計画（Claude Code が起案し、Yoshinobu が承認）
- `test_result`: テスト実行結果（tester が保存）
- `final`: 最終確認

レビュー・実装・final 用の空ファイルは事前に作らない。  
必要になった工程のファイルだけ、その時点で作成する。

### 基本フロー

```text
1. ユーザーが作りたい Playbook / Role を ChatGPT に相談する

2. ChatGPT が会話を通じて要求仕様を整理する

3. ユーザーが要求仕様を確認する

4. ユーザーが Claude Code に要求仕様を渡す

5. Claude Code は、ユーザーから受け取った要求仕様を以下に保存する

   docs/ai/reviews/<target>/YYYY-MM-DD_001_requirement.md

6. Claude Code が playbook / role / shell を実装する

7. Claude Code は、実装完了後に作成・更新した内容を以下に保存する

   docs/ai/reviews/<target>/YYYY-MM-DD_002_implement.md

   implement には以下を含める。

   - 実装概要
   - 作成・更新したファイル一覧
   - 変更内容の要約
   - 実行した確認コマンド
   - 実行結果
   - 未対応事項
   - 注意点

8. Codex が git diff、requirement、implement をもとにレビューする

   保存先例:

   docs/ai/reviews/<target>/YYYY-MM-DD_003_review.md

9. 修正が必要な場合、ユーザーが Claude Code に review ファイルを渡して追加実装を依頼する

10. Claude Code は、追加実装後の内容を次の implement として保存する

    保存先例:

    docs/ai/reviews/<target>/YYYY-MM-DD_004_implement.md

11. Codex が再レビューする

    保存先例:

    docs/ai/reviews/<target>/YYYY-MM-DD_005_review.md

12. ユーザーが最終判断する

13. 問題なければ commit する
```

### レビュー依頼時の注意

Codex にレビューを依頼する場合は、対象となる requirement / implement / review のファイル名を明示する。

例:

```text
以下を読んで、現在の git diff をレビューしてください。

- docs/ai/reviews/radius_healthcheck/2026-05-06_001_requirement.md
- docs/ai/reviews/radius_healthcheck/2026-05-06_002_implement.md

レビュー結果は以下に保存してください。

- docs/ai/reviews/radius_healthcheck/2026-05-06_003_review.md
```

再レビューの場合も同様に、直前の review と最新の implement を明示する。

例:

```text
以下を読んで、現在の git diff を再レビューしてください。

- docs/ai/reviews/radius_healthcheck/2026-05-06_001_requirement.md
- docs/ai/reviews/radius_healthcheck/2026-05-06_003_review.md
- docs/ai/reviews/radius_healthcheck/2026-05-06_004_implement.md

レビュー結果は以下に保存してください。

- docs/ai/reviews/radius_healthcheck/2026-05-06_005_review.md
```

### 次工程ファイルの明示

各工程が完了したら、その工程を担当した AI は、出力の最後に次工程で参照すべきファイル名を明記する。

誰が何を保存し、何を次に渡すかを明確にする。

| 工程             | 担当        | 保存するファイル                                             | 次に参照する主なファイル                                     |
| ---------------- | ----------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 要求仕様の整理   | ChatGPT     | 直接ファイル保存はしない。ユーザーに Claude Code へ渡す要求仕様を提示する。 | ChatGPT が提示した要求仕様本文                               |
| requirement 保存 | Claude Code | `YYYY-MM-DD_001_requirement.md`                              | `YYYY-MM-DD_001_requirement.md`                              |
| 初回実装         | Claude Code | `YYYY-MM-DD_002_implement.md`                                | `YYYY-MM-DD_001_requirement.md`, `YYYY-MM-DD_002_implement.md` |
| レビュー         | Codex       | `YYYY-MM-DD_003_review.md`                                   | `YYYY-MM-DD_001_requirement.md`, `YYYY-MM-DD_002_implement.md`, `YYYY-MM-DD_003_review.md` |
| 追加実装         | Claude Code | `YYYY-MM-DD_004_implement.md`                                | `YYYY-MM-DD_001_requirement.md`, `YYYY-MM-DD_003_review.md`, `YYYY-MM-DD_004_implement.md` |
| 再レビュー       | Codex       | `YYYY-MM-DD_005_review.md`                                   | `YYYY-MM-DD_001_requirement.md`, `YYYY-MM-DD_004_implement.md`, `YYYY-MM-DD_005_review.md` |

Claude Code は、ユーザーから受け取った要求仕様を `requirement` ファイルとして保存する。
ユーザーが手作業で requirement ファイルを作る運用ではない。

Claude Code は、実装完了後に実装内容・作成/更新ファイル・確認結果を `implement` ファイルとして保存する。
Codex は、レビュー完了後にレビュー内容を `review` ファイルとして保存する。

各工程の出力末尾には、次のように `Next step files` を明記する。

例:

```text
Next step files:
- docs/ai/reviews/radius_healthcheck/2026-05-06_001_requirement.md
- docs/ai/reviews/radius_healthcheck/2026-05-06_002_implement.md
```

ユーザーは、この一覧をそのまま次の Claude Code / Codex への依頼に含める。

agmsg を使う場合の受け渡しは、次の「エージェント間メッセージング（agmsg）」に従う。


### エージェント間メッセージング（agmsg）

工程間の受け渡しは、agmsg（team `homelab`）のメッセージで行ってよい。
これは従来の VS Code 拡張による手動コピペ運用の代替である。

| ロール     | エージェント | 種別                         |
| ---------- | ------------ | ---------------------------- |
| `claude`   | Claude Code  | 実装担当                     |
| `reviewer` | Codex        | レビュー担当                 |
| `tester`   | Codex        | テスト担当（on-demand 起動） |

受け渡しの原則:

- メッセージ本文には、実装内容・レビュー内容そのものを書かない。
  対象となる requirement / implement / review の**ファイルパス**を載せる。
- 実装内容・レビュー内容の本文は、これまで通り `docs/ai/reviews/<target>/`
  配下のファイルに書く。ファイルが正本であり、git にコミットされる監査証跡である。
- 両エージェントは同じ作業ディレクトリ（`ansy` 上のリポジトリ）を共有するため、
  受け取った側は、メッセージのパスから実体ファイルを読む。

流れ:

```text
1. Claude Code が実装し、implement ファイルを書く
2. Claude Code が reviewer に agmsg で
   requirement / implement のパスと、review の保存先パスを送る
3. Codex がファイルを読み、レビューして review ファイルを書く
4. Codex が claude に agmsg で、結果サマリと review ファイルのパスを返す
5. 必要なら 2〜4 を繰り返す
6. Yoshinobu が判断し、commit する
```

注意:

- Codex（`reviewer`）は Monitor を持たず、agmsg を自動受信しない。
  Claude Code 側から agmsg をキックして、受信・処理させる。
  Claude Code（`claude`）は monitor モードで自動受信する。
- agmsg はあくまで受け渡し手段であり、運用判断・本番実行判断・commit 判断は
  §14 の通り Yoshinobu が行う。agmsg ループは Yoshinobu の判断待ちで止まる。
  AI が agmsg 経由で自律的に commit や危険操作を行う構成は採用しない。


### Codex レビュー観点

Codex にレビューを依頼する場合は、主に以下を確認する。

- `core.md` の方針に反していないか
- shell / script が収集と JSON 整形に留まっているか
- warning / critical / fail 制御が Ansible tasks 側にあるか
- read-only playbook に変更操作が混入していないか
- patch / reboot / restart / reload などの変更系処理が専用 playbook に分離されているか
- 秘密鍵、認証情報、証明書秘密鍵などを読んでいないか
- inventory / group_vars / host_vars が名前ベース方針に沿っているか
- 生成物や runtime report を commit 対象に混ぜていないか
- 要求仕様に対して実装が過不足ないか
- 変更内容をこのまま commit してよいか

レビュー時は、本質（バグ・安全性・`core.md` 違反・要求仕様との過不足）を優先する。
軽微なスタイルや好みの問題は、任意（optional）の指摘として扱う。

各指摘には、原則として重大度ラベルを付ける。

- `must-fix`: バグ / 安全性 / `core.md` 違反 / 要求仕様の欠落。直さないと commit 不可。
- `suggestion`: 妥当な改善。採否は判断対象。
- `nit`: 軽微・主観的。任意。

### レビュー指摘のトリアージと仲裁

Claude Code は、Codex のレビュー結果を鵜呑みにして全指摘を機械的に反映しない。
各指摘を自分で評価し、分類したうえで Yoshinobu に提示し、採否の判断を仰ぐ。

| 分類                                                        | Claude Code の対応                                           |
| ----------------------------------------------------------- | ------------------------------------------------------------ |
| must-fix（バグ / 安全性 / `core.md` 違反 / 要求仕様の欠落） | 「要修正」と明示して提示する。原則、反映する前提で確認する。 |
| 妥当な改善（suggestion）                                    | 価値を説明して提示し、採否の判断を仰ぐ。                     |
| 些末（nit）                                                 | 「些末。許容を推奨」と意見を添えて提示する。                 |
| 的外れ / 誤り                                               | どこを誤解しているか根拠を示し、「反論して棄却を推奨」と提示する。 |
| スコープ外                                                  | 「妥当だが今回の範囲外。次イテレーション送りを推奨」と提示する。 |

採否の最終判断は Yoshinobu が行う（§14）。Claude Code は自分の実装を盲目的に庇わず、
Codex を盲目的に追従もしない。「Codex が正しい（見落とし）」「Codex が誤り（根拠あり）」の
いずれも正直に報告する。

指摘を棄却する場合は、棄却理由を監査証跡（次の implement、または final）に記録する。
黙って握りつぶさない。必要に応じて、Codex に agmsg で根拠を返し、再レビューで合意させる。

このトリアージ層により、軽微指摘の往復（nit ping-pong）や半自動ループの暴走を防ぎ、
人間ゲート（§14）を保ったまま実装・レビューを回す。

---

## 16. 実装後のレビュー・確定フロー

実装後は以下の流れで進める。

```text
1. Claude Code が実装する
2. Claude Code が implement ファイルに実装内容を記録する
3. Codex（reviewer）が git diff / requirement / implement を確認する
4. Codex（reviewer）が review ファイルにレビューを書く
5. Claude Code がレビュー指摘をトリアージし（§15 参照）、採否を Yoshinobu に提示する
6. 修正する指摘について、Claude Code が追加実装する
7. Claude Code が次の implement ファイルに追加実装内容を記録する（棄却した指摘は理由も記録する）
8. Codex（reviewer）が再レビューする
9. 必要に応じて 3〜8 を繰り返す
10. Claude Code がテスト計画（test_plan）を起案し、Yoshinobu が承認する
11. Codex（tester）が dry-run / semi-safe テストを実行し、test_result に保存する
12. Claude Code がテスト結果を意図（requirement の確認項目 / host_vars 期待値）と突合し、違和感や本番適用の要否を Yoshinobu に提示する
13. Yoshinobu が「これで確定」と判断する
14. 必要に応じて final ファイルを作る
15. Yoshinobu が commit する
```

工程間（2→3、4→5 など）の受け渡しに agmsg を使う場合は、
§15「エージェント間メッセージング（agmsg）」に従う。
implement / review の本文はファイルに書き、agmsg にはパスを載せる。

### テスト工程（tester）

レビューがおおむね収束したら、実装をテストする。テストは reviewer とは別の Codex
エージェント `tester` が担当する。役割を物理的に分けることで、Codex の作業が
レビューとテストの間で混線するのを防ぐ。`tester` は on-demand で起動し、専用の
作業ウィンドウで実行する。

受け渡しと判定:

- Claude Code が、requirement の確認項目とレビュー指摘から **test_plan** を起案する。
- Yoshinobu が test_plan を承認する（テスト方針の判断は人間に残す）。
- `tester` が test_plan に沿ってテストを実行し、結果を **test_result** に保存する。
- Claude Code がテスト結果を requirement の確認項目 / host_vars 期待値と突合し、
  「意図通り / 違和感」を判定する。違和感、または本番適用の要否は Yoshinobu に提示する。

`tester` の自律境界:

| 種別                                                         | tester の扱い                                                |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| SAFE:read-only（healthcheck / precheck / ping / `--syntax-check` / `ansible-lint`） | 自律実行してよい                                             |
| SEMI-SAFE:（冪等で、何度実行しても安全な更新系）             | 自律実行してよい                                             |
| UN-SAFE:変更系（patch / reboot / migrate など）              | `--check --diff` の dry-run のみ。複数ノードがあれば各ノード分のバリエーションを回し、差分を提示する |
| 本番適用（実際の変更反映）                                   | `tester` は行わない。Claude Code が Yoshinobu と相談して決める |

補足:

- **semi-safe** とは、更新系であっても冪等で、何度実行しても結果が壊れない操作を指す。
- 本番適用を `tester` に行わせないのは、§14 の人間ゲートを保ち、かつ失敗時に Claude Code が
  状況をスムーズに把握できるようにするため。
- テスト対象は pve2 を先行する（§2: pve2 は先行検証・縮退運用）。pve1 / 本番は dry-run → 人間判断。
- 初期運用（v1）では高度なことは求めず、まず dry-run のバリエーションテストを中心に回す。

### final ファイル

確定時には、必要に応じて `final` ファイルを作る。

例:

```text
docs/ai/reviews/proxmox_healthcheck/2026-05-06_006_final.md
```

中身は簡潔でよい。

```md
# Final

この内容で確定。

確認者: Yoshinobu
日付: 2026-05-06

## 対象

- proxmox_healthcheck role
- playbooks/proxmox_healthcheck.yml

## コメント

レビュー指摘を反映済み。
初期運用版として採用する。
```

### playbook先頭への最終仕様コメント

実装が確定したら（最終判断後）、playbook先頭のコメントに「現在の最終仕様」を
要約して記載する。docs/ai/reviews/<target>/ 配下の各ファイルは工程ごとの履歴であり、
設計判断が途中で転換することもある。「今のコードが何をしているか」を読み取るために
履歴を毎回遡る運用は非効率なため、playbook自体に最終形のサマリを残す。

記載するタイミング:

- 初回実装確定時
- 設計の転換を伴う大きな追加実装が確定した時

含める内容（書きすぎない。地図程度に留める）:

- 目的（1-2行）
- 対象ホスト・実行元
- 主要な処理フロー（Phase構成等）
- 重要な前提・制約（認証方式、設計上のキー判断の理由）
- 詳細経緯を追う場合の参照先（docs/ai/reviews/<target>/の最新implement）

Claude Codeは、実装完了の最後のステップとしてこのコメントを書く。

---

## 17. 禁止事項

### check 系 shell

```text
- 変更操作を入れない
- 正常/異常判定をしない
- warning/criticalを作らない
- host_varsの期待値を持たせない
- 通知しない
- レポート保存しない
```

### Ansible playbook

```text
- Git pull を playbook 内で行わない
- check / patch / reboot を同じ入口に混ぜない
- 危険操作を確認なしで実行しない
```

### quory

```text
- 原則として直接コード編集しない
- 原則として commit しない
- 未確認コードを日次 timer で自動実行しない
```

### IP アドレス（リポジトリ全体）

```text
- IP リテラルをファイルに直接書かない（§3 参照。docs/ も san_ip も対象）
- IP が必要な場合は実行時に getent 等で動的解決する
- ホストはDNS名 / /etc/hosts で名前解決する
```

