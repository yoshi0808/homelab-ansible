# implement: Phase 4 Step 2 / Step 3 — `incident_sync` の退役 + 月次評価の入力移設

日付: 2026-08-03 (JST)
plan: `2026-08-03_015_plan_phase4.md` §4 Step 2 / Step 3
requirement: `2026-08-02_001_requirement.md` R14b、AC19 / AC20(PASS 済 — `..._013_`)
catalog: `2026-08-03_008_phase3_check_catalog.md`(Q1〜Q4 `bundle-list` / `bundle-show`)
担当: Implementer

Step 2 と Step 3 は plan 上「同一単位でよい」とされており、依頼どおり1件の記録にまとめる。

## 1. 対象パス

### 削除

| パス | 内容 |
|---|---|
| `roles/incident_sync/` 一式(10ファイル) | quory→ansy 証拠バンドルの周期ミラー同期 role |
| `playbooks/incident_sync.yml` | 同期本体(2 play) |
| `playbooks/incident_sync_timer.yml` | ansy側 timer 配置 |
| `playbooks/incident_sync_trigger_setup.yml` | quory→ansy 即時同期起動の受け口配置 |
| `roles/incident_investigate/tasks/sync_trigger.yml` | quory側の同期起動用SSH鍵生成 |

### 変更

| パス | 変更内容 |
|---|---|
| `roles/incident_investigate/tasks/main.yml` | `sync_trigger.yml` の import を削除(8行) |
| `roles/incident_investigate/defaults/main.yml` | sync_trigger系7変数を削除、`incident_investigate_dispatch_ssh_alias: quory-investigate` を新設 |
| `roles/incident_investigate/templates/incident-investigate.json.j2` | 対応するキーを削除・追加 |
| `roles/incident_investigate/files/incident-investigate.py` | `trigger_ansy_sync()` 関数を削除、`post_artifact_actions()` から呼び出しを除去、`build_notify_payload()` の `iv_report_path` をミラー相対パスから「dispatch経由の取得コマンド文字列」(`ssh quory-investigate investigation-show semaphore-<id> md`)へ変更 |
| `roles/incident_investigate/callback_plugins/incident_investigate_trigger.py` | コメント中の `incident_sync_outer_lock_path` という具体名参照を一般化(機能変更なし) |
| `playbooks/README.md` | カタログから3行削除、新設 `incident_sync_teardown.yml` の1行を追加 |
| `playbooks/incident_inspect_setup.yml` | ヘッダコメントの scope 除外列挙から `roles/incident_sync` を削除 |
| `roles/knowledge_review/defaults/main.yml` | `knowledge_review_incident_mirror_dir` / `knowledge_review_incident_heartbeat_max_age_s` を削除、dispatch用3変数(ssh bin / alias / timeout×2)を新設 |
| `roles/knowledge_review/tasks/incident_metrics.yml` | 全面書き換え(下記§2) |
| `roles/knowledge_review/tasks/incident_evaluation.yml` | `評価対象ミラー:` 行の文言変更、`incident_eval_summary` のSTALE分岐をFETCH_ERRORへ置換 |
| `roles/knowledge_review/templates/incident-review-prompt.md.j2` | 評価対象セクションの全面書き換え(下記§4) |
| `playbooks/knowledge_review.yml` | Slack通知本文の `STALE`→`FETCH_ERROR`、`ミラー心拍age` 行を `取得エラー`(条件付き)へ置換 |

### 新設

| パス | 内容 |
|---|---|
| `playbooks/incident_sync_teardown.yml` | 実ホスト上の後始末(下記§3)。**未実行。** 実行はCoordinator / Yoshinobu |

`roles/dev_investigate/` を含め、上記以外のファイルは変更していない。着手前の `git status` はクリーンだった(既存変更なし)。

## 2. Step 3 の設計 — バンドルID方式への転換

`mirror_bundle_total` / `bundles_new_since_last_eval` / `oldest_unreviewed_bundle` の3指標は、`ssh quory-investigate bundle-list` / `bundle-show <id> summary.json` を叩いて採る。旧実装(ローカルミラーの `find` + 全バンドル `summary.json` slurp + `generated_at` 比較)とは判定方式を変えた。

