# implement: Phase 1 リポジトリ側(タグ適格化 + probe 第2インスタンス化)

日付: 2026-08-02 (JST)
requirement: `2026-08-02_001_requirement.md` R2 / R6
plan: `2026-08-02_002_plan.md` §2

Yoshinobu 側の実機配備(`sandbox` VM / タグ / HA登録 / Semaphore テンプレート3本)は着手前に完了しており、本記録の着手時点の現況は下記「0. 実機の現況」のとおり。

## 0. 実機の現況(着手前に確認)

| 項目 | 値 | 確認手段 |
|---|---|---|
| VM | `name=sandbox` / `vmid=2000` / `node=pve2` / `status=running` | pve2 で `pvesh get /cluster/resources --type vm` |
| タグ | `sandbox`(`prefer*` なし) | 同上 |
| HA登録 | `sid=vm:2000` / `state=ignored` / `failback=0` / `auto-rebalance=0` | pve2 で `pvesh get /cluster/ha/resources` |
| HAルール | **新規なし**。`vm:101` / `vm:1000` の2本は未変更 | pve2 で `cat /etc/pve/ha/rules.cfg` |
| Semaphore | `SANDBOX:` 3本。playbook パス正常、`target` は enum `[sandbox]` | quory の `semaphore.db` |
| 既存 `UN-SAFE:Recovery ha failover(Manual)` | `.yml` 欠落を修正済み | 同上 |

**AC15 充足**(既存2サービスの resources 行・rules 定義とも変更前と同一)。

## 1. 変更内容

### 1.1 ラダー適格タグへの `sandbox` 追加(R2)

| ファイル | 変更 |
|---|---|
| `roles/recovery_vm_reboot/tasks/main.yml` | `hacritical` / `ops` に `sandbox` を追加 |
| `roles/recovery_ha_failover/tasks/main.yml` | `hacritical` に `sandbox` を追加(`ops` は従来どおり対象外) |
| `roles/recovery_service_restart/tasks/main.yml` | `hacritical` / `ops` に `sandbox` を追加。`sophos-fw` 除外は維持 |

3本とも **assert 内のリテラルとして追加**した。role default 等の変数へ括り出していない(`-e` で上書きされると任意の VM がラダー対象になるため)。`fail_msg` の列挙も実態に合わせた。

### 1.2 `recovery_probe` の第2インスタンス化(R6)

`recovery_probe_instance`(既定 `""` = 本番)を導入し、そこから unit 名・設定パス・状態ディレクトリを導出する。

| 変数 | `instance=""`(本番) | `instance=sandbox` |
|---|---|---|
| `recovery_probe_unit_name` | `recovery-probe` | `recovery-probe-sandbox` |
| `recovery_probe_config_path` | `/etc/homelab-recovery/recovery-probe.json` | `/etc/homelab-recovery/recovery-probe-sandbox.json` |
| `recovery_probe_state_dir` | `/var/lib/homelab-recovery/probe` | `/var/lib/homelab-recovery/probe-sandbox` |

`recovery_probe_mute_dir` と `recovery_probe_monitoring_pause_flag` も変数化した(既定は本番値)。第2インスタンスで本番と共有すると本番の mute が検証側を黙らせるため、分ける場合は明示的に上書きする。

**daemon 本体は共有する。** `ExecStart` は両インスタンスとも `/usr/local/sbin/recovery-probe.py` であり、コードは複製しない。分離するのは設定と状態だけである。

変更ファイル: `defaults/main.yml`、`templates/recovery-probe.json.j2`、`templates/recovery-probe.service.j2`、`tasks/main.yml`、`handlers/main.yml`。

## 2. 自己検証

すべて実ホストへ変更を加えずに実施した。

