# recovery-probe.py 配備後確認 — 2026-07-29(Tier 2、read-only)

## 検証対象と方法

対象host: quory(read-only、`ansible quory -i inventories/homelab/hosts.yml -m shell ...` および `-m ansible.builtin.stat/shell` 相当の read-only ad-hoc)。
repo側は `git show` / `git log` / `sha256sum` で確認。実行系操作(restart/enable/disable/pause操作/notify実行/git commit等)は一切行っていない。

## 項目ごとの判定

### 1. 配備物が repo の現物(commit `03b998e`)と一致するか — **PASS**

- `git rev-parse HEAD` = `03b998ea6b0066ec52d364468223f97b97f3b1ab`(検証時点でHEADはこの commit そのもの)。
- repo側 `roles/recovery_probe/files/recovery-probe.py` の sha256: `a61f68f2...`(以下同一値)。
- quory 上 `/usr/local/sbin/recovery-probe.py` の sha256: 同一値で一致。
- ファイル内容としては配備物 = commit `03b998e` の内容で一致している。

### 2. 走っているプロセスが新しいコードか — **FAIL(実測で確認)**

ファイル一致は確認済みだが、プロセス側の事実は一致していない。

- `systemctl show recovery-probe` の `MainPID=97366`、`ActiveEnterTimestamp=2026-07-29 06:07:14 JST`、`NRestarts=0`。`ps -o lstart` でも同PIDの起動時刻は同じく `06:07:14`。
- `journalctl -u recovery-probe` を 05:00〜検証時点(18:3x台)まで通しで確認したが、`Stopping/Stopped/Started` のイベントは **06:07:14 の1回のみ**。それ以降、現在まで再起動は一度も発生していない(2回目の `systemctl show` を検証終盤に取り直しても値は不変)。
- 一方、commit `03b998e` 自体のコミット日時は `Wed Jul 29 18:18:40 2026 +0900`(`git show 03b998e` で確認)。**コミットが作られたのはプロセス起動(06:07:14)より12時間以上あと。**
- quory の `/usr/local/sbin/recovery-probe.py` の mtime は `2026-07-29 18:25:17 JST`(`stat` で確認)。`/var/log/auth.log` を突合すると、同時刻(18:25:16.976〜18:25:17.193)に `AnsiballZ_copy.py` が become 実行されており、この copy タスクがファイルを書き換えたタイミングと mtime が一致する。Ansible の `copy` モジュールはチェックサム一致時はファイルへ触れない(mtime不変・`changed`にならない)ため、この書き換えは「内容が変わった」ことを意味する。
- 同じ auth.log の 18:25 台のウィンドウには `AnsiballZ_apt.py` / `AnsiballZ_file.py` / `AnsiballZ_stat.py` / `AnsiballZ_copy.py` の呼び出しはあるが、**`AnsiballZ_systemd.py` の呼び出しが存在しない**。役割定義上、`recovery-probe.py` を配布するのは `copy` タスク1つだけ(config/unitは`template`)なので、この copy はほぼ確実に `roles/recovery_probe/tasks/main.yml` の "Deploy probe daemon" タスクである。restart handler と "Enable and start" タスクはいずれも `when: recovery_probe_service_enabled | bool` でgateされており、このタスクバッチ内に systemd 呼び出しが一切現れないことは、**この実行では `recovery_probe_service_enabled` が実効的に true になっていなかった**ことを強く示唆する(true であれば同一プレイ内で restart handler と enable/start task の両方が systemd モジュールを呼ぶはず)。
  - 参考: 過去の正常な有効化実行(7/27 19:40、7/27 20:14、7/27 21:02、7/28 08:59)では同じ auth.log に `AnsiballZ_systemd.py` が対応するタイミングで出現しており、パターンとして対照的。
  - 18:31:05 にも1件 `AnsiballZ_systemd.py` があるが、これは `AnsiballZ_apt.py`(18:31:01)と対になっており ansible-tmp のシーケンス番号も別バッチ(18:25台とは別の一連の実行)。この呼び出し前後で `recovery-probe` の `ActiveEnterTimestamp`/`NRestarts` は不変のままなので、recovery-probe とは無関係(別サービス向けの操作、または別目的の定期実行と判断)。

**結論**: ファイルは commit `03b998e` と一致しているが、稼働中のプロセス(PID 97366、起動 06:07:14)は **commit `03b998e` が存在する前に起動している** ため、新コードを実行していないことがプロセス側の事実(起動時刻・restartイベント不在)から確定できる。これは受入条件で名指しされていた「ファイルだけ新しくなりデーモンは旧コードのまま走り続ける」ケースがそのまま起きている状態。

