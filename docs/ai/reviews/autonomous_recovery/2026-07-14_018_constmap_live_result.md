# 構成マップ live 検証結果（2026-07-14）

対象チェックリスト:
`docs/ai/reviews/autonomous_recovery/2026-07-14_017_constmap_live_check.md`

実機観測時刻: 2026-07-14 21:28〜21:32 JST

## 2026-07-04 から変わった点

- quory の `recovery-probe.service` は、2026-07-04 時点の
  `disabled` / `inactive` / 起動履歴なしから、`enabled` / `active` に変化した。
  `ActiveEnterTimestamp` は 2026-07-08 06:08:23 JST。直近 journal にも
  60 秒間隔の probe 処理（monnie mute による skip）があり、pull 型検知ループは稼働中。
- quory の `recovery-io.service` は引き続き `active` だが、連続稼働開始は
  2026-07-01 から 2026-07-14 20:58:42 JST に変わっており、途中で再起動している。
- per-target mute の 3 wrapper と mute 状態ディレクトリが quory に配備された。
  観測時には monnie の mute が 2026-07-14 21:32:47 JST まで有効だった。
- pve 調査用秘密鍵と pve1 / pve2 wrapper が quory に配備された。
- pve1 / pve2 の両方に `recovery-exec` 着地アカウント、forced-command dispatch、
  固定コマンド列挙型 sudoers が配備された（2026-07-04 スナップショットへの新規追記項目）。
- push dispatch log に 2026-07-14 20:23:29 JST の monnie mute-skip が追加された。
  ただし直近の実発火（Codex investigation 起動）は 2026-07-03 のまま。

## 確認結果

### A. quory（制御ノード / Slack入口 / Codex実行環境）

#### 1. recovery-probe.service

- 現状値:
  - `is-enabled`: `enabled`
  - `is-active`: `active`
  - `UnitFileState=enabled`
  - `ActiveEnterTimestamp=Wed 2026-07-08 06:08:23 JST`
  - privileged journal の直近 5 件は、2026-07-14 21:28〜21:32 JST に
    `PROBE monnie: muted ... — skip` が 60 秒間隔で記録されていた。
- 2026-07-04 との差分: **変化あり**。未起動から常時稼働へ移行し、pull 型検知が動いている。
- 補足: ann の通常権限では journal が見えなかったため、許可された read-only の
  `sudo -n journalctl` で再確認した。

#### 2. recovery-io.service

- 現状値:
  - `is-active`: `active`
  - `ActiveEnterTimestamp=Tue 2026-07-14 20:58:42 JST`
- 2026-07-04 との差分: **変化あり**。active は維持しているが、2026-07-01 からの
  連続稼働ではなくなり、2026-07-14 に再起動している。

#### 3. recovery-exec

- 現状値:
  - アカウントあり: UID 1004、home `/home/recovery-exec`、shell `/bin/sh`。
  - `/etc/systemd/system`、`/lib/systemd/system`、`/usr/lib/systemd/system` に
    `recovery-exec*` unit は見つからなかった。
  - `systemctl status recovery-exec.service` は `Unit ... could not be found`。
- 2026-07-04 との差分: **変化なし**。systemd 常駐 unit を持たない on-demand 構成を維持。
- 未検証事項: チェックリストの read-only コマンド許可範囲に `ps` がないため、
  瞬間的な全プロセス一覧との突合は行っていない。systemd 常駐 unit 不在で確認した。

#### 4. global monitoring pause

- 現状値: `/var/lib/recovery-exec/workspace/monitoring-paused` は存在しない。
- 2026-07-04 との差分: **変化なし**。global pause は解除状態。

#### 5. per-target mute

- 現状値:
  - `/usr/local/bin/homelab-mute-set`: 配備済み（0755、2026-07-14 19:52 JST）
  - `/usr/local/bin/homelab-mute-status`: 配備済み（同上）
  - `/usr/local/bin/homelab-mute-clear`: 配備済み（同上）
  - `/var/lib/homelab-recovery/mute/` に lock 3 件と JSON 3 件あり。
  - authy JSON の期限: 2026-07-13 19:51:52 JST（観測時点で期限切れ）
  - monnie JSON の期限: 2026-07-14 21:32:47 JST（観測時は有効、直後に期限到来）
  - sophos-fw JSON の期限: 2026-07-11 09:57:25 JST（観測時点で期限切れ）
