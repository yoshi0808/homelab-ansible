# Knowledge運用(Phase6 TODO6-0〜6-3)

`docs/ai/reviews/agent_skills_reorganization_plan.md` Phase6の成果物。`docs/ai/memory/`配下のKnowledgeをどう分類し、どう昇格・廃止し、誰が読むかを決める。

## 1. 4層モデル(TODO6-0)

| 層 | 位置づけ |
|---|---|
| Core(`docs/ai/core.md`) | 全Role共通の不変原則 |
| **状態**(`docs/ai/status.md`、および影響先のコード・Policy・Contextの当該箇所) | 知識ではなく**現在地**。進行中の作業、観測待ち、着手候補。可変であり、repoの現物で真偽を確かめられる |
| **Knowledge**(`docs/ai/memory/`、本ファイルの対象) | プロジェクト全体で共有すべき知識。特定AI製品に紐づかない、リポジトリ内の共有資産 |
| Skill(`skills/`) | 再利用可能な能力・手順 |
| Claude Memory(`~/.claude/projects/.../memory/`) | Coordinator(このClaude Codeセッション)固有の経験・運用。Coordinatorが起動するAgent tool subagentは前提としてこの内容を見ない(subagentは都度コールドスタートし、渡されたprompt以外の文脈を持たない) |

**判定は2段階で行う**(2026-07-27に第0段を追加)。

**第0段 — 知識か、状態か。** 「repoの現物(コード・commit・reviews)を見れば真偽を確かめられるか」を先に問う。確かめられるものは**状態**であり、Knowledgeでもauto-memoryでもなく`docs/ai/status.md`か「使う場所」(該当するコード・Policy・Contextの当該箇所)へ置く。判断の順序は次のとおり。

- 影響先のコード・Policy・Contextに書ける → **そこへ書く**(第一選択。変更する人の目に必ず入る)
- 書ける場所が無い(将来の日付やイベントを待つ、複数箇所にまたがる) → **`docs/ai/status.md`**
- repoでは確かめようがない(Yoshinobuの判断傾向、Coordinator自身の作法) → **知識**として第1段へ進む

**auto-memoryに「残タスク」「将来課題」「完了済み」を書かない。** 検証されないまま索引に残り、repoの現物と食い違う。2026-07-27時点のauto-memory索引には、隣接する2行が同じ案件を「将来課題」と「完走・commit済み」と述べる矛盾が実在し、既に解決済みの項目(`AGENTS.md`要否判断)も残タスクとして残っていた。これは`lessons/always-loaded-summaries-are-the-least-current.md`の構造そのものである。

**第1段 — 誰が読む知識か**: 「この知識を知らないことで、Coordinatorが起動するsubagent(Tech Lead/Implementer/Reviewer/Tester役)の判断や実装が変わるか」。(2026-07-26改訂: 旧「Codex系Role」の判定基準を、Codex撤退後のsubagent体制に合わせて言い換えた。判定の実質は変わらない)

- Yes → Knowledge(`docs/ai/memory/`)へ書く。
- No(Yoshinobuとのコミュニケーションスタイル、Coordinator自身の作業習慣など、Coordinatorの運用に閉じるもの)→ Claude Memoryのままでよい。

**KnowledgeはClaude Memoryのコピーではない**。Claude MemoryはこれまでどおりCoordinatorが単独で活用し続け、そのうちsubagentの判断にも必要になったものだけを都度Knowledgeへ書き出す(遅延移行)。既存Claude Memory(現在数十件)は一括移行しない。

## 2. Knowledgeの内部分類(TODO6-1)

Claude Memoryの`user`/`feedback`/`project`/`reference`とは別の分類体系である(型名を無理に揃えない)。

| 分類(ディレクトリ) | 内容 | 保存期間・参照範囲 | 例 |
|---|---|---|---|
| `incidents/` | 起きた事実そのもの | 昇格判断が付くまで保持。Lessonへ昇格したら本文をLessonへ寄せ、このファイルには昇格済み・参照先だけ残す | testerが誤ったinventoryを選びかけた |
| `lessons/` | 再発防止の学び(再利用可能) | 恒久。ただしSkillへ昇格したら参照はSkillへ寄せる(3節) | テストではinventoryを明示する |
| `decisions/` | 承認済み設計判断 | 恒久。前提が変わったら見直す(3節) | Shellは収集、判定はAnsible側 |
| `temporary/` | 作業中だけ必要な情報 | 案件クローズ時に削除 | request-42のテストが未完了 |

`incidents/`のファイル形式(ファイル名規則・記載項目・原因分類タグ・`状態`)は`skills/incident-recording/SKILL.md`が正本。**記録は気づいた時点で開始し、原因判明後に同じファイルを完成させる2段階**(2026-07-27改訂。旧ルール「修正して正常動作の確認が取れた時点で1回記録する」は、修正されなかった事象と工程内で解決した事象が丸ごと網から漏れるため撤回した)。

## 3. 昇格・廃止ルール(TODO6-2)

