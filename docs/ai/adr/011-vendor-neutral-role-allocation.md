# ADR-011: Role配分をベンダー中立な「作る側 / 検める側」で決める

**Status:** Accepted (Role割当は実験期間中[`ADR-013`](013-cross-vendor-implementer-reviewer-experiment.md)がsupersede。ベンダー中立とCoordinator effortの原則は維持)

## Context

ADR-010は、CoordinatorがClaude Codeで動くことを前提に、Coordinatorは`Opus`以上、subagentはSonnet、effortはRole特性で決める、という配分を定めた。

2026-09-06、CoordinatorをCodexへ移すことになった。あわせて、**このリポジトリは公開されており特定ベンダーのAIを前提にしない**という方針が明示された(Yoshinobu)。CoordinatorがのちにClaude Codeへ戻ることも想定される。

ADR-010の決定は、次の2点で成立しなくなる。

1. **`Opus`以上**は1ベンダーのモデル名であり、Coordinatorが別のCLIで動くとき意味を持たない。
2. **配分の軸が「Coordinator vs subagent」だった。** CLIが2つある構成では、**どちらのCLIがどの役を持つか**が独立性を決めるため、この軸だけでは足りない。

判断すべきことは2軸ある。

1. どの役をどちらのCLIへ割り当てるか(独立性)。
2. モデルとeffortをどう決めるか(品質とコスト)。

## Options Considered

### 役とCLIの割り当て

| Option | Pros | Cons |
|---|---|---|
| 役ごとに個別最適で割り当てる | 各役に向いた製品を選べる | **牽制の対が壊れる。** 実際に検討した案(Coordinator=Codex / Implementer=Claude Code / Reviewer=Codex)では、検める対4つのうち2つが同一CLIになった — Reviewerが**Coordinatorの計画**を査読する対と、Testerが**Implementerの実装**を検証する対 |
| **作る側(Coordinator + Implementer)と検める側(Reviewer + Tester + Auditor)でCLIを分ける** | **検める対4つすべてが別CLIになる。CLIが2つのとき、これが唯一の充足解である** | CoordinatorとImplementerが同一CLIになる。両者の独立性は文脈の分離だけで担保される |

### モデルとeffort

| Option | Pros | Cons |
|---|---|---|
| Coordinatorも最低段で回す | 応答が速く、コストが低い | **Coordinatorの判断には検める工程が無いものがある**(分解の粒度、どこで止めるか、承認境界の当てはめ)。落ちるのは速度ではなく制約の見落としであり、下流のレビューでは拾えない |
| **Coordinatorは1段上、検められる側は下げてよい** | 検める工程がある役は、落としても下流が拾う | Coordinatorのコストが上がる |

## Decision

- **割り当ての軸を「作る側 / 検める側」にする。** Coordinatorが載っているCLIが作る側、もう一方が検める側になる。**製品名で決めない。**
- **Coordinatorのeffortを最も低い段へ置かない**(Yoshinobu決定、2026-09-06)。
- 決定時点の値(Yoshinobu決定、2026-09-06)。**現在のImplementer / Reviewer / Tester / Auditorのmodel / effort値はADR-012が該当行をsupersedeする。**

| Role | 側 | CLI | モデル | 段 |
|---|---|---|---|---|
| Coordinator | 作る側 | Codex | `gpt-6-astra` | medium |
| Implementer | 作る側 | Codex | `gpt-5.6-sol` | low |
| Reviewer / Tester / Auditor | 検める側 | Claude Code | `sonnet` | medium |

**現在値そのものは各プラットフォームの設定が持つ。上表は決定時点の値であり、設定と食い違ったら設定が正しい。どこを見ればよいかの正本は`docs/ai/roles/coordinator.md`「モデル・effort配分」である。**

## Trade-off Analysis

**受け入れる代償**

- **CoordinatorとImplementerが同一CLI・同一世代になる。** ADR-010の構成では両者は別製品だった。以後、両者の独立性は文脈の分離(別セッション)と依頼文の明示だけで担保される。**Implementerの出力はReviewerとTesterが別CLIで検めるため、この代償は下流で回収される。**
- **Implementerの段が`high`から`low`へ下がる。** ADR-010は「本番影響のある差分を作る唯一のRole」を理由に据え置いていた。モデル世代が変わっており、同じ根拠が同じ値を指すとは限らない。**品質低下が観測されたら1段上げる。**

**受け入れない代償**

- 役ごとの個別最適。牽制の対を2つ失う。

## Consequences

- 品質低下が観測されたら、該当Roleの段を1つ上げる。
- **CLIが3つ以上になったら、この軸を再検討する。** 「作る側 / 検める側」は、選択肢が2つしか無いことから導いた解である。
- ADR-010はSupersededとする。**subagentをSonnet / mediumで回して本番影響前に実バグを検出できたという実績と根拠は、010に残る。**