- 2026-07-04 との差分: **変化あり**。2026-07-14 実装の wrapper / 状態ファイルが配備された。
- 注意: `clear` / `set` は実行していない。JSON の存在だけでなく `until` を読んで
  有効・期限切れを判定した。

#### 6. pve 調査の鍵 / wrapper

- 現状値:
  - `/home/recovery-exec/.ssh/id_recovery_investigate_pve`: 存在、0600、
    `recovery-exec:recovery-exec`（秘密鍵内容は表示していない）
  - `/usr/local/bin/homelab-investigate-pve1`: 配備済み、0755
  - `/usr/local/bin/homelab-investigate-pve2`: 配備済み、0755
- 2026-07-04 との差分: **変化あり**。pve read-only 調査経路が新規配備された。

### B. ansy（開発ノード）

#### 7. recovery-io.service / recovery-probe.service

- 現状値:
  - `recovery-io.service`: `disabled` / `inactive`
  - `recovery-probe.service`: `disabled` / `inactive`
- 2026-07-04 との差分: **変化なし**。開発ノードでは両方とも常時稼働していない。
- 補足: `systemctl is-active` が inactive を exit 3 で返したため、SSH コマンド全体も
  exit 3 になったが、これは期待した状態値であり接続・確認失敗ではない。

### C. authy（被監視 / FreeRADIUS）

#### 8. freeradius OnFailure drop-in

- 現状値:
  - `OnFailure=recovery-trigger@freeradius.service`
  - `/etc/systemd/system/freeradius.service.d/recovery-trigger.conf` が存在。
- 2026-07-04 との差分: **変化なし**。push 配線済みの状態を維持。

#### 9. recovery-exec 着地アカウント

- 現状値:
  - アカウントあり: UID 1003、home `/home/recovery-exec`、shell `/bin/sh`。
  - `authorized_keys` は 2 行で、forced command は
    `/usr/local/sbin/recovery-investigate-dispatch.sh` と
    `/usr/local/sbin/recovery-action.sh`。
  - 両行とも agent/X11/port forwarding と pty を禁止。
- 2026-07-04 との差分: **変化なし**。investigate/action の着地構成を維持。
- 補足: 公開鍵本体は結果文書には転記していない。

### D. monnie（被監視 / Prometheus・Grafana・Loki・unpoller）

#### 10. OnFailure drop-in 4 本

- 現状値:
  - grafana-server: `OnFailure=recovery-trigger@grafana-server.service`
  - prometheus: `OnFailure=recovery-trigger@prometheus.service`
  - loki: `OnFailure=recovery-trigger@loki.service`
  - unpoller: `OnFailure=recovery-trigger@unpoller.service`
- 2026-07-04 との差分: **変化なし**。4 サービス全て push 配線済み。

#### 11. recovery-exec 着地アカウント

- 現状値: アカウントあり。UID 1004、home `/home/recovery-exec`、shell `/bin/sh`。
- 2026-07-04 との差分: **変化なし**。着地アカウントを維持。

### E. pve1 / pve2（新規追記対象）

#### 12. recovery-exec 着地アカウント

- 現状値:
  - pve1: アカウントあり（UID 1002、home `/home/recovery-exec`、shell `/bin/sh`）
  - pve2: 同じくアカウントあり（UID 1002、同 home / shell）
- 2026-07-04 との差分: **スナップショット未記載（新規追記）**。

#### 13. investigate dispatch

- 現状値:
  - pve1: `/usr/local/sbin/recovery-investigate-dispatch-pve.sh` が存在、0755、
    2026-07-14 21:04 JST 配備。
  - pve2: 同じパスに存在、0755、2026-07-14 21:01 JST 配備。
- 2026-07-04 との差分: **スナップショット未記載（新規追記）**。

#### 14. id_recovery_investigate_pve の authorized_keys

- 現状値:
  - pve1 / pve2 とも 1 行のみ。
  - forced command は `/usr/local/sbin/recovery-investigate-dispatch-pve.sh` に固定。
  - agent/X11/port forwarding と pty を禁止。
  - 両ノードで同じ `recovery-investigate-pve` 公開鍵を使用。
- 2026-07-04 との差分: **スナップショット未記載（新規追記）**。
- 補足: 公開鍵本体は結果文書には転記していない。

