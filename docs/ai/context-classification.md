# 情報分類の最小単位

`docs/ai/`配下の情報をどの分類へ置くかを決める。

## 1. 4分類の定義

### System Context(`docs/ai/context/system/`)

**対象**: 「このシステムが何であるか」— ノードの役割、依存関係、可用性、安全上の注意。Ansibleコードを読んでも分からない、実環境についての知識。

**例**: `overview.md`(全体概要)、`proxmox.md`/`radius.md`/`monitoring.md`/`semaphore.md`(対象領域別)。

**書かないもの**: IPアドレス・VLAN ID・VM ID・認証情報の実値(4節参照)、Ansibleの実装詳細(それはRepository Context)。

### Repository Context(`docs/ai/context/ansible/`)

**対象**: 「このリポジトリのAnsibleコードがどう構成されているか」— ディレクトリ構成、開発から本番実行までの流れ、対象ファイルへの辿り方。inventory group一覧・playbook一覧・role一覧そのものは複製せず、`inventories/homelab/hosts.yml`・`playbooks/*.yml`・`roles/*`を直接参照する。

**例**: `repository-overview.md`。

**書かないもの**: 個別playbook/roleの実装詳細そのもの(地図であって仕様書ではない。詳細はコードを読む)。

### Operations Context(`docs/ai/context/operations/`)

**対象**: 「複数のroleにまたがる、運用上の共通パターン・慣習」— System/Repository Contextのどちらにも収まらない、横断的な知識。

**例**: `healthcheck.md`(healthcheck系role共通のshell/Ansible責務分離、warning/critical二段階閾値の慣習、tester-gateマーカーと実guardの整合、reportの保存パターン、既知の落とし穴)。

**作成条件**: 単一role/単一領域に閉じない、繰り返し現れるパターンが見つかった時に作る。1回しか使わない知見はContextでなくレビュー記録(`docs/ai/reviews/`)や[[Knowledge]]に留める。

### Policy(`docs/ai/policies/`)

**対象**: 「何をしてよいか・してはいけないかの判断基準」— Context(事実)と違い、Policyは規範(ルール)。

**例**: `proxmox_operations_policy.md`、`ubuntu_vm_patch_policy.md`。

**Context/Policyの区別の原則**: 「これは何か」を答える文書はContext、「これをしてよいか」を答える文書はPolicy。例: 「proxmox-patch-dryrunは実patchを行わない」はContext(事実)、「dry-run結果でmust-fixが出た場合は本適用を止める」はPolicy(規範)。

## 2. コードから分かる情報と、文書化すべき情報の分離基準

次のいずれかに該当する情報だけをContext/Policyへ文書化する。該当しない情報は書かない(コードが正本のまま)。

- **複数ファイル・複数roleを横断しないと分からない**(例: どのplaybookがどのroleを使うか)。
- **実環境の知識でコードに現れない**(例: pve1とpve2の可用性の違い、sophos-fwのDNS挙動)。
- **繰り返し同じ調査が発生している**(例: 複数roleにまたがって発生したdf Use%意味論の誤り)。
- **判断基準そのもの**(Policy)。

該当しない例: 単一ファイルを読めば分かる実装詳細、1回限りの調査結果(→レビュー記録or Knowledgeへ)、変化の速い値(→3節参照)。

## 3. 実値を書かない情報の正本(秘密情報と変化の速い値)

### 3.1 IPアドレス・VLAN ID・VM ID・認証情報

正本はInventory(`inventories/homelab/hosts.yml`、`inventories/homelab/group_vars/`、`inventories/homelab/host_vars/`)・Ansible変数・秘密管理(Ansible Vault等)に限定する。System/Repository/Operations Context、Policy、Skillのいずれにも実値を書かない。既にリポジトリ規約として運用済みであり、本分類方針もこれに従う。

Context内で対象を指す必要がある場合は、inventory group名・変数名・ホスト役割名(「pve1」「quory」等の既に公開済みのホスト名は可、IPやVLAN IDは不可)で表現する。

### 3.2 変化の速い値

秘密情報でなくても、次の値の**実値**をContext・Policy・Skillへ書かない。値そのものではなく正本へのポインタを書く。

| 値の種類 | 正本 |
|---|---|
| 実行schedule、時刻、曜日、cadence | scheduler設定(systemd timer定義またはSemaphore UI)。UI設定はリポジトリ外で変化するため、リポジトリ内の記述は現在値を保証しない |
| ソフトウェアのバージョン、リリース番号 | 対象host上の実測値、またはrole defaults / vars |
| 件数、閾値、世代数、保持期間 | role defaults / vars |
| systemd unit名、timer名の一覧 | 該当roleのvars / templates |