| # | 検証 | 手段 | 結果 |
|---|---|---|---|
| V1 | 3本の playbook が構文として通る | `ansible-playbook <各> --syntax-check -e target=sandbox` | PASS |
| V2 | タグ判定式が実タグを正しく分類する | 使い捨て playbook(`hosts: localhost` / `connection: local` / 副作用なし)で9ケースを評価。実行後に削除 | 下表 |
| V3 | `tags` が None / 欠落のときに落ちない | 同上 + `pvesh` の生 JSON で `tags` キーの有無を確認 | PASS(下記) |
| V4 | **本番の描画結果が配備物とバイト一致する** | 既定値でテンプレートを描画し、quory の配備済み `/etc/homelab-recovery/recovery-probe.json` と `/etc/systemd/system/recovery-probe.service` を `diff` | **両方 IDENTICAL** |
| V5 | `instance=sandbox` で全パスが分離される | 同じ描画を `-e recovery_probe_instance=sandbox` で実施 | PASS(下記) |
| V6 | lint | `ansible-lint roles/recovery_probe playbooks/recovery_probe_setup.yml` | `0 failure(s), 0 warning(s)`(profile: production) |

### V2 の結果

| ケース(実タグ) | reboot 適格 | failover 適格 |
|---|---|---|
| `hacritical;preferpve1;verify`(sophos-fw) | ○ | ○ |
| `ops;preferpve2;verify`(monnie) | ○ | **×**(従来どおり) |
| `sandbox` | ○ | ○ |
| `preferpve2`(ansy) | × | × |
| `""`(空文字列) | × | × |
| `None` | × | × |
| `sandboxfoo` | × | × |
| `notsandbox` | × | × |
| `sandbox;preferpve2` | ○ | ○ |

**部分一致は起きない**(`(^|;)…(;|$)` のアンカーが効いている)。**空文字列と None も適格にならない** — 過去に「decoy 検証が None / 空文字列を見逃した」事例があるため明示的に検査した。

### V3 の詳細

`pvesh get /cluster/resources` は、タグの無い VM について **`tags` キー自体を返さない**(`'tags' in r` が False)。したがって `_rvr_vm.tags is defined` が False となり、assert は `fail_msg` で正常に停止する。仮に `tags` が None として存在した場合も、`None is search(...)` は例外ではなく False を返すことを確認した。**どちらの経路でもクラッシュしない。**

### V5 の結果

```
state_dir              : /var/lib/homelab-recovery/probe-sandbox
config                 : /etc/homelab-recovery/recovery-probe-sandbox.json
unit                   : recovery-probe-sandbox
ExecStart              : /usr/bin/python3 /usr/local/sbin/recovery-probe.py   ← 本番と同一
```

`state_dir` が分離されるため、`fire_ladder` の `state_dir/ladder.lock` が本番と衝突しない(**AC14 の前提が成立**)。

## 2.5 quory への配備(実施済み)

`ansible-playbook playbooks/recovery_probe_sandbox_setup.yml -l quory` を実行した(quory は非保護ホストのため事前確認不要の区分。事後報告)。

**配備前の確認**: daemon 本体が ansy の作業ツリーと quory の配備物で一致していること(`sha256sum` 前16桁 `113475e1f933ec11` で一致、`drill` 残存も両方0件)。一致していなければ、この配備が本番の共有バイナリだけを更新して本番 daemon を旧プロセスのまま取り残す。

新規 playbook: `playbooks/recovery_probe_sandbox_setup.yml`(`hosts: control_nodes`、`tester-gate: check-mode-native`)。

| 検証 | 結果 |
|---|---|
| `--check` 実行 | `changed=0` / `failed=0`(destructive ブロックは9タスク skip) |
| 本適用 | `changed=3` / `failed=0` |
| unit | `recovery-probe-sandbox.service` = **disabled**、`recovery-probe.service` = **enabled / active**(従来どおり) |
| **本番 daemon の起動時刻** | 配備前と同一(**再起動されていない**) |
| **本番 config** | mtime・`state_dir` / `mute_dir` / `monitoring_pause_flag` とも**未変更** |
| 状態ディレクトリ | `/var/lib/homelab-recovery/probe` と `probe-sandbox` が**別に存在**(**AC14 の前提が実機で成立**) |
| 検証側 config | `state_dir` / `mute_dir` / `monitoring_pause_flag` が本番と別、`targets` は `sandbox` の1件のみ |

