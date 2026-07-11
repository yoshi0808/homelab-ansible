# patch 中の external recovery 通知と monnie restart 説明の調査

- 調査日: 2026-07-11
- 担当: tester
- 種別: read-only
- 調査時間帯: 2026-07-11 07:30〜08:30 JST

## 結論

**パッチ中に自律復旧アクションは実行されていない。**

08:13:57 の「外部到達性の回復」は、authy / monnie / sophos-fw の target probe とは
独立した global external URL check の状態遷移通知である。per-target mute の対象外だが、
コード上は通知専用であり dispatch / LADDER / VM reboot / failover / service restart を
発火しない。

monnie の grafana-server / prometheus / loki / unpoller は、すべて patch の6日前である
7月5日の boot 直後から継続稼働し、`NRestarts=0`。patch 時間帯の restart / stop / start
ログもない。「4サービスが active になった = service restart 結果」という説明は誤りで、
active 状態を取得した status 調査の出力を restart 結果と誤解したものと判定する。

## 1. External check の設定と mute の関係

quory の `/etc/homelab-recovery/recovery-probe.json`:

```json
{
  "external_check_url": "https://one.one.one.one",
  "targets": {
    "authy": {"action": "ladder"},
    "monnie": {"action": "ladder"},
    "sophos-fw": {"action": "ladder"}
  }
}
```

external check は `targets` 内に target 名を持たない。main loop は次の順序で動く。

1. `targets` の authy / monnie / sophos-fw をループ。
2. 各 target で global pause と per-target mute を確認。
3. target loop 完了後、別枠で `external_reachable(cfg)` を1回実行。

従って authy / monnie / sophos-fw の mute JSON は各 target probe を止めるが、target loop
外の external check 自体と、その回復通知は止めない。今回 Slack に通知が出たことは
実装どおりであり、mute 不良ではない。

global monitoring pause についても現行コードでは target loop 内だけで評価され、external
check はその後に実行されるため、external 通知を抑止しない。

## 2. External check が行う処理

`recovery-probe.py` の external branch:

- external URL に到達不能となった最初の cycle:
  - `isp_down_since` を設定。
  - `EXTERNAL unreachable ... — 監視のみ、発火しない` と記録。
- 到達性が戻った cycle:
  - warning の「外部到達性の回復」を notify queue に追加。
  - `isp_down_since` を clear。
- notification queue を `recovery_probe_notify.yml` で Slack へ送信。

この branch には `fire_ladder()`、push dispatch、Codex、recovery action playbook の呼び出しが
ない。**通知のみであり、自律復旧アクションへ進む経路は存在しない。**

## 3. 07:30〜08:30 の probe / dispatch ログ

### Target probe

調査時間帯を通じ、3 target は毎分 mute skip だった。

```text
PROBE authy: muted (...) — skip
PROBE monnie: muted (...) — skip
PROBE sophos-fw: muted (...) — skip
```

07:55 と07:57頃に mute 残時間が増えており、patch/restore/evacuate playbook により mute が
更新されたことも読み取れる。08:13時点でも各 target は約103分残で mute 中だった。

時間帯内に次は存在しない。

- `PROBE <target>: FAIL`
- failure threshold 到達
- `LADDER`
- VM reboot / start / HA failover
- push dispatch
- Codex recovery session 発火

`/var/lib/homelab-recovery/push/dispatch.log` にも07:30〜08:30のエントリは0件。

### External state transition

```text
08:12:57 EXTERNAL unreachable (ISP または FW 断) — 監視のみ、発火しない
08:13:57 NOTIFY queued: [warning] [recovery-probe] 外部到達性の回復
08:13:57 RUN ansible-playbook playbooks/recovery_probe_notify.yml ...
08:13:59 NOTIFY sent: ...json
```

recovery-io/Slack Socket Mode 側も同時刻に DNS resolution failure を記録している。

```text
08:13:00 Temporary failure in name resolution
08:13:06 Temporary failure in name resolution
08:13:17 new session established
```

従って短時間の DNS/外部接続断が実際にあり、約1分後の回復通知は事実と整合する。

## 4. Recovery reports と「4サービス active」の出典

quory の `/home/yoshi/homelab-ansible/reports` を07:30〜08:30で列挙した結果、生成されたのは
次のカテゴリだけだった。

- `proxmox-health`
- `proxmox-patch`
- `proxmox-restore`
- `proxmox-evacuate`

`reports/recovery_investigations/` 配下にこの時間帯の monnie service restart / VM reboot /
failover report はない。`/var/lib/recovery-exec/workspace` にも同時間帯の成果物はない。

`homelab-investigate-monnie status` は4サービスそれぞれの `systemctl status` を表示する
read-only wrapper であり、出力には `Active: active (running)` が並ぶ。実際、SSH key 修復後の
read-only 疎通確認でもこの4サービスの active 状態が取得された。

一方、実 service restart は `homelab-recover-monnie` または
`recovery_service_restart.yml` の変更経路を必要とする。対応する report、push dispatch、
OnFailure trigger、サービス journal の restart 記録がすべてないため、Slack Codex が
言及した4サービス active の出典は **status 調査出力** と判断する。Codex の応答本文自体は
system journal/report に保存されていないため直接引用はできないが、実ホストの時系列が
restart 説明を明確に否定する。

## 5. monnie boot / service 時刻

monnie boot:

```text
2026-07-05 07:09:38 JST
```

| service | ActiveEnterTimestamp | ExecMainStartTimestamp | NRestarts | 現在 |
| --- | --- | --- | ---: | --- |
| grafana-server | 2026-07-05 07:09:43 | 同左 | 0 | active/running |
| prometheus | 2026-07-05 07:09:43 | 同左 | 0 | active/running |
| loki | 2026-07-05 07:09:43 | 同左 | 0 | active/running |
| unpoller | 2026-07-05 07:09:44 | 同左 | 0 | active/running |

07:30〜08:30 の4 unit journal に Starting / Started / Stopping / Stopped / restart / failed /
shutdown / SIGTERM はない。通常の稼働ログ（Loki checkpoint、Prometheus compaction等）は
継続しており、monnie VM自体も再起動していない。

## 最終判定

| 問い | 判定 |
| --- | --- |
| 外部回復通知は mute 不良か | いいえ。global external check は per-target mute 外 |
| external check は recovery action を発火するか | いいえ。通知のみ |
| target probe は patch 中に動作したか | mute skip のみ |
| dispatch / LADDER は発火したか | いいえ |
| monnie VM は patch 中に再起動したか | いいえ |
| monnie 4サービスは restart されたか | いいえ |
| 「active」は restart 成功の証拠か | いいえ。read-only status の観測値 |
| パッチ中に自律復旧アクションが実行されたか | **実行されていない** |

## 実行した主な read-only 確認

```bash
cat /etc/homelab-recovery/recovery-probe.json
journalctl -u recovery-probe.service --since ... --until ...
awk ... /var/lib/homelab-recovery/push/dispatch.log
find /home/yoshi/homelab-ansible/reports -newermt ...
journalctl -u recovery-io.service --since ... --until ...
uptime -s
systemctl show <service> -p ActiveState -p SubState \
  -p ActiveEnterTimestamp -p ExecMainStartTimestamp -p NRestarts
journalctl -u grafana-server -u prometheus -u loki -u unpoller --since ... --until ...
```

