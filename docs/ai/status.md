# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)はここに書かない。対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。

## このファイルの規律

1. **完了したら行を消す。履歴を残そうとしない。** 履歴は `git log` が持つ。
2. **値を二重に持たない。** 他に正本があるものは参照だけ書く。

## Now(進行中)

**観測待ち: sandbox が自分でパッチを当てて再起動すること(2026-09-05 配備、案件 `docs/ai/reviews/sandbox_auto_patch/`)** — sandbox は `-security` しか当たらず、`/var/run/reboot-required` が2026-08-22から立ったままだった。原因は本番の `-updates` と再起動を担う月次 `ubuntu_vm_full_upgrade` レーンに `sandbox_nodes` が入っていないこと。**quory は sandbox の鍵を持たないためレーンへ足せない**(`id_sandbox` は ansy 専用)ので、箱自身の unattended-upgrades へ drop-in で `-updates` と `Automatic-Reboot`(04:00、ログイン中でも)を足した。Semaphore には登録していない — 配ったあと動かすのは sandbox 自身の apt timer である。

**再起動の側は証明済み、インストールの側は未観測。** 実効値が `Automatic-Reboot "true"` / `04:00` / `WithUsers "true"` になっていることと、AC9(効いていなければ playbook が失敗する)は実機で確認した。**まだ確かめていないのは、日次実行が実際に `-updates` を入れるところである** — 2026-09-05 の `dpkg.log` は0行で、`-updates` を許可した状態での日次実行はまだ一度も起きていない。`apt.systemd.daily` は前回実行のスタンプが間隔より新しいと飛ばすため、**9/6 の発火(06:16)は現スタンプ(9/5 06:41)より早く、もう1回飛ぶ可能性がある。9/6 と 9/7 の両方を見る。**

**drop-in が `99` でなければならない理由を消さないこと。** `52` にすると **cloud-init 由来の `/etc/apt/apt.conf.d/52unattended-upgrades-local`**(`Automatic-Reboot "false"` のみ)に名前順で負け、再起動設定が黙って無効化される。**これは実機でしか出ず、Implementer と Reviewer の fixture では通っていた。** 同ファイルは `ansy` にもあり、本番ではそれで正しい(再起動は月次playbookと03:30の条件付きrebootが担う)。**cloud-init の user-data は触らない** — 変えると今後作る全VMに効く。sandbox の cloud-init は seed が外れており再実行されない(2026-09-05実測)。

**sandbox は本番より先へ進む。** `-updates` を随時取り込むため、月次でしか上がらない本番との間に「進んでいる側」の乖離が生まれる。**承知のうえで受け入れた**(requirement §8)。



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

**観測待ち: syslog週次ダイジェストの初回実行(2026-09-04 実装、commit `2eeb51c`)** — `SAFE: Syslog weekly digest`、**毎週月曜 09:00**。閾値を持たないダイジェストであって検知ではない(`level`を発火条件にしない)。**登録は済んでおり、あとは発火を待つだけである** — template 56 / schedule 23(`0 9 * * 1`、`active: true`)。**実行回数は0回で、初回は2026-09-08(月)09:00**。

**独立レビュー6巡でApprove、Testerが実測でAC2〜AC6を検証した。AC1(実Slack送信)とAC7(実monnie上の無変化)は到達手段が無く未検証である** — ansyからmonnieへの鍵は2026-08-19に削除済みで、使えるのは`monnie-investigate`の24h窓だけ。**本実装が使う168hは配備前には原理的に確かめられない。**

**初回実行で見るもの(観測計画の正本は `docs/ai/reviews/syslog_weekly_digest/2026-09-01_004_test_result.md` §4)。**

- 実Lokiが168hのqueryと`limit=300`を受理するか
- **実Slackで本文が6,000字に収まり省略表示が出るか** — Slackのattachment textの実上限はrepoのどこにも記録が無く、誰も測っていない。6,000は保守的に置いた値である
- Semaphoreのジョブ出力にマスク前の生データが出ていないこと
- **`error_total`と`error_entries`が食い違う頻度** — 食い違うと原因が何であれ「取得失敗」として届く設計にした(`core.md`「判定できないときは止める」に従った受容)。頻発するなら許容幅を設けるかを判断する
- series件数と`MAX_SERIES=500`の余裕

