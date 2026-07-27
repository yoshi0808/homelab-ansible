---
date: 2026-07-27(JST, +09:00)
role: Reviewer(独立レビュー、W4相当)
target: roles/incident_capture/ 一式、playbooks/incident_capture_setup.yml
scope外: roles/common_slack/(W1、確定済み)、scripts/git-pre-commit-check.sh、scripts/check-staged-yaml.py(別Reviewer担当)
---

## Code Review: incident_capture role(証拠バンドル収集器、W3)

### Summary

収集器本体(Python、時刻パース、D1準拠のサブプロセス呼び出し、collection_errors設計、AC6拡張子)は丁寧に作られており、R5の「握りつぶさない」方針を概ね実装できている。しかし `roles/incident_capture/tasks/main.yml` の `_spool/` ディレクトリ作成タスクに **owner未指定のまま `become: true`(root昇格)を使う** 欠陥があり、配備順序次第でT1(`common_slack/capture.yml`、実行ユーザ`yoshi`)の書き込みを永続的に拒否し得る。この経路はT1自身のrescueに握りつぶされ、R5b・run_run_report のいずれからも検出できない組み合わせが存在するため、Critical(Request Changes)とする。ADR-003からの逸脱(`_spool/`へのACL付与)自体は正当と判断した。

### Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `roles/incident_capture/tasks/main.yml` | 28-33 | `Ensure reports/incidents/_spool/ exists` タスクが `become: true`(become_userはinventory未設定のためroot)で実行され、`owner:` を指定していない。**兄タスク(11-21行、`reports/incidents/` 本体)は同じ状況で明示的に `owner: yoshi` を付けているのに、この1タスクだけ抜けている。** `reports/incidents/` がまだ存在しない初回配備で `incident_capture_setup.yml` がT1(`capture.yml`)より先に走ると、`_spool/` は `root:root mode 0755` で作られる。T1は `delegate_to: localhost` / `become: false` で実行され、quory本番のAnsible実行ユーザは `yoshi`(W0実測 T-OQ2で確認済み、`systemctl show semaphore -p User` → `User=yoshi`)。root所有・0755のディレクトリに非root・非グループメンバーのyoshiは書き込めない。このタスクの直後に付与されるACLは `recovery-exec` 宛のみで `yoshi` には何も与えない。結果、**T1の全38呼び出し箇所での書き込みが `mv`/`copy` 失敗で永続的に失敗し続け**、しかしT1自身の `rescue:` が `debug` のみで吸収するため通知・呼び出し元playbookのrc/failedには一切現れない(R3の「観測が被観測を変えない」設計そのものが、この欠陥を外から見えなくする)。W0実測(`2026-07-27_004_observation.md` T-OQ4)で「`reports/incidents/` は現時点で存在しない」ことを確認済みであり、**この配備順序は仮説ではなく実際に起こり得る初回配備の標準経路**(playbook冒頭コメントが `ansible-playbook playbooks/incident_capture_setup.yml -l quory` を独立実行手順として明示している)。<br>**再現条件**: `reports/incidents/` が存在しない状態で `incident_capture_setup.yml` を先に実行し、その後 `capture.yml` を経由するplaybookを実行 → spoolファイルが1つも作られないことを、書込み権限エラーとして(`ls -la` で `_spool/` の owner が root であることと合わせて)確認できる。<br>**影響**: R1(通知経路での捕捉)がサイレントに全滅する。R5bは「新規失敗ジョブがあるのにspool総数ゼロ」の周期でのみ気づけるため(下記Suggestions参照)、失敗ジョブが出るまで検出されない可能性がある。<br>**修正案**: 兄タスクと同様に `owner: yoshi` を明示するか、このタスクから `become: true` を外す(T1自身の作成手順と同じ非become実行に揃える)。 | **Critical** |

### Suggestions

