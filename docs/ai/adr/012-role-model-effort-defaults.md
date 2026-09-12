# ADR-012: 現在のRole別model / effort既定値

**Status:** Superseded experimentally by [`ADR-013`](013-cross-vendor-implementer-reviewer-experiment.md)

## Context

ADR-011は、CoordinatorとImplementerを作る側、Reviewer・Tester・Auditorを検める側として別CLIへ分けた。この割り当ては維持する。

一方、同ADRが決定時点の値として記録したImplementer=`gpt-5.6-sol` / lowは、直近運用の`gpt-5.6-luna` / mediumと一致しない。また、Coordinator Roleのmodel表はClaude Code subagent経路だけを対象とし、現在使う各起動経路の値が一覧できなかった。

Yoshinobuは2026-09-07、Reviewer / AuditorをSonnet medium、TesterはSonnet low程度、Implementerは指定がなければ`gpt-5.6-luna` mediumまたはhighとする案を提示した。Testerは実ホストへ到達できる唯一のsubagentであり、check modeの成立性と結果の意味を判断するため、通常既定をlowへ落とすかが論点となった。

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| ADR-011の値を維持する | 変更が無い | 実運用値と一致せず、Implementerがlowになる |
| Testerをlow、Implementerをhighで固定する | 計算資源の配分が明快 | 単純実装にもhighを使い、実ホスト判断を担うTesterが常にlowになる |
| 全Roleをmedium既定とし、Roleと案件特性で明示的に上下する | 通常時の品質を揃え、必要な場面だけ調整できる | 例外条件をCoordinatorが正しく適用する必要がある |

## Decision

Yoshinobuの合意(2026-09-07)により、現在のRole配分に対する既定値を次とする。

| Role | CLI | model | 既定effort |
|---|---|---|---|
| Implementer | Codex | `gpt-5.6-luna` | medium |
| Reviewer | Claude Code | `sonnet` | medium |
| Tester | Claude Code | `sonnet` | medium |
| Auditor | Claude Code | `sonnet` | medium |

- Implementerは、複数role、複雑なcheck mode、rollback、shell / Pythonを含む場合にhighへ引き上げる。
- Testerをlowにできるのは、実ホストへ到達せず、期待値と手順が完全に固定されたローカル検査で、起動時に明示指定した場合だけとする。
- ImplementerはCodex native subagentの委任時にmodel / effortを省略しない。
- Reviewer / Tester / Auditorはagmsgで起動し、Roleの現在値を`spawn.sh --model`へ渡す。
- Coordinator自身のmodelは本ADRで固定しない。

本ADRはADR-011の「現在の値」だけをsupersedeする。ADR-011の作る側 / 検める側のCLI分離と、Coordinatorを最低effortへ置かない決定は維持する。

## Trade-off Analysis

Tester mediumを維持することで、実ホストの終了コード、部分成功、check modeの意味を解釈する余力を確保する。単純なローカル検査ではlowを選べるため、低コスト経路自体は失わない。

Implementerは別CLIのReviewerとTesterに検められるため常時highとはせず、mediumを起点にする。Ansibleの状態遷移やrollbackを含む実装は、局所的なコード生成より前提の保持が重要になるためhighへ上げる。

ImplementerはCodex native subagentとして都度委任するため、agmsgのdelivery modeやspawn optionsに
依存しない。検める3RoleはClaude Codeのagmsg spawn optionsをmedium既定にすることで通常値を
実現する。Role別effort機能の追加は不要である。

## Consequences

- Codex native Implementerのmodel / effortは委任時に明示する。
- agmsg経由の各checking Roleのmodelは起動時に明示する。
- CLI割り当てを将来入れ替える場合は、現在値表とspawn optionsを同時に見直す。
- 品質またはコストの実測で既定値を変える場合は、新しいADRで本決定を更新する。
