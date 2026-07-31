# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)はここに書かない。対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。

## このファイルの規律

1. **状態は「使う場所」へ書くのが第一選択。** コード・Policy・Contextの当該箇所に書けば、そこを変更する人の目に必ず入る(例: `roles/recovery_probe/defaults/main.yml` の `recovery_probe_pve_host`)。**ここへ載せるのは置き場が他に無い状態だけ** — 将来の日付やイベント待ち、複数箇所にまたがるもの。
2. **Watchの各行に検証手段を必須とする。** 書けない項目は載せず、残存リスクとして一次記録へ残し、「載せていないもの」へ1行残す。Nextは検証手段の代わりに**根拠**を必須とする。
3. **完了したら行を消す。** 履歴は `git log` が持つ。積み増すとこのファイル自身が「いちばん古いのに確実に読まれる層」になる(`docs/ai/memory/lessons/always-loaded-summaries-are-the-least-current.md`)。
4. **値を二重に持たない。** 他に正本があるものは参照だけ書く。
5. **更新のトリガは3つ** — 完了した / 方針を変えた / 観測待ちが増えた。

**このファイルも古くなりうる。** 3トリガはCoordinatorセッションを経由しない変化(Yoshinobuの手作業、外部システムの変化)を拾えず、補いは①案件やレビューの過程で気づいたらその場で消す②月次Knowledge振り返りが現物と突き合わせる、の2つで周期は最長1か月ある。**各行は「主張」ではなく「検証手段つきの申し送り」として読み、判断に使う前に検証手段の側を確かめること。**

`skills/goal-tracking/SKILL.md` の Now / Next / Later とは軸が違う(あちらは優先度軸、ここの Watch は時間・イベント軸)。優先度の議論が要る項目は Next に置く。

## Now(進行中)

**進行中の案件は無い。**

**「`--check` の意味の一本化」は2026-07-31にクローズした(Auditor条件付き受入、指摘2件は反映済み)。** `--check` が `check-mode-native` では「シミュレート」、`risk-accepted` では `check_mode: false` により「本適用」を意味していた多重定義を解消した。Round 1で `risk-accepted` を `--check` で**停止**させ、通知抑止の判定を `notify.yml` へ集約。Round 2で分類棚卸しを行い、**TS-009の条件2を満たすのは3本だけ**と判明したため残り14本を `check-mode-native` へ変換した(A/B-1/B-2/Cの4バッチ、各バッチで独立レビューとTester検証)。規範の正本は `docs/ai/policies/ansible_test_safety_policy.md` **TS-030〜TS-036**、案件記録は `docs/ai/reviews/check_mode_semantics/`(001〜022)。**未検証のまま残した項目はすべて下のWatchが持つ。**

**この案件で判明した重い事実**: `recovery_exec_setup` の `authorized_keys` 配布taskは、2026-07-08にquoryで3日間の本番SSH障害を起こした当のtaskである。同playbookが `risk-accepted` の根拠として掲げていた「影響は軽微・自己完結」はこの実績と矛盾していた。**条件1だけで分類してよいことにすると、こういう齟齬が検出されないまま残る** — 変換後は `check-mode-native` であり、`--check` は本物のdry-runとして機能する。

**「Codexのexecpolicy allowlistが境界として機能していない」Incidentは2026-07-31にクローズした。** 実測で、config.tomlに `[execpolicy]` というキーがそもそも存在せず(実体はStarlarkの`.rules`)、`.rules`へ移してもallowlistは表現できない(catch-allが書けず、未一致コマンドはdecisionが付かずに通る。`codex exec`には承認系フラグが1つも無い)ことが確定した。方針は**「能力の不在へ一本化、execpolicyの復活は追わない」**(Yoshinobu決定)。死んだ`[execpolicy]`テーブルを`recovery_exec`/`incident_inspect`両方から削除し、AR-069/071/073を改訂・AR-102を新設、ADR-009も追随、commit `45a3b5e` で確定、quoryへ配備・再実行で `changed=0` を確認済み。**境界の再建は新規案件を立てず、下のNext「Codexの調査面を広げ、SSH鍵配布を縮小する」が本体である。** 正本は `docs/ai/memory/incidents/2026-07-31_codex-execpolicy-allowlist-not-enforcing.md`(`codex execpolicy check` という決定論的な検証手段もそこに記載)。

