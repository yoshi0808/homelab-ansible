# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)はここに書かない。対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。

## このファイルの規律

1. **状態は「使う場所」へ書くのが第一選択。** コード・Policy・Contextの当該箇所に書けば、そこを変更する人の目に必ず入る。**ここへ載せるのは置き場が他に無い状態だけ** — 将来の日付やイベント待ち、複数箇所にまたがるもの。
2. **Watchの各行に検証手段を必須とする。** 書けない項目は載せず、残存リスクとして一次記録へ残し、「載せていないもの」へ1行残す。Nextは検証手段の代わりに**根拠**を必須とする。
3. **完了したら行を消す。履歴を残そうとしない。** 履歴は `git log` が持つ。クローズした案件の経緯・成果物・正本へのポインタをここへ書かない(2026-08-01、Yoshinobu指示で徹底した)。積み増すとこのファイル自身が「いちばん古いのに確実に読まれる層」になる(`docs/ai/memory/lessons/always-loaded-summaries-are-the-least-current.md`)。
4. **値を二重に持たない。** 他に正本があるものは参照だけ書く。Policyが決めていることをここへ写さない。
5. **更新のトリガは3つ** — 完了した / 方針を変えた / 観測待ちが増えた。

**このファイルも古くなりうる。** 3トリガはCoordinatorセッションを経由しない変化(Yoshinobuの手作業、外部システムの変化)を拾えず、補いは①案件やレビューの過程で気づいたらその場で消す②月次Knowledge振り返りが現物と突き合わせる、の2つで周期は最長1か月ある。**各行は「主張」ではなく「検証手段つきの申し送り」として読み、判断に使う前に検証手段の側を確かめること。**

`skills/goal-tracking/SKILL.md` の Now / Next / Later とは軸が違う(あちらは優先度軸、ここの Watch は時間・イベント軸)。優先度の議論が要る項目は Next に置く。

## Now(進行中)

| # | 項目 | 現在地 | 次にやること |
|---|---|---|---|
**進行中の案件は無い。**

**「一次調査の結果をSlack通知 + quory→ansy同期の即時実行」(R14)は2026-08-01にクローズした。** commit `4e7233b`、quory・ansy双方へ配備済み。**境界の非通過側3件はすべてPASS** — forced commandが引数を無視する(任意コマンドが実行されない)、専用ユーザーが他のunitを起動できない(`cron.service` の `ActiveEnterTimestamp` が試行前後で不変)、`recovery-exec` が鍵を読めない(`sudo -u recovery-exec` で実際に再現)。同期の即時起動も、timerの発火とは別の非定刻起動として観測した。**残る観測はWatchが持つ。** 案件記録は `docs/ai/reviews/incident_investigation_notify/`(001〜006)。**R15(修正依頼の自動起票)はやらない**(2026-08-01 Yoshinobu)。

## Watch(観測待ち)

**将来の時点でしか確かめられないこと**を置く。着手すべき作業ではない。

