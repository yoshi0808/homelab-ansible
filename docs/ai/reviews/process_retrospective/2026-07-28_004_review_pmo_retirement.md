# PMO退役・体制作り直し — Reviewer逐行照合(Tier `1+R`のR)

- 作成: 2026-07-28 Reviewer(subagent、コールドスタート、独立セッション)
- 対象: `docs/ai/reviews/process_retrospective/2026-07-28_003_pmo_retirement.md` の決定に基づく規範変更一式(`git diff --cached` の全差分)
- 前提記録: `2026-07-28_003_pmo_retirement.md`(決定と根拠)、`git show HEAD:docs/ai/roles/pmo.md`(旧PMO本文、責務対応表の元)
- 制約: 対象は変更していない。実ホストへ触れていない。`git commit`/`git push`は行っていない。

## Summary

規範9ファイル+新規Auditor 2ファイルの差分を通読し、旧`pmo.md`の責務を1項目ずつ新体制の行き先へ対応付けた。**責務の消失は無い**(意図的に捨てた「走行中の定期点検」を除く)。数の主張(「4つに限る」「9ファイル」「代替3つ」)はいずれも実物の行数・列挙数と一致した。宙ぶらりん参照も深刻なものは無かった(進行中案件のPMO言及はすべて「旧体制のまま完走させる」という決定どおりの意図的な残置)。

一方で、**Coordinator自身の役割定義の中核行(Tier 3/4のフロー要約)が今回の変更で一度も触れられておらず、新設した2工程(2人目のTech Leadによる計画査読、Auditorのクローズ受入)を欠いたまま**になっている。また「Auditorを誰が起動するか」が他Roleほど明示されておらず、`effort-baseline.md`には退役決定と直接矛盾する退役前提の文（「今回は削らない」）が是正されずに残っている。これらをCriticalとして報告する。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `docs/ai/roles/coordinator.md` | 14 | 「責任・権限」冒頭のTier 3/4フロー要約が「Tech Lead役subagentを起動→分解案確認後、Implementer/Reviewer/Tester役をそれぞれ起動する」のままで、**今回新設した「2人目のTech Leadによる計画査読」と「Auditorによるクローズ時の受入」の2工程が一度も現れない**。同ファイル41行目以降の「計画受領時のゲート」節や75行目以降の「工程遵守の点検について」節では新工程を説明しているが、Roleの根幹となるこの1行の要約だけが更新から漏れている。Coordinatorはこの行を「Tier 3/4で何を起動するか」の最上位の記述として読むため、ここだけを読むと計画査読・Auditorの起動義務が存在しないように見える。半端な移行の典型(旧い一覧が新しい詳細節と矛盾したまま残る)。 | Critical |
| 2 | `docs/ai/effort-baseline.md` | 117-127(「常設の工程管理役の費用」節末尾) | 「退役の理由は費用ではなく機能しなかったことである」と述べた直後に、**「ただし今回は削らない。CP2・CP3が実際に拾ったものが軽くないため」と続けている**。これは`2026-07-28_003_pmo_retirement.md`が確定させた「PMOを退役させる」という決定そのものと矛盾する文言で、退役決定より前(まだPMOを残す方向で検討していた段階)の文章がそのまま残置されたものと見える。読者はこの節を読むと「PMOは今回は削らないことになった」と誤読する。直後のCP2/CP3の成果自体は事実として有用な記録だが、導入の一文が退役決定と正面から矛盾しているため、少なくとも「(この評価は退役前のものであり、実際には退役した)」等の訂正が要る。 | Critical |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `docs/ai/role-routing-index.md` | 18 | Implementer/Reviewer/Tester各行は「同様にCoordinatorが別のAgent tool subagentを起動する」と明示しているが、Auditor行は「案件クローズ時に1回だけ起動し」と受身形で、**起動主体(Coordinator)が他行と同じ明示のされ方をしていない**。`docs/ai/roles/coordinator.md`側にも「案件クローズ時にAuditorを起動する」という明文の義務規定が見当たらない(69行目「書けていなければクローズできない」はprogress.mdの記入義務であって起動義務ではない)。「誰が」「どのタイミングで(案件クローズの定義=何をもってクローズと判定するか)」起動するかを、Implementer等と同じ強さで一箇所に明文化することを勧める。 | 明確化 |
| 2 | `docs/ai/roles/coordinator.md` | 41-56(「計画受領時のゲート」節) | 「2人目のTech Leadによる計画査読」を誰が起動するかも同様に明示されていない(査読結果を「受け取ったとき」の記述はあるが、起動主体の記述がない)。`skills/delegation-tier/SKILL.md`のTier表では「Tech Lead→2人目のTech Lead→Coordinator承認」という順序は読み取れるが、起動主体はいずれの文書でも暗黙のままである。Finding 1の是正と合わせて明記すると解消する。 | 明確化 |
| 3 | `docs/ai/reviews/incident_auto_capture/progress.md` | 3 | 「正本の読み方: `docs/ai/roles/techlead.md`「進捗・課題の記録(PMOへの入力)」」という引用が、現在の`techlead.md`の見出し(24行目、`### 進捗・課題の記録`。「(PMOへの入力)」の部分は今回の改訂で外れている)と一致しなくなっている。本ファイルは決定どおり旧体制のまま完走させる対象であり修正必須ではないが、**この案件のクローズ時にAuditorが最初に突き合わせる参照であるため**、見出し文字列のずれは「参照が現物と食い違う」の指摘対象になりうる。次にこのファイルへ触れる機会に直しておくと、Auditorの実地初回起動でノイズにならない。 | 参照精度 |
| 4 | `docs/ai/role-routing-index.md` | 42 | 「2026-07-28の`pmo`追加では同一セッション中に登録された」という実例注記が、pmoが同日中に退役したことに触れないまま残っている。事実としては正しい(記録として有効)が、この一文だけを読むと`pmo`が現存するRoleであるかのように読める。「(このpmoは同日中に退役し現存しない)」等の一言を添えると、将来の読者がAuditor退役後の実例と誤認しない。 | 明確化 |

