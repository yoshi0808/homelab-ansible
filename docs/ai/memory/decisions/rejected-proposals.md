# 退けた提案の記録 — 再提案を止めるための索引

決定日: 個別に記載 / 記録: Coordinator

## この記録の使い方

**通常は読まない。** 解決策がすぐに思いつかないとき、判断に迷ったときに辿る(Yoshinobu、2026-08-18)。常に読み込ませる形にはしない。

**やらないと決めたもの**を置く。判断の芯と、ここにしか無い制約だけを書く。経緯は一次記録(`docs/ai/reviews/`、`docs/ai/memory/incidents/`)と commit にある。

`docs/ai/memory/decisions/README.md` は「経緯の既定の置き場はcommitメッセージであり、独立ファイルを起こすのはcommitを辿らせるだけでは同種の提案を止められないときに限る」と定めている。**本ファイルはその例外に当たる** — ここに並ぶ提案は、commitに理由が書かれていてもなお再び持ち出された形をしている。

2026-08-18に `docs/ai/status.md` から移設した。status.mdは「今どこにいて何を待っているか」の正本であり、**退けた案の一覧はそのどちらでもない**ため(Yoshinobu指摘)。

## 記録

- **Ubuntu と Proxmox の Status 語彙を統一すること** — 2026-08-23 Yoshinobu不採用(「別にproxmoxのパッチと統一したいとも思いません」)。**両者は5値で構造が同じだが、同じ位置の語が別の意味を持つ** — Proxmoxの `MAINTENANCE_REQUIRED` は**自動適用の条件**(`remove_count=0` なら無人で当たる)であるのに対し、Ubuntuの `REVIEW_REQUIRED` は**人が中身を見るべき**という助言でしかない(Ubuntu側に自動適用は無い)。**揃えると、片方にしか無い意味が読み手に付いてくる。** `PATCH_READY` ↔ `UPGRADE_READY` も同様。**Proxmox側は5値が `proxmox_operations_policy.md` で定義済みで自動適用を実際に動かしているのに対し、monthly `ubuntu_vm_full_upgrade` のStatus経路に自動適用は無く(`REVIEW_REQUIRED` と `UPGRADE_READY` の差は重大度だけで適用可否を変えない)**(UV-090) — この非対称が統一を退ける理由である
- **prometheus を 3.14 系へ上げること** — 2026-08-22 Yoshinobu決定、**3.13 LTS に留まる**。3.13.0 が LTS で、現在の 3.13.2 はその最新パッチ(CVE 2件の修正を含む)。**3.14.0 は通常の機能リリースであり、上げることは「上げる」ではなく「LTS から降りる」ことになる。** 3.14.0 の `[CHANGE]` 5件は、当環境の dashboard・alert rule・scrape 設定がいずれも使っていない — 危険だから見送ったのではなく、得るものが無い。**次に当てるのは 3.13.3 が出たとき。**
  **月次は事実を reason に載せるが、Status は上げない**(UV-032 / UV-094、2026-08-23 改訂)。系統を移すかどうかは人が決めるものであり(UV-087)、機械は提示に留まる。**週次の検知は 3.13 系の中だけを見る**(UV-088)。
