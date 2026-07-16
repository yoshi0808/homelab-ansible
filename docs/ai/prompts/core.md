# core.md

このファイルは、`homelab-ansible` リポジトリで AI に作業を依頼するときに毎回共有する共通前提である。

`core.md` は、環境情報・設計方針・禁止事項・AIレビュー運用・ファイル命名ルールをまとめた正本である。

Playbook / Role の要求仕様は、ユーザーと ChatGPT及びCLAUDEとの会話で整理する。Codexは要求仕様に対する実装レビュー、テスト実行を依頼する。

---

## 1. リポジトリの目的

このリポジトリは、homelab 環境の Ansible Playbook / role / script を管理する。

主な目的は以下。

- Proxmox ノードの稼働確認
- Proxmox ノードのハードウェア確認
- Proxmox ノードのパッチ前確認
- Proxmox ノードのパッチ適用
- vmの稼働確認
- vmの再起動
- quory 上での本番 Ansible 実行
- Semaphore UI による GUI 実行・自動実行

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

本リポジトリはパブリック GitHub への公開をしているため、IP アドレスを
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
| `cloudkey_devices`   | `cloudkey`     | UniFi CloudKey 管理（証明書配信・バックアップ取得・NTP状態確認等） |
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
| `time_sync_check_policy.md`                     | quory 基準の NTP 同期状態チェック・quory 参照追加準備     |
| `autonomous_recovery_policy.md`                 | Sophos / authy / monnie の自律復旧ラダー（検知→restart→reboot→HA failover） |
| `log_observability_policy.md`                   | monnie 中心のログ収集基盤（UniFi/機器 syslog → rsyslog → Alloy → Loki → Grafana、将来 pve/Sophos 拡張・エラーフック） |

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

quory 上で SemaphoreUI 自体を再起動・停止させる（例: `cert_renew_quory.yml` の
semaphore 再起動）、またはホストの再起動を伴いジョブ実行そのものが中断してしまう
（例: `proxmox_patch_apply_node.yml`、`ubuntu_nightly.yml`）playbook については、
SemaphoreUI が自身の処理を道連れに中断してしまうため `systemd timer` が
`ansible-playbook` を起動する。

単にモジュール／パッケージを更新するだけで、SemaphoreUI プロセス自体やジョブ実行
環境そのものには影響しない playbook（例: `codex_update_check.yml`）は、上記に該当
しないため SemaphoreUI のスケジュール機能で問題ない（2026-07-10、モジュール更新を
一律 systemd timer 対象としていたのを訂正）。

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
要求仕様整理: ChatGPT / Claude Code（要件定義・ハブ役）
実装: Claude Code（implementer ロール）
レビュー: Codex（reviewer ロール）
追加実装: Claude Code（implementer ロール）
再レビュー: Codex（reviewer ロール）
テスト: Codex（tester ロール。安全な検証方法を選択し、品質を保証する QA 担当。本番適用はしない）
運用判断: Yoshinobu
本番実行判断: Yoshinobu
確定判断: Yoshinobu
コミット: Yoshinobu
```

Claude Code は agmsg 上で2ロールに分かれる（詳細は §15）。

- 要件定義・ハブ役（agmsg 名 `claude`）: ユーザーとの対話、requirement 整理・保存、
  implementer / reviewer / tester との受け渡し仲介、レビュー指摘のトリアージ、
  test_plan 起案、テスト結果と requirement の突合。
- 実装担当（agmsg 名 `implementer`）: `claude` から受け取った requirement /
  review をもとに実装し、implement ファイルを保存する。reviewer / tester とは
  直接やり取りせず、常に `claude` 経由で受け渡しする。

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

Playbook / Role を作成する場合、まずユーザーが Claude/ChatGPT と会話しながら、作りたい内容を整理する。

AIは、ユーザーとの会話を通じて、目的・対象・確認項目・制約・初回除外範囲を整理し、Claude Code に渡せる要求仕様としてまとめる。

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
- `test_plan`: テスト計画（`claude`(要件定義・ハブ役)が起案し、Yoshinobu が承認）
- `test_result`: テスト実行結果（tester が保存）
- `final`: 最終確認

レビュー・実装・final 用の空ファイルは事前に作らない。  
必要になった工程のファイルだけ、その時点で作成する。

### 基本フロー

```text
1. ユーザーが作りたい Playbook / Role を ChatGPT、または要件定義・ハブ役の
   Claude Code（agmsg 名 `claude`）に相談する

