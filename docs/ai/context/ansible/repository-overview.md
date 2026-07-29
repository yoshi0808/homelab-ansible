# Ansible Repository Overview

この文書は、新しいIssueから対象のinventory、playbook、role、Policy候補へ進むための入口である。詳細仕様や変化する値は複製せず、現行コードを正本とする。

## 正本の使い方

**2026-07-29、`inventory-map.md` / `playbook-map.md` / `role-map.md` を廃止した。** 手動更新の索引は現物との乖離が繰り返し発生し(`docs/ai/reviews/process_retrospective/2026-07-29_006_ansible_context_map_retirement.md`)、古い索引を信じて見落とす方が索引なしで現物を確認するより危険と判断したため、要約の地図を持たず現行ファイルへ直接あたる運用へ一本化した。

1. 対象ホストまたはgroupは `inventories/homelab/hosts.yml` を確認する。
2. 対象playbookの実行入口・対象範囲は `playbooks/*.yml` と `playbooks/README.md` を確認する。安全区分は各playbook先頭の `# tester-gate:` が正本である。
3. 対象roleの処理本体・主要入力・副作用は `roles/<role>/tasks/`・`roles/<role>/defaults/` を直接確認する。利用元(どのplaybookがどのroleを呼ぶか)は `grep -rl '<role名>' playbooks/` で特定する。
4. 実装判断は対象ファイル、現在のdiff、関連Policyを読んで確定する。

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
| `docs/ai/policies/*_policy.md` | システム別許可・禁止・停止条件 | 該当Policy |
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

- playbook追加・改名・対象・role・処理種別・依存変更: `playbooks/README.md` を更新する。
- Policy追加・対象変更: 対象playbookのヘッダコメントまたは `playbooks/README.md` から参照できるようにする。
