# Autonomous Recovery Policy

対象: authy / monnie / sophos-fw の異常検知 → 自律復旧パイプライン

参照:

- docs/ai/prompts/core.md
- docs/ai/prompts/proxmox_patch_policy.md

本書は現在実装されている自律復旧パイプラインの仕様を記述する。実装の変遷や設計判断の経緯は含まない。

---

## 1. 目的

authy / monnie / sophos-fw の業務継続を、人間の承認を待たずに自律的な復旧試行で支える。Slackは承認ゲートではなく、手動依頼の入口と結果通知に使う。

---

## 2. 対象と適用される復旧手段

| 対象 | タグ | VMID | 自己回復(サービスrestart) | pingベースのラダー(VM reboot / failover) |
|---|---|---|---|---|
| sophos-fw | `hacritical`, `preferpve1` | 1000 | なし | VM reboot → failover |
| authy | `hacritical`, `preferpve1` | 101 | freeradius | VM reboot → failover |
| monnie | `ops`, `preferpve2` | 211 | prometheus / grafana-server / loki / unpoller | VM reboot(failoverなし) |
| pve1 / pve2 | - | - | 対象外(`proxmox_patch_policy.md`の枠組みに委ねる) | - |
| ansy | - | - | 対象外(開発環境) | - |

この2つの経路は独立した別の障害クラスを扱う。

- **自己回復(サービスrestart)はVM内部の出来事**であり、個別サービスのクラッシュを検知して直す。sophos-fwには自己回復対象サービスが無いため、この経路自体が存在しない。
- **pingベースのラダーはVM単位の生死判定**であり、対象VM上でどのサービスが動いているかを問わない。ping無応答は常にVM reboot、hacriticalタグがあれば追加でfailover、という一律の対応になる。

---

## 3. アカウント構成

| Identity | 配置 | 目的 | 保持する鍵・情報 |
|---|---|---|---|
| `ann` | 既存の対象ホスト全般 | 既存の定常自動化(patch/evacuate/restore等)専用 | NOPASSWD ALL sudo、forced command無し |
| `recovery-io` | quory | Slack接続(Socket Mode)。認可チェックのみ | Slack Bot Token / App Token のみ |
| `recovery-exec` | quory | Codexの呼び出し、調査・復旧の実行。常駐プロセスではなく、recovery-ioまたはOnFailure pushから呼ばれた時だけCodexを起動する | 調査用キー1本、action用キー1本。Slackトークンは持たない |
| `recovery-exec`(着地用) | authy / monnie | quory側`recovery-exec`からのSSH接続の着地専用アカウント | forced commandのみ、シェルは`/bin/sh` |
| (yoshi) | quory | `recovery-probe.py`の実行ユーザー。global pauseフラグの読み取りのため`recovery-exec`グループに所属 | - |

`recovery-io`はquoryでのみ稼働する常駐systemdサービス。`recovery-exec`は常駐プロセスを持たない。

---

## 4. 鍵構成

| 鍵 | 保持者 | 対象ホスト | forced commandの性質 |
|---|---|---|---|
| 調査用キー(`id_recovery_investigate`) | quory `recovery-exec` | authy / monnie(共用、1本) | パラメータ受領可。対象ホスト側の`recovery-investigate-dispatch.sh`が許可リスト(case文)照合 |
| action用キー(`id_recovery_action`) | quory `recovery-exec` | authy / monnie(共用、1本) | パラメータ不可。`recovery-action.sh`は接続するだけで固定のサービス再起動一式を実行 |
| push用キー | authy / monnie 各ホスト固有 | quory `recovery-exec`(着地) | quory側`authorized_keys`のforced commandで`recovery-push-dispatch.sh <ホスト名>`に固定。ホスト側からは引数を渡せない |
| `ann`の既存鍵 | `ann`自身 | 既存対象ホスト全般 | forced command無し(既存の定常自動化専用、recovery-execは使わない) |

authy/monnieのauthorized_keysは、この2エントリ(investigate/action)のみをAnsible templateで生成し、都度上書きする(drift防止、`authorized_keys.j2`)。

### 4.1 調査系コマンド(investigate)

対象ホストの`/usr/local/sbin/recovery-investigate-dispatch.sh`が`$SSH_ORIGINAL_COMMAND`をcase文で照合する。許可される値は`roles/recovery_exec/defaults/main.yml`の`recovery_exec_targets[].investigate_services`(サービス名 / `journal-<service>`)と`investigate_extra`(ノード別の固定コマンド)、および共通システムチェック(`failed`/`disk`/`memory`/`load`/`network`/`ports`/`journal-system`)。一致しない値は`denied`で拒否する。