| 項目 | 発火条件 | 検証手段 | 一次記録 | 最終確認 |
|---|---|---|---|---|
| quoryの作業ツリーを**Coordinator / Testerが直接確認できない** | quoryの作業ツリー状態を検証したいとき | 接続identity(`ann`)と所有者(`yoshi`)が異なり `dubious ownership` が `rc=128` で拒否する。回避には `safe.directory` が要り承認範囲外。**gitの状態は読めないが、ファイルの中身は読めるので内容で代替できる**(2026-08-01に実施)。`semaphore.db` も `ann` では開けない | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md`、`.../incident_auto_capture_step2/2026-07-28_004_quory_units_survey.md` | 2026-08-01 |
| 月次Knowledge振り返りの**初回無人実行**。**障害評価(2本目の `claude -p`)を含む** | 毎月26日(期日の正本はauto-memory `MEMORY.md` 先頭行。ここへ写さない) | ansyで `systemctl list-timers ansible-knowledge-review.timer` と `journalctl -u ansible-knowledge-review`。実行後は作業ツリーに未commit差分が出る。**障害評価の成果物は `reports/incidents/_evaluations/` に出る(gitignore済みなので差分には現れない)。** 手動での通しは2026-07-28に成功済み | `roles/knowledge_review/`、`docs/ai/reviews/incident_auto_capture_step2/2026-07-28_020_u11_test_result.md` | 2026-07-28 |
| Context陳腐化チェック追加後の**`knowledge_review_timeout`(1800秒)が足りるか** | 次回2026-08-26の月次実行 | `journalctl -u ansible-knowledge-review`でタイムアウト終了していないか確認。Testerのdecoy見積もりでは余裕が無い可能性が高いとされた(実測はデータが無く不可) | `docs/ai/reviews/knowledge_review_context_check/2026-07-29_005_u1_test_result.md` | 2026-07-29 |
| **一次調査 → 通知 → 即時同期が、実データで通しで成立するか**(AC1とAC4のエンドツーエンド) | 次にSemaphoreジョブが失敗したとき | ①`#alerts` に通知が1本届く(**本番でまだ一度も出ていない**)②その直後にansyで `ansible-incident-sync.service` が**定刻でない**タイミングで起動する。**2026-08-01に観測した非定刻起動は手動SSHテストによるもので、`incident-investigate.py` からの結線はまだ一度も発火していない** — 機構は動くが実データでの通しは未達である | `docs/ai/reviews/incident_investigation_notify/2026-08-01_006_post_deploy_observation.md` | 2026-08-01 |
| **月次実行と同期起動が競合したとき静かにskipするか**(AC8) | 月次Knowledge振り返り(2026-08-26)の実行中に一次調査が走ったとき。**または外側flockを占有して意図的に作る** | 同期起動が exit 0 で終わり `failed` にならないこと。取りこぼしは次の定刻同期が埋めること。**意図的に作る場合はロックの占有という非冪等操作を伴う**ため、実施の可否はその時点で判断する | 同上 | 2026-08-01 |
| **一次調査の失敗が本番で可視化されるか**(IC-038の本番実測) | 一次調査が実際に失敗したとき(LLM呼び出し失敗・タイムアウト等) | `_investigations/` に `status: failed` の成果物が残り、かつ `systemctl is-failed homelab-incident-investigate.service` が `failed` を返すこと。**2026-08-01時点で本番の成果物は10件すべて `status: new`** であり、失敗経路は配備前fixtureでしか通っていない。`SuccessExitStatus=75` により、flockによる正常なskipは `failed` にならない | 同上 | 2026-08-01 |
| weekly full patchの**apply gateを実データで通す** | Proxmox dry-runが `PATCH_READY` を返す週 | `playbooks/proxmox_patch_weekly_full.yml` の `_dryrun_missing_nodes` が実データで空になること。現状の根拠はdecoy検証のみ | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L426 | 2026-07-27 |
| Proxmoxパッチ自動チェーンの **実発火の観測** | パッチ件数が少なく手動介入が要らない週末 | 自動チェーンが最後まで通ったログ。過去2回(07-11/12、07-18/19)は大量パッチで手動対応となり未観測 | `docs/ai/reviews/tester_mode/`、`docs/ai/context/operations/proxmox-patch.md` | 2026-07-27 |
| Alloy **Phase 3(異常値のFire)** | Lokiにログが十分蓄積した時点 | requirementは作成済み。Grafana Exploreで対象シグネチャの出現頻度を見て閾値を決める | `docs/ai/reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md` | 2026-07-27 |
| ubuntu_nightly の **monnie / authy リブート経路が実機で通るか** | 次に各ホストの `reboot_required` が true になる夜 | `[ubuntu_nightly] OK - monnie` / `authy` がinfoへ飛ぶこと。失敗した場合は本文に**失敗タスク名と理由**が入っていること(固定文言でないこと)。**authy側(commit `3fbb9e8`)は実機検証を経ずに本番投入している** — decoy検証のみ | `docs/ai/memory/incidents/2026-07-30_ubuntu-nightly-monnie-external-port-wait.md`、`docs/ai/reviews/ubuntu_nightly_reboot_check/` | 2026-07-30 |
| **pve1が起動している時にしか確かめられない2件** | pve1が起動している時間帯(週末のパッチ運用が自然) | ①`playbooks/proxmox_backup_restore_verify.yml` を本実行し、対象VMの `prefer<node>` タグどおりのノードでrestoreされ、レポートJSONの `restore_node_fallback` が **false** になること ②`playbooks/unifi_backup_fetch.yml` の Play 1 が両系到達可能時に **pve1** を選ぶこと。**①②とも共通role `proxmox_exec_node` の同じ分岐**であり、decoyでは両方PASS済み | `docs/ai/reviews/proxmox_exec_node_selection/2026-07-29_007_test_result_step1.md`、`docs/ai/reviews/unifi_backup_fetch/2026-07-25_013_test_result.md` L114 | 2026-07-29 |
| **pve1停止中のread-only点検3本がSemaphoreで緑になるか** | 平日の発火(healthcheck 05:40 JST / hw_check 05:45 JST 毎日、snapshot_check 木18:00 JST) | `homelab-semaphore-query recent-failed` にこの3本が現れなくなること、かつSemaphore summaryに`Result=OK \| Unchecked=pve1`が出ていること。**`ann` は `semaphore.db` を開けないため、この確認にはyoshi権限かSemaphore UIが要る**(2026-08-01に試行して確認) | `docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_006_test_result.md` | 2026-08-01 |
| **両ノード到達可能時の回帰** | pve1が起動している時間帯 | 上記3本のsummaryに`Unchecked=`が**出ない**こと、rc=0であること。両ノードの行が従来どおり並ぶこと。decoyとテンプレート描画では確認済み | 同上 §5・§7 | 2026-07-30 |
| **変換した14本のうち13本で「通常実行の不変」が未検証** | 各playbookが次に**`--check` なしで**通常実行されるとき。`cert_renew` は2026-08-02〜03の週末に本番でまとめて回す予定 | 追加した `when: not ansible_check_mode` は既存条件への**AND追加**であり通常実行時は影響しない、というのが根拠だが**静的読解のみ**(Tester役は `--check` なし実行を禁じられている)。壊れている場合の出方は「本来走るべきtaskがskipされる」で、playbookのサマリとSlack通知に出る。**`codex_update_check` は2026-07-31の通常実行で確認済み** | `docs/ai/reviews/check_mode_semantics/` 009 / 012 / 015 / 018 / 019 | 2026-07-31 |
| **`cert_renew` の ansy / proxmox / monnie play が `--check` で未到達** | 上と同じ週末の本番実行 | Tester接続identity(`ann`)がこれらのホストへのSSH認証情報を持たないため到達できなかった(**identity昇格は試みずに停止**)。quory上の `localhost` / `quory` play では rc=0・破壊的task全skip・CA証明書のmtime不変まで確認済み | `docs/ai/reviews/check_mode_semantics/2026-07-31_019_round2_batchC_quory_test_result.md` | 2026-07-31 |
| **Semaphoreの定期ジョブが `risk-accepted` へ `--check` を渡していないか**(残るは `proxmox_backup_restore_verify` と `cloudkey_cert_deploy` の2本) | 次に各定期ジョブが発火したとき | 渡していればそのジョブが **rc=2 で赤くなる**(TS-030の停止assert)。**Semaphoreの設定はrepo外でAIから確認できないため、事前確認ではなく発火で検出する設計を選んだ。** 赤が出た場合の正しい対処は、assertを外すことではなく**そのジョブから `--check` を外すこと** | `docs/ai/reviews/check_mode_semantics/2026-07-31_001_requirement.md` §7 OQ3、`docs/ai/policies/ansible_test_safety_policy.md` TS-030 | 2026-07-31 |
| Semaphore実行環境で **fact caching が無効か** | Yoshinobuが Semaphore UI を開いたとき | ジョブ/テンプレート設定に `ANSIBLE_CACHE_PLUGIN` / `ANSIBLE_GATHERING` が注入されていないこと。**有効だと `proxmox_patch_dryrun` が停止中のノードをキャッシュ済みfactsから「到達可能」と誤判定する**。**repo外のためAIからは確認できない。** 残る影響は `proxmox_patch_dryrun` 1箇所のみ | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` §14-5 a | 2026-07-29 |
| **`proxmox_backup_restore_verify` Play 3 の停止assertが実行検証できない** | 検証手段が無い。**Playの構造を変えたときに再考する** | **`--check` で観測する経路が原理的に存在しない** — Play 2 の停止assertが先に失敗して run 全体が止まるため Play 3 へ到達しない。これは多重防御であり、**現時点では静的な存在確認しかできない**。Play の順序・`add_host` の構造・Play 2 のassertを変更する人は、Play 3 側が唯一の防波堤になることを踏まえること | `docs/ai/reviews/check_mode_semantics/2026-07-31_022_audit.md` 指摘#2 | 2026-07-31 |

## Next(着手候補) — 工程・体制

| 項目 | 内容 | 根拠 |
|---|---|---|
| **`skills/subagent-briefing/` の改訂**(申し送り5件を1本化) | いずれも「Coordinatorの依頼文の欠陥が実装・検証を歪めた」同一クラス。①subagentのscratch作業がリポジトリ内へ漏れる(自己参照シンボリックリンク2本。`git status --short` は未追跡ディレクトリの中身を畳むため取りこぼす)②前景タイムアウトを超える単位は依頼文でバックグラウンド実行と完了検知を扱う必要がある ③「レビューが独立に見つけるか」を試す項目を、レビュー担当が読むファイルに置いてはならない ④触れてよいパスをファイル単位で切ると、値の置き場所まで歪む(4回発生)⑤走行中のsubagentの中間成果がcommitに巻き込まれた | `docs/ai/reviews/incident_auto_capture_step2/progress.md` A-4 / A-5 / A-6 / A-7 / A-12 |
| **通知抑止の既定を反転させるか**(`--check` 実行時は既定で抑止する等) | `roles/common_slack/tasks/notify.yml` は `tester_mode` / `skip_notifications` が真のときだけ送信を抑止し、**どちらも既定は偽 — 渡し忘れ・抑止手段の選択を誤ると本番Slackへ出る**。`--check` の有無は判定に入っていない。**Testerの検証が本番Slackへ到達した事象は3回目**(2026-07-26 / 07-29 / 08-01)。`roles/common_slack` の全利用箇所へ波及するためIncident対応では即断せず案件として扱う。**この行は2026-07-29のIncidentが「起票した」と記載していたが実際には存在せず、2026-08-01に追加した**(同日の別Incidentでも同じ欠落が起きている) | `docs/ai/memory/incidents/2026-07-29_tester-slack-notify-misfire.md`「修正内容」、`.../2026-08-01_tester-slack-decoy-did-not-contain-request.md` |
| **Lesson昇格 2件** | ①**decoyは「対象モジュールが実際にどう宛先を決めるか」を確かめない限り成立していると仮定してはならない。実例が2つ揃った** — `ansible.posix.synchronize` は `C.LOCALHOST` を特別扱いして黙ってローカル実行に落ちる(A-3)、`community.general.slack` は token のURL形状を無視し `domain` 未指定なら常に `hooks.slack.com` へ組み立てる(2026-08-01) ②subagentがharnessのブロックを迂回せず報告した**成功例** — `permission-boundaries-must-be-designed-not-prompted.md` は逸脱例しか持っていない | 同 A-3 / A-8、`docs/ai/memory/incidents/2026-08-01_tester-slack-decoy-did-not-contain-request.md` |
| `skills/requirements-analysis/` に索引更新を成果物へ含める | playbookを増やす案件で `playbooks/README.md` の更新を成果物に含めれば、**Auditorの職掌を広げずに**「受入条件の充足」の検査で拾える。**当初はrole索引も対象だったが、`role-map.md` / `playbook-map.md` は2026-07-29に廃止済みで対象は1つに縮小した** | 同 A-11、`docs/ai/context/ansible/repository-overview.md` L7 |
| Operator役の新設 | 現行のRoleは**開発工程しか持たず運用工程が空白**。Incident記録・運用レポートをAIへ委ねる方向。着手時期は未定 | `docs/ai/roles/` に運用工程のRoleが無いこと。Yoshinobu表明(2026-07-26) |
| リポジトリ直下 `AGENTS.md` の要否判断 | Codexが開発工程から外れ、このファイルを読む主体が存在しない。**そこを開く動機を持つ人がいない**ため起票だけをここに置く | `AGENTS.md` L7 |

## Next(着手候補) — システム・運用

| 項目 | 内容 | 根拠 |
|---|---|---|
| **`playbooks/README.md` と現物の突合を機械的検査にする** | **索引ズレ自体は2026-08-01に解消した**(未記載2本の追加と、**安全区分が食い違っていた12本**の修正)。12本はすべて2026-07-31の `--check` 意味統一Round 2で `risk-accepted` → `check-mode-native` へ変換した際にREADMEが取り残されたもので、**案件のクローズ時にもAuditorにも捕まらなかった**。残る作業は検査の実装で、**「未記載が無いこと」だけでなく「安全区分がplaybookヘッダと一致すること」まで比較する必要がある** — 今回のドリフトは全件記載済みの状態で起きた。`scripts/check-tester-gate.sh` の兄弟として書く。**人の記憶にも工程にも依存しない形が、この欠陥クラスへの最も確実な対処である**(文章の教訓では止まらなかった実績がある) | `docs/ai/reviews/incident_auto_capture_step2/progress.md` A-10、`docs/ai/reviews/incident_investigation_notify/2026-08-01_004_test_result.md` |
| **月次評価に一次調査の成果物を読ませる**(R13) | 月次評価のprompt(`roles/knowledge_review/templates/incident-review-prompt.md.j2`)は `_investigations/` を読まない。一次調査が付いていないバンドルや、拾われないまま滞留している調査結果の指摘(IC-021)が働かない。**見送った理由(成果物の実物が1件も無い)は解消した** — 2026-08-01時点で10件ある。**次回の月次は2026-08-26** | `docs/ai/reviews/incident_auto_investigation/2026-07-31_001_requirement.md` §5 R13 |
| **一次調査成果物の保持期間と、滞留の検知** | `_investigations/` は消す仕組みを持たず、拾われないまま溜まった成果物を知る経路も無い(IC-021の一次調査への適用)。**Policy §8が「未決」として明示している項目のうち、一次調査が本番稼働に入ったことで実際に効き始めた2件**である。バンドル本体は `incident_capture_retention_days`(30日)で消えるため、成果物だけが残り続ける | `docs/ai/policies/incident_capture_policy.md` §8 |
| 障害捕捉 Step 1 の残件2件 | ①**R8(Semaphore外ジョブの保険)が未実装** ②シェルとPythonで staged mode 取得を**二重実装**している負債。**置き場が他に無いためここに持つ**(規律1の例外) | `docs/ai/reviews/incident_auto_capture/` |
| **Codexの調査面を広げ、SSH鍵配布を縮小する**(方向。着手時期未定) | `homelab-investigate-*` がSSHで取る情報のうち**ログ系は既にLokiへ集約済み**で、`loki-count` / `loki-window` が**鍵を使わない調査経路の実例**になっている。残るのは①リアルタイムの現在値②復旧アクション。②はSemaphoreテンプレート経由へ寄せれば鍵は3本から実質1本へ減るが、境界が forced command から「どのテンプレートを起動できるか」へ移るため新しい面のゲートが要る。**ターゲット側のforced commandは、execpolicyが防御層から外れた現在いちばん硬く効いている層**であり、「無くす」ではなく「同じ強さへ置き換える」形にしないと実質的な防御が下がる | `roles/recovery_exec/defaults/main.yml`、`docs/ai/memory/incidents/2026-07-31_codex-execpolicy-allowlist-not-enforcing.md` |
| **global pauseの解除忘れを構造で防ぐ**(TTL付与、または未解除の定期通知) | `homelab-monitoring-pause` はTTLを持たず、未解除を知らせる経路も無い。2026-07-21から**8日間**自律復旧が全target無効のまま誰も気づかなかった。どちらの方式を採るかは設計判断を含むため案件として扱う | `docs/ai/memory/incidents/2026-07-29_global-monitoring-pause-left-on-8-days.md` |
| 時刻表記JST規約をrepoへ明文化 | 規約本体がCoordinatorのauto-memoryにあり、repo内は `autonomous_recovery_policy.md` L174(通知文言の1行)のみ。Implementerが従うべき規約なのでrepo側が正本であるべき。**障害バンドルがSemaphoreのUTCとreportsのJSTを混在させる** | `grep -rn "JST" docs/` が通知文言1件のみ |
| `proxmox_snapshot_check` の時刻が**コントローラの暗黙システムTZに依存**している | `roles/proxmox_snapshot_check/tasks/main.yml:57` の `strftime` はJinjaの既定(`utc=False`)を使うため、ansyのシステムTZが変わると出力もずれる。repo内で唯一このクラス。**急がない、かつ安易に直すと悪化する** — `%z` が実オフセットを出すので**TZが変わっても嘘にはならない**。`+09:00` の直書きは UTC の値に JST ラベルを付ける「詐称」になる | `docs/ai/reviews/ubuntu_nightly_reboot_check/2026-07-30_004_review_jst_sweep.md` |
| **reboot後のpost-check待ち時間をPolicyに規定するか** | `retries: 12` / `delay: 10` と `wait_for timeout: 120` は**実装判断のみで、Policyに根拠が無い**(UV系・TS系・AR系のいずれにも規定なし)。値そのものは実測に対し6倍の余裕があり急がないが、次に同種のチェックを足す人が拠るものが無い | `docs/ai/reviews/ubuntu_nightly_reboot_check/2026-07-30_002_policy_review.md` |
| **`roles/proxmox_exec_node` のT1 assertが`--limit`を拒否する** | 同roleのT1は厳密一致であり、呼び出し側5本は`--limit`付きで実行できない。**新設した`roles/proxmox_reachable_nodes`では同じassertが実際に回帰を生み、部分集合へ緩めた**。exec_node側で`--limit`が許容されるべきかはPolicyを見ないと言えず、独立した確認を要する | `docs/ai/adr/008-proxmox-readonly-check-unreachable-node.md` Consequences |
| **`proxmox_patch_dryrun`のinline機構を`proxmox_reachable_nodes`へ寄せ替える** | 同一機構が2つ並存している既知の負債。寄せ替えると副産物として上のWatch「fact cachingが無効か」がrepo側で塞がる(roleは`ping` probeで判定するため)。外した理由は、weekly full chainのapply gateが実データで未観測の段階で作り直すと回帰の切り分けができないこと | `docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_001_requirement.md` §5 P1 |
| `proxmox_hw_check.yml`がSB-020の安全度表に無い | Policy側の記載漏れ。`proxmox_healthcheck.yml`は表にあるが`proxmox_hw_check.yml`は入っておらず、safe分類の根拠がplaybook冒頭の`tester-gate`コメントにしかない | `docs/ai/policies/proxmox_patch_policy.md` §3.1 |
| **UV-011と汎用healthcheckの食い違い** | `ubuntu_vm_patch_policy.md` UV-011 は「`ansy`は方針2とし、rebootをunattended-upgradesに任せ、**Ansible healthcheckの対象にしない**」と定めるが、`roles/ubuntu_vm_full_upgrade/tasks/healthcheck.yml` の汎用checkは `['ansy', 'quory']` を対象にしている。**2026-08-01の修正が持ち込んだものではなく既存**。UV-011が禁じているのが「専用healthcheck playbookの対象にしない」なのか「あらゆるhealthcheckの対象にしない」なのかはPolicy本文から決められず、**解釈と改訂はYoshinobuの領域**。実装側のコメントは「ansy/quoryには専用healthcheck roleが無いので最小限の汎用checkを置いた」と実装者判断であることを明示している | `docs/ai/reviews/ubuntu_upgrade_healthcheck_scope/2026-08-01_004_audit.md`(Coordinatorが現物で照合) |
| `docs/ai/context-classification.md` の `## 6.` 重複 | `## 6.` で始まる節が2つあり、節番号で参照すると誤った節へ着地する | 同ファイルの現物 |
| **規範文書間の突合を定期的に自動でかける仕組みの要否** | Auditorは案件クローズ時にしか起動しないため、案件が動いていない期間の規範ドリフトは拾えない。2026-07-29のCoordinator自己レビューで6件超の欠陥が見つかったが、これは人間が明示的に求めた1回限りの検出であり再発防止の仕組みではない。月次Knowledge振り返りの拡張が候補 | `docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md` §4 |