2. ChatGPT / `claude` が会話を通じて要求仕様を整理する

3. ユーザーが要求仕様を確認する

4. `claude` は、ユーザーから受け取った要求仕様を以下に保存する

   docs/ai/reviews/<target>/YYYY-MM-DD_001_requirement.md

5. `claude` が `implementer` に requirement のパスと implement の保存先パスを
   agmsg で送る（§「エージェント間メッセージング（agmsg）」）

6. `implementer` が playbook / role / shell を実装する

7. `implementer` は、実装完了後に作成・更新した内容を以下に保存する

   docs/ai/reviews/<target>/YYYY-MM-DD_002_implement.md

   implement には以下を含める。

   - 実装概要
   - 作成・更新したファイル一覧
   - 変更内容の要約
   - 実行した確認コマンド
   - 実行結果
   - 未対応事項
   - 注意点

   `implementer` は保存後、implement ファイルのパスを `claude` に agmsg で返す。

8. `claude` が reviewer に requirement / implement のパスと review の保存先を送る

9. Codex（`reviewer`）が git diff、requirement、implement をもとにレビューし、
   以下に保存する

   docs/ai/reviews/<target>/YYYY-MM-DD_003_review.md

10. `reviewer` が review ファイルのパスを `claude` に返す。`claude` は指摘を
    トリアージし（後述）、修正要否をユーザーに提示する

11. 修正が必要な場合、`claude` が `implementer` に review ファイルのパスを渡して
    追加実装を依頼する

12. `implementer` は、追加実装後の内容を次の implement として保存し、
    `claude` に返す

    保存先例:

    docs/ai/reviews/<target>/YYYY-MM-DD_004_implement.md

13. `claude` が reviewer に再レビューを依頼する

    保存先例:

    docs/ai/reviews/<target>/YYYY-MM-DD_005_review.md

14. ユーザーが最終判断する

15. 問題なければ Yoshinobu が commit する
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

| 工程             | 担当                          | 保存するファイル                                             | 次に参照する主なファイル                                     |
| ---------------- | ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 要求仕様の整理   | ChatGPT / `claude`（ハブ）    | ChatGPT の場合は直接ファイル保存はせず要求仕様本文を提示する。`claude` の場合は次行の requirement 保存まで行う。 | ChatGPT が提示した要求仕様本文、または requirement ファイル  |
| requirement 保存 | `claude`（ハブ）              | `YYYY-MM-DD_001_requirement.md`                              | `YYYY-MM-DD_001_requirement.md`                              |
| 初回実装         | `implementer`                 | `YYYY-MM-DD_002_implement.md`                                | `YYYY-MM-DD_001_requirement.md`, `YYYY-MM-DD_002_implement.md` |
| レビュー         | Codex（`reviewer`）           | `YYYY-MM-DD_003_review.md`                                   | `YYYY-MM-DD_001_requirement.md`, `YYYY-MM-DD_002_implement.md`, `YYYY-MM-DD_003_review.md` |
| 追加実装         | `implementer`                 | `YYYY-MM-DD_004_implement.md`                                | `YYYY-MM-DD_001_requirement.md`, `YYYY-MM-DD_003_review.md`, `YYYY-MM-DD_004_implement.md` |
| 再レビュー       | Codex（`reviewer`）           | `YYYY-MM-DD_005_review.md`                                   | `YYYY-MM-DD_001_requirement.md`, `YYYY-MM-DD_004_implement.md`, `YYYY-MM-DD_005_review.md` |

`claude`（要件定義・ハブ役）は、ユーザーから受け取った要求仕様を `requirement` ファイルとして保存する。
ユーザーが手作業で requirement ファイルを作る運用ではない。

`implementer` は、実装完了後に実装内容・作成/更新ファイル・確認結果を `implement` ファイルとして保存する。
Codex（`reviewer`）は、レビュー完了後にレビュー内容を `review` ファイルとして保存する。

各工程の出力末尾には、次のように `Next step files` を明記する。

例:

