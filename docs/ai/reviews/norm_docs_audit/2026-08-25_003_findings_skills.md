# 規範文書横断監査 — skills/*/SKILL.md・.claude/agents/*.md 群 findings

日付: 2026-08-25
担当群: `skills/*/SKILL.md`(14本)、`.claude/agents/*.md`(4本)
共通の背骨(CLAUDE.md / AGENTS.md / core.md / context-classification / role-context-matrix / memory-classification / roles 6本)との突合を含む。
技術的正否は判定していない。文書どうしの整合のみ。

---

## 1. 矛盾

### 1-1. subagent-briefing が「依頼文へ複製しない」と宣言した共通則を、依頼文へ書けと指示している

- `skills/subagent-briefing/SKILL.md:12` —「**全subagentへ常に適用される共通則は `docs/ai/core.md`「subagentが共通して守ること」が正本であり、依頼文へ複製しない。** 依頼文に書くのは、そこに無いもの — 案件固有の書込先と、Role文書より**狭める**制限だけである。」
- `skills/subagent-briefing/SKILL.md:26` —「**書くもの**: 各subagentが触れてよいパス、`git status`に現れる他方の未追跡ファイルを**自分の成果物として報告・削除・整形しない**旨、`git add`/`commit`/`push`を行わない旨。」
- `docs/ai/core.md:136` —「他のsubagentが並行して作る未追跡ファイルを、自分の成果物として報告・削除・整形しない。」/ `docs/ai/core.md:64-65` —「`git add` を行うのはCoordinatorだけである。」「`git commit` / `git push` は…**subagentは承認の有無にかかわらず行わない。**」/ `docs/ai/core.md:131` —「**依頼文はこれらを複製せず、案件固有の制限だけを書く。**」

L26 が依頼文へ書けとする2項目(未追跡ファイル・git操作)は、いずれも core.md「subagentが共通して守ること」に既にある共通則そのものであり、同じSkillの L12 と core.md:131 の「複製しない」指示と両立しない。

### 1-2. architecture-decision-record が `docs/ai/adr/` を「新設予定」と述べるが、他の入力文書と現物は既設として扱っている

- `skills/architecture-decision-record/SKILL.md:40` —「新設予定の`docs/ai/adr/`。」
- `docs/ai/roles/coordinator.md:35` —「根拠は `docs/ai/adr/010-role-model-effort-allocation.md`。」
- 現物: `docs/ai/adr/` は実在し、`001`〜`010` の10本のADRを持つ(`ls docs/ai/adr/` で確認)。

同じ入力群の中で、片方は将来形、片方は既存の正本として同一ディレクトリを指しており、Skillの記述が現状と両立しない。

### 1-3. incident-recording の description「型のみ定める」と、本文の「運用ルール」節が両立しない

- `skills/incident-recording/SKILL.md:3`(description)—「分類・保存期間・昇格条件は docs/ai/memory-classification.md が正本、このSkillは**Incidentファイル自体の型のみ定める**。」
- `skills/incident-recording/SKILL.md:54-59` —「## 運用ルール」節。「月次のタグ集計は`状態: 解決済み`のファイルのみを数える。」「同じ`原因分類`タグが複数件で繰り返し検出された場合、Lessonを経由せず直接、該当業務のPolicy改訂…またはSkill新設・改訂…を検討する。」

description は自らを「型のみ」と限定するが、本文は月次振り返りの集計・昇格の運用規則を規定しており、自己宣言と実内容が食い違う(この運用規則の実体が別正本と二重になっている点は 3-2 に分離した)。

### 1-4. role-context-matrix「Auditorは次の4つに限る」の直後の表が3行しかない

- `docs/ai/role-context-matrix.md:38` —「Auditorは**案件クローズ時に1回だけ**起動し、読むのは**次の4つ**に限る。」
- 同 `docs/ai/role-context-matrix.md:40-44` — 直後の表の行は「案件フォルダ `docs/ai/reviews/<target>/` の全成果物」「`docs/ai/status.md`(現在地)」「成果物から**参照されている先**」の**3つ**だけ。

