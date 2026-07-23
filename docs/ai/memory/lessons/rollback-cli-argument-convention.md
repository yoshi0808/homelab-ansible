# 手動適用・ロールバック系playbookの共通CLI引数規約

**分類**: Lesson
**由来**: 2026-07-19、`prometheus_update_check`のupgrade/rollback実装で決めた規約。unpoller等の以後の手動適用/復旧playbookでも使い回す。

## 規約

- CLI表面はシンプルに `-e rollback=true` / `-e rollback_to=X.Y.Z`(打ちやすさ優先・全playbook共通のmuscle memory)。
- role内部は必ず **`<role>_rollback` / `<role>_rollback_to` にmap**して参照する(例: `prometheus_update_check_rollback: "{{ rollback | default(false) | bool }}"`)。グローバル`rollback`をroleロジックへ直接撒かない(複数role読込時の変数衝突回避、`-e`はグローバル最優先のため汎用名のまま撒くと危険)。
- 意味論(全playbook共通): `rollback=true`→直近backupへ復帰 / `rollback_to=X`→特定backup選択(無ければfail-closed) / `--check`併用→対象表示のみ(dry-run)。戻す前に現物も退避する(rollback自体も可逆)。backup不在はfail-closed。

## 構文注意

`-e`はコンマ区切り不可。`-e rollback=true -e rollback_to=3.12.0`(別々)か`-e "rollback=true rollback_to=3.12.0"`(スペース)。`-e rollback=true,rollback_to=3.12.0`はrollbackに文字列全体が入る誤り。

## 適用条件

新規の手動適用系playbookを作るとき、この引数名・map方式・意味論を踏襲する。
