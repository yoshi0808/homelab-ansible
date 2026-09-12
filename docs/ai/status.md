# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)はここに書かない。対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。

## このファイルの規律

1. **完了したら行を消す。履歴を残そうとしない。** 履歴は `git log` が持つ。
2. **値を二重に持たない。** 他に正本があるものは参照だけ書く。

## Now(進行中)

**ストレージ月次点検レポートの可読性改善: 本番表示確認済み・closeout待ち**。日本語の結論、重大度順の対応事項、ラベル付きZFS/NVMe値、簡潔なSlack短報へ変更。独立Reviewer=Approve、Tester=PASS。Semaphore #1062でcollectが成功し、Yoshinobuが改善後の内容を確認した。案件正本は `docs/ai/reviews/proxmox_storage_report_readability/2026-09-12_001_requirement.md`。

**Implementer / Reviewerのベンダー分離実験: 観測中(0/3件)**。ローカルreset後、Claude Code Implementer / 計画Reviewer / Auditorの常駐起動とREADY、fresh Codex差分Reviewer / Testerを常駐させない構成を実測した。次の非自明な実装案件3件で、Coordinatorの実装負担とトークン消費を観測する。独立規範レビュー=Approve、Codex Tester=PASS。要求は `docs/ai/reviews/cross_vendor_role_allocation/2026-09-12_001_requirement.md`、配備観測は `docs/ai/reviews/cross_vendor_role_allocation/2026-09-12_008_deployment_observation.md`、判断は `docs/ai/adr/013-cross-vendor-implementer-reviewer-experiment.md`。

**Proxmoxストレージ月次点検: 次回定期実行の観測待ち**。配備案件はクローズ。次回の自然実行・比較結果を確認する。Survey任意欄の反復差分有無と省トークン効果は未評価。根拠・残存事項は `docs/ai/reviews/proxmox_storage_monthly/2026-09-11_014_closeout.md`。

**auto-memory 110件の仕分けは保留**(Yoshinobu、2026-09-06)。**Codex は auto-memory を読まないため、移行後この知識は使われない。** Coordinator が Claude Code へ戻る機会があれば再開する。案件記録は `docs/ai/reviews/coordinator_platform_migration/`。

**Operator が起動時にこの repo を読む。`operator.md` は本番エージェントの起動時契約である(2026-09-03 クローズ、`42b639b`)** — Yoshinobu が quory 側で設定した。OPREQ で繰り返しトラブったことへの対応である。**編集は「文書の更新」ではなく「本番の挙動を変える変更」として扱う** — push すれば `worktree_sync` の timer で quory へ入り、次の起動から効く。

| | |
|---|---|
| repo から読む4文書 | `docs/ai/core.md` / `docs/ai/roles/operator.md` / `docs/ai/context/operations/operator-request-channel.md` / `docs/ai/policies/execution_boundary_policy.md` |
| 読み込み元 | `/home/yoshi/homelab-ansible` の **Git作業ツリーそのもの**。毎セッションの作業開始時 |
| 起動時の入口 | **repo外の `/home/yoshi/operator-runtime/AGENTS.md`**(cwd も同じ)。repo直下の `AGENTS.md` は読まれていない |

**正本は2軸に分かれる**(`operator.md`「この文書の位置づけ」が正本)。規範上の責務と禁止は repo の Role文書と個別Policy、起動時の入口・読む範囲・実効能力の現物は quory 側。**食い違うときは狭いほうが効く。** **Operator をこのリポジトリで管理し切ろうとしない** — 独立性の担保として入口が意図的に repo 外にある。

**読ませる文書を増減させるのは Yoshinobu 側の操作で、開発側からは観測も変更もできない。** 変更後に再起動して往復を確認済み。

**申し送り**: `operator-request-channel.md` と `execution_boundary_policy.md` は本文を点検し、直すべき記述は無かった。ただし後者は冒頭で「AIが実ホストへ何をしてよいか」の正本と名乗る一方、中身は全て ansy 側で `EXEC-050` に Operator の行が無い。**穴ではなく「Operator を規定していない」意味で、Operator 自身もそう読めている。** 表題の広さと適用範囲のずれは、次に本書を改訂する機会に一緒に見る。

