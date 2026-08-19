# Decisions

承認済みの設計判断を記録する。分類・保存期間・見直し条件は `docs/ai/memory-classification.md` 2節・3節を参照する。

**経緯の既定の置き場はcommitメッセージであり、ここではない**(`docs/ai/roles/coordinator.md`)。commitは親commitという形で判断時点の前提を持つが、日付だけを書いたファイルはそれを持たない。ここへ独立したファイルを起こすのは、commitを辿らせるだけでは同種の提案を止められないときに限る。

既存Claude Memoryの一括棚卸しは行わない(遅延移行のみ)。

- `rejected-proposals.md` — 退けた提案の索引(22件)。**通常は読まず、解決策が出ないときや判断に迷ったときに辿る。** 2026-08-18に`docs/ai/status.md`から移設した。
- `approval-authority-for-real-host-operations.md` — 実ホスト操作の承認権限をYoshinobuからCoordinatorへ移す(2026-07-26)。運用上の境界の正本は`docs/ai/roles/coordinator.md`であり、本記録は決定の根拠と見直し条件を扱う。
- `improve-prompts-by-deleting-not-adding.md` — 規範の品質向上をAI側で自律的に回す。**自律化するのは削除だけ**で、足すのはYoshinobuが決める(2026-08-19)。削除の根拠は「その文を書いた後にも再発しているか」であり、**未発火を不要と読まない**。固定点(AIが書き換えてよい文書の分離)は未着手。
- `ansy-must-not-trigger-production-changes.md` — ansyから本番の状態を変えない。配備を自動起動する2案の却下理由と、判定の軸を「叩かれる余地があるか」から「本番の状態が変わるか」へ移した経緯(2026-08-04)。規範の正本は`docs/ai/core.md`。
