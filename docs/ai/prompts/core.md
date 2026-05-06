# core.md

このファイルは、`homelab-ansible` リポジトリで AI に作業を依頼するときに毎回共有する共通前提である。

`docs/ai/prompts/*-template.md` は作業種別ごとの依頼テンプレートであり、この `core.md` はそれらすべての前提として扱う。

---

## 1. リポジトリの目的

このリポジトリは、homelab 環境の Ansible Playbook / role / script を管理する。

主な目的は以下。

- Proxmox ノードの稼働確認
- Proxmox ノードのハードウェア確認
- Proxmox ノードのパッチ前確認
- Proxmox ノードのパッチ適用
- RADIUS / FreeRADIUS サーバーの稼働確認
- RADIUS / FreeRADIUS サーバーのパッチ前確認
- RADIUS / FreeRADIUS サーバーのパッチ適用
- 将来的な Semaphore UI による GUI 実行・自動実行

---

## 2. 主要ノードと役割

| ホスト名 | 種別 | 役割 |
|---|---|---|
| `ansy` | VM | Ansible 開発環境。VS Code / Codex / Claude Code を使い、実装・レビュー・commit / push を行う。 |
| `quory` | 物理ノード | QDevice + 監視基盤。本番 Ansible 実行基盤。Git から確定済みソースを取得して実行する。 |
| `pve1` | 物理ノード | Proxmox メインノード。通常稼働の中心。 |
| `pve2` | 物理ノード | Proxmox セカンダリノード。先行検証・縮退運用・フェイルオーバー先。 |
| `authy` | VM | RADIUS / FreeRADIUS サーバー。WPA3 Enterprise / EAP-TLS 認証基盤。 |

基本方針は以下。

```text
ansy  = 開発・レビュー・commit/push
Git   = 正本管理
quory = 本番取得・Ansible実行
```

quory 上では原則として直接コード編集しない。

---

## 3. 名前解決方針

Ansible inventory では、原則として IP アドレスを直接書かない。

内部DNS名または `/etc/hosts` による名前解決を使う。

| ホスト | 推奨名 |
|---|---|
| `pve1` | `pve1.internal` |
| `pve2` | `pve2.internal` |
| `quory` | `quory.internal` |
| `ansy` | `ansy.internal` |
| `authy` | `authy.internal` |

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
```

名前解決は DNS または quory / ansy の `/etc/hosts` で担保する。

---

## 4. 管理対象グループ

| グループ | 対象 | 用途 |
|---|---|---|
| `proxmox` | `pve1`, `pve2` | Proxmox VE ノード管理 |
| `control_nodes` | `quory` | Ansible 実行基盤 / Semaphore UI / QDevice / 監視基盤管理 |
| `dev_nodes` | `ansy` | Ansible 開発環境管理 |
| `radius_servers` | `authy` | FreeRADIUS / RADIUS サーバー管理 |

`proxmox_healthcheck.yml` や `proxmox_hw_check.yml` は `proxmox` グループを対象にする。

`radius_healthcheck.yml` や `radius_patch.yml` は `radius_servers` グループを対象にする。

quory を対象にする playbook は、`quory_setup.yml` / `quory_update.yml` / `semaphore_setup.yml` のような専用 playbook に限定する。

---

## 5. SSH 接続と秘密鍵の扱い

Ansible 実行環境 `ansy` / `quory` から管理対象ホストへ接続する場合、原則として Ansible 管理用ユーザー `ann` と Ansible 管理用 SSH 鍵 `~/.ssh/id_ann` を使う。

対象ホスト側では、`~/.ssh/id_ann.pub` を `ann` ユーザーの `authorized_keys` に登録する。

`ann` は Ansible 管理用ユーザーであり、NOPASSWD sudo 可能であることを前提とする。

秘密鍵そのもの、秘密鍵の中身、パスフレーズ、認証情報はリポジトリに保存しない。

Playbook / role / inventory では、秘密鍵の中身を扱わず、必要な場合はパス参照のみ使う。

例:

```yaml
ansible_user: ann
ansible_ssh_private_key_file: ~/.ssh/id_ann
```

`all.yml` や `vault.yml` など、秘密情報を含む可能性があるファイルは Git 管理しない。

代わりに `all.yml.example` を Git 管理する。

例:

```yaml
---
# Copy this file to all.yml and customize locally.
# Do not commit all.yml.