**月次 apply は2026-09-03に4台とも完了し、`timeout` の SIGTTOU 案件もクローズした(`d95133c`)** — 発端は 9/3 08:09 の monnie への apply(#938)で、`Run apt full-upgrade` が無期限停止した。原因は2026-08-22 の conffile 対策が入れた `timeout` 自身である — `become: true` で Ansible が pty を割り当てる文脈で `timeout` が新しいプロセスグループを作り、それが背景グループとして制御端末に触って `SIGTTOU` で停止した(`timeout` も同じグループで止まるため、3600秒のアラームは発火しない)。**conffile 対策そのものは効いている** — 4台とも term.log に conffile プロンプトは1つも出ていない。復旧は同日 09時台に完了し(`dpkg --configure -a` は即返、`loki` / `unpoller` を再起動)、修正 `41a55ae`(`setsid -w` + 既定モードの `timeout`)で **quory #943 / authy #944 / ansy #945 の3台が完走した**。Incidentは `docs/ai/memory/incidents/2026-09-03_apt-stalled-by-the-timeout-added-to-prevent-stalls.md`。

**案件 `docs/ai/reviews/ubuntu_vm_apply_timeout_sigttou/` はクローズした**(closeout `_005`、Auditor `_006` は条件付き受入 → 指摘を反映)。blockingだったIncidentの状態欄(「恒久対策は未実施」のまま取り残されていた)を是正し、非ブロッキング2件(3600秒の見直しを扱わなかったこと、差し替え前レビューの一次記録が無いこと)をcloseoutへ明記した。**本番3台の完走は「修正が効いた」ことの証明ではない** — 3台の apt が端末に触ったかどうかは分からない。機構が効くことの確認は sandbox の実測(`.../2026-09-03_003_implement.md`)が担う。

**残存リスクと申し送り。**

- **`--force-confold` は手動管理の設定をメジャー版更新でも黙って保持する。** 今回 unpoller は 4.x → 5.x をまたいで旧設定のまま動いたが、**観測であって保証ではない**。また `MAJOR_UPGRADE_DETECTED` は codename drift / 合計100超 / remove 30超の3信号だけで、**個々のパッケージのメジャー版差は見ていない**(守備範囲の違いであり欠陥ではない)
- **Operator は apt のログを読めない**(`root:adm 0640`、`ann` では拒否)。本番で apt が止まったとき、運用側から中身を確かめる手段が無い
- **`NEEDRESTART_MODE=l` は再起動しないため、更新したパッケージのうち動いているプロセスが旧版のままのものがある。** authy は `libpam` 系が入ったが `freeradius` は旧ライブラリのまま動いている(再起動不要と出ており、急がない)

**一次調査の先読みは成立した(2026-09-03 観測、案件クローズ)** — ジョブ #938 の失敗で一次調査が自然に動き、`notes` に `Permission denied` は現れず、`observations` が Semaphore のエラー本文(`rc=-9`)まで引用した。2026-08-25 の traverse ACL 付与(`bbf2afa`)が効いている。記録は `docs/ai/reviews/incident_prefetch_traverse/2026-09-03_006_observed.md`。**同じ通知で Slack uri 移行の AC3 も充足した**(色バー無し=プレーンテキスト。`docs/ai/reviews/slack_notify_uri_migration/2026-09-03_008_ac3_observed.md`)。

**この2件から残った弱点は3つで、いずれも案件を起こしていない。**

- **`workspace` の本番現物を開発側から観測する手段が無い。** `acl-status` の表に arm が無く、repo 側の定義までしか言えない
- **`acl-status semaphore-db` は恒久的に `Permission denied`。** `dev-investigate` が traverse を失ったためで異常ではないが、**ACLが付け直されていないかを開発側から観測する手段は失われた**
- **先読みが空でも「調査したがわからなかった」と同じ見た目で通知が出る。** 通知が運ぶのは verdict / confidence / known_condition で `notes` は運ばない。2026-08-22 の #802 では `EACCES` が成果物の中にしか無く、Slack には「特定不能」としか出なかった

## Next(着手候補) — 工程・体制

| 項目 | 内容 | 根拠 |
|---|---|---|
| **規範監査の残余(小粒3点)** | 2026-08-25の横断監査は第1束・第2束とも実施済みでクローズ(Auditor受入=`_014`)。残るのは①findings 3本の「未確認」節のうち巻き取られていない項目 ②C3-3(現在は一致している複製群の扱い) ③credential保管pathの2Policy間のねじれ(`_013`のCoordinator判断節)。いずれも急がない。次の監査サイクルでまとめて判断する | 案件記録 `docs/ai/reviews/norm_docs_audit/` |
| **`docs/ai/roles/` 5本のプロンプト最適化(継続案件)** | Coordinator / Implementer / Reviewer / Tester / Auditorの各Role文書を、**実際に運用してみて出てきた歪みを持ち寄って協議しながら**直し続ける。対象は①**やること・やらないことの衝突**②**何を言われているのか読み取れない箇所**③**細かく指示するよりAIに任せた方が結果が良い箇所**の3クラス。一度に全部やる案件ではなく、気づいたものを溜めて定期的に議論する形を採る | Yoshinobu表明(2026-08-01)「ある程度最適化して随分良くなってきたが、まだ矛盾・不明瞭・非効率が残る」。**歪みの実例はCoordinatorが運用中に気づいた時点で書き溜める**(置き場は本行) |
| **sandbox を検証環境として使い込む** | **inventory 登録と `serial_getty_mask` は2026-08-06に完了**(`b20c43d`。`NRestarts=20322` の agetty ループを停止、hostname も `ubuntu` から `sandbox` へ)。承認境界でも `monnie` / `ansy` と同じ「確認不要」側にある。**ここから先は使い道の話であって、必須の作業ではない。** Yoshinobu が挙げた候補は ①monnie のサービスの検証 ②**まだAnsibleへ移行していない FreeRADIUS**(`authy`)— ただしクライアント/サーバのテスト用公開鍵を一度置く必要があり、かつ RADIUS は設定をほとんど変えないため**費用対効果は未評価**。**この行の要点は「decoy より広く試せる実ホストが手に入った」ことで、個々の候補ではない。** 監視対象にはしない。`rsyslog_forward_to_monnie` を向けるには allow-list への追加とホストごとの recon が要る(未着手・急がない)。**次に手を加える機会があれば、`authorized_keys` をrepoへ入れる**(2026-08-19。いま「どの公開鍵がsandboxを開けるか」はrepoのどこにも無く、実体を見るしかない)。**そのとき排他上書きに注意する** — 既存のsetup系roleは `authorized_keys` を上書きするため、素直に当てると同居する quory の `ann` 鍵を消す。追記型にするかsandbox専用にするかを先に決める | Yoshinobu表明(2026-08-06)。前提・使い方・限界・壊したときの扱いは `docs/ai/context/operations/sandbox-vm.md` が正本 |
| **monnie の代わりになる開発機を作るか**(鍵は2026-08-19に切断済み) | **`id_ann` を ansy から削除し、monnie への到達は閉じた**(EXEC-005)。本番の管理は quory の Semaphore で走るため何も止まっていない。**残っているのは「開発とテストで monnie 相当の相手が要るか」だけで、これは不便を実際に測ってから決める**(Yoshinobu、2026-08-19)。`sandbox-mon`(requirement R19〜R21、D3 で別案件へ切り出し済み)がその受け皿になりうるが、当時の目的は「監視スタックのupgradeリハーサル」であり、**今回示された目的(ansy が本番へ触らないこと)の方が広い**。着手時期は未定 | Yoshinobu表明(2026-08-03、Phase 4 の D9 を決めた文脈)。`docs/ai/reviews/dev_prod_boundary/2026-08-03_015_plan_phase4.md` §3.1 |

## Next(着手候補) — システム・運用

| 項目 | 内容 | 根拠 |
|---|---|---|
| **Ubuntu inspection templateのUI名称を整理する** | `SEMI-SAFE: Ubuntu vm full upgrade (dry-run)`は既存identity維持のため旧名を残したが、現在はSurveyの`operation=inspect`を通常実行し、Semaphore native Dry RunはOFFにする契約である。2026-09-09の手動inspection時、名称からnative Dry Runやapply templateとの区別を誤りやすいことをYoshinobuが実際に確認した。機能上はoperation guardが変更経路を閉じているため、本案件を再開せず別案件でUI名称とidentity移行方法を整理する | `docs/ai/reviews/update_playbooks_dry_run_collision/2026-09-09_015_deployment_observation.md` |
| **ドリフト検査が「見られなかった」を「差分なし」として通す(2件)** | `roles/deployment_drift_check/tasks/evaluate.yml:142,145`(所有権)と `:240`(禁止ファイル)が、収集`find`の `rc` を見ずに `stdout` だけを読む。`collect.yml:98,140` が `failed_when: false` のため、**収集が失敗した周期は finding が出ず、毎日「差分なし」で通る。** Coordinator が現物で確認済み。**誤検出ではなく検出漏れなので急がない。** 直す方向は「収集失敗そのものを finding にする」で、`--check` と通知経路への影響を見る必要がある | 掃き出し `docs/ai/reviews/undecidable_falls_through_sweep/`。**`\| length` の383ヒットを全件走査して確定したのはこの2件だけである**(未確定18)。`or []` / `or {}` / `or 0` の23件と `\| default(x, true)` の90件も走査済みで確定ゼロ。**計496ヒットを見て確定はこの2件だけだった。** 残るのは `\| default(x)` 素の869ヒットだが、**収穫率と、この家族が「任意変数に既定を与える」定石そのものであることから着手しないと判断した**(Yoshinobu了承のうえCoordinator判断、2026-09-05)。やるなら「コマンド結果・API応答に対する `default()`」へ絞り直す |
| **apt以外のアップデートを機械的に当てる** | Yoshinobu表明(2026-08-23)「update は機械的に行う(人の判断が入らない)」。**aptはそうなっている**(Ubuntu Pro / unattended-upgrades)が、現行の定期経路はscheduled `operation=inspect`で検知まで行い、変更は人がmanual `operation=apply`（apt）/ `operation=update|rollback`（Prometheus）を明示する。non-aptの現行境界は `UV-035`〜`UV-038` に記録済みであり、無人適用を実現するならPolicyと実装を同じ案件で改訂する。`roles/prometheus_update_check/` は無人運用向けの機構を既に持つ(チェックサム検証・トランザクションロック・リトライ付きhealthcheck・**失敗時の自動ロールバック**・バックアップ3世代)。**ただし監視の中核を無人で入れ替える変更**なので、requirementとTesterを通す。**Semaphoreは同じ扱いになるが、そもそも検知経路が無い**(本表の別行) | Yoshinobu表明(2026-08-23)。現行の境界は `docs/ai/policies/ubuntu_vm_patch_policy.md` `UV-086` |
| **DLP entropy の既存誤検知(14件)** | 2026-08-23 の corpus scan(**5ルート・376本に絞った母集団**での手分類)で、`high-entropy-string` が **PascalCase の長い識別子と hex 文字列 14 種**を BLOCK していることが分かった。**全追跡ファイル(1,737本)まで広げると、20文字以上の BLOCK は 57 種になる**(内訳の手分類は未実施)。**同日の候補パターン変更より前から BLOCK されており、今回の変更が持ち込んだものではない**(`git show HEAD` で着手前の状態を再判定して確認)。**文字クラスの調整では衝突ゼロに到達しない**ことが4ラウンドで分かっており、直すなら指標か適用範囲の側を変える案件になる。**急がない** — 止まったときは拒否メッセージが `rule_id at pointer` で場所を示すため、書き換えて再送できる | `docs/ai/reviews/oprc_dlp_false_positive/2026-08-23_005_review.md`。判定の境界は `docs/ai/context/operations/operator-request-channel.md` |
| **ansy が自分自身を対象にする playbook を実行できない** | `id_ann` 削除(2026-08-19)以降、`dev_nodes` の group_vars が**存在しない鍵を指す**ため、ansy から ansy 自身への SSH が成立しない。2026-08-23 に `operator_request_channel_client_setup.yml` の配備が止まった(その場は暫定で通し、下記の理由で revert 済み)。**いま困ってはいない** — client は配備済みで、次に ansy が自分へ配備するときに再発する。<br>**素の `ansible_connection: local` を `host_vars/ansy.yml` へ入れてはいけない。** host_vars は inventory のデータで、**quory の Semaphore も同じものを読む**。2026-08-24、これにより quory が `ansy` を対象にした検査で **quory 自身を見て** drift 2件を誤報した(`89e822a` → `9e9daf5` で revert)。**変更系 playbook を流していれば quory が書き換わっていた。**<br>**正しい形は `inventories/homelab/host_vars/quory.yml` に既にある** — `lookup('pipe', 'hostname -s')` でコントローラを見て条件分岐する。**同じ問題が同じ inventory の中で既に解かれていた。**<br>**入れるときの受入条件**: quory から `ansy` を対象に `--check` を流し、**quory ではなく ansy を見ている**ことを確認する。これを確かめずに入れない | `9e9daf5` の commit メッセージ。ドリフトの実測は 8/22・8/23 が 0、8/24 00:40 が 2、revert 後の 07:50 が 0 |
| **template の reconcile が `false` / `{}` を空配列へ畳む** | `roles/semaphore_templates/` の template 側で、API の `arguments: false` や `survey_vars: {}` が **`value or []` で空配列に倒れる**。`false` も `{}` も falsy なため、**型を確かめずに `or` で既定へ流している**。結果、**現物とカタログが食い違っていても `unchanged` を返す**。<br>**HEAD にもある既存欠陥**で、2026-08-24 の有効化ゲート撤去が持ち込んだものではない。**同案件では直さなかった** — 既存欠陥であること、撤去の差分が読みにくくなること、**template の reconcile 挙動が変わるため実 Semaphore に対する受入検証が別途要る**ことによる。<br>**同じ形(型を確かめず truthiness や長さで判断し、判定不能が通す側へ倒れる)が 2026-08-24 に4件出ている** — `semaphore_update_check` の `html_url` を `length > 0` で見た件、同 `null`/数値での評価例外、有効化ゲート撤去での `active` の truthiness、そして本件。**4件とも読解では出ず、実行して出た。4件とも独立レビューが見つけた** | `docs/ai/reviews/semaphore_activation_gate_removal/2026-08-24_006_review.md` |
| **Operator Request Channel の後続2件** | MVPは2026-08-09にクローズ。**残存リスク4件と設計上の申し送りは `docs/ai/reviews/operator_request_channel/2026-08-09_018_closeout.md` §4 が正本**(quory側ライブラリのhash照合手段が無いこと、checkpoint 4のreject方向が原理的に検証不能なこと、spoolに試験messageが4件残ること、**書き込みの門をPOSIX ACLだけと仮定していたこと**)。後続は①**ID専用の通知**(本文はDLP経路だけ、通知は `request_id` しか運ばない) ②**storeの簡素化**(容量会計・イベントログ・conversation索引)。②はquory側Operatorが「一定期間使ってから判断」としていた。**実バグ4件はいずれもstoreと権限の層で、DLPでは1件も出ていない** — 芯と帳簿の切り分けが実測で裏づいた形であり、②の設計入力になる | Yoshinobu決定(2026-08-09にクローズ)。案件記録は `docs/ai/reviews/operator_request_channel/` |
| **一次調査成果物の保持期間と、滞留の検知** | `_investigations/` は消す仕組みを持たず、拾われないまま溜まった成果物を知る経路も無い(IC-021の一次調査への適用)。**Policy §8が「未決」として明示している項目のうち、一次調査が本番稼働に入ったことで実際に効き始めた2件**である。バンドル本体は `incident_capture_retention_days`(30日)で消えるため、成果物だけが残り続ける | `docs/ai/policies/incident_capture_policy.md` §8 |
| Jinjaの`strftime`フィルタが**コントローラの暗黙システムTZに依存**している(**2箇所**) | `roles/proxmox_snapshot_check/tasks/main.yml:57` と `playbooks/recovery_monitoring_check.yml:103,137`。Jinjaの既定(`utc=False`)を使うため、ansyのシステムTZが変わると出力もずれる。**「repo内で唯一」ではない** — 2026-08-03の独立レビューが2件目を検出した(1件目しか知らないまま規範文書へ「唯一」と書き、その誤りが同レビューで指摘された)。**急がない、かつ安易に直すと悪化する** — `%z` が実オフセットを出すので**TZが変わっても嘘にはならない**。`+09:00` の直書きは UTC の値に JST ラベルを付ける「詐称」になる。規約そのものは `skills/ansible-implementation-style/SKILL.md` が正本 | `docs/ai/reviews/ubuntu_nightly_reboot_check/2026-07-30_004_review_jst_sweep.md`、`docs/ai/reviews/norm_docs_convention_relocation/2026-08-03_001_review.md` |
| **`proxmox_patch_dryrun`の到達性判定を`proxmox_reachable_nodes`へ寄せ替える** | **機能の穴ではない。単一node時にパッチ情報を取れることは実装済みで動いている。** 残っているのは判定機構が2つ並存していることで、**判定の起点が違う** — roleは明示的な`ping` probe、`proxmox_patch_dryrun.yml`は`gather_facts`の結果(`ansible_facts \| length > 0`、同ファイル49-53行のコメント参照)。差が出るのはfact cachingが有効なときだけで、そのとき**dryrun側だけが**停止中のnodeを到達可能と誤判定する。寄せ替えれば、Semaphore側のfact caching設定に依存しなくなる。着手を外した理由は、weekly full chainのapply gateが実データで未観測の段階で作り直すと回帰の切り分けができないこと | `docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_001_requirement.md` §5 P1 |
| **`authy` / `monnie` 側にも同じ構造が残っている** | `recovery_exec_targets` を回す `roles/recovery_exec/tasks/target_setup.yml` の各タスクは、pve 側と同じく `delegate_to` のループで到達性を判定しない。どちらかが停止していれば `recovery_exec_setup.yml` は同じ形(ループ1件の unreachable が task 全体へ昇格し play が打ち切られる)で rc=4 になる。**pve 側は 2026-08-16 に probe + 絞り込みで解消したが、こちらは対象外とした** — 観測された事象が pve に限られたため(requirement §5 の P2 = R8)。**同じ直し方がそのまま使える。** 着手の引き金は authy / monnie を計画停止する運用が入るとき | `docs/ai/reviews/pve_unreachable_handling/2026-08-16_001_requirement.md` §5 R8 |
| **Semaphore が受理する cron grammar が未実測** | schedule カタログの preflight は、標準の5フィールド cron を受理し判定できないものを拒否する保守的な検査に留まる。**当該版が実際に何を受理するかを測っていない**ため、Semaphore が拒否する cron をカタログへ書いたときに preflight が通してしまう可能性がある。**2026-08-18の版上げで前提が変わった** — 測る対象は 2.18.4 ではなく 2.19.8(quory)/ 2.19.12(ansy)になり、さらに **2.18.28 が cron 検証をJSライブラリからバックエンドendpointへ変えている**ため、検査の性質そのものが変わっている可能性がある。**効くのは cron を変更するときだけで、現在の20件は稼働中の実値をそのまま転記したもの**。既存20件を valid fixture、当該版が拒否する代表値を invalid fixture として固定すれば閉じる | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-10_025_closeout.md` §3、`docs/ai/reviews/semaphore_upgrade/` |
| **規範文書間の突合を定期的に自動でかける仕組みの要否** | Auditorは案件クローズ時にしか起動しないため、案件が動いていない期間の規範ドリフトは拾えない。2026-07-29のCoordinator自己レビューで6件超の欠陥が見つかったが、これは人間が明示的に求めた1回限りの検出であり再発防止の仕組みではない。月次Knowledge振り返りの拡張が候補 | `docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md` §4 |
