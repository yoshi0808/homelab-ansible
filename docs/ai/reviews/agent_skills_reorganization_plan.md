# homelab-ansible AI Agent / Skills 再構成計画

## 1. この計画の目的

現在の `homelab-ansible` では、`techlead`、`implementer`、`reviewer`、`tester` の各AIが、`agmsg` を使ってメッセージを受け渡しながら継続的にAnsibleを改善している。

AIはSSHログイン後に `new-session.sh` からtmux上へ起動され、次のように `agmsg` のidentityを与えられる。

```bash
/agmsg actas reviewer
/agmsg actas implementer
/agmsg actas tester
/agmsg actas techlead2
```

`agmsg` はAgent Skillとしてインストールされ、Shellスクリプト群とSQLiteを使って、AI間のメッセージ配送、identity登録、monitorモードによる受信を行う。

一方、現在の `core.md`(`docs/ai/prompts/core.md`)は、以下が一つのファイルに集約されている。

> **2026-07-21実測による訂正**: 本計画の初版では `core.md` を約755行、`agmsg` を約500行と概算していたが、実測では `core.md` は**1253行**(18セクション)、`new-session.sh` は218行、`prep-agent.sh` は87行だった。`agmsg` のShellスクリプトは、インストール済み`~/.agents/skills/agmsg/scripts/`配下(74ファイル)で**10,028行**、実際に使うドライバ(claude-code + codex)・`lib`・`internal`・トップレベル(56ファイル)に限定して**9,044行**、ソースclone(`~/agmsg`、58ファイル)で**7,838行**である。10,028行はSkillルート全体ではなく`scripts/`配下だけの値であり、ルート直下の`uninstall.sh`は含めない。初版および中間訂正の「約5200行」は前提として使わず、Phase 0 TODO 0-1はこの実測値を起点にする。この乖離自体が、後述の課題5・6(前提を確認せず記述すると古い数値が独り歩きする)の実例である。

- プロジェクトの目的
- オンプレ環境の構成
- Ansibleリポジトリの構成
- 実装ルール
- 運用ポリシー
- AIの役割と連携方法
- レビュー・テスト手順
- 禁止事項
- 過去から積み上げた判断

この状態には、次の課題がある。

1. 全AIが毎回、担当に不要な情報まで読む。
2. 重要な共通原則が詳細情報に埋もれる。
3. 役割ごとの責任が暗黙的で、identity名からAIが推測している。
4. 一般的なAnsible実装・レビュー・テストの知識まで独自に抱えている。
5. 過去のミスをMemoryへ追加し続けると、情報が増え、古い教訓や一時的な事象が恒久ルール化する可能性がある。
6. `new-session.sh` が今後どこまで初期化を担うべきかが決まっていない。

本計画の目的は、AIが担当業務に必要な情報とSkillだけを利用し、現在よりも少ないコンテキストで、高い品質と安全性を維持できる構成へ移行することである。

---

## 2. 目指す状態

各情報の責務を次のように分ける。

| 要素 | 答える質問 | 内容 |
|---|---|---|
| `core.md` | 全員が絶対に守ることは何か | プロジェクトの目的、共通原則、安全境界、正本の位置づけ |
| Role定義 | 自分は誰で、何を判断するのか | techlead / implementer / reviewer / tester の責務、権限、成果物 |
| Context | この環境やリポジトリはどうなっているか | オンプレ構成、Ansible構造、playbook・role・inventoryの関係 |
| Policy | 特定業務で何を許可・禁止するか | パッチ、再起動、通知、秘密情報などの運用判断 |
| Skill | 仕事をどう進めるか | 要件整理、実装、レビュー、テスト、調査などの再利用可能な手順 |
| Knowledge(`docs/ai/memory/`) | プロジェクト全体で共有すべき知識は何か | Codex系Roleの判断にも関わるIncident、Lesson、Decision、Temporaryな作業情報(Claude Code固有のMemoryとは別物。詳細はPhase 6 TODO 6-0) |
| Issue | 今回何を実現するか | 要求、範囲、受入条件、対象Context(GitHub Issueは当面使わない。agmsgの依頼メッセージと`docs/ai/reviews/`配下の該当フォルダが実体を兼ねる) |
| PR / diff | 何が変更されたか | 実装差分、レビュー指摘、テスト結果 |
| `agmsg` | 誰とどう連絡するか | identity、送受信、monitor、AI間の作業引き継ぎ |

全体の関係は次のとおり。

```text
agmsg actas <identity>
        ↓
identityに対応するRoleを解決
        ↓
core.mdの共通原則を確認
        ↓
Roleが必要とするSkillとContextを選択
        ↓
Issue / PR / メッセージに基づいて作業
        ↓
結果・判断・未解決事項をagmsgで引き継ぐ
        ↓
必要な学びだけをKnowledgeへ記録
```

---

## 3. 基本方針

### 3.1 `core.md` は起動規約にする

`core.md` は詳細手順書ではなく、全AIが短時間で読める「プロジェクト共通の起動規約」にする。

目安は100〜200行以内とし、理想的にはさらに短くする。

### 3.2 役割と能力を分ける

- Roleは「誰として、何を判断するか」を定義する。
- Skillは「その仕事をどう行うか」を定義する。
- `reviewer` というidentity名だけから、責務や権限をAIに推測させない。

### 3.3 全員に全体構成を読ませない

Tech Leadは全体構成を理解する。

Implementer、Reviewer、Testerは、全体の概要と担当対象に必要な構成だけを読む。担当に関係しない詳細情報は読まない。

### 3.4 公開Skillを基礎にする

Ansible実装、コードレビュー、テスト設計、要件分解などの一般能力は、一から独自設計しない。

信頼できる公開Skillを調査し、次のいずれかで利用する。

- そのまま使用
- 上流Skillを参照し、ホームラボ固有の補足だけ追加
- 必要部分のみ派生Skillへ取り込む

### 3.5 Knowledgeをルールのゴミ箱にしない

ミスが発生したとき、直ちに `core.md` やRole Skillへ恒久ルールとして追加しない。

```text
ミス
  ↓
Incidentとして記録
  ↓
原因・再発可能性を整理
  ↓
再利用可能ならLessonへ昇格
  ↓
作業手順ならSkillへ反映
  ↓
全員共通の不変原則だけcore.mdへ反映
```

### 3.6 起動スクリプトの変更は最後に行う

`new-session.sh` はすでにtmux、AI起動、agmsg identity、monitor、複数Agentの配置を担っている。

Role、Skill、Contextの構造が決まる前に変更すると、設計変更のたびに起動処理を直すことになる。そのため、最終構成が固まってから変更する。

### 3.7 Codex・Claude Codeの入口とSkillの正本を分ける

プロジェクト共通原則の実体は `docs/ai/core.md` を正本とし、各AI製品が自動認識する入口ファイルは薄く保つ。

