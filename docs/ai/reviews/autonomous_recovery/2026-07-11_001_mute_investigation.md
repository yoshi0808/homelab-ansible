# proxmox evacuate 中の recovery mute 緊急調査

- 調査日時: 2026-07-11 07:32 JST
- 担当: tester
- 種別: read-only 運用調査
- 変更操作: なし

## 結論

**2026-07-11 09:10 JST 頃まで、recovery が monnie に対して自動復旧を発動する危険はない。**

`proxmox_evacuate_node.yml target_node=pve2` による対象別 mute は authy / monnie /
sophos-fw の3対象すべてに正しく作成され、現在有効である。`recovery-probe` は monnie を
毎分 `muted — skip` しており、設計上この時点で連続失敗カウンタもリセットされる。
push dispatch も同じ mute JSON を発火前に確認する実装である。

monnie 自体は Ansible ping に応答し、Proxmox cluster resources 上で pve1 に running
状態で存在する。pve2 は maintenance mode で、pve2 に残る guest は停止済み template
1台だけであり、running VM は0台だった。

一方、quory の `recovery-exec` 用 investigate SSH は monnie と pve1/pve2 のいずれにも
`Permission denied (publickey)` で失敗する。この障害は自律 recovery の mute 判定とは
別経路であり、現在の mute を無効化しないが、Slack/Codex からの read-only 調査能力が
失われているため別途修復が必要である。

## 1. Mute ファイル

quory 現在時刻:

```text
2026-07-11T07:32:08+09:00
```

| target | file mtime | until | reason | 調査時点 |
| --- | --- | --- | --- | --- |
| authy | 07:10:21 | 09:10:21 +09:00 | `proxmox_evacuate_node: pve2 evacuation in progress` | 有効（約98分残） |
| monnie | 07:10:22 | 09:10:22 +09:00 | 同上 | 有効（約98分残） |
| sophos-fw | 07:10:23 | 09:10:23 +09:00 | 同上 | 有効（約98分残） |

全ファイルは `/var/lib/homelab-recovery/mute/*.json`、所有者 `root:root`、mode `0644`。
evacuate 開始直後に3秒間で順番に作成されている。

## 2. Probe / push dispatch

`recovery-probe.service` の直近ログでは、monnie は 07:10:47 から調査時点の
07:31:48 まで毎分、継続して次の形式で skip されていた。

```text
PROBE monnie: muted (残 119 分) — skip
...
PROBE monnie: muted (残 98 分) — skip
```

直近1時間に monnie の `FAIL`、failure counter 増加、`LADDER monnie`、VM reboot、
dispatch 発火の記録はない。policy および `recovery-probe.py` の実装上、mute 分岐は
probe 判定前に failure counter を0へ戻して skip する。

`/var/lib/homelab-recovery/push/dispatch.log` に今回の時間帯の monnie エントリはない。
過去ログには mute skip と通常 dispatch の両方があり、dispatch script の mute 判定が
実装・稼働していた履歴は確認できる。

```text
2026-07-03T06:35:01+09:00 PUSH monnie: muted (...) — skip
2026-07-03T07:16:46+09:00 PUSH monnie: firing: Codex investigation for monnie
```

## 3. recovery-io と SSH エラー

`recovery-io.service`:

```text
Active: active (running) since 2026-07-08 06:08:23 JST
Main PID: 156153
```

Slack mention の受付と `codex-exec-wrapper` 起動は 07:22〜07:27 に記録されている。
07:26 の1件は、メッセージ先頭が `-i` だったため wrapper/Codex CLI が prompt を
受け取れず `rc=1: No prompt provided via stdin` となっている。これは monnie への
SSH到達性そのもののエラーではない。

本調査で本番の read-only wrapper を直接確認した結果:

```text
$ sudo -H -u recovery-exec /usr/local/bin/homelab-investigate-monnie status
recovery-exec@monnie.internal: Permission denied (publickey).
```

