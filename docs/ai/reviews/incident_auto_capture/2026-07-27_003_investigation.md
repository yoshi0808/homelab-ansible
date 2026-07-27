# 調査と分解: 障害の証拠バンドル生成(Step 1)

日付: 2026-07-27(JST)
状態: **調査完了。実装未着手。**
Tier: 4
起点HEAD: `8310126`(作業ツリーclean)
前提: `2026-07-27_001_design_agreement.md` のD1〜D7、`2026-07-27_002_requirement.md` のR1〜R9・AC1〜AC7。本書はこれらを覆さない。覆す必要があると判断した箇所は §7 に差戻し提案として分離した。

関連ADR: `docs/ai/adr/003-incident-capture-collector-runtime.md`、`docs/ai/adr/004-notify-capture-insertion.md`

---

## 1. 現物確認で判明した事実(既存記述の訂正を含む)

すべて HEAD `8310126` の現物で確認した。設計合意・requirementの記述と食い違うものは訂正として明示する。

### 1-1. `notify.yml` の include は 33箇所ではなく **38箇所 / 25ファイル**

```
grep -rn "include_tasks.*common_slack/tasks/notify.yml" --include=*.yml . | grep -v ^./docs
→ 38 hits, 25 files
```

内訳の偏りが大きい。`playbooks/ubuntu_nightly.yml` が単独で8箇所、`roles/ubuntu_vm_full_upgrade/` が7箇所、`roles/time_sync_check/` が3箇所。D6/requirementの「33箇所」は古い値であり、**T1のレビュー範囲は38箇所**である。

### 1-2. `notify.yml` は「全ジョブ結果の絞り」ではなく「**送ろうとした通知の**絞り」である — AC3に直接影響

38箇所のうち **13箇所は include 自体に `when:` を持つ**。さらにそのうち**3箇所は `skip_notifications` そのものでゲートしている**。

| ファイル:行 | include の when |
|---|---|
| `roles/radius_healthcheck/tasks/main.yml:21` | `criticals/warnings > 0` **かつ** `not skip_notifications` |
| `roles/monitoring_healthcheck/tasks/main.yml:21` | 同上 |
| `roles/proxmox_healthcheck/tasks/main.yml:227` | 同上 |
| `roles/proxmox_snapshot_check/tasks/main.yml:134` | `status in ['WARNING','CRITICAL']` |
| `roles/time_sync_check/tasks/main.yml:32,60,285` | `not ansible_check_mode`(285は加えて異常時のみ) |
| `playbooks/ubuntu_nightly.yml:105,125,352,372` | `ansible_check_mode` / `not ansible_check_mode` |
| `playbooks/knowledge_review.yml:32` | `not ansible_check_mode` |
| `roles/codex_update_check/tasks/main.yml:223` | 更新ホストが存在するときのみ |

帰結は2つある。

1. **AC3の `skip_notifications` 側は、上記3 roleでは原理的に成立しない。** `skip_notifications: true` を渡すと `notify.yml` が **include されない**ため、その冒頭に何を置いても発火しない。「抑止ゲートより前に置く」だけでは足りず、抑止判断はゲートの**手前(caller側)**にも存在する。`tester_mode` 側にはcaller側ゲートが無いため、AC3のうち `tester_mode` の半分だけが成立する。
2. `proxmox_snapshot_check` のように「異常時のみ include」する呼び出し元では、**正常時(`ok`)のレコードが原理的に取れない。** D7が期待する「要約OK / 生ログ異常」の突き合わせは、この role については成立しない(§3 OQ6 も参照)。

### 1-3. `tester_mode` は「廃止済み」だが `notify.yml` では現役

`ansible_test_safety_policy.md` TS-003 は `tester_mode` 変数を2026-07-06〜07に廃止済みと書くが、現物では:

- `inventories/homelab/group_vars/all.yml:5` に `tester_mode: false` が**実在**する。
- `roles/common_slack/tasks/notify.yml:18,21` の抑止ゲートは**現役**である。
- 一方 `playbooks/recovery_ha_failover.yml` / `recovery_vm_reboot.yml` / `recovery_service_restart.yml` / `proxmox_restore_vm_placement.yml` / `recovery_io_setup.yml` は冒頭で `assert: not tester_mode` を持ち、**`-e tester_mode=true` を渡すと即failする**。

Testerへの帰結: AC3の `tester_mode` 検証には、この assert を持たない playbook を選ぶ必要がある。候補は §9 に挙げる。

### 1-4. Semaphore結果の取得口は既に存在する — `homelab-semaphore-query`

`roles/recovery_exec/files/homelab-semaphore-query`(quory-local、`/usr/local/bin/`配備)が既に読み取り専用でSQLiteを引いている。requirementの「SQLite直読み vs API」という選択肢は、実際には**既存の名前付き操作を再利用するか否か**という問いに縮む。

現行4クエリと、その限界:

| クエリ名 | SQL | 本案件での限界 |
|---|---|---|
| `recent-failed <n>` | `task` × `project__template` LEFT JOIN、`status IN ('error','stopped')`、`substr(t.start,1,19)` | **`substr(...,1,19)` がタイムゾーン情報を切り落とす**(§3 OQ1)。`end` 列を返さない。`status` 語彙が2値に固定 |
| `task-errors <id>` | `task__ansible_error` の先頭500字 | 500字打ち切り |
| `task-hosts <id>` | `task__ansible_host` 全列 | — |
| `task-output <id>` | `task__output(time, output)` 全件 | 生ログ全文が取れる(D7の「生ログ」要件を満たす) |