数の宣言と列挙が一致せず、4つ目が削除されたのか、数え方が別なのかを読者は判別できない(背骨内の指摘。担当群との突合中に検出した)。

---

## 2. 宙ぶらりん参照

### 2-1. subagent-briefing が自ファイル内の存在しない「参照」節を指す

- `skills/subagent-briefing/SKILL.md:8` —「規範の中身は正本を参照する(**下記「参照」**)。」
- 同ファイルの見出し一覧(`grep '^#'`): `実行identityと権限境界 / 渡すもの / 渡さないもの / 並行作業の境界 / 所要時間が前景の上限を超えうる単位 / 自己検証 / 報告形式 / Role別の差分 / 差し戻し時の再起動 / 型が塞がないもの / AC1対応表` —「参照」という節は存在しない。

### 2-2. goal-tracking が現行 core.md に存在しない「on the horizon」を指す

- `skills/goal-tracking/SKILL.md:18` —「core.mdの「on the horizon」的な位置づけと相性が良い。」
- `docs/ai/core.md` — `grep -n "on the horizon" docs/ai/core.md` は0件。現行 core.md にこの節・語は存在しない(旧core.mdは2026-07-26に退役済みで、この記述はその旧版を指したまま残っている)。

### 2-3. 4本のSkillが「重大度分類」の正本として reviewer.md を指すが、reviewer.md に重大度分類の定義が無い

- `skills/code-review/SKILL.md:35` —「重大度分類・エスカレーション基準は `docs/ai/roles/reviewer.md` を参照する。」
- `skills/ansible-correctness-review/SKILL.md:32` —「重大度、返却先、レビュー独立性は`docs/ai/roles/reviewer.md`を正本とする。」
- `skills/document-norm-review/SKILL.md:116` —「重大度分類・返却先は`docs/ai/roles/reviewer.md`が正本」
- `skills/test-gap-review/SKILL.md:35` —「重大度と出力形式は`docs/ai/roles/reviewer.md`および`skills/code-review/SKILL.md`に従う。」
- `docs/ai/roles/reviewer.md` に「重大度」が現れるのは2箇所のみ:`:15`「指摘を重大度、根拠、対象箇所、必要な対応とともに整理する。」/ `:32`「重大度別findings」。分類そのもの(何段階か、各段の意味)はどこにも定義されていない(`grep -n "Critical\|Severity" docs/ai/roles/reviewer.md` は0件)。

参照先ファイルは実在するが、指されている規則(重大度分類)がそこに存在しない。`skills/code-review/SKILL.md:21` の出力表は `Severity` 欄を要求するため、書き手はどの尺度で埋めるかをどの正本からも得られない。

### 2-4. coordinator.md が status.md の存在しない節「載せていないもの」を指す

- `docs/ai/roles/coordinator.md:80` —「やらないと決めたことは `docs/ai/status.md`「載せていないもの」が持つ。」
- `docs/ai/status.md` の見出しは「このファイルの規律 / Now(進行中)/ Next(着手候補) — 工程・体制 / Next(着手候補) — システム・運用」のみで、「載せていないもの」という節は無い(`grep -n "載せていない" docs/ai/status.md` は0件。status.md本文は入力にしていないが、参照先実在確認として見出しのみ確認した)。

(背骨内の指摘。担当群との突合中に検出した。)

---

## 3. 正本の二重化

### 3-1. subagent-briefing が core.md の規範文を逐語で再掲している(ポインタなし)

- `skills/subagent-briefing/SKILL.md:73` —「この型が塞ぐのは書き落としまでで、解釈による逸脱は塞がない。…実効的な境界は文章ではなく、能力の不在(鍵・到達先・wrapperが存在しないこと)で作る。」
- `docs/ai/core.md:39` —「実効的な境界は文章ではなく、能力の不在(鍵・到達先・wrapperが存在しないこと)で作る。」/ `docs/ai/core.md:143` —「これで塞げるのは書き落としまでで、解釈による逸脱は塞げない。」

