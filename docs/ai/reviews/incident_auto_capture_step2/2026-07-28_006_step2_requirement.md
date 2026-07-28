# Step 2(転送と評価)— requirement

- 作成: 2026-07-28 Coordinator
- 対象: 障害の自動捕捉パイプラインの残り2段 — **転送(quory→ansy)** と **評価(ansy・月次)**
- 状態: **確定**(Tech Leadへの入力)
- 案件のTier: **Tier 4**(軸A。複数ホストのorchestration、無人実行の権限プロファイル変更、未決の設計判断が複数)。軸Bによる `+R` は付けない(Tier 3/4はReviewerを工程内に含む)
- 正本: 許可・禁止・停止条件は `docs/ai/policies/incident_capture_policy.md`(IC-001〜IC-032)。**本requirementはPolicyの下位にあり、競合したらPolicyを優先する。**

## 1. 問題定義(観測された事実のみ)

因果は組み立てない。**判断はTech Leadが現物で確かめて行うこと。**

| # | 観測 | 一次記録 |
|---|---|---|
| O1 | 捕捉(段1)は本番quoryで稼働中。`homelab-incident-capture.timer` が5分毎に収集器を起動し、バンドルを **quory自身のローカル** `reports/incidents/` へ書く | `2026-07-28_004_quory_units_survey.md` 観測1・2 |
| O2 | **quory→ansy へファイルを運ぶ実装は存在しない。** 稼働unit 3系統すべての `ExecStart` 実体を全文検索し、転送語彙0件。cron・user timer・常駐プロセスにも該当なし | 同 観測2・4・5 |
| O3 | quoryとansyは**同一の絶対パス**(`/home/yoshi/homelab-ansible`)に**独立したgit checkout**を持つ。`reports_base_dir` がgroup_varsの絶対パス値であるため、両ホストの `reports/incidents/` は同名だが別物 | 同 観測3、`inventories/homelab/group_vars/all.yml:1` |
| O4 | quory側のバンドル保持は `incident_capture_retention_days: 30`(ディレクトリmtime基準) | `roles/incident_capture/defaults/main.yml:59` |
| O5 | 月次評価の器は既存。ansyの `ansible-knowledge-review.timer` が毎月26日に `claude -p` を起動する。その読取allowlistは `Read(docs/**)` と `Read(skills/**)` のみで、**`reports/` を含まない** | `roles/knowledge_review/templates/job-settings.json.j2:28-34` |
| O6 | 月次評価は `git status --porcelain` が非空なら**何も書かずに中止**する(`ABORTED_DIRTY`、Slack warning、`fail` させない)。迂回変数はtimerから渡らない | `roles/knowledge_review/tasks/main.yml:27-51`、`defaults/main.yml`、`templates/knowledge-review.service.j2` |
| O7 | 月次評価自身も差分を作業ツリーに残し、commitはしない(`deny: ["Bash"]` により手段が無い)。中止理由の文言も「先月分の昇格結果が未commitの場合もここで止まる」と、正常運用での中止を前提にしている | `roles/knowledge_review/tasks/main.yml:44-51`、`templates/job-settings.json.j2:35-39` |
| O8 | 同roleには既に「`claude -p` の標準出力をAnsibleが確定的にファイル化する」形が実装されている | `roles/knowledge_review/tasks/main.yml:175-192` |
| O9 | `.gitignore` の `reports/` 除外は**拡張子3つ**(`.json` / `.log` / `.md`)のみ。ディレクトリ単位ではない。`reports/incidents/` 配下に追跡中のファイルは無い(`git ls-files reports/` は `reports/radius-health/` の2件のみ) | `.gitignore` 冒頭3行、`git ls-files reports/` |
| O10 | ansy側にも `reports/incidents/` ディレクトリが実在する(2026-07-27作成)。由来は未確認 | `ls -la reports/` |
| O11 | Tester接続identity(`ann`)と所有者(`yoshi`)が異なるため、**quory側の作業ツリー状態をTesterが直接確認できない**(`dubious ownership` で `rc=128`)。回避には `safe.directory` の設定が要り、承認範囲外 | `docs/ai/status.md` Watch、`2026-07-28_004_quory_units_survey.md`「観測できなかったこと」 |
| O12 | 本番quoryのバンドルは実測41件、うち**約46〜49%** が既知条件(pve1の夏季平日シャットダウン運用)由来。捕捉は平日ほぼ毎日発生する | `../incident_auto_capture/2026-07-28_031_production_status_check.md` 観測5 |

## 2. ゴール

**捕捉した証拠がansyへ届き、月次 `claude -p` がそれを評価して、開発プロセス全般の見直しへ供せる状態にする。**

Yoshinobuの言葉(2026-07-28、`progress.md`「目的の再提示」が原文):