**承知の上の残存リスク**: 秘匿の保証は機械的に検出できるIPv4に限る。error全文を出す以上、IPv4以外のcredential/tokenが`#info`へ出る可能性は残る(**安全境界の緩和としてYoshinobuが判断した**、EXEC-030、requirement §5)。**Testerが実データで確認済み** — 実ログ行の`::ffff:`付きIPv4は伏せられ、`user=admin@pve`は伏せられない。

**観測待ち: Semaphore の新版検知が初めて発火すること(2026-08-25 実装)** — `SAFE: Semaphore update check monthly`、**毎月10日 20:00**。**初回は 2026-09-10。** **2026-08-30 に v2.19.12 が出ており、ansy は 2.19.8 実測(quory は未確認)なので、次に回れば鳴るのが正常である**(2026-09-05 に WebFetch で確認)。**「鳴らないのが正常」と読まないこと。** Yoshinobu が検知ジョブを前倒しで手動実行する可能性がある。apt リポジトリが無く GitHub Releases からしか取れないため、この経路が唯一の検知手段である。**適用は手動**で、手順は `docs/ai/reviews/semaphore_upgrade/2026-08-18_002_manual_procedure.md`。**本番で1回手動実行して `up_to_date` を確認済み**(ジョブ #827)。案件記録は `docs/ai/reviews/semaphore_update_check/`。**同日、schedule の有効化ゲートを撤去した**(`docs/ai/reviews/semaphore_activation_gate_removal/`) — カタログが `active: true` と書けば1回の適用で有効になる

**観測待ち: 誤りの再発を機械が刻む仕組み(2026-08-18 実装)** — **規範に書いても守れない誤りがあり、それを自己申告でしか検出できていない**という問題への手探り。**2回目の発火で過検出が確定し、2026-08-19に門を2段階で差し替えた。過検出は大きく下がったが、残っており、合否を判定する手段がまだ無い。**

- **形式は `docs/ai/memory/lessons/` の「再発記録」節**。**契約の正本は `docs/ai/memory-classification.md`「`lessons/`の「再発記録」節」**(2026-08-25に移設 — それまで各lessonへ12行の定型文を複製しており、8本で96行の二重化になっていた)。節が持つのは見出し・正本へのポインタ1行・表だけである。書き込む実装は `scripts/session-recurrence-record.py`
- **機構は `SessionEnd` hook と `scripts/session-recurrence-record.py`**(`.claude/settings.json` に登録)。決めた3点は①hookは `SessionEnd`、`reason` が `resume` のときだけ対象外とし **`clear` は含める**(この環境では境界の大半が `/clear` のため)②別体は**役を着せない `codex exec` を1回**(Reviewer役は着せない — 「findingsを重大度別に返せ」が過検出へ引くため)③渡すのは user/assistant の本文と `tool_use` の入力のみで **`tool_result` は捨てる**。transcript のパスは codex へ渡さず stdin で流す(境界を依頼文でなく入力経路に置く)
- **異常終了では発火しない。** OOM・SIGKILL・電源断は `shutdown()` を通らず hook が起動しないため、**取りこぼしは沈黙として現れる。対象外とすることをYoshinobuが決めた**(2026-08-18)
- **hook自身が起動したのに黙って終わる経路は、2026-08-25に塞いだ。** それまで「該当なし」「対象外」「本文が空」は無言で `return` しており、**ログに行が無い状態が「該当なし」「途中で落ちた」「起動しなかった」の3つと同じ見た目になっていた**。実際 2026-08-19 に `TimeoutExpired` で1回取りこぼしている(ログには残っていたが誰も読んでいなかった)。全経路で1行残すようにし、**ログを月次の測定対象へ入れた**(`docs/ai/memory/knowledge-review-log.md`)。ログはrepo外(`~/.claude/`)にあり、gitに入らない
- **`/clear` のたびに codex が1回走り、最大120秒待つ。** 待ち時間の上限は `.claude/settings.json` の `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS`
- **同じ日に、現在地の渡り方も直した** — SessionStartで渡る本ファイルが **hookの10,000文字制限で切れていた**(出力16,821文字に対し先頭2,000文字しか届かず、Next表の2行目で切断)。`scripts/session-context.py` で節境界に分割し4エントリ登録した(commit `036649d`)。**分割は成立している** — 2026-08-18のセッション開始で全節が届いた。
- **初回発火を確認した**(2026-08-18、commit `dcb7375`)。lesson 4本へ追記され、**再発記録節が無い lesson への新設経路も通った**
- **2回目の発火で過検出が確定した**(2026-08-19、9本へ13行)。Yoshinobuの判定は「**これみんな不要**」で、記録してよいのはPolicy違反・harnessによる停止・書いてあることをしなかった、の類だけである。**原因は分類器の門そのもの**で、旧プロンプトは「どの形に当たるか」しか問わず**誤りがあったかを一度も問うていなかった**ため、話題が似ていれば当たった。既存13行のうち**規範の所在を書けない11行を削除**した(残り2行はいずれも「確認していないものは未確認と明示する」違反)
- **門は2段階で直した**(commit `47c01b2` / `397efbe`)。①3分類へ限定し `norm` を必須にした ②**推測で行動する類を名指しで立てた** — 一般則だけでは拾えず、8/18のtranscriptが0件になっていた。**規範側は既に `coordinator.md` と `core.md` へ5文書いており、足りなかったのは分類器がこの類を名指しで探していないことだけだった**(Yoshinobu、2026-08-19「過去何度も推測で行動される傾向がある」)
- **実測**: 8/18 は 6件 → 0件 → **5件**、8/19 は 9件 → 4件 → **5件**。後者10件はすべて `core.md` か `coordinator.md` の実文を norm に引いている
- **合否を判定する手段が無い。** 「既知の正解が返れば合格」は成立しなかった — **lessonごと1行の上限**があるため、1セッションに同じ形が複数あるとどれが返るかが決まらない。判定できるのは「その類が規範の引用つきで検出されるか」までである
- **過検出はゼロになっていない。** 10件中1件、**docstringに理由を書いた意図的な設計**(SessionEnd hookは非0を返すと終了を妨げるため常に exit 0)を `core.md`「空の成功で先へ進めない」違反として読んだ
- **回数は推定であって測定ではない。** 分類器はLLMで、見落とせば沈黙し過検出すれば水増しする。**回数だけを昇格の根拠にしない**
- **良くなる確証は双方とも持っていない**(Yoshinobu、2026-08-18)。やってみる価値はあるという判断で始めた
- **やめる条件は現段階では定めない**(Yoshinobu、2026-08-18)。Coordinatorが「効かなかったことを観測可能にするため先に決めるべき」と進言し、**現段階では不要と判断された**。再提案しない

**一次調査の先読みは成立した(2026-09-03 観測、案件クローズ)** — ジョブ #938 の失敗で一次調査が自然に動き、`notes` に `Permission denied` は現れず、`observations` が Semaphore のエラー本文(`rc=-9`)まで引用した。2026-08-25 の traverse ACL 付与(`bbf2afa`)が効いている。記録は `docs/ai/reviews/incident_prefetch_traverse/2026-09-03_006_observed.md`。**同じ通知で Slack uri 移行の AC3 も充足した**(色バー無し=プレーンテキスト。`docs/ai/reviews/slack_notify_uri_migration/2026-09-03_008_ac3_observed.md`)。

**この2件から残った弱点は3つで、いずれも案件を起こしていない。**

- **`workspace` の本番現物を開発側から観測する手段が無い。** `acl-status` の表に arm が無く、repo 側の定義までしか言えない
- **`acl-status semaphore-db` は恒久的に `Permission denied`。** `dev-investigate` が traverse を失ったためで異常ではないが、**ACLが付け直されていないかを開発側から観測する手段は失われた**
- **先読みが空でも「調査したがわからなかった」と同じ見た目で通知が出る。** 通知が運ぶのは verdict / confidence / known_condition で `notes` は運ばない。2026-08-22 の #802 では `EACCES` が成果物の中にしか無く、Slack には「特定不能」としか出なかった

**Implementer と Reviewer を入れ替えた(2026-09-04)** — **Implementer は agmsg 経由の codex(tmux右ペイン、`new-session.sh` が起動時に立てる)、Reviewer は Claude Code subagent** になった。正本は `docs/ai/roles/coordinator.md`「起動できるRoleと、その実現方式」、経路は `docs/ai/context/operations/agent-messaging.md`。**片側だけを動かす選択肢は無い** — 実装が codex なら codex Reviewer は自己レビューになり、別モデルであることによる独立性が失われる。

狙いは利用量の平準化(Claude側が上限に当たり、Codex側に余裕があった)と、両モデルの得意・苦手を実地で知ること。**次の1〜2案件で判断する。1案件では決めない。**

**測るもの**(新しい台帳は作らない。案件記録の implement / review ファイルに載る範囲で見る)。

- **codexの過剰実装** — requirementに無い実装が入っていないか。2026-09-02にYoshinobuが実装をcodexへ回さない理由として挙げた傾向であり、今回はそれを承知で試している。歯止めは依頼文でのファイル列挙と、Reviewerへ渡す明示の観点(`coordinator.md`「委任するときの独立性」)
- **Claude Reviewerの検出力** — 直前まではcodex Reviewerが2案件連続で正しかった。その優位を手放した影響が出るか
- 実装の往復回数と差分規模

**1案件目は `docs/ai/reviews/loki_window_embedded_newline/`(2026-09-04、配備まで完了)。**codex Implementerは**過剰実装なし・往復0回**、Claude Reviewerは**findings 0でApprove**。ただし対象は同一ファイル内に雛形のある1行修正で、**検出力の比較材料にはなっていない**。**この回で欠陥が出たのは記録側で、拾ったのはAuditorだった** — Reviewerが自分の検証カバレッジを過小に書き(11種回して「10種」、実際に回した文字種を「未検証」と記載)、Coordinatorがそれを現物で確かめずに引き継いだ。**2案件目は、検出力が問われるものを当てる。**

**`~/.codex/rules/default.rules` の実装時の許可は、1案件目では問題にならなかった** — ファイル編集・`python3`・`git diff` の範囲では昇格を求めて止まることは無かった。**Ansibleの実行を伴う実装ではまだ通していない。** Reviewerで通る範囲しか実績が無い。足りなければcodexは迂回せず昇格を求めて止まる(`agent-messaging.md` §5 と同じ形)ので、危険ではなく手間として現れる。

## Next(着手候補) — 工程・体制

| 項目 | 内容 | 根拠 |
|---|---|---|
| **規範監査の残余(小粒3点)** | 2026-08-25の横断監査は第1束・第2束とも実施済みでクローズ(Auditor受入=`_014`)。残るのは①findings 3本の「未確認」節のうち巻き取られていない項目 ②C3-3(現在は一致している複製群の扱い) ③credential保管pathの2Policy間のねじれ(`_013`のCoordinator判断節)。いずれも急がない。次の監査サイクルでまとめて判断する | 案件記録 `docs/ai/reviews/norm_docs_audit/` |
| **`docs/ai/roles/` 5本のプロンプト最適化(継続案件)** | Coordinator / Implementer / Reviewer / Tester / Auditorの各Role文書を、**実際に運用してみて出てきた歪みを持ち寄って協議しながら**直し続ける。対象は①**やること・やらないことの衝突**②**何を言われているのか読み取れない箇所**③**細かく指示するよりAIに任せた方が結果が良い箇所**の3クラス。一度に全部やる案件ではなく、気づいたものを溜めて定期的に議論する形を採る | Yoshinobu表明(2026-08-01)「ある程度最適化して随分良くなってきたが、まだ矛盾・不明瞭・非効率が残る」。**歪みの実例はCoordinatorが運用中に気づいた時点で書き溜める**(置き場は本行) |
| **sandbox を検証環境として使い込む** | **inventory 登録と `serial_getty_mask` は2026-08-06に完了**(`b20c43d`。`NRestarts=20322` の agetty ループを停止、hostname も `ubuntu` から `sandbox` へ)。承認境界でも `monnie` / `ansy` と同じ「確認不要」側にある。**ここから先は使い道の話であって、必須の作業ではない。** Yoshinobu が挙げた候補は ①monnie のサービスの検証 ②**まだAnsibleへ移行していない FreeRADIUS**(`authy`)— ただしクライアント/サーバのテスト用公開鍵を一度置く必要があり、かつ RADIUS は設定をほとんど変えないため**費用対効果は未評価**。**この行の要点は「decoy より広く試せる実ホストが手に入った」ことで、個々の候補ではない。** 監視対象にはしない。`rsyslog_forward_to_monnie` を向けるには allow-list への追加とホストごとの recon が要る(未着手・急がない)。**次に手を加える機会があれば、`authorized_keys` をrepoへ入れる**(2026-08-19。いま「どの公開鍵がsandboxを開けるか」はrepoのどこにも無く、実体を見るしかない)。**そのとき排他上書きに注意する** — 既存のsetup系roleは `authorized_keys` を上書きするため、素直に当てると同居する quory の `ann` 鍵を消す。追記型にするかsandbox専用にするかを先に決める | Yoshinobu表明(2026-08-06)。前提・使い方・限界・壊したときの扱いは `docs/ai/context/operations/sandbox-vm.md` が正本 |
| **Testerをcodex側へ移すか(未決)** | Implementer と Reviewer の交換で、codex側に残る未決はTesterだけになった。**`ansible-playbook --syntax-check` はcodex側でも通る**ことを2026-08-09に実測したので、実行可否は除外理由にならない。**判断軸は実ホストへの到達手段の所在である** — Testerはsubagentのうち実ホストへ到達してよい唯一のRoleであり(`docs/ai/policies/execution_boundary_policy.md` EXEC-050)、codexへ移すとその到達手段をcodex側の権限層(`~/.codex/rules/default.rules` と `[sandbox_workspace_write]`)で作り直すことになる。急がない | Yoshinobu決定(2026-08-09)。経路・落とし穴・権限層の正本は `docs/ai/context/operations/agent-messaging.md` |
| **monnie の代わりになる開発機を作るか**(鍵は2026-08-19に切断済み) | **`id_ann` を ansy から削除し、monnie への到達は閉じた**(EXEC-005)。本番の管理は quory の Semaphore で走るため何も止まっていない。**残っているのは「開発とテストで monnie 相当の相手が要るか」だけで、これは不便を実際に測ってから決める**(Yoshinobu、2026-08-19)。`sandbox-mon`(requirement R19〜R21、D3 で別案件へ切り出し済み)がその受け皿になりうるが、当時の目的は「監視スタックのupgradeリハーサル」であり、**今回示された目的(ansy が本番へ触らないこと)の方が広い**。着手時期は未定 | Yoshinobu表明(2026-08-03、Phase 4 の D9 を決めた文脈)。`docs/ai/reviews/dev_prod_boundary/2026-08-03_015_plan_phase4.md` §3.1 |

## Next(着手候補) — システム・運用

| 項目 | 内容 | 根拠 |
|---|---|---|
| **ドリフト検査が「見られなかった」を「差分なし」として通す(2件)** | `roles/deployment_drift_check/tasks/evaluate.yml:142,145`(所有権)と `:240`(禁止ファイル)が、収集`find`の `rc` を見ずに `stdout` だけを読む。`collect.yml:98,140` が `failed_when: false` のため、**収集が失敗した周期は finding が出ず、毎日「差分なし」で通る。** Coordinator が現物で確認済み。**誤検出ではなく検出漏れなので急がない。** 直す方向は「収集失敗そのものを finding にする」で、`--check` と通知経路への影響を見る必要がある | 掃き出し `docs/ai/reviews/undecidable_falls_through_sweep/`。**`\| length` の383ヒットを全件走査して確定したのはこの2件だけである**(未確定18)。`or []` / `or {}` / `or 0` の23件と `\| default(x, true)` の90件も走査済みで確定ゼロ。**計496ヒットを見て確定はこの2件だけだった。** 残るのは `\| default(x)` 素の869ヒットだが、**収穫率と、この家族が「任意変数に既定を与える」定石そのものであることから着手しないと判断した**(Yoshinobu了承のうえCoordinator判断、2026-09-05)。やるなら「コマンド結果・API応答に対する `default()`」へ絞り直す |
| **apt以外のアップデートを機械的に当てる** | Yoshinobu表明(2026-08-23)「update は機械的に行う(人の判断が入らない)」。**aptはそうなっている**(Ubuntu Pro / unattended-upgrades)が、**apt以外は検知までで、適用は人が `dry_run=false` を明示する**。**この原則は現時点でPolicyに書いていない** — 現在形の規範として書くと `UV-035`〜`UV-038`(定期実行を `dry_run=true` に限定)と正面から矛盾するため(2026-08-23の独立レビューが検出)。実現するなら **`UV-035`〜`UV-038` と実装を同じ案件で改訂する**。`roles/prometheus_update_check/` は無人運用向けの機構を既に持つ(チェックサム検証・トランザクションロック・リトライ付きhealthcheck・**失敗時の自動ロールバック**・バックアップ3世代)。**ただし監視の中核を無人で入れ替える変更**なので、requirementとTesterを通す。**Semaphoreは同じ扱いになるが、そもそも検知経路が無い**(本表の別行) | Yoshinobu表明(2026-08-23)。現行の境界は `docs/ai/policies/ubuntu_vm_patch_policy.md` `UV-086` |
| **DLP entropy の既存誤検知(14件)** | 2026-08-23 の corpus scan(**5ルート・376本に絞った母集団**での手分類)で、`high-entropy-string` が **PascalCase の長い識別子と hex 文字列 14 種**を BLOCK していることが分かった。**全追跡ファイル(1,737本)まで広げると、20文字以上の BLOCK は 57 種になる**(内訳の手分類は未実施)。**同日の候補パターン変更より前から BLOCK されており、今回の変更が持ち込んだものではない**(`git show HEAD` で着手前の状態を再判定して確認)。**文字クラスの調整では衝突ゼロに到達しない**ことが4ラウンドで分かっており、直すなら指標か適用範囲の側を変える案件になる。**急がない** — 止まったときは拒否メッセージが `rule_id at pointer` で場所を示すため、書き換えて再送できる | `docs/ai/reviews/oprc_dlp_false_positive/2026-08-23_005_review.md`。判定の境界は `docs/ai/context/operations/operator-request-channel.md` |
| **ansy が自分自身を対象にする playbook を実行できない** | `id_ann` 削除(2026-08-19)以降、`dev_nodes` の group_vars が**存在しない鍵を指す**ため、ansy から ansy 自身への SSH が成立しない。2026-08-23 に `operator_request_channel_client_setup.yml` の配備が止まった(その場は暫定で通し、下記の理由で revert 済み)。**いま困ってはいない** — client は配備済みで、次に ansy が自分へ配備するときに再発する。<br>**素の `ansible_connection: local` を `host_vars/ansy.yml` へ入れてはいけない。** host_vars は inventory のデータで、**quory の Semaphore も同じものを読む**。2026-08-24、これにより quory が `ansy` を対象にした検査で **quory 自身を見て** drift 2件を誤報した(`89e822a` → `9e9daf5` で revert)。**変更系 playbook を流していれば quory が書き換わっていた。**<br>**正しい形は `inventories/homelab/host_vars/quory.yml` に既にある** — `lookup('pipe', 'hostname -s')` でコントローラを見て条件分岐する。**同じ問題が同じ inventory の中で既に解かれていた。**<br>**入れるときの受入条件**: quory から `ansy` を対象に `--check` を流し、**quory ではなく ansy を見ている**ことを確認する。これを確かめずに入れない | `9e9daf5` の commit メッセージ。ドリフトの実測は 8/22・8/23 が 0、8/24 00:40 が 2、revert 後の 07:50 が 0 |
| **template の reconcile が `false` / `{}` を空配列へ畳む** | `roles/semaphore_templates/` の template 側で、API の `arguments: false` や `survey_vars: {}` が **`value or []` で空配列に倒れる**。`false` も `{}` も falsy なため、**型を確かめずに `or` で既定へ流している**。結果、**現物とカタログが食い違っていても `unchanged` を返す**。<br>**HEAD にもある既存欠陥**で、2026-08-24 の有効化ゲート撤去が持ち込んだものではない。**同案件では直さなかった** — 既存欠陥であること、撤去の差分が読みにくくなること、**template の reconcile 挙動が変わるため実 Semaphore に対する受入検証が別途要る**ことによる。<br>**同じ形(型を確かめず truthiness や長さで判断し、判定不能が通す側へ倒れる)が 2026-08-24 に4件出ている** — `semaphore_update_check` の `html_url` を `length > 0` で見た件、同 `null`/数値での評価例外、有効化ゲート撤去での `active` の truthiness、そして本件。**4件とも読解では出ず、実行して出た。4件とも独立レビューが見つけた** | `docs/ai/reviews/semaphore_activation_gate_removal/2026-08-24_006_review.md` |
| **Operator Request Channel の後続2件** | MVPは2026-08-09にクローズ。**残存リスク4件と設計上の申し送りは `docs/ai/reviews/operator_request_channel/2026-08-09_018_closeout.md` §4 が正本**(quory側ライブラリのhash照合手段が無いこと、checkpoint 4のreject方向が原理的に検証不能なこと、spoolに試験messageが4件残ること、**書き込みの門をPOSIX ACLだけと仮定していたこと**)。後続は①**ID専用の通知**(本文はDLP経路だけ、通知は `request_id` しか運ばない) ②**storeの簡素化**(容量会計・イベントログ・conversation索引)。②はquory側Operatorが「一定期間使ってから判断」としていた。**実バグ4件はいずれもstoreと権限の層で、DLPでは1件も出ていない** — 芯と帳簿の切り分けが実測で裏づいた形であり、②の設計入力になる | Yoshinobu決定(2026-08-09にクローズ)。案件記録は `docs/ai/reviews/operator_request_channel/` |
| **証明書の更新が、週次・期限駆動で実際に回るか** | **repo・Semaphore とも配備完了**(2026-08-06)。カタログの `force_renew` 既定値は `false` へ変更し reconcile 済み(`changed: cert_renew` を確認)、`cert_renew_quory.timer` は `Persistent=true` で quory に入り(`unit-cat` で実測)、`cert_renew.yml` の schedule も Yoshinobu が週次・週末へ調整済み。**残るのは観測だけ。** ①次の週次実行が緑で終わること(証明書は8/5に全ノード更新済みで残り45日なので、**当面は「更新せずに緑」が正しい**) ②**実際に更新が走るのは 2026-09-07(日)06:00 の回**で、そこが本番の答え合わせになる(schedule は日曜06:00。8/31 の回は残り19日で閾値に届かず「更新せずに緑」が正しかった)。規範は `docs/ai/policies/cert_renew_policy.md` CERT-024。**承知の上の残存リスク** — `prepare_ca_apply`(CA鍵のtmpfs展開)は `cert_needs_renewal` ではなく `not ansible_check_mode` だけでgateされているため、更新不要な週も毎回展開される(年12回→52回)。抑えるなら `issue_check` を全ホストで先に回す形になるが、playの順序組み替えを伴うので別案件 | Yoshinobu決定(2026-08-06)。数値は `roles/homelab_cert_renew/defaults/main.yml`(valid 45 / threshold 15) |
| **一次調査成果物の保持期間と、滞留の検知** | `_investigations/` は消す仕組みを持たず、拾われないまま溜まった成果物を知る経路も無い(IC-021の一次調査への適用)。**Policy §8が「未決」として明示している項目のうち、一次調査が本番稼働に入ったことで実際に効き始めた2件**である。バンドル本体は `incident_capture_retention_days`(30日)で消えるため、成果物だけが残り続ける | `docs/ai/policies/incident_capture_policy.md` §8 |
| Jinjaの`strftime`フィルタが**コントローラの暗黙システムTZに依存**している(**2箇所**) | `roles/proxmox_snapshot_check/tasks/main.yml:57` と `playbooks/recovery_monitoring_check.yml:103,137`。Jinjaの既定(`utc=False`)を使うため、ansyのシステムTZが変わると出力もずれる。**「repo内で唯一」ではない** — 2026-08-03の独立レビューが2件目を検出した(1件目しか知らないまま規範文書へ「唯一」と書き、その誤りが同レビューで指摘された)。**急がない、かつ安易に直すと悪化する** — `%z` が実オフセットを出すので**TZが変わっても嘘にはならない**。`+09:00` の直書きは UTC の値に JST ラベルを付ける「詐称」になる。規約そのものは `skills/ansible-implementation-style/SKILL.md` が正本 | `docs/ai/reviews/ubuntu_nightly_reboot_check/2026-07-30_004_review_jst_sweep.md`、`docs/ai/reviews/norm_docs_convention_relocation/2026-08-03_001_review.md` |
| **`proxmox_patch_dryrun`の到達性判定を`proxmox_reachable_nodes`へ寄せ替える** | **機能の穴ではない。単一node時にパッチ情報を取れることは実装済みで動いている。** 残っているのは判定機構が2つ並存していることで、**判定の起点が違う** — roleは明示的な`ping` probe、`proxmox_patch_dryrun.yml`は`gather_facts`の結果(`ansible_facts \| length > 0`、同ファイル49-53行のコメント参照)。差が出るのはfact cachingが有効なときだけで、そのとき**dryrun側だけが**停止中のnodeを到達可能と誤判定する。寄せ替えれば、Semaphore側のfact caching設定に依存しなくなる。着手を外した理由は、weekly full chainのapply gateが実データで未観測の段階で作り直すと回帰の切り分けができないこと | `docs/ai/reviews/proxmox_readonly_check_single_node/2026-07-30_001_requirement.md` §5 P1 |
| **`authy` / `monnie` 側にも同じ構造が残っている** | `recovery_exec_targets` を回す `roles/recovery_exec/tasks/target_setup.yml` の各タスクは、pve 側と同じく `delegate_to` のループで到達性を判定しない。どちらかが停止していれば `recovery_exec_setup.yml` は同じ形(ループ1件の unreachable が task 全体へ昇格し play が打ち切られる)で rc=4 になる。**pve 側は 2026-08-16 に probe + 絞り込みで解消したが、こちらは対象外とした** — 観測された事象が pve に限られたため(requirement §5 の P2 = R8)。**同じ直し方がそのまま使える。** 着手の引き金は authy / monnie を計画停止する運用が入るとき | `docs/ai/reviews/pve_unreachable_handling/2026-08-16_001_requirement.md` §5 R8 |
| **Semaphore の新版検知を自動化するか(未着手)** | **適用そのものは2026-08-18に手動で完了した**(ansy / quory とも 2.19.8)。**手順の正本は `docs/ai/reviews/semaphore_upgrade/2026-08-18_002_manual_procedure.md`** で、次回の版上げもこれを使えばよい。**残っているのは「新版が出たことを知る経路が無い」ことだけである** — apt リポジトリが存在せず、GitHub Releases を見に行くしかない。方針は決定済み(Yoshinobu、2026-08-10): **自動適用はしない。** `dry_run=true` の検知だけを回し、当てるときは手動。雛形は `roles/prometheus_update_check/`(GitHub Releases API → 差分判定 → 通知、`dry_run` 明示必須の fail-closed)。**検知だけなら Semaphore の schedule に載せてよい** — 自分を再起動しないため。**着手条件だった「quory 側の現在版の実測」は解けた** | Yoshinobu決定(2026-08-10)。インストール形態と版上げの制約は `docs/ai/context/system/semaphore.md`「インストールと版上げ」が正本 |
| **次の Semaphore 版上げで community 版へ寄せる** | 現在は非 community 版が入っている。**ライセンス上の問題は無い**(`.deb` のメタデータはどちらも `License: MIT` で区別を宣言していない)が、**バイナリが 100.4MB 対 49.6MB** で、使っていない Pro 機能のコードを倍載せている。**単独では切り替えない** — 機能的な見返りがゼロの本番バイナリ差し替えになるため、**版上げと同時なら追加コストは実質ゼロ**。前提の `executor_image` 空 / `runner` 0件は2026-08-19に quory で確認済み(切り替える直前に再測する)。**手順書の3節に同じことを書いてあり、次回そこで読まれる** | Yoshinobu提起(2026-08-19)。`docs/ai/reviews/semaphore_upgrade/2026-08-18_002_manual_procedure.md` §3 |
| **Semaphore 2.19.8 が受理する cron grammar が未実測** | schedule カタログの preflight は、標準の5フィールド cron を受理し判定できないものを拒否する保守的な検査に留まる。**当該版が実際に何を受理するかを測っていない**ため、Semaphore が拒否する cron をカタログへ書いたときに preflight が通してしまう可能性がある。**2026-08-18の版上げで前提が変わった** — 測る対象は 2.18.4 ではなく 2.19.8 になり、さらに **2.18.28 が cron 検証をJSライブラリからバックエンドendpointへ変えている**ため、検査の性質そのものが変わっている可能性がある。**効くのは cron を変更するときだけで、現在の20件は稼働中の実値をそのまま転記したもの**。既存20件を valid fixture、当該版が拒否する代表値を invalid fixture として固定すれば閉じる | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-10_025_closeout.md` §3、`docs/ai/reviews/semaphore_upgrade/` |
| **規範文書間の突合を定期的に自動でかける仕組みの要否** | Auditorは案件クローズ時にしか起動しないため、案件が動いていない期間の規範ドリフトは拾えない。2026-07-29のCoordinator自己レビューで6件超の欠陥が見つかったが、これは人間が明示的に求めた1回限りの検出であり再発防止の仕組みではない。月次Knowledge振り返りの拡張が候補 | `docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md` §4 |