## 責務対応表(旧`pmo.md`→新体制、消失の有無を確認)

旧`pmo.md`の章立てを単位に、行き先を突き合わせた。

| 旧PMOの責務(`pmo.md`の節) | 新体制での行き先 | 消失の有無 |
|---|---|---|
| §1 工程の組み立て(Tech Leadの見積もりを実行可能な工程表へ組む) | `docs/ai/roles/coordinator.md`「計画受領時のゲート」(Coordinatorが1回)。工程表そのものを別Roleが「組む」機能は無くなり、**Coordinatorが直接見て判断する**形へ縮小。 | 意図的な縮小(決定記録の代替案1に相当)。消失ではなく機能の簡素化として明記あり |
| §2 計画レビュー(3基準・60分/30分・未決定2件以上) | `docs/ai/roles/techlead.md`「計画査読」層1(基準を`tool_uses`80/30-40へ更新)。`skills/delegation-tier/SKILL.md`「計画レビュー」節にも反映。 | 引き継がれている。基準値の単位変更は`effort-baseline.md`の実測に基づき正当化されている |
| §2 技術的精査が要る場合の2人目のTech Lead進言 | 進言ではなく**必須の層2(技術的前提の反証)**として格上げ。`docs/ai/roles/techlead.md`「計画査読」層2。 | 引き継がれ、むしろ強化(退役の主因である「誤った因果を検出できなかった」ことへの直接対応) |
| §3 進捗確認・逸脱検出(チェックポイント、10%基準) | 常設チェックポイントは廃止。事象駆動(超過10%・未決定ブロック・波及)へ置換。`docs/ai/roles/coordinator.md`「工程遵守の点検について」。 | **意図的に捨てた**と決定記録・coordinator.mdの双方に明記あり。消失ではなく受容リスク |
| §4 課題管理表の維持 | 明示的な引き継ぎ先が無い。`progress.md`の「課題」表自体は`techlead.md`「進捗・課題の記録」で存続し書き手も定義されているが、**「課題を集約し滞留を可視化する」という能動的な管理機能**(PMOが課題管理表を「維持」する主体だった点)は、Auditorの職掌にも Coordinatorの職掌にも明文で引き継がれていない。Auditorは「未解決の明示」を検査するのみ(受動的な受入検査であり、走行中の滞留の可視化ではない)。 | **軽微な機能低下の可能性。決定記録は「走行中の点検」を明示的に捨てたと書いているため、課題管理の常時可視化もこの受容済みリスクの一部と解釈できるが、`2026-07-28_003_pmo_retirement.md`の「何を失うか」節はPMO§6(工程遵守の点検)しか名指ししておらず、§4(課題管理)を失うことは明記されていない**。決定の対象範囲をやや超えて機能が落ちている可能性があるため、次回の月次振り返りで拾うか、現時点でCoordinatorに確認を求めることを推奨する |
| §5 計画外事象の判定(局所収束/波及/10%超) | `docs/ai/roles/coordinator.md`「計画外事象の扱い」にそのまま存続(Coordinatorが元々権限を持っていた節で、PMO側は判定の代行者だった)。 | 引き継がれている。むしろ本来Coordinatorの権限だったことが明確化された |
| §6 Coordinatorの工程遵守の点検(本Roleの中核) | 3分散: ①計画受領時のゲート ②2人目のTech Leadの査読 ③Auditorのクローズ受入。 | 引き継がれているが、**走行中の点検という性質は失われ、着手前1点+事後1点の2点に縮小**。この縮小は決定記録が正面から認めて受容している(「残る穴」節)ため指摘ではない |
| 入出力: コールドスタート設計 | Auditorが継承(`docs/ai/roles/auditor.md`冒頭で明言)。 | 引き継がれている |

