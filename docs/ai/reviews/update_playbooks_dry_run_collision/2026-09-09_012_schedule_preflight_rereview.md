# Code Review: schedule operation key preflight修正（再レビュー）

作成: 2026-09-09 / Reviewer（011 Major修正後）

### Summary

011のMajorは解消した。Incidentは同一ファイルのまま解決済みへ完成され、状態、原因分類、確定原因、修正内容、確認方法、残る実Semaphore未確認事項が実装記録010およびレビュー011と整合している。blocking findingは残っていない。

### Critical Issues

なし。

### Suggestions

なし。

### What Looks Good

- **状態と分類**: `状態: 解決済み`へ更新され、原因分類はallowlist同時更新漏れとconsumer-path test不足に対応する`#製造ミス #テスト不足`になった。
- **確定原因**: catalogへoperation keyを追加した一方で、その実consumerであるschedule preflightのclosed-world environment allowlistを更新しなかったことを明記した。catalog単体のshape testだけでは検出できず、実preflightへ新scheduleを渡すtestが無かったという検出漏れも具体化されている。
- **修正内容**: 2つのoperation keyをenvironment限定で追加し、key別enum外をfail-closed、native `params`への混入を拒否する実装と、job #1027相当のpreflight-to-diff回帰testを正確に記録している。
- **確認方法**: 97 unit tests、task-flow 6 scenarios、構文、doc consistency、diff checkに加え、別体Reviewerの公開consumer pathとcross-enum・非文字列・native params混入spot-checkを記録しており、実装記録010・レビュー011と一致する。
- **未確認境界**: 修正後の実Semaphore Dry Run、template/schedule readback、通常inspection通知が未確認で、commit/push後の配備観測として残ることを解決済み記録内でも明示している。ローカルで確定したpreflight欠陥の解消と、未実施の外部観測を混同していない。
- **差分健全性**: 返却前の`git diff --check`はrc=0。対象実装・test・記録以外の新たな変更は見つからなかった。

### 未確認事項

- 実Semaphoreでのcatalog reconcile再実行、schedule readback、通常inspection/Slack通知。これはIncidentにも未確認として残されている。
- 実ホスト・quory・API・Slack・commit・pushは実施していない。

### Verdict

**Approve** — Critical / Major / Minorなし。011のMajorは解消した。実Semaphoreでの配備後観測は案件全体の残作業として維持する。
