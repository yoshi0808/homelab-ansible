# Operations Context: agmsg委任・報告メッセージの形式

TODO5-3(Contextの遅延読み込み方法)・TODO5-4(Roleごとの出力フォーマット)の成果物。2026-07-22〜23の実運用(delegation skill草案の確定、Phase2/3/4の委任)で実際に使われた形式を、Coordinatorが明文化した(2026-07-23)。

## 1. Coordinatorからsubagentへの委任メッセージ形式(TODO5-3)

**2026-07-29、Tech Lead役廃止に伴い、委任元はCoordinatorに一本化した**(`docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md`)。Coordinatorが案件を委任するとき、次の項目を明示する。委任Skill(`docs/ai/reviews/agent_skills_reorganization_phase4_delegation_skill_draft.md`)§3の必須記載事項と同一。

```
【objective】何を達成するか(完了条件を含む)
【output format】成果物の形式・保存先
【scope】対象ファイル・対象外(他roleとの境界を明示)
【参照範囲】読むべきContext/Policyと、読まなくてよい範囲
【Tier】委任SkillのどのTierに該当するか、分解方針の要否
```

**Context指定の原則**: 起動時に読むContextは`docs/ai/core.md`・`docs/ai/role-routing-index.md`・`docs/ai/roles/<role>.md`のみに最小化する(全Roleが起動時READYで既に読了済み)。案件固有のContextは【参照範囲】で都度指定し、全体を毎回読ませない。Coordinatorのcontext指定に不足があれば、各Roleは追加調査してよい(`docs/ai/role-context-matrix.md`の原則)。

**実例**: 2026-07-22のPhase2/Phase3委任メッセージ(techlead/techlead2への各TODO委任。当時の常駐trio体制下の実例であり、現行のAgent tool subagent体制とは委任経路が異なる)。

## 2. Role別の完了報告形式(TODO5-4)

**2026-07-29以前は、Implementer/Reviewer/Testerの報告先は「担当Tech Lead」であり、Tech Leadがそれらを統合してCoordinatorへ報告する2段構造だった。Tech Lead廃止に伴い、下記3形式の宛先はいずれもCoordinatorへ一本化した。** 統合はCoordinator自身が行うため、旧「Tech Lead → Coordinator(統合結果)」形式は廃止した。

### Implementer → Coordinator(実装報告)

```
変更ファイル: [パス一覧]
実装内容: [要点]
自己検証: [実施した確認]
未検証事項: [あれば]
```

### Reviewer → Coordinator(レビュー指摘、差分レビュー・計画査読とも共通)

```
判定: [Approve/NEEDS_CHANGES]
指摘: [must-fix/suggestion/nitで重大度別に整理、severity/location/issue/reasonを含む]
確認した対象: [レビュー範囲]
対象外: [scope外として送った項目があれば]
```

### Tester → Coordinator(テスト結果)

```
判定: [PASS/FAIL]
実施した検証: [コマンド・範囲]
未実施項目: [あれば、理由も]
残存リスク: [あれば]
```

**共通原則**: 受信側が追加質問なしで次の作業に移れるだけの情報を含める(計画書TODO5-4完了条件)。中間成果物・詳細な調査ログはagmsg本文に貼らず、ファイルパスだけを渡す(`docs/ai/reviews/`配下の該当ファイル参照)。

## 3. 分解方針の確定(Tier3以上)

2026-07-22〜2026-07-29は、Tier3以上の案件で着手前に短い分解方針をTech LeadからCoordinatorへ報告し、承認を得てから実行する運用だった。**2026-07-29のTech Lead廃止により、分解方針はCoordinator自身が確定するため、この報告は不要になった。** 代わりにReviewerによる計画査読と、Coordinatorの「計画受領時のゲート」(`docs/ai/roles/coordinator.md`)が同じ役割(対象Role、各Roleの作業範囲、想定所要時間の確認)を担う。

## 関連

- `docs/ai/reviews/agent_skills_reorganization_phase4_delegation_skill_draft.md`(Tier判定・委任時の必須記載事項の正本)
- `docs/ai/role-context-matrix.md`(誰が何をいつ読むか)
- `docs/ai/roles/*.md`(各Roleの成果物と返却先の定義)
