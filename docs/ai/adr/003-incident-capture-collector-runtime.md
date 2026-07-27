# ADR-003: 証拠バンドル収集器の実行形態・実行identity・Semaphore取得経路

**Status:** Proposed

対象案件: `docs/ai/reviews/incident_auto_capture/2026-07-27_002_requirement.md`(Step 1)
前提決定: 同 `..._001_design_agreement.md` のD1(名前付き操作のみ)、D4(収集はquory・LLMなし)、D5(排他はflock)、D6(捕捉の起点は2つ)、D7(要約と生ログの両方)
調査の一次記録: 同 `..._003_investigation.md`

## Context

Step 1の収集器は、quory上で周期的に (1) `notify.yml` が残したレコード、(2) Semaphoreのジョブ結果(生ログ含む)、(3) 既存の名前付き操作による現況スナップショット を1つのバンドルへまとめる。決めるべきことは互いに独立に決められない。

- **(a) 何として動かすか**(systemd / Semaphore / Ansible)は、
- **(b) どのidentityで動くか**を決め、それが
- **(c) Semaphoreをどう読むか** と **(d) スナップショットをどう起動するか** の可否を直接決める。

現物調査(HEAD `8310126`)で確定した制約:

1. **Semaphore結果の読み取り口は既に存在する。** `roles/recovery_exec/files/homelab-semaphore-query`(quory-local)が `sqlite3 -readonly` で固定SQLを引く。SQL文はこの1ファイルに閉じており、引数は整数のみ(`is_uint`)。設計合意「実装前に潰す細部 #2(SELECTを1箇所へ閉じ込める)」は既に満たされている。
2. **その読み取りは `recovery-exec` のACLに依存する。** `roles/recovery_exec/tasks/main.yml:238-254` が `/var/lib/semaphore` のtraverseと `semaphore.db` のreadを `recovery-exec` にPOSIX ACLで与えている。sudoではない(理由は同ファイルのコメント: Codex sandboxの `no_new_privileges` がsudoを無条件に阻む)。
3. **スナップショット用wrapperも `recovery-exec` 固有である。** `homelab-investigate-{authy,monnie}` / `homelab-investigate-{pve1,pve2}` は `/home/recovery-exec/.ssh/id_recovery_investigate*`(0600、`recovery-exec` 所有)を読む。他のユーザでは動かない。
4. **名前付き操作が存在するのは authy / monnie / pve1 / pve2 の4ホストのみ。** quory自身とansyには `homelab-investigate-*` が無い(`roles/recovery_exec/defaults/main.yml:48-92`)。
5. **`reports/` は他系統のgate入力を含む。** `roles/proxmox_patch_apply_node/tasks/main.yml:293` が `reports/proxmox-dryrun/*_unified_dryrun.json` を fileglob で読み、パッチ適用の可否判断に使う。
6. unit前例が2つある。`roles/recovery_probe/templates/recovery-probe.service.j2`(`User=` 指定のPythonスクリプト + JSON設定)と `roles/knowledge_review/templates/knowledge-review.service.j2`(`flock -n` + oneshot)。汎用の `roles/systemd_timers` は `systemd_timers_run_user: yoshi` 固定で `ansible-playbook` を回す形。

## Options Considered

### (a) 収集器を何として動かすか

| Option | Pros | Cons |
|---|---|---|
| a-1: Pythonスクリプト + systemd timer(`User=recovery-exec`) | `recovery-probe.py` の前例をそのまま踏襲。`User=` で実行identityを直接固定できる。Ansibleの外側で動くため、観測対象(Ansible実行)の失敗に巻き込まれない。SQLite読み・JSON組み立て・サブプロセス起動はPythonの素直な守備範囲 | roleとして配備するPython資産が1つ増える。Ansible playbookに比べImplementerの検証手段が変わる |
| a-2: `ansible-playbook` + systemd timer(`roles/systemd_timers` 流用) | 既存の配備パターンをそのまま使える。Implementerの慣れた形 | **実行ユーザが `yoshi` になり、`semaphore.db` も `recovery-exec` の鍵も読めない。**become/sudoで補うと新しい特権経路が要る。加えて「Ansibleの失敗を観測する仕組み自体がAnsible」という自己参照になり、Ansible側の障害で観測も落ちる |
| a-3: Semaphore schedule上のジョブ | UIから実行履歴が見える | **観測者が被観測系の内側に入る。** Semaphoreが落ちれば観測も止まる(D4がansyを退けたのと同じ論法)。加えてrequirement §3が「Semaphore UI設定・スケジュールの変更」を明示的に非ゴールとしており、**この案は要求段階で既に除外されている** |
| a-4: 既存unitへの `OnFailure=`(`recovery_push` 方式) | 失敗と同時に発火し遅延がない | systemdが起動したjobしか拾えない。Semaphore経由の失敗(D6の主経路)を拾えないため、単独では要件を満たさない |

