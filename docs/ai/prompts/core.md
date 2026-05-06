# core.md

このファイルは、`homelab-ansible` リポジトリで AI 支援により Ansible Playbook / role / shell を設計・実装・レビューするための共通前提である。

Codex / Claude Code に依頼する際は、原則として最初にこの `core.md` を読ませる。

---

## 1. このリポジトリの目的

このリポジトリは、Yoshinobu の homelab 環境を Ansible で管理するためのもの。

主な対象は以下。

| 名前 | 役割 |
|---|---|
| `ansy` | Ansible 開発環境。VS Code / Codex / Claude Code を使い、Playbook や role を作成・レビューする。Git へ commit / push する作業場。 |
| `quory` | 本番 Ansible 実行基盤。Git から確定済みソースを取得し、Proxmox や VM に対して Ansible を実行する。 |
| `pve1` | Proxmox メインノード。通常稼働の中心。 |
| `pve2` | Proxmox セカンダリノード。先行検証・縮退運用・フェイルオーバー先。 |
| Git repository | Ansible コードの正本。ansy から push し、quory が pull する。 |

基本方針は以下。

```text
ansy  = 開発・レビュー・commit/push
Git   = 正本管理
quory = 本番取得・Ansible実行
```

quory 上では原則として直接コード編集しない。

---

## 2. ノード名と名前解決

Ansible inventory では、原則として IP アドレスを直接書かない。

以下のような名前ベースで管理する。

```text
pve1  -> pve1.internal
pve2  -> pve2.internal
quory -> quory.internal
ansy  -> ansy.internal
```

名前解決は DNS または quory の `/etc/hosts` で担保する。

inventory では以下のような形式を基本とする。

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
```

`proxmox_healthcheck.yml` や `proxmox_hw_check.yml` は `proxmox` グループを対象にし、quory は対象に含めない。

quory を対象にする playbook は専用 playbook に限定する。

例:

```text
quory_setup.yml
quory_update.yml
semaphore_setup.yml
```

---

## 3. Ansible と shell の責務分離

本リポジトリでは、Ansible と shell の責務を明確に分離する。

```text
Shell:
  収集とJSON整形のみ

Ansible:
  配置、実行、JSON読込、期待値比較、warning/critical分類、保存、fail制御