| 用途 | Codex | Claude Code | 共通正本 |
|---|---|---|---|
| プロジェクト常設指示 | `AGENTS.md` | `CLAUDE.md` | `docs/ai/core.md` |
| 再利用可能な作業能力 | `SKILL.md` | `SKILL.md` | リポジトリ内の共通Skillソース |

`AGENTS.md` と `CLAUDE.md` へ共通原則を二重記載しない。両ファイルには、共通正本、Role定義、現在のIssue、適用対象Skillを確認する入口だけを書く。

Skillは `skills.md` という単一ファイルではなく、Skillごとのディレクトリに置く `SKILL.md` を基本単位とする。CodexとClaude Codeで探索場所や呼び出し方法が異なる場合でも、Skill本文の正本は一か所とし、必要に応じてsymlinkまたは同期処理で各製品の探索場所へ公開する。

```text
homelab-ansible/
├── AGENTS.md
├── CLAUDE.md
├── docs/ai/core.md
└── skills/
    ├── ansible-techlead/SKILL.md
    ├── ansible-implementer/SKILL.md
    ├── ansible-reviewer/SKILL.md
    └── ansible-tester/SKILL.md
```

また、Skillを環境台帳にしない。

- IPアドレス、認証情報、VLAN ID、VM IDなどの具体的な環境識別情報はSkillへ記載しない。
- ホスト名、物理・仮想配置、ネットワーク構成も、再利用可能な作業手順に不可欠な場合を除きSkillへ記載しない。
- 環境固有情報はInventory、変数、Context、Policy、Issueから解決する。
- Skillには「どの情報を、どこから取得し、どう判断するか」を記載する。

これにより、SkillをCodexとClaude Codeで共有しやすくし、環境変更による陳腐化や構成情報の不要な複製を防ぐ。

### 3.8 低難度作業はCodex中心に配分する(2026-07-21合意)

Tech Lead(Claude Code)はコストの高いモデルであるため、本計画の実行そのものをTech Leadが抱え込まない。

- **設計判断**(何を残すか、Role/identityの意味付け、Knowledgeの分類基準など)はTech Leadが行う。
- **機械的な棚卸し・調査・草案作成**(現行ファイルの見出し一覧化、移行表の下書き、公開Skillの一次スクリーニングなど)は、難易度が低ければCodex側(implementer/reviewer/tester)へ委任する。
- 各PhaseのTODOへ着手する際、Tech Leadはまず「これは設計判断か、それとも調査・作業か」を仕分けてから割り当てる。

---

# 4. 実施ToDo

## Phase 0: 現状を基準化する

### TODO 0-1: 現行ファイルの正本を確定する

- [x] 現在利用中の `core.md` のパスと最新版を確認する。→ `docs/ai/prompts/core.md`、2026-07-21実測で1253行・18セクション。
- [x] 現在利用中の `new-session.sh` と `prep-agent.sh` の最新版を確認する。→ リポジトリ直下、それぞれ218行・87行。
- [x] `agmsg` のインストール場所、バージョン、`SKILL.md`、主要Shellを確認する。→ 稼働コピーは `~/.agents/skills/agmsg` v1.1.10。インストール済み`scripts/`配下74ファイル・10,028行、実使用範囲56ファイル・9,044行、ソースclone 58ファイル・7,838行。ソース(`~/agmsg`)と稼働コピーはversion、`SKILL.md`、主要scriptが異なり、自動同期されない。再現コマンドと差分はPhase 0現状基準に記録済み。
- [x] AIのMemory/Knowledgeがどこに、どの形式で保存されているか確認する。→ Claude Memoryは `~/.claude/projects/.../memory/`(`feedback` / `project` / `reference`型)。Codex側・リポジトリ内には現時点で共通Knowledge相当のディレクトリは存在しない。詳細な整理はPhase 6で行う。
- [x] 現在のRoleごとの実際の作業フローを一度記録する。→ Phase 0現状基準にscript実装済みboot経路、合意済みtrio routing、両者の未移行差分を記録済み。

**この作業を行う意味**

複数の旧ファイルやバックアップを基準に設計すると、使われていない運用を移行対象に含めたり、現行機能を落としたりする。最初に「現在実際に動いているもの」を基準として固定する必要がある。

**成果物**

- 現行ファイル一覧
- 各ファイルの正本パス
- 現在の起動・通信・作業フロー図

**完了条件**

第三者が一覧を見て、どのファイルを調査・変更すべきか迷わない。

---

## Phase 1: `core.md` の役割を確定する

### TODO 1-1: `core.md` に残す条件を定義する

- [x] 全Roleが必ず必要とする情報か確認する。
- [x] プロジェクト固有の不変原則か確認する。
- [x] Issue、Context、Policy、Skill、Knowledgeへ置く方が適切でないか確認する。
- [x] 頻繁に変化する情報を `core.md` から除外する。

**この作業を行う意味**

単に文章を短くするだけでは、必要な情報を削除するだけになる。何を残すかの判断基準を先に決めることで、今後も `core.md` が再び肥大化するのを防ぐ。

**`core.md` に残す候補**

- リポジトリの目的
- Yoshinobuが最終判断者であること
- Git、Issue、PR、Policyの正本関係
- ansyは開発、quoryは本番実行という共通原則
- 秘密情報を扱わない共通安全原則
- Role / Skill / Context / Knowledgeの参照方法
- AI間連携にagmsgを使うこと
- 不明点や安全上の懸念を黙って推測しないこと

**完了条件**

「この情報はなぜ全員が毎回読む必要があるのか」を各項目について説明できる。

### TODO 1-2: 現行 `core.md` の全項目を棚卸しする

- [x] 現行見出しと主要ルールを一覧化する。
- [x] 各項目を次の分類へ割り当てる。

| 分類 | 移動先 |
|---|---|
| 全員共通の不変原則 | `core.md` |
| 役割固有の責務・権限 | Role定義 |
| オンプレ環境の事実 | System Context |
| Ansibleリポジトリの構造 | Repository Context |
| 個別運用の判断基準 | Policy |
| 一般的な作業手順 | 公開Skillまたは派生Skill |
| 過去のミス・教訓 | Knowledge |
| 特定案件だけの要求 | Issue |
| 現在の変更内容 | PR / diff |
| 重複または古い説明 | 削除 |

**この作業を行う意味**

`core.md` を直接編集し始めると、削除した情報の移動先が分からなくなる。移行表を先に作ることで、情報を失わず、重複も防げる。

**成果物**

`core-migration-map.md` 相当の移行表。

例：

| 現行内容 | 判断 | 移動先 | 理由 |
|---|---|---|---|
| 主要ノードと役割 | 移動 | `context/system/overview.md` | 環境情報であり全Roleの不変原則ではない |
| Shellは収集とJSON整形のみ | 要検討 | `core.md` またはAnsible Policy | プロジェクト固有の重要設計原則 |
| Reviewerの確認手順 | 移動 | Reviewer Role / Review Skill | 役割固有 |
| 秘密鍵を表示しない | 残す | `core.md` | 全Role共通の安全境界 |