ansible_user: ann
ansible_ssh_private_key_file: ~/.ssh/id_ann
```

AI への禁止事項:

```text
- 秘密鍵ファイルを生成しない
- 秘密鍵の中身を表示しない
- ~/.ssh/id_ann をリポジトリ内にコピーしない
- group_vars/all.yml を勝手に作成・コミットしない
- vault.yml を平文で作成しない
- authorized_keys を勝手に上書きしない
- SSHポートやユーザーを推測して固定しない
```

---

## 6. Ansible role の基本方針

人間向けには以下のように理解する。

| 人間向けの理解 | 実ファイル | 役割 |
|---|---|---|
| playbook | `playbooks/*.yml` | 人間が実行する入口。 |
| shell / script | `roles/*/files/*.sh` | 対象ホスト上で動く処理本体。check 系では収集と JSON 整形のみを行う。patch / reboot 系では限定的な変更操作を行う場合がある。 |
| Ansible 配管 | `roles/*/tasks/main.yml` | shell の配置・実行・JSON 読み込み・保存・判定。 |
| 初期設定 | `roles/*/defaults/main.yml` | role のデフォルト設定。 |
| ホスト別設定 | `inventories/homelab/host_vars/*.yml` | ホスト固有の期待値や差分。 |

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

| Playbook | 目的 | 変更有無 |
|---|---|---|
| `ping.yml` | 疎通確認 | なし |
| `proxmox_hw_check.yml` | ハードウェア棚卸し・確認 | 原則なし |
| `proxmox_healthcheck.yml` | 日常ヘルスチェック | 原則なし |
| `proxmox_patch_precheck.yml` | パッチ前確認 | なし |
| `proxmox_patch_pve2.yml` | pve2 へのパッチ適用 | あり |
| `proxmox_patch_pve1.yml` | pve1 へのパッチ適用 | あり |

### RADIUS 系

| Playbook | 目的 | 変更有無 |
|---|---|---|
| `radius_healthcheck.yml` | RADIUS / FreeRADIUS 稼働確認 | 原則なし |
| `radius_patch_precheck.yml` | RADIUS サーバーのパッチ前確認 | なし |
| `radius_patch.yml` | RADIUS サーバーのパッチ適用 | あり |

role / playbook 名は、ホスト名 `authy` ではなく役割名 `radius` ベースを基本とする。

---

## 11. precheck NG 時の運用

`proxmox_patch_precheck.yml` や `radius_patch_precheck.yml` が失敗した場合、patch 系 playbook は実行しない。

基本フロー:

```text
1. precheck を実行する
2. warnings / criticals / fail を確認する
3. NGなら patch を中止する
4. 原因を修正する
5. precheck を再実行する
6. OKなら patch へ進む
7. patch 後に healthcheck を実行する
```

Semaphore UI 導入後は、precheck task が fail した場合に patch task へ進ませない運用に移行する。

---

## 12. Git 更新運用

開発環境 `ansy` で実装・レビュー・commit・push を行う。

本番実行基盤 `quory` は Git から確定済みソースを取得して実行する。

```text
ansy
  ↓ commit / push
Git repository
  ↓ pull
quory
  ↓ ansible-playbook
pve1 / pve2 / authy / VM
```

quory での基本ルール:

```text
- quory では原則として直接コード編集しない
- quory では原則として commit しない
- quory は Git から pull して実行する
- pull は --ff-only を使う
- pull 前に working tree が clean であることを確認する
```

Git pull を Ansible playbook 自身で行うことは避ける。

理由は、実行中の playbook が自分自身を更新する「自己更新問題」が起きるため。

---

## 13. 自動実行方針

Ansible 自体には「時間になったら自分で起動する」機能はない。

Semaphore UI 導入前は、quory 上で `systemd timer` が `ansible-playbook` を起動する。

日次 healthcheck では、原則として毎回自動で Git pull しない。

```text
コード更新:
  手動または専用スクリプトで実施

日次実行:
  反映済みコードを systemd timer で実行
```

これにより、ansy から push したばかりの未確認コードが、翌朝に自動で本番実行される事故を避ける。

将来的には Semaphore UI の Schedule 機能へ移行する。

---

## 14. .gitignore 方針

生成される reports や、秘密情報を含む可能性のある変数ファイルは Git 管理しない。

例:

```gitignore
# Ansible runtime output
reports/**/*.json
reports/**/*.log

