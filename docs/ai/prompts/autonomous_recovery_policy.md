# Autonomous Recovery Policy v0.3 (draft)

作成日: 2026-06-27
版: v0.3（draft、実装前確定用。v0.2からSlackメンション経由の手動調査依頼を確定として追加）
対象: Sophos / authy（hacritical）を中心とした異常検知 → 自律復旧パイプライン

参照:

- docs/ai/prompts/core.md
- docs/ai/prompts/proxmox_patch_policy.md（prefer* / hacritical タグ、proxmox_healthcheck.yml の既存実装、ミュート機構の元ネタ）
- docs/ai/prompts/proxmox_backup_restore_verify_policy.md（verify タグ、controlled apply の扱い）

本書は「何を許可し、何を許可しないか」を定める。実装方法（スクリプト本体、Ansible task の書き方）はここでは規定しない（v2.0方針: what/howの分離）。

---

## 1. 目的

Sophos / authy の業務継続を最優先とし、異常検知時に人間の承認を待たず自律的に復旧を試みる。外出時（スマホのみ、SSH鍵なし、VPN経由でも実質操作困難）でも対応できることが前提。

---

## 2. 対象と対象外

| 対象 | タグ | 適用される復旧手段 |
|---|---|---|
| Sophos (`sophos-fw`) | `hacritical`, `preferpve1` | VMリブート、フェイルオーバー（サービスrestartは対象外） |
| authy | `hacritical`, `preferpve1` | サービスrestart、VMリブート、フェイルオーバー |
| monnie | `ops`, `preferpve2` | サービスrestart、VMリブート（フェイルオーバーは対象外） |
| pve1 / pve2 | - | 対象外。既存 `proxmox_patch_policy.md` の枠組みに委ねる |
| ansy | - | 対象外（パイプライン自身の母艦） |

対象の適格性は、Proxmox上のタグ（`hacritical` / `ops` / `prefer*`）から動的に判定する。本ポリシーや実装側に固定VMIDリストを別途持たない（タグが正本、core.md/proxmox_patch_policy.mdの既存方針を継承）。

### 2.1 VMID / systemdユニット対応表（確認済み）

| 対象 | VMID | サービスrestart対象unit |
|---|---|---|
| authy | 101 | `freeradius.service` |
| monnie | 211 | `grafana-server.service`, `prometheus.service`, `loki.service`, `unpoller.service` |
| sophos-fw | 1000 | 対象外（VMリブート・フェイルオーバーのみ） |

VMIDはタグ判定の補助情報であり、適格性そのものの判定根拠ではない（タグが正本、上記の通り）。

---

## 3. 調査方法: 限定列挙されたplaybookのみを使う

新しいOSユーザーや新しい認証情報（read-only専用アカウント、Proxmox APIトークン等）は作らない。**既存の `ann`（NOPASSWD ALL）と、既存/新規のhealthcheck系playbookをそのまま使う。**

理由:

- `ann` は既にVault管理・既存の信頼チェーンに乗っている。新しい鍵・ユーザーを増やすと、その分の管理対象が増えるだけで安全性は上がらない
- shellが収集、Ansibleが判定する責務分離（core.md §7）は、Codexレビューの既存チェック項目（core.md §16: 「read-only playbookに変更操作が混入していないか」）でカバーされている
- 調査エージェントが実行できるのは**playbook名の選択**のみであり、コマンド文字列を自分で組み立てる場面が発生しない。コマンド単位の許可/禁止リストを維持する必要がなくなる

### 3.1 調査用playbook一覧（限定列挙）

| Playbook | 対象 | 状態 | 備考 |
|---|---|---|---|
| `proxmox_healthcheck.yml` | pve1 / pve2 + クラスタ全体のVM/CT配置・状態 | 既存・流用 | quorum / zpool / replication / failed units / 主要service / VM・CT配置を収集済み |
| `radius_healthcheck.yml` | authy | 既存・流用 | |
| `monitoring_healthcheck.yml` | monnie（grafana/prometheus/loki/unpoller） | 新規作成が必要 | 既存healthcheck系と同じ責務分離（shell収集のみ、Ansible判定）で実装する |

