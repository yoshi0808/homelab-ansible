# Knowledge運用(Phase6 TODO6-0〜6-3)

`docs/ai/reviews/agent_skills_reorganization_plan.md` Phase6の成果物。`docs/ai/memory/`配下のKnowledgeをどう分類し、どう昇格・廃止し、誰が読むかを決める。

## 1. 4層モデル(TODO6-0)

| 層 | 位置づけ |
|---|---|
| Core(`docs/ai/core.md`) | 全Role共通の不変原則 |
| **Knowledge**(`docs/ai/memory/`、本ファイルの対象) | プロジェクト全体で共有すべき知識。特定AI製品に紐づかない、リポジトリ内の共有資産 |
| Skill(`skills/`) | 再利用可能な能力・手順 |
| Claude Memory(`~/.claude/projects/.../memory/`) | Claude Code固有の経験・運用。Codex系Roleからは見えない |

**判定ルールは1つだけ**: 「この知識を知らないことで、Codex系Role(`implementer`/`reviewer`/`tester`/`techlead2`等)の判断や実装が変わるか」。

- Yes → Knowledge(`docs/ai/memory/`)へ書く。
- No(Yoshinobuとのコミュニケーションスタイル、Claude Code自身の作業習慣など、Claude Code固有の運用に閉じるもの)→ Claude Memoryのままでよい。

**Knowledgeは Claude Memoryのコピーではない**。Claude Memoryはこれまで通りClaude Codeが単独で活用し続け、そのうちCodex系Roleの判断にも必要になったものだけを都度Knowledgeへ書き出す(遅延移行)。既存Claude Memory(現在数十件)は一括移行しない。

## 2. Knowledgeの内部分類(TODO6-1)

Claude Memoryの`user`/`feedback`/`project`/`reference`とは別の分類体系である(型名を無理に揃えない)。

| 分類(ディレクトリ) | 内容 | 保存期間・参照範囲 | 例 |
|---|---|---|---|
| `incidents/` | 起きた事実そのもの | 昇格判断が付くまで保持。Lessonへ昇格したら本文をLessonへ寄せ、このファイルには昇格済み・参照先だけ残す | testerが誤ったinventoryを選びかけた |
| `lessons/` | 再発防止の学び(再利用可能) | 恒久。ただしSkillへ昇格したら参照はSkillへ寄せる(3節) | テストではinventoryを明示する |
| `decisions/` | 承認済み設計判断 | 恒久。前提が変わったら見直す(3節) | Shellは収集、判定はAnsible側 |
| `temporary/` | 作業中だけ必要な情報 | 案件クローズ時に削除 | request-42のテストが未完了 |

`incidents/`のファイル形式(ファイル名規則・記載項目・原因分類タグ)は`skills/incident-recording/SKILL.md`が正本。修正して正常動作の確認が取れた時点で1回記録する。

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
- **Temporaryの削除条件**: 紐づく案件(agmsgの依頼・`docs/ai/reviews/<target>/`)がクローズした時点で削除する。
- **Decisionの見直し**: 定期レビューはしない。前提条件(依存する環境事実・技術選定)が変わったとYoshinobu・Tech Lead・Coordinatorのいずれかが気づいた時点で見直す。
- **Incidentの月次振り返り**: Coordinatorが月次で`docs/ai/memory/incidents/`を振り返り、上記のPolicy/Skill直接昇格の要否を判断する。

## 4. Role別のKnowledge参照範囲(TODO6-3)

| Role | 参照するKnowledge |
|---|---|
| Coordinator | 全`decisions/`(重要度問わず)、Tech Lead統合結果に関わる`incidents/` |
| Tech Lead | 重要`decisions/`、担当領域(自trio)に関連する`lessons/`全般、委任判断に関わる`incidents/` |
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