```text
Next step files:
- docs/ai/reviews/radius_healthcheck/2026-05-06_001_requirement.md
- docs/ai/reviews/radius_healthcheck/2026-05-06_002_implement.md
```

ユーザーは、この一覧をそのまま次の `claude` / `implementer` / Codex への依頼に含める。

agmsg を使う場合の受け渡しは、次の「エージェント間メッセージング（agmsg）」に従う。


### エージェント間メッセージング（agmsg）

工程間の受け渡しは、agmsg（team `homelab`）のメッセージで行ってよい。
これは従来の VS Code 拡張による手動コピペ運用の代替である。

| ロール        | エージェント | 種別                                                         |
| ------------- | ------------ | ------------------------------------------------------------ |
| `claude`      | Claude Code  | 要件定義・ハブ担当（ユーザー対話、requirement 作成、implementer/reviewer/tester との受け渡し仲介、トリアージ、test_plan 起案、結果突合） |
| `implementer` | Claude Code  | 実装担当（`claude` から requirement / review を受け取り実装、implement ファイル作成） |
| `reviewer`    | Codex        | レビュー担当                                                 |
| `tester`      | Codex        | テスト担当（on-demand 起動）                                 |

受け渡しの原則:

- メッセージ本文には、実装内容・レビュー内容そのものを書かない。
  対象となる requirement / implement / review の**ファイルパス**を載せる。
- 実装内容・レビュー内容の本文は、これまで通り `docs/ai/reviews/<target>/`
  配下のファイルに書く。ファイルが正本であり、git にコミットされる監査証跡である。
- 全エージェントは同じ作業ディレクトリ（`ansy` 上のリポジトリ）を共有するため、
  受け取った側は、メッセージのパスから実体ファイルを読む。
- `implementer` は `reviewer` / `tester` と直接やり取りしない。受け渡しは常に
  `claude` を経由する（`claude` がハブ）。

流れ:

```text
1. claude が requirement を書き、implementer に
   requirement / implement 保存先のパスを送る
2. implementer が実装し、implement ファイルを書いて claude に返す
3. claude が reviewer に agmsg で
   requirement / implement のパスと、review の保存先パスを送る
4. Codex（reviewer）がファイルを読み、レビューして review ファイルを書く
5. reviewer が claude に agmsg で、結果サマリと review ファイルのパスを返す
6. claude が指摘をトリアージし、修正が必要なら review のパスを添えて
   implementer に追加実装を依頼する
7. 必要なら 2〜6 を繰り返す
8. Yoshinobu が判断し、commit する
```

注意:

- Codex（`reviewer` / `tester`）は Monitor を持たず、agmsg を自動受信しない。
  Claude Code 側から agmsg をキックして、受信・処理させる。
  Claude Code（`claude` / `implementer`）はどちらも monitor モードで自動受信する。
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

要件定義・ハブ役の `claude` は、Codex のレビュー結果を鵜呑みにして全指摘を機械的に
implementer へ流さない。各指摘を自分で評価し、分類したうえで Yoshinobu に提示し、
採否の判断を仰ぐ。

| 分類                                                        | `claude` の対応                                               |
| ----------------------------------------------------------- | ------------------------------------------------------------ |
| must-fix（バグ / 安全性 / `core.md` 違反 / 要求仕様の欠落） | 「要修正」と明示して提示する。原則、反映する前提で確認する。 |
| 妥当な改善（suggestion）                                    | 価値を説明して提示し、採否の判断を仰ぐ。                     |
| 些末（nit）                                                 | 「些末。許容を推奨」と意見を添えて提示する。                 |
| 的外れ / 誤り                                               | どこを誤解しているか根拠を示し、「反論して棄却を推奨」と提示する。 |
| スコープ外                                                  | 「妥当だが今回の範囲外。次イテレーション送りを推奨」と提示する。 |

採否の最終判断は Yoshinobu が行う（§14）。反映が決まった指摘は、review ファイルの
パスを添えて `claude` から `implementer` に追加実装を依頼する。`claude` は
implementer の実装を盲目的に庇わず、Codex を盲目的に追従もしない。
「Codex が正しい（見落とし）」「Codex が誤り（根拠あり）」のいずれも正直に報告する。

指摘を棄却する場合は、棄却理由を監査証跡（次の implement、または final）に記録する。
黙って握りつぶさない。必要に応じて、Codex に agmsg で根拠を返し、再レビューで合意させる。