```text
Incident
  ↓ (同種の問題が2回目以降発生、または初回でも再利用可能な教訓を抽出できる)
Lesson
  ↓ (注意喚起でなく具体的な手順・チェックリストとして繰り返し使う価値が固まった)
Skill
  ↓ (全Role共通の不変原則になった場合のみ。極めて稀)
core.md

Incident
  ↓ (`skills/incident-recording/SKILL.md`の原因分類タグが月次振り返りで繰り返し検出された場合)
Policy または Skill (該当業務のPolicyファイル新設・改訂、または該当作業のSkill新設・改訂)
```

- **Incident→Lesson**: 上記条件を満たした時点でTech LeadまたはCoordinatorが判断する。昇格後、元のIncidentファイルは本文を削除し「Lesson `<path>`へ昇格済み」の1行だけ残す(二重保持しない)。
- **Lesson→Skill**: 単なる注意喚起ではなく、具体的な手順・テンプレートとして再利用できる形に育った場合。昇格後、Lesson側は「Skill `<path>`へ昇格済み」の1行だけ残す。
- **Skill→core**: 全Roleが例外なく毎回必要とする不変原則になった場合のみ。ハードルは高く保ち、安易に昇格させない。
- **Incident→Policy/Skill(直接、Lessonを経由しない)**: Incidentの`原因分類`タグ(`skills/incident-recording/SKILL.md`参照)が月次振り返りで複数件にわたり繰り返し検出された場合、個別の再利用可能な気づきを待たず、直接Policy改訂(許可/禁止/停止条件の明文化が必要な場合)またはSkill新設・改訂(再利用手順の整備が必要な場合)を検討する。判断はTech LeadまたはCoordinatorが行う。一度きりの気づきは従来どおりLesson経由とする。
- **昇格時は根拠を先に移送してから縮約する**(2026-07-27追加)。上記の「1行だけ残す」を機械的に適用すると、**なぜその教訓に至ったかが失われる**。順序は「①昇格先へ本文と根拠(具体的な事例・日付・失敗の経緯)を書く → ②元を1行へ縮約する」であり、逆順や同時に行わない。根拠のない規範は、前提が変わったときに見直す手がかりを持たない。
  - 全体を昇格させたときは元を1行へ縮約する。**一部だけを昇格させたときは全体を縮約しない**(残る項目は根拠として存置する)。
  - 縮約後は、元ファイルへの被参照が壊れていないことを検索で確認する(`skills/document-norm-review/SKILL.md`の宙ぶらりん参照の項)。
- **Temporaryの削除条件**: 紐づく案件(agmsgの依頼・`docs/ai/reviews/<target>/`)がクローズした時点で削除する。
- **Decisionの見直し**: 定期レビューはしない。前提条件(依存する環境事実・技術選定)が変わったとYoshinobu・Tech Lead・Coordinatorのいずれかが気づいた時点で見直す。
- **Incidentの月次振り返り**: Coordinatorが月次で`docs/ai/memory/incidents/`を振り返り、上記のPolicy/Skill直接昇格の要否を判断する。

### 月次振り返りの対象と手順(2026-07-26拡張)

当初この振り返りは`incidents/`だけを対象としていたが、**本番影響が出ずIncidentにならなかった学びが網から漏れる**ことが判明したため対象を広げる。2026-07-26のTier 4案件では、工程内で実バグ4件を検出・修正して本番影響ゼロだったためIncidentを1件も作っておらず、そこで得た教訓はCoordinatorの個人memory(Claude Memory、subagentからは読めない)にしか存在しなかった。「苦労した」という体験が学習として定着しないまま流れる状態である。

**対象**: `docs/ai/memory/incidents/`に加え、**前回の振り返り以降にCoordinatorのClaude Memoryへ蓄積された項目**、および工程を何周も往復した案件の`docs/ai/reviews/<target>/`記録。

**捕捉と昇格を分ける**: 教訓の捕捉は即時に行う(詳細は時間が経つと失われる)。月次で行うのは**昇格判断**であり、初回記録の場ではない。

**Incidentの`状態`は3値**(`調査中` / `解決済み` / `未解決`)。形式は`skills/incident-recording/SKILL.md`が正本。月次振り返りでの扱いは状態ごとに異なる。`解決済み`のみ`原因分類`タグを集計する(`調査中`のタグは未確定で集計を歪めるため)。`調査中`は滞留件数と経過日数を報告する(滞留自体が検出対象)。`未解決`(調査打ち切り)は集計にも滞留にも入れず別枠で一覧し、打ち切り判断が今も妥当かを問い直す。

**振り返りで各項目を3つに仕分ける**(Yoshinobu提案、2026-07-26)。

| 仕分け | 判定基準 | 行き先 |
|---|---|---|
| 再利用可能な**手順** | 注意喚起でなく、次回そのまま使えるチェックリスト・テンプレートになっているか | `skills/` |
| この**環境独自の事実** | このホームラボ固有の落とし穴・構成事実で、知らないと判断を誤るか | `docs/ai/memory/lessons/` または`docs/ai/context/` |
| **Yoshinobuの考え方** | 承認境界・優先順位・役割分担など、人の判断基準そのものか | `docs/ai/memory/decisions/` または Policy |