**完了条件**

現行 `core.md` の主要項目すべてに、残す・移す・削除の判断が付いている。

### TODO 1-3: 短い `core.md` の草案を作る

- [x] 移行表に基づいて草案を作る。
- [x] 詳細なコマンド例や長い構成表を置かない。
- [x] 他ファイルへの参照方法を明記する。
- [x] 全Roleで読ませ、共通原則に不足がないか確認する。

**この作業を行う意味**

新しい情報構造の中心を先に作ることで、RoleやSkillを設計するときに共通部分を重複して書かずに済む。

**完了条件**

- 100〜200行以内を目安とする。
- 役割別手順、環境詳細、個別ポリシーが混在していない。
- 全Roleが毎回読む価値のある内容だけになっている。

### TODO 1-4: `AGENTS.md`・`CLAUDE.md`・共通正本の関係を確定する

- [x] `docs/ai/core.md` を共通原則の正本にする。
- [x] Codex向け `AGENTS.md` を薄い入口として作る。
- [x] Claude Code向け `CLAUDE.md` を薄い入口として作る。
- [x] 両ファイルから参照するRole、Context、Skillの選択ルールをそろえる。
- [x] 共通内容を `AGENTS.md` と `CLAUDE.md` に複製しない。

**この作業を行う意味**

CodexとClaude Codeは常設指示として認識するファイル名が異なる。共通内容をそれぞれへコピーすると更新漏れが起きるため、製品別ファイルは入口、`docs/ai/core.md` は正本という関係を明確にする。

**成果物**

- `AGENTS.md`
- `CLAUDE.md`
- 両者が参照する短い `docs/ai/core.md`
- どのファイルが正本かを示す説明

**完了条件**

- 共通原則を変更するとき、原則として一か所だけ編集すればよい。
- CodexとClaude Codeの双方が、同じ共通原則とRole選択規則へ到達できる。
- `AGENTS.md` と `CLAUDE.md` に環境詳細や役割別手順が重複していない。

---

## Phase 2: 環境・Ansible・運用情報を分類する

### TODO 2-1: 情報分類の最小単位を決める

- [ ] System Contextを定義する。
- [ ] Repository Contextを定義する。
- [ ] Operations Contextを定義する。
- [ ] Policyを定義する。
- [ ] コードを見れば分かる情報と、文書化すべき情報を分ける。
- [ ] IPアドレス、VLAN ID、VM ID、認証情報の正本をInventory・変数・秘密管理へ限定する。
- [ ] ホスト名や構成情報をSkillへ書く必要がある条件を例外として定義する。
- [ ] 既存の `docs/ai/reviews/`(機能別フォルダ35件超)と、新設するIssue/Context/Policyの関係を整理する(廃止・統合はせず、位置づけを明記するだけでよい)。

**この作業を行う意味**

細かく分けすぎると、AIが大量のファイルを探す必要がある。大きくまとめすぎると、再び不要な情報を読む。適切な粒度を決める必要がある。

**推奨分類**

```text
docs/ai/
├── core.md
├── context/
│   ├── system/
│   │   ├── overview.md
│   │   ├── proxmox.md
│   │   ├── radius.md
│   │   ├── monitoring.md
│   │   └── semaphore.md
│   ├── ansible/
│   │   ├── repository-overview.md
│   │   ├── inventory-map.md
│   │   ├── playbook-map.md
│   │   └── role-map.md
│   └── operations/
│       ├── patching.md
│       ├── healthcheck.md
│       └── notification.md
├── policies/
│   ├── proxmox_patch_policy.md
│   └── ubuntu_vm_patch_policy.md
├── roles/
└── memory/
```

これは初期案であり、既存ファイルとの重複を確認してから確定する。

**完了条件**

新しい情報を追加するとき、どの分類へ置くか迷わない。

### TODO 2-2: System Contextを作る

- [ ] 全体概要を短くまとめる。
- [ ] Proxmox、RADIUS、監視、Semaphoreなど対象領域別に分ける。
- [ ] ノードの役割、依存関係、可用性、安全上の注意を記録する。
- [ ] 変化しやすい値を固定文章へ埋め込みすぎない。

**この作業を行う意味**

Tech Lead、Reviewer、Testerが、コードだけでは判断できない実環境への影響を理解するために必要である。一方、対象外の構成まで毎回読ませないため、領域別に分ける。

**完了条件**

- Tech Leadが全体構成と主要な依存関係を説明できる。
- 他Roleは対象領域のContextだけで、安全性と影響範囲を判断できる。

### TODO 2-3: Ansible Repository Contextを作る

- [ ] inventory groupと対象ホストの関係を整理する。
- [ ] playbookの目的、対象、変更系／read-only、利用roleを一覧化する。
- [ ] roleの目的と主要な入出力を一覧化する。
- [ ] 開発からquory本番実行までの流れを整理する。

**この作業を行う意味**

AIが毎回リポジトリ全体を探索し直す負担を減らし、類似実装や影響先を見落としにくくする。

ただし、コードの詳細仕様を重複して書くと陳腐化する。そのため、地図として必要な情報だけを記載する。

**playbook-mapに含める候補**

| 項目 | 内容 |
|---|---|
| Playbook名 | 実行入口 |
| 目的 | 何を実現するか |
| 対象inventory group | どこへ実行するか |
| 主なrole | どの処理を利用するか |
| 種別 | read-only / change / patch / reboot |
| 関連Policy | どの判断基準を使うか |
| 主要依存 | 前後に必要な処理 |

**完了条件**

新しいIssueを受けたTech Leadが、対象playbook・role・inventory・Policy候補を短時間で特定できる。

### TODO 2-4: Role別Contextマトリクスを確定する

- [ ] 各Roleが起動時に必ず読む情報を決める。
- [ ] 作業開始時に読む情報を決める。
- [ ] 必要時だけ読む情報を決める。
- [ ] 読まなくてよい情報を明確にする。

**この作業を行う意味**

全員に全情報を読ませないための中心的な設計である。情報不足を防ぎながら、コンテキスト量を抑える。

**初期マトリクス案**

| 情報 | Tech Lead | Implementer | Reviewer | Tester |
|---|---:|---:|---:|---:|
| `core.md` | 必須 | 必須 | 必須 | 必須 |
| System overview | 詳細 | 概要または必要時 | 概要または必要時 | 概要または必要時 |
| 対象System Context | 詳細 | 詳細 | 詳細 | 詳細 |
| Ansible全体構成 | 詳細 | 概要 | 概要〜詳細 | 概要 |
| 対象playbook / role | 概要 | 詳細 | 詳細 | 詳細 |
| Issue / 受入条件 | 詳細 | 詳細 | 詳細 | 詳細 |
| PR / diff | 必要時 | 自分の実装 | 詳細 | 詳細 |
| 実環境の期待状態 | 詳細 | 必要範囲 | 必要範囲 | 詳細 |
| Policy | 対象分野 | 対象分野 | 対象分野 | 対象分野 |
| Knowledge | 重要Decision | 対象関連 | 対象関連 | 対象関連 |

