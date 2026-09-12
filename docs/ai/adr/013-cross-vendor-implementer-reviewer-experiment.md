# ADR-013: Implementerと差分Reviewerを別ベンダーへ分離する実験

**Status:** Accepted (experimental; next three non-trivial implementation cases)

## Context

ADR-011はCoordinatorとImplementerを同じ「作る側」、Reviewer・Tester・Auditorを別CLIの「検める側」へまとめ、すべての検める対を別CLIにすることを優先した。ADR-012はその現在値を定めた。

月次ストレージ点検では、Lunaへ調査または実装の一部だけを委ねても、Codex Coordinatorが調査結果の再読、設計、実装、差し戻し対応を担い、3回のトークン枯渇が発生した。部分委任では最も重い工程がCoordinatorに残る。一方、実装全体をClaude Codeへ移してReviewerもClaude Codeのままにすると、実装差分の主要な牽制が同一ベンダーへ閉じる。

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| ADR-011/012の現行配分を維持 | すべての検める対が作る側と別CLI | Codex側へ実装トークンが残る |
| Lunaへ調査・部分実装だけを委任 | 小さい単位を安価に処理できる | Coordinatorの再読・再設計・統合が残り、実測で節約にならなかった |
| ImplementerとReviewerをClaude Codeへ置く | Codex消費を最小化できる | 実装と主要レビューが同一ベンダーになる |
| **Claude Code Implementer + fresh Codex差分Reviewer** | 実装トークンをClaude側へ移し、差分を別ベンダーが検める | Coordinatorと差分Reviewer、ImplementerとAuditorは同じベンダーになるため、全対のCLI分離は失う |

## Decision

次の非自明な実装案件3件で、次の配分を試す。

| 工程 / Role | CLI | model / effort | 起動経路 |
|---|---|---|---|
| Coordinator | Codex | ユーザーが選択した現行値 | 人が直接使うsession |
| 計画Reviewer | Claude Code | `sonnet` / medium | agmsg、Implementerとは別identity |
| Implementer | Claude Code | `sonnet` / medium | agmsg、調査から差し戻し対応まで一貫して担当 |
| 差分Reviewer | Codex | `gpt-5.6-sol` / medium | native subagent、fresh context |
| Tester | Codex | `gpt-5.6-luna` / medium | native subagent、Reviewerとは別fresh context |
| Auditor | Claude Code | `sonnet` / medium | agmsg、案件クローズ時に1回 |

Coordinatorは実験対象案件の実装ファイルを編集せず、要求、承認境界、依頼、成果物統合、ユーザー判断だけを担う。差分ReviewerへImplementerの会話履歴や因果説明を渡さず、requirementと現物差分だけを渡す。

agmsgのClaude Code起動経路はmodelだけを渡し、role別effortを渡さないため、Claude Roleは共通のmedium既定として扱う。実効経路のないhigh指定は行わない。Implementerの品質不足が観測された場合は、文書上の値だけでなく起動経路を含めて見直す。

案件ごとにCoordinatorの実装ファイル編集有無、会話リセット回数、ユーザーが観測できる開始・終了時のトークン残量、レビュー差し戻し回数を記録する。3件後に継続・修正・撤回を決める。品質低下または起動経路の運用不能が観測された場合は3件を待たず見直す。

本ADRはADR-011のRoleを二群へ固定する割当決定と、ADR-012の現在値表を実験期間中supersedeする。ベンダー中立、Coordinatorを最低effortへ置かない、Role間のcontext独立という原則は維持する。

## Trade-off Analysis

全Roleを二群に分ける単純さと、Coordinatorの計画を別CLIが必ず査読する構造の一部を手放す代わりに、実装工程全体をCodexの週間枠から外す。計画査読はClaude Code、実装差分レビューはCodexと工程別に分け、実装と差分レビュー、実装とテストの2対ではベンダー分離を維持する。

部分委任を続ける案は、Coordinatorが同じ内容を再構成する重複を実測で解消できなかったため採らない。恒久変更ではなく3件の期限を置き、トークン削減と品質の両方を観測して判断する。

## Consequences

- Claude Codeの常駐RoleはImplementer、計画Reviewer、Auditorとなる。
- Codexの差分ReviewerとTesterは案件ごとにfreshなnative subagentとして起動する。
- `new-session.sh`のreset後に新しい常駐構成が有効になる。
- 過去のADRと案件記録は当時の判断として書き換えない。
- 3件目のcloseout後に本ADRを継続、改訂、またはsupersedeする。
