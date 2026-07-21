# AI Agent / Skills 再構成 Phase 0 現状基準

調査日: 2026-07-21

この文書は `docs/ai/reviews/agent_skills_reorganization_plan.md` の TODO 0-1 に対する実測記録である。将来像ではなく、調査時点で実際に参照・実行されているものを記録する。

## 正本と現行ファイル

| 対象 | 現行の正本・実体 | 実測 | 判断 |
|---|---|---:|---|
| AI共通前提（移行前） | `docs/ai/prompts/core.md` | 1,253行、18セクション | Phase 1移行元。詳細情報を含む旧正本 |
| AI共通原則（Phase 1草案） | `docs/ai/core.md` | 本作業で新規作成 | 共通原則の新しい正本。未移行の詳細は旧正本を参照 |
| 移行中のRole / routing | `docs/ai/role-routing-index.md` | 本作業で新規作成 | Phase 3/5/8までのidentity解決・trio routing正本 |
| セッション起動 | リポジトリ直下 `new-session.sh` | 218行 | tmux、Role配置、agmsg monitor有効化、AI起動を担当 |
| Agent初期化 | リポジトリ直下 `prep-agent.sh` | 87行 | Role別bootメッセージ送信とready待ちを担当 |
| agmsg稼働コピー | `/home/yoshi/.agents/skills/agmsg` | `version.sh` は `v1.1.10` | 実際の送受信・起動で使う稼働正本 |
| agmsgソースclone | `/home/yoshi/agmsg` | `v1.1.2-14-gc71531b`、調査時clean | 開発用clone。install/updateなしでは稼働コピーへ反映されない |
| Claude Code Memory | `/home/yoshi/.claude/projects/-home-yoshi-homelab-ansible/memory/` | `MEMORY.md` と個別Markdown | Claude Code固有。リポジトリ共通知識の正本ではない |
| リポジトリ共通Knowledge | 該当なし | `docs/ai/memory/` / `docs/ai/knowledge/` とも未作成 | Phase 6で設計・移行する |
| 案件記録 | `docs/ai/reviews/<target>/` | requirement / implement / review / test_plan / test_result / final | 当面のIssueとPR/diff監査証跡を兼ねる |

調査開始時の `git status --short` は、既存の未追跡ファイル `docs/ai/reviews/agent_skills_reorganization_plan.md` のみだった。本作業では同ファイルを編集対象にせず、techlead2側の変更を保護した。

## agmsgの正本確認

- インストール場所は `/home/yoshi/.agents/skills/agmsg`。`new-session.sh` と `prep-agent.sh` もこの配下の `scripts/` を絶対パスで呼ぶ。
- インストール版は、提供スクリプト `scripts/version.sh` の結果で `v1.1.10`。
- ソースclone `/home/yoshi/agmsg` は `v1.1.2-14-gc71531b` で、インストール版より現行稼働仕様を表していない。
- 両方の `SKILL.md` の SHA-256 は異なる。
  - source: `daec690895bfb72d236e88d5aa68c8577c23d6dcba4c378f8cbf2aef74cb8f3c`
  - installed: `d9e58412539922a6a978cce27e3c3ee981137989c877a4c151a7262741fe1590`
- インストール版 `SKILL.md` は Codex の `actas`、Roleごとのsession記録、monitor bridge、delivery modeを具体的に扱う。一方、source版は汎用CLI・Claude Code中心の旧説明を多く含む。
- `scripts/` の比較でも、`send.sh`、`inbox.sh`、`join.sh`、`spawn.sh`、Codex driver群など多数が相違し、インストール版だけに `codex-record-session.sh` 等が存在した。

結論: 現行運用の確認は、デプロイ済みの `SKILL.md` と提供スクリプトの出力を基準にする。`~/agmsg` の内容や `git pull` だけを根拠に稼働仕様を判断しない。

### Shell行数baselineと再現方法

実測日: 2026-07-21。installed versionは `v1.1.10`、source revisionは `v1.1.2-14-gc71531b`（source working treeは実測時clean）。

| 範囲 | 行数 | 包含・除外 |
|---|---:|---|
| installedの全Shell | 10,028 | `/home/yoshi/.agents/skills/agmsg/scripts/` 配下の全 `.sh`。Skill root直下の `uninstall.sh` 等は含めない |
| installedの現行主要範囲 | 9,044 | `scripts/` top-level + `lib` / `internal` / `drivers/types/claude-code` / `drivers/types/codex`。その他product driver、Windows PowerShell、JavaScriptは除外 |
| source cloneの全Shell | 7,838 | `/home/yoshi/agmsg` 配下の全 `.sh`。`.git/` は除外 |

再現コマンドは空白を含むpathでも壊れないよう、`find -print0`、`sort -z`、`xargs -0` を使う。

```bash
# installed: scripts/ 配下の全 .sh
find /home/yoshi/.agents/skills/agmsg/scripts -type f -name '*.sh' -print0 \
  | sort -z | xargs -0 wc -l | tail -1

# installed: top-level + lib + internal + claude-code/codex driver
{
  find /home/yoshi/.agents/skills/agmsg/scripts -maxdepth 1 \
    -type f -name '*.sh' -print0
  find /home/yoshi/.agents/skills/agmsg/scripts/lib \
    /home/yoshi/.agents/skills/agmsg/scripts/internal \
    /home/yoshi/.agents/skills/agmsg/scripts/drivers/types/claude-code \
    /home/yoshi/.agents/skills/agmsg/scripts/drivers/types/codex \
    -type f -name '*.sh' -print0
} | sort -zu | xargs -0 wc -l | tail -1

# source clone: .gitを除く全 .sh
find /home/yoshi/agmsg -type f -name '*.sh' \
  -not -path '/home/yoshi/agmsg/.git/*' -print0 \
  | sort -z | xargs -0 wc -l | tail -1
```