| # | File | Suggestion | Category |
|---|---|---|---|
| 2 | `roles/incident_capture/files/incident-capture-collector.py`(main、R5b部分, 538-551行) | requirement R5bの文言「ジョブ実行の記録があるのにspoolレコードが1件も無い」に対し、実装は「**新規の失敗ジョブ**があるのにspool総数ゼロ」に狭めている(docstring 29-37行で自己申告済み)。既存 `homelab-semaphore-query recent-failed` のみを使う制約(ADR-003 (c)、新規SQL追加禁止)の下では妥当な選択だが、**成功ジョブしか起きていない周期にT1が壊れても検出できない**という既知の限界が残る。Critical #1のような「T1が完全に沈黙する」欠陥と組み合わさると、失敗ジョブが偶然出るまで誰にも気づかれない期間が生じうる。目的(T1停止の検出)を完全には達成しない。次項(#3)のハートビート方式を、この限界の補完として検討する価値がある。 | Design gap(R5b範囲) |
| 3 | `roles/incident_capture/files/incident-capture-collector.py`(main、650-663行) | `write_run_report` は `collection_errors` かバンドル単位のエラーがある場合にのみ呼ばれる設計(Implementer自己申告どおり、ADR/requirementに明記なし)。**正常終了時(新規イベント無し、または全て正常に処理できた周期)は `reports/` 配下に一切の成果物を残さない。** systemd timer/oneshotが5分ごとに走っていること自体を外部から確認する手段が無く、収集器プロセスが完全に停止しても(unit失敗、flockのlockファイル権限問題、Pythonインタプリタ不在等)、それを検出する仕組みが repo 内に存在しない。Critical #1・#2との組み合わせで「T1もR5bも収集器自身の死活も、何一つ検出しない」という完全な沈黙状態が理論上成立する。**提案**: 毎周期(正常時も含め)`_runs/` へ軽量なハートビートレコード(`generated_at`, `spool_total_this_cycle`, `bundles_created` 件数, `exit_code` のみ)を無条件で書く。既存の `retention_days` とは別の短い保持(例: 直近数十件)で回転させれば `.gitignore` 適合(`.json`)のまま運用でき、将来の監視(既存 `monitoring_healthcheck` 系や新規チェック)が「最後の成功実行からの経過時間」を読める。AC5/AC7の終了コード契約は変更不要。 | Observability(R5の主題) |
| 4 | ADR-003 §Decision (b) / 本Decision記述 | ADR-003は「新しく増える権限は **`reports/incidents/` に対するPOSIX ACL(default entry付き)だけ**」「`reports/` 直下へのACL付与を禁止する」と書くが、実装は `reports/incidents/_spool/` にも明示的な named-user ACL(access + default)を追加している(`tasks/main.yml` 67-84行)。**現物確認の結果、この逸脱はRSK-06の実害(reports/直下 or reports/proxmox-dryrun/への書込み権限化)を引き起こしておらず正当と判断した**: (1) `_spool/` は `reports/incidents/` の内側であり `reports/` 直下にもproxmox_patch_apply_nodeのgate入力(`reports/proxmox-dryrun/`)にも触れない、(2) 理由も技術的に妥当 — default ACLは「そのディレクトリ配下に新規作成されるエントリ」にしか継承されず、T1がこのroleより先に `_spool/` を作っていた場合(通常の配備順序ではこちらが普通)、`reports/incidents/` への default ACL だけでは既存の `_spool/` 自体には遡って効かない(POSIX ACLの一般的な仕様どおり)。ただし **ADR本文の一文「だけ」はこの例外を書いていない** ため、Tech Lead/Coordinatorの判断でADR-003の当該一文を「`reports/incidents/` 配下(サブディレクトリを含む。ただし `reports/` 直下・その他の兄弟ディレクトリには付与しない)」のように改訂し、この逸脱を追認しておくことを推奨する(正本と実装の食い違いをそのまま残さない)。blockingにはしない。 | ADR-code整合性 |
| 5 | `roles/incident_capture/files/incident-capture-collector.py`(`run_investigate`, 249-266行) | SSH到達不能(routineなpve1平日停止)と、`homelab-investigate-<host>` バイナリそのものが存在しない(デプロイ不整合・設定ミス)が、どちらも `{"ok": False, "error": ...}` として同じ扱いになり、`collection_errors[]`にもexit codeにも一切影響しない。前者は意図的にnon-fatal(ADR-003末尾の解説どおり妥当)だが、後者は本来「収集器の設定・配備そのものの欠陥」であり、`incident_capture_investigate_bin_template` のtypoや配備漏れが起きても収集器は気づかず動き続ける。`os.path.exists(path)` が false のケースだけ `collection_errors` へ積む(exit 2)よう分岐すると、routineなSSHタイムアウトと配備欠陥を区別できる。 | Robustness |
| 6 | `roles/incident_capture/files/incident-capture-collector.py`(`parse_recent_failed` / `parse_task_time`, 147-189行) | `line.split("|", n)` によるパースは、テンプレート名(`template`)や `playbook` フィールドに偶然 `\|` 文字が含まれた場合、フィールドがずれて誤った値を拾う(エラーにはならず静かに間違った位置の値を使う)。現状のtemplate名はYoshinobu管理下で `\|` を含む可能性は低いが、フィールド数チェック(`len(parts) != 5/6`)は列数のみを見ており列内容の妥当性までは保証しない。優先度は低いが、`homelab-semaphore-query` 側の出力デリミタが将来変わった際の余寿命として留意。 | Robustness(低頻度) |
| 7 | `roles/incident_capture/files/incident-capture-collector.py`(`apply_retention`, 353-371行) | `retention_days` による削除対象は `bundle_dir` 直下の `semaphore-*` / `spool-*` ディレクトリのみで、`_spool/_rejected/`(スキーマ不正spoolの退避先)と `_runs/`(run report)には保持期限が無く、無期限に増え続ける。件数は少ないと想定されるが、R7の「quory上に無限に溜めない」という趣旨からは両方とも対象に含めるべきではないか検討の余地がある。 | Retention漏れ(R7) |
| 8 | `roles/incident_capture/files/incident-capture-collector.py`(`main` 554-583行) | 同一のSemaphore失敗ジョブに複数ホスト(同一playの複数対象)からのspoolレコードが時間窓内で相関した場合、`host_for_ops = matched_recs[0]["play_host"]` は最初にマッチしたレコードのホストだけを追加スナップショット対象に選ぶ。全レコード自体は `spool_records[]` に保存されるため情報は失われないが、他のホストに対応する `failure_snapshot_ops` があっても取得されない。低頻度・低影響と判断し非blocking。 | Completeness(軽微) |