**バンドルID(`semaphore-<job_id>`)の数列で「新着」を判定する。** Semaphoreのjob idは単調増加であり(実測: 2026-08-03時点で55件)、「前回評価時点で見た最大id」より大きいidだけが新着と一致する。この方式により、往復は**最大2回**(`bundle-list` 1回 + 最古の新着1件だけ `bundle-show`)で済み、`bundle-grep`(横断走査、初期リリースから意図的に除外済み — R14c)を必要としない。全新着バンドルのsummary.jsonを毎回取得する設計は却下した(件数が増えるほど往復が線形に増え、IC-021が求める「滞留の検知」に対して過剰)。

前回の基準値(`last_bundle_id_seen`)は前回の `<date>-index.json` の内容から読む(新設フィールド、schema_version 1→2)。この読み取りは block/rescue で防御し、壊れていても機構全体を止めない(`finalize.yml` の旧heartbeat解析と同型)。

### V3(取得失敗と「取得できて0件」の区別)

`bundle-list` 自体が非0終了・unreachable等で失敗した場合、`mirror_bundle_total` / `bundles_new_since_last_eval` は **`null`**、`bundle_fetch_error` に理由文字列を入れる。成功して0件だった場合は `mirror_bundle_total: 0`、`bundle_fetch_error: ""`。両者はJSON上明確に区別できる(オフラインテストで確認、§5)。

`last_bundle_id_seen` は、取得できなかった(失敗/0件)場合は**前回値をそのまま引き継ぐ**。0で巻き戻すと、次回に本来「新着でない」ものまで新着扱いしてしまうため。

自己検証中に見つけて直した不具合: 最古の新着バンドルの `bundle-show` 呼び出し自体が失敗した場合(bundle-listは成功、この1件だけ失敗)、当初は理由を記録せず黙って `generated_at: null` に落ちていた。`ansible.builtin.fail` を明示的に挟み、rescueで `oldest_bundle_summary_parse_error` へ理由を残す形に直した(§5 fail_show ケース)。

### --check の扱い

`bundle-list` / `bundle-show` の呼び出しは `not ansible_check_mode` でゲートし、**`--check` では quory へ一切接続しない。** 本role内の他のread-onlyタスク(`git status`・`systemctl list-timers`等)はローカル操作のため `check_mode: false` で常時実行される慣習があるが、今回は実本番ホストへのネットワーク接続を伴うため、既存の `claude -p` 呼び出しと同じ「`--check`では実行しない」側に揃えた。`--check` 下では `bundle_fetch_error` に `"not attempted under --check (no real host contacted)"` が入り、`incident_eval_summary` は `FETCH_ERROR` になる(既知の無害な挙動として本文にコメント済み)。

### スキーマ変更(schema_version 1→2)

| 変更 | 内容 |
|---|---|
| 削除 | `mirror_heartbeat_age_seconds` / `mirror_stale`(ミラーごと削除、代替なし) |
| 追加 | `last_bundle_id_seen`(次回比較の基準) / `bundle_fetch_error` / `oldest_bundle_summary_parse_error` / `new_bundle_detection` |
| 名前不変 | `mirror_bundle_total` はデータの出所が変わった(ansy側コピー→quory原本へのライブ問い合わせ)が、requirement/planがこの名前で指標を指しているため改名していない。コード中コメントに明記 |

## 3. `incident_sync_teardown.yml`(後始末playbook・未実行)

対象: ansy側(`ansible-incident-sync.timer`/`.service` の停止・無効化・unit削除、`incident-sync-trigger` ユーザーとホーム削除、forced-commandスクリプト・sudoersファイル削除、`reports/incidents/_sync/` 削除)、quory側(`incident_investigate` roleが生成していたsync-trigger鍵ペアと専用known_hostsの削除)。

**触れていないもの**: `reports/incidents/quory/`(ミラーの凍結スナップショット。データであり機構ではないため残す)、quory上のバンドル原本(元々incident_syncの書込対象外)。

`--syntax-check` 通過を確認済み(§5)。`ansible-lint` は production profile で0件。**実行はしていない**(Implementerの権限外)。

## 4. Step 3 実装中に見つけた未解決の設計ギャップ(重要)

月次の障害評価は2つの別セッションから成る。

