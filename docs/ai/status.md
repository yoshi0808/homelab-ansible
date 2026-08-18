# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)はここに書かない。対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。

## このファイルの規律

1. **完了したら行を消す。履歴を残そうとしない。** 履歴は `git log` が持つ。
2. **値を二重に持たない。** 他に正本があるものは参照だけ書く。

## Now(進行中)

**観測待ち: 誤りの再発を機械が刻む仕組み(2026-08-18 実装)** — **規範に書いても守れない誤りがあり、それを自己申告でしか検出できていない**という問題への手探り。機械側まで通した。**初回発火は確認した。効いているか(過検出していないか)は分かっていない。**

- **形式は `docs/ai/memory/lessons/` の「再発記録」節**。契約は「**別体**がセッション終了時に transcript を17本の lesson の形と照合し、当たれば1行足す。当たらなければ何もしない」。**判断は「どの形か」だけで「記録すべきか」は問わない**
- **機構は `SessionEnd` hook と `scripts/session-recurrence-record.py`**(`.claude/settings.json` に登録)。決めた3点は①hookは `SessionEnd`、`reason` が `resume` のときだけ対象外とし **`clear` は含める**(この環境では境界の大半が `/clear` のため)②別体は**役を着せない `codex exec` を1回**(Reviewer役は着せない — 「findingsを重大度別に返せ」が過検出へ引くため)③渡すのは user/assistant の本文と `tool_use` の入力のみで **`tool_result` は捨てる**。transcript のパスは codex へ渡さず stdin で流す(境界を依頼文でなく入力経路に置く)
- **異常終了では発火しない。** OOM・SIGKILL・電源断は `shutdown()` を通らず hook が起動しないため、**取りこぼしは沈黙として現れる。対象外とすることをYoshinobuが決めた**(2026-08-18)
- **`/clear` のたびに codex が1回走り、最大120秒待つ。** 待ち時間の上限は `.claude/settings.json` の `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS`
- **同じ日に、現在地の渡り方も直した** — SessionStartで渡る本ファイルが **hookの10,000文字制限で切れていた**(出力16,821文字に対し先頭2,000文字しか届かず、Next表の2行目で切断)。`scripts/session-context.py` で節境界に分割し4エントリ登録した(commit `036649d`)。**分割は成立している** — 2026-08-18のセッション開始で全節が届いた。
- **初回発火を確認した**(2026-08-18、commit `dcb7375`)。lesson 4本へ追記され、**再発記録節が無い lesson への新設経路も通った**。Yoshinobuの評価は「4件のうち2件は解決できる問題ではなく、深刻度も低い」で、**機構はこのまま続ける**と決めた。**残る未確認は過検出の有無だけで、判別にはこの機構を話題にしていないセッションを1回通す必要がある**
- **回数は推定であって測定ではない。** 分類器はLLMで、見落とせば沈黙し過検出すれば水増しする。**回数だけを昇格の根拠にしない**
- **良くなる確証は双方とも持っていない**(Yoshinobu、2026-08-18)。やってみる価値はあるという判断で始めた
- **やめる条件は現段階では定めない**(Yoshinobu、2026-08-18)。Coordinatorが「効かなかったことを観測可能にするため先に決めるべき」と進言し、**現段階では不要と判断された**。再提案しない

## Next(着手候補) — 工程・体制

