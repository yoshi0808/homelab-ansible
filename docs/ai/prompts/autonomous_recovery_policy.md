# Autonomous Recovery Policy v0.4

作成日: 2026-06-27
版: v0.4（実装完了後の正本。v0.3 draft からアカウント構成・権限境界・Slackループを実装に合わせて全面改訂）
対象: authy / monnie / sophos-fw の異常検知 → 自律復旧パイプライン

参照:

- docs/ai/prompts/core.md
- docs/ai/prompts/proxmox_patch_policy.md（prefer* / hacritical タグ、ミュート機構の元ネタ）
- docs/ai/prompts/proxmox_backup_restore_verify_policy.md（verify タグ、controlled apply の扱い）

本書は「何を許可し、何を許可しないか」を定める。実装方法の詳細（スクリプト本体、Ansible task の書き方）はここでは規定しない（v2.0方針: what/howの分離）。

---

## 1. 目的

authy / monnie / Sophos の業務継続を最優先とし、異常検知時に人間の承認を待たず自律的に復旧を試みる。外出時（スマホのみ、SSH鍵なし、VPN経由でも実質操作困難）でも対応できることが前提。

---

## 2. 対象と対象外

| 対象 | タグ | 適用される復旧手段 |
|---|---|---|
| Sophos (`sophos-fw`) | `hacritical`, `preferpve1` | VMリブート、フェイルオーバー（サービスrestartは対象外） |
| authy | `hacritical`, `preferpve1` | サービスrestart、VMリブート、フェイルオーバー |
| monnie | `ops`, `preferpve2` | サービスrestart、VMリブート（フェイルオーバーは対象外） |
| pve1 / pve2 | - | 対象外。既存 `proxmox_patch_policy.md` の枠組みに委ねる |
| ansy | - | 対象外（Slackリスナーの母艦） |

対象の適格性は、Proxmox上のタグ（`hacritical` / `ops` / `prefer*`）から動的に判定する。本ポリシーや実装側に固定VMIDリストを別途持たない（タグが正本）。

### 2.1 VMID / systemdユニット対応表

| 対象 | VMID | サービスrestart対象unit |
|---|---|---|
| authy | 101 | `freeradius.service` |
| monnie | 211 | `grafana-server.service`, `prometheus.service`, `loki.service`, `unpoller.service` |
| sophos-fw | 1000 | 対象外（VMリブート・フェイルオーバーのみ） |

VMIDはタグ判定の補助情報であり、適格性そのものの判定根拠ではない（タグが正本）。

---

## 3. アカウント構成

v0.3の「既存 `ann`（NOPASSWD ALL）を流用」方式は採用しなかった。代わりに、用途を明確に分けた専用アカウントを新設する。

### 3.1 アカウント一覧

| ユーザー | ホスト | 役割 | シェル |
|---|---|---|---|
| `recovery-slack` | ansy | Slackリスナー常駐プロセスの実行ユーザー。systemd service として動作 | `/usr/sbin/nologin` |
| `recovery-slack` | authy / monnie | ステータスチェック用SSH着地ユーザー（forced command専用） | `/bin/sh`（SSH forced commandに必要） |
| `trigger` | quory | authy/monnieからのSSHトリガーを受け取るユーザー（forced command専用） | `/bin/sh`（SSH forced commandに必要） |
| `recovery-runner` | quory | ansible-playbookを実行する専用ユーザー。triggerからsudoで起動される | `/usr/sbin/nologin` |

### 3.2 SSH鍵構成

```text
[ansy上 /etc/recovery/keys/]
  id_trigger_ansy_authy         — ansy → quory(trigger) : authy向けトリガー用
  id_trigger_ansy_monnie        — ansy → quory(trigger) : monnie向けトリガー用
  id_trigger_ansy_sophos_fw     — ansy → quory(trigger) : sophos-fw向けトリガー用
  id_status_ansy_authy          — ansy → authy(recovery-slack) : ステータスチェック用
  id_status_ansy_monnie         — ansy → monnie(recovery-slack) : ステータスチェック用

[quory上 /home/recovery-runner/.ssh/]
  id_ann          — recovery-runner → 各ホスト : ansible-playbook実行用（yoshi/.ssh/id_ann のコピー）
  id_rsa_sophos   — recovery-runner → sophos-fw : Sophos専用鍵
```

各鍵はそれぞれ1つの用途にのみ使われる。`ann` の NOPASSWD ALL 権限をリスナープロセスに直接持ち込まない。

### 3.3 SSH forced commandの制約

authy/monnie 上の `recovery-slack` ユーザーの `authorized_keys` には forced command を設定する。

