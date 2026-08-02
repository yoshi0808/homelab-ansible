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

## 3. 未実施・未解決

| # | 内容 |
|---|---|
| N1 | **実機ACは未実施**(AC1 / AC2 / AC3 / AC17 / AC18)。配備は完了したが(2.5)、AC1 / AC3 は `sandbox.internal` の名前解決(N5)が要る。AC2(強制電源断フォールバック)と AC17(failover `--check`)は Semaphore テンプレートから起動でき、DNS を待たずに実施可能。**AC14 の前提(state_dir 分離)は 2.5 で実機確認済み** |
| N2 | ~~対象リストの置き場所~~ **決定・実施済み**(2.5)。専用 playbook の `vars` |
| N5 | ~~`sandbox.internal` が未登録~~ **解消(2026-08-02)。** DNS と ansy / quory の `/etc/hosts` の双方へ登録済み。quory から `getent` / ICMP / tcp:22 を3回連続で確認 |
| N7 | **内部DNSを提供しているのは `sophos-fw` 自身**であり、再起動・フェイルオーバー中は名前解決ができない(2026-08-02 Yoshinobu指摘)。ラダーの第一の標的が DNS サーバでもあるため、DNS だけに頼ると「sophos-fw を直すために pve1 を名前で引く」で詰む。**quory の `/etc/hosts` がこの循環を切っており、便宜の重複ではなく設計上の耐障害機構である**。`docs/ai/context/system/autonomous-recovery.md` に追記し、requirement R8 ⑤ でドリフト検出の対象に加えた |
| N6 | ~~検証インスタンスに `homelab-mute` が効かない~~ **解消(2.5.1 修正1)。** mute ディレクトリを本番と共有したため `homelab-mute sandbox <分>` が効く |
| N3 | `SANDBOX: Recovery ha failover (check)` に `--check` を焼き込めない(Semaphore の制約)。ただし HA が `state: ignored` の間は CRM がサービスをマネージャ状態から除外するため、`relocate` を発行しても VM は動かない(`PVE/HA/Manager.pm` L1047 / L1059-1064 をソースで確認。実行しての確認は AC17 実施時) |
| N4 | pve1 の `ann` 権限と authorized_keys(U3)は依然未確認。週末に確認する |

## 4. commit しない

`git add` まで実施。commit は Yoshinobu が行う。
