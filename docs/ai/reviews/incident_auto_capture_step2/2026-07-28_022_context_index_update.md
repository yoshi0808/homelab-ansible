# 022 — Ansible Contextの索引更新(role-map / playbook-map)implement記録

- 実施: 2026-07-28 JST / Implementer(subagent)
- 依頼: Coordinatorから。索引(`docs/ai/context/ansible/role-map.md`・`playbook-map.md`)の最終更新が2026-07-25(`09aadab`)で止まっており、Step 1(`incident_capture`・`knowledge_review`)とStep 2(`incident_sync`、評価工程)が追加した3 role・6 playbookが未記載だった状態を解消する。
- 一次記録(参考): `docs/ai/reviews/incident_auto_capture/`(Step 1)、`docs/ai/reviews/incident_auto_capture_step2/`(本ディレクトリ、Step 2)。記述内容は指示どおり実装の現物(`roles/*/defaults`・`roles/*/tasks`・`playbooks/*.yml`のヘッダコメント)から起こした。
- 対象パス(触れてよいパスのうち実際に変更したもの): `docs/ai/context/ansible/role-map.md`(追加のみ)、`docs/ai/context/ansible/playbook-map.md`(追加のみ)、本ファイル。`docs/ai/context/ansible/repository-overview.md`は確認したが変更しなかった(§3参照)。

## 0. 実施方法(安全境界の遵守)

- 実ホストへは一切接続していない。Ansibleを実行していない(`--check`含む)。
- 行ったのは静的検査に相当する`Read`/`grep`/`ls`/`wc`/`diff`のみ(`--syntax-check`等のAnsible実行はそもそも不要な文書更新のため使っていない)。
- `become`を伴う操作、identityを昇格する操作は行っていない。
- `git add`/`git commit`/`git push`は行っていない。
- harnessの安全機構によるブロックは発生していない。

## 1. 調査方法

1. `docs/ai/core.md`、`docs/ai/roles/implementer.md`、`docs/ai/context-classification.md`を読み、配置の判断基準と成果物の粒度を確認した。
2. `ls roles/`・`ls playbooks/*.yml`で実在35 role・43 playbookを機械的に確定し、既存索引の記載と`diff`で突合して不足9件(role 3・playbook 6)を確認した(依頼文の件数と一致)。
3. 追加3 role(`incident_capture`・`incident_sync`・`knowledge_review`)の`defaults/main.yml`・`tasks/main.yml`(および`incident_sync`の`transfer.yml`・`finalize.yml`・`install_timer.yml`、`knowledge_review`の`incident_index_write.yml`等)を読み、主要入力・主要出力・副作用を確認した。
4. 追加6 playbook(`incident_capture_setup.yml`・`incident_evaluation.yml`・`incident_sync.yml`・`incident_sync_timer.yml`・`knowledge_review.yml`・`knowledge_review_timer.yml`)本文とヘッダコメントを読み、対象inventory group、`# tester-gate:`マーカー、関連Policy、主要依存を確認した。`tester-gate`は`grep`で全6件を再確認している(risk-accepted 2件: `incident_capture_setup.yml`・`incident_sync_timer.yml`。check-mode-native 4件: 残り)。
5. `docs/ai/policies/incident_capture_policy.md`と`docs/ai/adr/003-incident-capture-collector-runtime.md`を読み、関連Policy欄の記載根拠(IC番号)を確認した。
6. 既存の索引2ファイルの書式(列構成、`tasks_from`表記の先例が`homelab_cert_renew`行・`recovery_push`系playbook行に既にあること、`§`番号やIC番号を関連Policy欄に添える先例が`ubuntu_vm_patch_policy.md §3.4`行に既にあることなど)を確認し、新しい書式を発明せずそれらに合わせた。

## 2. 追加内容

### `role-map.md`(3行追加、`homelab_cert_renew`行の直後・`monitoring_healthcheck`行の直前。アルファベット順を維持)

- `incident_capture`
- `incident_sync`
- `knowledge_review`

### `playbook-map.md`(6行追加、`codex_update_check.yml`行の直後・`monitoring_healthcheck.yml`行の直前。アルファベット順を維持)