同一の規範文が2箇所に本文として存在し、どちらにも他方への参照が無いため、片方だけが直る経路がある(`docs/ai/core.md:127`「複製した時点で、片方だけが直る経路ができる」に照らして)。

### 3-2. incident-recording「運用ルール」が memory-classification の月次振り返り規則を本文で再掲している

- `skills/incident-recording/SKILL.md:57-58` —「月次のタグ集計は`状態: 解決済み`のファイルのみを数える。`調査中`の原因分類は未確定のため集計を歪める。」「ただし`調査中`のまま滞留している件数と経過日数は別途報告する。滞留自体が検出対象。」
- `docs/ai/memory-classification.md:98` —「`解決済み`のみ`原因分類`タグを集計する(`調査中`のタグは未確定で集計を歪めるため)。`調査中`は滞留件数と経過日数を報告する(滞留自体が検出対象)。」
- 同様に `skills/incident-recording/SKILL.md:59`(直接Policy/Skill昇格の条件)は `docs/ai/memory-classification.md:82` の再掲。

Skill側の L60 は「昇格ルールの**全体像**は…3節が正本」と添えるが、L57-59 自体はポインタでなく規則本文の複製であり、正本改訂時にSkill側だけが古く残る経路がある。

---

## 4. 読み取れない箇所

### 4-1. subagent-briefing「AC1対応表」の「AC1」が、このSkillからは何か判別できない

- `skills/subagent-briefing/SKILL.md:75-77` —「## AC1対応表 / 過去に実際起きた3クラスの逸脱を、どの章がどう塞ぐか。/ | AC1のクラス | 塞ぐ章 | どう塞ぐか |」

「AC1」はこのSkill内で定義も参照もされておらず、入力文書群のどこにも現れない。実体は `docs/ai/reviews/subagent_briefing/2026-07-28_001_requirement.md:43` の受入条件AC1だが、Skillはそこを指しておらず、読者は表の見出しが何の識別子か判別できない。

---

## 5. 群固有: Skillへの埋め込み / agent定義への規範複製

### 5-1. test-strategy に環境固有の構成情報(実行ユーザー名・sandbox構成)が埋め込まれている

- `skills/test-strategy/SKILL.md:26-27` —「Testerが自分のsandboxからplaybookを実行する際は、temp pathを実行ユーザーごとに分離する。固定パスにすると別ユーザー(`ann` / `yoshi`)の残骸と衝突してUNREACHABLEになる。」
- `docs/ai/context-classification.md:73` —「原則、ホスト名・構成情報はSkill(…)へ書かない。以下の両方を満たす場合のみ例外とする。」/ 同 `:78` —「例外を適用する場合は、そのSkillのコメントまたはREADMEに「ホームラボ固有の補足」である旨を明記し、汎用部分と分離する」

ansy上の実行ユーザー名2つとTester sandboxの構成事情という環境固有情報がSkill本文にあり、§4の例外を適用したとしても要求される「ホームラボ固有の補足」の明記・分離が無い。

### 5-2. duplication-reuse-check が Coordinator/Reviewer の責務分担と Reviewer への制限を定義している

- `skills/duplication-reuse-check/SKILL.md:18-19` —「**発見・指示はCoordinatorが担う**: requirement作成・タスク分解時に…再利用対象をrequirementへ明記する。/ **Reviewerは照合のみ**: 「指定された既存資産を実装が実際に使ったか」を確認する軽量な検査に限定する。**全リポジトリ横断検索はReviewerに行わせない。**」
- `docs/ai/core.md:98` —「Skillは「作業をどう進めるか」を定義する。環境台帳や**Roleの権限をSkillへ埋め込まない**。」

「Coordinatorが担う」「Reviewerに行わせない」というRole間の権限・責務の割当がこのSkillにしか書かれておらず(`docs/ai/roles/reviewer.md`・`coordinator.md`に対応する記述は無い)、Role権限の実質的な正本がSkill側に置かれている。

### 5-3. .claude/agents/ 4定義すべてが、core.md の規範文(対話ログ非永続・成果物のリポジトリ保存)を本文に複製している

