# Operations Context: agmsg委任・報告メッセージの形式

TODO5-3(Contextの遅延読み込み方法)・TODO5-4(Roleごとの出力フォーマット)の成果物。2026-07-22〜23の実運用(delegation skill草案の確定、Phase2/3/4の委任)で実際に使われた形式を、Coordinatorが明文化した(2026-07-23)。

## 1. Tech Leadへの委任メッセージ形式(TODO5-3)

Coordinator(またはTech Lead)が案件を委任するとき、次の項目を明示する。委任Skill(`docs/ai/reviews/agent_skills_reorganization_phase4_delegation_skill_draft.md`)§3の必須記載事項と同一。

```
【objective】何を達成するか(完了条件を含む)
【output format】成果物の形式・保存先
【scope】対象ファイル・対象外(他roleとの境界を明示)
【参照範囲】読むべきContext/Policyと、読まなくてよい範囲
【Tier】委任SkillのどのTierに該当するか、分解方針の要否
```

**Context指定の原則**: 起動時に読むContextは`docs/ai/core.md`・`docs/ai/role-routing-index.md`・`docs/ai/roles/<role>.md`のみに最小化する(全Roleが起動時READYで既に読了済み)。案件固有のContextは【参照範囲】で都度指定し、全体を毎回読ませない。Tech LeadのContext指定に不足があれば、各Roleは追加調査してよい(`docs/ai/role-context-matrix.md`の原則)。

**実例**: 2026-07-22のPhase2/Phase3委任メッセージ(techlead/techlead2への各TODO委任)。

## 2. Role別の完了報告形式(TODO5-4)

### Tech Lead → Coordinator(統合結果)

```
結果: [完了/NEEDS_CHANGES/保留]
成果物: [ファイルパス]
要点: [何をしたか、主要な指摘・修正があれば]
所要時間: [着手から完了まで]
未解決事項: [あれば]
commit/push: [実施有無]
次のアクション: [あれば]
```

### Implementer → Tech Lead(実装報告)

```
変更ファイル: [パス一覧]
実装内容: [要点]
自己検証: [実施した確認]
未検証事項: [あれば]
```

### Reviewer → Tech Lead(レビュー指摘)

```
判定: [Approve/NEEDS_CHANGES]
指摘: [must-fix/suggestion/nitで重大度別に整理、severity/location/issue/reasonを含む]
確認した対象: [レビュー範囲]
対象外: [scope外として送った項目があれば]
```

### Tester → Tech Lead(テスト結果)

```
判定: [PASS/FAIL]
実施した検証: [コマンド・範囲]
未実施項目: [あれば、理由も]
残存リスク: [あれば]
```

**共通原則**: 受信側が追加質問なしで次の作業に移れるだけの情報を含める(計画書TODO5-4完了条件)。中間成果物・詳細な調査ログはagmsg本文に貼らず、ファイルパスだけを渡す(`docs/ai/reviews/`配下の該当ファイル参照)。

## 3. 分解方針の事前報告(Tier3以上)

Tier3以上の案件は、着手前に短い分解方針をTech LeadからCoordinatorへ報告し、承認を得てから実行する(2026-07-22の複数案件で実証済みの運用)。分解方針には対象Role、各Roleの作業範囲、想定所要時間の目安を含める。

## 関連

- `docs/ai/reviews/agent_skills_reorganization_phase4_delegation_skill_draft.md`(Tier判定・委任時の必須記載事項の正本)
- `docs/ai/role-context-matrix.md`(誰が何をいつ読むか)
- `docs/ai/roles/*.md`(各Roleの成果物と返却先の定義)