#### 15. sudoers

- 現状値:
  - pve1 / pve2 とも `/etc/sudoers.d/recovery-exec-pve` が存在（0440）。
  - 両ノードの内容は同一で、`recovery-exec` から root として実行できる
    read-only コマンドを 11 行、完全な引数付きで 1:1 列挙している。
  - 対象は `pvesh get` 2 本、`ha-manager status`、`pvesr status/list`、
    `pvecm status`、`pvesm status`、`zpool status -x`、`zfs list`、
    固定引数の `journalctl` 2 本。
  - ワイルドカード、`pvesh create/set/delete`、変更系コマンドはない。
- 2026-07-04 との差分: **スナップショット未記載（新規追記）**。
- 判定: pve1 / pve2 の両方に配備済みで、ワイルドカードなしの 1:1 列挙を確認。

### F. 補足（informational）

#### 16. recovery-push 発火ログ

- 現状値:
  - `/var/lib/homelab-recovery/push/dispatch.log` は存在し、最終更新は
    2026-07-14 20:23:29 JST。
  - 最新行は `PUSH monnie: muted (残 5 分, tester push mute) — skip`。
  - 直近の「実発火」は 2026-07-03 07:16:46 JST の monnie investigation。
    2026-07-14 の行は mute による skip であり、Codex investigation は起動していない。
- 2026-07-04 との差分: **変化あり**。2026-07-14 の mute-skip 記録が追加された。

## 実行方法と安全判断

- playbook は実行していないため、`# tester-gate:` マーカーの対象外。
- 実行したのは `systemctl is-enabled/is-active/show/status`、`journalctl -n 5`、
  `getent passwd`、`ls`、`stat`、設定・状態ファイルの `cat` のみ。
- `start/stop/enable/disable/restart`、mute の `set/clear`、ファイル変更、APPLY は
  一切実行していない。
- quory は指示どおり `ssh -i ~/.ssh/id_ann ann@quory.internal` を使用した。
  sandbox 内では system-wide SSH config の所有者判定に失敗したため、実接続時は
  `-F none` を追加した。接続先・鍵・remote command の意味は変更していない。
- 他ホストも同じ `id_ann` と `ann@<host>.internal` を使い、remote command の性質が
  read-only であることを個別に確認して SSH 実行した。

## 実行コマンド（要約）

```text
ssh -F none -i ~/.ssh/id_ann ann@quory.internal '<systemctl/show/journalctl/getent/ls/stat/cat>'
ssh -F none -i ~/.ssh/id_ann ann@ansy.internal '<systemctl is-enabled/is-active>'
ssh -F none -i ~/.ssh/id_ann ann@authy.internal '<systemctl show/getent/ls/cat>'
ssh -F none -i ~/.ssh/id_ann ann@monnie.internal '<systemctl show/getent>'
ssh -F none -i ~/.ssh/id_ann ann@pve1.internal '<getent/ls/cat>'
ssh -F none -i ~/.ssh/id_ann ann@pve2.internal '<getent/ls/cat>'
```

## 未検証事項・注意点

- `recovery-exec` の非常駐性は systemd unit 不在で確認した。許可コマンド外の `ps` は
  実行していないため、全プロセス一覧による二重確認は未実施。
- monnie mute は観測終了直後の 21:32:47 JST に期限到来する一時状態だった。
  Notion の定常構成値には「mute 機構配備済み」と記載し、特定 target の active mute は
  時点情報として扱うのが妥当。
- sudoers のコメントには一部「pre-deploy check」と残っているが、本チェックでは
  配備場所・内容・固定引数列挙のみを確認した。各 named check の実行成否は今回の
  1..16 の確認範囲外であり、実行していない。

## 結論

構成マップ更新上の最大の変更は、quory の `recovery-probe.service` が
`enabled` / `active` となり pull 型検知が実稼働している点である。ansy は従来どおり
両 recovery service が停止・無効。authy / monnie の push 配線と着地アカウントは維持。
pve1 / pve2 の read-only investigate 経路は両ノードに配備済みで、Notion へ新規追記できる。

Next step files:

- `docs/ai/reviews/autonomous_recovery/2026-07-14_017_constmap_live_check.md`
- `docs/ai/reviews/autonomous_recovery/2026-07-14_018_constmap_live_result.md`