## 載せていないもの(判断の記録)

規律2により意図的に載せていない。**やらないと決めたもの**もここに置く。再度提案しようとしたときのために理由を残す。

- **調査結果を入力とする修正依頼の自動起票(R15)** — 2026-08-01、Yoshinobuが**やらない**と決定した。
- **収集器へ「消費済みidの記憶」防御を入れること** — 見送った。「消費済み」の正本は「spoolファイルが存在しないこと」の1つのみであり、state.jsonへの二重化は**両者が食い違う新しい欠陥クラス**を生む。検出は `collection_errors` + exit 2 + systemd `failed` で効いている。一次記録は `.../incident_auto_capture/2026-07-28_018_acl_mask_plan.md` D7。
- **ACL付きパスへのchmodをpre-commitで検査すること** — 見送った。**検査対象がパス変数の解決を要する**ため、パス文字列のgrepでは現に壊れている箇所を1件も拾えないことが実証済み。**効かない検査は「掃引済み」という誤った安心を生む。** 同上 D9。
- **一次調査のAC5(封じ込め)の負経路の実行検証** — 「`incident-inspect` が復旧系コマンドへ到達できない」ことは、①recover系wrapperが鍵パスを直書きしていること ②鍵が `0600 recovery-exec` ③親ディレクトリが `0750 recovery-exec` ④当該ユーザーがそのグループに属さないこと、の4点で**構造的に決まる**(2026-07-31にquory実機で全点を観測)。これは時間ではなく**変更**によってしか崩れないため、守る場所は `roles/incident_inspect/tasks/main.yml` 冒頭のコメントである。
- **proxmox_patch_dryrun / proxmox_exec_node_selection の「両ノード同時到達不能」の実地検証** — いずれもpve2の停止が必要で許可範囲外。decoyでは独立にPASSしており、残存リスクとして各案件のtest_resultに記録済み。**同型の2件が別々の案件で同じ理由により未検証である**ことを、次にこの制約へ当たったときの判断材料として残す。
- **既知条件由来の捕捉が全体に占める割合(実測値)** — `docs/ai/policies/incident_capture_policy.md` IC-022 が正本。規律4により値をここへ写さない。
- **quoryの作業ツリー同期(`git pull`)の自動化** — 2026-07-29に検討し**見送った**(Yoshinobu判断)。手打ちで残すこと自体が制御である: playbook化するとAIから実行可能になり、Slack(`recovery_io` → Codex)へ載せると露出面が増える。**現状は「漏洩してもCodex経由では破壊的作業ができない」状態にあり、利便性と引き換えにこれを崩さない。摩擦は理由にならない。再提案しないこと。** 受け入れている残存リスクは「quoryのcheckoutが古いまま、ラダー系playbookが旧コードで走る」ことである。
