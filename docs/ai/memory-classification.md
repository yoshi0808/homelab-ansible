# Knowledge運用

`docs/ai/memory/`配下のKnowledgeをどう分類し、どう昇格・廃止し、誰が読むかを決める。

## 1. 層モデル

| 層 | 位置づけ |
|---|---|
| Core(`docs/ai/core.md`) | 全Role共通の不変原則 |
| **状態**(`docs/ai/status.md`、および影響先のコード・Policy・Contextの当該箇所) | 知識ではなく**現在地**。進行中の作業、観測待ち、着手候補。可変であり、repoの現物で真偽を確かめられる |
| **Knowledge**(`docs/ai/memory/`、本ファイルの対象) | プロジェクト全体で共有すべき知識。特定AI製品に紐づかない、リポジトリ内の共有資産 |
| Skill(`skills/`) | 再利用可能な能力・手順 |
| Claude Memory(`~/.claude/projects/.../memory/`) | Coordinator(このClaude Codeセッション)固有の経験・運用。Coordinatorが起動するAgent tool subagentは前提としてこの内容を見ない(subagentは都度コールドスタートし、渡されたprompt以外の文脈を持たない) |

**判定は2段階で行う。**

**第0段 — 知識か、状態か。** 「repoの現物(コード・commit・reviews)を見れば真偽を確かめられるか」を先に問う。確かめられるものは**状態**であり、Knowledgeでもauto-memoryでもなく`docs/ai/status.md`か「使う場所」(該当するコード・Policy・Contextの当該箇所)へ置く。判断の順序は次のとおり。

- 影響先のコード・Policy・Contextに書ける → **そこへ書く**(第一選択。変更する人の目に必ず入る)
- 書ける場所が無い(将来の日付やイベントを待つ、複数箇所にまたがる) → **`docs/ai/status.md`**
- repoでは確かめようがない(Yoshinobuの判断傾向、Coordinator自身の作法) → **知識**として第1段へ進む

**auto-memoryに「残タスク」「将来課題」「完了済み」を書かない。** 検証されないまま索引に残り、repoの現物と食い違う。

**第1段 — 誰が読む知識か**: 「この知識を知らないことで、Coordinator自身の判断、またはCoordinatorが起動するsubagent(Implementer/Reviewer/Tester役)の判断や実装が変わるか」。

- Yes → Knowledge(`docs/ai/memory/`)へ書く。
- No(Yoshinobuとのコミュニケーションスタイル、Coordinator自身の作業習慣など、Coordinatorの運用に閉じるもの)→ Claude Memoryのままでよい。

**KnowledgeはClaude Memoryのコピーではない**。Claude MemoryはこれまでどおりCoordinatorが単独で活用し続け、そのうちsubagentの判断にも必要になったものだけを都度Knowledgeへ書き出す(遅延移行)。既存Claude Memory(現在数十件)は一括移行しない。

## 2. Knowledgeの内部分類

Claude Memoryの`user`/`feedback`/`project`/`reference`とは別の分類体系である(型名を無理に揃えない)。

| 分類(ディレクトリ) | 内容 | 保存期間・参照範囲 | 例 |
|---|---|---|---|
| `incidents/` | 起きた事実そのもの | 昇格判断が付くまで保持。Lessonへ昇格したら本文をLessonへ寄せ、このファイルには昇格済み・参照先だけ残す | testerが誤ったinventoryを選びかけた |
| `lessons/` | 再発防止の学び(再利用可能) | 恒久。ただしSkillへ昇格したら参照はSkillへ寄せる(3節) | テストではinventoryを明示する |
| `decisions/` | 承認済み設計判断 | 恒久。前提が変わったら見直す(3節) | Shellは収集、判定はAnsible側 |
| `temporary/` | 作業中だけ必要な情報 | 案件クローズ時に削除 | request-42のテストが未完了 |

`docs/ai/memory/knowledge-review-log.md`は上の4分類に属さない。月次振り返りの**測定値だけ**を月ごとに積む(3節「月次振り返りの対象と手順」)。

`incidents/`のファイル形式(ファイル名規則・記載項目・原因分類タグ・`状態`)は`skills/incident-recording/SKILL.md`が正本。**記録は気づいた時点で開始し、原因判明後に同じファイルを完成させる2段階。**

### `lessons/`の「再発記録」節

**本節が契約の正本である。** 各lessonの`## 再発記録`節は機械だけが書き、人は手で書かない。節の中身は見出しと表だけとし、この契約を各ファイルへ複製しない。

追記するのは**別体**であり、セッション終了時にtranscriptを読み、**次のいずれかが実際に起きたときだけ**1行足す。無ければ何もしない。

1. Policy(`docs/ai/policies/*_policy.md`)の許可・禁止・停止条件に反した。
2. harnessの安全機構(permission classifier / `permissions.deny` / `autoMode`)に止められた。
3. 規範文書または依頼文に書いてあることをしなかった。

