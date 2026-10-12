# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)はここに書かない。対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。

## このファイルの規律

1. **完了したら行を消す。履歴を残そうとしない。** 履歴は `git log` が持つ。
2. **値を二重に持たない。** 他に正本があるものは参照だけ書く。

## Now(進行中)

**障害捕捉の `--check` 継承の修正(案件3): 2026-10-26の観測待ち**(`docs/ai/reviews/capture_check_mode_inheritance/`)。10/26の月次振り返りのときに、9/27 20:44(commit `02edaed`)以降、`reports/incidents/_spool/` と収集後のバンドルに `check_mode: true` の記録が1件も無いことを、Coordinatorが `quory-investigate` の読み取り語彙で確かめる。不具合は「`--check`」と「自律復旧の3 roleかubuntu月次full-upgradeからの通知」が重なったときだけ起きるため、特定のDry Runを押して観測する方式は取らない。

**NVMe error-log増加を参考扱いに(`docs/ai/reviews/storage_monthly_error_log_note/`): 10月の月次点検の観測待ち**。pushでquoryへ自動反映される。10月の月次点検(Semaphoreのschedule)のNotionレポートで、pve2のerror-logが増え、かつほかのNVMe健康条件(媒体エラー0・重大警告なし・予備領域がしきい値以上)が正常なら、総合判定が「問題なし」のまま「## 参考」に「NVMeが拒否したコマンドの記録が+N件」が出ることを、Yoshinobuが貼ったレポートでCoordinatorが確かめる。

**Operatorの調査鍵(`docs/ai/reviews/operator_investigate_key/`)とLokiの固定文字列検索(`docs/ai/reviews/loki_text_filter/`): 配備済み、残り1点**。配備は #1362(2026-10-05)と、`loki-text all` の不具合修正の #1419(2026-10-10、`all` で全jobを検索できることをansyから確認済み)。Operatorの鍵(AC9)と障害捕捉の収集器の経路(AC9b)は確認済み。残りは、自律復旧のCodex(sandbox経由)が次に調査を走らせたとき、wrapperの `denied: investigation wrapper requires` が出ていないこと(ansyでの実測を根拠に受け入れ、quory上では未観測)。

**Wi-Fiテレビの切断(5GHzチャンネル入れ替えの実験): 2026-10-13に結果をまとめる**。テレビ(MAC `00:16:f5:22:da:86`)は1階のAP(u7-1f)にLock to AP中。2026-10-06 07:07に5GHzのチャンネルを入れ替えた(1階 36→52、2階 52→36。Yoshinobuが操作)。入れ替え前の7日間で、テレビの再送過多(`Excessive Retries`)による切断は2件(10/5 07:12 u7-2f、09:36 u7-1f)。入れ替え後のテレビの再送過多を数え、件数が0〜1件なら一時的なものとみなす。家族のiPhoneの切断(圏外へ出たとき・眠っている間)は除外する。手段は `ssh monnie-investigate loki-text network-devices <since> 7d Excessive`。結果をYoshinobuへ報告し、1階を元のch36(DFS対象外)へ戻すかはYoshinobuが決める。UniFiの設定は人が操作する。

**ansy内のCodexの役を `codex exec` へ移す(`docs/ai/reviews/codex_exec_roles/`、ADR-016): repo外の変更と実機確認の待ち**。repo内(`scripts/codex-role.sh`、規範・Context、`.codex/rules`)は実装・レビュー済み。残りはrequirement R5(ansyの `new-session.sh` からImplementerを外す、agmsgのteam `homelab` の登録を外す、`~/.codex/config.toml` のwritable_rootsからagmsgを外す、Codexのagmsg hookとshimを外す)と、AC6(`--reset` 後にpane 0だけが上がり、`actas` なしで受信の監視が始まる)・AC7(Implementerがagmsgで送れない)の確認。Coordinatorが行う。

**月次full-upgradeでauthy / monnieのhealthcheck WARNINGを通知する(`docs/ai/reviews/ubuntu_full_upgrade_warning_drop/`): 次の月次自動発火の観測待ち**。2026-10-12にcommit `30da754`。次の月次の自動発火で、authyかmonnieのhealthcheckが `WARNING` を出したら、Slackの通知にその項目が載ることをCoordinatorが確かめる。`WARNING` が出なかった月は観測にならないので、出る月まで持ち越す。

## Next(着手候補) — 工程・体制

