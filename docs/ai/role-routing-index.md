# 移行期間用 Role / routing index

状態: **既存・移行期間の正本**（Phase 3の正式Role定義とrouting定義が完成するまで使用）

このindexは、identityからRole、暫定参照先、案件ownerを推測なしに解決するための正本である。Role本文は複製せず、旧 `core.md` の正確な参照範囲と移行先だけを示す。

## identityからRoleを解決する

| identity | Role | 通常の案件owner | 旧coreの暫定参照範囲 |
|---|---|---|---|
| `claude` | Coordinator | Yoshinobuとの対話・Tech Lead統合結果の確認 | §14「AI運用方針」「2セッション体制」、§15「基本フロー」「agmsg」「トリアージ」、§16「レビュー・確定フロー」、Claude Codeなら§17の製品固有限界 |
| `techlead` | Tech Lead | 無印trio | §14「AI運用方針」「2セッション体制」、§15「基本フロー」「agmsg」「トリアージ」、§16「レビュー・確定フロー」、Claude Codeなら§17の製品固有限界 |
| `techlead2` | Tech Lead | 2付きtrio | §14「AI運用方針」、§15「基本フロー」「agmsg」「トリアージ」、§16「レビュー・確定フロー」 |
| `implementer` | Implementer | `techlead` | §14「AI運用方針」、§15「要求仕様」「命名」「基本フロー」「agmsg」、§16「playbook先頭への最終仕様コメント」、§17「禁止事項」 |
| `implementer2` | Implementer | `techlead2` | `implementer` と同じ |
| `reviewer` | Reviewer | `techlead` | §14「AI運用方針」、§15「レビュー依頼」「agmsg」「reviewerレビュー観点」、§16「レビュー・確定フロー」、§17「禁止事項」 |
| `reviewer2` | Reviewer | `techlead2` | `reviewer` と同じ |
| `tester` | Tester | `techlead` | §14「AI運用方針」、§15「agmsg」、§16「テスト工程」、§17「禁止事項」、§18全体 |
| `tester2` | Tester | `techlead2` | `tester` と同じ |

番号付きidentityは番号なしidentityと同じRoleを使う。番号はRoleの違いではなく、通信上の席とtrio ownerを表す。

## trio routing

- `techlead` は無印trio（`implementer` / `reviewer` / `tester`）へ直接依頼し、各成果物の報告を直接受ける。
- `techlead2` は2付きtrio（`implementer2` / `reviewer2` / `tester2`）へ直接依頼し、各成果物の報告を直接受ける。
- 各Tech Leadは実装・レビュー・テスト結果を統合した後、Coordinator（`claude`）へ共有する。trio memberが通常案件の成果物をCoordinatorへ直接返す経路ではない。
- cross-trioの依頼、応援、移管は通常経路ではない。両Tech LeadまたはCoordinatorを介して明示合意し、agmsgで旧ownerの停止、新owner、進行中成果物の返却先を通知してから切り替える。
- 現行boot scriptはこのroutingをまだ実装していない。実装済み経路との差は Phase 0現状基準を正本とし、Phase 3で正式化、Phase 8でscriptへ反映する。

## 正本の優先順位

競合時は、情報の種類ごとに次を使う。Yoshinobuの当該案件に対する最新の明示指示が常に最優先である。

| 情報 | 優先する正本 | fallback |
|---|---|---|
| 全Role共通原則・安全境界 | `docs/ai/core.md` | なし。旧coreと競合したら新coreを優先 |
| identity、Role、trio routing | 本index | `agent_skills_reorganization_plan.md` Phase 3は設計根拠。旧coreから推測しない |
| 現在scriptが実際に行うboot・配送 | `new-session.sh`, `prep-agent.sh`, 配備済みagmsg、およびPhase 0現状基準 | 計画書は将来像であり、実装済み事実を上書きしない |
| 未移行の許可・禁止・例外・手順 | `docs/ai/core-migration-map.md` の該当行 | 行が指す `docs/ai/prompts/core.md` の正確な節だけを読む |
| 案件固有の要求・成果物 | agmsgの最新依頼と指定された `docs/ai/reviews/<target>/` | 関係しそうなreviewsを無差別に探索しない |
| 対象システム固有の判断 | 現行 `docs/ai/prompts/*_policy.md` | Phase 2で新Policy indexへ置換予定 |

Phase 0現状基準は実測事実、計画書は将来の作業順・設計根拠を表す。両者が違う場合は矛盾ではなく未移行差分として扱い、現状の説明にはPhase 0、将来の実装判断には計画書を使う。

## 作業開始時の暫定解決手順

1. `docs/ai/core.md` を読む。
2. 本indexでidentityを一つのRoleとownerへ解決する。
3. agmsgで指定された案件成果物だけを読む。
4. `docs/ai/core-migration-map.md` から対象ルールを選び、その行が指す既存Policyまたは旧coreの節だけを読む。
5. コード、`git status`、diffで現在の事実を確認する。

## 置換条件

- **Phase 3**: `docs/ai/roles/` に正式なCoordinator / Tech Lead / Implementer / Reviewer / Tester定義とrouting・移管規則が作成されたら、本indexのRole本文参照とtrio routingをそれらへ置換する。
- **Phase 5**: Role / Context / Policy / Skillの選択・遅延読込手順が実装されたら、本indexの暫定解決手順をそのindexへ置換する。
- **Phase 8**: `new-session.sh` / `prep-agent.sh` が正式indexを読み、bootメッセージと返信先がtrio ownerに一致することを検証したら、本indexを廃止する。

廃止時は `AGENTS.md` と `CLAUDE.md` の参照を正式Role indexへ同時に変更し、旧core fallbackを削除する。