## Memory / Knowledgeの現状

Claude Code Memoryはプロジェクト別ディレクトリにMarkdownで保存される。

```text
/home/yoshi/.claude/projects/-home-yoshi-homelab-ansible/memory/
├── MEMORY.md
├── feedback_*.md
├── project_*.md
└── reference_*.md
```

個別ファイルはYAML front matterに `metadata.node_type: memory` と `metadata.type` を持ち、実測した型は `feedback`、`project`、`reference` だった。`MEMORY.md` は索引である。これはClaude Codeのセッション支援情報であり、Codexを含む全Roleが同じ方法で自動参照する共通知識ではない。

リポジトリ内には調査時点でKnowledge専用ディレクトリがない。共有すべきIncident、Lesson、Decision、Temporary情報の形式と移行判断はPhase 6へ残す。

## scriptで実装済みの起動・boot経路

```text
Yoshinobu
  |
  +-- new-session.sh
       |
       +-- agmsg delivery=monitor を設定
       +-- tmux window 0
       |    +-- claude      : 要件定義・ハブ
       |    +-- reviewer    : レビュー
       |    +-- implementer : 実装
       |    `-- tester      : テスト
       `-- tmux window 1
            +-- techlead2   : 要件・調整
            +-- reviewer2   : 第2レビュー
            +-- implementer2: 第2実装
            `-- tester2     : 第2テスト

各Codex Role
  <- agmsg spawn/join + /agmsg actas <identity>
  <- prep-agent.sh が送信元 claude でbootメッセージを送る
  <- monitor bridgeを有効化済みだが、prep-agent.shはready後にkick.shも実行
```

実装済み経路の詳細:

- `new-session.sh` はCodex deliveryをmonitorへ設定し、reviewer / tester / reviewer2 / tester2を `spawn.sh`、implementer / techlead2 / implementer2を `join.sh` + `respawn-pane` で起動する。
- `prep-agent.sh` のCodex経路は、送信元を常に `claude` としてbootメッセージを先にqueueし、Roleのreadyを待ち、最後に `kick.sh` でinbox処理を促す。したがって現在はmonitor有効化と明示kickが併用される。
- 既定boot文は reviewer/reviewer2、tester/tester2、implementerだけが専用caseを持つ。`implementer2` と `techlead2` は汎用文へfallbackする。
- 専用boot文の返信先は `claude` であり、trio owner別routingを実装していない。
- `new-session.sh` 冒頭の説明は、tester2の選択者を `claude` としており、合意済みroutingより古い。

Roleの責務本文と返信先が起動スクリプト内へ埋め込まれている。これは現状の事実であり、次節の合意済みroutingとは分けて扱う。

## 合意済みの案件owner / trio routing

移行期間の運用正本は `docs/ai/role-routing-index.md` とする。

```text
Coordinator: claude
  <- Tech Lead統合結果を受け、Yoshinobuへの判断材料を整える

techlead
  -> implementer / reviewer / tester
  <- 無印trioの各成果物を直接受領・統合

techlead2
  -> implementer2 / reviewer2 / tester2
  <- 2付きtrioの各成果物を直接受領・統合
```

cross-trioは、両Tech LeadまたはCoordinatorを介した明示移管がある場合だけ行う。旧ownerの停止、新owner、進行中成果物の返却先をagmsgで通知する。通常案件ではtrio memberがCoordinatorへ直接返却せず、owner Tech Leadが統合後にCoordinatorへ共有する。

script実装と合意済みroutingには差がある。**Phase 3**でRole、返却先、移管条件を正式定義し、**Phase 8**で `new-session.sh` / `prep-agent.sh` のboot送信元、専用case、返信先、説明コメントを正式routingへ合わせる。

## 合意済みroutingによる案件作業フロー

```text
Yoshinobuの要求
  -> Coordinatorが案件をtechleadまたはtechlead2へ割当
  -> owner Tech Leadがrequirementを保存
  -> ownerの専属implementerへ依頼、implementをownerへ返却
  -> ownerの専属reviewerへ依頼、reviewをownerへ返却
  -> ownerが指摘をトリアージし、必要なら反復
  -> ownerがtest_planを起案しYoshinobuが承認
  -> ownerの専属testerがtest_resultをownerへ返却
  -> owner Tech Leadが全成果物を統合しCoordinatorへ共有
  -> Coordinatorが妥当性を確認しYoshinobuへ判断材料を提示
  -> Yoshinobuが確定・commitを判断
```

無印trioと2付きtrioは同じRole・成果物形式を使うが、直接返却先がそれぞれ `techlead` / `techlead2` で異なる。共通の受け渡し原則は、本文を `docs/ai/reviews/` に置き、agmsgにはパス、短い結果、未解決事項だけを載せることである。

## 未検証事項

- `new-session.sh` を実行して新規tmuxセッションを生成する動的試験は行っていない。フローはスクリプトの静的確認に基づく。
- 合意済みtrio routingは手動agmsgで運用可能だが、boot scriptへの反映は未実装である（Phase 3/8対象）。
- agmsg sourceとinstalledの差分は正本判定に必要な範囲で確認したが、全スクリプトの意味差分レビューは行っていない。
- Claude Code Memoryの内容をKnowledgeへ移す採否・分類・保持期間はPhase 6へ残した。
- Codex製品側のセッション履歴は存在するが、リポジトリ共通Knowledgeとして利用する仕組みは確認できなかった。
