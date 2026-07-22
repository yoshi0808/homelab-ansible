# Ansible Repository Overview

この文書は、新しいIssueから対象のinventory、playbook、role、Policy候補へ進むための入口である。詳細仕様や変化する値は複製せず、現行コードを正本とする。

## 正本と地図の使い方

1. 対象ホストまたはgroupを [`inventory-map.md`](inventory-map.md) で確認する。
2. 実行入口、安全上の種別、関連Policy候補を [`playbook-map.md`](playbook-map.md) で絞る。
3. 処理本体、主要入力、副作用、利用元を [`role-map.md`](role-map.md) で確認する。
4. 実装判断は、地図ではなく対象ファイル、現在のdiff、関連Policyを読んで確定する。

地図と実体が食い違う場合は、`ansible.cfg`、`inventories/homelab/hosts.yml`、`playbooks/*.yml`、`roles/*` の現行実体を優先し、地図を更新する。安全区分は各playbook先頭の `# tester-gate:` が正本である。

## 構造

| Path | 責務 | 値・詳細の正本 |
| --- | --- | --- |
| `ansible.cfg` | 既定inventory、role探索path、Ansible共通設定 | ファイル本体 |
| `inventories/homelab/hosts.yml` | inventory groupとホスト所属 | ファイル本体 |
| `inventories/homelab/group_vars/` | group共通の接続・期待値・設定 | 各varsファイル |
| `inventories/homelab/host_vars/` | ホスト固有の期待値・差分 | 各varsファイル |
| `inventories/vars/` | 複数入口から参照する実行変数。秘密を含み得る | 各varsファイルと秘密管理 |
| `playbooks/*.yml` | 人間、Semaphore、timer等が呼ぶ実行入口と処理順 | 各playbook |
| `roles/*/defaults/` | roleの既定入力 | 各roleのdefaults |
| `roles/*/tasks/` | 配置、実行、判定、通知、変更処理の配管・本体 | 各roleのtasks |
| `roles/*/files/` | 対象へ配置する固定script・資産 | 各ファイル |
| `roles/*/templates/` | 変数展開して配置する設定・unit・script | 各template |
| `roles/*/handlers/` | 通知を受けて行うservice操作等 | 各handler |
| `docs/ai/prompts/*_policy.md` | 移行期間中のシステム別許可・禁止・停止条件 | 該当Policy |
| `playbooks/README.md` | 人間向けplaybookカタログと更新規則 | READMEと各playbookの現行実体 |

小さな処理はroleを作らずplaybook内tasksで完結する場合がある。逆に `common_slack` や `recovery_mute` のように、独立playbookではなく複数入口からtask単位で利用されるroleもある。

## 開発と本番実行の境界

```text
ansy: Issueに基づく開発・レビュー・検証・commit/push準備
  -> Git: Yoshinobuが確定したコードと文書の正本
  -> quory: working treeがcleanであることを確認後、確定済みGitを
            git pull --ff-onlyで取得し、本番実行
```

- commit、push、本番適用、restart、reboot、patch、migrationはYoshinobuの判断対象である。
- quoryでは原則としてコードを直接編集・commitしない。
- playbook自身にGit更新を行わせない。Git取得と対象ホストへのAnsible処理を分離する。
- Contextへ接続値や秘密を複製しない。値はinventory、vars、Vault等の秘密管理から実行時に解決する。

## 更新時の最小確認

- inventory groupや所属変更: `inventory-map.md` を更新する。
- playbook追加・改名・対象・role・処理種別・依存変更: `playbook-map.md` と `playbooks/README.md` を更新する。
- role追加・削除・責務・主要入出力変更: `role-map.md` を更新する。
- Policy追加・対象変更: playbook mapの関連Policyを更新する。
