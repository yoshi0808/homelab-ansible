# ADR-015: CoordinatorをClaude Code、ImplementerをCodexへ置く

**Status:** Accepted

## Context

ADR-013は、Coordinatorを人が直接使うCodexセッション、ImplementerをClaude Codeへ置く配分を「次の非自明な実装案件3件」の実験として決めた。**この実験は1件も観測しないまま終了する。** 2026-09-14、YoshinobuがCoordinatorをClaude Codeへ戻し、ImplementerとAuditorをCodexへ置くと決めた。

同日、`new-session.sh`は既に2026-09-06版(pane 0 = Claude Code、pane 1 = Codex Implementer)へ復元されており、**現物が先に新しい配分の形になっていた。** repoの規範だけがADR-013のまま残り、`docs/ai/roles/coordinator.md`の割当表と現物が食い違っていた。

決めるべきことは2つある。

1. 5つの役をどちらのCLIへ割り当てるか。
2. 計画Reviewerをどちらへ置くか。**Coordinatorの計画を査読する対だけは、下流に検める工程が無い。**

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| ADR-013の実験配分を続ける | 3件の観測が揃う | Yoshinobuの決定と現物の双方に反する |
| Coordinator=Claude / Implementer=Codex、**Reviewerは計画・差分とも Claude** | 起動経路が単純になり、Codexの起動は案件あたりImplementerとAuditorの2つで済む | Coordinatorと計画Reviewerが同一ベンダーになる。**この対だけは誤りを拾う下流の工程が無い** |
| **Coordinator=Claude / Implementer=Codex、計画ReviewerだけCodexへ残す** | **牽制の対4つすべてがベンダーを跨ぐ。** 計画査読は読解と判定だけで、実装に比べ負担が小さい | Codexの起動が案件あたり最大3つになる。Reviewerの起動経路が計画と差分で2本に分かれる |

## Decision

Yoshinobuの承認(2026-09-14)により、次の配分とする。

| Role / 工程 | CLI | 起動経路 | model | effort |
|---|---|---|---|---|
| Coordinator | Claude Code | 人が直接使うセッション、tmux pane 0 | 当該CLIの設定 | 最低段へ置かない |
| Implementer | Codex | agmsg。tmux pane 1へ常駐し、セッションごとにfresh | `gpt-5.6-terra` | medium |
| 計画Reviewer | Codex | agmsg。案件ごとにfresh、Implementerとは別identity | `gpt-5.6-sol` | medium |
| 差分Reviewer | Claude Code | native subagent。実装履歴を継承しないfresh context | `sonnet` | medium |
| Tester | Claude Code | native subagent。Reviewerとは別のfresh context | `sonnet` | medium |
| Auditor | Codex | agmsg。案件クローズ時に1回だけfresh | `gpt-5.6-sol` | medium |

牽制の対は4つとも別ベンダーになる — Coordinator(Claude)↔計画Reviewer(Codex)、Implementer(Codex)↔差分Reviewer(Claude)、Implementer(Codex)↔Tester(Claude)、案件記録(Claude)↔Auditor(Codex)。

Testerをlowにできるのは、実ホストへ到達せず、期待値と手順が完全に固定されたローカル検査で、起動時に明示した場合だけとする。Implementerは複数role、複雑なcheck mode、rollback、shell / Pythonを含む場合にhighへ引き上げる。

**Claude CodeのImplementerとAuditorを起動する手段を残さない。** `.claude/agents/implementer.md` と `.claude/agents/auditor.md` を削除し、Agent toolからこの2役をClaude Codeで起こせない状態にする。宣言だけで同一ベンダーの起動を避ける形は採らない(`docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`)。

本ADRはADR-013をsupersedeし、ADR-012の値表をsupersedeする。ADR-011のベンダー中立、Coordinatorを最低effortへ置かない、Role間のcontext独立という原則は維持する。**ADR-011の「作る側 / 検める側でCLIを分ける」割当規則は本ADRがsupersedeする** — 本ADRは作る側(Coordinator / Implementer)をベンダーで割り、代わりに検める対ごとの分離を直接満たす。

## Trade-off Analysis

ADR-011は「CLIが2つのとき、作る側と検める側で分けることが牽制4対を満たす唯一の解」とした。本ADRはその前提を採らない。**満たすべきものは群の分け方ではなく対の分離であり、対を直接並べれば別の解がある。** 代わりに作る側の2役が別CLIになるため、CoordinatorとImplementerの間では会話履歴だけでなく製品も異なる。要求の受け渡しはagmsgの依頼文と `docs/ai/reviews/<target>/` の成果物だけに載る。

計画ReviewerをCodexへ残すことで、Codexの起動は案件あたり最大3つ(Implementer常駐、計画Reviewer、Auditor)になる。ADR-013はCodexのトークン枯渇を発端としていたが、枯渇したのはCoordinatorが調査・設計・実装・差し戻し対応まで抱えた場合であり、**計画査読とauditはいずれも読解と判定に閉じる。** 実装本体がCodexへ戻る点は負担増だが、それはRoleの分担どおりの消費であってCoordinatorへの集中ではない。

失うものとして、Claude Code側のImplementer / Auditor定義を消すため、配分を戻すときは定義の復元(`git log`)が要る。

## Consequences

- Claude Codeで常駐するのはCoordinator(pane 0)だけになる。差分ReviewerとTesterは案件ごとのnative subagentであり、常駐paneを持たない。
- Codexの常駐はImplementer(pane 1)であり、計画ReviewerとAuditorは案件ごとにagmsgでfresh起動して畳む。
- `.claude/agents/` に残るのは `reviewer.md` と `tester.md` の2つになる。`scripts/check-doc-consistency.py` check2 は、この2つと `docs/ai/roles/coordinator.md` のmodel / effort表を照合する。
- gitignoredの `new-session.sh` は、pane 0でClaude Codeを起動し、pane 1へCodex Implementerを `--fresh --model` 付きでspawnする。要件の正本は `docs/ai/context/operations/agent-messaging.md` §10。
- 過去のADRと案件記録は当時の判断として書き換えない。