### (b) 実行identity

| Option | Pros | Cons |
|---|---|---|
| b-1: `User=recovery-exec` + `reports/incidents/` **のみ**へのACL付与 | 読み取り側の新規特権が**ゼロ**(semaphore.dbも鍵も既に持っている)。新しく増える権限は1つのディレクトリへの書き込みだけ | Slack→Codexから到達しうるidentityが、Step 2で叙述対象になるディレクトリへ書けるようになる(下記Trade-off参照) |
| b-2: `User=yoshi` + `sudo -u recovery-exec` でwrapperを叩く | `reports/` の所有者のまま書けるためACL不要 | wrapper起動のためのsudoers追加が要る。`recovery_exec` roleがsudoからACLへ意図的に移行した経緯(同role内コメント)に逆行する。書き込み側の裁量が `reports/` 全体に広がり、制約5(パッチ適用gateの入力)に触れる |
| b-3: `User=root` | 権限問題が消える | 収集器の欠陥がそのままroot権限の欠陥になる。read-only収集にroot権限は不要 |

### (c) Semaphoreジョブ結果の取得方式

| Option | Pros | Cons |
|---|---|---|
| c-1: 既存 `homelab-semaphore-query` を**拡張して**再利用 | SQLが1ファイルに閉じたままになる(細部#2の性質を維持)。ACLも配線済み。D1の「引数面ゼロ・名前を選ぶだけ」という性質を引き継ぐ | タイムゾーンを保持するクエリの追加が要る(現行 `recent-failed` は `substr(t.start,1,19)` でオフセットを切り落とす)。追加は repo編集 → commit → pull → 再デプロイ の人手2回の経路になる |
| c-2: 収集器内で `sqlite3` を直接叩く | 追加のカタログ変更が不要。必要な列を自由に取れる | **SQLが2箇所になる。** 設計合意 細部#2 が名指しで警戒した形そのもの。スキーマ変更時に片方だけ直る |
| c-3: Semaphore REST API | スキーマではなくAPI契約に依存するため、DBスキーマ変更に強い | 長期保持のtoken(新しい秘密情報)が要る。**Semaphoreのプロセスが落ちていると読めない**が、そのときこそ観測したい。DBファイルは落ちていても最後の行を保持している |

### (d) 現況スナップショットの起動方法と対象

| Option | Pros | Cons |
|---|---|---|
| d-1: 失敗ホストから対象を導出し、対応する名前付き操作を呼ぶ | 直感的で無駄がない | 制約4により、失敗ホストがquory/ansyだと**対応する操作が1つも無い**。cert系のquory失敗で完全な空振りになる |
| d-2: 設定JSONに固定の `(host, 操作名)` 表を持ち、そこから選ぶ。基礎セット(pve1/pve2のクラスタ状態)は常に取り、失敗ホストに対応する操作があれば追加する。無ければ「操作が存在しない」ことを記録する | 失敗ホストが何であれクラスタの生死が残る(D7の #461 が示した「隣のホストが判断材料」)。操作が無い事実が `collection_errors[]` に残り、D3 §5「叩ける操作が無かった」→カタログ拡張の根拠 という設計上のループへ直接つながる | 常に2ホストへSSHするため、無条件だと負荷が乗る(下記Decisionで新規イベントのある周期に限定する) |
| d-3: 収集器が `ssh`/`journalctl` を直接組み立てて実行 | 対象と内容を自由に決められる | **D1違反。** 引数面がゼロという allowlist の安全性の根拠を捨てることになる |

## Decision

- **(a) a-1を採用。** Pythonスクリプト + systemd timer、`User=recovery-exec`。`recovery-probe.service.j2` の形(`User=` / `Environment=<CONFIG>` / JSON設定の外出し)を踏襲する。多重起動は `knowledge-review.service.j2` に倣い `flock -n` で止めるが、**AC7が「多重起動を意味する定義済みの終了コード」を要求するため `flock -n -E 75` として通常の失敗(exit 1)と区別できる値にする**(knowledge-reviewは素の `flock -n` で exit 1。ここは意図的に変える)。
- **(b) b-1を採用。** `User=recovery-exec`。新規に与える権限は **`reports/incidents/` に対するPOSIX ACL(default entry付き)だけ**とする。**`reports/` 直下へのACL付与を禁止する**(制約5)。
- **(c) c-1を採用。** `homelab-semaphore-query` に、`task.start` / `task.end` を**切り詰めずに**返すクエリを1つ追加する。既存4クエリの挙動は変更しない。スキーマ不一致・SQLiteロック・行なしは、いずれも握りつぶさずバンドルの `collection_errors[]` へ `{what, why}` として記録し、収集器の終了コードを定義済みの非ゼロにする(AC5)。
- **(d) d-2を採用。** 設定JSONの固定表から名前を選び、`/usr/local/bin/homelab-investigate-<host> <操作名>` を**名前で呼ぶだけ**にする。文字列連結でコマンドを作らない。対象は「基礎セット: pve1/pve2 の `cluster-quorum` / `ha-status`」+「失敗ホストに対応する操作があればそのホストの `status` / `failed` / `disk` / `journal-system`」。存在しない場合は `collection_errors[]` へ明記する。
- **(補) スナップショットは新規イベントのある周期だけ取る。** 収集器は毎周期まずspoolとSemaphoreの差分だけを見て、新規が無ければ**SSHを1本も張らずに** exit 0 する。これにより起動間隔(OQ2、提案5分)を短くしても対象ホストへの平常時負荷が増えない。

## Trade-off Analysis

4つの決定は「**観測者を被観測系の外に置き、かつ新しい特権と新しいSQLを増やさない**」という一貫した方針で選んでいる。a-3(Semaphore上で動かす)とa-2(Ansibleで動かす)を退けた理由は同一で、D4がansyを退けたのと同じ「障害と一緒に死ぬ観測者は役に立たない」である。c-3(API)を退けた理由も同じ系統で、Semaphoreプロセスの死が観測の死になる。

b-1の代償は明確に1つある。**`recovery-exec` はSlack経由のCodexが動くidentityであり、そこに `reports/incidents/` への書き込みが加わる。** そしてStep 2はこのディレクトリを読んで公開repoへ叙述する。したがってb-1は「バンドルの内容は信頼できる」という前提を置けなくする。ただしこれはb-2/b-3でも程度が変わるだけで消えない(b-2でも書き手は同じ収集器である)。**受け止め方は権限側ではなく叙述側に置く** — Step 2のrequirementに「バンドル内容を非信頼データとして扱い、生ログを本文へ転記せず参照だけ書く」を必須要件として引き継ぐ(D3・R9と同じ規律)。加えてReviewerが、Codex sandboxの `writable_roots`(`roles/recovery_exec/templates/codex-config.toml.j2`)と `recovery-io.service` の `ReadWritePaths` の**どちらにも `reports/incidents/` を追加していない**ことを確認する。この2層が揃わないとCodexは書けない、という既知の性質をそのまま防壁として使う。

c-1の代償はカタログを1件増やすことである。D2は「カタログ登録は1本ずつ人が判断する」と定めるが、これは**AIが叩ける操作を増やす**話であり、今回追加するのは収集器が使う読み取りクエリである。とはいえ `homelab-semaphore-query` はCodexからも叩ける同一ファイルなので、実質的にカタログが1件増えるのは事実であり、そのつもりでレビューする。増える能力は「タイムスタンプを切り詰めずに読む」だけで、引数面は既存同様に整数のみに保つ。

d-2はpve1が停止している平日日中に必ず10秒のSSHタイムアウトを1回踏む。これは無駄ではなく「pve1に到達できなかった」という事実の記録であり、`collection_errors[]` に載って第一報の §5(未確認事項)の材料になる。隠すべき失敗ではない(D5の同旨)。

## Consequences

- 新規role(仮 `incident_capture`)が `roles/` に増える。中身は Pythonスクリプト + 設定JSONテンプレート + systemd service/timer テンプレート + ACL付与task。配備playbookには `# tester-gate:` マーカーが必須(`scripts/check-tester-gate.sh` がcommitをブロックする)。
- `roles/recovery_exec/files/homelab-semaphore-query` にクエリが1つ増える。既存4クエリのSQLと挙動は変更しない。反映には `recovery_exec_setup.yml` の再実行が要る(`roles/recovery_exec/tasks/main.yml:335-342`)。
- `recovery-exec` のACLが1つ増える(`reports/incidents/`、default entry付き)。`recovery_exec` roleに追加するか新roleに置くかはImplementerの判断だが、**`reports/` 直下への付与は禁止**という制約はどちらでも守る。
- 収集器の終了コードは定義済みの集合とする(AC5/AC7)。最低限: 0=正常(新規なしを含む)、75=多重起動により実行せず(`flock -E`)、非ゼロのいずれかの値=Semaphore取得失敗。実値はImplementerが定義し、role内に文書化する。
- 起動間隔・保持世代・スナップショット対象表はすべて変数/設定JSONで外出しし、Yoshinobuが動かせるようにする。
- **Step 2への引き継ぎ事項**: バンドル内容は非信頼データである(上記Trade-off)。この一文をStep 2のrequirementへ必ず持ち込む。
- 収集器はquoryにのみ配備する。ansyへは配備しない(ansyのSemaphoreは開発側であり対象外)。ただしTesterがansy上で単体実行して異常系を検証できるよう、DB取得コマンドと出力先は変数化する。