エラー分類は **SSH public key 認証拒否**。timeout / connection refused / host key /
name resolution ではない。調査時点 07:32:57 に確実に再現した。journal には過去1時間の
同エラー本文が保存されていないため、機械的に確定できる開始時刻は07:32:57のみ。
Slack 会話からは07:24頃には同問題が疑われていたが、これは状況証拠である。

同様に PVE 調査 wrapper も両ノードで publickey 拒否となった。

```text
homelab-investigate-pve1 cluster-resources → Permission denied (publickey)
homelab-investigate-pve2 cluster-resources → Permission denied (publickey)
```

quory の recovery-exec 秘密鍵ファイルは存在し、所有者/mode も
`recovery-exec:recovery-exec 0600`。公開鍵 fingerprint も読み出せたため、少なくとも
quory 側の「鍵ファイルがない」問題ではない。対象側 authorized_keys との不一致・欠落等は
今回の調査範囲では確定していない。

## 4. monnie の生死と現在位置

quory 正式 checkout から read-only Ansible ping:

```text
monnie | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

cluster resources（PVE wrapper が認証失敗したため、tester 権限で quory から Ansible
`command` を使い、read-only の `pvesh get /cluster/resources --output-format json` を
実行）:

```text
name=monnie vmid=211 node=pve1 status=running uptime=1261
```

従って monnie は生存しており、pve2 から pve1 への evacuation 済み。

## 5. Evacuate 進行状態

`ha-manager status`:

```text
lrm pve1 (active, watchdog active, ...)
lrm pve2 (maintenance mode, watchdog standby, ...)
service vm:1000 (pve1, started)
service vm:101 (pve1, started)
```

cluster resources:

- pve2: `status=online`, `hastate=maintenance`
- pve2 の running VM/CT: **0**
- pve2 に残る guest: `ubuntu-2604-template-v2` (VMID 9001), `status=stopped`, template
- monnie (211): pve1 / running
- authy (101): pve1 / running / HA started
- sophos-fw (1000): pve1 / running / HA started

evacuation の主要目的（pve2 の running guest を退避し maintenance mode にする）は
達成済みと判断できる。

## 安全判定と注意

- **現在の recovery 誤発動リスク: なし（mute 有効期限内）**
- mute 期限: monnie は 09:10:22 JST。patch 作業がこれを超える場合は、人間判断で
  mute 延長が必要（本調査では変更禁止のため実施していない）。
- `recovery-probe` は正常稼働し mute skip を継続している。
- push 経路も mute ファイルを発火前に読む設計で、今回の時間帯に dispatch 発火なし。
- recovery-exec の investigate SSH publickey 認証は別途要修正。これは現在の mute
  防御には影響しないが、障害調査・Slack応答品質に影響する。

## 実行した主な read-only コマンド

```bash
find /var/lib/homelab-recovery/mute -maxdepth 1 -type f -printf ...
cat /var/lib/homelab-recovery/mute/*.json
journalctl -u recovery-probe.service --since '1 hour ago'
tail /var/lib/homelab-recovery/push/dispatch.log
systemctl status recovery-io.service
journalctl -u recovery-io.service --since '1 hour ago'
ansible -i inventories/homelab/hosts.yml monnie -m ansible.builtin.ping
homelab-investigate-monnie status
homelab-investigate-pve{1,2} cluster-resources
ansible pve1 -b -m ansible.builtin.command \
  -a 'pvesh get /cluster/resources --output-format json'
ansible pve1 -b -m ansible.builtin.command -a 'ha-manager status'
```

## 未確認事項

- Slack UI 上で「監視停止」と表示されなかった理由。mute は実ファイルと probe log では
  正常に有効であり、表示/応答経路側の問題と考えられる。
- recovery-exec 公開鍵が monnie / pve1 / pve2 の authorized_keys に存在するか、および
  forced command エントリとの一致。対象側への通常 ann/Ansible経路は生きているが、
  本依頼では変更・修復は行っていない。
- patch 作業完了時刻が mute 期限を超えるかどうか。

