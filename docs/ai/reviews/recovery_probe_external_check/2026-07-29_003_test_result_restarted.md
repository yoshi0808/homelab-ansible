# recovery-probe.service 再起動後確認 — 2026-07-29(Tier 2、read-only)

## 検証対象と方法

対象host: quory(read-only ad-hoc、`ansible quory -i inventories/homelab/hosts.yml -m shell`、journalctl閲覧のみ`-b`(become)使用)。
restart/enable/disable/pause操作/notify実行/git commit等の実行系操作は一切行っていない。

## 項目ごとの判定

### 1. 稼働中のプロセスが入れ替わったか — **PASS(プロセス側の事実で判定)**

- `systemctl show recovery-probe`: `MainPID=112498`、`ActiveEnterTimestamp=Wed 2026-07-29 18:44:33 JST`、`ExecMainStartTimestamp`同時刻、`NRestarts=0`。
- 前回確認(`002`)時点の `MainPID=97366`(起動 06:07:14 JST)から **PIDが変わり、起動時刻も更新されている**。`ps -o pid,lstart -p 112498` でも同じ起動時刻(18:44:32〜33)を独立に確認済み。
- `journalctl -u recovery-probe --since '18:00'` に `Stopping → Deactivated successfully → Stopped → Started` の一連のイベントが1回だけ記録されており、18:44:33 に手動再起動が発生した実測と整合する(`Consumed 19.249s CPU time over 12h 37min 18.521s wall clock time` の行は、旧プロセスが約12.6時間=06:07:14〜18:44:33走っていたことも裏付ける)。
- commit `03b998e` のコミット日時(18:18:40 JST)より新しい起動時刻(18:44:33)であり、ファイル一致ではなくプロセス起動時刻・PID変化・restartイベントの3点で新コードへの入替を確認した。

### 2. デーモンが健全に継続しているか — **PASS**

- 起動直後のログは `recovery-probe start (interval=60s, threshold=5, once=False)` の1行のみで、クラッシュ・異常終了を示すメッセージなし。
- 再起動後(18:44:33〜検証時点、約1分)の `journalctl` を `error|exception|traceback|fail|restart|main process|scheduled` でgrepしたが該当なし。
- `systemctl is-active` = `active`、`is-enabled` = `enabled`、`NRestarts=0`(再起動ループの兆候なし)。
- 検証時点で経過時間が短い(約1分)ため、長時間安定性は未確認。正常サイクルはログを出さない設計(`002`記録より)のため、この短時間の静寂は異常の証拠にはならない。

### 3. 再起動を契機に外部到達性チェックの通知が発生したか — **発生せず(観測どおり記録)**

- `/var/lib/homelab-recovery/probe/notify-queue/` は空(`.`/`..`のみ)、ディレクトリの mtime は `Jul 29 06:08` のまま更新されていない。すなわち旧プロセス起動時(06:07:14の再起動)以降、新しい通知キュー投入は一切発生していない。
- `recovery_probe_notify.yml` は実行していない。通知本文の新形式(連続失敗回数・失敗理由・原因非断定)の確認は、通知が発生していないため実施対象なし。

### 4. 監視が ACTIVE のままか — **PASS**

- `/var/lib/recovery-exec/workspace/monitoring-paused` は存在しない(`NO_PAUSE_FLAG`)。pause状態への変更は確認されなかった。

## 未実施・到達不能

- 新コードが外部到達性チェックを実際に正しく検出・通知するかは、read-only制約と「通知を発生させようとしない」制約により未検証(発生していない事実のみ記録)。
- 長時間(数時間オーダー)の安定稼働・実際の失敗検出サイクルは、検証時点で再起動から約1分しか経過していないため確認できていない。

## 残存リスク

- 再起動から検証時点までの経過時間が短い(約1分)ため、新コードが定常運用下で健全に動き続けるかは今回の確認だけでは保証されない。後続の定期確認(数時間〜翌日)で `NRestarts=0` の継続と通知キューの正常動作を再確認することが望ましい。
- `002`で指摘済みの、捕捉した例外の `__str__` 自身が例外を送出する境界ケース(AC5)は本確認の対象外で、依然未修正のまま残存している。

> **訂正(Coordinator、2026-07-29)**: 本ファイルの残存リスク欄にある「AC5(例外の `__str__` 自身が例外を送出する境界ケース)は未修正のまま」は**誤り**。`2026-07-29_001_test_result.md` の FAIL を受けて commit `03b998e` の時点で既に修正済みであり、`git show 03b998e:roles/recovery_probe/files/recovery-probe.py` の `except Exception as exc:` 節が try/except で文字列化を保護していることを確認できる。Tester 001 の再現ケース(`__str__` が送出する例外オブジェクト)でも `(False, "Evil")` を返しループが継続することを実測済み。**配備済みコードにこの欠陥は無い。** 001 の FAIL 記述を後続が未検証のまま引き継いだもの。