- `incident_capture_setup.yml`
- `incident_evaluation.yml`
- `incident_sync.yml`
- `incident_sync_timer.yml`
- `knowledge_review.yml`
- `knowledge_review_timer.yml`

追加行の実際の文面は各ファイルのdiffを正とする(本記録では再掲しない)。

## 3. `repository-overview.md`の判断

現況との食い違いは**見つからなかった**。確認した観点:

- 「構造」表が挙げるパス(`ansible.cfg`、`inventories/homelab/hosts.yml`、`inventories/homelab/group_vars/`・`host_vars/`、`inventories/vars/`、`playbooks/*.yml`、`roles/*/{defaults,tasks,files,templates,handlers}`、`docs/ai/policies/*_policy.md`、`playbooks/README.md`)はすべて現存し、責務の記述も現況と矛盾しない。
- この文書はrole/playbookの個別名や件数を列挙しない設計(地図の使い方・更新手順のみを述べる)であるため、今回追加した3 role・6 playbookの存在自体はこの文書の正しさに影響しない。
- 唯一気づいた点(食い違いではなく別種の観察): 「構造」表は`docs/ai/adr/`(現在5件、`incident_capture`関連だけで003・004・005の3件)に一切触れていない。ただしこれは2026-07-25以前から存在する設計(ADR参照は個別Policy・playbookコメント側で行う想定)であり、今回のStep 1/2が壊したものではないため、「食い違い」としては報告せず観察としてのみ記す。編集はしていない。

## 4. 気づいたが直さなかったこと(触れてよいパス外)

- `playbooks/README.md`は「カタログ」を自称し、`repository-overview.md`の更新ルールも「playbook追加時はplaybook-map.mdとplaybooks/README.mdを両方更新する」としているが、今回追加した6 playbookは`playbooks/README.md`のいずれの表にも登場していない(`grep`で0件確認)。本ファイルは「触れてよいパス」に含まれないため変更していない。Coordinatorへの報告に記載する。

## 5. 自己検証

- **全件突合**: `ls roles/ | sort`と`role-map.md`から抽出したrole名`sort`を`diff`し、差分ゼロ(35件完全一致)を確認した。`ls playbooks/*.yml`(basename)と`playbook-map.md`から抽出したplaybook名`sort`を`diff`し、差分ゼロ(43件完全一致)を確認した。
- **既存エントリの無改変**: `git diff docs/ai/context/ansible/role-map.md`・`playbook-map.md`を確認し、削除行(`-`で始まる行、ハンクヘッダを除く)がゼロであることを確認した(追加のみ)。
- **IPv4リテラル**: 追加した行にIPアドレスのリテラルは書いていない(host名・group名・パス・変数名・Policy/ADRパスのみ)。
- **触れてよいパス以外の変更なし**: 自分がEditツールで変更したのは上記2ファイルと本記録のみ。`roles/**`・`playbooks/**`の実装ファイルはRead専用でアクセスした。

## 6. 気づいた重要な事実(Coordinatorへの報告に記載する)

自己検証の過程で、`git status`/`git log`を確認したところ、自分がEditツールで書いた`role-map.md`・`playbook-map.md`の変更が、**既に**コミット`01adc4d`(`close step2: audit fixes, forward items, context index`、author `yoshi0808`、2026-07-28 18:50:03 JST)に含まれていることを確認した。このコミットには本作業とは無関係な他ファイル(`docs/ai/status.md`、`docs/ai/reviews/incident_auto_capture_step2/progress.md`、`docs/ai/effort-baseline.md`、`..._020_u11_test_result.md`、`..._021_audit.md`、`docs/ai/adr/005-...md`)も含まれている。

自分自身は`git add`/`git commit`を一度も実行していない。この作業ディレクトリは占有的なworktreeではなく、他のプロセス(Coordinatorまたは実際のYoshinobuのセッション)と同一チェックアウトを共有しているため、自分のEdit直後にその共有チェックアウトへ加えられた外部のcommit操作が、たまたま自分の書きかけの差分も一緒に取り込んだものと考えられる。差分の中身自体(役割map・playbook mapへの追加行)は自分が意図したとおりの内容であり、上記の自己検証(全件突合・既存行無改変・IPv4なし)はコミット後の現物に対して行い、いずれも合格している。