**判断の原則**

- Tech Leadは全体像を理解し、必要Contextを選ぶ。
- Implementerは対象機能と接続部分を深く理解する。
- Reviewerは要件・差分・影響する構成を理解する。
- Testerは対象構成・依存関係・期待状態・安全な検証範囲を理解する。
- Tech LeadのContext指定に不足があれば、各Roleは追加調査する。

**完了条件**

各Roleについて、「なぜこの情報が必要か」と「なぜ他の情報は不要か」を説明できる。

---

## Phase 3: Role定義を設計する

### TODO 3-1: identityとRoleを分離する

- [ ] `reviewer2`、`implementer2`、`tester2`、`techlead2` のidentityとRoleの対応を定義する。
- [ ] identity名からRoleを暗黙推論しない構成を決める。
- [ ] 対応表をどこに置くか決める。

**この作業を行う意味**

`reviewer2` は通信上の宛先であり、仕事の内容は `reviewer` と同じである。これを分けないと、席を増やすたびにRole定義やSkillを複製することになる。

**初期対応案**

| Identity | Role |
|---|---|
| `claude` | coordinator |
| `techlead`, `techlead2` | techlead |
| `reviewer`, `reviewer2` | reviewer |
| `implementer`, `implementer2` | implementer |
| `tester`, `tester2` | tester |

`claude` の正式Roleは、現在の要件整理・ハブ・引き継ぎ責務を確認して決める。

> **2026-07-21 訂正**: 当初、`techlead`(Claude Code)と`techlead2`(Codex)は起動チャネルの違い(tmux常駐 / ネイティブアプリ)により異なる特性を持つ別席として扱うべきか保留としていたが、Yoshinobuさんに確認したところ誤解だった。実態は次の通りで、Role設計上の論点ではない。
>
> - Codexベースのidentity(`implementer`/`implementer2`/`reviewer`/`reviewer2`/`tester`/`tester2`/`techlead2`)はいずれもtmuxペイン上で稼働し、Yoshinobuさんがスマホ等からそのペインへアタッチして直接やり取りする。
> - Claude Codeベースのidentity(`claude`/`techlead`)はtmuxペインの外からagmsg経由で参加する。
>
> この違いはCodexとClaude Codeそれぞれのプロダクト仕様に起因するものであり、Yoshinobuさんが選択・コントロールできる設計判断ではない。したがって`techlead`/`techlead2`も他のペア(`reviewer`/`reviewer2`等)と同様に、各identityから単一Roleへ一意に対応すればよく、保留は解除する。複数identityが同じRoleを共有するため、対応関係全体は多対1である。

**trio専属の運用規則**

- `techlead` は無印trio (`implementer` / `reviewer` / `tester`)へ直接指示し、その報告を受ける。
- `techlead2` は2付きtrio (`implementer2` / `reviewer2` / `tester2`)へ直接指示し、その報告を受ける。
- Tech Leadが他方のtrioへ直接指示することは通常運用では行わない。trio間の移管、応援、担当変更が必要な場合は、担当Tech Lead同士またはCoordinatorを介して明示的に合意し、agmsg上で新しい指揮系統を通知する。
- この規則は通信identityの指揮系統を定めるものであり、Role定義やSkillを無印用・2付き用に複製するものではない。

**完了条件**

AIがidentity登録後、機械的かつ一意にRoleを解決できる。

### TODO 3-2: 各Roleの判断責任を定義する

- [ ] Coordinator(`claude`)の責任、権限、成果物を定義する。
- [ ] Tech Leadの責任、権限、成果物を定義する。
- [ ] Implementerの責任、権限、成果物を定義する。
- [ ] Reviewerの責任、権限、成果物を定義する。
- [ ] Testerの責任、権限、成果物を定義する。
- [ ] Role間の引き継ぎ条件を定義する。
- [ ] trio間の移管で、Coordinatorが仲介するのか割当を変更できるのか、旧ownerの停止、新ownerの通知、進行中成果物の返却先を定義する。
- [ ] requirement / implement / review / test_result / Tech Lead統合結果の返却先と、Coordinator差戻し時の再指示経路を定義する。

**この作業を行う意味**

Role Skillへ詳細手順を書く前に、誰が何を決めるかを固定する必要がある。これが曖昧だと、複数AIが同じ作業をしたり、誰も最終確認しなかったりする。

**初期責務案**

#### Coordinator(`claude`)(2026-07-21、Yoshinobuとの合意に基づき追加)

- Yoshinobuの壁打ち相手として要求を明確化し、案件をTech Lead(`techlead`または`techlead2`)へ振り分ける。
- Tech Leadと(必要ならCodex側のTech Lead席とも)協議して決定された内容を検討する。
- 検討結果をYoshinobuへアドバイスとして伝える(単なる清書・記録ではなく、内容の妥当性を評価する)。
- Claude Memory(Claude Code固有の経験・運用知識)を維持する。
- 権限: 実装そのものは行わない。Tech Leadの決定を差し戻す・保留するよう助言はできるが、最終判断はYoshinobuに委ねる。

#### Tech Lead(`techlead` / `techlead2`)

- ホームラボとAnsible全体を理解する。
- 要求を実装可能・検証可能な単位へ分解する。
- 対象Context、Policy、リスク、受入条件を指定する。
- 各Roleへ作業を割り当てる。
- 通常は自席に対応する専属trioへ割り当てる(`techlead`は無印、`techlead2`は2付き)。他方のtrioへ直接割り当てる場合は、担当Tech Lead同士またはCoordinatorを介して指揮系統の変更を明示する。
- 実装・レビュー・テスト結果を統合し、agmsgでCoordinator(`claude`)へ共有する。Yoshinobuへ直接報告する場合もあるが、正式な判断材料はCoordinatorのレビューを経て伝わる。

#### Implementer

- Issueと指定Contextを理解する。
- 対象コードと関連実装を調査する。
- 要件を満たす最小差分を実装する。
- 自己検証を行い、変更内容と未検証事項を引き継ぐ。
- 要件を独断で拡張しない。

#### Reviewer

- Issue、差分、対象Context、Policyを確認する。
- 正確性、安全性、保守性、影響範囲、テスト不足を評価する。
- 指摘を重大度別に整理する。
- 原則として自ら実装を変更せず、Implementerへ戻す。

#### Tester