## 数の主張の検証

| 主張箇所 | 主張 | 実物確認 | 結果 |
|---|---|---|---|
| `docs/ai/role-context-matrix.md` L36 | 「Auditorが読むのは次の4つに限る」 | 直後の表の行数を数えた: 案件フォルダの全成果物/`status.md`/`effort-baseline.md`/参照されている先 = 4行 | 一致 |
| `docs/ai/status.md` L28 | 「規範9ファイルへ反映済み」 | PMO退役に伴い書き換えられた規範ファイルを数えた: `coordinator.md` `techlead.md` `role-routing-index.md` `role-context-matrix.md` `skills/delegation-tier/SKILL.md` `effort-baseline.md` `core.md` `overview.md` `memory-classification.md` = 9(`auditor.md`は新設、`status.md`自身、`.claude/settings.json`は無関係の別修正のため対象外として除外するのが妥当な数え方) | 一致 |
| `2026-07-28_003_pmo_retirement.md` L67 | 「代替は3つ」 | 直後の番号付きリストが1〜3の3項目 | 一致 |
| `docs/ai/status.md` 冒頭「現行6役」 | Coordinator/Tech Lead/Implementer/Reviewer/Tester/Auditorの6役 | 列挙を数えた=6 | 一致 |

3回過去に間違えたという同種の主張はいずれも今回は正確だった。

## What Looks Good

- 新体制の各要素(計画受領時のゲート、計画査読層1/層2、Auditorの入力制限)は、退役理由(「唯一の入力`progress.md`が壊れていたことを検出できなかった」)に対して**それぞれ別の弱点を埋める設計**になっており、代替案がPMOの機能をただ細切れにしただけではない。特にAuditorが「Coordinatorの説明を入力にしない」という設計は、PMOの構造的欠陥(自己申告経由でしか逸脱を知れない)への直接対応として一貫している。
- `progress.md`の書き手をフェーズで分離した設計(計画・統合=Tech Lead、実行=Coordinator)は、`docs/ai/roles/techlead.md`と`docs/ai/roles/coordinator.md`の両方に同じ内容で対称的に書かれており、食い違いは無い。
- 進行中の`incident_auto_capture`案件については「旧体制のまま完走させる」という決定が、`2026-07-28_003_pmo_retirement.md`冒頭・`docs/ai/status.md`・`progress.md`双方に一貫して現れており、旧PMO関連の記述の大半(調査した27件超)はこの意図的な残置として説明がつく。宙ぶらりん参照として指摘したのは実質1件(progress.md L3の見出し文字列ずれ、Suggestion #3)のみ。
- `docs/ai/effort-baseline.md`の見積もり単位変更(「分」→`tool_uses`)は、実測データ(3.1倍のばらつき→1.8倍)を根拠に説明されており、`skills/delegation-tier/SKILL.md`・`docs/ai/roles/techlead.md`の基準値(80/30-40)と数値が一致している。
- `.claude/settings.json`への`defaultMode: "auto"`追加(今回のdiffに同梱)は、PMO退役そのものとは別件だが、`docs/ai/roles/coordinator.md`「この境界を実際に強制している機構」節の記述と実ファイルの内容が一致していることを確認した。

## Verdict

**Request Changes**(Critical 2件)。Critical 1は次のCoordinatorセッション開始時に新体制の起動漏れ(2人目のTech Lead査読、Auditor)を誘発しうるため、`docs/ai/roles/coordinator.md` L14の一文を新工程を含む形へ更新することを求める。Critical 2は退役決定と正面から矛盾する文言であり、`docs/ai/effort-baseline.md`の当該箇所に「この一文は退役決定前の記述であり、実際には退役した」旨の訂正、または文言そのものの削除を求める。Suggestions 4件はCoordinatorの判断でよい。