**話題がlessonに似ていることは記録の理由にならない。** 調べた・検証した・見つけた、は記録しない。lessonを正しく適用できているものも記録しない。**反した規範の所在を書けない項目は記録しない**(機械が落とす)。

**回数は推定であって測定ではない。** 分類器はLLMであり、見落とせば沈黙し、過検出すれば水増しする。**回数だけを昇格の根拠にしない。**

実装は`scripts/session-recurrence-record.py`(`SessionEnd` hook、`.claude/settings.json`に登録)。

## 3. 昇格・廃止ルール

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

- **Incident→Lesson**: 上記条件を満たした時点でCoordinatorが判断する。昇格後、元のIncidentファイルは本文を削除し「Lesson `<path>`へ昇格済み」の1行だけ残す(二重保持しない)。
- **Lesson→Skill**: 単なる注意喚起ではなく、具体的な手順・テンプレートとして再利用できる形に育った場合。昇格後、Lesson側は「Skill `<path>`へ昇格済み」の1行だけ残す。
- **Skill→core**: 全Roleが例外なく毎回必要とする不変原則になった場合のみ。ハードルは高く保ち、安易に昇格させない。
- **Incident→Policy/Skill(直接、Lessonを経由しない)**: Incidentの`原因分類`タグ(`skills/incident-recording/SKILL.md`参照)が月次振り返りで複数件にわたり繰り返し検出された場合、個別の再利用可能な気づきを待たず、直接Policy改訂(許可/禁止/停止条件の明文化が必要な場合)またはSkill新設・改訂(再利用手順の整備が必要な場合)を検討する。判断はCoordinatorが行う。一度きりの気づきは従来どおりLesson経由とする。
- **昇格時は根拠を先に移送してから縮約する。** 上記の「1行だけ残す」を機械的に適用すると、**なぜその教訓に至ったかが失われる**。順序は「①昇格先へ本文と根拠(具体的な事例・日付・失敗の経緯)を書く → ②元を1行へ縮約する」であり、逆順や同時に行わない。根拠のない規範は、前提が変わったときに見直す手がかりを持たない。
  - 全体を昇格させたときは元を1行へ縮約する。**一部だけを昇格させたときは全体を縮約しない**(残る項目は根拠として存置する)。
  - 縮約後は、元ファイルへの被参照が壊れていないことを検索で確認する(`skills/document-norm-review/SKILL.md`の宙ぶらりん参照の項)。
- **Temporaryの削除条件**: 紐づく案件(`docs/ai/reviews/<target>/`)がクローズした時点で削除する。
- **Decisionの見直し**: 定期レビューはしない。前提条件(依存する環境事実・技術選定)が変わったとYoshinobu・Coordinatorのいずれかが気づいた時点で見直す。
- **Incidentの月次振り返り**: Coordinatorが月次で`docs/ai/memory/incidents/`を振り返り、上記のPolicy/Skill直接昇格の要否を判断する。

### 月次振り返りの対象と手順

**本番影響が出ずIncidentにならなかった学びも網から漏らさない**ため、対象は`incidents/`だけに限らない。

**対象**: `docs/ai/memory/incidents/`に加え、**前回の振り返り以降にCoordinatorのClaude Memoryへ蓄積された項目**、および工程を何周も往復した案件の`docs/ai/reviews/<target>/`記録。

**捕捉と昇格を分ける**: 教訓の捕捉は即時に行う(詳細は時間が経つと失われる)。月次で行うのは**昇格判断**であり、初回記録の場ではない。

**Incidentの`状態`は3値**(`調査中` / `解決済み` / `未解決`)。形式は`skills/incident-recording/SKILL.md`が正本。月次振り返りでの扱いは状態ごとに異なる。`解決済み`のみ`原因分類`タグを集計する(`調査中`のタグは未確定で集計を歪めるため)。`調査中`は滞留件数と経過日数を報告する(滞留自体が検出対象)。`未解決`(調査打ち切り)は集計にも滞留にも入れず別枠で一覧し、打ち切り判断が今も妥当かを問い直す。

**振り返りで各項目を3つに仕分ける。**

| 仕分け | 判定基準 | 行き先 |
|---|---|---|
| 再利用可能な**手順** | 注意喚起でなく、次回そのまま使えるチェックリスト・テンプレートになっているか | `skills/` |
| この**環境独自の事実** | このホームラボ固有の落とし穴・構成事実で、知らないと判断を誤るか | `docs/ai/memory/lessons/` または`docs/ai/context/` |
| **Yoshinobuの考え方** | 承認境界・優先順位・役割分担など、人の判断基準そのものか | `docs/ai/memory/decisions/` または Policy |