- 受入条件、差分、対象構成、依存関係を確認する。
- 静的検証、限定実行、再実行、異常系を計画・実施する。
- 本番影響がある検証は安全境界を確認する。
- 実施結果、未実施項目、残存リスクを報告する。

**完了条件**

同じ作業について、担当Roleと承認Roleが明確になっている。

### TODO 3-3: Role定義が参照するContextとSkillを定義する

- [ ] Roleごとの必須Contextを記載する。
- [ ] RoleごとのContext選択基準を記載する。
- [ ] Roleごとの必要Skillを記載する。
- [ ] Roleごとの禁止事項とエスカレーション条件を記載する。

**この作業を行う意味**

Roleファイルへ環境情報や一般ノウハウをコピーすると、重複と陳腐化が発生する。Roleは「何を参照するか」を示し、詳細はContext・Policy・Skill側に持たせる。

**完了条件**

Role定義が薄く保たれ、同じルールが複数Roleへコピーされていない。

---

## Phase 4: 公開Skillを調査・評価する

### TODO 4-1: Skillの利用目的をRoleごとに明確にする

- [ ] Tech Leadに不足している能力を列挙する。
- [ ] Implementerに不足している能力を列挙する。
- [ ] Reviewerに不足している能力を列挙する。
- [ ] Testerに不足している能力を列挙する。

**この作業を行う意味**

先に公開Skillを眺めると、面白そうなSkillを目的なく導入しやすい。現在の弱点や役割の責任から、必要な能力を先に決める。

**調査候補**

| Role | 探す能力 |
|---|---|
| Tech Lead | repository exploration、architecture analysis、requirements decomposition、risk analysis、task delegation |
| Implementer | Ansible best practices、idempotency、secure implementation、Git workflow、minimal change |
| Reviewer | code review、security review、change impact analysis、Ansible review、severity classification |
| Tester | test planning、acceptance testing、failure-path testing、idempotency testing、Ansible validation |
| 共通 | multi-agent collaboration、PR / diff workflow(GitHub Issueは当面不使用のため対象外)、memory / lessons management |

**完了条件**

各Skill候補について、どのRoleのどの能力を改善するためか説明できる。

### TODO 4-2: 信頼できる公開Skillを探索する

- [ ] OpenAI、Anthropic、Microsoft等の公式・信頼できるリポジトリを優先する。
- [ ] Ansible、レビュー、テスト、要件分解に関するSkillを収集する。
- [ ] Skill本文だけでなく、付属するShell、Python、外部通信、権限要求も確認する。
- [ ] ライセンス、更新状況、上流リポジトリ、コミットを記録する。

**この作業を行う意味**

公開Skillには、単なる手順書だけでなく実行コードが含まれる場合がある。agmsgと同様に、コード・状態管理・外部通信を含むSkillはサプライチェーン上のリスクになるため、内容確認が必要である。

**評価項目**

| 項目 | 確認内容 |
|---|---|
| 出典 | 公式または信頼できる作者か |
| ライセンス | 流用・改変可能か |
| 更新状況 | 放置されていないか |
| 適合性 | 今回のRole責務に合うか |
| 実行コード | Shell / Python / API呼び出しがあるか |
| 権限 | ファイル、ネットワーク、秘密情報へのアクセス |
| 冗長性 | core / Role / Contextと重複しないか |
| 導入方式 | そのまま利用、参照、fork、部分流用 |
| 上流追跡 | 元Skillとrevisionを記録できるか |

**成果物**

`public-skills-evaluation.md` 相当の比較表。

**完了条件**

採用、部分採用、不採用の理由が記録されている。

### TODO 4-3: 公開Skillの利用方式を決める

- [ ] そのままインストールするSkillを決める。
- [ ] 上流Skillを参照して使うものを決める。
- [ ] ホームラボ用の補足を追加するものを決める。
- [ ] forkまたはローカルコピーする場合の更新追跡方法を決める。

**この作業を行う意味**

公開Skillをコピーして独自改造すると、上流改善を取り込めなくなる。一方、外部Skillを無条件に自動更新すると、挙動が変わる。利用方式と更新方針を決める必要がある。

**推奨原則**

```text
公開Skillの一般能力
    +
ホームラボ固有のRole / Context / Policy
```

公開Skill内へホームラボのIP、ホスト、運用ルールを大量に書き込まない。

**完了条件**

各採用Skillについて、上流、revision、ローカル拡張、更新方法が追跡できる。

---

## Phase 5: Role SkillとContext読み込みを実装する

### TODO 5-1: Role定義ファイルを作る

- [ ] coordinator(`claude`)のRole定義を作る(2026-07-21確定。壁打ち・案件振り分け・Tech Lead決定内容のレビューを担うため必須)。
- [ ] techleadのRole定義を作る。
- [ ] implementerのRole定義を作る。
- [ ] reviewerのRole定義を作る。
- [ ] testerのRole定義を作る。

**この作業を行う意味**

現在は `agmsg actas reviewer` というidentityから、AIが役割を推測している。Role定義を明示することで、責任・権限・参照Skill・成果物を一貫させる。

**完了条件**

各AIがRole定義を読んだ後、自分の責任、禁止事項、必要成果物を説明できる。


### TODO 5-2: Codex・Claude Codeで共有するSkillソースを決める

- [ ] Skillの共通正本ディレクトリを決める。
- [ ] 各Skillを `skill-name/SKILL.md` の単位で管理する。
- [ ] CodexとClaude Codeの探索場所・起動方法の違いを確認する。
- [ ] 必要ならsymlinkまたは同期スクリプトで各製品へ公開する。
- [ ] Skill内にIPアドレスや具体的な環境識別情報がないことを検査する。
- [ ] ホスト名や構成情報を記載した場合、その必要性と参照元をレビューする。

**この作業を行う意味**

同じRole能力をCodex用とClaude Code用に別々に保守すると、内容差異と更新漏れが発生する。Skill本文を共通化し、製品差は配置・呼び出し部分だけへ限定する。

**完了条件**

- 一つのSkill修正がCodexとClaude Codeの双方へ反映される。
- Skillが環境台帳化していない。
- 環境固有値はInventory、変数、Context、Policy、Issueから解決される。

### TODO 5-3: Contextの遅延読み込み方法を決める

- [ ] 起動時に読むContextを最小化する。
- [ ] Issue受領時にTech Leadが必要Contextを指定する形式を決める。
- [ ] 他Roleが追加Contextを自主調査する条件を決める。
- [ ] Context指定をagmsgメッセージへ含める形式を決める。

**この作業を行う意味**

SkillやContextを分割しても、起動時に全ファイルを読ませれば効果がない。案件に応じて必要な情報だけを読む仕組みが必要である。

**メッセージ例**