このトリアージ層により、軽微指摘の往復（nit ping-pong）や半自動ループの暴走を防ぎ、
人間ゲート（§14）を保ったまま実装・レビューを回す。

---

## 16. 実装後のレビュー・確定フロー

実装後は以下の流れで進める。

```text
1. implementer が実装する
2. implementer が implement ファイルに実装内容を記録し、claude に返す
3. claude が reviewer に requirement / implement を渡す
4. Codex（reviewer）が git diff / requirement / implement を確認する
5. Codex（reviewer）が review ファイルにレビューを書き、claude に返す
6. claude がレビュー指摘をトリアージし（§15 参照）、採否を Yoshinobu に提示する
7. 修正する指摘について、claude が review のパスを添えて implementer に追加実装を依頼する
8. implementer が次の implement ファイルに追加実装内容を記録する（棄却した指摘は理由も記録する）
9. claude が reviewer に再レビューを依頼する
10. 必要に応じて 3〜9 を繰り返す
11. claude がテスト計画（test_plan）を起案し、Yoshinobu が承認する
12. Codex（tester）が安全な検証方法を選択してテストを実行し、test_result に保存する
13. claude がテスト結果を意図（requirement の確認項目 / host_vars 期待値）と突合し、違和感や本番適用の要否を Yoshinobu に提示する
14. Yoshinobu が「これで確定」と判断する
15. 必要に応じて final ファイルを作る
16. Yoshinobu が commit する
```

工程間（2→3、4→5 など）の受け渡しに agmsg を使う場合は、
§15「エージェント間メッセージング（agmsg）」に従う。
implement / review の本文はファイルに書き、agmsg にはパスを載せる。

### テスト工程（tester）

レビューがおおむね収束したら、実装をテストする。テストは reviewer とは別の Codex
エージェント `tester` が担当する。`tester` は単なる Ansible 実行担当ではなく、
実装内容の検証、安全な実行方法の選択、検証結果の品質保証を担う QA 担当である。
役割を物理的に分けることで、Codex の作業がレビューとテストの間で混線するのを防ぐ。
`tester` は on-demand で起動し、専用の作業ウィンドウで実行する。

受け渡しと判定:

- `claude`(要件定義・ハブ役)が、requirement の確認項目とレビュー指摘から **test_plan** を起案する。
- Yoshinobu が test_plan を承認する（テスト方針の判断は人間に残す）。
- `tester` が test_plan に沿って安全な検証方法を選択し、結果を **test_result** に保存する。
- `claude` がテスト結果を requirement の確認項目 / host_vars 期待値と突合し、
  「意図通り / 違和感」を判定する。違和感、または本番適用の要否は Yoshinobu に提示する。
- `implementer` はテスト工程には関与しない。test_result を踏まえた追加実装が必要な場合、
  `claude` が指示を添えて依頼する。

`tester` の責務:

- 実装内容が requirement / implement / review の意図を満たしているか検証する。
- 実行方法の安全性を判断し、必要に応じてより安全な検証方法へ置き換える。
- `claude` が提示したコマンドをそのまま実行しない。対象 playbook / role / task の性質を確認し、安全な実行方法を選ぶ。
- playbook を実行する前に、必ずヘッダの `# tester-gate: <種別>` マーカー（§18）を確認し、
  種別に応じた実行方法を選ぶ（`tester_mode` は廃止。判断は marker 一本）。
- Codex が `--check` 付き playbook を実行する場合は、原則として
  `scripts/safe-ansible-check.sh` を使う（§18.6）。`--check` なしの
  `ansible-playbook` は人間確認の対象であり、tester は APPLY として扱う。
- 検証結果、実行したコマンド、置き換えた理由、未検証事項を test_result に記録する。

`tester` の自律境界:

| 種別 | 判断基準 | tester の扱い |
| --- | --- | --- |
| SAFE | ヘッダが `safe-readonly` / `role-guarded`。healthcheck / precheck / stat など対象状態を読むだけ、または副作用が Slack 通知のみ。リスク受容が発生しない、文字通り安全 | 自律実行してよい（`--check` は不要） |
| SEMI-SAFE（risk-accepted） | ヘッダが `risk-accepted`。実変更を伴うが本番影響ゼロ/軽微・復旧容易と人間が判断済み。`--check` の有無で挙動は変わらない（常に本実行） | 自律実行してよい（そのまま通常実行する） |
| UN-SAFE（--check実行） | ヘッダが `check-mode-native` / `dry-run-aware`。`--check` を付けた場合のみ安全（破壊的操作がゲートされる、またはネイティブ dry-run 引数に差し替わる）。素の実行（次行の APPLY）は本番変更を起こすため、本質的には UN-SAFE な playbook | 自律実行してよい。**ただし必ず `--check` を付ける**（`--check --diff` を重ねてもよい） |
| UN-SAFE（APPLY） | `check-mode-native` / `dry-run-aware` の playbook を **`--check` なしで**実行し、実際に破壊的操作（patch / reboot / restart / migration / firewall変更 / VM操作等）を行わせること | `tester` は実施しない。Yoshinobu の本番適用判断が必要 |

Semaphore UI 登録・運用判断用のリスク分類:

| 種別 | 意味 | Semaphore UI 登録時の扱い |
| --- | --- | --- |
| SAFE | read-only 確認、healthcheck、status、stat、gather、precheck など。実行しても対象状態を変更しない | 自動実行に載せてよい |
| SEMI-SAFE | 変更を伴うが、冪等で、何度実行しても状態を壊しにくい構成管理・検証実行。例: `risk-accepted` playbook の通常実行、`check-mode-native` / `dry-run-aware` playbook の `--check` 実行 | 自動実行可否を用途ごとに判断する。初回は手動確認を推奨 |
| UN-SAFE | `check-mode-native` / `dry-run-aware` playbook を `--check` なしで実行する場合など、停止・切断・本番影響を起こし得る操作 | 人間の明示判断が必要。自動実行に載せる場合は個別ポリシーと停止条件を必ず確認する |

この `SAFE / SEMI-SAFE / UN-SAFE` は、Yoshinobu が Semaphore UI に task を登録する際に
リスクを認識するための運用分類であり、tester の自律境界表と同じ3語を使うが指す粒度が異なる
（Semaphore 表は playbook 自体の危険度、tester 表は「今からの1回の実行」の安全性）。
tester の `SAFE / SEMI-SAFE（risk-accepted）/ UN-SAFE（--check実行）/ UN-SAFE（APPLY）` は、
テスト時にどの実行方法を選ぶかを判断するための分類である。

補足:

- SSH 接続そのものではなく、SSH 先で実行するコマンドの性質で判断する。
- SSH 先で read-only コマンドを実行するだけなら、SAFE として自律実行してよい。
- 本番適用を `tester` に行わせないのは、§14 の人間ゲートを保ち、かつ失敗時に `claude` が
  状況をスムーズに把握できるようにするため。
- テスト対象は pve2 を先行する（§2: pve2 は先行検証・縮退運用）。pve1 / 本番は dry-run → 人間判断。
- 初期運用（v1）では高度なことは求めず、まずヘッダの `# tester-gate:` マーカーで実行方針を
  判断し、`--syntax-check` / `--check --diff` を重ねるバリエーションテストを中心に回す。
- quory 上での確認が必要な場合、tester はまず`ssh -i ~/.ssh/id_ann ann@quory.internal` を使う。鍵指定なしの SSH 失敗をもって quory へ SSH 不可と判断しない

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

`implementer` は、実装完了の最後のステップとしてこのコメントを書く。

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

### ssh・git commit・git push・ansible-playbook 素実行の直接実行（Claude Code）

`claude`（要件定義・ハブ役）・`implementer`（実装担当）どちらのロールにも適用される。

```text
- Claude Code は ssh を直接実行しない（対象ホストへの接続は ansible 経由で行う）
- Claude Code は git commit / git push を自ら実行しない（必ずユーザーが実行する）
- Claude Code は ansible-playbook を確認なしに実行しない
- Claude Code は実ホストに触れる ansible ad-hoc コマンド（`ansible <host> -m ...`）
  を自分の判断で実行しない。read-only な調査であっても例外にせず、tester に
  依頼するか Yoshinobu に実行してもらう
```