### 2.5.1 配備後の設計修正(2026-08-02、週次パッチとの相互作用の確認により)

初回配備の直後に2点を直し、再配備した(`changed=1`。本番 config・本番 daemon の起動時刻とも無変更を再確認済み)。

**修正1: mute ディレクトリと監視一時停止フラグを本番と共有へ戻した。** 分離した当初の理由(「共有すると本番の mute が検証側を黙らせる」)は誤りだった — `mute_remaining()` が読むのは `<mute_dir>/<target>.json` で target ごとに別ファイルであり、本番の3件と `sandbox` は名前が重ならないため干渉しない。分離すると `homelab-mute sandbox <分>` が効かず、暴走時の安全弁を失う。**分離が要るのは `state_dir` だけである**(`ladder.lock` が target 別でないため)。

**修正2: 検証インスタンスを常設しないことにした。** 理由は2つ。

1. **週次パッチと衝突する。** `proxmox_evacuate_node` は `prefer*` タグを持たない VM を移行対象にせず、Phase 6 で「残って稼働している VM」として停止する。`sandbox` はこれに該当するためパッチ中に停止され、probe が常駐していると5分後にラダーが発火して**パッチ中のノードで VM を起動しにいく**。週次パッチが mute するのは `authy` / `monnie` / `sophos-fw` の3件のみで(`playbooks/proxmox_patch_weekly_full.yml` L514 / L522 / L530)、`sandbox` は含まれない。
2. **常駐させても回帰検出は増えない。** 動かすコードは本番 probe と同一で、本番インスタンスが実 target に対して常時走っている。

運用は「窓を開けて閉じる」形とし、playbook ヘッダに明記した。

```
systemctl enable --now recovery-probe-sandbox     # 窓を開ける
systemctl disable --now recovery-probe-sandbox    # 窓を閉じる
```

**既定では enable / start しない。** 標的が到達不能なまま起動すると、閾値到達のたびにラダーが発火して flapping エスカレーションに至るため。

### 検証インスタンスの標的設定(N2 の決定)

置き場所は `host_vars` ではなく**専用 playbook の `vars`** とした。`host_vars/quory.yml` へ置くと本番インスタンスの実行時にも解決され、値の取り違えが起きうる。playbook を分けることで、どちらのインスタンスを配備しているかが起動コマンドから一意に決まる。

`failover: false` としたのは、`state: ignored` の間 relocate が VM を動かさず、ラダーから呼ぶと Phase 4 の待機300秒を消費して必ずエスカレーションするためである。failover 段は `SANDBOX: Recovery ha failover (check)` テンプレート(`--check`)で個別に検証する。

## 2.6 標的 VM の現況(着手後に判明した前提の欠落)

| 項目 | 結果 | 手段 |
|---|---|---|
| OS | Ubuntu 26.04 LTS、kernel 7.0.0-28-generic | pve2 で `qm agent 2000 get-osinfo` |
| QEMU guest agent | 応答あり(`qm agent 2000 ping` rc=0)。`agent: enabled=1` | 同上 / `qm config 2000` |
| cloud-init | `cicustom` + `ipconfig0`(静的IP)設定済み | `qm config 2000` |
| **`sandbox.internal` の名前解決** | **NXDOMAIN(未登録)** | ansy で `getent hosts sandbox.internal` |

**VM 自体は健全で、欠けているのは内部 DNS のレコードだけである。** リポジトリ規約により probe の標的は DNS 名で書くため(IP を書かない)、`sandbox.internal` が解決できるようになるまで検証インスタンスは起動できない。

なお `recovery_vm_reboot_guest_agent_targets` は `[authy, monnie]` のままであり、**`sandbox` は guest agent ではなく ACPI 経路を通る** — これは意図どおりで、sophos-fw と同じ経路を検証することになる。

## 2.7 実機観測: probe → `stopped` → start(AC3 相当)

2026-08-02 21:44〜21:51 に実施。検証インスタンスを一時的に起動し、Yoshinobu が PVE GUI で `sandbox` を停止、経過を観測したのち停止した。

