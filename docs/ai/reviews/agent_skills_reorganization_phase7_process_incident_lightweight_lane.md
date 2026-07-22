# Phase 7 Process Incident: コメント修正でのコスト委任失敗

- 発生日: 2026-07-22
- 対象: 7 playbookの `tester-gate: safe-readonly` 理由コメント実態整合
- 種別: Process Incident / コスト委任失敗
- 状態: Coordinator承認済み

## 概要

挙動を変えないコメント修正に対して、通常のImplementer → Reviewer → Tester独立フローを機械的に適用した。実態調査そのものは有効で、通知経路の取り違えもレビューで検出できたが、同種の小変更としては引き継ぎ、待機、polling、中間成果物が過剰になった。

これは品質事故ではない。変更内容に対して工程コストが過大だった、Role / Workflow設計上のProcess Incidentである。

## 観察

- 7 playbookの通知経路棚卸しを3 Roleがそれぞれ実施し、重複調査が発生した。
- 各ファイルの変更は最終的にL2のコメント1行だけだった。
- `monitoring_healthcheck.yml` の先行依頼により、同じバッチを途中で分割して個別レビュー・テストした。
- Reviewerは `proxmox_patch_dryrun` の2通知経路を正しく区別し、must-fixを1件検出した。この意味論レビューは必要だった。
- Testerの `git diff --check`、marker lint、差分限定確認は有効だったが、ファイル単位の逐次受け渡しは不要だった。
- `/tmp` の3棚卸し結果は最終記録へ統合でき、中間成果物を恒久保存する必要はなかった。
- 長い待機中の頻繁なinbox pollingが、変更規模に対して追加コストになった。

## 採用する軽量レーン

軽量レーンは、コメントまたは文書だけを変更し、実行時の挙動が変わらない案件に限定する。実ロジック変更、新しい条件分岐、task・role・guard・scriptの変更には適用しない。たとえばradius / monitoringのdisk使用率チェック追加は対象外で、従来の3-Role独立フローを維持する。

軽量レーンでは次を標準とする。

1. 実態棚卸しは原則1 Roleが担当し、根拠となるpath・条件・到達経路をまとめる。
2. Reviewerは変更差分と、その差分が依存する実態だけを意味論レビューする。
3. Testerはdiff check、専用lint、対象限定、重複・形式などの機械検査を一括実行する。
4. 複数ファイルへの同種変更は1バッチで扱い、中間文書を増やさず最終記録1件へ統合する。
5. Tech Leadは不要なpollingを減らし、担当からの返却またはmonitor通知を基本にする。
6. 着手時に時間とコンテキストの上限を置き、超過時は工程をそのまま継続せず見直す。

緊急の先行引き渡しが必要な場合も、対象差分だけを切り出して確認し、残りを同じレビュー・テストへ重複して通さない。

## 反映先と昇格判断

- coreへは追加しない。
- Phase 7のProcess Incidentとして本書に保持する。
- TODO 7-2で得たRole別不足分析の結論を補足し、今後のRole / Workflow設計で軽量レーンを再評価する材料にする。
- Knowledge基盤の整備後に、複数案件で同じ効果を確認できた場合のKnowledge昇格候補とする。単一Incidentから恒久ルールへ即時昇格しない。

## 関連資料

- `docs/ai/reviews/agent_skills_reorganization_todo7-2_result.md`
- `docs/ai/reviews/agent_skills_reorganization_tester_gate_comment_alignment.md`
- `docs/ai/reviews/agent_skills_reorganization_plan.md`

