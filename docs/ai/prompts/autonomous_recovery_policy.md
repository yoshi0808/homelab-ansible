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
| pve1 / pve2 | - | - | 対象外(`proxmox_patch_policy.md`の枠組みに委ねる) | 対象外(read-only調査のみ§4.6の対象) |
| ansy | - | - | 対象外(開発環境) | - |

この2つの経路は独立した別の障害クラスを扱う。

- **自己回復(サービスrestart)はVM内部の出来事**であり、個別サービスのクラッシュを検知して直す。sophos-fwには自己回復対象サービスが無いため、この経路自体が存在しない。
- **pingベースのラダーはVM単位の生死判定**であり、対象VM上でどのサービスが動いているかを問わない。pveshで状態を確証したうえで、runningのまま無応答ならVM reboot、hacriticalかつ未復旧ならfailoverへ進む(詳細な分岐は§5.1)。

pve1/pve2は自律復旧アクション(自己回復・pingベースのラダー)の対象外であり、この点は変更しない(`proxmox_patch_policy.md`の枠組みに委ねる)。一方、read-onlyの調査(investigate)のみ§4.6の対象に含む。復旧アクション(action_services相当)は追加しない。

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

対象ホストの`/usr/local/sbin/recovery-investigate-dispatch.sh`が`$SSH_ORIGINAL_COMMAND`をcase文で照合する。許可される値は`roles/recovery_exec/defaults/main.yml`の`recovery_exec_targets[].investigate_services`(サービス名 / `journal-<service>`、および期間・優先度指定の`journal-<service>-{1h,24h,err,warn}`)と`investigate_extra`(ノード別の固定コマンド)、および共通システムチェック(`failed`/`disk`/`memory`/`load`/`network`/`ports`/`journal-system`/`dmesg`)。一致しない値は`denied`で拒否する。

#### 4.1.1 調査バリエーションの追加手順

新しい調査コマンド(読み取り専用の確認のみ。復旧コマンドの追加は§4.2の対象外)を増やす場合、原則`roles/recovery_exec/defaults/main.yml`の`recovery_exec_targets[]`を編集するだけでよい。

- **既存サービスの状態確認を増やす**: 該当ノードの`investigate_services`にサービス名を追加する。`<svc>`/`journal-<svc>`のcase分岐と`status`集計表示に自動反映される。
- **任意の読み取り専用コマンドを追加する**: 該当ノードの`investigate_extra`に`{name, cmd}`を追加する。コマンドが`sudo`を必要とする場合は、`roles/recovery_exec/templates/sudoers-recovery-exec-target.j2`にも対応するNOPASSWDエントリを追加する(`investigate_extra`から自動生成されないため個別対応が必要)。

`recovery_exec_targets`は、quory側wrapper(`roles/recovery_exec/templates/homelab-investigate.sh.j2`)と対象ホスト側dispatch(`recovery-investigate-dispatch.sh.j2`)両方の許可リストを同時にレンダリングする単一のソースであり、この2ファイルを直接編集する必要はない。

追加後に行うこと:

1. `roles/recovery_exec/templates/AGENTS.md.j2`の該当ノードのセクションに説明を追記する(手書きのドキュメントで自動生成されないため、追記しないとCodexがそのチェックの存在を認識しない)
2. `ansible-playbook playbooks/recovery_exec_setup.yml -l quory`を再実行する(wrapper・dispatch script・AGENTS.mdが同じroleで配備されるため1回で反映される)

全ノード共通のチェック種別自体(`failed`/`disk`/`memory`等と同格の新カテゴリ)を新設する場合に限り、`recovery-investigate-dispatch.sh.j2`と`homelab-investigate.sh.j2`の両方のcase文に直接追記が必要(この部分のみデータ駆動ではない)。`dmesg`共通チェックと、`investigate_services`の各サービスに対する`journal-<svc>-{1h,24h,err,warn}`(期間・優先度指定)は、この方式でテンプレート側に直接実装している(defaults/main.ymlの編集だけでは増えない)。