# Local secrets / private variables
inventories/homelab/group_vars/all.yml
inventories/homelab/group_vars/vault.yml
inventories/homelab/host_vars/*/vault.yml

# Retry files
*.retry

# Python / tooling
__pycache__/
*.pyc

# Editor / OS
.vscode/
.DS_Store

# Temporary files
*.tmp
```

`all.yml` を除外する場合は、代わりに `all.yml.example` を Git 管理する。

---

## 15. AI の役割分担

AI の役割分担は以下とする。

```text
設計方針: Codex
実装: Claude Code
レビュー: Codex
再実装: Claude Code
再レビュー: Codex
決定: Yoshinobu
正本登録: Codex
コミット: Yoshinobu
```

実ファイルを直接更新するAIは原則として Claude Code / Codex に限定するが、同じタイミングで複数AIに同じファイルを更新させない。

ChatGPT は設計相談、レビュー観点整理、壁打ちに使う。

---

## 16. prompts と reviews の使い分け

`docs/ai/prompts/` は、AIに渡す固定テンプレートを置く場所である。

`core.md` は共通前提。

それ以外の `*-template.md` は依頼テンプレート。

```text
docs/ai/prompts/
├── core.md
├── codex-design-template.md
├── codex-review-template.md
├── claude-code-implement-template.md
└── claude-code-reimplement-template.md
```

`docs/ai/reviews/` は、実際の設計結果・レビュー結果・反証・確定記録を置く場所である。

```text
docs/ai/reviews/<target>/
├── YYYY-MM-DD_001_codex_design.md
├── YYYY-MM-DD_002_claude_implementation_note.md
├── YYYY-MM-DD_003_codex_review.md
├── YYYY-MM-DD_004_claude_counterargument.md
├── YYYY-MM-DD_005_codex_review_after_fix.md
└── YYYY-MM-DD_006_final.md
```

`decisions/` は作らない。理由や経緯は `reviews/` に残す。

---

## 17. Playbook 作成依頼から確定までの運用フロー

ユーザーが作りたい playbook / role をリクエストする。

以後の流れは以下。

```text
1. ユーザーが作りたい playbook / role をリクエストする

2. Codex は docs/ai/prompts/core.md と
   docs/ai/prompts/codex-design-template.md を元に設計書を作成する

3. Codex は設計書を以下に保存する
   docs/ai/reviews/<target>/YYYY-MM-DD_001_codex_design.md

4. Codex は docs/ai/prompts/claude-code-implement-template.md を参考に、
   Claude Code に渡す個別の実装依頼ファイルを作成する

   例:
   docs/ai/reviews/<target>/YYYY-MM-DD_002_claude_implement_request.md

5. Codex はレビュー用の空ファイルを作成する

   例:
   docs/ai/reviews/<target>/YYYY-MM-DD_003_codex_review.md

6. Codex は再実装依頼用の空ファイルを作成する

   例:
   docs/ai/reviews/<target>/YYYY-MM-DD_004_claude_reimplement_request.md

7. ユーザーは Claude Code に
   YYYY-MM-DD_002_claude_implement_request.md を渡して実装を依頼する

8. Claude Code は playbooks/、roles/、inventories/ などの正本候補を実装する

9. Codex は git diff を確認し、
   YYYY-MM-DD_003_codex_review.md にレビューを書く

10. 修正が必要な場合、ユーザーは Claude Code に
    YYYY-MM-DD_004_claude_reimplement_request.md を渡して再実装を依頼する

11. Claude Code が Codex レビューに反証する場合は、
    docs/ai/reviews/<target>/ に反証ファイルを書く

12. Codex が再レビューする

13. 必要に応じて 9〜12 を繰り返す

14. Yoshinobu が「これで確定」と判断する

15. Codex が正本登録する

16. Yoshinobu が commit する
```

この運用では、`prompts/` は固定テンプレートとして使い回し、対象ごとの設計・レビュー・確定記録は `reviews/<target>/` に蓄積する。

---

## 18. 禁止事項

AI に作業を依頼するときは、以下を禁止する。

```text
- 秘密鍵、パスワード、トークン、証明書秘密鍵を生成・表示・コミットすること
- IPアドレスを推測して inventory に直書きすること
- check系 shell に変更操作を入れること
- shell側で warning / critical 判定を行うこと
- Ansible playbook 内で Git pull すること
- quory 上で直接開発・commit する前提にすること
- patch / reboot / migrate を check 系 playbook に混ぜること
- 既存ファイルを破壊的に上書きすること
```