| 項目 | 内容 | 根拠 |
|---|---|---|
| **Policy改訂案(playbook一覧・Policy監査の仕分けC)** | 実装にPolicyの記述が追随していない、または両立しない約20件(SB-025の判定の並びを含む)。改訂案を起こしてYoshinobuが判断する(Yoshinobu了承、2026-09-26)。**実装側を直す案件2〜5(Proxmoxパッチの判定と停止 / 障害捕捉の書き込み / ubuntu系 / 小粒の束)も同じ集約から起こす**。急がない | `docs/ai/reviews/playbook_catalog_policy_audit/2026-09-26_005_summary.md` |
| **Loki検索結果のIPアドレスをマスクする** | 開発・運用の調査語彙(`recovery-loki-helper`)が返す本文のIPアドレスを、返す段階で伏せる(Lokiへの取り込み前に伏せる案は、sshdの接続元やWi-Fi端末のIPなどIPしか手がかりが無いログが多く、調査ができなくなるため採らない。Yoshinobu、2026-10-05)。repoと会話へIPが書き写される経路を塞ぐのが目的。上の2案件の配備後に着手する | Yoshinobu表明(2026-10-05) |
| **規範監査の残余(小粒3点)** | 2026-08-25の横断監査は第1束・第2束とも実施済みでクローズ(Auditor受入=`_014`)。残るのは①findings 3本の「未確認」節のうち巻き取られていない項目 ②C3-3(現在は一致している複製群の扱い) ③credential保管pathの2Policy間のねじれ(`_013`のCoordinator判断節)。いずれも急がない。次の監査サイクルでまとめて判断する | 案件記録 `docs/ai/reviews/norm_docs_audit/` |
| **`docs/ai/roles/` 5本のプロンプト最適化(継続案件)** | Coordinator / Implementer / Reviewer / Tester / Auditorの各Role文書を、**実際に運用してみて出てきた歪みを持ち寄って協議しながら**直し続ける。対象は①**やること・やらないことの衝突**②**何を言われているのか読み取れない箇所**③**細かく指示するよりAIに任せた方が結果が良い箇所**の3クラス。一度に全部やる案件ではなく、気づいたものを溜めて定期的に議論する形を採る | Yoshinobu表明(2026-08-01)「ある程度最適化して随分良くなってきたが、まだ矛盾・不明瞭・非効率が残る」。**歪みの実例はCoordinatorが運用中に気づいた時点で書き溜める**(置き場は本行)<br><br>**実例1(2026-09-14)**: 計画Reviewerが承認の「後ろ」に置かれているため、**Yoshinobuの承認が出た瞬間に実装へ行きたくなり、査読が飛ぶ**。実際この日、dispatch語彙の案件で計画Reviewerを一度も起こさなかった(依頼文の「既存20件」が現物23件と食い違う誤りは、1工程後ろのImplementerが拾った)。2つのゲートは見ているものが違う — Yoshinobuは**やってよいか**、計画Reviewerは**計画として成立しているか**。Yoshinobuがどれだけ丁寧に読んでも後者の誤りは出てこない。**直す方向は「気をつける」ではなく順序** — requirementを書いたら、Yoshinobuへ計画を出すのと**並行に**計画Reviewerへ投げる。直列に足すと承認から着手までが伸び、同じ力がまた働く。Yoshinobu了承のうえ本案件で扱う(2026-09-14) |
| **Alloy Phase 3(Lokiのログから不調の予兆をアラートする)** | 2026-07-20に**意図的に保留**した。閾値(error/warningの急増など)を先に決め打ちすると誤検知が多いため、ログを溜めて分布とノイズを見てから閾値を設計する。**着手するときは最初に「データは溜まったか」を確かめる**。Lokiのデータは2026-07-26に一度消去しているので、溜まっているのはそれ以降の分である | 要求仕様 `docs/ai/reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md`、棚卸し `2026-07-19_loki_content_survey.md`、消去の記録 `2026-07-26_031_test_result_loki_data_wipe.md`。status.mdへの記載はYoshinobu了承(2026-09-26) |
| **sandbox を検証環境として使い込む** | **inventory 登録と `serial_getty_mask` は2026-08-06に完了**(`b20c43d`。`NRestarts=20322` の agetty ループを停止、hostname も `ubuntu` から `sandbox` へ)。承認境界でも `monnie` / `ansy` と同じ「確認不要」側にある。**ここから先は使い道の話であって、必須の作業ではない。** Yoshinobu が挙げた候補は ①monnie のサービスの検証 ②**まだAnsibleへ移行していない FreeRADIUS**(`authy`)— ただしクライアント/サーバのテスト用公開鍵を一度置く必要があり、かつ RADIUS は設定をほとんど変えないため**費用対効果は未評価**。**この行の要点は「decoy より広く試せる実ホストが手に入った」ことで、個々の候補ではない。** 監視対象にはしない。`rsyslog_forward_to_monnie` を向けるには allow-list への追加とホストごとの recon が要る(未着手・急がない)。**次に手を加える機会があれば、`authorized_keys` をrepoへ入れる**(2026-08-19。いま「どの公開鍵がsandboxを開けるか」はrepoのどこにも無く、実体を見るしかない)。**そのとき排他上書きに注意する** — 既存のsetup系roleは `authorized_keys` を上書きするため、素直に当てると同居する quory の `ann` 鍵を消す。追記型にするかsandbox専用にするかを先に決める | Yoshinobu表明(2026-08-06)。前提・使い方・限界・壊したときの扱いは `docs/ai/context/operations/sandbox-vm.md` が正本 |
| **monnie の代わりになる開発機を作るか**(鍵は2026-08-19に切断済み) | **`id_ann` を ansy から削除し、monnie への到達は閉じた**(EXEC-005)。本番の管理は quory の Semaphore で走るため何も止まっていない。**残っているのは「開発とテストで monnie 相当の相手が要るか」だけで、これは不便を実際に測ってから決める**(Yoshinobu、2026-08-19)。`sandbox-mon`(requirement R19〜R21、D3 で別案件へ切り出し済み)がその受け皿になりうるが、当時の目的は「監視スタックのupgradeリハーサル」であり、**今回示された目的(ansy が本番へ触らないこと)の方が広い**。着手時期は未定 | Yoshinobu表明(2026-08-03、Phase 4 の D9 を決めた文脈)。`docs/ai/reviews/dev_prod_boundary/2026-08-03_015_plan_phase4.md` §3.1 |