重要な性質: SQL文はこの1ファイルに閉じており、引数は `is_uint` で整数のみ。設計合意「実装前に潰す細部 #2(SELECTを1箇所へ閉じ込める)」は**既に実装済み**である。新規に直読みを書くと、この性質を壊して2箇所目のSQLを作ることになる。

権限も配線済み: `roles/recovery_exec/tasks/main.yml:238-254` が `recovery-exec` に `/var/lib/semaphore` のtraverseと `semaphore.db` のread ACLを与えている(sudoではなくPOSIX ACL。理由は同ファイルのコメント)。

### 1-5. 現況スナップショットに使える名前付き操作の実在範囲は **authy / monnie / pve1 / pve2 の4ホストのみ**

- `homelab-investigate-{authy,monnie}`(`homelab-investigate.sh.j2`) — `failed|disk|memory|load|network|ports|journal-system|dmesg|status` + service別journal。
- `homelab-investigate-{pve1,pve2}`(`homelab-investigate-pve.sh.j2`) — `cluster-status|ha-status|cluster-quorum|storage-status|zpool-health|...`。
- **quory自身と ansy には `homelab-investigate-*` が存在しない。** `recovery_exec_targets` / `recovery_exec_pve_targets`(`roles/recovery_exec/defaults/main.yml:48-92`)に無いため。

帰結: OQ3の「失敗したホストのみか」という問いは、**そもそも失敗ホストに対応する名前付き操作が無い場合がある**という形で崩れる(例: `cert_renew_quory.yml` はquoryで失敗する)。§3 OQ3で扱う。

もう1点、実行identityの制約がある。これらのwrapperは `/home/recovery-exec/.ssh/id_recovery_investigate*`(0600 recovery-exec所有)を読むため、**`recovery-exec` として実行しない限り動かない**。ADR-003の中心的な制約はこれである。

### 1-6. `.gitignore` の除外は3拡張子のみ — 拡張子の罠が実在する

```
reports/**/*.json
reports/**/*.log
reports/**/*.md
```

- `.jsonl` は `*.json` に**一致しない**。
- `.gz`(`raw.log.gz`)も**一致しない**。生ログの圧縮保存はAC6を壊す。
- `.txt` も一致しない(requirementの指摘どおり)。
- 一方 `*.tmp` はグローバルに除外されているため、**アトミック書き込みの一時ファイルは `.tmp` を使えば安全**。

`reports_base_dir` は `inventories/homelab/group_vars/all.yml:1` で `/home/yoshi/homelab-ansible/reports` に固定されている(絶対パス)。

### 1-7. AC2の再現手段は、現行コードには**もう存在しない**

requirement AC2は「`hosts: proxmox` かつ `any_errors_fatal: true` のplaybook」を再現手段に指定するが、現物では:

- `any_errors_fatal: true` が残るのは `playbooks/proxmox_patch_weekly_full.yml:118` の**1箇所のみ**。これは実パッチ適用playbookであり、Testerが再現目的で走らせてよい対象ではない。
- `playbooks/proxmox_patch_dryrun.yml` の `any_errors_fatal` は **ADR-002 decision a-1 で撤去済み**(同ファイル `:10` のコメントが根拠)。requirementが実例として挙げた当のplaybookは、もう当該挙動を示さない。