| 項目 | 内容 | 根拠 |
|---|---|---|
| **`docs/ai/roles/` 5本のプロンプト最適化(継続案件)** | Coordinator / Implementer / Reviewer / Tester / Auditorの各Role文書を、**実際に運用してみて出てきた歪みを持ち寄って協議しながら**直し続ける。対象は①**やること・やらないことの衝突**②**何を言われているのか読み取れない箇所**③**細かく指示するよりAIに任せた方が結果が良い箇所**の3クラス。一度に全部やる案件ではなく、気づいたものを溜めて定期的に議論する形を採る | Yoshinobu表明(2026-08-01)「ある程度最適化して随分良くなってきたが、まだ矛盾・不明瞭・非効率が残る」。**歪みの実例はCoordinatorが運用中に気づいた時点で書き溜める**(置き場は本行) |
| **sandbox を検証環境として使い込む** | **inventory 登録と `serial_getty_mask` は2026-08-06に完了**(`b20c43d`。`NRestarts=20322` の agetty ループを停止、hostname も `ubuntu` から `sandbox` へ)。承認境界でも `monnie` / `ansy` と同じ「確認不要」側にある。**ここから先は使い道の話であって、必須の作業ではない。** Yoshinobu が挙げた候補は ①monnie のサービスの検証 ②**まだAnsibleへ移行していない FreeRADIUS**(`authy`)— ただしクライアント/サーバのテスト用公開鍵を一度置く必要があり、かつ RADIUS は設定をほとんど変えないため**費用対効果は未評価**。**この行の要点は「decoy より広く試せる実ホストが手に入った」ことで、個々の候補ではない。** 監視対象にはしない。`rsyslog_forward_to_monnie` を向けるには allow-list への追加とホストごとの recon が要る(未着手・急がない) | Yoshinobu表明(2026-08-06)。前提・使い方・限界・壊したときの扱いは `docs/ai/context/operations/sandbox-vm.md` が正本 |
| **Reviewerをcodex側へ委ねる — 渡し方の確定** | **agmsgの復活とReviewerの疎通は2026-08-09に完了した。** team `homelab` に `claude`(claude-code)と `reviewer`(codex)が登録され、双方向のmonitor配送が通っている。同日、実案件のレビューを1本流して**成立を確認済み** — commit `3743707` を対象に、`docs/ai/roles/reviewer.md` と `skills/code-review/SKILL.md` を指しただけで型どおりのfindingsが返り、「repoを変更しない」制限も作業ツリーで守られていた。**構成・落とし穴・権限層の正本は `docs/ai/context/operations/agent-messaging.md`**(値をここへ写さない)。Implementer / Auditor は現行のClaude subagentのまま据え置き。<br>**残っているのはTesterの扱いだけである。** codexがrepoへ書き込めることは2026-08-09に実証した — 査読記録4本を `docs/ai/reviews/semaphore_schedules_as_code/` へ直接書かせ、作業ツリーでその1ファイル以外を触っていないことを確認している。<br>**`claude → reviewer` の配送は、再spawn後に成立しないことがある**(同日実測。`delivery.sh status` が `bridge not running`、`history.sh` の既読マークが `●` のまま)。逆向きは通っていた。回避はboot promptか `tmux send-keys` で直接渡すこと。**原因は未特定** — 心当たりは `despawn.sh` が placement record を持たず `tmux kill-pane` で畳んだこと。<br>**Testerの扱いは未確認** — Yoshinobuが「今のまま」と挙げたのはImplementerとAuditorのみ。**`ansible-playbook --syntax-check` はcodex側でも通る**ことを同日実測したので、実行可否は除外理由にならない。判断軸は実ホストへの到達手段の所在である | Yoshinobu決定(2026-08-09)。ペイン構成の意向は「左=implementer、右=ReviewerとTester」(同日、着手は未定) |
| **ansy が monnie へも直接触らなくなる方向**(開発機の新設) | **Phase 4 は monnie への到達を残すが、それは終点ではなく途中段階である。** いずれ ansy の操作対象は本番の monnie ではなく開発機になる。`sandbox-mon`(requirement R19〜R21、D3 で別案件へ切り出し済み)がその受け皿になりうるが、当時の目的は「監視スタックのupgradeリハーサル」であり、**今回示された目的(ansy が本番へ触らないこと)の方が広い**。着手時期は未定 | Yoshinobu表明(2026-08-03、Phase 4 の D9 を決めた文脈)。`docs/ai/reviews/dev_prod_boundary/2026-08-03_015_plan_phase4.md` §3.1 |

## Next(着手候補) — システム・運用