**「障害の一次調査の自動化」は2026-07-31にクローズし、本番稼働に入った。** Semaphoreジョブが失敗すると、callbackが要求をキューへ入れ、quoryの毎分timerが証拠バンドルの到着を待って調査専用ユーザー `incident-inspect` のCodexを起動し、一次情報を `reports/incidents/_investigations/semaphore-<id>.{json,md}` へ書く。毎時 :07 の同期でansyへ渡る。**Codexの出力は一次情報であって原因の確定ではない**(真因の特定と修正の著述は開発側、正本は `docs/ai/core.md`「開発と運用の分離」)。規範は `docs/ai/policies/incident_capture_policy.md` **§3.5(IC-034〜IC-042)**、設計は `docs/ai/adr/009`(**Accepted**)、案件記録は `docs/ai/reviews/incident_auto_investigation/`(001〜008)。**実発火の観測2件はWatchが持つ。** この案件から派生したIncident 2件は、execpolicyの方が上記のとおりクローズ、`--check` の意味の多重定義はRound 1で解消し残るRound 2を上のNow #1が持つ。

**「Grafanaダッシュボード/アラートのrepo正本化」は2026-07-30にクローズした。** Step 1・2・3すべて配備・検証済み、Auditor条件付き受入の2件も反映済み。規範の正本は `docs/ai/policies/log_observability_policy.md` **v4.0**(LOG-078〜LOG-089)、設計判断は `docs/ai/adr/007-grafana-provisioning-as-code.md`(**Accepted**)、調整手順は `docs/ai/context/operations/grafana-alerting-tuning.md`、案件記録は `docs/ai/reviews/grafana_provisioning/`(001〜018)。**Watchへ回していたAC4(実発火時の通知本文)は2026-07-31に観測してPASS**、Watch行は削除した — 観測の一次記録は `docs/ai/reviews/grafana_provisioning/2026-07-31_018_ac4_observation.md`。**この案件は残件なしで完全にクローズした。**

それ以前の案件は2026-07-29時点ですべてクローズ済みである。「Proxmox実行ノード選定の共通化」は commit `beff0f5` / push / quory への配備まで完了してクローズした(判断の正本は `docs/ai/adr/006-proxmox-exec-node-selection.md`、案件記録は `docs/ai/reviews/proxmox_exec_node_selection/`)。**pve1が起動している時にしか確かめられないAC4(`proxmox_backup_restore_verify`側)だけがWatchに残る。**「障害の自動捕捉・評価」も**3段すべてが本番で成立してクローズ済み** — 捕捉=quory(5分毎)、転送=ansy `ansible-incident-sync.timer`(毎時)、評価=既存の月次 `ansible-knowledge-review.timer` の中の2本目の `claude -p`。**次の観測点は2026-08-26の月次発火**で、Watch行が持つ。

**規範の正本は `docs/ai/policies/incident_capture_policy.md`**(IC-001〜IC-033)。設計判断は `docs/ai/adr/003` / `004` / `005`(いずれも Accepted)。案件記録は `docs/ai/reviews/incident_auto_capture/`(Step 1)と `.../incident_auto_capture_step2/`(Step 2)。**未決の一覧は Policy §8 が正本。**

**Step 1の残件2つは、使う場所へ書かず現状ここにしか無い**(規律1の例外として明示する)。①**R8(Semaphore外ジョブの保険)が未実装** ②シェルとPythonで staged mode 取得を**二重実装**している負債。一次記録は `docs/ai/reviews/incident_auto_capture/`。

## Watch(観測待ち)

**将来の時点でしか確かめられないこと**を置く。着手すべき作業ではない。

