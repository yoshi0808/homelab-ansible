# Codex Design Template

このファイルは、Codex に Playbook / Role の設計方針を書かせるための依頼テンプレートです。  
実装は行わず、設計書のみを作成してください。

---

## 依頼内容

`docs/ai/prompts/core.md` を読んでください。

以下の対象について、Ansible Playbook / Role の設計書を作成してください。

---

## 対象

`<target_name>`

例:

- `proxmox_healthcheck`
- `proxmox_hw_check`
- `proxmox_patch`
- `radius_healthcheck`
- `radius_patch`

---

## 目的

`<purpose>`

例:

- `authy.internal 上の FreeRADIUS サーバーの稼働状態を確認する`
- `pve1 / pve2 の Proxmox 運用状態を確認する`
- `pve2 に先行してパッチを適用する前の安全確認を行う`

---

## 設計で整理すること

以下を必ず整理してください。

### 1. Playbook の役割

- playbook 名
- 対象ホスト / 対象グループ
- 実行タイミング
- 読み取り系か変更系か
- 呼び出す role

### 2. Role の役割

- role 名
- role が担当する処理
- defaults / tasks / files の役割
- report 出力先

### 3. shell / script と Ansible tasks の責務分離

以下の原則を守ってください。

```text
shell / script:
  収集とJSON整形のみ

Ansible tasks:
  配置、実行、JSON読込、期待値比較、warning/critical分類、保存、fail制御
```

check 系 shell は原則として判断を行いません。

shell が行わないこと:

- 正常 / 異常の判定
- warning / critical の分類
- host_vars との期待値比較
- 実行継続 / 中止の判断
- 通知
- レポート保存

### 4. shell が収集する項目

shell が対象ホスト上で収集する情報を整理してください。

例:

- service 状態
- port listen 状態
- journal の直近エラー
- バージョン情報
- 証明書ディレクトリの存在
- 時刻同期状態
- raw output
- command return code

shell は収集結果を JSON として標準出力に返します。

### 5. Ansible tasks が判定する項目

Ansible tasks 側で判定する内容を整理してください。

例:

- service が active でない場合は critical
- 必須ポートが listen していない場合は critical
- 時刻同期が取れていない場合は warning / critical
- 証明書ディレクトリが存在しない場合は critical
- journal に重大エラーがある場合は warning

### 6. warnings / criticals の考え方

以下を整理してください。

- warning とする条件
- critical とする条件
- fail する条件
- fail せず report に残す条件

### 7. report JSON の保存先

report の保存先を指定してください。

例:

```text
reports/<target-name>/
reports/radius-health/
reports/proxmox-health/
reports/proxmox-hardware/
```

### 8. 変更操作の有無

読み取り系の場合:

- 対象ホストの状態を変更しない
- restart / reload / reboot / apt upgrade などを行わない

変更系の場合:

- どの変更操作を行うか
- 事前条件
- 中止条件
- rollback または停止判断
- precheck との関係

### 9. SSH鍵・秘密情報の扱い

以下を守ってください。

- SSH秘密鍵そのものを生成・表示・変更しない
- 秘密鍵の中身をリポジトリに保存しない
- `ansible_ssh_private_key_file` はパス参照のみ許容する
- `all.yml` / `vault.yml` / 秘密情報を含むファイルを勝手に作成しない
- `all.yml.example` には例だけを書く
- `authorized_keys` を勝手に変更しない

### 10. 初回実装で含める範囲

最初の実装で含める項目を整理してください。

### 11. 初回実装では除外する範囲

最初の実装では扱わない項目を整理してください。

例:

- restart / reload
- patch 適用
- reboot
- 証明書の自動更新
- 設定ファイルの自動修正
- 認証の実トラフィック試験

### 12. 想定ファイル

作成・更新が想定されるファイルを整理してください。

例:

```text
playbooks/<target_name>.yml
roles/<role_name>/defaults/main.yml
roles/<role_name>/tasks/main.yml
roles/<role_name>/files/<script-name>.sh
reports/<report-dir>/README.md
docs/ai/reviews/<target_name>/
```

---

## 出力先

設計結果は以下に保存してください。

```text
docs/ai/reviews/<target_name>/YYYY-MM-DD_001_codex_design.md
```

日付は作業日の年月日を使ってください。

---

## 禁止事項

- 実装しない
- playbook / role / shell の中身をまだ変更しない
- 既存ファイルを破壊的に上書きしない
- 秘密情報を生成・表示・保存しない
- 判断ロジックを shell 側に寄せる設計にしない
- IPアドレス直書き前提にしない

---

## 出力形式

以下の構成で設計書を書いてください。

```md
# <target_name> Design

## 1. 目的

## 2. 対象ホスト / グループ

## 3. Playbook 設計

## 4. Role 設計

## 5. shell / script 設計

## 6. Ansible tasks 設計

## 7. 収集項目

## 8. 判定項目

## 9. warnings / criticals 方針

## 10. report JSON 設計

## 11. 変更操作の有無

## 12. SSH鍵・秘密情報の扱い

## 13. 初回実装で含める範囲

## 14. 初回実装では除外する範囲

## 15. 作成・更新予定ファイル

## 16. リスク / 注意点

## 17. Claude Code 実装依頼ファイル名案

## 18. Codex レビュー用空ファイル名案

## 19. Claude Code 再実装依頼用空ファイル名案
```

---

## 補足

設計書の最後に、次工程で Claude Code に渡す実装依頼ファイル名案を記載してください。

例:

```text
docs/ai/reviews/<target_name>/YYYY-MM-DD_002_claude_code_implement_request.md
docs/ai/reviews/<target_name>/YYYY-MM-DD_003_codex_review.md
docs/ai/reviews/<target_name>/YYYY-MM-DD_004_claude_code_reimplement_request.md
```