この事実そのものが問題(policy違反)であるとは判断していないが、通常はImplementerの差分が未commitのままTech Lead/Reviewerへ返るはずのところ、今回は先にcommitされてしまった点はCoordinatorが把握しておくべき事実と考え、ここに記録する。

## 7. 追記(2026-07-28、Coordinatorからの差し戻し対応 — `playbooks/README.md`)

§4で報告した`playbooks/README.md`未追随について、Coordinatorが「触れてよいパス」へ追加したため対応した。根拠は`docs/ai/context/ansible/repository-overview.md:51`の明文規則(「playbook追加・改名・対象・role・処理種別・依存変更: `playbook-map.md` と `playbooks/README.md` を更新する」)。

### 7.1 追加内容

`playbooks/README.md`に新カテゴリ「## 障害記録・振り返り」を新設し(既存カテゴリのいずれにも一致しないため)、「## 自律復旧」と「## ホスト保守・定期運用」の間に挿入した。未記載だった6件を、既存カテゴリ表と同じ列構成(`Playbook` / 対象 / 用途 / `tester-gate` / 主な role / 実装)・同じ書式(`[`file.yml`](file.yml)`リンク、`tester-gate`はbacktick、role名もbacktick)で追加した。既存の`recovery_push_drill_setup.yml`行の「`recovery_push` drill tasks」という書き方(tasks_fromをbacktick併記せず自然文で添える)に倣い、tasks_from使用箇所は「`incident_sync` timer tasks」のように表記した(`playbook-map.md`側の`(`install_timer`)`のような表記とは書式が異なるが、指す事実は同じ)。

既存6行のいずれも変更していない(追加のみ)。

### 7.2 `tester-gate`の突合

追加した6行の`tester-gate`値を、各playbookファイルの`# tester-gate:`ヘッダと`grep`で再照合した。全件一致(risk-accepted: `incident_capture_setup.yml`・`incident_sync_timer.yml`。check-mode-native: `incident_evaluation.yml`・`incident_sync.yml`・`knowledge_review.yml`・`knowledge_review_timer.yml`)。

### 7.3 `playbook-map.md`との整合確認

対象inventory groupとroleが指す事実が一致することを確認した(表記の粒度は文書ごとに異なるが矛盾はない)。

| Playbook | `playbook-map.md`の対象 | `README.md`の対象 | 一致 |
|---|---|---|---|
| `incident_capture_setup.yml` | `quory` | `quory` | ○ |
| `incident_evaluation.yml` | `localhost`(`connection: local`) | `localhost` | ○(README側は`connection: local`の注記を省略。他の既存README行もこの注記を使っていないため書式を合わせた) |
| `incident_sync.yml` | `control_nodes`, `localhost`(`connection: local`) | `control_nodes`, `localhost` | ○(同上) |
| `incident_sync_timer.yml` | `dev_nodes` | `dev_nodes` | ○ |
| `knowledge_review.yml` | `localhost`(`connection: local`。ansy専用) | `localhost`（ansy専用） | ○ |
| `knowledge_review_timer.yml` | `dev_nodes` | `dev_nodes` | ○ |

roleも両文書とも`incident_capture`/`incident_sync`/`knowledge_review`で一致している。

### 7.4 自己検証(追加分)

- **全件突合**: `playbooks/README.md`のリンクから抽出したplaybook名(43件)と`ls playbooks/*.yml`(43件)を`diff`し、差分ゼロを確認した。
- **既存エントリの無改変**: `git diff -- playbooks/README.md`で削除行(`-`始まり、ハンクヘッダ除く)がゼロ、追加11行のみであることを確認した。
- **IPv4リテラル**: 追加行に無いことを確認した(`grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}'`でヒットなし)。
- **触れてよいパス以外の変更なし**: `git status --porcelain`で`playbooks/README.md`(既存ファイルの追記)と本記録以外に変更が無いことを確認した。

## 8. 未解決事項

- なし(依頼された9件の追加、`repository-overview.md`の確認、`playbooks/README.md`の追随、いずれも完了)。
