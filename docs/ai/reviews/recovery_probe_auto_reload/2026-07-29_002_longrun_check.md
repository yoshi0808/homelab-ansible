# recovery-probe.service 定常運用下の再確認(手動restartから約2時間17分後) — 2026-07-29(Tier 2、read-only)

## 検証対象と方法

対象host: quory(read-only ad-hoc、`ansible quory -i inventories/homelab/hosts.yml -m shell -b`。
journalctl閲覧、systemctl show、/proc観測、`strace -p`によるsyscall観測(アタッチのみ、対象プロセスへの
シグナル送信やptrace以外の操作は行っていない)、mute/notify-queue/pauseフラグの内容確認のみ。
restart/stop/start/enable/disable、mute/pause/notify-queue/stateディレクトリへの書込、
`ansible-playbook`実行、git操作は一切行っていない。

前提となる手動restart時刻: 2026-07-29 18:44:33 JST(`2026-07-29_003_test_result_restarted.md`に記録済み、
MainPID=112498)。本確認の実施時刻は 2026-07-29 21:01〜21:04 JST(restartから約2時間17分後)。

## 実行コマンド(実測)

```
ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "systemctl show recovery-probe -p MainPID,ActiveEnterTimestamp,ExecMainStartTimestamp,NRestarts,ActiveState,SubState,UnitFileState" -b

ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "date '+%Y-%m-%d %H:%M:%S %Z'; ps -o pid,lstart,etime -p 112498" -b

ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "journalctl -u recovery-probe --since '18:44:00' -o short-iso | tail -n 100" -b

ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "journalctl -u recovery-probe --since '18:44:00' -o short-iso | grep -iE 'error|exception|traceback|fail|restart|main process|scheduled|kill|core' || echo NO_MATCH" -b

# AC3: CPU/コンテキストスイッチの70秒間隔サンプリング(プロセスの外側の事実、ログに依存しない)
ansible quory -i inventories/homelab/hosts.yml -m shell -a "
PID=112498
awk '{print \$14, \$15, \$22}' /proc/\$PID/stat
grep -E 'voluntary_ctxt_switches|nonvoluntary_ctxt_switches' /proc/\$PID/status
sleep 70
awk '{print \$14, \$15, \$22}' /proc/\$PID/stat
grep -E 'voluntary_ctxt_switches|nonvoluntary_ctxt_switches' /proc/\$PID/status
" -b

# AC3: syscall観測(65秒、network系のみtrace、read-onlyアタッチ)
ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "timeout 65 strace -f -tt -e trace=network -p 112498 2>&1 | head -n 60" -b

# AC4: 通知キュー
ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "ls -la /var/lib/homelab-recovery/probe/notify-queue/" -b

# AC5: pauseフラグ、muteディレクトリ
ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "ls -la /var/lib/recovery-exec/workspace/monitoring-paused 2>&1 || echo NO_PAUSE_FLAG" -b
ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "stat /var/lib/homelab-recovery/mute; cat /var/lib/homelab-recovery/mute/authy.json; cat /var/lib/homelab-recovery/mute/sophos-fw.json" -b

# 事後の再確認(strace観測がプロセス状態に影響していないことの確認)
ansible quory -i inventories/homelab/hosts.yml -m shell \
  -a "systemctl show recovery-probe -p MainPID,ActiveEnterTimestamp,NRestarts,ActiveState,SubState; journalctl -u recovery-probe --since '18:44:00' -o short-iso | tail -20" -b
```

`-e`、`--check`以外のplaybook実行、systemdの状態変更モジュールは一度も使っていない。

## 受入条件ごとの判定

### 1. プロセスが 18:44:33 JST 起動のまま入れ替わっていない — **PASS(実測)**

- `systemctl show`: `MainPID=112498`、`ActiveEnterTimestamp=Wed 2026-07-29 18:44:33 JST`、
  `ExecMainStartTimestamp`同時刻、`NRestarts=0`。
- `ps -o pid,lstart,etime -p 112498`: `STARTED = 水 7月 29 18:44:32 2026`、`ELAPSED = 02:16:48`。
  systemd側の記録と独立にプロセス起動時刻が一致し、PIDも同一。
- 全observation(strace実施の前後含む)を通じて `MainPID`・`ActiveEnterTimestamp` は一度も変化せず。
  再起動ループの兆候なし。

### 2. 起動以降、クラッシュ・異常終了・例外の記録が無い — **PASS(実測)**

- `journalctl -u recovery-probe --since '18:44:00'` は起動直後の
  `recovery-probe start (interval=60s, threshold=5, once=False)` の1行のみ。
- `error|exception|traceback|fail|restart|main process|scheduled|kill|core` の正規表現grepで
  `NO_MATCH`(該当行なし)。
- `NRestarts=0`(systemdによる自動再起動が一度も発生していないことの独立した裏付け)。

### 3. probeサイクルが実際に回り続けている(ハングしていない)ことを、ログの沈黙以外の事実で示す — **PASS(実測)**

正常サイクルはログを出さない設計のため、ログ以外の2種類の独立した観測手段を用いた。

**(a) /proc上のCPU消費・コンテキストスイッチの70秒間隔サンプリング**

| | サンプル1(21:01:46) | サンプル2(21:02:56、70秒後) |
|---|---|---|
| utime (jiffies) | 221 | 222 |
| stime (jiffies) | 27 | 27 |
| voluntary_ctxt_switches | 2762 | 2782(+20) |

interval=60秒の設計に対し70秒の観測窓でCPU時間の増分とvoluntary context switchの増分(+20)が
観測された。プロセスが単純にブロックしたまま停止していれば、この時間枠でこれらの値は
一切増加しない。ハングしていないことの直接証拠。

**(b) `strace -f -tt -e trace=network -p 112498`(65秒、read-onlyアタッチ)**

アタッチ直後(21:03:43台)に、probeが生成した子プロセスが実際に以下を実行しているのを観測した:

- `socket(AF_INET, SOCK_DGRAM, IPPROTO_ICMP)` によるICMP echoの送信・応答受信(`sendto`/`recvmsg`
  が正常に完了、応答受信まで成功)。
- 別の対象に対する `socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)` → `connect()` → `getsockopt(SO_ERROR)`
  によるTCPポート到達性チェック。
- 複数の子プロセス(strace上のpid、probe対象ごとにforkしていると見られる)が並行して同種の
  ICMP/TCP到達性チェックを実行し、いずれも正常終了(`exited with 0`)している。

これはprobeが実際に到達性チェックのサイクルを実行中であることの直接的な観測事実であり、
推測ではない。対象ホストのIPアドレスは本記録に残さない(内部IP秘匿方針)。

**(c) 事後確認**: strace観測後に再度 `systemctl show` と `journalctl` を確認し、
`MainPID`・`ActiveEnterTimestamp`・`NRestarts=0` に変化がないこと、新規のエラーログが
出ていないことを確認した。観測行為自体がプロセス状態に影響していない。

### 4. 通知キューに滞留した通知が無い — **PASS(実測)**

- `/var/lib/homelab-recovery/probe/notify-queue/` は `.`/`..`のみで空。
- ディレクトリのmtimeは(前回`003`記録時点と同じ)`Jul 29 06:08`のままで、手動restart(18:44:33)
  以降も含め新規投入は発生していない。

### 5. 監視がpauseされておらず、muteの状態が説明できる — **PASS(実測)**

- `/var/lib/recovery-exec/workspace/monitoring-paused` は存在しない(`NO_PAUSE_FLAG`)。pause中ではない。
- `/var/lib/homelab-recovery/mute/` には `authy.json`(`until: 2026-07-25T12:52:58+09:00`)と
  `sophos-fw.json`(`until: 2026-07-25T12:53:00+09:00`)が残存するが、確認時刻(2026-07-29 21:04:08 JST)
  は両方の`until`より4日以上後であり、期限切れ。
- `roles/recovery_probe/files/recovery-probe.py` の `mute_remaining()` を確認したところ、
  `until`をパースし `remaining = until.timestamp() - time.time()` を `max(0, int(remaining))` で
  返す実装であり、期限切れの`until`は自動的に「mute残0秒」= mute無効となる(ファイルが残っていても
  実効的にはmuteされない設計)。実際のjournalログにも `muted` によるskip行は一度も出ていない
  (受入条件2の確認と同じgrep結果で裏付け済み)。したがって「muteファイルが存在するが無効」という
  状態を静的コード確認と動的ログ確認の両方で説明できる。
- `monitoring_pause_flag`・`mute_dir`のパスは `roles/recovery_probe/templates/recovery-probe.json.j2`
  の設定値と実機で確認したパスが一致することを確認済み(設定不一致による見落としではない)。

## 未実施・到達不能

- 該当なし。全受入条件について、ログの沈黙に依存しない観測可能な事実で判定できた。

## 残存リスク

- 今回の観測は手動restartから約2時間17分後の1時点のスナップショットである。数時間〜翌日規模の
  さらに長い定常運用(特にthreshold=5回連続失敗による実際のフェイルオーバー判定サイクルが
  一度も発生していない状態が継続すること)は本確認の範囲外。
- strace観測は`network`トレースのみに限定し65秒×1回のみ実施した。観測時に捉えた対象は
  probeが到達性チェックを行っている複数対象のうち先頭の数件のみ(`head -n 60`で打ち切り)であり、
  全対象を巡回していることの網羅的確認ではない。ただし、受入条件3の趣旨(「ハングしていないこと」)
  に対しては、(a)のCPU/ctxt-switch増分という独立した定量的観測と合わせて十分な根拠と判断した。
- mute期限切れファイル(`authy.json`/`sophos-fw.json`)自体は不要な残存物である可能性があるが、
  削除は本確認のスコープ外(read-only)であり、状態変更は行っていない。