### What Looks Good

- **時刻パース(OQ1/R5)**: `GO_TIME_RE` はW0実測(`2026-07-27_004_observation.md`)の生値 `YYYY-MM-DD HH:MM:SS[.nnnnnnnnn] +0000 UTC` に正確に一致し、Goの `time.Time.String()` が小数点以下を全て0の場合に省略する仕様(`.999999999` レイアウト)にも `(?:\.(\d+))?` で対応している。パース失敗は握りつぶさず必ず `ValueError` として呼び出し側の `try/except` で捕捉され `collection_errors`/`bundle_errors` に積まれる(コードパスを一通り追跡して確認)。出力側 `to_rfc3339_jst` は常にオフセット付き(`isoformat(timespec="seconds")`)で、裸の `Z`/`UTC` を一切付けない。JST変換は固定 `timedelta(hours=9)` の単純加算で日本にDSTが無いため境界値・日跨ぎとも問題なし。
- **静かに壊れる経路への対策(全体)**: SemaphoreクエリのOSError/timeout、行パース失敗、spoolのJSONスキーマ不正、`written_at` 不正はすべて `collection_errors[]` または `_rejected/` への退避+記録として可視化される。トップレベルの `except Exception` も内部バグを exit 3 として区別し、AC5が要求する「非ゼロかつ意味が定義済み」の終了コードを満たす。
- **D1準拠(コマンド構築)**: `run_semaphore_query` / `run_investigate` とも `subprocess.run([bin, *args], ...)` の argv リスト形式のみで、`shell=True` や文字列連結は一切無い。投機的に気になった「spoolレコード由来の `play_host` がinvestigateのホスト名に化けて未検証のパスを組み立てないか」を追ったが、`collect_host_snapshot` が `cfg["failure_snapshot_ops"]`(固定allowlist辞書のキー)に無いホストを弾いてから `run_investigate` を呼ぶ構造になっており、spool由来の任意文字列が `bin_template.format(host=...)` へ到達する経路は無いことを確認した。
- **AC6(拡張子)**: 収集器が生成しうる全パス形状(`summary.json`、`*.json.tmp`、`semaphore-log.log`/`semaphore-errors.log`/`semaphore-hosts.log`、`_spool/*.json`、`_spool/_rejected/*.json`、`_runs/run-*.json`)を列挙し、`git check-ignore -v --no-index` で1件ずつ照合した。全て `.gitignore` の `reports/**/*.json`・`reports/**/*.log`・`*.tmp` のいずれか1規則に一致し、対象外に漏れるパスは見つからなかった(実ファイルは作らず `--no-index` の規則照合のみ、確認後の後始末不要)。`state_dir`(`/var/lib/homelab-recovery/`)と `config_dir`(`/etc/homelab-recovery/`)は `reports/` 外にあり、AC6の対象そのものにならないことも確認した。
- **RSK-06本体(reports/直下)**: `incident_capture_bundle_dir` は `reports_base_dir + "/incidents"` に固定され、`proxmox_patch_apply_node` が読む `reports/proxmox-dryrun/*_unified_dryrun.json`(`roles/proxmox_patch_apply_node/tasks/main.yml:293`)とは別ディレクトリツリーであることをgrepで確認した。ACL付与はすべて `reports/incidents/` ツリー内に閉じており、`reports/` 直下やそのきょうだいディレクトリには一切触れていない。
- **終了コード設計**: `0`/`2`/`3` の3値+`flock -E 75`は明確に定義・文書化されており、AC7(多重起動)の要求(定義済みの値で区別できる)を満たす。SSH到達不能を単体でexit 2に昇格させない判断は、ADR-003末尾の解説(pve1平日停止の常態化)と整合しており妥当と判断した。ただしSuggestion #5のとおり「配備欠陥によるSSH以前のバイナリ不在」まで同列に扱っている点は改善余地がある。
- **systemd unit**: 既存前例(`recovery-probe.service.j2` の `User=`/`Environment=`、`knowledge-review.service.j2` の `flock -n`)を踏襲しており、新しいパターンを持ち込んでいない。`roles/systemd_timers`(User固定yoshi)を使わなかった判断もADR-003の記述と一致し、重複再利用の観点で問題なし。