**書き方**: 「毎日03:30にscheduleする」ではなく「日次で自動実行する。実値はscheduler設定を正本とする」と書く。過去値を記録する必要がある場合は、現在値と誤読されない形(「旧timer名、移行前の値」等の明示)にする。

## 4. ホスト名・構成情報をSkillへ書く例外条件

原則、ホスト名・構成情報はSkill(`~/.agents/skills/`配下の汎用スクリプト、および本リポジトリ`skills/`配下のプロジェクトSkill。いずれもホームラボ外・他プロジェクトで再利用されうるもの)へ書かない。以下の両方を満たす場合のみ例外とする。

1. その情報がなければSkillの動作自体が成立しない(例: 対象ホストを明示しないと安全に実行できないスクリプト)。
2. 既にpublic GitHub公開済みで、秘匿性のない情報である(IPアドレス・VLAN ID・認証情報は該当しない。ホスト名は個別に判断)。

例外を適用する場合は、そのSkillのコメントまたはREADMEに「ホームラボ固有の補足」である旨を明記し、汎用部分と分離する(委任Skill草案の「上流Skillを参照し、ホームラボ固有の補足だけ追加」方式と同じ考え方)。

## 5. 既存`docs/ai/reviews/`との関係

`docs/ai/reviews/`は**廃止・統合しない**。位置づけを次のように整理する。

| 種別 | 目的 | 更新頻度 | 例 |
|---|---|---|---|
| `docs/ai/context/`・`docs/ai/policies/` | **今**を答える生きた参照文書。各Roleが着手時に読む。 | 実態が変わったら更新 | `proxmox.md`、`repository-overview.md` |
| `docs/ai/reviews/<feature>/` | **その時**の作業記録・監査証跡(setup→implement→review→test_plan→test_result)。 | 案件ごとに追記、既存ファイルは基本上書きしない | `radius_healthcheck/<日付>_020_final.md` |
| `docs/ai/reviews/`直下の横断プロジェクトファイル | 個別案件をまたがる計画・進捗記録。 | プロジェクト進行に応じて更新 | 複数案件にまたがる計画ファイル |

**読む場面の違い**: 「このrole/システムは今どうなっているか」を知りたければContext/Policyを読む。「あの案件でなぜこの実装になったか」を知りたければ`reviews/<feature>/`を読む。Context作成時に元になった調査は`reviews/`に残したまま、Contextへは結論だけを転記してよい。

**将来の移行方針**: `reviews/`配下の記録のうちLesson/Decisionに該当するものをKnowledgeへ昇格させることはあるが、新設分類との共存が基本であり、既存フォルダを一括移行はしない。

## 6. Skillの配置とCodex/Claude Codeへの公開方法

**共通正本**: `skills/<skill-name>/SKILL.md`(リポジトリ直下)。CodexとClaude Codeで内容を二重管理しない。

**Claude Code側**: `.claude/skills/<skill-name>` から `skills/<skill-name>` への相対symlinkで公開する。Claude Codeは`.claude/skills/<name>/SKILL.md`をプロジェクトスコープで自動検出し、descriptionに基づき自動的に候補として提示する(実機のバイナリ文字列で`.claude/skills/<name>/SKILL.md`規約を確認済み)。

**Codex側**: Codexのネイティブ自動検出は`$CODEX_HOME/skills`(既定`~/.codex/skills`)というユーザーレベル・グローバルな場所のみを見る(`skill-creator`スキルの記載で確認済み)。プロジェクトスコープの自動検出機構が無いため、ホームラボ固有のSkillをそこへ配置すると他プロジェクトのCodexセッションからも見えてしまう(環境台帳化・目的外露出のリスク、2節参照)。このため、CodexへはAGENTS.md→`role-routing-index.md`→`docs/ai/roles/<role>.md`が既に採用している「明示参照」方式をSkillにも適用する。各Roleファイルの「必須Skill」欄に`skills/<name>/SKILL.md`への相対パスを明記し、自動検出には頼らない。

**環境情報混入検査**: `scripts/git-pre-commit-check.sh`の既存IPv4リテラルチェックは`*.md`全体に効いており、`skills/**/*.md`・`.claude/skills/**/*.md`(実体は同一ファイル)も自動的にカバーされる。VLAN ID・VM ID・ホスト名はパターン化しにくいため、4節の例外条件に基づきレビュー時に人手で確認する。

## 関連

- [[role-context-matrix.md]](誰がいつ何を読むか)
- `docs/ai/context/operations/healthcheck.md`(Operations Contextの先行実装)