```text
command="<healthcheck-script>",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty
```

quory 上の `trigger` ユーザーの `authorized_keys` には、対象別 forced command を設定する。

```text
command="/usr/local/bin/recovery-trigger.sh <target> 1",no-agent-forwarding,...,no-pty
```

`no-pty` を設定する場合、SSH クライアント側で `-T` フラグが必要（PTY割り当てエラー回避）。

---

## 4. Sophosの調査方針

OSレベルの深堀り（SSH等）は行わない。判定はansy/quoryからの外部到達性アクティブprobe（pingによるWAN reachability確認）のみで行う。Sophos自身のログ機構が壊れていても検知できることを重視する。

Sophos上の追加調査が必要な場合は、本ポリシーの対象外とし、人間が判断する（§7のエスカレーション経路に乗る）。

---

## 5. 実行権限境界（Claude -p モードの制約）

### 5.1 基本方針

Slackアジェンティックループ（§6.3）でClaude Code を `-p`（print / non-interactive）モードで呼び出す。このとき **`allow` リストは機能しない。`deny` リストのみが有効**。

```text
【確認済み制約】
  claude -p --setting-sources project --permission-mode dontAsk
    → .claude/settings.json の permissions.allow は無視される
    → permissions.deny のみが有効

  Claude Code workspace 設定（/etc/recovery/claude-ws/.claude/settings.json）:
    {
      "permissions": {
        "deny": ["Bash", "Write", "Edit", "Read", "Glob", "Grep"]
      }
    }
```

これにより、Claude Code がツールを使おうとしても全拒否される。Claude は JSON テキストを返すだけで、副作用はすべてPython側が担う。

### 5.2 接続先の制御単位

従来方式（playbook許可リスト / PreToolUseフック）は採用しなかった。実際の制御は以下の3層で行う。

| 層 | 制御点 | 内容 |
|---|---|---|
| Claudeツール制限 | deny リスト | Bash/Write/Edit/Read/Glob/Grep を全 deny。Claude はツールを一切実行できない |
| Pythonアクション固定 | `ACTIONS` dict | Claude が選べるアクションはPythonに固定列挙されたもののみ。文字列を自由組み立てできない |
| SSH forced command | authorized_keys | 接続先ホスト側で強制的に1コマンドのみ実行。それ以外は拒否 |

`recovery_*` playbookは、`target` 変数を信用せず、実行直前にProxmoxのタグ（`hacritical` / `ops` / `prefer*`）をAnsible tasks側で再照会して適格性を確認する（core.md §7の責務分離）。タグと一致しない場合は実行せず失敗として終了する。

---

## 6. トリガー伝達経路

### 6.1 authy / monnie → quory（systemd OnFailure=）

systemd `OnFailure=` フックから、SSH forced command方式でquoryへ自動通知する。

```text
各対象ホストにdrop-inファイルを設置:
  /etc/systemd/system/<unit>.d/recovery_trigger_override.conf
    OnFailure=recovery-notify-quory@<target>.service

送信元: authy/monnie 上の専用 systemd service（recovery-notify-quory@<target>.service）
使用鍵: /etc/recovery/<target>-recovery.key（対象ホスト側に保管）
着地先: quory の trigger ユーザー（forced command）
```

### 6.2 外部到達性低下時（probe失敗）

quory上でping probeを実行し、失敗時に `recovery-trigger.sh <target> 0` を直接呼ぶ。

### 6.3 Slackメンション経由（手動・アジェンティックループ）

ユーザー本人がSlackで `@Homelab` にメンションして調査・復旧を依頼する経路。

**アーキテクチャ概要:**

```text
Slack mention
  → recovery-slack-listener.py (ansy上のsystemd service)
    → run_loop() : Python がオーケストレーション
      → Claude Code -p : JSON アクション決定のみ返す（副作用ゼロ）
        → Python が ACTIONS dict からアクションを実行
          → 結果をhistoryに蓄積 → 次ターンのプロンプトに追加
      → MAX_TURNS=6、終了時に Slack へ返答
```

**利用可能なアクション（固定列挙）:**

```text
調査系:
  authy_healthcheck       — authy の FreeRADIUS 状態を SSH forced command 経由で取得
  monnie_healthcheck      — monnie の monitoring stack 状態を SSH forced command 経由で取得
  network_probe_authy     — authy への ping
  network_probe_monnie    — monnie への ping
  network_probe_sophos_fw — sophos-fw への ping

復旧系（Python側のガードを通過した場合のみ実行可能）:
  trigger_recovery_authy     — SSH で quory:trigger → recovery-pipeline.sh authy
  trigger_recovery_monnie    — SSH で quory:trigger → recovery-pipeline.sh monnie
  trigger_recovery_sophos_fw — SSH で quory:trigger → recovery-pipeline.sh sophos-fw

終了:
  done — 調査完了。message フィールドに Slack 向け日本語返答
```

