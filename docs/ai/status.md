# 現在地(status)

状態: **正本**(2026-07-27新設)

このファイルは「**今どこにいて、何を待っているか**」の正本である。規範(どう振る舞うか)はここに書かない。対話セッションは `/clear` のたびに文脈を失うが、このファイルとgitの現物があれば現在地を復元できる状態を保つ。

## このファイルの規律

1. **完了したら行を消す。履歴を残そうとしない。** 履歴は `git log` が持つ。
2. **値を二重に持たない。** 他に正本があるものは参照だけ書く。

## Now(進行中)

**incident-captureの分類変更: 2026-09-28(月)の観測待ち**。成功ジョブの `info` / `warning` 通知が相関先なしで収集エラー扱いになり、週1回 `Failed to start homelab-incident-capture.service` が出ていた件を直した(案件クローズ、`docs/ai/reviews/incident_capture_exit_semantics/`)。**配備は2026-09-23に完了した**(ジョブ#1210 success、`deployed-hash incident-capture-collector` がrepoの現物と一致)。**2026-09-28(月)09:00**の `SAFE: Syslog weekly digest` の成功通知のあと、09:05の収集周期で `Failed to start` が出なければ狙いどおり。

## Next(着手候補) — 工程・体制

| 項目 | 内容 | 根拠 |
|---|---|---|
| **規範監査の残余(小粒3点)** | 2026-08-25の横断監査は第1束・第2束とも実施済みでクローズ(Auditor受入=`_014`)。残るのは①findings 3本の「未確認」節のうち巻き取られていない項目 ②C3-3(現在は一致している複製群の扱い) ③credential保管pathの2Policy間のねじれ(`_013`のCoordinator判断節)。いずれも急がない。次の監査サイクルでまとめて判断する | 案件記録 `docs/ai/reviews/norm_docs_audit/` |
| **`docs/ai/roles/` 5本のプロンプト最適化(継続案件)** | Coordinator / Implementer / Reviewer / Tester / Auditorの各Role文書を、**実際に運用してみて出てきた歪みを持ち寄って協議しながら**直し続ける。対象は①**やること・やらないことの衝突**②**何を言われているのか読み取れない箇所**③**細かく指示するよりAIに任せた方が結果が良い箇所**の3クラス。一度に全部やる案件ではなく、気づいたものを溜めて定期的に議論する形を採る | Yoshinobu表明(2026-08-01)「ある程度最適化して随分良くなってきたが、まだ矛盾・不明瞭・非効率が残る」。**歪みの実例はCoordinatorが運用中に気づいた時点で書き溜める**(置き場は本行)<br><br>**実例1(2026-09-14)**: 計画Reviewerが承認の「後ろ」に置かれているため、**Yoshinobuの承認が出た瞬間に実装へ行きたくなり、査読が飛ぶ**。実際この日、dispatch語彙の案件で計画Reviewerを一度も起こさなかった(依頼文の「既存20件」が現物23件と食い違う誤りは、1工程後ろのImplementerが拾った)。2つのゲートは見ているものが違う — Yoshinobuは**やってよいか**、計画Reviewerは**計画として成立しているか**。Yoshinobuがどれだけ丁寧に読んでも後者の誤りは出てこない。**直す方向は「気をつける」ではなく順序** — requirementを書いたら、Yoshinobuへ計画を出すのと**並行に**計画Reviewerへ投げる。直列に足すと承認から着手までが伸び、同じ力がまた働く。Yoshinobu了承のうえ本案件で扱う(2026-09-14) |
| **Alloy Phase 3(Lokiのログから不調の予兆をアラートする)** | 2026-07-20に**意図的に保留**した。閾値(error/warningの急増など)を先に決め打ちすると誤検知が多いため、ログを溜めて分布とノイズを見てから閾値を設計する。**着手するときは最初に「データは溜まったか」を確かめる**。Lokiのデータは2026-07-26に一度消去しているので、溜まっているのはそれ以降の分である | 要求仕様 `docs/ai/reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md`、棚卸し `2026-07-19_loki_content_survey.md`、消去の記録 `2026-07-26_031_test_result_loki_data_wipe.md`。status.mdへの記載はYoshinobu了承(2026-09-26) |
| **sandbox を検証環境として使い込む** | **inventory 登録と `serial_getty_mask` は2026-08-06に完了**(`b20c43d`。`NRestarts=20322` の agetty ループを停止、hostname も `ubuntu` から `sandbox` へ)。承認境界でも `monnie` / `ansy` と同じ「確認不要」側にある。**ここから先は使い道の話であって、必須の作業ではない。** Yoshinobu が挙げた候補は ①monnie のサービスの検証 ②**まだAnsibleへ移行していない FreeRADIUS**(`authy`)— ただしクライアント/サーバのテスト用公開鍵を一度置く必要があり、かつ RADIUS は設定をほとんど変えないため**費用対効果は未評価**。**この行の要点は「decoy より広く試せる実ホストが手に入った」ことで、個々の候補ではない。** 監視対象にはしない。`rsyslog_forward_to_monnie` を向けるには allow-list への追加とホストごとの recon が要る(未着手・急がない)。**次に手を加える機会があれば、`authorized_keys` をrepoへ入れる**(2026-08-19。いま「どの公開鍵がsandboxを開けるか」はrepoのどこにも無く、実体を見るしかない)。**そのとき排他上書きに注意する** — 既存のsetup系roleは `authorized_keys` を上書きするため、素直に当てると同居する quory の `ann` 鍵を消す。追記型にするかsandbox専用にするかを先に決める | Yoshinobu表明(2026-08-06)。前提・使い方・限界・壊したときの扱いは `docs/ai/context/operations/sandbox-vm.md` が正本 |
| **monnie の代わりになる開発機を作るか**(鍵は2026-08-19に切断済み) | **`id_ann` を ansy から削除し、monnie への到達は閉じた**(EXEC-005)。本番の管理は quory の Semaphore で走るため何も止まっていない。**残っているのは「開発とテストで monnie 相当の相手が要るか」だけで、これは不便を実際に測ってから決める**(Yoshinobu、2026-08-19)。`sandbox-mon`(requirement R19〜R21、D3 で別案件へ切り出し済み)がその受け皿になりうるが、当時の目的は「監視スタックのupgradeリハーサル」であり、**今回示された目的(ansy が本番へ触らないこと)の方が広い**。着手時期は未定 | Yoshinobu表明(2026-08-03、Phase 4 の D9 を決めた文脈)。`docs/ai/reviews/dev_prod_boundary/2026-08-03_015_plan_phase4.md` §3.1 |