```yaml
task: implement request-42  # GitHub Issueは不使用。agmsgの依頼メッセージ/docs/ai/reviews配下のフォルダ名などで識別する
role: implementer
context:
  required:
    - docs/ai/core.md
    - docs/ai/context/system/proxmox.md
    - docs/ai/context/ansible/playbook-map.md
    - docs/ai/policies/proxmox_patch_policy.md
  optional:
    - docs/ai/memory/lessons/patching.md
acceptance_criteria:
  - ...
```

**完了条件**

Implementer、Reviewer、Testerが、案件に無関係な全体Contextを読まずに作業できる。

### TODO 5-4: Roleごとの出力フォーマットを決める

- [ ] Tech Leadの依頼・判断メッセージ形式を決める。
- [ ] Implementerの完了報告形式を決める。
- [ ] Reviewerの指摘形式を決める。
- [ ] Testerの結果形式を決める。

**この作業を行う意味**

AI間の引き継ぎが自由文だけだと、必要情報の欠落や解釈違いが起きる。最低限の構造を決めることで、agmsgによる非同期連携を安定させる。

**例：Reviewer報告**

```yaml
result: NEEDS_CHANGES
findings:
  - severity: blocker
    location: roles/example/tasks/main.yml
    issue: ...
    reason: ...
    required_action: ...
residual_risks:
  - ...
```

**完了条件**

受信側が追加質問なしで次の作業に移れるだけの情報が含まれる。

---

## Phase 6: Knowledge(`docs/ai/memory/`)運用を改善する

### TODO 6-0: 4層モデルへ整理する(2026-07-21、Codexのレビューを反映)

情報の置き場を、Memory一本ではなく次の4層で整理する。

| 層 | 位置づけ |
|---|---|
| Core | プロジェクト共通ルール(`docs/ai/core.md`) |
| **Knowledge**(現 `docs/ai/memory/`) | **プロジェクト全体で共有すべき知識**。特定AI製品に紐づかない、リポジトリ内の共有資産 |
| Skill | 再利用可能な能力・手順 |
| Claude Memory | Claude Code固有の経験・運用(`~/.claude/projects/.../memory/`)。Codex系Roleからは見えない |

ポイントは、**Knowledgeは Claude Memoryのコピーではない**ということである。Claude Memoryはこれまで通りClaude Codeが単独で活用し続け、そのうちCodex系Role(`implementer`/`reviewer`/`tester`/`techlead2`)の判断にも必要になったものだけを、都度Knowledgeへ書き出す(遅延移行)。一括移行はしない。

- [ ] 判定ルールを1つだけ採用する: 「この知識を知らないことで、Codex系Roleの判断や実装が変わるか」。
  - Yesの場合 → Knowledge(`docs/ai/memory/`)へ書く(例: rollback系CLI引数の規約、破壊的操作の分類基準、multilayer escapeの落とし穴など)。
  - Noの場合 → Claude Memoryのままでよい(例: Yoshinobuとのコミュニケーションスタイル、Claude Code自身の作業習慣など、Claude Code固有の運用に閉じるもの)。
- [ ] 既存のClaude Memory(現在数十件)を一括移行しない。上記ルールに該当するものが実際に必要になった時点で、都度Knowledgeへ書き出す。一括棚卸しは低難度作業としてCodexへ依頼してもよいが、着手はPhase 7の実証結果を見てから判断する。
- [ ] Knowledgeは恒久的な置き場ではない。再利用可能な手順として固まったものは、TODO 6-2の昇格ルールに従ってSkillへ昇格させ、Knowledge側からは昇格済みである旨を残す(参照はSkillへ寄せ、内容を二重に保持しない)。
- [ ] Knowledgeの内部分類(Incident/Lesson/Decision/Temporary)は、Claude Memoryの`user`/`feedback`/`project`/`reference`とは別の分類体系であることを明記する(型名を無理に揃えない)。

### TODO 6-1: Knowledgeを分類する

- [ ] Incidentを定義する。
- [ ] Lessonを定義する。
- [ ] Decisionを定義する。
- [ ] Temporary情報を定義する。
- [ ] 各分類の保存期間と参照範囲を決める。

**この作業を行う意味**

一時的な失敗、恒久的な設計判断、再利用可能な教訓を同じ置き場で扱うと、AIが古い情報を現行ルールと誤認する。

**分類案**

| 分類 | 内容 | 例 |
|---|---|---|
| Incident | 起きた事実 | testerが誤ったinventoryを選びかけた |
| Lesson | 再発防止の学び | テストではinventoryを明示する |
| Decision | 承認済み設計判断 | Shellは収集、判定はAnsible側 |
| Temporary | 作業中だけ必要 | request-42のテストが未完了 |

**完了条件**

Knowledgeの各項目について、事実・教訓・正式判断・一時情報のどれか判別できる。

### TODO 6-2: Knowledgeの昇格・廃止ルールを決める

- [ ] IncidentからLessonへ昇格する条件を決める。
- [ ] LessonからSkillへ昇格する条件を決める(恒久的なノウハウは最終的にKnowledgeではなくSkillへ寄せる)。
- [ ] Skillからcoreへ昇格する条件を決める(全Role共通の不変原則になった場合のみ)。
- [ ] Temporary情報の削除条件を決める。
- [ ] 古くなったDecisionを見直す方法を決める。

**この作業を行う意味**

改善を蓄積しながら、Knowledge自体・Skill・coreを肥大化させないために必要である。Knowledgeは中間集積所であり、最終的な置き場ではない。

**完了条件**

ミスが起きたとき、どこへ記録し、いつSkillやcoreへ反映するか迷わない。

### TODO 6-3: RoleごとのKnowledge参照範囲を決める

- [ ] Tech Leadが読むDecisionと重要Lessonを決める。
- [ ] Implementerが読む対象関連Lessonを決める。
- [ ] Reviewerが読む過去のレビューLessonを決める。
- [ ] Testerが読む障害・テストLessonを決める。

**この作業を行う意味**

全KnowledgeをRoleへ読ませると、コンテキストが増え、無関係な過去事例に引きずられる。案件と役割に関連するものだけを参照する。

**完了条件**

各RoleがKnowledgeを検索・選択でき、起動時に全件読み込まない。

---

## Phase 7: 小規模な実証を行う

### Phase 7開始前のpilot最小実装

Phase 7はPhase 3〜5の本格展開を待たないが、実証対象が存在しない状態でも開始しない。低リスク案件を一件選んだ後、その案件に必要な最小セットだけを先に用意する。

- Phase 3: Coordinator / Tech Lead / Implementer / Reviewer / Testerの最小Role定義、identity対応、trio routing、返却先を定義する。移行期間は `docs/ai/role-routing-index.md` を使う。
- Phase 2: pilot対象だけのContextとPolicy参照を決める。全System / Repository Contextの分割は行わない。
- Phase 4: pilotで使う公開Skill候補を少数だけ一次評価する。適切な候補がなければ、現行手順を暫定Role Skillとして明記する。
- Phase 5: core → Role → 対象Context / Policy → Skillの手動読み込み手順を用意する。起動スクリプトへの自動実装はPhase 8まで行わない。