**Python側の trigger ガード（`_TRIGGER_PREREQ` + `_is_unhealthy()`）:**

`trigger_recovery_*` を実行する前に、Pythonは以下を検証する。

```text
1. 同一 run_loop 内で対応する healthcheck / probe が実行済みか
   （未実行なら Python が即拒否し、エラーを history に積んで続行）

2. その結果が「異常あり」と判定されるか
   （healthcheck が ok=True を返し、かつサービスが non-active であること）
   （ok=False = SSH/ping失敗 = 異常の確証なし → 拒否）

3. 両方クリアした場合のみ trigger SSH を実行する
```

この検証はClaude側ではなくPython側で行う。Claudeの判断のみに依存しない（core.md §7の責務分離）。

**Slack Appスコープ:**

```text
app_mentions:read, chat:write（Socket Mode）
```

認可済みユーザー（`SLACK_AUTHORIZED_USER_ID`）からのメンションのみ処理する。他ユーザーは無視。

§6.1の自動経路との差分:

```text
- §9の24時間フラッピングカウントはスキップする（人間の明示依頼のため）
- 実行中ロック（§6.4）は適用する
- 復旧の実行可否は自動経路と同じくProxmoxタグ判定に従う
```

### 6.4 `recovery-trigger.sh` の前提チェック（実行順序）

```text
1. target 検証（allowlist: authy / monnie / sophos-fw のみ）
2. 実行中ロック確認（同targetで前のパイプラインが稼働中ならskip）
3. muteファイル確認（§7、メンテナンス系playbookがmute中ならskip）
4. flapping count（直近24時間3回以上 → 即エスカレーション）
5. すべて通過 → バックグラウンドで recovery-pipeline.sh 起動（SSH接続をブロックしない）
```

---

## 7. ミュート/TTL機構

メンテナンス系playbookが「今このtargetに触っている」ことを自己宣言する仕組み。明示的なclearは行わず、TTL自然失効に任せる。

```text
ファイル: /var/lib/homelab-recovery/mute/<target>.json
形式:     { "until": "<ISO8601+09:00>", "reason": "..." }
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

承認なし、各段1回のみ試行。各段は専用playbook（§13参照）で実行する。

```text
（Slackループまたは systemd OnFailure=）
  ↓ trigger_recovery_<target>
    ↓ recovery-trigger.sh <target> <manual>
      ↓ recovery-pipeline.sh <target> <escalate_immediately>
        ├─ LADDER1: recovery_service_restart.yml（sophos-fw は対象外）
        │    OK  → 完了（Slack通知）
        │    NG  ↓
        ├─ LADDER2: recovery_vm_reboot.yml
        │    OK  → 完了（Slack通知）
        │    NG  ↓
        ├─ LADDER3: recovery_ha_failover.yml（hacritical タグなしは playbook 内で拒否）
        │    OK  → 完了（Slack通知）
        │    NG  ↓
        └─ ESCALATE: recovery_escalate.yml（Slack通知、自動対応終了）
```

`recovery_vm_reboot.yml` はソフトリブート（ACPI/guest agent経由）を試行し、タイムアウト内に復帰しなければ強制電源断＋起動にフォールバックする。この内部フォールバックも含めて「1回」と数える。

各段の試行・結果は §10 に従い都度Slackへ通知する。

---

## 9. flapping対策

| 仕組み | 目的 | 性質 |
|---|---|---|
| 実行中ロック（`/var/run/homelab-recovery/<target>.lock`） | 並行実行防止 | EXIT trap で自動解放 |
| 直近24時間のトリガー回数（`/var/lib/homelab-recovery/counts/<target>.json`） | 繰り返し失敗時の暴走防止 | 回数ベース。3回以上で即エスカレーション |

Slackループ（手動依頼）はflappingカウントをスキップする（人間の明示依頼のため）。ただしロックは適用する。

---

## 10. Slack通知仕様

**新規Slack App / Incoming Webhook スコープは不要。** 既存の `slack_webhook_alerts`（Vault管理済み）をそのまま流用する。Slack Appに必要なスコープは `app_mentions:read` / `chat:write`（Socket Mode）のみ。`incoming-webhook` スコープは不要であることを実装で確認済み。

```text
通知タイミング:
  - トリガー受理時（recovery_notify_trigger.yml）
  - 各ラダー段の試行結果（recovery_service_restart / vm_reboot / ha_failover 各 playbook 内）
  - 最終エスカレーション時（recovery_escalate.yml）