代替は §9 の T-AC2 に示す。結論だけ先に書くと、**「新しい失敗を起こす」のではなく「既に semaphore.db に存在する過去の失敗ジョブ(例: #461)を収集器に読ませる」**のが本筋であり、これによりAC2はpve1停止運用の時間窓に依存しなくなる。

### 1-8. systemd unit の前例が2種類ある

| 前例 | 形 | 参考になる点 |
|---|---|---|
| `roles/recovery_probe/templates/recovery-probe.service.j2` | `Type=simple` / `User=` / `Environment=<CONFIG>` / Pythonスクリプト直起動 | **非Ansibleの常駐・定期処理をquoryで動かす形の正準**。設定はJSONファイル(`recovery-probe.json.j2`)で外出し |
| `roles/knowledge_review/templates/knowledge-review.service.j2` | `Type=oneshot` / `ExecStart=/usr/bin/flock -n /run/lock/....lock <cmd>` | **flockの前例**(D5が指す実装)。`TimeoutStartSec` を明示的に伸ばしている |

`roles/systemd_timers/` は `ansible-playbook` を回す汎用timerで、`systemd_timers_run_user: yoshi` 固定。実行identityがrecovery-execにならないため本案件には合わない(ADR-003)。

---

## 2. 実装方式の結論(要点)

詳細と却下理由はADRに書いた。ここでは対応関係のみ示す。

| requirementが挙げた論点 | 結論 | 根拠の所在 |
|---|---|---|
| 収集器をquory上で何として動かすか | **Pythonスクリプト + systemd timer、`User=recovery-exec`、`flock -n -E 75`** | ADR-003 §Decision(a)(b) |
| Semaphoreジョブ結果の取得方式 | **既存 `homelab-semaphore-query` を拡張して再利用**(新規直読みもAPIも採らない) | ADR-003 §Decision(c) |
| スキーマ結合リスクの受け止め | SQLは既に1ファイルに閉じている。**取得失敗を握りつぶさず `collection_errors[]` へ記録し、収集器の終了コードを非ゼロにする** | ADR-003 §Decision(c)、§6 RSK-10 |
| T1をinclude構造を壊さずどう挿入するか | **`notify.yml` 冒頭に `include_tasks` 1行**(絶対パス形式)、実体は `roles/common_slack/tasks/capture.yml`。失敗隔離は `block`/`rescue` | ADR-004 §Decision(a)(b) |
| 現況スナップショットの起動方法 | **固定の `(host, 操作名)` 表を持ち、`/usr/local/bin/homelab-investigate-<host> <名前>` を名前で呼ぶだけ。** 引数の組み立て・連結を一切行わない | ADR-003 §Decision(d) |
| バンドルのディレクトリ構成とファイル形式 | §4。全ファイル `.json` / `.log` / `.md` のみ | 本書 §4 |
| 相関IDの所有者 | **T1はIDを決めない。収集器がIDを確定する** | ADR-004 §Decision(c) |

---

## 3. オープンクエスチョンの解決状況

### OQ1. Semaphoreのタイムスタンプの実体 — **未解決。ただし requirement が示した実測方法は成立しない**

リポジトリ内から言えることは3点ある。

1. `homelab-semaphore-query recent-failed` は `substr(t.start,1,19)` を返す。**19文字で切ると、保存形式を決める情報(末尾の `Z` / `+09:00` / 無印)がちょうど落ちる。** つまり**既存の名前付き操作では OQ1 は原理的に測れない**。requirementの「SQLiteの当該カラムの生値と突き合わせて実測する」は方針としては正しいが、それを実行する手段が現行カタログに無い。
2. `substr(...,1,19)` という書き方自体が、`t.start` が **TEXT型で先頭19文字が `YYYY-MM-DDTHH:MM:SS` 相当**であることを前提にしている。Go実装がSQLiteへ `time.Time` を書くときの標準形はRFC3339(オフセット付き)であり、この前提と整合する。
3. Yoshinobuが `recovery.io` 経由で見た `2026-07-26 20:45:01 UTC` は、**区切りが空白で末尾に ` UTC` という語がある**。`substr(t.start,1,19)` の出力(区切りは `T`、ゾーン表記なし)とは形が違う。したがって**その文字列は `homelab-semaphore-query` の出力ではなく、Semaphore UI/API の表示かCodexの散文**である可能性が高い。設定ファイル(`Asia/Tokyo`)との矛盾は、DB保存形式の証拠ではなく表示層の話である可能性がある。

**決めるために観測すべきこと**(§9 T-OQ1):

- `task` テーブルの `start` / `end` 列の**生値**を1件、切り詰めずに見る。
- **まず ansy のSemaphoreで測る。** ansyは開発側であり、同一プロダクト・同一構成である。ここで形式が確定すれば本番DBに触れずに済む。両者のSemaphoreバージョンが一致することを先に確認する(不一致なら quory 側でも1回だけ読む)。
- 併せて `task` テーブルの列一覧(`PRAGMA table_info(task)`)と、`status` 列に実在する値の集合(`SELECT DISTINCT status FROM task`)を取る。`recent-failed` が `('error','stopped')` の2値しか見ていないことの妥当性はこれで決まる(OQ6に効く)。

**設計側の逃げ道**: 実測結果がどちらでも壊れないよう、収集器は生値をそのまま `semaphore_start_raw` として保持し、解釈済みの値は `occurred_at`(RFC3339、オフセット必須)として**別フィールド**に持つ。解釈に失敗したら `occurred_at` を埋めず `collection_errors[]` に理由を書く。裸の `UTC` / `Z` をローカル時刻に付けない(設計合意「実装前に潰す細部 #1」)。

### OQ2. 収集器の起動間隔 — **解ける(提案: 5分。ただし「差分があるときだけSSHする」ことが本質)**

間隔そのものより、**間隔が現況スナップショットのSSH負荷に直結しないようにする**ほうが効く。

- 収集器は毎周期、(a) spool の新規レコード と (b) `recent-failed` の新規ジョブID を見る。**どちらも新規が無ければSSHを一切行わずに終了する**(exit 0)。
- 新規がある回だけ、そのバンドルに対して1度だけスナップショットを取る。
- したがって周期を短くしても、平常時の対象ホストへの追加負荷はゼロである。増えるのは quory 内のSQLite読みとファイルstatだけ。

イベント駆動(systemd `.path` unit で spool を監視)を検討したが**採らない**。T1が書く時点ではSemaphore側のジョブ行がまだ `running` であり、終端状態を読めないためである。時刻の遅れは、`occurred_at`(事象時刻)と `snapshot_captured_at`(観測時刻)を**別フィールドで持ち、差を明示する**ことで扱う(D3 §2「報告時点の観測」という但し書きと整合する)。

**5分**を提案値とするが、これは変数(`incident_capture_interval`)で外出しし、Yoshinobuが動かせるようにする。

### OQ3. 現況スナップショットの対象ホスト — **解ける(提案: 失敗ホスト由来ではなく、固定表 + 取得不能の明示)**

§1-5のとおり、名前付き操作が存在するのは authy / monnie / pve1 / pve2 の4ホストだけである。「失敗したホストのみ」という決め方は、失敗ホストがquoryやansyだったときに空振りする。

提案する決め方:

1. **常に取る(基礎セット)**: `pve1: cluster-quorum, ha-status` と `pve2: cluster-quorum, ha-status`。クラスタの生死は、失敗ホストが何であれ判断材料になる(D7の #461 が示したとおり、隣のノードの状態が要約と食い違う情報源になる)。pve1停止中は接続が10秒でタイムアウトし `collection_errors[]` に落ちるだけで、これも情報である。
2. **失敗ホストに対応する操作があれば追加する**: 失敗ホスト名が `recovery_exec_targets` / `recovery_exec_pve_targets` に一致する場合のみ、そのホストの `status` / `failed` / `disk` / `journal-system` を追加する。
3. **無ければ明示的に記録する**: 「host=quory に対応する名前付き操作が存在しない」を `collection_errors[]` へ書く。これがR5の意図であり、D3 §5「確かめたかったが叩ける操作が無かった」の各行になり、カタログ拡張の根拠になる(D3のカタログ成長ループそのもの)。

対象表は収集器の設定JSONに置き、**コードから組み立てない**(D1)。

### OQ4. 保持期間・世代数 — **解ける(提案: 90日 かつ 300バンドル、先に当たったほうで削除)**

- 生ログは `task__output` 全文であり、バンドルの容量の大半を占める。**1バンドルあたりの生ログを上限(提案: 2 MiB)で切り、切った事実を末尾のマーカー行とバンドルの `truncated: true` に記録する。**
- **圧縮しない。** `.gz` は `.gitignore` に一致せずAC6を壊す(§1-6)。
- spool レコードは、バンドルへ取り込まれた時点で削除する。**どのバンドルにも取り込まれないまま所定時間(提案: 24時間)を超えた spool レコードは、`orphan` バンドルとして必ずバンドル化してから削除する。**単純に消すと「Semaphore外で起きた通知」が静かに失われ、R5の趣旨(静かな取りこぼしを作らない)に反する。

数値はいずれも変数で外出しし、Yoshinobuの判断で動かせるようにする。

### OQ5. 作業ツリー汚れ vs 月次振り返り — **requirementの結論を支持(Step 2へ持ち越し)**

Step 1の生成物はすべて `reports/incidents/` 配下であり `.gitignore` 済みなので、`git status --short` に現れない(AC6)。**ただし成立条件は「全ファイルが `.json` / `.log` / `.md` である」ことだけ**であり、§1-6の拡張子の罠を1つでも踏むと即座にこの前提が崩れて8/26の月次無人実行を止める。AC6は形式的な確認ではなく、**この案件で最も安価に壊れる受入条件**として扱う(§6 RSK-13)。

### OQ6. 対象ジョブ範囲 — **解ける(結論: 観測面で定義するというrequirementの方針を支持。ただし2点を追加する)**

**追加1: T1は `slack_status` で絞らず、到達したすべての通知を記録する。**

理由はD7そのものにある。D7の実例(#461)は「要約 `Result=OK` / ジョブ全体 rc=4」という食い違いであり、**`ok` の要約レコードが残っていなければ食い違いを検出できない**。`warning`/`critical`/`error` だけを記録する設計は、D7が最も価値を置いた情報を構造的に捨てる。副次的に、T1から `when:` 条件が消えるためAC4のリスクも下がる(条件式の評価自体が失敗経路になりうる。ADR-004 §Decision(b))。

なお§1-2のとおり `proxmox_snapshot_check` など一部の呼び出し元は異常時しか include しないため、この方針でも `ok` レコードが取れない role は残る。それは実装の欠陥ではなく caller 側の構造であり、`collection_errors` ではなくバンドルの `notify_records: []`(空)という事実として現れる。

**追加2: `status='stopped'` は「Yoshinobuが手で止めた」を含む。**

`recent-failed` の `status IN ('error','stopped')` の `stopped` には人為的な中断が混ざる。DBだけでは誰が止めたかは分からない。**捨てずに取り込み、`semaphore_status` をそのまま持たせる**。仕分け(これはIncidentか否か)は叙述側(Step 2)と人が行う — D3の「捕捉と昇格を分ける」と同じ形である。

**範囲外の確認**: ansy のSemaphoreは開発側であり本案件の対象外。収集器はquoryにのみ配備する。

---

## 4. バンドルの仕様(提案)

```
reports/incidents/
  _spool/<epoch>-<rand8>.json          # T1が書く。収集器が消費して消す
  <id>/bundle.json                     # 索引。スキーマ版・ID・出所・時刻・状態・フラグ・取得失敗
  <id>/notify.json                     # このIDに紐づくT1レコードの配列(ホストごとに複数ありうる)
  <id>/raw.log                         # semaphore task__output の連結(上限で切る)
  <id>/snapshot.json                   # 名前付き操作ごとの rc / 実行時刻 / 出力ファイル名
  <id>/snapshot-<host>-<op>.log        # 各名前付き操作の生stdout/stderr
```

- 拡張子は `.json` / `.log` のみ(`.md` は使わない)。一時ファイルは `*.tmp` → `rename` でアトミックに置く。
- `id`: Semaphoreジョブ由来なら `sem-<jobid>`、Semaphore外なら `timer-<unit>-<epoch>`。**`sem-` の接頭辞は付けるが番号は発明しない**(D6/R6)。
- `bundle.json` の必須フィールド(型と意味はImplementerが確定):
  - `schema_version`(整数。Step 2の入力契約)
  - `id`, `source`(`semaphore` / `notify-only` / `orphan`)
  - `occurred_at`(RFC3339、オフセット必須)、`semaphore_start_raw`(生値そのまま)、`collected_at`, `snapshot_captured_at`
  - `semaphore_job_id`, `semaphore_template`, `semaphore_playbook`, `semaphore_status`
  - `controller`(このバンドルを作ったホスト名)
  - `flags`: `tester_mode`, `skip_notifications`, `check_mode`(T1レコード由来)
  - `truncated`(生ログを切ったか)
  - **`collection_errors[]`**: `{what, why}` の配列。空でないことが正常でもありうる(pve1停止中など)
- **`collection_errors` を持たないバンドルを作れる実装にしない。** 「Semaphoreから取れなかった」が表現できない設計だと、AC5(静かに空のバンドルを作らない)が満たせない。

---

## 5. T1のレコード仕様(提案)

`_spool/<epoch>-<rand8>.json` の1ファイル1レコード。T1が知りうる情報だけを書く。

```
record_version, written_at(オフセット付き), controller(実行ホスト),
playbook(playbook_dir由来のbasename), play_host(inventory_hostname),
slack_channel, slack_status, slack_title, slack_message,
tester_mode, skip_notifications, check_mode
```

- **ファイル名に秒精度だけを使わない。** `notify.yml` は `delegate_to: localhost` だが **play のホストごとに実行される**(`run_once` は付いていない)。複数ホストのplayでは同一秒に複数レコードが出る。`<epoch>-<rand8>` のようにランダム成分を必ず入れる(§6 RSK-07)。
- `slack_message` は複数行。JSONへ入れるため改行はエスケープされる。**`no_log` は付けない**(内容が目的)。ただしwebhook URL・tokenには一切触れない(T1は `vars/slack.yml` を読む前に走るため、そもそも到達しない)。

---

## 6. リスクレジスタ

AC4(観測が被観測の挙動を変えない)に関わるものを先頭に置く。Likelihood / Impact は 高・中・低。

| ID | 分類 | Risk | L | I | Mitigation |
|---|---|---|---|---|---|
| RSK-01 | Operational | T1が参照する4変数のいずれかを定義していない呼び出し元があり、テンプレート展開エラーで**38経路のplayが落ちる** | 中 | 高 | すべての変数参照に `\| default('')` を付ける。Reviewerが38箇所すべてで4変数の定義を照合する(§8 W3-a) |
| RSK-02 | Operational | 書き込み失敗(権限・ディスクフル・パス不在)がplayを失敗させる | 中 | 高 | `block`/`rescue` で隔離。`rescue` は `debug` のみ。`changed_when: false` も付け、changed数も動かさない(ADR-004) |
| RSK-03 | Operational | `include_tasks` するファイルが見つからず**ハードエラー**になる(相対パス解決の前提違い) | 低 | 高 | 既存慣行どおり `{{ playbook_dir }}/../roles/common_slack/tasks/capture.yml` の絶対形で書く。相対 include にしない |
| RSK-04 | Operational | `--check` 実行時にT1が書き込み、Tester実行がバンドルを汚す / 逆に `--check` でも捕捉したいのに書かない | 中 | 低 | `check_mode: false` を**付けない**(=`--check` では書かない)ことを明示的な仕様とする。`check_mode` フラグ自体はレコードに持ち、Step 2が読めるようにする |
| RSK-05 | Operational | `run_once` を付けると**全ホスト失敗時に発火しない**(2026-07-26の既知の罠) | 低 | 中 | T1に `run_once` を付けない。ホストごとに書き、収集器側で束ねる |
| RSK-06 | Security | `recovery-exec` に `reports/` 全体の書き込みを与えると、**`proxmox_patch_apply_node` がgate入力に使う `reports/proxmox-dryrun/*_unified_dryrun.json` を上書きできる**identityになる(`roles/proxmox_patch_apply_node/tasks/main.yml:293` が fileglob で読む) | 中 | 高 | ACLは **`reports/incidents/` にのみ**付与する。`reports/` 直下には決して付けない。Reviewerの必須確認項目とする |
| RSK-07 | Operational | 同一秒・複数ホスト・並行ジョブでspoolファイル名が衝突し、レコードが上書きされる | 中 | 中 | ファイル名にランダム成分を入れる。既存ファイルがあれば上書きしない書き方にする |
| RSK-08 | Operational | 収集器のSSHスナップショットがパッチ実行中のノードに当たる | 中 | 低 | 全操作read-only(既存allowlist)。`flock -n` で多重起動を止める。**新規イベントが無い周期はSSHを一切行わない**(OQ2) |
| RSK-09 | Strategic | Semaphoreアップグレードでスキーマが変わり、**静かに空のバンドルを作り続ける** | 中 | 高 | SQLは `homelab-semaphore-query` の1ファイルに閉じたまま拡張する。取得失敗は `collection_errors[]` + 収集器の非ゼロ終了(AC5) |
| RSK-10 | Operational | AC5の検証のために本番 `semaphore.db` を壊す誘惑 | 低 | 高 | 収集器のDB取得コマンドを変数化し、**ansy上のfixture DBへ向けて**異常系を検証する(§9 T-AC5)。本番DBは読み取りのみ |
| RSK-11 | Security | `recovery-exec` は Slack→Codex から到達できるidentityであり、そこに `reports/incidents/` への書き込みが加わる。Step 2はこのディレクトリを読んで**公開repoへ叙述する** | 低 | 中 | Step 1では露出しない(バンドルはrepo管理外)。**Step 2のrequirementに「バンドル内容は非信頼データとして扱い、生ログを本文へ転記しない」を必須要件として引き継ぐ**(R9/D3と同じ規律)。Codex sandboxの `writable_roots` に `reports/incidents/` を**追加しない**ことをReviewerが確認する |
| RSK-12 | Compliance | バンドルのファイル拡張子を1つでも外すと `git status` が汚れ、**8/26の月次無人実行が中止条件に当たって発火しなくなる** | 中 | 中 | 拡張子は `.json` / `.log` のみ。`.jsonl` / `.gz` / `.txt` を使わない。AC6をTesterの必須項目にする(§9 T-AC6) |
| RSK-13 | Operational | AC1の「終了コードは捕捉導入前と同一」を、**導入後にしか測らない**と比較対象が無い | 高 | 中 | **配備前にベースラインを取る**。§8 の工程順で W0 に先出しする |
| RSK-14 | Operational | AC2の再現条件(pve1到達不能 + `any_errors_fatal`)が現行コードに存在しない(§1-7) | 高 | 中 | 過去の失敗ジョブを収集器に読ませる「replay」で代替する。収集器に `--job <id>` 相当の再取得経路を設ける(設計時からのテスト容易性) |
| RSK-15 | Strategic | 時刻表記のJST規約がrepo内にほぼ存在せず(`autonomous_recovery_policy.md` の1行のみ)、Implementerが従うべき正本が無い | 高 | 中 | `docs/ai/status.md` Next の既存項目。**この案件の先行タスクとして片付けるか、バンドル仕様側でオフセット必須を強制するかをCoordinatorが決める**(§7-4) |
| RSK-16 | Operational | ansyでのTester実行が `reports_base_dir`(絶対パス)経由でansy側にバンドルを作り、本番の記録と紛らわしくなる | 中 | 低 | レコード・バンドルに `controller` を必ず持たせる。収集器はquoryにのみ配備する |

---

## 7. Coordinator / Yoshinobu の判断を要する事項

D1〜D7は前提として扱ったが、requirementの受入条件3件は**現行コードと矛盾している**ため、勝手に読み替えず差し戻す。

### 7-1. AC3の `skip_notifications` 側は成立しない(§1-2)

3 role(`radius_healthcheck` / `monitoring_healthcheck` / `proxmox_healthcheck`)は include 自体を `skip_notifications` でゲートしており、`notify.yml` 冒頭に何を置いても発火しない。選択肢:

- **(A) ACを狭める** — AC3を `tester_mode: true` のケースに限定し、`skip_notifications` については「caller側ゲートにより捕捉されない role が3件ある」を既知の欠落として記録する。**推奨。** T1の目的(通知抑止と証拠保全の分離)は `tester_mode` 経路で実証でき、`skip_notifications` は主にTesterの `--check` 実行で使われるため、そこで捕捉が落ちること自体の実害は小さい。
- (B) 3 role の caller 側 `when:` から `not skip_notifications` を外す — 通知抑止の意味論を変える変更であり、38経路のうち3経路の本番挙動を触る。Step 1のscopeを超える。
- (C) T1をcaller側へ移す — 38箇所への挿入になり、D6の「単一の絞り」設計を捨てることになる。

### 7-2. AC2の再現手段が存在しない(§1-7)

`proxmox_patch_dryrun` の `any_errors_fatal` はADR-002で撤去済み、残る1件は実パッチ適用playbook。選択肢:

- **(A) ACの `Then` を保ったまま `When` を差し替える** — 「新しい失敗を起こす」のではなく「semaphore.db に既にある過去の失敗ジョブ(pve1 UNREACHABLE / rc=4 として既知の #461 など)を収集器に読ませ、バンドルが生成されることを確認する」。**推奨。** pve1停止運用の時間窓への依存が消え、requirement §8のタイムライン制約自体が解消する。
- (B) pve1停止中に、全対象ホストがpve1のみになるsafe-readonly templateをSemaphore UIから手動実行する — 実行可能だが、該当するtemplateが存在するかがUI側の事実であり、repoからは確認できない。requirement §3の非ゴール(Semaphore UI設定の変更)に触れない範囲で可能かをYoshinobuに確認する必要がある。

### 7-3. AC1の観測時点(IDの所有者、ADR-004 §Decision(c))

T1はSemaphoreジョブ番号を知らない可能性が高い(§9 T-OQ3で観測する)。IDは収集器が確定する設計にしたため、**AC1の `Then`「`reports/incidents/<id>/` が生成され」は、playbook終了直後ではなく次の収集周期の後に成立する**。AC1の観測時点を「次の収集器実行の完了後」へ改める必要がある。playbookの終了コードとfailed数の比較は、従来どおりplaybook終了直後に取る。

### 7-4. JST規約の明文化を、この案件の先行タスクにするか(RSK-15)

`docs/ai/status.md` Next に既に起票されている。バンドルのスキーマがUTC/JSTを跨ぐため、Implementerが従う正本が無いまま実装すると混入する。選択肢: (A) この案件の W0 として先に片付ける / (B) バンドル側で「RFC3339・オフセット必須・裸の `Z`/`UTC` 禁止」を仕様として強制し、規約の明文化は別案件のまま残す。**(B)で実装は進められる**が、決めるのはCoordinatorである。

### 7-5. カタログの拡張が1件必要になる(D1/D2との関係)

OQ1を解き、かつ「タイムゾーンを明示したフィールドで保持する」(設計合意 細部#1)を満たすには、`homelab-semaphore-query` に**タイムゾーンを切り落とさないクエリを1つ足す**必要がある(§1-4)。これはD1が定める拡張経路(repo編集 → commit → quory pull → 再デプロイ、人手が2回)そのものであり、**実行時に引数で影響範囲が変わる類の拡張ではない**。D1/D2に反しないと判断したが、カタログへの追加であることは明示して記録する。

---

## 8. Implementer / Reviewer / Tester への分解案

Coordinatorが起動する順に並べる。**W0 の一部(ベースライン取得、T-OQ1)は実装前でなければ意味を失う。**

### W0. 先行観測(Tester)— 実装着手前

出力: `docs/ai/reviews/incident_auto_capture/2026-07-27_004_observation.md`

| # | 観測 | 決まること |
|---|---|---|
| T-OQ1 | Semaphore `task.start` / `task.end` の**生値**、`PRAGMA table_info(task)`、`SELECT DISTINCT status FROM task` | OQ1、OQ6の `status` 語彙、`end` 列の有無 |
| T-OQ2 | quory上でSemaphoreが `ansible-playbook` を実行するユーザ名 | T1が書き込めるパスの範囲、spool配置の妥当性 |
| T-OQ3 | Semaphoreジョブ実行時、playbookのプロセス環境にジョブIDらしき変数が渡るか | ADR-004 §Decision(c) の裏付け(渡るならバンドルの相関精度が上がる。渡らなくても設計は変えない) |
| T-OQ4 | quory上の `reports/` と `reports/*/` の所有者・モード | ACL付与の設計(RSK-06) |
| T-BASE | **AC1のベースライン**: 対象playbookの現在の終了コードとPLAY RECAP(ok/changed/failed/ignored) | AC1の比較対象。**配備後には取得不能** |

安全分類はすべて `safe-readonly` 相当の読み取り。ただしT-OQ1は本番 `semaphore.db` に触れうるため、**まずansyで実施し、ansy/quoryのSemaphoreバージョンが一致することを確認したうえで、必要な場合のみquoryで1回だけ読む**。コマンドと安全分類は §9 に書く。

### W1. T1の実装(Implementer A)

- `roles/common_slack/tasks/capture.yml` を新規作成。
- `roles/common_slack/tasks/notify.yml` の**冒頭1行**に `include_tasks` を追加。**それ以外の行を触らない。**
- レコードスキーマを `docs/ai/context/` か role 内コメントに固定(Step 2の契約になる)。
- 出力: `2026-07-27_005_implement_t1.md`。
- 必読: `skills/ansible-implementation-style/SKILL.md`、ADR-004、本書 §5・§6。

### W2. T1のレビュー(Reviewer 1、W1とは別subagent)

W3-a〜d は §9 のレビュー観点表に対応する。**W1をW2で確定させてからW3へ進む。** 38経路に波及する差分を、収集器の差分と一緒にレビューさせない。

### W3. 収集器の実装(Implementer B)

- `homelab-semaphore-query` に **タイムゾーンを保持するクエリを1つ追加**(§7-5)。既存4クエリの挙動は変えない。
- 収集器スクリプト(Python)+ 設定JSON + systemd service/timer を持つ新規role(仮 `incident_capture`)。
- `recovery-exec` への ACL は **`reports/incidents/` にのみ**付与(RSK-06)。
- 配備playbook。`# tester-gate:` マーカー必須(`scripts/check-tester-gate.sh` がcommitをブロックする)。
- テスト容易性を設計時から持たせる: DB取得コマンドと `reports_base_dir` 相当を変数化(RSK-10)、過去ジョブIDを指定して再取得できる経路(RSK-14)。
- 出力: `2026-07-27_006_implement_collector.md`。
- 必読: ADR-003、本書 §3・§4・§6、`docs/ai/policies/autonomous_recovery_policy.md`、`docs/ai/context/system/semaphore.md`。

### W4. 収集器のレビュー(Reviewer 2、W3とは別subagent)

### W5. 検証(Tester)

出力: `2026-07-27_007_test_plan.md` / `2026-07-27_008_test_result.md`。詳細は §9。

### 受入条件の担当

| AC | 一次確認者 | 段階 | 備考 |
|---|---|---|---|
| AC1 | Tester | W5(ベースラインはW0) | ID確定時点の差戻し(§7-3)が承認されている前提 |
| AC2 | Tester | W5 | §7-2の差戻しが承認されている前提。replay方式 |
| AC3 | Tester | W5 | §7-1の差戻し後の範囲で |
| AC4 | Reviewer 1(静的) + Tester(実測) | W2 / W5 | **最重要。両方で見る** |
| AC5 | Tester | W5 | ansy上のfixture DBで |
| AC6 | Reviewer 2(拡張子の静的照合) + Tester(実測) | W4 / W5 | |
| AC7 | Tester | W5 | ansy上で二重起動 |

Reviewer 1 と Reviewer 2 は**別subagent**で起動する(`docs/ai/roles/reviewer.md` の独立性)。Implementer A / B は同一でもよいが、W2の指摘を反映した後にW3へ進む順序は守る。

---

## 9. Tester検証項目(誰が・何を・どのコマンドで・安全分類)

`docs/ai/policies/ansible_test_safety_policy.md` の分類と `docs/ai/roles/tester.md` の禁止事項に照らして割り当てた。**すべてTesterが実施する。Tech Lead・Coordinatorは実行しない。**

### W0(実装前)

| ID | 対象ホスト | 実施内容 | 安全分類 | 承認 |
|---|---|---|---|---|
| T-OQ1a | ansy | `sqlite3 -readonly <ansy semaphore.db> "PRAGMA table_info(task);"` と `"SELECT id,status,start,end FROM task ORDER BY id DESC LIMIT 3;"`、`"SELECT DISTINCT status FROM task;"`。**`substr` を掛けず生値を見る** | 読み取りのみ。ansyは開発ホスト | 提示不要 |
| T-OQ1b | ansy / quory | 両者のSemaphoreバージョン比較(`semaphore version` 相当、または `dpkg -l`/`systemctl show`) | 読み取りのみ | 提示不要 |
| T-OQ1c | quory | T-OQ1bで**バージョンが一致しない場合のみ**、T-OQ1aと同じ3クエリを `sqlite3 -readonly` で1回だけ実行 | 読み取りのみだが**本番制御平面のDB**。`-readonly` 必須 | **Coordinatorへ提示** |
| T-OQ2 | quory | Semaphoreサービスの実行ユーザと、ジョブが起動する `ansible-playbook` プロセスの所有者(`systemctl show semaphore -p User`、直近ジョブ中の `ps` など) | 読み取りのみ | 提示不要 |
| T-OQ3 | quory | Semaphoreの既存 safe-readonly template を1本、**通常どおり**手動実行し、そのジョブのplaybookプロセス環境にジョブIDらしき変数が渡るか確認する。**新規templateを作らない**(requirement §3 非ゴール) | 対象playbookのマーカーに従う。`safe-readonly` を選ぶこと | **Coordinatorへ提示**(本番Semaphoreからの起動であるため) |
| T-OQ4 | quory | `ls -ld` / `getfacl` で `reports/` と `reports/*/` の所有者・モード・既存ACL | 読み取りのみ | 提示不要 |
| T-BASE | ansy | AC1で使う対象playbookを**現行コードのまま**実行し、終了コードとPLAY RECAP(ok/changed/failed/**ignored**)を記録する。マーカーが `check-mode-native`/`dry-run-aware` なら `--check` 付き | 対象playbookのマーカーに従う | マーカー次第 |

### W5(実装後)

| ID | AC | 対象 | 実施内容 | 安全分類 |
|---|---|---|---|---|
| T-AC1 | AC1 | ansy → quory | T-BASEと同一のplaybookを同一条件で再実行し、**終了コード・failed数・ignored数・changed数がベースラインと一致**することを確認。次の収集周期後に `reports/incidents/<id>/` とメタデータを確認 | ベースラインと同一分類 |
| T-AC2 | AC2 | quory | **replay方式**(§7-2 A案): 既に `semaphore.db` にある過去の失敗ジョブ(pve1 UNREACHABLEでrc=4だった回など)のIDを収集器へ与え、バンドルにジョブID・`UNREACHABLE` を含む生ログ・`semaphore_status` が入ることを確認。新しい失敗を起こさない | 読み取り + `reports/incidents/` への書き込みのみ |
| T-AC3 | AC3 | ansy | **`tester_mode is deprecated` assert を持たない**playbookで `-e tester_mode=true` を実行し、(1) Slack通知が飛ばない (2) spool レコードが生成され `tester_mode: true` が記録されている、を確認。候補: `playbooks/recovery_probe_notify.yml`(`role-guarded`、include無条件)。`recovery_ha_failover` / `recovery_vm_reboot` / `recovery_service_restart` / `proxmox_restore_vm_placement` / `recovery_io_setup` は**assertでfailするため使わない** | `role-guarded` |
| T-AC4 | AC4 | ansy | 捕捉の書き込み先を**変数で存在しないパス/書込不可パスへ向けて**同じplaybookを実行し、終了コード・failed数がT-BASEと一致することを確認。**実ホストのディレクトリ権限を書き換えない** | ベースラインと同一分類 |
| T-AC5 | AC5 | ansy | 列名を変えた**fixture SQLite DB**を `/tmp` 配下に作り、収集器のDB取得先をそこへ向けて実行。(1) 空バンドルを黙って作らない (2) `collection_errors[]` に記録される (3) 終了コードが定義済みの非ゼロ、を確認 | ansy + `/tmp` に閉じる |
| T-AC6 | AC6 | ansy → quory | バンドル1件以上を生成した状態で `git status --short` が**空**であることを確認。加えて `git check-ignore -v` で各生成ファイルが除外規則のどれに当たるかを1件ずつ表示させる(`.gitignore` の3規則以外に当たっていないこと) | 読み取りのみ |
| T-AC7 | AC7 | ansy | 収集器を1つ走らせた状態でもう1つ起動し、後発が即終了して終了コードが「多重起動」を意味する定義済み値であることを確認 | ansy に閉じる |
| T-REG | — | ansy | T1導入後、`notify.yml` を通る代表的な role を数種(healthcheck系 / cert系 / patch dry-run系)実行し、Slack通知の内容・宛先チャネルが従来どおりであること | 各playbookのマーカーに従う |

**Testerへの申し送り**:

- `roles/recovery_ha_failover` 等5 playbook は `-e tester_mode=true` で assert fail する(§1-3)。AC3の対象に選ばないこと。
- pve1/pve2・sophos-fw・UniFi機器への非冪等操作は本計画に含まれない。含まれる形になったら停止してCoordinatorへ返すこと。
- ansy上での実行でも `reports_base_dir` は `/home/yoshi/homelab-ansible/reports` の絶対パスであり、ansyのrepo作業ツリーへ書く。実行後に `git status` を必ず確認すること。

---

## 10. 参照

- `docs/ai/reviews/incident_auto_capture/2026-07-27_001_design_agreement.md`(D1〜D7)
- `docs/ai/reviews/incident_auto_capture/2026-07-27_002_requirement.md`(R1〜R9、AC1〜AC7)
- `docs/ai/adr/003-incident-capture-collector-runtime.md`
- `docs/ai/adr/004-notify-capture-insertion.md`
- `docs/ai/adr/002-proxmox-patch-dryrun-single-node.md`(§1-7 の `any_errors_fatal` 撤去の根拠)
- `roles/common_slack/tasks/notify.yml`、`roles/recovery_exec/files/homelab-semaphore-query`、`roles/recovery_exec/templates/homelab-investigate*.sh.j2`、`roles/recovery_exec/defaults/main.yml`
- `roles/recovery_probe/templates/recovery-probe.service.j2`、`roles/knowledge_review/templates/knowledge-review.service.j2`(unit前例)
- `.gitignore`、`inventories/homelab/group_vars/all.yml`
- `docs/ai/policies/ansible_test_safety_policy.md`、`docs/ai/roles/tester.md`、`docs/ai/context/system/semaphore.md`