### 4.2 action系コマンド(復旧)

対象ホストの`/usr/local/sbin/recovery-action.sh`は引数を受け取らず、接続されただけで`recovery_exec_targets[].action_services`に列挙された全サービスを`systemctl reset-failed <svc> || true` → `systemctl restart <svc>`で一括再起動する(個別サービス指定はしない)。`reset-failed`は、OnFailure発火直後の`StartLimitIntervalSec`ウィンドウ内でのrestartがsystemdのstart-limitに拒否されるレースを避けるためのもの。

---

## 5. 検知経路

### 5.1 Pull — `recovery-probe.service`(quory常駐)

`recovery-probe.py`が60秒間隔で全対象をprobeする(`/etc/homelab-recovery/recovery-probe.json`)。

| 対象 | probe | 閾値 |
|---|---|---|
| sophos-fw | icmp + dns(`@sophos-fw.internal`への問い合わせ) | 5回連続失敗(=5分) |
| authy | icmp + tcp:22 | 同上 |
| monnie | icmp + tcp:3000 | 同上 |

各対象は`host`フィールドでFQDN(`<target>.internal`)を明示している(短縮名はOSレベルDNSで解決できないため必須)。

発火時の処理(`fire_ladder()`):

1. 実行中ロック(`ladder.lock`をmkdirで取得。既に実行中ならskip)
2. flapping判定(直近24時間で3回以上発火していれば、ラダーを実行せずエスカレーション通知のみ)
3. `pvesh`でVM状態を確証
   - pve自体に到達不能 → critical通知
   - VMが`stopped` → `pvesh start`(rebootではなく起動)→ 復旧確認
   - VMが`not-found` → critical通知
   - 上記以外(runningなのにping無応答=ハング疑い) → 4へ
4. `recovery_vm_reboot.yml`を実行(target固定)。復旧すればok通知で終了
5. 復旧しなければ、対象が`failover: true`(sophos-fw / authy)の場合のみ`recovery_ha_failover.yml`を実行。それでも復旧しなければ人間へエスカレーション通知

### 5.2 Push — systemd `OnFailure=`(authy / monnie)

各対象サービス(authy: freeradius / monnie: grafana-server・prometheus・loki・unpoller)のunitに`OnFailure=recovery-trigger@%p.service`のdrop-inを配置している。

サービスがfailed状態に入ると:

1. `recovery-trigger@.service`(oneshot)が`recovery-push.sh`を実行
2. push用キーでquoryの`recovery-exec`へSSH接続(forced command: `recovery-push-dispatch.sh <host>`)
3. quory側で対象のmute状態を確認、実行中ロック(`mkdir`)を取得
4. `codex-exec-wrapper exec --cd <workspace> "<host>でサービス障害をOnFailureで検知しました。調査・復旧してください。"`でCodexセッションを起動

Codexは`AGENTS.md`の手順(investigate → 判定 → recover → 再investigate → エスカレーション)に従う。VM reboot / failoverへの手段はCodexに渡していない(§6参照)。

### 5.3 Slack — `recovery-io.service`(quory常駐)

Slack(`@Homelab`メンション、Socket Mode)からのリクエストを受け、`sudo -u recovery-exec codex-exec-wrapper exec --cd <workspace> "<メッセージ>"`でCodexへジョブとして渡す。結果はSlackスレッドに日本語で返信される。

---

## 6. Codex実行環境の安全設計

- LLM(Codex)にはBash/Write/Edit/Read等のツールを渡さない。execpolicy(`default_policy="deny"`)で、呼べるコマンドを以下のみに絞る:
  - `homelab-investigate-{authy,monnie}`
  - `homelab-recover-{authy,monnie}`
  - `homelab-monitoring-{pause,resume,status}`
