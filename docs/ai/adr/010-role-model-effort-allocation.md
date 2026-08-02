# ADR-010: Role別のmodel/effort配分

**Status:** Accepted

## Context

`docs/ai/role-routing-index.md`「モデル・effort配分」表は、各Roleに割り当てる`model:`/`effort:`の値を`.claude/agents/<role>.md`のfrontmatterへ固定し、Coordinatorが`subagent_type`で指定すれば配分が自動的に守られる仕組みになっている。表自体は値だけを持ち、値を選んだ根拠は本ADRに置く(索引側は「いま守るべき値」だけを持ち、根拠の経緯は持たない方針。索引の非ゴールは他文書へ広げないことであり、本ADRはその受け皿として新設した)。

判断すべきことは2軸ある。

1. Coordinatorとsubagent(Implementer / Reviewer / Tester / Auditor)でモデルを分けるか。
2. subagent間でeffortを一律にするか、Role特性に応じて下げるか。

## Options Considered

### モデル(Coordinator vs subagent)

| Option | Pros | Cons |
|---|---|---|
| 全RoleをOpus級で統一 | 判断力の差を気にしなくてよい | subagentは並行起動が多く、コスト・レイテンシが線形に効く |
| CoordinatorのみOpus以上、subagentはSonnet | subagentをSonnetで回しても本番影響前に実バグを検出できた実績がある(実装は本番影響のある差分を作る唯一のRoleであり、ここは下げない)。Opus級の判断が要るのは「あるべきものが無い」ことの検出(規範のドリフト、決定根拠がリポジトリに存在しない欠落)であり、それはCoordinatorの領分である | Sonnet側の品質低下を見逃すと本番へ届く前に気づけない |

### effort(subagent間で一律 vs Role別)

| Option | Pros | Cons |
|---|---|---|
| 全subagentを`high`で統一 | 品質低下のリスクを最小化できる | Auditorはrepoの成果物のみを読み技術的な正否を判定しないため推論深度を要さず、`high`は過剰。Reviewer/Testerも下げられる余地があるかを検証しないまま高コストを固定することになる |
| Role特性に応じて`medium`へ下げる(Auditor常時、Reviewer/Testerは試行) | Auditorは検査項目が`docs/ai/roles/auditor.md`§1に列挙済みで判定の型が決まっている。Reviewer/Testerは「レビュー精度は低effortでも保たれる」というOpus 5世代のガイドの示唆を実案件で検証できる。Implementerは本番影響のある差分を作る唯一のRoleであるため据え置き、品質変化が出たときに原因をReviewer/Tester側へ切り分けられるようにする | 試行中は品質低下を見逃すリスクがある。切り分けにはImplementerを対照群として固定する運用上の手間が要る |

## Decision

- **モデル**: Coordinatorは`Opus`以上を原則とする(「以上」は特定の1モデルへ固定しない、モデルの選択はYoshinobuが行う)。Implementer / Reviewer / TesterはSonnet。Auditorも同様にSonnet。
- **effort**: Auditorは新設時から`medium`(推論深度を要さないため)。Implementerは`high`で据え置き(本番影響のある差分を作る唯一のRoleのため下げない)。Reviewer / Testerは`medium`を試行し、`incident_investigate_trigger`案件での実績を根拠に確定させた。
  - Reviewerは、走査の起点で例外を握りつぶし「未調査バンドルが無かった」と区別できなくなる退行(削除された旧コードとの比較を要する指摘)を検出した。
  - Testerは、実装記録が書いていた検証手段が技術的に成立しないこと(`chmod 000`したファイルへの`stat`は`PermissionError`にならない)を独立に見抜き、正しい手段で再現し直した。
  - いずれも逐行照合と、先行成果物の主張を現物で確かめる作業であり、mediumで品質が落ちる懸念の中心だった部分である。この実績をもってReviewer / Testerの`medium`試行を終了し、そのまま確定値とした。

現行値は次のとおり(値そのものの正本は`docs/ai/role-routing-index.md`「モデル・effort配分」表)。

| Role | model | effort |
|---|---|---|
| Auditor | sonnet | medium |
| Implementer | sonnet | high |
| Reviewer | sonnet | medium |
| Tester | sonnet | medium |

## Trade-off Analysis

**受け入れる代償**

- Reviewer / Testerの`medium`は、確定前の試行期間中に品質低下を見逃すリスクを負っていた。実際には`incident_investigate_trigger`案件で退行検出・検証手段の誤りの指摘という、逐行照合と現物確認を要する働きが観測できたため、リスクは顕在化せずに試行を終えられた。
- Implementerを`high`のまま据え置くことで、subagent全体の品質変化が観測されたときに原因をReviewer / Tester側(effortを下げた側)へ切り分けられる。Implementer自身に品質問題が出た場合はこの切り分けが効かず、Implementer側の要因を別途調べる必要がある。

**受け入れない代償**

- 全subagentをOpus級に統一すること。本番影響前の実バグ検出という実績がSonnetで既に成立しており、コストに見合わない。

## Consequences

- 品質低下が観測されたら、該当Roleのeffortを`high`へ戻す。この方針自体は`docs/ai/role-routing-index.md`に残す。
- 新しくRoleを追加する、または既存Roleの職務範囲が変わるときは、上記の判断軸(モデルはCoordinator/subagentの分離、effortは判定の型が決まっているか・本番影響のある差分を作るか)に照らして値を決め、本ADRを更新するかsupersedeする新ADRを作る。
- `.claude/agents/<role>.md`のfrontmatterと`docs/ai/role-routing-index.md`の表の一致は`scripts/check-doc-consistency.py`のcheck 2が機械的に検査する。値を変更する際は両方を揃える。