### 未解決事項

- Critical #1は実host(quory)での再現・修正確認をTesterに委ねる必要がある(本レビューはコード追跡のみで、実ホストへのアクセスは行っていない)。修正後は「`reports/incidents/` が存在しない状態から `incident_capture_setup.yml` を先に実行 → T1経由のplaybookを実行 → spoolファイルが作られる」の順序を明示的にTesterのW5項目へ追加することを推奨する(現行の投資調査書W5表にはこの配備順序ケースが無い)。
- Suggestion #2/#3は設計判断であり、実装の欠陥ではない。採否はCoordinator/Tech Leadの判断事項として残す。
- 本レビューは `roles/incident_capture/` と `playbooks/incident_capture_setup.yml` に限定し、`roles/common_slack/tasks/capture.yml` は入力契約の確認のためにのみ読んだ(変更提案なし、別Reviewer担当のため対象外)。
- 実ホスト・Semaphoreデータベースへのアクセスは行っていない。検証は静的コード追跡と `.gitignore` 照合(`--no-index`、ファイル未生成)のみ。

### Verdict

**Request Changes**(Critical #1のため)。Critical #1の修正(`_spool/` 作成タスクへの `owner: yoshi` 明示、または `become: true` の削除)のみでBlockingは解消できる見込み。Suggestions は非blocking。