- `docs/ai/roles/coordinator.md:39` —「**body に置いてよいのは、正本へのポインタと、Roleごとの成果物ファイル名の対応だけである。**」
- `.claude/agents/auditor.md:15` —「あなたはCoordinatorが起動したsubagentである。**会話の過程は永続しないので**、**判定と指摘は案件のaudit記録ファイルへ書き切る**。最終メッセージはCoordinatorへの報告であり、それ自体は記録として残らない。」(同型の文が `.claude/agents/implementer.md:15`、`.claude/agents/reviewer.md:15`、`.claude/agents/tester.md:16` にもある)
- `docs/ai/core.md:131` —「subagentの対話ログは永続しない前提とする。」/ `docs/ai/core.md:133` —「成果物本文と監査証跡は必ずリポジトリ内へ保存する。判断の根拠を最終報告だけに残さない。」

「〜記録ファイルへ書き切る」の成果物ファイル名対応は許容範囲だが、その前後の「会話の過程は永続しない」「最終報告は記録として残らない」は core.md「subagentが共通して守ること」の規範の言い換え複製であり、coordinator.md:39 が許すポインタと成果物対応のどちらでもない。

---

## 未確認(確信が持てない・解釈が割れる)

- **ansible-implementation-style:143 のReviewerへの適用拡張** —「本Skillは表現・スタイルレベルの基準であり、Reviewer/Testerの検査基準には拡張しない。**ただし上記「check_modeの実装上の落とし穴」はReviewerも確認対象とする**」。Roleの確認義務をSkill側で定めており core.md:98 と同型に見えるが、`docs/ai/policies/ansible_test_safety_policy.md:63`(TS-028)が同節の併読を義務付けており、Policy経由の正本があるとも読めるため、埋め込み違反かどうか断定できない。
- **subagent-briefing:54 の括弧書き** —「(詳細設計・機能分割・インターフェースの確定は**現在Coordinator自身の責務**であり、subagentへは渡さない)」。Role責務の記述がSkillにあるが、`docs/ai/roles/coordinator.md:7`「どこまで分解し、誰へ何を委任するかはCoordinatorが決める」の敷衍とも読め、独立した権限定義と断定できない。「現在」という時制の語も、規範か状態の記述かを曖昧にしている。
- **skills/goal-tracking/SKILL.md:37 の適用先** —「構想中の`iac_coverage.md`」。ファイルは実在しない(`find`で確認)が、「構想中」と自己申告しているため宙ぶらりん参照とは断定しなかった。2-2 と同じく旧core.md時代の記述が残っている可能性はある。

---

## 実在確認済みで指摘に該当しなかった主な参照(記録)

各SKILL.md・agent定義が指す次の参照先は実在を確認した: `docs/ai/policies/ansible_test_safety_policy.md` TS-028(`skills/ansible-implementation-style`との相互参照は両側とも成立)、`docs/ai/policies/execution_boundary_policy.md` §4.3/EXEC-002、`docs/ai/policies/cert_renew_policy.md` CERT-017、`scripts/check-doc-consistency.py` check2(agent frontmatter `model:`/`effort:` は coordinator.md の表と4件とも一致)、`scripts/session-recurrence-record.py`、`scripts/check-staged-yaml.py`、`roles/knowledge_review`・`playbooks/knowledge_review.yml`、`roles/prometheus_update_check`(upgrade/manual_rollback/discover_backups)、`roles/recovery_exec/files/recovery-loki-helper`、`roles/proxmox_snapshot_check/tasks/main.yml`、`playbooks/recovery_monitoring_check.yml`、`roles/recovery_push/tasks/drill_setup.yml`、`roles/common_slack/tasks/notify.yml`、`playbooks/README.md`、`docs/ai/context/operations/`(healthcheck / code-delivery-to-production / agent-messaging / operator-request-channel)、`docs/ai/context/system/semaphore.md`、document-norm-review・requirements-analysis が根拠として引く `docs/ai/reviews/` 配下および `docs/ai/memory/lessons/` 配下の全ファイル、`.claude/skills/` の14本の相対symlink(全skillと対応)。