```
21:46:15 → 21:50:27   PROBE sandbox: FAIL ['icmp','tcp:22'] (1/5) … (5/5)
21:50:34   LADDER sandbox: pvesh status = stopped
21:50:34   NOTIFY queued: [warning] VM 停止検知 → start 実行 - sandbox
21:50:37   LADDER sandbox: vm start ok=True
21:51:10   NOTIFY queued: [ok] 復旧確認 (start) - sandbox
21:51:13 / 21:51:16   NOTIFY sent ×2
```

| 観測項目 | 結果 |
|---|---|
| 閾値(60秒×5)の到達 | 期待どおり |
| `pick_pve_host` → `pvesh` 確証 | `stopped` を取得 |
| **決定論分岐(reboot ではなく start)** | `pvesh_vm_start` が実行され `ok=True`。VM は `running` へ復帰 |
| `wait_for_recovery` | 33秒で回復を検知 |
| 通知 | warning → ok の2本。見出しに `sandbox` が入り本番障害と区別できる。**Slack 着信を Yoshinobu が確認** |
| **`ladder.lock`** | `probe-sandbox/` 配下に生成され、`finally` で解放された。**本番側 `state_dir` には現れなかった**(AC14 相当が実データで成立) |
| `firings-sandbox.json` | 1件記録(flapping カウンタ) |
| **本番インスタンスへの影響** | 無し。`ExecMainStartTimestamp` は `10:20:25` のまま、本番 `state_dir` は `notify-queue` のみ |

**削除した probe drill が訓練するはずだった配線が、実データで通ったことになる。** drill と異なり障害は偽物ではない。

観測後、`systemctl disable --now recovery-probe-sandbox` で窓を閉じた(`disabled` / `inactive` を確認)。

### 副作用: 検証由来の通知が incident spool に載る

通知2本が quory の `reports/incidents/_spool/` に捕捉された(`slack_title: [recovery-probe] 復旧確認 (start) - sandbox` 等、`skip_notifications: False` / `check_mode: False`)。`homelab-incident-capture.timer` は active であり、このまま起票される。

**削除せず残す判断(2026-08-02 Yoshinobu)。** 「検証を回したときにどう記録へ残るか」自体が成果物として意味を持ち、削除すると捕捉されたものを消す形になるため。ただし検証を繰り返すたびに溜まるので、**検証由来の通知を捕捉対象から外す条件**を requirement の P2 へ申し送る。

## 2.8 AC18 の充足(2.7 の実行データによる)

**別途の実行を要しない。** 2.7 の実行中、`sandbox` は 21:45 頃の停止から probe が起動をかける 21:50:37 まで**約5分間 `stopped` のまま**であり、**HA は一度も起動を試みていない**。これは `state: ignored` のサービスが CRM のマネージャ状態から除外される(`PVE/HA/Manager.pm` L1047 / L1059-1064)ことの実データによる裏づけであり、AC18(「`ignored` のVMをHAが自動起動しないこと」)を満たす。

副次的に、R5 が旧 R5 から引き取った懸念 —「HA管理下のVMは停止すると自動起動され、ラダーの『VMを起こす』検証と競合する」— が `state: ignored` によって実際に解消されていることも確認できた。

## 2.9 発見: ACPI shutdown の失敗時に強制電源断へ落ちない

`roles/recovery_vm_reboot/tasks/main.yml` の Phase 2 は、2つの shutdown 手段で**エラー時の扱いが非対称**である。

| タスク | `ignore_errors` |
|---|---|
| L84 `Send guest agent shutdown command (authy / monnie)` | **あり** |
| L95 `Send ACPI shutdown command (sophos-fw or agent shutdown failed)` | **なし** |

ACPI shutdown が**タイムアウトではなくエラー**を返した場合、play はそこで失敗し、L136 の `Force power off if soft shutdown timed out (fallback)` に到達しない。playbook ヘッダは「ACPI shutdown が timeout の場合は `pvesh .../status/stop`(強制)にフォールバック」と述べており、エラー時の経路は想定されていない。