### 4.2 action系コマンド(復旧)

対象ホストの`/usr/local/sbin/recovery-action.sh`は引数を受け取らず、接続されただけで`recovery_exec_targets[].action_services`に列挙された全サービスを`systemctl reset-failed <svc> || true` → `systemctl restart <svc>`で一括再起動する(個別サービス指定はしない)。`reset-failed`は、OnFailure発火直後の`StartLimitIntervalSec`ウィンドウ内でのrestartがsystemdのstart-limitに拒否されるレースを避けるためのもの。

### 4.3 reportsレポート調査(`homelab-reports`)

quoryローカルの`~/homelab-ansible/reports/<playbook>/`配下のJSONレポート(healthcheck等の実行結果)を参照するための調査コマンド。SSHホップは無く、quory上で完結する。

- `list-playbooks` / `list-reports <playbook> [target]` / `show-report <playbook> [target] <filename>`の3コマンドのみ。`target`は`recovery_investigations/<target>/`のようなネスト構造(自律復旧パイプライン自身の調査ログ)向けの追加path segmentを1つだけ許可するもので、ほとんどのplaybook(フラット構造)では使わない。
- ベースパス(`~/homelab-ansible/reports`)は固定。`playbook`/`target`/`filename`は`[a-zA-Z0-9_-]+`(filenameは末尾`.json`必須)のみ許可し、スラッシュ・ドットを含む値はトラバーサル防止のため拒否する。`list-reports`は`*.json`のみを列挙する(非JSONファイルが混在するplaybookディレクトリがあるため)。
- `reports/`は`/home/yoshi`配下にあり、recovery-execは直接読めない。POSIXACL(`recovery-exec:x`)で`/home/yoshi`のtraverseのみを付与し、`reports/`以下(既に0755/644)を直接読む。sudo/setuidによる昇格は使わない(§4.5参照)。
- `homelab-reports`(引数検証)→ `recovery-reports-helper`(再検証してから読む)の2層構成。investigate系のローカルwrapper→SSH forced commandの2層検証と同じ考え方だが、ここでは権限昇格自体が発生しない。

### 4.4 Semaphore失敗タスク調査(`homelab-semaphore-query`)

quoryの`/var/lib/semaphore/semaphore.db`(SQLite、`yoshi:yoshi 0600`、`journal_mode=delete`。`-wal`/`-shm`副ファイルは無し)を read-only で参照し、Semaphoreタスクの失敗原因を調査するコマンド。

- Codexは`recent-failed <n>` / `task-errors <id>` / `task-hosts <id>` / `task-output <id>`の4種の定型クエリ名と、整数パラメータ(`n`は1-200、`id`)のみを選択する。SQL本文は`homelab-semaphore-query`内に固定文字列として持ち、自由なSQLは受け付けない。
- `/var/lib/semaphore`のtraverseと`semaphore.db`の読み取りをPOSIX ACL(`recovery-exec:x` / `recovery-exec:r`)で付与する。sudoは使わない(§4.5参照)。`-readonly`フラグにより、万一SQL側に細工があっても書き込みはSQLiteエンジン側で拒否される。
- 完成したSQL文字列は配列(`exec ... "$sql"`)としてsqlite3へ渡し、シェル経由の文字列連結・再解釈を行わない。

### 4.5 なぜsudoを使わないか(2026-07-05判明)

②③は当初sudoersベースの権限昇格(`(yoshi)`/`(root)`)で設計したが、Slackからの実運用テストで`sudo: The "no new privileges" flag is set, which prevents sudo from running as root.`により失敗することが判明した。

原因は、Codexが`codex exec --sandbox workspace-write`で起動される際にサンドボックス側が`no_new_privileges`を設定するため。このフラグは sudo・setuid・ファイルcapability経由の権限昇格を**sudoersの設定に関わらず一律ブロックする**(Linuxカーネルの`no_new_privileges` prctlの仕様通り)。フラグ自体を解除するとサンドボックス全体の防御が弱まるため不採用。