例外（2026-07-10 Yoshinobu 承認）: `hosts: localhost` + `connection: local` かつ
副作用のないロジック検証用の使い捨て playbook（set_fact / assert 等による
Jinja 式・判定ロジックの検証）は、事前確認なしで実行してよい。
実ホストに触れる可能性のあるもの、ファイル変更・通知等の副作用を持つものは
この例外に含まれない。使い捨て playbook は検証後に削除し、実行した事実と
検証内容を implement ファイルに記録する。

`git commit` / `git push` は `.claude/settings.json` の `deny` で技術的に塞ぐ。
`ssh` / `ansible-playbook` / 実ホストへの `ansible` ad-hoc コマンドは
`.claude/settings.local.json` の `ask` で毎回確認を挟む。

2026-07-08〜09、`bash -c "ssh ..."` のようなラップで `Bash(ssh*)` 系の deny を
すり抜けられることを発見し、一時的に文字列パターンマッチの PreToolUse フックで
対策した。しかしその後、`ansible <host> -m ansible.builtin.command -a "<任意の
コマンド>"` 自体が ssh と同等（あるいはそれ以上）に強力な実行手段であり、これは
`ask` で許可さえ通れば通ってしまうことに気づいた。フックを増やして塞いでも、
`python3 -c` や別のラップ手段など、Turing-complete な実行手段がある限りいたちご
っこが終わらない——文字列パターンマッチでは原理的に勝てないと判断し、フックは
全廃した（旧 `.claude/hooks/check-ansible-playbook-flags.sh` /
`check-wrapped-denies.sh` は削除済み）。

代わりに、ここに書かれたルール自体と、実行前に必ず人間の確認（`ask`）を挟む
運用、そして Yoshinobu 自身のレビュー（実際にこのラウンドで ad-hoc コマンドの
使用を指摘され気づいた）を安全網として扱う。技術的な壁を過信せず、ここに
書かれた約束を守ることそのものが最後の拠り所である。

### IP アドレス（リポジトリ全体）

```text
- IP リテラルをファイルに直接書かない（§3 参照。docs/ も san_ip も対象）
- IP が必要な場合は実行時に getent 等で動的解決する
- ホストはDNS名 / /etc/hosts で名前解決する
```

---

## 18. playbook の check_mode 安全分類（tester-gate）

`tester_mode` / `tester_gate` role は 2026-07-06〜07 に廃止した。理由:
`tester_gate` が play/host 単位で `end_play` / `end_host` するため、危険操作の
手前にある本来安全な診断ロジック（healthcheck、apt dry-run シミュレーション等）
までテスト対象から外れ、テストの実効性が低かった。Ansible が標準で持つ
`--check`（`ansible_check_mode`）をゲート機構として使う方式へ移行した。
Semaphore の `--check` オプションがそのまま効くため、独自の `-e` 変数は不要。

### 18.1 5つの安全分類

どの playbook も、ヘッダに `# tester-gate: <種別> — <理由>` を1行で宣言する
（`scripts/check-tester-gate.sh` が機械チェックする。§18.4）。

| 種別 | 意味 |
| --- | --- |
| `safe-readonly` | 完全 read-only（収集・観測のみ）。ゲート不要、常に本実行してよい。 |
| `role-guarded` | 副作用が Slack 通知のみで、`common_slack/tasks/notify.yml` の `skip_notifications` ガードで抑止される。 |
| `risk-accepted` | 破壊性はあるが、下記2条件を満たすため常に本実行してよいと人間が判断した playbook。`--check` の有無で挙動は変わらない。 |
| `check-mode-native` | read-only な診断・検証部分は `--check` でも常に本実行し、実際の破壊的操作（またはそれに依存する後続処理）だけを `ansible_check_mode` でゲートする。 |
| `dry-run-aware` | 破壊的コマンド自体を、`ansible_check_mode` 下でネイティブの dry-run 引数に差し替えて実行する（スキップではなく安全な引数での実行）。 |

`risk-accepted` の判断基準（2点のみ。**実行コスト＝時間・ストレージI/O等の
大小は理由にしない**）:

1. 本番サービス・他システムへの実害がない（隔離されている / 影響範囲が
   自己完結 / 最悪ケースが軽微で復旧が容易）
2. 破壊的な本体操作を省いた検証には意味がない、または省く価値が乏しい
   （バックアップのリストア検証など、本体操作自体が検証の目的そのものであるケース）