| 項目 | 発火条件 | 検証手段 | 一次記録 | 最終確認 |
|---|---|---|---|---|
| quoryの作業ツリーを**Testerが直接確認できない** | quoryの作業ツリー状態を検証したいとき | Tester接続identity(`ann`)と所有者(`yoshi`)が異なり `dubious ownership` が `rc=128` で拒否する。回避には `safe.directory` が要り承認範囲外。**AC6のquory側継続確認が原理的に盲目**。2026-07-28にも再発 | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md`、`.../incident_auto_capture_step2/2026-07-28_004_quory_units_survey.md` | 2026-07-28 |
| 月次Knowledge振り返りの**初回無人実行**。2026-07-28以降は**障害評価(2本目の `claude -p`)を含む** | 毎月26日(期日の正本はauto-memory `MEMORY.md` 先頭行。ここへ写さない) | ansyで `systemctl list-timers ansible-knowledge-review.timer` と `journalctl -u ansible-knowledge-review`。実行後は作業ツリーに未commit差分が出る。**障害評価の成果物は `reports/incidents/_evaluations/` に出る(gitignore済みなので差分には現れない)。** 手動での通しは2026-07-28に成功済み | `roles/knowledge_review/`、`docs/ai/memory-classification.md`、`docs/ai/reviews/incident_auto_capture_step2/2026-07-28_020_u11_test_result.md` | 2026-07-28 |
| **中止した月次評価の再実行は人が行う**(IC-033) | 月次が `ABORTED_DIRTY` で中止したとき | Slackへwarningが飛び、本文が再実行手順を案内する。**commitで作業ツリーを清潔にしてから `systemctl start ansible-knowledge-review.service`**。中止は喪失でなく遅延に留まる(ミラーは削除されず、評価はcatch-up型) | `docs/ai/policies/incident_capture_policy.md` §7 IC-033 | 2026-07-28 |
| weekly full patchの**apply gateを実データで通す**(AC5) | Proxmox dry-runが `PATCH_READY` を返す週 | `playbooks/proxmox_patch_weekly_full.yml` L159-188。`_dryrun_missing_nodes` が実データで空になること。現状の根拠はdecoy検証のみ | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L426 | 2026-07-27 |
| Reviewer / Testerの **effort=medium 試行** | 次に逐行照合を伴うレビュー・検証を回すとき | findings品質(逐行照合の取りこぼし)が落ちていないか。落ちていれば `.claude/agents/reviewer.md` / `tester.md` の `effort:` を `high` へ戻す | `docs/ai/role-routing-index.md`「モデル・effort配分」 | 2026-07-27 |
| Alloy **Phase 3(異常値のFire)** | Lokiにログが十分蓄積した時点 | requirementは作成済み。Grafana Exploreで対象シグネチャの出現頻度を見て閾値を決める | `docs/ai/reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md` | 2026-07-27 |
| Proxmoxパッチ自動チェーンの **実発火の観測** | パッチ件数が少なく手動介入が要らない週末 | 自動チェーンが最後まで通ったログ。過去2回(07-11/12、07-18/19)は大量パッチで手動対応となり未観測 | `docs/ai/reviews/tester_mode/`、`docs/ai/context/operations/proxmox-patch.md` | 2026-07-27 |
| Context陳腐化チェック追加後の**`knowledge_review_timeout`(1800秒)が足りるか** | 次回2026-08-26の月次実行 | `journalctl -u ansible-knowledge-review`でタイムアウト終了していないか確認。Testerのdecoy見積もりでは余裕が無い可能性が高いとされた(実測はデータが無く不可) | `docs/ai/reviews/knowledge_review_context_check/2026-07-29_005_u1_test_result.md` | 2026-07-29 |
| ubuntu_nightly の **monnie / authy リブート経路が実機で通るか** | 次に各ホストの `reboot_required` が true になる夜(`meta: end_host` により、不要な夜はこの経路に入らない)。**monnie側は決定論的な欠陥だったため、`reboot_required=true`の夜は毎回失敗していた**(発生日と回数は一次記録が正本。ここへ写さない) | `[ubuntu_nightly] OK - monnie` / `authy` がinfoへ飛ぶこと。失敗した場合は本文に**失敗タスク名と理由**が入っていること(固定文言でないこと)。**authy側(`until`/`retries`追加、commit `3fbb9e8`)は実機検証を経ずに本番投入している** — decoy検証のみ | `docs/ai/memory/incidents/2026-07-30_ubuntu-nightly-monnie-external-port-wait.md`、`docs/ai/reviews/ubuntu_nightly_reboot_check/` | 2026-07-30 |
| **pve1が起動している時にしか確かめられない2件**(AC4 / unifi #4) | pve1が起動している時間帯(週末のパッチ運用が自然) | ①`playbooks/proxmox_backup_restore_verify.yml` を本実行し、対象VMの `prefer<node>` タグどおりのノードでrestoreされ、レポートJSONの `restore_node_fallback` が **false** になること ②`playbooks/unifi_backup_fetch.yml` の Play 1 が両系到達可能時に **pve1** を選ぶこと。**①②とも共通role `proxmox_exec_node` の同じ分岐**であり、decoyでは両方PASS済み | `docs/ai/reviews/proxmox_exec_node_selection/2026-07-29_007_test_result_step1.md`、`docs/ai/reviews/unifi_backup_fetch/2026-07-25_013_test_result.md` L114 | 2026-07-29 |
| **pve1停止中のread-only点検3本がSemaphoreで緑になるか**(本案件の目的の達成確認) | commit / push とquoryでの`git pull --ff-only`の**後**の平日発火(healthcheck 05:40 JST / hw_check 05:45 JST 毎日、snapshot_check 木18:00 JST。Semaphore保存値はUTCで20:40 / 20:45 / 木09:00) | `homelab-semaphore-query recent-failed`にこの3本が現れなくなること、かつSemaphore summaryに`Result=OK \| Unchecked=pve1`が出ていること。**ansyからの実機実測ではrc=0・`Unchecked=pve1`まで確認済み**で、残るのはquory上の本番経路(Gitから取得したコードで走ること)だけである | `docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_006_test_result.md` | 2026-07-30 |
| **両ノード到達可能時の回帰**(AC5 / AC7の実ホスト分) | pve1が起動している時間帯(週末のパッチ運用が自然) | 3本のsummaryに`Unchecked=`が**出ない**こと、rc=0であること。両ノードの行が従来どおり並ぶこと。decoyとテンプレート描画では確認済みで、実ホスト両ノードでの確認だけが残る | 同上 §5・§7 | 2026-07-30 |
| **一次調査の callback が実Semaphore経路で発火するか**(OQ2の決着) | 次にSemaphoreジョブが失敗したとき | quoryの `/var/lib/homelab-recovery/incident-investigate/queue` に要求ファイルが現れること。**現れなければリポジトリ直下の `ansible.cfg` がSemaphore実行に効いていない**ことになり、Semaphore側の環境設定(`ANSIBLE_CALLBACK_PLUGINS` / `ANSIBLE_CALLBACKS_ENABLED`)をYoshinobuがUIで足す必要がある。U0では確定できなかった(確認用DBクエリがharnessにブロックされた) | `docs/ai/reviews/incident_auto_investigation/2026-07-31_005_u2_implement.md`、同 `_002_u0_test_result.md` M2 | 2026-07-31 |
| **調査失敗時に `systemctl is-failed` が `failed` を返すか**(AC6の実unit経路) | 実際に調査が失敗したとき(LLM呼び出しの失敗・タイムアウト等) | `systemctl is-failed homelab-incident-investigate.service` が `failed` を返し、かつ `_investigations/` に `status: failed` の成果物が残っていること。**Tester検証では実unit経路の再現がharnessにブロックされ、`/tmp` に複製した設定で本体スクリプトを直接動かす形に留まった**(成果物側の `status: failed` は実測済み)。`SuccessExitStatus=75` により正常なskipは `failed` にならない | `docs/ai/reviews/incident_auto_investigation/2026-07-31_007_test_result.md` | 2026-07-31 |
| **`proxmox_backup_restore_verify` Play 3 の停止assertが実行検証できない** | 検証手段が無い(下記)。**Playの構造を変えたときに再考する** | **`--check` で観測する経路が原理的に存在しない** — Play 2 の停止assertが先に失敗して run 全体が止まるため、Play 3 へ到達しない。したがってこのassertは「Play 2 の機構が将来壊れた/playが並べ替えられた場合」に効く多重防御であり、**現時点では静的な存在確認しかできない**(TS-030 は変更を行う各playへの設置を求めるため、字義を満たす目的で置いた)。Play の順序・`add_host` の構造・Play 2 のassertを変更する人は、Play 3 側が唯一の防波堤になることを踏まえること | `docs/ai/reviews/check_mode_semantics/2026-07-31_022_audit.md` 指摘#2、`playbooks/proxmox_backup_restore_verify.yml` L228-237 | 2026-07-31 |
| **変換した14本の AC2(通常実行の不変)が未検証**(Round 2の唯一の穴) | 各playbookが次に**`--check` なしで**通常実行されるとき。`cert_renew` は2026-08-02〜03の週末に本番でまとめて回す予定(2026-07-31 Yoshinobu) | 追加した `when: not ansible_check_mode` は既存条件への**AND追加**であり通常実行時は `False` なので影響しない、というのが根拠だが**静的読解のみで実行検証していない**(Tester役は `--check` なし実行を禁じられている)。壊れている場合の出方は「本来走るべきtaskがskipされる」で、**playbookのサマリとSlack通知に出る**。証明書が更新されない / unitが配置されない / ユーザーが作られない等。異常があれば `docs/ai/reviews/check_mode_semantics/` の該当バッチのdiffを見る | `docs/ai/reviews/check_mode_semantics/` 009 / 012 / 015 / 018 / 019(各test_resultのAC2欄はいずれも「契約により未実行」) | 2026-07-31 |
| **`cert_renew` の ansy / proxmox / monnie play が `--check` で未到達** | 上と同じ週末の本番実行、または誰かがquory上で `--check` を回したとき | Tester接続identity(`ann`)がこれらのホストへのSSH認証情報を持たないため到達できなかった。**鍵の読み取りやsudoでのidentity昇格は試みずに停止**している(2026-07-31)。quory上の `localhost` / `quory` play では rc=0・破壊的task全skip・CA証明書のmtime不変まで確認済み | `docs/ai/reviews/check_mode_semantics/2026-07-31_019_round2_batchC_quory_test_result.md` | 2026-07-31 |
| **Semaphoreの定期ジョブが `risk-accepted` へ `--check` を渡していないか**(commit `3bf9894` の直接の帰結) | 次に各定期ジョブが発火したとき | 渡していればそのジョブが **rc=2 で赤くなる**(TS-030の停止assert)。Semaphore UIの失敗、または障害捕捉パイプラインが `reports/incidents/` にバンドルを作ることで判明する。**Semaphoreの設定はrepo外でAIから確認できないため、事前確認ではなく発火で検出する設計を選んだ**(2026-07-31、requirement §7 OQ3)。赤が出た場合の正しい対処は、assertを外すことではなく**そのジョブから `--check` を外すこと** | `docs/ai/reviews/check_mode_semantics/2026-07-31_001_requirement.md` §7 OQ3、`docs/ai/policies/ansible_test_safety_policy.md` TS-030 | 2026-07-31 |
| Semaphore実行環境で **fact caching が無効か**(Q1) | Yoshinobuが Semaphore UI を開いたとき | Semaphoreのジョブ/テンプレート設定に `ANSIBLE_CACHE_PLUGIN` / `ANSIBLE_GATHERING` が注入されていないこと。**有効だと `proxmox_patch_dryrun` が停止中のノードをキャッシュ済みfactsから「到達可能」と誤判定する**(2026-07-26にReviewerが再現済み)。**repo外のためAIからは確認できない。** 新設の `roles/proxmox_exec_node` は明示的な `ping` で判定するため影響を受けず、残る影響は `proxmox_patch_dryrun` 1箇所のみ | `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` §14-5 a、`docs/ai/adr/006-proxmox-exec-node-selection.md` | 2026-07-29 |

## Next(着手候補) — 工程・体制

**2026-07-31、Yoshinobu指示によりTierの概念を廃止し、規範文書の簡素化を完了した。** どこまで分解し誰へ委任するかはCoordinatorの裁量である。`docs/ai/core.md` / `docs/ai/role-routing-index.md` / `CLAUDE.md` / `docs/ai/roles/*.md` / `skills/` すべて反映済みで、`skills/delegation-tier/` は削除した。**残っているTierの語は `docs/ai/reviews/` / `docs/ai/memory/` の過去記録だけ**(当時の事実の記述であり書き換えない)。見積もり実績の記帳先だった `docs/ai/effort-baseline.md` はYoshinobu判断で削除した(履歴は`git log`が持つ)。

| 項目 | 内容 | 根拠 |
|---|---|---|
| 案件の申し送り(上記2件以外) | decoy定型がモジュールによっては成立しない件のLesson昇格、`requirements-analysis` への索引更新の追加、subagentのscratch漏れ対策ほか**計12件**。**個別にここへ写さない** | `docs/ai/reviews/incident_auto_capture_step2/progress.md`「後続への申し送り」 |
| Operator役の新設 | 現行6役は**開発工程しか持たず運用工程が空白**。Incident記録・運用レポートをAIへ委ねる方向。着手時期は未定 | `docs/ai/roles/` に運用工程のRoleが無いこと。Yoshinobu表明(2026-07-26) |
| リポジトリ直下 `AGENTS.md` の要否判断 | Codexが開発工程から外れ、このファイルを読む主体が存在しない。**そこを開く動機を持つ人がいない**ため起票だけをここに置く | `AGENTS.md` L7 |

## Next(着手候補) — システム・運用

| 項目 | 内容 | 根拠 |
|---|---|---|
| **月次評価に一次調査の成果物を読ませる**(requirement R13。**本ラウンドで意図的に見送った**) | 月次評価の prompt(`roles/knowledge_review/templates/incident-review-prompt.md.j2`)は `_investigations/` を読まない。一次調査が付いていないバンドルや、拾われないまま滞留している調査結果の指摘(IC-021)が働かない。**見送った理由は、成果物の実物がまだ1件も蓄積しておらず、何を指摘させるべきかを決める材料が無いこと。** 次回の月次(2026-08-26)までに実データが溜まる | `docs/ai/reviews/incident_auto_investigation/2026-07-31_001_requirement.md` §5 R13、同 `_008_audit.md` |
| **Codexの調査面を広げ、SSH鍵配布を縮小する**(方向。着手時期未定。**2026-07-31以降はexecpolicy Incidentの「境界の再建」本体でもある**) | `homelab-investigate-*` がSSHで取る情報のうち**ログ系は既にLokiへ集約済み**で、`loki-count` / `loki-window` が**鍵を使わない調査経路の実例**になっている。残るのは①リアルタイムの現在値(systemctl status・listenポート等)②復旧アクション。②はSemaphoreテンプレート経由へ寄せれば鍵は3本から実質1本(Ansibleのもの)へ減るが、境界が forced command から「どのテンプレートを起動できるか」へ移るため新しい面のゲートが要る。**ターゲット側のforced commandは、execpolicyが防御層から外れた現在いちばん硬く効いている層**であり、「無くす」ではなく「同じ強さへ置き換える」形にしないと実質的な防御が下がる。**Codexの調査面が広がるほど、Claude Codeが本番へ越境する必要も減る**(2026-07-31 Yoshinobu: 現在の越境は調査環境が不十分な間の容認) | `roles/recovery_exec/defaults/main.yml`(鍵3本)、`roles/recovery_exec/templates/AGENTS.md.j2`(Loki経路)、`docs/ai/memory/incidents/2026-07-31_codex-execpolicy-allowlist-not-enforcing.md` |
| **global pauseの解除忘れを構造で防ぐ**(TTL付与、または未解除の定期通知) | `homelab-monitoring-pause` はTTLを持たず、未解除を知らせる経路も無い。2026-07-21から**8日間**自律復旧が全target無効のまま誰も気づかなかった。どちらの方式を採るかは設計判断を含むためIncident対応として即断せず案件として扱う。**この行は2026-07-29のIncidentが「起票した」と記載していたが実際には存在せず、同日に追加した**(規範文書間の突合が効いていなかった実例) | `docs/ai/memory/incidents/2026-07-29_global-monitoring-pause-left-on-8-days.md`「修正内容」 |
| 時刻表記JST規約をrepoへ明文化 | 規約本体がCoordinatorのauto-memoryにあり、repo内は `autonomous_recovery_policy.md` L174(通知文言の1行)のみ。Implementerが従うべき規約なのでrepo側が正本であるべき。**障害バンドルがSemaphoreのUTCとreportsのJSTを混在させる**ため実害が出る前に片付ける | `grep -rn "JST" docs/` が通知文言1件のみ。`docs/ai/memory-classification.md` 第0段 |
| `proxmox_snapshot_check` の時刻が**コントローラの暗黙システムTZに依存**している | `roles/proxmox_snapshot_check/tasks/main.yml:57` の `'%Y-%m-%dT%H:%M:%S%z' \| strftime(...)` はJinja `strftime` の既定(`utc=False` → `time.localtime`)を使うため、ansyのシステムTZが変わると出力もずれる。repo内で唯一このクラス。**ただし急がない、かつ安易に直すと悪化する** — `%z` が実オフセットを出すので**TZが変わっても嘘にはならない**。`+09:00` を直書きすると UTC の値に JST ラベルが付く「詐称」になる(実測: TZ=UTCで `2026-07-29T18:01:23+09:00`)。正しく直すなら `TZ='Asia/Tokyo' date -d @<epoch>` でTZを固定する形だが、ループ内で1件ごとにプロセスを起こす | `docs/ai/reviews/ubuntu_nightly_reboot_check/2026-07-30_004_review_jst_sweep.md` |
| **reboot後のpost-check待ち時間をPolicyに規定するか** | `retries: 12` / `delay: 10`(120秒)と `wait_for timeout: 120` は**実装判断のみで、Policyに根拠が無い**。`ubuntu_vm_patch_policy.md`(UV系)・`ansible_test_safety_policy.md`(TS系)・`autonomous_recovery_policy.md`(AR系)のいずれにも reboot後post-checkの待ち時間・リトライ回数の規定が無いことを事後照合で確認済み。値そのものは実測(freeradius 約20秒)に対し6倍の余裕があり急がないが、次に同種のチェックを足す人が拠るものが無い | `docs/ai/reviews/ubuntu_nightly_reboot_check/2026-07-30_002_policy_review.md` |
| **`roles/proxmox_exec_node` のT1 assertが`--limit`を拒否する** | 同roleのT1は`ansible_play_hosts_all \| sort == groups[...] \| sort`(厳密一致)であり、呼び出し側5本(`unifi_backup_fetch` / `proxmox_backup_restore_verify` / recovery系3本)は`--limit`付きで実行できない。**新設した`roles/proxmox_reachable_nodes`では同じassertが実際に回帰を生み、部分集合へ緩めた**(healthcheckは SB-021 が`--limit`を明示的に許可していた)。exec_node側で`--limit`が許容されるべきかはPolicyを見ないと言えず、独立した確認を要するため今回は触っていない | `docs/ai/adr/008-proxmox-readonly-check-unreachable-node.md` Consequences、`docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_005_review.md` Critical #1 |
| **`proxmox_patch_dryrun`のinline機構を`proxmox_reachable_nodes`へ寄せ替える**(P1-1) | 同一機構が2つ並存している既知の負債。寄せ替えると副産物として上のWatch「fact cachingが無効か(Q1)」がrepo側で塞がる(roleは`ping` probeで判定するため)。今回外したのは、weekly full chainのapply gateが実データで未観測の段階で作り直すと回帰の切り分けができないため | `docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_001_requirement.md` §5 P1、ADR-008 Consequences |
| `proxmox_hw_check.yml`がSB-020の安全度表に無い(P1-2) | Policy側の記載漏れ。`proxmox_healthcheck.yml`は表にあるが`proxmox_hw_check.yml`は入っておらず、safe分類の根拠がplaybook冒頭の`tester-gate`コメントにしかない | `docs/ai/policies/proxmox_patch_policy.md` §3.1、同 requirement §5 P1 |
| `docs/ai/context-classification.md` の `## 6.` 重複 | `## 6.` で始まる節が2つあり、節番号で参照すると誤った節へ着地する | 同ファイルの現物 |
| 収集器へ「消費済みidの記憶」防御を入れるか | 「消費済み」の正本は「spoolファイルが存在しないこと」の1つのみ。state.jsonへの二重化は**両者が食い違う新しい欠陥クラス**を生むため意図的に見送った。検出は `collection_errors` + exit 2 + systemd `failed` で効いている | `.../incident_auto_capture/2026-07-28_018_acl_mask_plan.md` D7 |
| ACL付きパスへのchmodをpre-commitで検査するか | **検査対象がパス変数の解決を要する**ため、パス文字列のgrepでは現に壊れている箇所を1件も拾えないことが実証済み。**効かない検査は「掃引済み」という誤った安心を生む**ため見送った | 同上 D9 |
| **規範文書間の突合を定期的に自動でかける仕組みの要否** | Auditorは案件クローズ時にしか起動しないため、案件が動いていない期間の規範ドリフトは拾えない。2026-07-29、Yoshinobu依頼によるCoordinatorの自己レビューで6件超の欠陥(2026-07-28以降ずっと存在)が見つかったが、これは人間が明示的に求めた1回限りの検出であり、再発防止の仕組みではない。月次Knowledge振り返りの拡張が候補 | `docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md` §4 |

## 載せていないもの(判断の記録)

規律2により意図的に載せていない。再度追加しようとしたときのために理由を残す。

- **一次調査のAC5(封じ込め)の負経路の実行検証** — **Watchに載せない。** 「`incident-inspect` が復旧系コマンドへ到達できない」ことは、①recover系wrapperが鍵パスを直書きしていること ②鍵が `0600 recovery-exec` ③親ディレクトリが `0750 recovery-exec` ④当該ユーザーがそのグループに属さないこと、の4点で**構造的に決まる**(2026-07-31にquory実機で全点を観測)。Watchは「将来の時点でしか確かめられないこと」を置く場所だが、これは時間ではなく**変更**によってしか崩れない。したがって守る場所は `roles/incident_inspect/tasks/main.yml` 冒頭のコメント(4点と、崩す典型的な変更2つを明記)であり、そこを変更する人の目に必ず入る。**Tester検証時にharnessが負経路の実行をブロックしたのは事実だが、実行しても結果は上記4点から動かない。**
- **proxmox_patch_dryrun AC4(両ノード同時到達不能)の実地検証** — pve2の停止が必要で許可範囲外。残存リスクとして `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` L425 に記録済み。
- **proxmox_exec_node_selection AC2(ラダーの両ノード同時到達不能)の実地検証** — 上と同じ理由(pve2の停止が要り許可範囲外)。decoyでは独立にPASSしており、残存リスクとして `docs/ai/reviews/proxmox_exec_node_selection/2026-07-29_007_test_result_step1.md` に記録済み。**同型の2件が別々の案件で同じ理由により未検証である**ことを、次にこの制約へ当たったときの判断材料として残す。
- **pve1の夏季平日シャットダウン運用** — **2026-07-29に申し送りが消滅した。** 実行ノードの決め打ちを共通機構(`roles/proxmox_exec_node`)で除去し、`recovery_probe_pve_host`(暫定でpve2を指していた単数変数)を候補リスト `recovery_probe_pve_hosts` へ置き換えたため、**pve1を平日常時起動へ戻す際にrepoを書き換える作業が無くなった**。判断は `docs/ai/adr/006-proxmox-exec-node-selection.md`。運用そのものの現状は Proxmox のノード状態が正本であり、ここでは持たない。
- **既知条件由来の捕捉が全体に占める割合(実測値)** — `docs/ai/policies/incident_capture_policy.md` IC-022 が正本。規律4により値をここへ写さない。
- **quoryの作業ツリー同期(`git pull`)の自動化** — 2026-07-29に検討し**見送った**(Yoshinobu判断)。手打ちで残すこと自体が制御である: playbook化するとAIから実行可能になり、Slack(`recovery_io` → Codex)へ載せると露出面が増える。**現状は「漏洩してもCodex経由では破壊的作業ができない」状態にあり、利便性と引き換えにこれを崩さない。** 同日3回この摩擦を踏んでいるが(Coordinator / Tester / Yoshinobu)、摩擦は理由にならない。**再提案しないこと。** なお、この判断が受け入れている残存リスクは「quoryのcheckoutが古いまま、ラダー系playbookが旧コードで走る」ことである — `recovery-probe`本体で今日塞いだのと同じ欠陥クラスであり、**検知だけを読み取り専用で持つ案は境界を崩さない**(適用は手打ちのまま)。未着手。