代わりにPOSIX ACL(`setfacl`相当、`ansible.posix.acl`で付与)を使う。ACLは対象ユーザー(`recovery-exec`)自身が最初から持つ権限ビットを増やすだけで、別ユーザーへの昇格が発生しないため`no_new_privileges`の影響を受けない。

この問題はreviewer・testerのレビュー/テストでは検出されなかった。理由は、tester はAnsible ad-hocの`command`モジュール経由(通常のsudoが効く環境)で検証しており、Codexサンドボックス内の実行パスを実際には通していなかったため。**「テストが通った」ことと「本番の実行経路を通った」ことは別**という教訓であり、副次的に「sudo昇格という環境依存処理」自体が無くなったことで、tester dry-runと本番実行の挙動差も併せて解消される。

補足(§4.6との関係): pve1/pve2向けのsudo(§4.6)はpve1/pve2上のSSHセッション内で完結するため、ここで述べた`no_new_privileges`問題そのものには該当しない。ただし「sudoは呼び出し環境によって想定と異なる挙動をする」という同種の教訓から、pve側では`requiretty`(tty無しsudoの拒否)を別のリスクとして事前に洗い出し、実機確認済み(§4.6、問題なし)。

### 4.6 Proxmoxクラスタ状態調査(`homelab-investigate-pve1` / `homelab-investigate-pve2`)

pve1/pve2のProxmoxクラスタ/HA状態をread-onlyで調査するコマンド。pve1/pve2は自律復旧アクションの対象外(§2)であり、これは変更しない。追加するのは調査のみで、`action_services`に相当する復旧手段は一切追加しない。

- 鍵は`id_recovery_investigate`(authy/monnie用)とは別に、pve専用の`id_recovery_investigate_pve`を新規に1本用意する。許可リストの中身が全く違う(pvesh/ha-manager系 vs freeradius/journal系)ため、目的別に鍵を分け取り違えを防止する。この1本をpve1・pve2両方の`authorized_keys`に登録する(片方が落ちていてももう片方から調査できるようにするため)。
- `ann`の鍵・権限は使わない(§10)。pve1/pve2にも`ann`とは別の、forced command専用の`recovery-exec`着地アカウントを新設する(authy/monnieと同じ構成)。
- named checkは3種のみ: `cluster-status` / `cluster-resources` / `ha-status`。対応する実行コマンドは、このリポジトリ内で既に実績のある呼び出しをそのまま流用する(新規のAPIパスを推測しない):
  - `cluster-status` → `pvesh get /cluster/status --output-format json`(`roles/recovery_ha_failover/tasks/main.yml`で実績)
  - `cluster-resources` → `pvesh get /cluster/resources --output-format json`(多数のroleで実績)
  - `ha-status` → `ha-manager status`(`roles/proxmox_evacuate_node`, `roles/proxmox_restore_vm_placement`で実績)
- `pvesh create`/`set`/`delete`は許可リストに存在しないため構造的に実行できない。`/nodes/<node>/status`相当の個別ノード状態(node-status)は、このリポジトリ内に実績が無く、かつ`cluster-resources`のレスポンス(`type=node`のエントリ)で代替できるため、今回は追加しない。
- sudoersは完成形3本を1:1で列挙し、ワイルドカードは使わない:
  ```
  recovery-exec ALL=(root) NOPASSWD: /usr/bin/pvesh get /cluster/status --output-format json
  recovery-exec ALL=(root) NOPASSWD: /usr/bin/pvesh get /cluster/resources --output-format json
  recovery-exec ALL=(root) NOPASSWD: /usr/sbin/ha-manager status
  ```
  §4.3/§4.4がACLに切り替えたのに対し、ここでは通常のsudoersを使う。理由は、このsudoがpve1/pve2上のSSHセッション内(sshd経由)で完結し、quory側Codexサンドボックスの`no_new_privileges`問題(§4.5)が発生する経路(quory上でCodexプロセス自身がsudoを呼ぶ経路)を一切通らないため。ACLに変更する必要が無い。Proxmox(Debianベース)のsudoersデフォルトがauthy/monnie(Ubuntu)と異なりforced command経由(tty無し)のsudoを`requiretty`等で拒否する可能性を事前に懸念していたが、2026-07-05にansy起点・quory起点の両方で実機確認済み: `cluster-status`/`cluster-resources`/`ha-status`とも forced command 経由(no-pty、`sudo -n`)で問題なく成功し、`requiretty`による拒否は発生しなかった。`ha-manager`のフルパスも両ノードで`/usr/sbin/ha-manager`と一致することを確認済み(sudoersの想定通り)。

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