```

### shell が行うこと

check 系 shell は対象ホスト上でコマンドを実行し、結果を JSON に整形して標準出力へ返す。

check 系 shell が行うのは以下。

```text
- コマンド実行
- raw stdout / stderr / rc の取得
- JSONへの整形
- 標準出力へのJSON出力
```

### shell が行わないこと

check 系 shell は判断を行わない。

```text
- 正常 / 異常の判定
- warning / critical の分類
- host_vars との期待値比較
- 実行継続 / 中止の判断
- 通知
- レポート保存
```

これらは Ansible tasks 側で行う。

---

## 4. shell / script の配置方針

check 系 shell は `roles/*/files/*.sh` に置く。

通常は Ansible が `copy` して `/usr/local/sbin/` に配置し、`command` で実行する。

一時実行だけでよい role では `ansible.builtin.script` の利用も許容する。

### 通常方式: copy + command

```yaml
- name: Install healthcheck shell
  ansible.builtin.copy:
    src: proxmox-healthcheck.sh
    dest: "{{ proxmox_healthcheck_script_path }}"
    owner: root
    group: root
    mode: "0755"

- name: Run healthcheck shell
  ansible.builtin.command:
    cmd: "{{ proxmox_healthcheck_script_path }}"
  register: proxmox_healthcheck_result
  changed_when: false
```

この方式では、対象ホスト上に `/usr/local/sbin/proxmox-healthcheck` として shell が残る。

障害時に Proxmox 上で直接実行できる利点がある。

### 一時実行方式: script

```yaml
- name: Run healthcheck shell temporarily
  ansible.builtin.script: proxmox-healthcheck.sh
  register: proxmox_healthcheck_result
  changed_when: false
```

この方式は、対象ホスト上に shell を恒久配置したくない場合に使う。

---

## 5. templates の扱い

本構成では、check 系 shell は原則として `templates/*.sh.j2` には置かない。

Ansible 変数をファイル内へ埋め込む必要がある場合のみ `roles/*/templates/*.j2` を使う。

静的 shell で足りる場合は `roles/*/files/*.sh` に置く。

---

## 6. 変更系 shell の扱い

`proxmox_patch` や将来の `proxmox_reboot` では、shell が更新・再起動などの変更操作を含む可能性がある。

ただし、変更系 shell は例外扱いとし、以下を守る。

```text
- 読み取り系 role と変更系 role を分ける
- playbook 名で変更系だと分かるようにする
- reboot / patch / migrate などは専用 playbook に分離する
- check 系 shell に変更操作を混ぜない
- 変更系 shell は Ansible tasks 側で明示的に実行条件を制御する
```

---

## 7. playbook の分け方

playbook は 1 ファイルにまとめず、運用目的ごとに分ける。

| Playbook | 目的 | 変更有無 |
|---|---|---|
| `ping.yml` | 疎通確認 | なし |
| `proxmox_hw_check.yml` | ハードウェア棚卸し・確認 | 原則なし |
| `proxmox_healthcheck.yml` | 日常ヘルスチェック | 原則なし |
| `proxmox_patch_precheck.yml` | パッチ前確認 | なし |
| `proxmox_patch_pve2.yml` | pve2 へのパッチ適用 | あり |
| `proxmox_patch_pve1.yml` | pve1 へのパッチ適用 | あり |

読み取り系と変更系は必ず分ける。

特に `check` / `precheck` / `patch` / `reboot` は同じ入口に混ぜない。

---

## 8. role の基本構成

代表的な role 構成は以下。

```text
roles/<role_name>/
├── defaults/
│   └── main.yml
├── tasks/
│   └── main.yml
└── files/
    └── <script>.sh
```

| 人間向けの理解 | 実ファイル | 役割 |
|---|---|---|
| playbook | `playbooks/*.yml` | 人間が実行する入口。 |
| shell / script | `roles/*/files/*.sh` | 対象ホスト上で動く処理本体。check 系では収集と JSON 整形のみを行う。patch / reboot 系では限定的な変更操作を行う場合がある。 |
| Ansible 配管 | `roles/*/tasks/main.yml` | shell の配置・実行・JSON 読み込み・保存・判定。 |
| 初期設定 | `roles/*/defaults/main.yml` | role のデフォルト設定。 |
| ホスト別設定 | `inventories/homelab/host_vars/*.yml` | pve1 / pve2 固有の期待値。 |

---

## 9. Git 更新運用

開発環境 `ansy` で実装・レビュー・commit・push を行う。

本番実行基盤 `quory` は Git から確定済みソースを取得して実行する。

```text
ansy
  ↓ commit / push
Git repository
  ↓ pull
quory
  ↓ ansible-playbook
pve1 / pve2 / VM
```

### quory での基本ルール

```text
- quory では原則として直接コード編集しない
- quory では原則として commit しない
- quory は Git から pull して実行する
- pull は --ff-only を使う
- pull 前に working tree が clean であることを確認する
```

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

## 10. 自動実行の考え方

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

---

## 11. RADIUS サーバーの管理対象追加

本リポジトリは Proxmox ノードだけでなく、重要サービス VM も管理対象に含める。

authy は RADIUS / FreeRADIUS サーバーとして扱う。

Ansible グループ名は `radius_servers`。

playbook / role 名は `authy_` ではなく `radius_` ベースを基本とする。

RADIUS 系でも責務分離は同じ。

- shell: 収集と JSON 整形のみ
- Ansible tasks: 判定、warnings/criticals、保存、fail制御

check 系 shell は `roles/*/files/*.sh` に置く。

通常は copy + command で `/usr/local/sbin/` に配置して実行する。

一時実行だけでよい role では ansible.builtin.script も許容する。

将来的には、Semaphore UI の Repository / Task Template / Schedule 機能に移行する。

---

## 11. .gitignore 方針

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

## 12. AI を使った構築・レビュー運用

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

### prompts/ の考え方

`docs/ai/prompts/` は、AI に渡す固定テンプレートを置く場所である。

`core.md` は共通前提であり、その他は依頼テンプレートである。

```text
docs/ai/prompts/
├── core.md
├── codex-design-template.md
├── codex-review-template.md
├── claude-code-implement-template.md
└── claude-code-reimplement-template.md
```

| ファイル | 役割 |
|---|---|
| `core.md` | AIに毎回渡す共通前提。環境・運用ルール・禁止事項など。 |
| `codex-design-template.md` | Codexに設計方針を作らせる依頼テンプレート。 |
| `codex-review-template.md` | Codexに差分レビューさせる依頼テンプレート。 |
| `claude-code-implement-template.md` | Claude Codeに初回実装させる依頼テンプレート。 |
| `claude-code-reimplement-template.md` | Claude Codeにレビュー反映・再実装させる依頼テンプレート。 |

---

## 13. ユーザーからの playbook 作成リクエスト時の流れ

ユーザーが作りたい playbook / role のリクエストを出したら、以下の流れで進める。

### 13.1 Codex による設計

ユーザーのリクエストを受けたら、Codex は以下を読む。

```text
docs/ai/prompts/core.md
docs/ai/prompts/codex-design-template.md
```

Codex はその内容を元に、対象 playbook / role の設計書を書き起こす。

設計書は `docs/ai/reviews/<target>/` に保存する。

例:

```text
docs/ai/reviews/proxmox_healthcheck/2026-05-06_001_codex_design.md
docs/ai/reviews/proxmox_patch/2026-05-07_001_codex_design.md
```

### 13.2 Claude Code 実装依頼用ファイルの作成

Codex は、設計書の内容を元に、Claude Code に渡す個別の実装依頼ファイルも作成する。

このファイルは、`docs/ai/prompts/claude-code-implement-template.md` を参考にして作る。

保存先は `docs/ai/reviews/<target>/` とする。

例:

```text
docs/ai/reviews/proxmox_healthcheck/2026-05-06_002_claude_code_implement_request.md
docs/ai/reviews/proxmox_patch/2026-05-07_002_claude_code_implement_request.md
```

ユーザーはこの個別の実装依頼ファイルの内容を Claude Code に渡し、playbook / role / shell の作成を指示する。

### 13.3 空のレビュー用ファイルの作成

Codex は、後続工程のために空のレビュー用ファイルも作成する。

例:

```text
docs/ai/reviews/proxmox_healthcheck/2026-05-06_003_codex_review.md
```

このファイルは、Claude Code の実装後に Codex がレビュー結果を書き込む場所として使う。

### 13.4 空の再実装依頼用ファイルの作成

Codex は、レビュー後に Claude Code へ再実装を依頼するための空ファイルも作成する。

このファイルは、`docs/ai/prompts/claude-code-reimplement-template.md` を参考にして後で埋める。

例:

```text
docs/ai/reviews/proxmox_healthcheck/2026-05-06_004_claude_code_reimplement_request.md
```

Codex のレビューで修正が必要になった場合、ユーザーまたは Codex はこのファイルに再実装依頼内容を書き、Claude Code に渡す。

---

## 14. 実装後のレビュー・再実装・確定フロー

実装後は以下の流れで進める。

```text
1. Claude Code が実装する
2. Codex が git diff を確認する
3. Codex が docs/ai/reviews/<target>/..._codex_review.md にレビューを書く
4. 修正が必要な場合、Claude Code 用の再実装依頼ファイルを作る
5. Claude Code が再実装する
   - レビューに反証がある場合は docs/ai/reviews/<target>/ に反証を書く
6. Codex が再レビューする
7. 必要に応じて 3〜6 を繰り返す
8. Yoshinobu が「これで確定」と判断する
9. Codex が正本登録する
10. Yoshinobu が commit する
```

### final ファイル

確定時には `final` ファイルを作る。

例:

```text
docs/ai/reviews/proxmox_healthcheck/2026-05-06_999_final.md
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

---

## 15. 禁止事項

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

---

## 16. 将来方針

最初は Ansible playbook / role / shell を CLI で安定させる。

Semaphore UI 導入前の日次実行は quory の systemd timer で行う。

将来的には、以下を Semaphore UI に移行する。

```text
- playbook のGUI実行
- Repository機能によるGit取得
- Task Templateによるplaybook実行
- Schedule機能による日次healthcheck
```

Semaphore UI に移行後は、systemd timer から Semaphore UI の Schedule へ自動実行を移す。