- **Codexのstop-time review gate**(Stop hookで直前ターンを審査) — 2026-08-09 Yoshinobu撤回。機構は正しく動いていた(誤検知0)。**退けられたのは検出能力ではなく繋ぎ方** — requirement・Policy・Contextと照合しないためReviewerの代わりにならず、工程を1層積むだけ。採る形はagmsg経由でcodexへReviewerを依頼する側。**制約: `/codex:review` と `/codex:adversarial-review` は `disable-model-invocation: true` で登録されており、Coordinatorからもsubagentからも起動できない**(呼ぶなら `codex-companion.mjs` を直接実行)
- **quoryのCodex向けSemaphore read-only MCPの案件化** — 2026-08-09 Yoshinobu保留。Reviewerからの依頼であり職掌の外。**ansy側には既に実体があり、codex側ReviewerはansyのSemaphore APIへread-onlyで到達できる**(`~/.codex/tools/semaphore-readonly-mcp.py`、repo外・GETのみ・`~/.codex/config.toml` に登録済み)。依頼文で「読み取りのみ可」と書いたときの実効性が変わる。再開時に決めるのはidentity / 能力境界 / 配備経路 / GETのallowlistの4点。**`semaphore-templates-api-token` は書込能力を持ちうるため流用しない**
- **`deployment_drift_check` にquoryの作業ツリーのclean判定を足すこと** — 2026-08-07 Yoshinobu却下。**退けられたのは検査の当否ではなく積み増しそのもの**(「場当たり的な対応でよく分からなくなるのが一番困る」)。**同種の提案の前に、それが「乱立」を1つ増やす側かを先に問う。** 検知の穴は `docs/ai/memory/incidents/2026-08-07_incident-investigation-notification-silent-since-deploy.md`
- **「巻き添えが大きいから資格情報を失効させない」という判断** — 2026-08-06 Yoshinobu却下(「放置できないでしょ」)。実際は同日中に完了した。**巻き添えは作業手順で吸収できる種類で、資格情報が生きていることと釣り合う天秤ではない。** `incidents/2026-08-06_slack-token-leak-via-environ-dump.md`
- **証明書の期限を独立に見る仕組み** — 2026-08-06 Yoshinobu不要と決定。**前提だった問題が週次化で消えたため。** 期限を見ているのが `cert_renew` 自身だけという構造は変わっていないので、**実行間隔を空ける変更をするときはこの判断の前提が消える**
- **sandboxを週次でベースラインへRestoreすること** — 2026-08-06 不採用。**乖離の懸念がこの案自身によって作られる** — sandboxは `unattended-upgrades` で既に追随しており、週次で巻き戻すと毎週打ち消して振動する。**「綺麗な状態が要る」の引き金は曜日ではなく、これから走らせるテストがそれを要求するとき**
- **Semaphoreにsandbox の VM Restore ボタンを作ること** — 2026-08-06 今は作らない(Coordinator判断)。頻度という前提が未観測。引き金は「壊す頻度」ではなく「綺麗な状態へ戻したい頻度」。**制約: 作るときは対象VMをsurveyパラメータにせず `sandbox` に固定する**(打ち間違いで本番VMを巻き戻せてしまう)
- **sandboxへ恒久的な開発環境を作ること** — 2026-08-06 Yoshinobu却下。**作り込むと壊すのが惜しくなり、使い捨てであること自体の価値が失われる。** 正本は `docs/ai/context/operations/sandbox-vm.md`
- **月次の見直しを無人セッションに行わせること** — 2026-08-03 Yoshinobu廃止決定。`claude -p` 2本を廃止し、timerは通知のみ。**同種の提案の前に「いつのベースラインに対する振り返りか」を確かめる**
- **案件記録の未来日付を弾く検査** — 2026-08-04 様子見(「日付はあまりクリティカルにならない」)。**頻度が増えたら作る。作るなら「未来の日付だけを弾く」形**(過去日付は正当なので偽陽性が原理的に出ない)。**規範へ「日付は実測せよ」の1行を足す案は採らない — 文章では止まらない**
- **`cloudkey.internal:8443` の自己署名** — 2026-08-05 Yoshinobu放置と決定。**UniFi製品の設計であり使っていない**(アクセスは443のみ、そちらは検証を通ることを実測済み)。**次に誰かがポートを覗いて「自己署名がある」と言い出したときのための記録**
- **`worktree_sync` の排他を外すこと** — 2026-08-05 Yoshinobu現状維持。前提だった「Semaphoreが作業ツリーを共有する」は誤りだが、**実際に使う実行主体が別にいる**(`ansible-cert-renew-quory.service` の `WorkingDirectory`)。**外すなら守る相手を付け替える形が正しい**(単に消すのではなく)
- **reboot後のpost-check待ち時間をPolicyへ規定すること** — 2026-08-05 規定しないと決定。120秒は方針1のホスト専用の実装細部で、根拠はコード側のコメントにある。**Policyは許可・禁止・停止条件を定めるものであり、タイムアウト値はその形をしていない**
- **調査結果を入力とする修正依頼の自動起票(R15)** — 2026-08-01 Yoshinobu却下
- **Policy ID(`SB-nnn` 等)の参照切れ検査** — 2026-08-01 不採用。素朴に実装すると**規範層の検出8件が全件偽陽性**(いずれも「退番: SB-049(再利用しない)」という正しい記載)。同じ罠は `skills/document-norm-review/SKILL.md` L98 が明文化済み。`docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_001_survey.md` §3.3
- **`.claude/settings.json` の `autoMode` とcoordinator.mdの保護対象ホスト一覧の突合検査** — 同日不採用。既知の二重化だが**両側とも散文の中に集合が埋まっており機械抽出できない**。**検査ではなく構造で直す対象**(片方を機械可読にし他方が参照する)。同上 §3.3
- **規範文書どうしの「意味の矛盾」の機械検査** — `check-doc-consistency.py` はリンク解決と値比較しか行わず、**「リンク先は実在するが主張が矛盾している」クラスは原理的に検出できない**。2026-08-01に実際に発生し独立レビューが捕まえた。**検査で置き換えられるものではないことの実例。** 同フォルダ `2026-08-01_007_review_policy_rename.md`
- **収集器へ「消費済みidの記憶」防御を入れること** — 見送り。「消費済み」の正本は**spoolファイルが存在しないことの1つのみ**で、state.jsonへの二重化は両者が食い違う新しい欠陥クラスを生む。`.../incident_auto_capture/2026-07-28_018_acl_mask_plan.md` D7
- **ACL付きパスへのchmodをpre-commitで検査すること** — 見送り。**検査対象がパス変数の解決を要する**ためgrepでは現に壊れている箇所を1件も拾えない(実証済み)。**効かない検査は「掃引済み」という誤った安心を生む。** 同上 D9
- **一次調査のAC5(封じ込め)の負経路の実行検証** — 不要。到達できないことは鍵パス直書き・`0600`・親ディレクトリ `0750`・グループ非所属の4点で**構造的に決まる**(2026-07-31にquory実機で観測)。**時間ではなく変更によってしか崩れないため、守る場所は `roles/incident_inspect/tasks/main.yml` 冒頭のコメント**
- **proxmox_patch_dryrun / proxmox_exec_node_selection の「両ノード同時到達不能」の実地検証** — pve2停止が必要で許可範囲外。decoyでは独立にPASS、残存リスクとして各案件のtest_resultに記録済み。**同型の2件が別々の案件で同じ理由により未検証**
- **既知条件由来の捕捉が全体に占める割合(実測値)** — `docs/ai/policies/incident_capture_policy.md` IC-022 が正本。規律2により値をここへ写さない