この最小セットをPhase 7で検証し、採用・修正・棄却を判断してから、Phase 2〜6の本格展開範囲を決める。

### TODO 7-1: 一つの低リスク案件で試行する

- [x] read-onlyのhealthcheck改善など、影響の小さいIssueを選ぶ。→ `radius_healthcheck` のdisk使用率チェック追加で実証。
- [x] Tech LeadがContextを指定する。→ pilot setupに限定Context / Policy参照を記録。
- [x] Implementerが新Role・Skillで実装する。→ `implementer2` が暫定Role Skillと手動読込順序で実装。
- [x] Reviewerが新Role・Skillでレビューする。→ `reviewer2` がUse%の意味論不足を検出し、修正後PASS。
- [x] Testerが新Role・Skillで検証する。→ `tester2` がlocal fixture / source task harnessで検証しPASS。
- [x] agmsgの引き継ぎ内容を確認する。→ 2付きtrio routingで全工程をowner `techlead2`へ返却し、Coordinatorへ統合報告。

2026-07-21、Coordinator承認済み。詳細は `docs/ai/reviews/radius_healthcheck/2026-07-21_020_final.md` を参照する。

**この作業を行う意味**

全体を一度に切り替えると、Role、Skill、Context、起動処理のどこに問題があるか分からない。低リスク案件で情報量・役割分担・引き継ぎを検証する。

**確認項目**

- 不要なContextを読んでいないか。
- 必要な環境情報が不足しなかったか。
- Tech Leadの指定が過不足なかったか。
- Roleの責務が重複しなかったか。
- 公開Skillが実際に品質向上へ寄与したか。
- Knowledgeへ何を残すべきか判断できたか。

**完了条件**

旧方式と比較して、作業品質を落とさず、読み込み量または指示の重複を減らせたことを確認する。

### TODO 7-2: Role別の不足を修正する

- [x] Tech LeadのContext選択漏れを分析する。
- [x] Implementerの実装Skill不足を分析する。
- [x] Reviewerの見落としを分析する。
- [x] Testerの検証不足を分析する。
- [x] 問題をcoreへ直接追加せず、適切なRole・Skill・Context・Knowledgeへ反映する。

2026-07-22、Coordinator承認済み。分析結果は `docs/ai/reviews/agent_skills_reorganization_todo7-2_result.md` を参照する。coreは変更せず、Knowledge候補2件は昇格を保留した。

同日のtester-gateコメント実態整合では、挙動不変の文書変更にも通常の3-Role独立フローを適用し、工程コストが変更規模を上回った。`docs/ai/reviews/agent_skills_reorganization_phase7_process_incident_lightweight_lane.md` にProcess Incidentとして記録し、軽量レーンを今後のRole / Workflow設計の再評価材料およびKnowledge昇格候補とした。coreへは追加しない。

**この作業を行う意味**

初期設計は必ず不足が出る。修正先の分類ルールを実際に試し、core肥大化を防げるか確認する。

**完了条件**

試行で発見した問題が、適切な情報層へ反映されている。

### Phase 7 follow-up: tester-gate理由コメントの実態整合（依頼B）

- [x] 7 playbookの通知経路と抑止条件を個別に棚卸しする。
- [x] `safe-readonly` 分類を維持し、実態とずれたmarkerコメントだけを修正する。
- [x] `time_sync_check` の3通知経路と過去事故対策が有効であることを確認する。
- [x] `proxmox_patch_dryrun` の2通知経路とdry-runコマンドを区別して記録する。
- [x] ReviewerとTesterが対象限定の差分、marker lint、guard実態を確認する。
- [x] 重複した棚卸し結果を正式記録1件へ統合する。
- [x] 過剰な工程をProcess Incidentとして記録し、軽量レーンの適用条件を定める。

2026-07-22、Coordinator承認済み。実装結果は `docs/ai/reviews/agent_skills_reorganization_tester_gate_comment_alignment.md`、工程改善は `docs/ai/reviews/agent_skills_reorganization_phase7_process_incident_lightweight_lane.md` を参照する。7 playbookはmarkerコメント各1行だけを変更し、分類と実装コードは変更していない。

---

## Phase 8: `new-session.sh` と初期化処理を変更する

このPhaseは、Role、Context、Skill、Knowledgeの構造が確定した後に実施する。

### TODO 8-1: 起動時に必要な処理を定義する

- [ ] agmsg identity登録を行う。
- [ ] identityからRoleを解決する。
- [ ] `core.md` を読む。
- [ ] Role定義を読む。
- [ ] 起動時必須Skillを確認する。
- [ ] 起動時必須Contextだけを読む。
- [ ] monitorを開始する。
- [ ] READY状態をagmsgで報告するか決める。

**この作業を行う意味**

`new-session.sh` へ場当たり的に読み込み処理を追加せず、AI初期化の正式な契約を決めるためである。

**READY報告例**

```yaml
status: READY
identity: reviewer2
role: reviewer
core: loaded
role_definition: loaded
skills:
  - agmsg
  - code-review
context:
  - system-overview
monitor: active
```

**完了条件**

起動したAIが、自分のidentity、Role、必須原則、利用Skillを明示できる。

### TODO 8-2: `new-session.sh` と `prep-agent.sh` の責務を分ける

- [ ] `new-session.sh` はtmux、pane、AIプロセス、agmsg参加を中心に保つ。
- [ ] Role解決と読み込みは `prep-agent.sh` または専用bootstrapへ寄せる。
- [ ] `reviewer2` などのidentityをRoleへ正規化する。
- [ ] readiness timeoutや失敗時の扱いを維持する。
- [ ] 既存monitor動作とper-agent bridgeを壊さない。

**この作業を行う意味**

現在の `new-session.sh` は、tmuxのambient targetやreadiness timeoutなど実運用で解決した重要な処理を持つ。RoleやSkillの詳細まで追加すると保守が難しくなるため、起動配置とAI初期化を分離する。

**推奨責務**

```text
new-session.sh
  - tmux session / window / pane作成
  - AIプロセス起動
  - agmsg join / monitor準備
  - identity付与

prep-agent.sh または bootstrap-agent.sh
  - identity確認
  - Role解決
  - core読み込み
  - Role定義読み込み
  - 起動時Context / Skill確認
  - READY報告
```

**完了条件**

- `new-session.sh` のtmux配置・monitor・並列起動が従来通り動く。
- 各AIが正しいRoleで初期化される。
- Role追加や席追加時に起動スクリプトの大幅変更が不要になる。

### TODO 8-3: 旧方式へ戻せる状態で切り替える