- VM reboot(`qm reboot`相当)・HA failover(`ha-manager crm-command relocate`)はCodexのexecpolicyに含まれない。これらは§5.1のpull経路からのみ、決定論的に(target固定の`ansible-playbook`呼び出しとして)実行される。
- `codex-exec-wrapper`は引数を`exec` / `--cd` / 固定workspaceパス / メッセージ本文の4つに厳密に限定し、個数・各位置の値が一致しなければ拒否する。sandbox・approval・execpolicyに関わるCLIオプションは呼び出し元から一切受け取らず、wrapper内部で固定する(`--sandbox workspace-write`, `approval_policy="never"`, `network_access=true`)。
- sandboxは実行後の動作(書き込み・ネットワーク到達)を制御する層、execpolicyは「そもそも呼べるコマンドの範囲」を制御する層であり、別物として扱う。sandboxは読み取りを制限しないため、機密ファイル(Slackトークン・SSH鍵)の保護は常にOSファイル権限(0600 + 専用ユーザー所有)が担う。

---

## 7. Mute / 一時停止機構

2つの独立した仕組みがある。

| 仕組み | 粒度 | 制御方法 | ファイル |
|---|---|---|---|
| 対象別mute | target単位、TTL付き | `homelab-mute set/status/clear`(CLI)、または各playbookが自動設定 | `/var/lib/homelab-recovery/mute/<target>.json`(`{"until": ISO8601, "reason": "..."}`) |
| グローバルpause | 全target一括、TTLなし(明示的なresumeまで) | `homelab-monitoring-pause/resume/status`(CLI、Slack経由でCodexからも呼べる) | `/var/lib/recovery-exec/workspace/monitoring-paused`(存在すればPAUSED) |

いずれも`recovery-probe.py`のループ先頭でチェックされ、有効な場合はそのサイクルの連続失敗カウンタをリセットしてskipする(mute解除直後にすぐ閾値に達することを防ぐ)。push経路(`recovery-push-dispatch.sh`)も対象別muteを個別に確認する。

対象別muteを自動設定するplaybook: `proxmox_evacuate_node.yml` / `proxmox_patch_apply_node.yml` / `proxmox_restore_vm_placement.yml` / `ubuntu_nightly.yml` / `proxmox_patch_weekly_full.yml` / `cert_renew.yml`(monnieはグローバルpauseで代替)。

---

## 8. 人間による手動レイヤー実行(Semaphore)

push(§5.2)・pull(§5.1)のどちらも検知できない障害クラスがある: **systemdはactive、pingも通るが、実際には機能していない**状態(ハング・機能劣化等)。この場合は人間が気づいてSemaphoreから対応する。

Codexの判断を介さず、3つのレイヤーをそれぞれ独立したplaybookとして人間が直接実行できる。全て`-e target=<対象>`で呼び出す。

| playbook | 対象 |
|---|---|
| `recovery_service_restart.yml` | `authy` / `monnie`(サービスrestartのみ。sophos-fwは対象外) |
| `recovery_vm_reboot.yml` | `authy` / `monnie` / `sophos-fw` |
| `recovery_ha_failover.yml` | `authy` / `sophos-fw`(monnieは対象外) |

いずれも対象の健全性を問わず、`target=`が指定されれば無条件に実行する(発火判断の責任は人間側にある)。タグ再検証・レポート保存・Slack通知(best-effort)は自動経路と共通。

---

## 9. 通知

Slack通知は既存の`slack_webhook_alerts`(Vault管理)を流用し、`common_slack/tasks/notify.yml`経由でbest-effort送信する。通知の送信失敗(ネットワーク断など)は本処理の成否に影響しない。通知タイミング: トリガー受理時、各ラダー段の試行結果、最終エスカレーション時。タイムゾーンはJST。

---

## 10. 禁止事項

- Codexにツール(Bash/Write/Edit/Read/Glob/Grep等)を許可する
- action用キーのforced commandにパラメータを許す
- 調査用キーのforced commandが、受け取った値を許可リスト照合せずにeval・変数展開して実行する
- `recovery_exec_targets`の`action_services`以外への変更操作を自動実行する
- ラダーの各段を2回以上自動で繰り返す(実行中ロックとflapping判定で担保)
- sophos-fw上でOSレベルの調査を自動的に行う(§2の通り、対象外)
- pve1/pve2/ansyを復旧アクションの対象にする
- `recovery-exec`にannの鍵・Slackトークンを持たせる

---

## 11. 既知の制約

- push経路(OnFailure→Codex)でサービスrestartが効かなかった場合、Codex自身にはVM reboot/failoverへ自動で進む手段が無く、人間へのエスカレーションで終わる。pull経路のラダー(§5.1)はping無応答という別の条件でのみ独立して発動する。VM reboot/failoverまで人間が直接持っていきたい場合は§8の手動レイヤー実行を使う。