この一覧へのplaybook追加は、本ポリシーの改訂を経る。Claude Code・Codexの判断で拡張しない。

### 3.2 既存通知との重複に関する注意

`proxmox_healthcheck.yml` 等は、スケジュール実行時に独自の通知（メール等）を行っている。調査フェーズからのアドホック呼び出しが、この既存通知経路を誤って二重に発火させないことを実装時に確認する（§14未確定事項）。

### 3.3 本方式の再検証について

§3の「限定列挙されたplaybookのみで調査が完結する」という前提自体、本当に成立するか（angero等の補助的なread-only経路が一切不要かどうか）は、実装時にClaude Codeとユーザーで協議し判断する。既存healthcheck系playbookの収集項目だけで実際の異常パターンに対する診断深度が足りるかは、書面上の判断だけでは確定しきれない部分があり、ここは留保する。

---

## 4. Sophosの調査方針

OSレベルの深堀り（SSH等）は行わない。判定はquory/ansyからの外部到達性アクティブprobe（WAN reachability）のみで行う。Sophos自身のログ機構が壊れていても検知できることを重視する。

Sophos上の追加調査が必要な場合は、本ポリシーの対象外とし、人間が判断する（§7のエスカレーション経路に乗る）。

---

## 5. 調査・復旧エージェントの実行権限境界（PreToolUseフック）

コマンド単位の許可/禁止リストではなく、「どのplaybookを実行してよいか」で制御する。

```text
allow:
  ansible-playbook playbooks/proxmox_healthcheck.yml ...
  ansible-playbook playbooks/radius_healthcheck.yml ...
  ansible-playbook playbooks/monitoring_healthcheck.yml ...
  ansible-playbook playbooks/recovery_service_restart.yml -e target=<target> ...
  ansible-playbook playbooks/recovery_vm_reboot.yml -e target=<target> ...
  ansible-playbook playbooks/recovery_ha_failover.yml -e target=<target> ...

deny:
  上記以外すべて
  ansible ad-hoc モジュール呼び出し（-m shell / -m command / -m raw 等）
  生のSSH接続（ann鍵を含む、agentが直接シェルを得る経路）
  curl / wget 等の汎用任意宛先アクセス
```

「ann で何ができるか」ではなく「agentがどのplaybookを選べるか」が制御点になる。これにより、新しい診断ニーズが出た場合の対応は「新しいplaybookを書いてレビューを通す」（既存の要求仕様→実装→レビューの流れに乗る）になり、ポリシー側でコマンドや権限を逐一見直す必要がない。

recovery_* playbookは、agentから渡された <target> を信用せず、実行直前にProxmoxのタグ（hacritical / ops / prefer*）をAnsible tasks側で再照会して適格性を確認する（shell側で判定しない、core.md §7の責務分離に従う）。タグと一致しない場合は実行せず失敗として終了する。

許可されるplaybookの追加は、本ポリシーの改訂を経る。

---

## 6. トリガー伝達経路

### 6.1 authy / monnie → quory

systemd OnFailure= フックから、SSH command-restricted方式でquoryへ通知する。

```text
対象ホストごとに専用keypair（id_trigger_authy / id_trigger_monnie）
quory側: 専用ユーザー trigger の authorized_keys に

  command="/usr/local/bin/recovery-trigger.sh <target>",
  no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty
  ssh-ed25519 AAAA...
```

forced commandのため、送信元が何を送っても「<target> 向けトリガーを1個受理する」以上のことはできない。

### 6.2 Sophos / pve1 / pve2 / monnie（healthcheck経由）

quory上で直接 recovery-trigger.sh <target> を呼ぶ（probe失敗 or healthcheck NG時）。