Slack(`@Homelab`メンション、Socket Mode)からのリクエストを受け、`sudo -H -u recovery-exec codex-exec-wrapper exec --cd <workspace> "<メッセージ>"`でCodexへジョブとして渡す。`-H`はrecovery-execの`~/.codex`を使うために必要。結果はSlackスレッドに日本語で返信される。

---

## 6. Codex実行環境の安全設計

- Codex側で任意コマンドを実行できないよう、execpolicy(`default_policy="deny"`)とし、許可する外部コマンドを以下のwrapperのみに限定する:
  - `homelab-investigate-{authy,monnie}`(調査)
  - `homelab-investigate-{pve1,pve2}`(調査。Proxmoxクラスタ/HA状態、read-only。§4.6)
  - `homelab-reports`(調査。`reports/`配下のJSONレポート参照。§4.3)
  - `homelab-semaphore-query`(調査。Semaphore失敗タスクの原因解析。§4.4)
  - `homelab-recover-{authy,monnie}`(復旧)
  - `homelab-monitoring-{pause,resume,status}`(監視制御)
- pve1/pve2には`homelab-recover-*`に相当する復旧wrapperを一切用意しない。Codexが呼べるのは§4.6の3つのread-only named checkのみ。
- VM reboot(`qm reboot`相当)・HA failover(`ha-manager crm-command relocate`)はCodexのexecpolicyに含まれない。これらは§5.1のpull経路からのみ、決定論的に(target固定の`ansible-playbook`呼び出しとして)実行される。
- `codex-exec-wrapper`は引数を`exec` / `--cd` / 固定workspaceパス / メッセージ本文の4つに厳密に限定し、個数・各位置の値が一致しなければ拒否する。sandbox・approval・execpolicyに関わるCLIオプションは呼び出し元から一切受け取らず、wrapper内部で固定する(`--sandbox workspace-write`, `approval_policy="never"`, `network_access=true`)。
- sandboxは実行後の動作(書き込み・ネットワーク到達)を制御する層、execpolicyは「そもそも呼べるコマンドの範囲」を制御する層であり、別物として扱う。sandboxは読み取りを制限しないため、機密ファイル(Slackトークン・SSH鍵)の保護は常にOSファイル権限(0600 + 専用ユーザー所有)が担う。
- `--sandbox workspace-write`はプロセスに`no_new_privileges`を設定する(2026-07-05、実運用で判明)。これにより、Codexから呼ばれるwrapper内でのsudo・setuid・ファイルcapability経由の権限昇格は、sudoers等の設定に関わらず一律失敗する。**Codexが呼ぶwrapperは権限昇格を前提に設計しない**。読み取り権限が足りない場合はsudoではなくPOSIX ACL(対象ユーザー自身への直接付与)を使う(§4.5)。

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

いずれもprobeの現在状態やサービス健全性を発火条件にはせず、`target=`が妥当なら人間判断で直接起動できる(発火判断の責任は人間側にある)。ただし対象allowlist・タグ再検証・VM存在確認・HA登録確認などのsafety gateは実装側で維持される。レポート保存・Slack通知(best-effort)は自動経路と共通。

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
