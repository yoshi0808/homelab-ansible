# Incident: AuditorがCoordinator専用Knowledgeを参照した

日付: 2026-09-07
状態: 解決済み
対象: `auditor_lesson` / `coordinator_owned_lesson_recurrence`案件
種別: 未遂
原因分類: #運用考慮ミス

## 症状

案件クローズ監査中、Auditorが`docs/ai/memory/lessons/`、
`docs/ai/memory/knowledge-review-log.md`、`docs/ai/memory/decisions/`をread-onlyで
参照した。`docs/ai/core.md`はKnowledgeを読む主体をCoordinatorだけに限定している。
Auditorは監査成果物で逸脱を自己申告した。ファイル変更や実ホスト到達は無い。

## 原因

Auditorがrequirement AC4の実体を確認しようとし、Role境界を先に照合しないまま
参照先へ入った。案件記録にACのCoordinator検証結果は存在しており、Auditorはその
記録の再構成に留めるべきだった。

## 修正内容

- 境界外の参照から得た指摘は監査の受入根拠として採用しなかった。
- Coordinatorが指摘されたDecision 2本を独立に確認し、撤去後の現行契約へ更新した。
- 本件を既存lessonの再発記録へCoordinatorが追記した。
- 既存の`core.md`とAuditor Roleに境界は明記済みのため、同じ規範を追加していない。

## 確認方法

- Auditor終了前まで、lesson全19本のSHA-256とmtimeは変更前snapshotと一致した。
- Auditorのrepo成果物は案件のaudit記録だけで、`docs/ai/memory/`への変更は無かった。
- 境界外の2文書はCoordinatorが現物を読み、旧自動分類器を現在形の根拠にしない記述へ
  更新した。