1. **決定論的メトリクス算出**(`incident_metrics.yml`、Ansible/timer側、shellあり)— 今回の対象。
2. **質的評価**(`incident-review-prompt.md.j2` を読む `claude -p`、Bashなし)— **今回の対象外だが、Step 2により実質的な機能低下が生じる。**

質的評価セッションは `reports/incidents/**` をローカルファイルシステムとして読むことしかできない(Bashが無いためdispatch/SSHを使えない)。この読み取り対象だった `reports/incidents/quory/` は `incident_sync` が運んでいたミラーであり、**Step 2でその同期が完全に止まるため、2026-08-03以降に生成される新規バンドルはこのディレクトリへ二度と増えない。**

結果として、質的評価セッションは新規バンドルについて「件数と最古バンドルの年齢」(Step 3が採るメトリクス)は知れるが、**個々のバンドルの内容(`summary.json`・ログ)を読んで質的に評価する能力を失う。** これはrequirementの「5指標のうち代替が要るのは2種類だけ」という記述には含まれておらず(その記述はあくまで決定論的メトリクスの話)、Step 2の副作用として今回新たに発見した。

**対応方針**: 本タスクのscope(5指標の移設 + `incident_sync` 退役)を超える新機構(例: Ansible側が新規バンドルの内容を事前取得してローカルへ書く、等)は実装しなかった。設計判断・Policy(IC-016/IC-031/IC-032)への影響を伴うため、実装せず判断材料として本記録に残す。緩和策として、プロンプトテンプレート側に「ローカルに実体が無い新規バンドルは内容を読めない旨を明記し、推測で埋めない」よう明示的な指示を追加した(§5でレンダリング確認済み)。**この点はCoordinatorの判断を要する。**

## 5. 自己検証

実ホストへは一切触れていない(Implementerの権限どおり)。

| # | 検証 | 手段 | 結果 |
|---|---|---|---|
| 構文 | 変更した全playbook | `ansible-playbook --syntax-check`(`playbooks/*.yml` 全件、事前に無関係な2件が失敗することを確認済み — `proxmox_evacuate_node.yml`/`proxmox_restore_vm_placement.yml` は `-e target_node=` 必須で私の変更と無関係) | 全件通過 |
| lint | 変更した全role/playbook | `ansible-lint`(対象を絞って実行 → 変更前後の出力を diff) | 変更前後とも同一の11件(すべて私が触れていない行、pre-existing)。新規0件。**当初1件の YAML load-failure(task名の `V2: this` がコロン+空白でmapping扱いされてparseエラー)を自己検証中に発見・修正**(§`incident_metrics.yml`) |
| Python構文 | `incident-investigate.py` / `incident_investigate_trigger.py` | `python3 -m py_compile` | 両方OK |
| Python単体 | `build_notify_payload()` | モジュールを直接importして呼出し、`iv_report_path` の値と `trigger_ansy_sync` の不在を確認 | `ssh quory-investigate investigation-show semaphore-12345 md`、関数削除済み |
| JSON生成 | `incident-investigate.json.j2` | `ansible.builtin.template` でレンダリング後 `python3 -c "json.load(...)"` | valid JSON、sync_trigger系キーが全て消え `dispatch_ssh_alias` が追加されていることを確認 |
| **機能テスト(オフライン)** | `incident_metrics.yml` を `include_role: tasks_from` でスタンドアロン実行。`ssh` 実体をローカルの fake_ssh.sh スタブへ差し替え(`knowledge_review_incident_dispatch_ssh_bin` を `-e` で上書き)。**実ホストへは一切接続していない** | 5パターン実行(下記) | 全パターンで期待どおりの `incident_eval_index` を確認(詳細は下記) |
| プロンプト描画 | `incident-review-prompt.md.j2` | `ansible.builtin.template` で2パターン(成功時/取得失敗時)レンダリング、目視で内容確認 | 両方とも意図した文言(取得失敗時は「推測で件数を埋めないこと」という明示指示が出る)で描画される |
| 分類ロジック | `incident_eval_summary` の4分岐 | Jinja式を4ケース分 `set_fact` で個別評価 | `A(rc≠0)=FAILED` / `B(fetch失敗)=FETCH_ERROR` / `C(取得成功0件)=NO_DATA` / `D(通常)=OK` — 設計どおり |
| V6 | 終了状態の判定方法 | 全 `command` タスクで `.rc` を直接読む形になっていることをコード読解で確認(`\| head` 等のパイプ越し判定は使用していない) | 該当箇所なし |