> quoryでインシデントをエラー発生ごとに確保する(完了)。そして8/26を皮切りに、ansy側でタイマー起動した `claude -p` がインシデントの評価をして、開発プロセス全般の見直しに寄与したい。

追加要求(同日): **対話セッションからも repo で障害の中身を確認できること。**

## 3. 非ゴール

- 捕捉(段1)の改修。**IC-027により、捕捉を成立させるためにcaller側を書き換えない**
- Policy本文(`incident_capture_policy.md`)の改訂。Yoshinobuの領域である
- 月次振り返りの**中止条件の変更**、および `docs/ai/core.md:25`(AIはcommit/pushしない)の変更。Policy §8がYoshinobu判断として分離した B / C / E に当たる
- Knowledge月次振り返りの**既存部分**(auto-memoryの仕分け・昇格判断)の再設計。入力と出力を足すのであって、既存の工程を組み替えない
- 起票された記録を `docs/ai/memory/incidents/` へ**昇格させる自動化**。IC-020により昇格は人の行為である

## 4. 概要設計(Coordinatorが確定させた線。詳細設計はTech Leadの責務)

**この4点は決定であり、Tech Leadが再検討する対象ではない。** ただし**現物と矛盾する事実を見つけた場合は、実装へ進まず停止して報告すること**(下記 §8)。

### D-1 転送はansy起点のpullとする

IC-013により**quoryにansyへの書込権を与えない**。したがって運ぶ向きはansyが取りに行く形になる。周期実行・冪等・差分を埋める(IC-012)。ansyの停止が**遅延にしかならない**こと、すなわち復旧後の周期で取りこぼしが解消されることを必須の性質とする。

転送は元の証拠を書き換えない(IC-014)。quory側での読み取り以外の操作を行わない。

### D-2 ansy側の着地点は repo作業ツリー内の gitignore済みパスとする

**2026-07-28 Yoshinobu決定。** 対話セッションから `Read` / `Grep` で直接中身を確認できることを要求に含めるため、作業ツリー外は採らない。

これは **ADR-005 Decision (1) および (4)「git作業ツリーの外」の改訂**にあたる。同ADRの前提(事象ごとに `claude -p` が叙述する)はIC-007で消えている(`progress.md`「ADR-005の前提が1つ消えた」)。**Tech Leadは ADR-005 を改訂し、どのDecisionが生き残り、どれが差し替わるかを明示すること。**

IC-030は動かさない — 書込権は `reports/incidents/` 配下にのみ与え、**`reports/` 直下へ与えてはならない**。これはADR-005とは独立の、パッチ適用ゲートに由来する制約である。

### D-3 評価は既存の月次 `claude -p` が行い、新しい器を作らない

`ansible-knowledge-review.timer` が既に毎月26日に起動している(O5)。**入力と出力の型を足すのであって、新しいtimer・新しいジョブを立てない。**

`Read(reports/incidents/**)` の追加は**Yoshinobu承認済み**(2026-07-28、IC-019)。承認された拡大は**この1エントリのみ**であり、repo外・`~/.ansible/vault/`・SSHキーへは依然として到達しない。拡大が足りないと判明した場合は、勝手に広げず停止して報告する。

### D-4 評価の出力はLLMの標準出力とし、ファイル化はAnsibleが行う

**2026-07-28 Yoshinobu決定。** 評価結果(障害の記録)は gitignore済みパスへ出し、`docs/ai/memory/incidents/` への昇格は人または対話セッションが行う(IC-020・IC-032)。

**評価のために `claude -p` へ新しい `Edit` 許可を足さない。** O8のとおり同roleに先例がある。

**この選択の代償はYoshinobuが認識したうえでの決定である** — 昇格されなければ記録は残らない。したがって**「拾われなかったことを検知できること」(IC-021)を必須要件に含める**(下記 P0-5)。

## 5. 要件(MoSCoW)

### P0(初回実装に不可欠)

| ID | 要件 |
|---|---|
| P0-1 | quory上のバンドルがansyの `reports/incidents/` 配下(またはその下の識別可能な位置)へ運ばれる。周期実行・冪等・差分埋め(IC-012)。ansyが停止していた期間の分は復旧後の周期で埋まる |
| P0-2 | quory側の保持期間(O4)が満了する前に転送が成立する(IC-015)。**周期と保持期間の関係を数値で示す** |
| P0-3 | 転送が生成するファイルは `reports/` の `.gitignore` 除外が**現に効く形式に限る**(IC-029)。転送後に ansy の `git status --porcelain` が空のままであること |
| P0-4 | 月次 `claude -p` が転送済みバンドルを読み、評価結果を標準出力へ返す。Ansibleがそれをファイル化して gitignore済みパスへ置く。**生ログを評価成果物へ転記しない — バンドルへの参照だけを書く**(IC-017) |
| P0-5 | **拾われなかったことを検知できる**(IC-021)。①転送が止まったこと ②評価結果が昇格されないまま滞留していること の両方。**保持期間・ローテーションが未昇格の記録を静かに消す経路を作らない** |
| P0-6 | 転送・評価の失敗を握りつぶさない(IC-011)。何を試みて何が取れなかったかを記録し、非ゼロ終了で外部から可視化する |
| P0-7 | 対話セッションが repo 内のパスから障害の中身を読める(§2 追加要求) |