**`sophos-fw` は guest agent を持たず ACPI 一択の対象である。** VM が locked(バックアップ・マイグレーション中)や paused の状態では `pvesh create .../status/shutdown` が非ゼロを返しうるため、その場合は強制停止まで進まない。

**これを欠陥と断定しない。** locked 中に強制停止を撃つほうが有害な場面もあり、失敗して人間へ上げるのが正しい設計でもありうる。**判断が要る非対称**として `docs/ai/status.md` の Next へ載せ、本案件では扱わない(Phase 1 の scope 外)。

なお AC2 を案B(起動順を空にして UEFI シェルで待たせる)で行う場合、`pvesh status/shutdown` は QEMU に受理されて成功し、ゲストが応答しないことで**タイムアウト側**に落ちる。したがって案Bは本節の非対称に影響されず、意図どおり強制電源断の経路を通る。

## 2.10 Phase 1 クローズにあたっての判断(2026-08-02 Yoshinobu合意)

| # | 事項 | 判断 |
|---|---|---|
| ① | AC1 / AC2 | **実施する。** 手順は 2.11。Yoshinobu が Semaphore と `qm set` で起動する |
| ② | **AC17**(failover `--check`) | **持ち越し。** pve1 が停止中で Phase 2 の「オンラインな非現在ノード」assert が通らない。**実装の不備ではなく前提の不在**。pve1 稼働時に `SANDBOX: Recovery ha failover (check)` を1回起動して確認する。`docs/ai/status.md` の Watch へ検証手段つきで載せる |
| ② | **flapping**(24時間に3回のラダー発火) | **descope。** VM停止3回を要し、得られるのは「カウンタが3で止まる」ことの確認に限られる。費用対効果が見合わない |
| ③ | **独立 Tester による受入判定** | **通さずにクローズする。** 本セッションは subagent を起動しない前提で運用したため。`docs/ai/roles/coordinator.md`「受入条件(AC)の実機検証をCoordinator自身で済ませない」に対する**明示的な例外**である。判定の追試可能性は、quory の journal と本記録 2.7 の一次記録によって担保する |

## 2.10.1 見落とし: `target` 名の allowlist が playbook 側にもう1枚あった

**Semaphore task #533 が失敗して判明した(2026-08-02)。** 原因は pve1 の停止ではない — `proxmox_exec_node` は pve1 の到達性 probe を `...ignoring` で正しく処理し pve2 を選んでいた。実際の失敗はこれである。

```
pve2 | Validate target variable (prevent path traversal)
  assertion: target in ['authy', 'monnie', 'sophos-fw']
  msg: target が不正です: 'sandbox'.
```

**ラダーのゲートはタグ1枚ではなく、少なくとも3層あった。**

| 層 | 場所 | 内容 | 当初の把握 |
|---|---|---|---|
| 1 | playbook の `pre_tasks` | `target` 名の allowlist(path traversal 防止) | **見落としていた** |
| 2 | role の Phase 1 | Proxmox タグの照合 | 把握・修正済み |
| 3 | role defaults | target ごとの対象サービス表(`recovery_service_restart` のみ) | **見落としていた** |

`2026-08-02_001_requirement.md` 4.4 に書いた「ホスト名のハードコードはどこにもない」は**誤りである**。role の Phase 1 だけを読んで断定し、playbook の `pre_tasks` を確認していなかった。同 4.4 の「タグは2枚目のゲート」という結論自体は変わらないが、1枚目の実体は `recovery_probe_targets` ではなく**この playbook 側 allowlist** である。

### 修正

| ファイル | 変更 |
|---|---|
| `playbooks/recovery_vm_reboot.yml` L69 | `['authy','monnie','sophos-fw']` → `+ 'sandbox'` |
| `playbooks/recovery_ha_failover.yml` L68 | `['authy','sophos-fw']` → `+ 'sandbox'` |
| `playbooks/recovery_service_restart.yml` L65 | `['authy','monnie']` → `+ 'sandbox'` |
| `roles/recovery_service_restart/defaults/main.yml` | `recovery_service_restart_units` へ `sandbox: [ssh.service]` を追加(層3) |