### 6.3 Slackメンション経由（手動）

ユーザー本人が気づいた場合（家族からの伝聞含む）、Slackで@メンションして手動で調査を依頼できる。

```text
仕組み: 最小権限のSlack App（Socket Mode、ansy上で常駐）
スコープ: app_mentions:read, chat:write のみ
反応条件: ユーザー本人のSlack IDからのメンションのみ。他者は無視
渡される内容: メンション本文をそのまま調査フェーズ（Claude Code）の入力として渡す（自然文でよい）
```

自動検知経路（§6.1, §6.2）との差分:

```text
- §9の24時間フラッピングカウントはスキップする（人間の明示依頼のため不要）
- 実行中ロック（§6.4相当）は適用する（並行実行防止）
- 復旧の実行可否は自動経路と同じくProxmoxタグ判定に従う
  （hacritical / ops を持たない対象は調査のみで、復旧は実行しない）
```

このSlack Appの作成（api.slack.com上でのスコープ設定・トークン発行）はユーザー自身が行う。トークンはVault管理。

### 6.4 `recovery-trigger.sh` の前提チェック（順序のみ規定）

```text
1. 実行中ロック確認（同targetで前のパイプラインが稼働中ならskip）
2. muteファイル確認（§7、メンテナンス系playbookがmute中ならskip）
3. 直近24時間のラダー実行回数確認（§9、3回以上なら即エスカレーション）
4. すべて通過 → 調査パイプラインをバックグラウンド起動（SSH接続をブロックしない）
```

---

## 7. ミュート/TTL機構

メンテナンス系playbookが「今このtargetに触っている」ことを自己宣言する仕組み。明示的なclearは行わず、TTL自然失効に任せる。

```text
ファイル: /var/lib/homelab-recovery/mute/<target>.json
形式:     { "until": "<ISO8601>", "reason": "..." }
更新規則: 既存のuntilと(今+想定時間+バッファ)を比較し、長い方を採用する
```

mute設定タスクを追加する対象playbook:

| Playbook | ミュート対象 |
|---|---|
| `proxmox_evacuate_node.yml` | target_node + destination_node |
| `proxmox_patch_apply_node.yml` | 対象ノード単体 |
| `proxmox_restore_vm_placement.yml` | target_node |
| `ubuntu_nightly.yml` | その回でrebootするVM |
| `proxmox_patch_weekly_full.yml` の評価対象 | sophos-fw を含む（VM退避中の一時的なWAN瞬断を誤検知しないため） |

---

## 8. 復旧エスカレーションラダー

承認なし、各段1回のみ試行。各段は専用playbook（§5参照）で実行する。

```text
調査 → 復旧見込みありか
  なし → 人間へエスカレーション（Slack通知、自動対応終了）
  あり →
     1. recovery_service_restart.yml（authy: freeradius / monnie: grafana・prometheus・loki・unpoller / Sophos: 対象外）
        NG → 2. recovery_vm_reboot.yml（authy / monnie / Sophos対象）
             NG → hacriticalタグあり？
                  No  → 人間へエスカレーション（終了）
                  Yes → 3. recovery_ha_failover.yml（Sophos / authyのみ）
                        NG → 人間へエスカレーション（終了）
```

各段の試行・結果は§10に従い都度Slackへ通知する。

`recovery_vm_reboot.yml`はソフトリブートが応答しない場合に強制電源断＋起動へ内部的にフォールバックする（§13参照）。この内部フォールバックも含めて「1回」と数える（ラダー全体としては依然1回のみの試行）。

---

## 9. flapping対策

時間ベースではなく回数ベースで判定する。

| 仕組み | 目的 | 性質 |
|---|---|---|
| 実行中ロック | 並行実行防止 | 時間ベース（〜15分目安） |
| 24時間以内のラダー実行回数（既存レポートJSON参照） | 繰り返し失敗時の暴走防止 | 回数ベース、3回以上で即エスカレーション |

---

