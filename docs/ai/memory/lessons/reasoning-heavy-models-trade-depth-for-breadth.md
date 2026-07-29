# 推論重視モデル(Claude 5シリーズ)は深掘りに強く、網羅性に弱い

## 教訓

Fable 5・Opus 5のような推論重視・thinking常時ONのモデルは、**1つの技術的前提を疑って掘り下げる作業には強いが、「列挙して漏れなく確認する」「同じ手順を最後まで一貫させる」という網羅性重視の作業には、体感で見えるほどの弱さがある**(2026-07-29、Yoshinobu指摘)。

原因はモデルの「賢さ」の欠如ではなく、**推論に割く分だけ、チェックリスト的な反復作業へ向ける注意が薄くなる**という性質だと考えられる(コンテキストの使われ方の非対称)。Sonnetのような相対的に軽いモデルは、単発の深い推論では劣る場面があっても、**同じ形式の確認を淡々と繰り返す作業では対等かそれ以上に機能する**。

## 根拠(2026-07-29、同一セッション内で複数回)

このセッション自体が実例になっている。Coordinator(Fable稼働)は、以下を含む「深く考えれば防げたはずの間違い」ではなく「やることリストの1項目を落とす」型のミスを繰り返した。

- `git add`のし忘れ2回(regnorm文書の一括改訂後、subagentへの依頼後)。
- **`docs/ai/reviews/knowledge_review_context_check/`案件で、subagentの最終報告をファイル保存せず要約だけで済ませる欠陥が、同一案件内で独立に2回発生した**(1回目: Reviewerの計画査読、2回目: Auditor自身の1回目報告)。`progress.md`「後続への申し送り」に詳細記録あり。

一方、Reviewer(Sonnet, medium)・Auditor(Sonnet, medium)は、この種の欠落を高い再現性で検出し続けた。特にAuditorは同一案件で**4回連続、性質の異なる記録欠落**(計画査読ファイル欠落 → Auditor自身の報告欠落 → 復元ファイル内の宙ぶらりん参照 → 進捗記録の記述放置)を1つずつ、独立に拾い切った(`docs/ai/reviews/knowledge_review_context_check/2026-07-29_007_audit_1.md`〜`2026-07-29_009_audit_5.md`)。

同日、Reviewerによる計画査読・差分レビューも、Coordinatorが見落とした宙ぶらりん参照や引用先の不在(層1相当の欠陥)を複数回検出している(`2026-07-29_002b_plan_review.md`Finding 1等)。

## 適用

- **Tier 3/4の判断・計画・技術的前提の反証はCoordinator(上位モデル)に残す**(`docs/ai/reviews/process_retrospective/2026-07-29_008_coordinator_model_tier_policy.md`)。この判断自体は変えない — 今回の教訓は「上位モデルが劣る」ではなく「上位モデルにも不得意な作業類型がある」という話である。
- **Reviewer / Auditorを「独立性のための儀式」ではなく「網羅性を補う実質的な防御」として扱う。** 今日のように同一案件で何度も差し戻しが起きても、それを工程の失敗と見なさない。差し戻しが繰り返し発生すること自体が、この設計が機能している証拠である。
- **Coordinator自身は、「サブエージェントの報告を受け取ったら最初にすること」のような手順を、自分の注意力だけで守れると期待しない。** 実際に今回、同じ手順の抜け(ファイル保存を要約より先にする)を2度繰り返した。頼れるのは自分の注意ではなく、Auditorのような外部の網羅性チェックである。
- **人間(Yoshinobu)が「網羅性が怪しい」と感じたときは、深掘りではなく列挙・確認が要る場面である可能性を疑う。** その勘は今回正しかった。

## 確度について

データ点はこのセッション1つ(2026-07-29)である。仮説として扱い、他のセッション・他の案件でも同型の失敗が観測されるかを見ていく。auto-memory `reference_model_selection_fable_vs_opus.md`(2026-07-26、Fable常用は見送りという古い結論)は、この教訓を踏まえて更新が必要。

## 関連

- `docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`(判断を当人に委ねず設計で作り込む、という同型の思想)
- `docs/ai/reviews/knowledge_review_context_check/progress.md`「後続への申し送り」
- `docs/ai/reviews/process_retrospective/2026-07-29_008_coordinator_model_tier_policy.md`