いずれか一方でも成立しない場合は `check-mode-native` または `dry-run-aware` を選ぶ。

### 18.2 実装パターン

**risk-accepted: 常時本実行。** 呼び出し元（playbook または role の import
箇所）に `check_mode: false` を1つ置けば、配下の task・block・rescue・
always・ネストされた `include_tasks`/`include_role`（`loop:` 付きも含む）まで
一括でカスケードする（実地検証済み）。

```yaml
tasks:
  - name: Run <role> (always for real)
    ansible.builtin.import_role:
      name: <role>
    check_mode: false
```

`ansible.builtin.include_role` / `ansible.builtin.include_tasks`（動的include）
は**`check_mode:` を直接付けられない**（`'check_mode' is not a valid attribute
for a IncludeRole/TaskInclude` エラー）。`import_role` / `import_tasks`
（静的）に置き換えるか、block で包んで block 側に `check_mode: false` を置く:

```yaml
- name: Run something (always for real)
  check_mode: false
  block:
    - ansible.builtin.include_role:
        name: <role>
```

呼び出し元の `include_tasks` に **`loop:` が付いている場合は block 化できない**
（Ansible は `block:` に `loop:` を許可しない）。この場合は include 先の
タスクファイル自身に `check_mode: false` を個別に付ける
（例: `roles/recovery_push/tasks/drill_setup.yml`）。

**check-mode-native: 破壊的操作だけゲート。** 読み取り専用の診断タスクには
`check_mode: false`、破壊的タスク（またはそれをまとめた block）には
`when: not ansible_check_mode` + `tags: [destructive]` を付ける:

```yaml
- name: Get cluster resources
  ansible.builtin.command: ...
  check_mode: false          # --check でも実データで実行

- name: Apply patches
  ansible.builtin.command: ...
  when: not ansible_check_mode
  tags: [destructive]
```

複数の破壊的 task が相互依存する場合（reboot→post-reboot検証→報告、
migrate→maintenance mode→HA待機→強制停止 等）は、個別 task に `when` を
付けるより、**一連をまとめて1つの named block にし block 単位でゲート**する
方が壊れにくい:

```yaml
- name: Reboot and post-reboot verification
  when: not ansible_check_mode
  tags: [destructive]
  block:
    - name: Reboot host
      ansible.builtin.reboot: ...
    - name: Check service status
      ansible.builtin.command: ...
```

**dry-run-aware: ネイティブ dry-run へ差し替え。** 破壊的コマンド自体の引数を
`ansible_check_mode` で切り替える（例: `roles/sophos_trim/tasks/main.yml`）:

```yaml
- name: Set fstrim options (dry-run under --check)
  ansible.builtin.set_fact:
    fstrim_opts: "{{ '--dry-run -v' if ansible_check_mode else '-v' }}"
```

この方式では、コマンドを実行するタスク自体（`expect` や `command` など
check_mode 非対応モジュール）に `check_mode: false` を付けないと、`--check`
時にタスクごと auto-skip され、フラグの切り替えが無意味になる（§18.3）。

**import_playbook で束ねるオーケストレータの注意。** import 先が既に
`check-mode-native` 化されている場合、オーケストレータ側の `when:` 条件に
`ansible_check_mode` を追加しない（`proxmox_patch_weekly_full.yml` の設計）。
追加すると、import 先で意図的に残した「read-only 部分は `--check` でも
本実行する」設計を上位で握りつぶし、テスト網羅性が落ちる。オーケストレータ
自身の preflight・完了通知等は別途 `--check` 対応が必要（§18.3 参照）。

### 18.3 Ansible check_mode の落とし穴

実装時に繰り返し踏んだ／踏みかけた問題。新しい playbook を書く・レビューする
際は毎回意識する:

1. **モジュールごとに check_mode 挙動が3パターンに分かれる。**
   - 非対応・auto-skip: `command` / `shell` / `expect` / `uri`
     （`ansible-doc <module>` の `attributes.check_mode.support: none` で
     確認できる）
   - 対応・simulate: `copy` / `template` / `file` / `systemd` / `apt` 等
     （`--check` 下では実際に書き込まず `changed` だけ返す）
   - `command`/`shell` + `creates:`/`removes:`: ファイル存在チェックの結果に
     応じて「`changed: true` と報告しつつ実行しない」という第3パターンを取る
   - `risk-accepted` で「初回でも必ず実データを作りたい」場合は、上記いずれの
     モジュールでも `check_mode: false` を明示しないと、実行されない・
     simulate されるだけで終わる。