**判定ルールは1節と同じ**: まず第0段(知識か状態か)、次に「この知識を知らないことで、Coordinatorが起動するsubagentの判断や実装が変わるか」。Yesならリポジトリへ書き出す。Noならauto-memoryのままでよい。

**状態の突合も月次で行う(2026-07-27追加)**。対象は2つある。

1. **auto-memory側**: 残っている状態記述(「残:」「将来課題」「完了済み」)をrepoの現物と突き合わせ、①既に解決しているもの、②`docs/ai/status.md`へ移すべきもの、③影響先のコードやContextへ書くべきもの、に仕分ける。**auto-memoryは状態を持たない**のが到達点であり、月次はその漏れを回収する場である。
2. **`docs/ai/status.md`自身**: 各行の検証手段を実際にたどり、記述が現物と合っているかを確かめる。このファイルの更新トリガはCoordinatorセッション内の3イベントだけなので、**セッションを経由せずに現実が変わった場合**(Yoshinobuが手動で片付けた、外部システムの状態が変わった)は誰も気づかない。月次がその唯一の周期的な検知点である。

**起動はtimerが行う(2026-07-27)**。`roles/knowledge_review`が配置する`ansible-knowledge-review.timer`が毎月26日にansyで発火し、`playbooks/knowledge_review.yml`が`claude -p`でこの手順を無人実行する。当初はMEMORY.md先頭行を「実質的な発火装置」としていたが、セッションが開かれなければ発火しないため、時刻起動へ移した。

**期日の正本はCoordinatorのMEMORY.md先頭の1行**であり続ける。timerは起動機構、MEMORY.mdは実施記録という分担で、振り返り自身が最後にこの行を更新する。二重管理を避けるため、期日を他所へ書かない(2026-07-27時点で、cloud routine `homelab-ansible-incident-monthly-review`が別日程を持っていたため無効化した)。

**自律の境界**: 振り返りは`docs/ai/memory/`・`docs/ai/context/`・`skills/`へ自分で書き出す。ただし`docs/ai/policies/`本文は書き換えず、必要な改訂は`docs/ai/memory/temporary/policy-proposal-<date>-<slug>.md`へ提案として残す(Policyは人間の判断領域)。commit/pushも行わない。作業ツリーが汚れているときは何も書かずに中止する。

**無人実行は`docs/ai/status.md`を書き換えない**(2026-07-27)。書込allowlistは上記3パスのみで、`status.md`はそこに含まれない(`role-routing-index.md`「無人実行されるCoordinator」の表)。読取は`docs/`配下なので可能である。したがって上記「状態の突合」で見つかった差分は、**書き換えずに報告へ列挙する**。auto-memoryを読み取りのみとしている扱いと同じで、反映は後で対話セッションかYoshinobuが行う。allowlistを広げて`status.md`を書けるようにするのは、封じ込めが成立している3条件(`docs/ai/memory/lessons/claude-code-unattended-session-confinement.md`)を崩さないか確認したうえで別途判断する。

## 4. Role別のKnowledge参照範囲(TODO6-3)

| Role | 参照するKnowledge |
|---|---|
| Coordinator | 全`decisions/`(重要度問わず)、Tech Lead統合結果に関わる`incidents/` |
| Tech Lead | 重要`decisions/`、担当領域(自trio)に関連する`lessons/`全般、委任判断に関わる`incidents/` |
| Auditor | **読まない。** 技術的な正否を判定しないため、Knowledgeを読んでも判断に使えない。参照範囲は`docs/ai/role-context-matrix.md`「Auditorの参照範囲」が正本 |
| Implementer | 対象role/playbookに関連する`lessons/`(実装例外・落とし穴) |
| Reviewer | 過去レビューで見つかった`lessons/`(見落としパターン) |
| Tester | 障害・テスト関連の`lessons/`(検証手段の穴、rc規約等) |

全Roleとも起動時に`docs/ai/memory/`全件を読み込まない。案件と役割に関連するものだけを、Tech Leadの指定または各Roleの追加調査で参照する(`docs/ai/role-context-matrix.md`の原則と同じ)。

## 5. pilot(2026-07-23)

Claude Memoryの既存項目のうち、TODO6-0の判定ルールに該当する3件を`lessons/`へ書き出した(Claude Memory側は削除せず、Claude Code固有の詳細を含む完全版として残す。二重管理でなく異なる読者向けの書き出しとして扱う)。

- `lessons/rollback-cli-argument-convention.md`
- `lessons/destructive-operation-classification-criteria.md`
- `lessons/multilayer-escaping-and-novel-stack-verification.md`

`incidents/`・`decisions/`・`temporary/`は現時点で書き出す実例がないため空(README.mdのみ)。既存Claude Memoryの一括棚卸しは行わない。

## 関連

- `docs/ai/context-classification.md`(Context/Policy/Skillの分類、Knowledgeとの境界)
- `docs/ai/reviews/agent_skills_reorganization_plan.md` Phase6