## 10. Slack通知仕様

承認ボタンは不要（§8の通りSlackは事後報告専用）。新規Slack App / Bot Token / Socket Modeは不要。既存の roles/common_slack/tasks/notify.yml が使うIncoming Webhook方式をそのまま拡張する。

```text
通知タイミング:
  - トリガー受理時
  - 各段（restart/reboot/failover）の試行開始・結果
  - 最終エスカレーション時（自動対応終了）

通知方法: 既存notify.yml と同方式（Incoming Webhook）
失敗時の扱い: best-effort。通知失敗で本処理を止めない（既存方針を継承）
送信先チャンネル: 既存のalertチャンネル（既存notify.ymlと同一Webhookを流用。Vault管理済み、本書にURLは記載しない）
```

---

## 11. ログ・レポート

| 種別 | 保存先 | 保持期間 | 用途 |
|---|---|---|---|
| 生ログ（authy/Sophos→quory転送syslog） | `/var/log/remote/<host>/` | 14日、logrotate | 調査材料のみ。トリガー判定には使わない |
| 構造化レポート | `reports/recovery_investigations/<target>/<timestamp>.json` | 長期（既存`reports/**`方針） | トリガー理由・調査結果・試行内容・成否の記録 |

monnieのLoki/Grafana（ネットワーク可視化用）とは完全に独立させる。混在させない。

---

## 12. 禁止事項

```text
- 調査・復旧エージェントに、§3.1で列挙したplaybook以外を実行させる
- ansible ad-hocモジュール呼び出し（-m shell等）や生SSHをagentに許可する
- recovery_* playbookで、タグ再検証を行わずに実行する
- 3 primitive（restart / reboot / failover）以外の変更操作を自動実行する
- ラダーの各段を2回以上自動で繰り返す
- §3.1 / §5の許可リストを実装側の判断で拡張する
- Sophos上でOSレベルの調査（SSH等）を自動的に行う
```

---

## 13. 対応するPlaybook / 役割（実装予定、未実装）

| 想定コンポーネント | 役割 | 状態 |
|---|---|---|
| `recovery_trigger`（quory常駐スクリプト群） | トリガー受理、ロック/mute/カウント判定、調査パイプライン起動 | 新規 |
| Slackメンションリスナー（Socket Mode, ansy常駐） | 手動調査依頼の受信。`app_mentions:read`/`chat:write`のみ、認可済みSlack IDのみ反応 | 新規 |
| `monitoring_healthcheck.yml` | monnieのサービス健全性確認 | 新規 |
| `recovery_service_restart.yml` | サービスrestart（タグ再検証含む） | 新規 |
| `recovery_vm_reboot.yml` | VMリブート（タグ再検証含む）。内部でソフトリブート（ACPI/guest agent経由）を試行し、タイムアウト内に復帰しなければ強制電源断＋起動にフォールバックする（既存`proxmox_patch_apply_node.yml`のpost-reboot retry機構と同じ思想） | 新規 |
| `recovery_ha_failover.yml` | HA failover（タグ再検証含む、既存`proxmox_restore_vm_placement.yml`のrelocateロジックを単一VM向けに再利用） | 新規 |
| 既存playbook4本への追記 | §7のmute設定タスク追加 | 既存への追記 |

---

## 14. 未確定事項（実装着手前に決める）

- §3の限定列挙playbook方式（angero等の補助read-only経路を作らない方針）で、実際の調査が完結するか。実装時にClaude Codeとユーザーで協議する（§3.3）
- `recovery-trigger.sh` 等の具体的な実装言語・配置パス
- systemd `OnFailure=` の設定方式（drop-in override で実装する方針は確定。各unitの既存`Restart=`/`StartLimitBurst=`設定を確認した上で、ラダー1段目（サービスrestart）との関係を決める必要あり）
- 調査フェーズのアドホック呼び出しが既存healthcheck系playbookの通知経路と二重に発火しないことの確認（§3.2）
