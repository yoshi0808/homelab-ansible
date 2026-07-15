# 構成マップ live 検証チェックリスト（Notion スナップショット更新用）

## 目的

Notion「自律復旧パイプライン 構成マップ(2026-07-04 実機確認)」を最新の実機状態で
更新したい。2026-07-04 以降、monnie 復元・mute/pve 調査(2026-07-14)など何度か
作り直しを挟んだので、当時の「稼働中 / 配備のみ / 未起動」の区分が今も正しいかを
再確認する。**この結果を claude が Notion 更新に使う。**

## 厳守事項

- **完全に read-only**。使ってよいのは `systemctl status/show/is-active/is-enabled`、
  `journalctl`(参照のみ)、`ls`、`getent`、`stat`、設定ファイルの `cat`(参照)まで。
  `start/stop/enable/disable/restart`・設定変更・mute set/clear は**一切しない**。
- 対象ホストへの接続は tester の判断で安全な方法を選ぶ(quory は
  `ssh -i ~/.ssh/id_ann ann@quory.internal`、他ホストは ansible ad-hoc の
  read-only モジュール等)。sudo が要る参照(sudoers 内容など)は `sudo -n` で。
- 結果は `docs/ai/reviews/autonomous_recovery/2026-07-14_018_constmap_live_result.md`
  に記録。各項目「現状値」と「2026-07-04 スナップショットとの差分(変化あり/なし)」を書く。
- 冒頭に「2026-07-04 から変わった点」だけを箇条書きサマリでまとめること(claude が
  Notion のどの行を直すか判断するのに使う)。

## 確認項目

### A. quory（制御ノード / Slack入口 / Codex実行環境）

1. **recovery-probe.service**: `is-enabled` / `is-active` / `UnitFileState` /
   `ActiveEnterTimestamp`、`journalctl -u recovery-probe.service -n 5`。
   → 2026-07-04 は「未起動(disabled・inactive、起動履歴 0 件)」。今も未起動か、
   起動履歴が付いたか(＝pull 型検知が動き出したか)。**ここが一番の確認ポイント。**
2. **recovery-io.service**: `is-active` と `ActiveEnterTimestamp`(いつから連続稼働か)。
   → 2026-07-04 は「active(2026-07-01 から)」。
3. **recovery-exec**: 常駐プロセスが無い(on-demand)ことの確認。
   `getent passwd recovery-exec`、recovery-exec の常駐 unit が無いこと。
4. **global monitoring pause 状態**:
   `/var/lib/recovery-exec/workspace/monitoring-paused` の有無(あれば PAUSED)。
   → 2026-07-04 は「解除(paused でない)」。
5. **per-target mute（2026-07-14 実装）**: `/usr/local/bin/homelab-mute-set` /
   `-status` / `-clear` の配備確認、`ls -la /var/lib/homelab-recovery/mute/` で
   現在アクティブな mute があるか(**閲覧のみ、clear しない**)。
6. **pve 調査の鍵/wrapper（2026-07-14 実装）**:
   `/home/recovery-exec/.ssh/id_recovery_investigate_pve` の有無、
   `/usr/local/bin/homelab-investigate-pve1` / `-pve2` の配備確認。

### B. ansy（開発ノード）

7. **recovery-io.service / recovery-probe.service**: `is-enabled` / `is-active`。
   → 2026-07-04 は「disabled・inactive(開発検証で手動起動の形跡のみ)」。今も同じか。

### C. authy（被監視 / FreeRADIUS）

8. **freeradius OnFailure drop-in**: `systemctl show freeradius -p OnFailure`、
   `ls /etc/systemd/system/freeradius.service.d/`。→ 「push 配線済み」。
9. **recovery-exec 着地アカウント**: `getent passwd recovery-exec`、
   `~recovery-exec/.ssh/authorized_keys` の forced command 有無。

### D. monnie（被監視 / Prometheus・Grafana・Loki・unpoller）

10. **OnFailure drop-in 4 本**: grafana-server / prometheus / loki / unpoller の
    各 `systemctl show <svc> -p OnFailure`。→ 「4 サービス全て push 配線済み」。
11. **recovery-exec 着地アカウント**: `getent passwd recovery-exec`。

### E. pve1 / pve2（2026-07-04 スナップショットに未記載 → 新規に確認して追記したい）

12. **recovery-exec 着地アカウント**: 両ノードで `getent passwd recovery-exec`。
13. **investigate dispatch**: `recovery-investigate-dispatch-pve.sh` の配備場所と有無。
14. **id_recovery_investigate_pve の authorized_keys**: forced command で dispatch に
    固定されているか。
15. **sudoers**: `/etc/sudoers.d/` の pve investigate 用ファイル有無と中身
    (`sudo -n cat`、read-only)。ワイルドカード無しで 1:1 列挙になっているか。
    → 2026-07-14 に「実機 PASS」記録があるので配備済みのはず。**pve1・pve2 両方に
    実際に載っているか**を確認。

### F. 補足（informational）

16. **recovery-push 発火ログ**: `/var/lib/homelab-recovery/push/dispatch.log` の
    最近のエントリ(直近の発火があるか。あれば日時を控える)。

## 出力

- `2026-07-14_018_constmap_live_result.md` に 1..16 の現状値 + 差分。
- 冒頭に「2026-07-04 から変わった点」サマリ。
- 判断に迷う点・確認できなかった点があれば明記(claude 側で拾う)。
