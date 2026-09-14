# quory月次ヘルス schedule 配備の観測

## 実施

Yoshinobuがquory Semaphoreの `SEMI-SAFE: Semaphore templates setup` を2回実行した。

| ジョブ | モード | 結果 |
|---|---|---|
| #1097 | check(native Dry Run) | success。新規作成1件(作成0件)、更新0、無変更23、管理外0 |
| #1098 | apply(通常実行) | success。**新規作成1件(作成1件)**、更新0、無変更23、管理外0 |

R6(「必ず先に`--check`で差分を読んでから適用する」)の順序どおりである。

## 観測した事実

- 両ジョブとも `failed: False`、phase=closed-world、recapは `failed=0`。
- `timezone expected/observed` は `Asia/Tokyo` / `Asia/Tokyo`(version `2.19.12-012ed06-1788086239`)。カタログの前提と実物が一致している(R11/AC10)。
- `canonical接続先一致(R2)` は True(`https://quory.internal:3000/api`)。
- #1098では作成後に **R16-2のround-trip検証が ok**、`Fail closed if the newly created schedule did not verify` はskipだった。**作った内容を読み直して一致していることは、role自身が確かめている。**
- 既存23件はcheck・applyとも「無変更」で、今回の追加が他のscheduleへ触れていない。
- 管理外(カタログに無いschedule)は0件のまま。

## 残っている観測

- **初回発火は2026-09-15 08:15 JST。** 実際に走ったこと、レポートとSlack短報が出ることの確認は未実施。
- 次回実行時刻そのものは開発側から読めない。**`semaphore-query schedule-list`を足したが(2026-09-14、未配備)、Semaphoreのschedule一覧APIが次回実行時刻を返さない**ため、読めるのは`active`と`cron_format`までである(実測: `docs/ai/reviews/dispatch_pkg_and_schedule_vocabulary/2026-09-14_004_test_result.md`)。次回実行時刻はUIでのみ確認できる。