いずれも**リテラルの追加**であり、変数化していない(層2と同じ理由)。`fail_msg` の列挙も実態へ合わせた。

### 再発防止としてやったこと

ラダー経路の playbook・role・defaults を対象に、`authy` / `monnie` / `sophos-fw` を名指ししている箇所を**網羅的に洗った**。残る名指しは次の3件で、いずれも意図どおりのため変更しない。

- `roles/recovery_vm_reboot/defaults/main.yml` の `recovery_vm_reboot_guest_agent_targets: [authy, monnie]` — `sandbox` を含めないことで **ACPI 経路(= sophos-fw と同じ)を通す**
- `roles/recovery_service_restart/tasks/main.yml` の `target != 'sophos-fw'` — sandbox に影響しない
- `roles/recovery_vm_reboot/tasks/main.yml` L84 / L95 のタスク名(文字列のみ)

## 2.11 AC1 / AC2 の実行と結果(実施済み 2026-08-03)

順番が重要である。起動順を戻す前に AC2 を撃つ。

```
1. pve2:      sudo qm set 2000 --boot order=          # UEFI シェルで待たせる
2. Semaphore: SANDBOX: Recovery vm reboot             # AC2 = 強制電源断フォールバック
3. pve2:      sudo qm set 2000 --boot order=scsi0     # 起動順を戻す
4. Semaphore: SANDBOX: Recovery vm reboot             # AC1 = 正常系
```

**期待する観測**

| 手順 | 期待 |
|---|---|
| 2 | ACPI shutdown は成功するがゲストが応答せず、`recovery_vm_reboot_soft_shutdown_timeout_s`(60秒)でタイムアウト → `Force power off ...` が実行され `_rvr_used_force_stop: true` → start → running。**終了コード0**、レポートに強制停止した旨が残る |
| 4 | ACPI shutdown でゲストが正常停止(60秒以内)→ 強制停止タスクは skip → start → running。**終了コード0** |

いずれも `reports/recovery_investigations/sandbox/` にJSONレポートが生成され、Slack へ `[recovery_vm_reboot] ... - sandbox` の通知が出る。

### 実施結果

手順は途中で変わった。当初案の `qm set --boot order=`(空値)は Proxmox が受け付けず(`invalid format - missing key`)、ゲスト内で ACPI を無視させる方式へ切り替えた。さらに**QEMU guest agent が有効なため `pvesh status/shutdown` がエージェント経由で停止し、`HandlePowerKey=ignore` を迂回する**ことが判明したため、ゲスト内で `qemu-guest-agent` を mask した(2.11.1)。

| AC | Semaphore task | 結果 | `used_force_stop` | 経路 |
|---|---|---|---|---|
| **AC2**(強制電源断フォールバック) | 538 | **success** / `failed=0` | **`true`** | ACPI 送信 → 12回リトライ全滅(60秒タイムアウト)→ `Force power off` 実行 → start → running |
| **AC1**(正常系) | 541 | **success** / `failed=0` | **`false`** | ACPI 送信 → 2回リトライで停止 → 強制停止は skip → start → running |

レポートは両方とも `reports/recovery_investigations/sandbox/` へ保存され、所有者は `yoshi`(2.11.2 の修正が実データで効いていることの裏づけ)。

**AC2 は本番では再現できない。** sophos-fw を60秒ハングさせる必要があるためである。

### 2.11.1 ゲスト側の設定変更(sandbox 固有・恒久)

| 設定 | 状態 | 理由 |
|---|---|---|
| `qemu-guest-agent` | **mask したまま維持** | `recovery_vm_reboot_guest_agent_targets` に `sandbox` は含まれず、role は常に ACPI 経路を使う。エージェントが生きていると role の前提とゲストの実態がずれる。**mask して sophos-fw と同条件を保つ** |
| `/etc/systemd/logind.conf.d/99-sandbox-ac2.conf` | **AC2 実施後に削除** | AC2 専用。`HandlePowerKey` は既定(poweroff)へ復帰済み |

### 2.11.2 発見(2): 本番のレポート保存が権限で失敗する