### P1(あると良い / 初回で落としてもよい)

| ID | 要件 |
|---|---|
| P1-1 | 既知条件(O12のpve1平日運用)の機械的な除外。**捕捉側では止めない。評価・起票側で除外する**(IC-022)。初回で判定基準を決め切れないなら、除外せず件数だけ分けて報告する形でもよい |
| P1-2 | 起票の粒度と重複排除。同一事象が複数バンドルに跨る場合の扱い |
| P1-3 | ansy側の保持期間・世代数・ローテーションの実値 |

### P2

| ID | 要件 |
|---|---|
| P2-1 | `skills/incident-recording/SKILL.md` へ「自動評価による第一報」の前段を追記する必要があるかの判断。現在のSKILLは2段階をcanonical path上で完結する形で書かれている |

## 6. 受入条件(Given/When/Then)

**「成功」の観測方法まで書くこと**(`skills/requirements-analysis/SKILL.md`)。終了コード・通知の有無・生成物のパスを `Then` に含める。

- **AC1**: Given quoryにバンドルが存在する、When 転送が1周期走る、Then ansyの `reports/incidents/` 配下に同じバンドルが存在し、**ansyの `git status --porcelain` が空**である。転送プロセスの終了コードは `0`
- **AC2**: Given 既に転送済みのバンドル、When 転送がもう1周期走る、Then 二重に運ばれず、quory側の元ファイルも変更されない(IC-014)。終了コードは `0`
- **AC3**: Given ansyが一定期間停止していた、When 復旧後に転送が走る、Then 停止期間中に発生したバンドルが**取りこぼしなく**運ばれる。すなわちansyの停止は遅延にしかならない(IC-012)
- **AC4**: Given quoryが到達不能、When 転送が走る、Then **握りつぶさず**、非ゼロ終了とsystemd `failed`(または同等の外部可視な形)で観測できる。何が取れなかったかが記録に残る(IC-011・IC-024)
- **AC5**: Given 転送済みバンドル、When 月次 `claude -p` が起動する、Then バンドルを読めており、評価結果がファイルとして gitignore済みパスに存在する。**`claude -p` はバンドルに対する書込許可を持たない**
- **AC6**: Given 月次評価が完了した、When `git status --porcelain` を見る、Then **評価成果物は現れない**(gitignore済みのため)。既存の振り返りが `docs/ai/memory/` 等へ書いた差分だけが現れる
- **AC7**: Given 転送が一定期間止まっている、When その状態が継続する、Then **誰かがそれに気づける観測点がある**(Slack通知・systemd `failed`・評価時の警告のいずれか。どれを採るかはTech Leadが決める)
- **AC8**: Given 評価結果が昇格されないまま残っている、When 次の月次評価が走る、Then その滞留が**件数と経過日数として報告される**(既存の `調査中` 滞留報告と同じ扱いにするかを含めて設計する)
- **AC9**: Given 転送も評価も未導入の現状、When 変更を適用する、Then **月次振り返りの既存動作(auto-memory仕分け、中止条件、期日更新)が変わらない**。回帰がないことを示す
- **AC10**: Given ADR-005、When 改訂する、Then どのDecisionが**生き残り**、どれが**差し替わり**、その理由が書かれている。根拠として挙げる file:line とモジュール挙動は**すべて現物で確認済み**であること(このリポジトリでは計画の技術的引用が誤っていた前例が複数ある)

## 7. 安全境界(動かせない前提)