| 項目 | 内容 | 根拠 |
|---|---|---|
| **Operator Request Channel の後続2件** | MVPは2026-08-09にクローズ。**残存リスク4件と設計上の申し送りは `docs/ai/reviews/operator_request_channel/2026-08-09_018_closeout.md` §4 が正本**(quory側ライブラリのhash照合手段が無いこと、checkpoint 4のreject方向が原理的に検証不能なこと、spoolに試験messageが4件残ること、**書き込みの門をPOSIX ACLだけと仮定していたこと**)。後続は①**ID専用の通知**(本文はDLP経路だけ、通知は `request_id` しか運ばない) ②**storeの簡素化**(容量会計・イベントログ・conversation索引)。②はquory側Operatorが「一定期間使ってから判断」としていた。**実バグ4件はいずれもstoreと権限の層で、DLPでは1件も出ていない** — 芯と帳簿の切り分けが実測で裏づいた形であり、②の設計入力になる | Yoshinobu決定(2026-08-09にクローズ)。案件記録は `docs/ai/reviews/operator_request_channel/` |
| **証明書の更新が、週次・期限駆動で実際に回るか** | **repo・Semaphore とも配備完了**(2026-08-06)。カタログの `force_renew` 既定値は `false` へ変更し reconcile 済み(`changed: cert_renew` を確認)、`cert_renew_quory.timer` は `Persistent=true` で quory に入り(`unit-cat` で実測)、`cert_renew.yml` の schedule も Yoshinobu が週次・週末へ調整済み。**残るのは観測だけ。** ①次の週次実行が緑で終わること(証明書は8/5に全ノード更新済みで残り45日なので、**当面は「更新せずに緑」が正しい**) ②**実際に更新が走るのは9月上旬**(残り15日を切る頃)で、そこが本番の答え合わせになる。規範は `docs/ai/policies/cert_renew_policy.md` CERT-024。**承知の上の残存リスク** — `prepare_ca_apply`(CA鍵のtmpfs展開)は `cert_needs_renewal` ではなく `not ansible_check_mode` だけでgateされているため、更新不要な週も毎回展開される(年12回→52回)。抑えるなら `issue_check` を全ホストで先に回す形になるが、playの順序組み替えを伴うので別案件 | Yoshinobu決定(2026-08-06)。数値は `roles/homelab_cert_renew/defaults/main.yml`(valid 45 / threshold 15) |
| **一次調査成果物の保持期間と、滞留の検知** | `_investigations/` は消す仕組みを持たず、拾われないまま溜まった成果物を知る経路も無い(IC-021の一次調査への適用)。**Policy §8が「未決」として明示している項目のうち、一次調査が本番稼働に入ったことで実際に効き始めた2件**である。バンドル本体は `incident_capture_retention_days`(30日)で消えるため、成果物だけが残り続ける | `docs/ai/policies/incident_capture_policy.md` §8 |
| Jinjaの`strftime`フィルタが**コントローラの暗黙システムTZに依存**している(**2箇所**) | `roles/proxmox_snapshot_check/tasks/main.yml:57` と `playbooks/recovery_monitoring_check.yml:103,137`。Jinjaの既定(`utc=False`)を使うため、ansyのシステムTZが変わると出力もずれる。**「repo内で唯一」ではない** — 2026-08-03の独立レビューが2件目を検出した(1件目しか知らないまま規範文書へ「唯一」と書き、その誤りが同レビューで指摘された)。**急がない、かつ安易に直すと悪化する** — `%z` が実オフセットを出すので**TZが変わっても嘘にはならない**。`+09:00` の直書きは UTC の値に JST ラベルを付ける「詐称」になる。規約そのものは `skills/ansible-implementation-style/SKILL.md` が正本 | `docs/ai/reviews/ubuntu_nightly_reboot_check/2026-07-30_004_review_jst_sweep.md`、`docs/ai/reviews/norm_docs_convention_relocation/2026-08-03_001_review.md` |
| **`proxmox_patch_dryrun`の到達性判定を`proxmox_reachable_nodes`へ寄せ替える** | **機能の穴ではない。単一node時にパッチ情報を取れることは実装済みで動いている。** 残っているのは判定機構が2つ並存していることで、**判定の起点が違う** — roleは明示的な`ping` probe、`proxmox_patch_dryrun.yml`は`gather_facts`の結果(`ansible_facts \| length > 0`、同ファイル49-53行のコメント参照)。差が出るのはfact cachingが有効なときだけで、そのとき**dryrun側だけが**停止中のnodeを到達可能と誤判定する。寄せ替えれば、Semaphore側のfact caching設定に依存しなくなる。着手を外した理由は、weekly full chainのapply gateが実データで未観測の段階で作り直すと回帰の切り分けができないこと | `docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_001_requirement.md` §5 P1 |
| **`authy` / `monnie` 側にも同じ構造が残っている** | `recovery_exec_targets` を回す `roles/recovery_exec/tasks/target_setup.yml` の各タスクは、pve 側と同じく `delegate_to` のループで到達性を判定しない。どちらかが停止していれば `recovery_exec_setup.yml` は同じ形(ループ1件の unreachable が task 全体へ昇格し play が打ち切られる)で rc=4 になる。**pve 側は 2026-08-16 に probe + 絞り込みで解消したが、こちらは対象外とした** — 観測された事象が pve に限られたため(requirement §5 の P2 = R8)。**同じ直し方がそのまま使える。** 着手の引き金は authy / monnie を計画停止する運用が入るとき | `docs/ai/reviews/pve_unreachable_handling/2026-08-16_001_requirement.md` §5 R8 |
| **Semaphore の版上げ playbook(未着手)** | **方針は決定済み**(Yoshinobu、2026-08-10): **自動適用はしない。** 通常は `dry_run=true` の検知だけを回し、当てるときは手動作業とする。運用は現行の `prometheus_update_check` とほぼ同じ形で、**ansy と quory の版は揃える**。雛形は `roles/prometheus_update_check/` — GitHub Releases API で最新版取得 → 差分判定 → 退避 → 適用 → health check → 失敗時の自動ロールバック → 通知、`dry_run` 明示必須の fail-closed、`-e rollback=` / `-e rollback_to=` の共通規約。**prometheus と変わるのは3点だけ**: ①取得物が tarball ではなく `.deb` ②退避対象がバイナリではなく `semaphore.db` で、`semaphore migrate` を明示タスクへ切る ③**適用を Semaphore job から実行させない**(自分自身を再起動するため。`playbooks/cert_renew_quory.yml` と同じ隔離。`dry_run=true` の検知側は schedule に載せてよい)。**着手時はまず quory 側の現在版の実測から** — 版を揃える前提の起点であり、現時点で未測定 | Yoshinobu決定(2026-08-10)。インストール形態・`.deb` の中身・DB マイグレーションの制約は `docs/ai/context/system/semaphore.md`「インストールと版上げ」が正本 |
| **Semaphore 2.18.4 が受理する cron grammar が未実測** | schedule カタログの preflight は、標準の5フィールド cron を受理し判定できないものを拒否する保守的な検査に留まる。**当該版が実際に何を受理するかを測っていない**ため、Semaphore が拒否する cron をカタログへ書いたときに preflight が通してしまう可能性がある。**効くのは cron を変更するときだけで、現在の19件は稼働中の実値をそのまま転記したもの**。既存19件を valid fixture、当該版が拒否する代表値を invalid fixture として固定すれば閉じる | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-10_025_closeout.md` §3 |
| **規範文書間の突合を定期的に自動でかける仕組みの要否** | Auditorは案件クローズ時にしか起動しないため、案件が動いていない期間の規範ドリフトは拾えない。2026-07-29のCoordinator自己レビューで6件超の欠陥が見つかったが、これは人間が明示的に求めた1回限りの検出であり再発防止の仕組みではない。月次Knowledge振り返りの拡張が候補 | `docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md` §4 |