### オフライン機能テストの5パターン

前回index(`last_bundle_id_seen: 12`)を用意し、stub `ssh` が `bundle-list` で `semaphore-10〜14` を返す設定を基本形とする。

| パターン | 条件 | 結果 |
|---|---|---|
| ok | 通常成功 | `mirror_bundle_total=5`, `bundles_new=2`(13,14), `oldest={id: semaphore-13, age_days: 8}`, `last_bundle_id_seen=14`, `bundle_fetch_error=""` |
| fail_list | `bundle-list` 自体が非0終了 | `mirror_bundle_total=null`, `bundles_new=null`, `bundle_fetch_error="bundle-list dispatch failed rc=1 stderr=denied: ..."`, `last_bundle_id_seen=12`(前回値を維持) |
| empty | `bundle-list` 成功・0件 | `mirror_bundle_total=0`(nullではない), `bundle_fetch_error=""`, `last_bundle_id_seen=12`(維持) |
| fail_show | `bundle-list` 成功だが最古1件の `bundle-show` が失敗 | `mirror_bundle_total=5` は正常、`oldest_unreviewed_bundle.generated_at/age_days=null`、`oldest_bundle_summary_parse_error="bundle-show for semaphore-13 summary.json failed rc=1 stderr=denied: ..."` |
| 初回(前回index無し) | previous_evaluation_date=null | 5件全件を新着扱い、oldest=semaphore-10(最小id) |
| `--check` | ok同条件、`--check` 付き | `bundle_fetch_error="not attempted under --check (no real host contacted)"`、`mirror_bundle_total=null`、`last_bundle_id_seen=12`(維持・real host未接続) |

V2(「`ssh quory-investigate bundle-list` は現時点で50件以上のバンドルを返す」)は**実機での確認であり、Implementerの権限では検証できない**(「実ホストへansibleを実行しない。状態を変えない確認も含む」)。上記オフラインテストは実装ロジックの正しさを実データ相当の入出力パターンで確認したものであり、実機接続そのものの成否はTester(またはCoordinatorの状態を変えない確認)による別途検証が必要。

## 6. NO_DATA の意味の再考(依頼事項への回答)

**判断: NO_DATAの意味は「取得は成功したが、quory原本に実際にバンドルが0件だった」に絞り込まれる。** 旧NO_DATAは「ミラーのbundle_totalが0」であり、これは①quory上に本当にバンドルが0件、②ミラーが一度も同期できていない、の2つの原因が区別なく混ざっていた(heartbeat/staleが別途②寄りの兆候を出していたが、bundle_total自体は原因を問わなかった)。

dispatchはquory原本への**ライブ問い合わせ**であり、「同期が止まっている」という中間状態が構造的に存在しない(取得できるか、できないかの二値)。取得失敗は新設した `FETCH_ERROR` へ先に分岐するため、NO_DATAへは混入しない。**したがって移行後のNO_DATAは、旧実装より意味が狭く・正確になった。**

`FETCH_ERROR` は旧`STALE`の**代替ではなく別概念**である点に注意 — 旧STALEは「転送は成功しているが心拍が古い(間接的な兆候)」、新FETCH_ERRORは「今回の実行でdispatch呼び出し自体が失敗した(直接的な失敗)」。`playbooks/knowledge_review.yml` のSlack通知では、両者を同じ扱い(alertsチャンネル・warning)にした — 深刻度としては同格と判断したため。

## 7. 残す参照とその理由(V1)

`incident_sync` / `incident-sync` という文字列は、`docs/ai/reviews/` 配下の履歴記録に加えて、次の非reviewファイルにも残っている。**いずれも「これは何を置き換えたか」を説明する経緯コメントであり、機能的な依存・呼び出しは無い。**

- `playbooks/incident_sync_teardown.yml`(新設。名前・コメントとも意図的 — 退役対象を指し示すためのファイル)
- `roles/incident_investigate/defaults/main.yml` / `files/incident-investigate.py` / `callback_plugins/incident_investigate_trigger.py` — 「以前はここでincident_syncの受け口を叩いていたが削除した」という経緯コメント
- `roles/knowledge_review/defaults/main.yml` / `tasks/incident_metrics.yml` / `tasks/incident_evaluation.yml` / `templates/incident-review-prompt.md.j2` — 同様の経緯コメント