通知方法: 既存 roles/common_slack/tasks/notify.yml と同一方式
失敗時の扱い: best-effort。通知失敗で本処理を止めない（既存方針を継承）
送信先チャンネル: alerts（既存 slack_webhook_alerts を流用）
タイムゾーン: JST（TZ=Asia/Tokyo）で統一
```

---

## 11. ログ・レポート

| 種別 | 保存先 | 保持期間 | 用途 |
|---|---|---|---|
| パイプライン生ログ | `/var/log/homelab-recovery/<target>_<timestamp>.log` | logrotate管理 | 調査・デバッグ |
| 構造化レポート | `reports/recovery_investigations/<target>/<timestamp>.json` | 長期（既存 `reports/**` 方針） | トリガー理由・試行内容・成否の記録 |
| systemd syslog | journald（`homelab-recovery*` タグ） | システム標準 | trigger.sh / pipeline.sh の起動・終了ログ |

monnieのLoki/Grafana（ネットワーク可視化用）とは完全に独立させる。混在させない。

---

## 12. 禁止事項

```text
- Claude Code に Bash / Write / Edit / Read / Glob / Grep を許可する
  （-p モードでは allow は機能しないため deny リストで制御すること）
- Python の ACTIONS dict に列挙されていないアクションを Claude に実行させる
- recovery_* playbook で Proxmox タグ再検証を行わずに実行する
- trigger_recovery_* を、対応する healthcheck の実行・異常確認なしに実行する
  （Python 側の _TRIGGER_PREREQ + _is_unhealthy() ガードを撤廃しない）
- 同一 run_loop 内で同一アクションを2回以上実行することを許可する
  （Claude の system prompt に「同じアクションを2回実行しないこと」を明記し維持すること）
- 3 primitive（service restart / VM reboot / HA failover）以外の変更操作を自動実行する
- ラダーの各段を2回以上自動で繰り返す
- Sophos 上で OS レベルの調査（SSH等）を自動的に行う
- §2 の対象外ホスト（pve1 / pve2 / ansy）を復旧アクションの対象にする
- アクション一覧（§6.3）や対象許可リスト（§6.4）を実装側の判断で拡張する
```

---

## 13. 実装コンポーネント一覧

| コンポーネント | ホスト | 実装 | 役割 |
|---|---|---|---|
| `recovery-slack-listener.service` | ansy | `roles/recovery_slack_listener` | Slackメンション受信・アジェンティックループ（§6.3） |
| `recovery-slack-listener.py` | ansy | template | run_loop / ACTIONS / _is_unhealthy / _ask_claude |
| Claude Code workspace | ansy | `/etc/recovery/claude-ws/` | deny設定のみ。`--setting-sources project` で読み込み |
| `CLAUDE_CODE_OAUTH_TOKEN` | ansy | Vault管理（`vault_claude_code_oauth_token`） | Claude Code の認証トークン。`claude setup-token` で発行した OAuth トークン（`sk-ant-oat01-` 形式）を使用。`ANTHROPIC_API_KEY` は使わない（§14.5参照） |
| `recovery-trigger.sh` | quory | `roles/recovery_trigger` | §6.4チェック（lock/mute/flapping） → pipeline起動 |
| `recovery-pipeline.sh` | quory | `roles/recovery_trigger` | ラダー実行（LADDER1/2/3/ESCALATE） |
| `recovery-runner` ユーザー | quory | `roles/recovery_trigger` | ansible-playbook専用実行ユーザー |
| `trigger` ユーザー | quory | `roles/recovery_trigger` | SSH forced command着地 → recovery-trigger.sh 起動 |
| `recovery-slack` ユーザー | authy / monnie | `roles/recovery_slack_listener` | SSH forced command着地 → healthcheck script 実行 |
| `monitoring_healthcheck.sh` | monnie | `roles/monitoring_healthcheck` | prometheus / grafana / loki / unpoller の状態収集 |
| `recovery_service_restart.yml` | quory実行 → 対象VM | 新規 | サービスrestart（タグ再検証含む） |
| `recovery_vm_reboot.yml` | quory実行 → pve | 新規 | VMリブート（タグ再検証含む） |
| `recovery_ha_failover.yml` | quory実行 → pve | 新規 | HAフェイルオーバー（タグ再検証含む） |
| `recovery_notify_trigger.yml` | quory実行 | 新規 | トリガー受理通知をSlackへ送信 |
| `recovery_escalate.yml` | quory実行 | 新規 | エスカレーション通知をSlackへ送信 |
| mute設定タスク | 各playbook | `roles/recovery_mute` | 既存5playbookへ追記済み |

---

## 14. 実装教訓

### 14.1 monitoring_healthcheck.sh への unpoller 追加漏れ

`monitoring_healthcheck.yml`（monnie向けサービス状態収集）を新規実装した際、`unpoller.service` の収集が漏れていた。

**実際の経緯:**
1. 初期実装では `prometheus / grafana-server / loki` の3サービスのみを収集対象としていた
2. E2Eテスト中、unpoller の状態がどの調査結果にも一度も現れなかった
3. CC自身が「monitoring_healthcheck.sh に unpoller.service は含まれていません」と明言した
4. ユーザーが追加を指示し、CC が実装した（`systemctl is-active unpoller` のみ、ポートチェックなし）
5. unpoller を停止してのSlackテストで、初めて正しく異常検知→復旧トリガーが動くことを確認した

**問題の構造:** `_is_unhealthy("monnie_healthcheck", result)` は `data.services` の全値を走査するため、unpollerが収集対象になければ停止しても「全サービス active」と判定され、復旧がトリガーされない。サイレントに機能しないため発見が遅れた。

**教訓:** 新規 healthcheck を作成する際は、§2.1 の systemdユニット対応表と照合し、対象ユニットが全て収集されていることをレビュー時に確認する。healthcheck の収集対象と `_is_unhealthy()` の判定対象は一致させる。「収集漏れはエラーにならず結果が正常扱いになる」という性質を念頭に置くこと。

### 14.2 SSH forced command と nologin シェルの非互換

`trigger` ユーザーおよび `recovery-slack` ユーザーのシェルを `/usr/sbin/nologin` に設定すると、SSHのforced command実行時に `This account is currently not available.` となり接続失敗する。

**原因:** SSHは forced command を `shell -c "forced_command"` の形で起動する。`nologin` はこれを拒否する。

**対処:** forced command を使うユーザーのシェルは `/bin/sh` に設定する。インタラクティブログインは `authorized_keys` の `no-pty` / パスワード無効（`!`）で防ぐ。

### 14.3 Claude -p モードでは allow が機能しない

Claude Code を `-p`（non-interactive / print）モードで呼び出す場合、`settings.json` の `permissions.allow` は無視される。`permissions.deny` のみが有効。

**対処:** deny リストに `["Bash", "Write", "Edit", "Read", "Glob", "Grep"]` をすべて列挙する。allow は書かない。

### 14.4 ANTHROPIC_API_KEY ではなく CLAUDE_CODE_OAUTH_TOKEN を使う理由

Claude Code を非対話モード（`-p`）で呼び出す際の認証方式として、`ANTHROPIC_API_KEY`（API直接課金）ではなく `CLAUDE_CODE_OAUTH_TOKEN`（Claude Maxサブスクリプション）を使用する。

**決定の経緯:** `recovery-slack` ユーザーで `claude -p` を実行したところ "Not logged in" エラーが発生した。`ANTHROPIC_API_KEY` を設定する方式も検討したが、すでに Claude Max サブスクリプションを契約済みであるため、API従量課金を別途追加する必要がない。`claude setup-token` を実行してブラウザ経由で発行した OAuth トークン（`sk-ant-oat01-` 形式）を `~/.claude/.credentials.json`（`claudeAiOauth.accessToken` フィールド）から取得し、Vault に格納した。

**運用上の注意:**
- このトークンは Claude Max サブスクリプションの月額内に含まれる（追加課金なし）
- トークンが失効した場合、`claude setup-token` を再実行して vault を更新する必要がある
- `ANTHROPIC_API_KEY` が環境変数に存在する場合でも `CLAUDE_CODE_OAUTH_TOKEN` が優先される

### 14.5 ansible-playbook の become_user に ACL 問題

Ansible で `become: true` + `become_user: <別ユーザー>` を組み合わせる場合、対象ホストで `setfacl` が使えない環境では `chmod: invalid operator` エラーになる。

**対処:** `become_user` を使わず、コマンド内で `sudo -u <user> <command>` の形に変える。

---

## 15. 未決事項

実装完了により、v0.3 時点の未確定事項の大半は解消した。以下のみ残存する。

- recovery_vm_reboot.yml および recovery_ha_failover.yml の実機検証（monnie以外の対象でのテスト未実施）
- systemd `OnFailure=` 経由の自動トリガーの実機検証（現在はSlackループ経由の手動トリガーのみ確認済み）
