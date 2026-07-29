# test_result_followup — 切り詰め通知の改修検証 + global pause resume確認

Tester、独立subagent。対象commit: `3f30d5f`(作業ツリーclean)。全実行はread-only(monnie: dispatchスクリプト直接実行、quory: `stat`/`journalctl`/`sha256sum`/`grep`)。構成変更・サービス再起動・Loki write/delete・`homelab-recover-*`/`homelab-monitoring-pause`/`homelab-monitoring-resume`/`homelab-mute-set`・`git add/commit/push`はいずれも実行していない。書込先以外のrepoファイルも変更していない。

## 1. 配備の確認 — PASS

- monnie `/usr/local/sbin/recovery-loki-helper` の sha256 が repo の `roles/recovery_exec/files/recovery-loki-helper` と完全一致(`07a64bed...`)。切り詰め通知の改修が実機に反映されている。
- quory `/var/lib/recovery-exec/workspace/AGENTS.md` に「切り詰めが出たら、結論を出す前に必ず引き直す」の節(TRUNCATED記法込み)が実在。repo `roles/recovery_exec/templates/AGENTS.md.j2` の追記内容と一致。

## 2. 切り詰め通知 — PASS

検証データは2026-07-29 06:00–06:15 JST(前回実測window、559行/343行と既知)。

| 実行 | 要求範囲 | 実際に読めた範囲 | 終端が手前か | 通知行長 |
|---|---|---|---|---|
| `loki-window ubuntu-nodes 2026-07-29T06:00 15m any` | 06:00:00–06:15:00 | 06:00:00–06:07:30 | YES | 221文字 |
| `loki-window network-devices 2026-07-29T06:00 15m any` | 06:00:00–06:15:00 | 06:00:00–06:13:30 | YES | 221文字 |

- 両実行とも「要求した範囲」「実際に読めた範囲」の両方が出力に含まれ、終端は要求範囲より確実に手前(前者は約7.5分、後者は約1.5分読めていない)。改修前の通知(行数のみ)では分からなかった「どこまで読めたか」が可視化されている。
- 通知行は1行221文字で、300文字上限を超えない(内訳: `MAX_LINE_LENGTH`はper-entry行にのみ適用され通知行自体には適用されないコード構造だが、実測で上限内に収まることを確認した)。
- 出力行数はいずれも300行ちょうど(データ299行+通知1行)で、`MAX_LINES`上限を超えない。

**負例(誤検出しないことの確認)**: `loki-window pve-nodes 2026-07-29T06:00 15m any` を実行(母数92行、300行未満)。出力92行、`TRUNCATED`行は0件。上限に当たらない窓では通知が出ないことを確認した。

## 3. Incidentの確認方法の充足 — PASS(read-only代替手段で確認)

Incident記載の確認方法2点をいずれもread-onlyで確認した。1点目は`homelab-monitoring-status`ラッパーの実行(recovery-exec identity要)ではなく、同ラッパーのロジック(`roles/recovery_exec/files/homelab-monitoring-status`: `[[ -f $PAUSE_FLAG ]]`で判定するのみ)と機能的に同一の`stat`直読みで代替した。

- **`homelab-monitoring-status` が `ACTIVE` を返すこと**: quory `/var/lib/recovery-exec/workspace/monitoring-paused` を`stat`したところ `No such file or directory`(不在)。ラッパーのロジック上、不在=`ACTIVE`と等価。2回(15:52頃・15:55頃)確認しいずれも不在。
- **以降のprobeサイクルでLokiに`monitoring paused (global)`のskip記録が現れないこと**: quoryの`journalctl -u recovery-probe`で確認したところ、直近のskip記録は`2026-07-29T15:45:42+09:00`(authy/monnie/sophos-fw の3行)が最後で、それ以降(15:45:43〜15:55:08、約9.5分・約9probeサイクル分)は`monitoring paused`の記録が0件。Loki側でも`loki-window ubuntu-nodes 2026-07-29T15:47 5m any`(読めた範囲06:47:00–06:49:01)で同区間に一致件数0を確認し、journalctlとLokiの2系統で一致した。
- 補足: `recovery-probe.py`のソース確認により、通常運用(非`--once`)では probe が正常(OK)な場合は毎サイクルのログを出さない設計(`if once: log(...OK...)`の分岐内のみ)であることを確認した。そのため resume 後にPROBE系ログが疎になるのは正常挙動であり、異常ではない。

## 自己検証

- 全観測は実測値であり、期待値(前回measurement/Incident記載)との突合を明示した。
- 到達不能項目なし。
- 生ログ全文・内部IPアドレスは本ファイルへ転記していない。

## 残存リスク

- `MAX_LINE_LENGTH`(300)は通知行自体には適用されないコード構造(per-entry行にのみ`if len(formatted) > MAX_LINE_LENGTH`が働く)。今回の実測(221文字)は上限内だが、job名や時刻書式が変わらない限り構造的に一定長のため大きく超過する可能性は低いと判断した。ただし将来的にjob名やメッセージ文言が長くなった場合、通知行自体に上限がかかっていない点は設計上の潜在リスクとして残る。
- global pauseの再発防止策(TTL付与や未解除通知)はrepo `docs/ai/status.md` Next記載どおり未実装のまま。今回の検証は「今回のresumeが実際に反映されたこと」の確認であり、再発防止そのものは対象外。