**触れていない(かつ現時点で `incident_sync` / 転送・ミラーの前提を含む)正本文書**:

- `docs/ai/policies/incident_capture_policy.md` §4「転送の規律」全体(IC-012〜IC-015)、および IC-021・IC-031・IC-032。いずれも「quory→ansyの転送」「ミラー」を前提にした規範であり、`incident_sync` 退役後は対象を失っている(IC-021の「拾われなかったことの検知」は今回Step 3のbundle-id方式に引き継がれたが、IC-031/IC-032の「ミラーへ判断を書くな」という規則自体は名宛人を失っている)。**Policy文書の改訂はImplementerの権限外**であり、依頼のファイルスコープにも含まれないため変更していない。Coordinatorの別途判断が要る。
- `docs/ai/adr/003-incident-capture-collector-runtime.md`(Status行が「転送=ansy `ansible-incident-sync.timer`」と明記)、`docs/ai/adr/009-per-incident-investigation-runtime.md`(「`incident_sync` は削除操作を持たない」等)。いずれも当時の設計決定の記録であり、書き換えるとADRとしての性質(決定時点のスナップショット)を損なうため触れていない。
- `docs/ai/status.md`(L23・L32・L36の3箇所)。Step 10でCoordinatorが更新する対象として plan に明記されており、今回は触れていない。L32(「incident_syncの退役に伴い...」のWatch項目)は本実装により解決済みのため、Coordinatorの更新対象になる。

## 8. 未解決事項

1. **§4のギャップ(質的評価セッションが新規バンドルの内容を読めなくなる)は未対応。** Coordinatorの判断を要する。
2. Policy(`incident_capture_policy.md`)とADR(003・009)が転送/ミラーを前提にした記述のまま残っている(§7)。Policy改訂の要否はCoordinator/Yoshinobuの判断。
3. `incident_sync_teardown.yml` は未実行。実行順序は plan §4 のとおり「Step 4(独立レビュー)の後」を想定しているが、リポジトリ側の削除自体はこのplaybookの実行有無に依存せず既に完了している(quory/ansyへの反映、すなわち `git pull` 後の実ホスト状態の一致は別途Coordinatorが確認する)。
4. V2(dispatchが実際に50件以上返すこと)はImplementerの権限では検証していない。§5のオフラインテストがロジックの正しさを裏付けるが、実機接続の成否はTester/Coordinatorの確認が必要。
5. `last_bundle_id_seen` はSemaphore job idが単調増加であることに依存する設計判断である。実測(2026-08-03、55件)ではこの前提が成立しているが、これはSemaphoreの実装詳細への依存であり、Semaphore側の仕様変更(id再利用等)があれば崩れうる。現時点でそれを示す情報は無い。

---

## 決着(Coordinator、2026-08-03)

### 実ホストの後始末

`playbooks/incident_sync_teardown.yml` は本記録の時点で「未実行」だったが、**独立レビュー(`..._018_`)が権限設計の Critical を検出したため修正し、その後に実行した。** 実行結果と残存確認は `..._018_` の「Coordinator の処置」節にある。

### 「質的評価が新規バンドルを読めなくなる」ギャップについて

本記録が範囲外として挙げたこのギャップは、**前提ごと解消した。**

指摘の内容は「ミラーが凍結されるため、以降の新規バンドルの本文を月次の `claude -p` セッションが読めなくなる」だった。Coordinator は「評価直前に Ansible が本文を取得して置く」案を推奨したが、**Yoshinobu が却下し、さらにその先へ進んだ** — 2026-08-03、**月次の `claude -p` を2本とも廃止**し、タイマーはきっかけの通知だけを出す形になった。見直しは人が対話セッションと行う。

**読み手が消えたため、「読めなくなる」という問題自体が存在しなくなった。** 却下の理由(規範を大きく入れ替えた直後で振り返りの前提が不明であること等)は `docs/ai/status.md`「載せていないもの」に記録した。以降の設計は `..._019_policy_revision_proposal.md` と `..._020_` / `..._021_` が持つ。