**判定ルールは1節と同じ**: まず第0段(知識か状態か)、次に「この知識を知らないことで、Coordinatorが起動するsubagentの判断や実装が変わるか」。Yesならリポジトリへ書き出す。Noならauto-memoryのままでよい。

**状態の突合も月次で行う。** 対象は2つある。

1. **auto-memory側**: 残っている状態記述(「残:」「将来課題」「完了済み」)をrepoの現物と突き合わせ、①既に解決しているもの、②`docs/ai/status.md`へ移すべきもの、③影響先のコードやContextへ書くべきもの、に仕分ける。**auto-memoryは状態を持たない**のが到達点であり、月次はその漏れを回収する場である。
2. **`docs/ai/status.md`自身**: 各行の検証手段を実際にたどり、記述が現物と合っているかを確かめる。このファイルの更新トリガはCoordinatorセッション内の3イベントだけなので、**セッションを経由せずに現実が変わった場合**(Yoshinobuが手動で片付けた、外部システムの状態が変わった)は誰も気づかない。月次がその唯一の周期的な検知点である。

**起動はtimerが行う。** `roles/knowledge_review`が配置する`ansible-knowledge-review.timer`が毎月26日にansyで発火し、`playbooks/knowledge_review.yml`がきっかけの通知を出す。振り返り自体は人がCoordinatorとの対話セッションで行う。

**期日の正本はCoordinatorのMEMORY.md先頭の1行**であり続ける。timerは起動機構、MEMORY.mdは実施記録という分担で、振り返り自身が最後にこの行を更新する。二重管理を避けるため、期日を他所へ書かない。

**書き出し先**: `docs/ai/memory/`・`docs/ai/context/`・`skills/`・`docs/ai/status.md`。`docs/ai/policies/`本文の改訂はYoshinobuの領域であり、必要なら提案として起こす。**状態の突合で見つかった差分は、その場で`docs/ai/status.md`へ反映する。**

**測定値は`docs/ai/memory/knowledge-review-log.md`へ1節足す。** 後から計算し直せないため、この系列でしか対応の有効性を判定できない。**まず前回の節の「次月に見るもの」を開いて突き合わせるところから始め**、最後に今回の節を書く。値は着手時に測る(振り返り自身が動かす前の状態が系列になる)。**判断はそこへ書かず、行き先を指す** — やることは`docs/ai/status.md`、やらないことは`docs/ai/memory/decisions/rejected-proposals.md`、原因の断定は`docs/ai/memory/decisions/`の個別ファイル。

**Context陳腐化チェックも行う。** 上記3系統(Incident/auto-memory/工程往復案件)とは別軸で、`docs/ai/context/system/`・`docs/ai/context/operations/`・`docs/ai/context/ansible/repository-overview.md`が`roles/`・`playbooks/`・`inventories/homelab/`の現物と整合しているかを検査する。手順は次の4つ。

1. 各Context文書から、明示的に名指しされているrole名・playbook名・host名を拾う。
2. 拾った名前が`roles/`・`playbooks/`・`inventories/homelab/hosts.yml`に実在するか確認する。存在しなければリネーム・削除された可能性が高く、指摘対象とする。
3. 実在するものについて、Context文書が述べる「処理順序」「依存関係」「安全上の注意」のうち、対象の`tasks/main.yml`または`defaults/main.yml`から**明確に矛盾すると判断できるものだけ**を指摘する。解釈が割れるもの・断定できないものは指摘しない。
4. **全文の逐語照合は求めない。** 前回以降にauto-memoryや案件記録で言及された形跡があるrole/playbookを優先し、終わらない範囲は「未確認」として次回へ持ち越す。

**指摘は矛盾の指摘に留め、Context文書を自動で書き換えて「直す」ことは求めない。** Policyの技術的正否はこのチェックの範囲外である。

## 4. Knowledgeを読むのはCoordinatorだけである

**`docs/ai/memory/`を読むのはCoordinatorに限る。** 全`decisions/`(重要度問わず)、統合結果に関わる`incidents/`、対象領域の`lessons/`を、着手時にCoordinator自身が確認する。起動時に全件を読み込むことはしない。

**subagent(Implementer / Reviewer / Tester / Auditor)は読まない。** `docs/ai/memory/`はRole別に分かれておらず、subagentは毎回コールドスタートで、どれが対象に関連するかを判断する材料を持たない。「必要時に対象関連のものを読む」という以前の定め方は、実質「読まない」であった。

**代わりに、蒸留して渡す。** 各Roleが常に持つべき型は`docs/ai/roles/<role>.md`へ、手順として一般化できるものは`skills/`へ、対象業務の許可・禁止は`docs/ai/policies/`へ落とす。昇格のラダーは3節が正本であり、**この昇格を行う機会が月次振り返りと、規範文書を見直す案件である。** 読ませる側ではなく渡す側で設計する。

## 関連

- `docs/ai/context-classification.md`(Context/Policy/Skillの分類、Knowledgeとの境界)
