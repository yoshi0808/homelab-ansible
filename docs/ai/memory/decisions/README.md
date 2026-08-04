# Decisions

承認済みの設計判断を記録する。分類・保存期間・見直し条件は `docs/ai/memory-classification.md` 2節・3節を参照する。

既存Claude Memoryの一括棚卸しは行わない(遅延移行のみ)。

- `approval-authority-for-real-host-operations.md` — 実ホスト操作の承認権限をYoshinobuからCoordinatorへ移す(2026-07-26)。運用上の境界の正本は`docs/ai/roles/coordinator.md`であり、本記録は決定の根拠と見直し条件を扱う。
- `ansy-must-not-trigger-production-changes.md` — ansyから本番の状態を変えない。配備を自動起動する2案の却下理由と、判定の軸を「叩かれる余地があるか」から「本番の状態が変わるか」へ移した経緯(2026-08-04)。規範の正本は`docs/ai/core.md`。