2. **ハンドラは通知元タスクの `check_mode: false` を継承しない。** ハンドラ
   自身に個別で `check_mode: false` を付ける必要がある（実地検証済み）。
3. **`meta: end_play` / `end_host` は、それが属する block の `always:` を
   丸ごとスキップする**（通常の task 失敗による rescue/always フローとは
   異なる）。これに依存した旧ゲート実装は、実は停止時にレポート保存も通知も
   一切残らない「無音停止」になっていた。
4. **2値分岐（`ok`/`error` 等）の通知・レポートに plan-only/check-mode の
   分岐を追加し忘れると、dry-run の成功が `error`（最悪 `critical`）として
   誤通知される。** `--check` 実行時は必ず結果分岐にも check_mode を考慮する。
5. **`block:` に `loop:` は付けられない。** `include_tasks`/`include_role` に
   `loop:` が付いている呼び出しは block 化でのカスケードが使えないため、
   include 先のタスクファイル自身に `check_mode: false` を個別に付ける。

### 18.4 機械チェック（lint）

「全 playbook が上記5分類のいずれかに分類されている」は規約ではなく lint で
保証する。

- `scripts/check-tester-gate.sh` が playbooks/ 配下の全 playbook を検査する
  （pre-commit フックから自動実行）。
- 判定: 以下のいずれかのヘッダマーカーがあること。

```text
# tester-gate: safe-readonly — <理由>       完全 read-only、ゲート不要
# tester-gate: role-guarded — <理由>        副作用が Slack 通知のみ
# tester-gate: risk-accepted — <理由>       常に本実行してよいと人間が判断
                                            （許容した最悪ケースを理由に明記）
# tester-gate: check-mode-native — <理由>   ansible_check_mode で破壊的操作をゲート
# tester-gate: dry-run-aware — <理由>       破壊的コマンドをネイティブ dry-run に差し替え
```

新規 playbook は、上記いずれかのマーカーを付けない限り commit できない。

### 18.5 tester の実行義務

- tester は `claude` から渡されたコマンドをそのまま実行しない。対象
  playbook のヘッダマーカーを必ず確認する。
- マーカーが `safe-readonly` / `role-guarded` / `risk-accepted`: 通常実行で
  よい（`--check` は不要。付けても `risk-accepted` は挙動が変わらない）。
- マーカーが `check-mode-native` / `dry-run-aware`: **必ず `--check` を付ける**
  （`--check --diff` を重ねてもよい）。`--check` を付けない実行は APPLY
  （本番適用）であり、tester は行わない。
- `allow_unsafe=true` は今回実装しない（将来のオプション）。

### 18.6 Codex 用 `--check` 実行 wrapper

Codex の承認ルール（`~/.codex/rules/default.rules`）は prefix ベースで判定するため、
`ansible-playbook playbooks/foo.yml --check` のように `--check` が後方にある
コマンドを「安全な check 実行」として一般判定できない。

そのため、Codex が `check-mode-native` / `dry-run-aware` の playbook を
`--check` 実行する場合は、原則として以下の wrapper を使う。

```bash
scripts/safe-ansible-check.sh playbooks/foo.yml --check
scripts/safe-ansible-check.sh playbooks/foo.yml -e target=authy --check
```

この wrapper は argv に `--check` が含まれない場合は即終了し、含まれる場合のみ
`ansible-playbook "$@"` に委譲する。

運用ルール:

- `check-mode-native` / `dry-run-aware` の検証実行は
  `scripts/safe-ansible-check.sh ... --check` を使う。
- `--check` なしの `ansible-playbook` は wrapper を使わない。APPLY または
  `risk-accepted` の通常実行として扱い、必要に応じて人間確認を通す。
- `risk-accepted` は常時本実行が前提なので、この wrapper の対象ではない。
- wrapper は Codex の承認プロンプト削減のための補助であり、安全性の最終判断は
  playbook header の `# tester-gate:` マーカーと test_plan に基づいて行う。