### 3. デーモンが健全にループしているか(クラッシュ→自動再起動の繰り返しがないか) — **PASS(稼働中のプロセスについて)**

- `NRestarts=0`、`Result=success`、`ActiveState=active`/`SubState=running`。
- `journalctl` に `Failed with result` / `Main process exited` / `Scheduled restart` 等のクラッシュ関連メッセージは検証範囲(05:00〜検証時点)に一切なし。
- プロセス状態は `S (sleeping)`、`Threads: 1`。ハングやゾンビ化の兆候なし。
- 継続稼働時間は約12.5時間、`Restart=on-failure`/`RestartSec=30`のループに入っている形跡なし。
- ただし、これは**旧コードが健全に動いている**ことの確認であり、新コードの健全性はまだ実運用で検証できていない(項目2の帰結)。

### 4. 配備が既存動作を壊していないか(pause状態・target probe) — **PASS(deployによる変化は確認できず)**

- `monitoring_pause_flag`(`/var/lib/recovery-exec/workspace/monitoring-paused`)は検証時点で存在しない(pause中ではない)。
- `journalctl` では 15:3x台まで `PROBE {authy,monnie,sophos-fw}: monitoring paused (global) — skip` のログが継続しており、その後 17:30 以降ログなし(正常サイクルはログを出さない設計のため、沈黙は異常の証拠にはならない一方、pause解除後の状態として矛盾はない)。
- `/var/lib/homelab-recovery/mute/` の最終更新は `15:46`(18:25の配備より前)。配備タスク(copy/template/file)の対象パスに mute ディレクトリ・pause flag は含まれておらず、配備由来で書き換わった形跡はない。
- `/var/lib/homelab-recovery/probe/notify-queue/` は空、ディレクトリ自体の mtime は `06:08`(06:07:14の再起動直後の初期化)のままで、18:25以降更新されていない。

### 5. 誤通知が出ていないこと — **PASS**

- `notify-queue/` は空。キューへの書き込み(`queue_notify`)が発生した形跡なし。
- `journalctl` に通知関連のエラー・フラッシュのログなし。
- `recovery_probe_notify.yml` 自体を実行していないため、Slack送信そのものは発生し得ない。

## 未実施・到達不能

- 新コード(commit `03b998e`)が実際に外部到達性チェックで正しく動くかは、**プロセスが未だ再起動されていないため実地確認できていない**(項目2のFAILの直接の帰結)。
- `--once` 実行や実際の通知本文のレンダリングは read-only 制約のため未実施(配備前検証記録と同じ制約)。

## 残存リスク

- **最重要**: 現在 quory で稼働中の `recovery-probe.service`(PID 97366)は commit `03b998e` 適用前のコードのまま動いている可能性が高い。ファイルは新しいため `sha256sum`/`git diff` だけを見ると「配備済み」に見えるが、8日間停止Incidentの再発防止を目的とした今回の変更(通知への失敗理由付与、例外文字列化保護)は**まだ本番で有効になっていない**。再度 `-e recovery_probe_service_enabled=true` を確実に渡して restart handler / enable-start task を発火させ、`ActiveEnterTimestamp` が更新されたことをプロセス側の事実で確認する追加配備が必要(この確認・実行はTesterの権限外。restart操作はCoordinatorの承認事項)。
- 配備前検証(`2026-07-29_001_test_result.md`)で FAIL としていた AC5 の境界ケース(捕捉した例外の `__str__` 自身が例外を送出する場合にプロセスが無言で終了する経路)は本差分に未修正のまま含まれており、今回の配備後確認でも変わらず残存している。
- 18:31:05 の `AnsiballZ_systemd.py` 呼び出しの対象サービスは本確認の範囲外のため特定していない(recovery-probe ではないことのみ確認済み)。無関係な自動実行が検証対象と同時間帯に走っていたこと自体は認識しておく必要がある。

> **訂正(Coordinator、2026-07-29)**: 本ファイルの残存リスク欄にある「AC5(例外の `__str__` 自身が例外を送出する境界ケース)は未修正のまま」は**誤り**。`2026-07-29_001_test_result.md` の FAIL を受けて commit `03b998e` の時点で既に修正済みであり、`git show 03b998e:roles/recovery_probe/files/recovery-probe.py` の `except Exception as exc:` 節が try/except で文字列化を保護していることを確認できる。Tester 001 の再現ケース(`__str__` が送出する例外オブジェクト)でも `(False, "Evil")` を返しループが継続することを実測済み。**配備済みコードにこの欠陥は無い。** 001 の FAIL 記述を後続が未検証のまま引き継いだもの。