**Semaphore task 535 の失敗から判明した。** ラダー本体は完走したが、最後の `Ensure report directory exists` が `[Errno 13] Permission denied` で落ちた。

```
reports/recovery_investigations/  … 所有 uid 1002(quory に存在しない uid)/ mode 755
report タスク                      … become: false → quory では yoshi として実行
→ yoshi は親ディレクトリにも配下にも書けない
```

**`reports/` 配下14ディレクトリのうち、これだけが uid 1002 所有**だった(他13件は `yoshi`)。ansy 側は `yoshi:yoshi` で正常。中身は 2026-06-27 の開発時の2件のみで、以後1件も書かれていない。

**影響は sandbox に限らない。** 本番のラダーが実際に発火すると、リブートが成功してもレポート保存で play が失敗し、`recovery-probe.py` は `r.returncode != 0` を見て**リブート失敗と判定する**。`fire_ladder` はそこから hacritical 対象(sophos-fw / authy)の HA failover へ進むため、**成功した復旧が失敗と誤読され、不要な failover を起こす**。

顕在化していなかったのは自律チェーンが本番で一度も実発火していないためである(`docs/ai/status.md` の既存 Watch)。

**対処**: quory で `chown -R yoshi:homelab-ansible reports/recovery_investigations` を実施(quory は非保護ホストのため Coordinator 判断・事後報告)。task 538 / 541 のレポートが `yoshi` 所有で保存されたことで修正を確認した。

**この修正は git の外にある。** quory を作り直せば再発する。Phase 2 のドリフト検出の対象へ含める(requirement R8 ⑥)。**Incident として起票するかは Yoshinobu の判断に委ねる** — 実害は出ていないが「窓は開いていた」類である。

## 3. 未実施・未解決

| # | 内容 |
|---|---|
| N1 | **AC3 / AC14 / AC18 は実機データで充足**(2.7 / 2.8)。**未実行は AC1 / AC2 のみ**で、手順は 2.11 に確定済み。**AC17 は持ち越し(pve1停止中)、flapping は descope**(2.10) |
| N8 | ~~独立 Tester の要否~~ **判断済み(2.10 ③)。通さずにクローズする。** 例外である事実と理由を 2.10 に記録した |
| N9 | **ACPI shutdown のエラー時に強制電源断へ落ちない非対称**(2.9)。本案件の scope 外。`docs/ai/status.md` の Next へ載せた |
| N2 | ~~対象リストの置き場所~~ **決定・実施済み**(2.5)。専用 playbook の `vars` |
| N5 | ~~`sandbox.internal` が未登録~~ **解消(2026-08-02)。** DNS と ansy / quory の `/etc/hosts` の双方へ登録済み。quory から `getent` / ICMP / tcp:22 を3回連続で確認 |
| N7 | **内部DNSを提供しているのは `sophos-fw` 自身**であり、再起動・フェイルオーバー中は名前解決ができない(2026-08-02 Yoshinobu指摘)。ラダーの第一の標的が DNS サーバでもあるため、DNS だけに頼ると「sophos-fw を直すために pve1 を名前で引く」で詰む。**quory の `/etc/hosts` がこの循環を切っており、便宜の重複ではなく設計上の耐障害機構である**。`docs/ai/context/system/autonomous-recovery.md` に追記し、requirement R8 ⑤ でドリフト検出の対象に加えた |
| N6 | ~~検証インスタンスに `homelab-mute` が効かない~~ **解消(2.5.1 修正1)。** mute ディレクトリを本番と共有したため `homelab-mute sandbox <分>` が効く |
| N3 | `SANDBOX: Recovery ha failover (check)` に `--check` を焼き込めない(Semaphore の制約)。ただし HA が `state: ignored` の間は CRM がサービスをマネージャ状態から除外するため、`relocate` を発行しても VM は動かない(`PVE/HA/Manager.pm` L1047 / L1059-1064 をソースで確認。実行しての確認は AC17 実施時) |
| N4 | pve1 の `ann` 権限と authorized_keys(U3)は依然未確認。週末に確認する |

## 4. commit しない

`git add` まで実施。commit は Yoshinobu が行う。