- [ ] 変更前スクリプトをGitまたはバックアップで保持する。
- [ ] 一つのRoleまたはworkers windowから段階導入する。
- [ ] monitor、agmsg配送、READY、引き継ぎを確認する。
- [ ] stale bridge、pane誤配置、bootstrap timeoutを再確認する。

**この作業を行う意味**

起動処理は全Agentに影響する。設計が正しくても、tmuxやagmsg bridgeの実装上の問題が起きる可能性があるため、段階導入と切り戻しを可能にする。

**完了条件**

新方式で全Agentが起動・受信・Role認識でき、問題発生時に旧方式へ戻せる。

---

# 5. 実施順序と依存関係

次の順番で進める。

```text
Phase 0  現状の基準化
   ↓
Phase 1  core.mdの役割確定と移行表
   ↓
Phase 2  Context / Policy分類とRole別マトリクス
   ↓
Phase 3  Role責務とidentity対応
   ↓
Phase 4  公開Skillの調査・評価
   ↓
Phase 5  Role定義・Skill・Context読み込み実装
   ↓
Phase 6  Knowledge運用改善
   ↓
Phase 7  低リスク案件で実証
   ↓
Phase 8  new-session.sh / prep-agent.sh変更
```

公開Skill調査をRole定義の後に置く理由は、必要な能力が決まる前にSkillを探すと、目的のない導入になりやすいためである。

`new-session.sh` を最後に置く理由は、何を読み込ませるかが決まっていない段階では、正しい起動処理を設計できないためである。

## 実施順序に対する優先度メモ(2026-07-21合意、2026-07-21 pilot依存を明確化)

上記の順序自体は維持しつつ、実際に着手する濃淡は次のようにする。

- **完了(2026-07-21)**: Phase 0のbaseline実測とPhase 1の`core.md`移行表・草案・製品別入口を作成し、Implementer / Reviewer / Tester / Tech Lead / Coordinatorの確認を完了した。
- **Phase 1完了後、pilot最小実装を先行**: Role別Contextマトリクス初期案に加え、pilot対象のContext / Policy、Phase 3の最小Role・routing・返却先、Phase 4の候補Skillまたは暫定Role Skill、Phase 5の手動読み込み手順を作る。
- Phase 3のTODO 3-1(identityとRoleの対応)は2026-07-21に解決済み(各identityから単一Roleへ一意に対応し、複数identityが同じRoleを共有できる)。Phase 7前にTODO 3-2のうちpilotに必要な責務・routing・返却先まで最小定義し、残りを本格展開で完成させる。
- **Phase 7で最小セットを実証**: 低リスク案件でRole、選択Context / Policy、候補Skill、手動読み込み手順を実際に使い、品質と読み込み量を評価する。
- **本格展開はPhase 7後**: System / Repository Context全面分割、公開Skill全体調査、Role / Skill / Context読込の本実装、Knowledge運用改善の本実装は、実証結果を見て範囲と優先度を決める。TODO 6-0の4層モデル整理自体は先に進めてよい。
- Phase 8は従来通り最後。

---

# 6. 最初に作るべき3つの成果物

実装へ入る前に、次の3つを完成させる。

## 6.1 `core.md` 移行表

現行 `core.md` の各項目について、残す・移す・削除を決める。

## 6.2 Role別Contextマトリクス

誰が、いつ、どの深さで、何を読むかを決める。

## 6.3 公開Skill評価表

どのRoleの能力向上に、どの公開Skillを利用するかを決める。

この3つが揃う前にRole Skillや起動スクリプトを作り始めない。

---

# 7. この計画で避けること

- `core.md` を単純に複数ファイルへ分割しただけで完了としない。
- 全Roleへ同じContextとSkillを読ませない。
- Role定義へ環境情報や一般ノウハウを大量コピーしない。
- `AGENTS.md` と `CLAUDE.md` に同じ共通原則を二重管理しない。
- SkillへIPアドレス、認証情報、VLAN ID、VM IDを記載しない。
- Skillへホスト名や構成情報を必要性なく埋め込まない。
- 公開Skillを内容確認せず直接導入しない。
- 過去のミスを即座に恒久ルールへしない。
- Tech LeadのContext指定だけを絶対視し、他Roleの追加調査を禁止しない。
- 現行tmux・agmsg・monitorの安定動作を壊してまで構成を刷新しない。
- `new-session.sh` から設計を始めない。

---

# 8. 最終的な完了条件

この再構成は、ファイルを分割した時点では完了ではない。次の状態を満たしたときに完了とする。

- [ ] `core.md` が短く、全Role共通の不変原則だけになっている。
- [ ] Codexの `AGENTS.md` とClaude Codeの `CLAUDE.md` が薄い入口になり、共通原則を二重管理していない。
- [ ] 各Skillは `SKILL.md` を正本としてCodexとClaude Codeで共有できる。
- [ ] SkillにIPアドレス、認証情報、VLAN ID、VM IDが記載されていない。
- [ ] ホスト名や構成情報がSkillへ無闇に埋め込まれていない。
- [ ] オンプレ環境、Ansible構成、運用、Policyが明確に分類されている。
- [ ] identityとRoleが分離され、AIが名前から役割を推測しない。
- [ ] Tech Lead、Implementer、Reviewer、Testerの責任と成果物が明確である。
- [ ] Roleごとに必要なContextだけを読み込める。
- [ ] 一般能力は公開Skillを基礎とし、独自Skillはホームラボ固有部分に限定されている。
- [ ] 採用Skillの出典、revision、ローカル変更、更新方法を追跡できる。
- [ ] KnowledgeがIncident、Lesson、Decision、Temporaryに分類されている。
- [ ] 低リスク案件で新しい連携方式を実証している。
- [ ] `new-session.sh` がtmuxと起動配置に集中し、Role初期化が分離されている。
- [ ] agmsg monitorとAI間メッセージ配送が従来通り安定して動く。
- [ ] 新しいRoleや第3席を追加するとき、Role定義とidentity対応の追加だけで済む。

---

# 9. 直近の着手項目(2026-07-21更新)

`core.md`移行(Phase 1)は2026-07-21に完了した。次Phaseへ進むかはYoshinobuの指示を待つ。

- [x] 現行 `core.md`(1253行・18セクション)の全見出しと主要ルールを移行表へ書き出す(TODO 1-2)。
- [x] 各項目を `core / Role / Context / Policy / Skill / Knowledge / Issue / 削除` に分類する。
- [x] 移行表に基づき、短い `core.md` 草案(92行)を作る(TODO 1-3)。
- [x] `AGENTS.md` / `CLAUDE.md` / `docs/ai/core.md` の関係を確定する(TODO 1-4)。

Role別Contextマトリクスの初期案(TODO 2-4)はcore.md移行と並行して着手してよいが、System/Repository Contextの本格分割・公開Skill調査・Knowledge本実装(Phase 2後半〜Phase 6)は、「実施順序に対する優先度メモ」のとおりPhase 7の実証後に着手を判断する。