- **AIは `git commit` / `git push` を行わない**(`docs/ai/core.md:25`)。**実ホストへの適用は必ずYoshinobuのcommit → quoryの `git pull` を挟む**。計画にこの待ちを工程として含めること(`docs/ai/roles/coordinator.md`「計画受領時のゲート」#5)
- **Policy本文を改訂しない。** Policyの制約下で設計する。Policyを変えないと解けないと判断したら、**変えずに停止して報告する**
- **quoryにansyへの書込権を与えない**(IC-013)。**`reports/` 直下への書込権を誰にも与えない**(IC-030)
- **無人セッションの読取範囲は承認済みの1エントリ(`Read(reports/incidents/**)`)まで。** それ以上の拡大はYoshinobu承認が要る(IC-019)
- **Tech Lead段階では実ホストへ触れない。** ansyの作業ツリーとrepoの読み取り、`git status` の照会までとする。Ansibleを実行しない(`--check` を含む)。実機での確認が要ると判断したら、実施せずTesterの単位として計画へ書く
- **identityを昇格させない。** 昇格した状態に到達しないこと
- **harnessの安全機構(permission classifier / `permissions.deny`)がブロックしたら、別の形で同じ結果へ到達しない。** ブロックが「形への異議」か「実質への異議」かの判定を、ブロックされた側が行わない。止まって、その事実を報告に含めて返す(`docs/ai/core.md`「安全機構がブロックしたとき」)
- 指定外パスが変更された状態で報告が返らないこと

## 8. Coordinatorの承認範囲(提案してよいが、勝手に実施しない)

- **`.gitignore` を `reports/incidents/` のディレクトリ単位除外へ変えること。** ADR-005 制約7のとおり追跡ファイルへの影響は無く、Coordinatorの承認範囲である。P0-3を拡張子依存のまま満たすか、除外の側を変えるかは**Tech Leadが判断して提案し、Coordinatorが承認する**
- **冪等なコマンドの操作カタログへの追加。** Coordinatorが承認しYoshinobuへ報告する。**非冪等な操作の追加はYoshinobuの領域**(IC-026)
- **§4のD-1〜D-4と現物が矛盾した場合。** 実装へ進まず停止して報告する

## 9. オープンクエスチョン(Tech Leadが決めるか、決められないなら明示する)

Policy §8 が未決として列挙しているものと対応する。**ここに挙がっていない事項を「決まっている」と扱わない。**

| ID | 内容 |
|---|---|
| Q1 | 転送の実装方式(何が運ぶか、運ぶ単位、周期の実値)。IC-012〜IC-015・IC-030の制約下 |
| Q2 | ansy側の着地パスの実値と、`.gitignore` の扱い(§8) |
| Q3 | 評価が既存の月次ジョブの**どこへ**入るか(同一 `claude -p` 呼び出しか、同一roleの別タスクか)。**新しいtimerは作らない**(D-3) |
| Q4 | 評価成果物の型・パス・保持 |
| Q5 | 検知(P0-5)の実装。転送停止と滞留の2つ |
| Q6 | 既知条件の除外判定(P1-1)。初回で決め切らない選択もある |
| Q7 | ansy側の保持期間の実値(P1-3)。quory側30日(O4)との関係 |

## 10. 制約

- IPアドレス・VLAN ID・VM IDの実値、および変化の速い値(件数・時刻の実測値)を成果物へ書かない(`docs/ai/context-classification.md`)。ホスト名は既公開のものを使う
- 時刻表記はJST(`date -u` やローカル時刻+リテラル `Z` は詐称にあたる)
- 分量は案件が必要とする範囲に合わせる。既存ファイルにある内容を再掲しない

## 11. タイムライン考慮

- 月次timerの次回発火は2026-08-26。**それまでに転送と評価が動いている**ことがゴール(§2)。期日の正本はauto-memory `MEMORY.md` 先頭行であり、ここへ写さない
- 8/26に間に合わないと判断した場合は、**間に合う範囲を切って提案する**。何を落としたかを明示すること

## 12. 成果物

1. `docs/ai/reviews/incident_auto_capture_step2/2026-07-28_007_step2_plan.md` — 分解・見積もり・並行して立てられる単位の組・単位ごとの未決定の設計判断の一覧
2. `docs/ai/adr/005-auto-incident-filing-destination.md` — **改訂**(AC10)
3. `docs/ai/reviews/incident_auto_capture_step2/progress.md` — **既存ファイルへの追記**。単位表・未決定・課題を更新する

**判断の根拠は成果物ファイルへ書き切ること。** 最終報告は記録として残らない。

## 13. 参照

- `docs/ai/policies/incident_capture_policy.md`(IC-001〜IC-032。**未決の一覧は §8 が正本**)
- `docs/ai/adr/003-incident-capture-collector-runtime.md`(実行形態・identity・取得経路。制約5がIC-030の由来)
- `docs/ai/adr/004-notify-capture-insertion.md`(通知経路への捕捉の挿入)
- `docs/ai/reviews/incident_auto_capture/2026-07-27_001_design_agreement.md`(D1〜D7)
- `docs/ai/reviews/incident_auto_capture_step2/` 配下 001〜005(OQ5のrequirement・調査・ADR査読・quory棚卸し・Policy査読)
- `docs/ai/memory/lessons/claude-code-unattended-session-confinement.md`(無人セッションの封じ込めが成立する3条件)
- `docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`
- `docs/ai/effort-baseline.md`(見積もりの単位。層1の基準値)
