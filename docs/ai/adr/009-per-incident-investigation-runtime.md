# ADR-009: 障害の一次調査(事象ごと)の実行形態

**Status:** **Accepted**(2026-07-31。前提だった2件 — Policy改訂の承認と調査専用ユーザーの `codex login` — はいずれも充足した。実装・独立レビュー・quoryへの配備・Tester実地検証(AC4/AC7/AC8/AC9 実測PASS)を経て `homelab-incident-investigate.timer` を有効化し、本番稼働に入った)

> **(a) と (f) は 2026-07-31 に暫定でsupersedeされている(他の決定は有効)。** 本番のSemaphore実行で a-4 の callback が発火しないことが実測で確定したため、起動契機を「証拠バンドル(`reports/incidents/semaphore-<id>/summary.json`)の出現を走査で拾う」形へ切り替えた。**暫定であり、恒久の設計判断としてこのADRを書き換えてはいない** — 経緯と選択肢の比較は `docs/ai/memory/incidents/2026-07-31_incident-investigate-callback-did-not-enqueue.md`、実装契約は `docs/ai/reviews/incident_investigate_trigger/2026-07-31_001_requirement.md` が正本。該当箇所は下記 Decision の (a) / (f) に注記した。

**経緯**: 当初 (c) は c-2(設定層でexecpolicyを絞る)としていたが、U0の実測で否定された — config.toml層のexecpolicyは `codex exec` + `approval_policy="never"` の経路でコマンド実行を阻止しない(allow-listに無い `id` が通った)。一次記録は `.../2026-07-31_002_u0_test_result.md`、**既存経路への影響**は `docs/ai/memory/incidents/2026-07-31_codex-execpolicy-allowlist-not-enforcing.md`。2026-07-31、Yoshinobuが c-3 を選択した。

要求は `docs/ai/reviews/incident_auto_investigation/2026-07-31_001_requirement.md`。

## Context

既存の3段パイプライン(捕捉=quory / 転送=quory→ansy / 評価=ansy月次)は「起きたこと」を保全するが、「なぜ落ちたか」を書く工程を持たない。2026-07-31、Yoshinobuが事象ごとの一次調査を自動化する方針を示した(この判断自体がADR-003以来の前提の変更であり、Policy改訂を伴う)。

判断に効く観測事実を挙げる。

- **playbook内の通知経路は失敗時にほとんど到達しない。** 捕捉が稼働していた2026-07-28〜30の失敗ジョブ9件のうち、`common_slack/notify.yml` が記録されたのは1件のみ。Ansibleはタスク失敗時点でplayを止めるため、post_tasksの通知へ進まない。
- **Semaphore(2.18.4)はquoryで `User=yoshi` として動く。** タスクプロセスもyoshiであり、semaphore.db(yoshi所有)・vault password file・`reports/incidents/`(yoshi所有)へ追加の権限なしで届く。
- **quoryのCodexは `recovery-exec` として動き、その execpolicy は復旧アクション(`homelab-recover-*`)・監視停止(`homelab-monitoring-pause`)・mute(`homelab-mute-set`)を許可している。** 対話経路(recovery-io)では人が応答を読むが、無人経路には読み手がいない。
- **証拠バンドルは非信頼データである**(IC-016)。調査の入力(Semaphoreのタスク出力)は、失敗したplaybookが出力した任意のテキストを含む。
- **`reports/incidents/<bundle>/` は `recovery-exec` 所有で、拡張ACLが付いている。** このツリーへの `chmod` 相当の操作はACL maskを書き換え、2026-07-28に実際の障害を起こした(`docs/ai/reviews/incident_auto_capture/2026-07-28_018_acl_mask_plan.md`)。
- **`incident_sync` は削除操作を持たない**(`--delete` を指定しない)。ansyへ渡ったものはquory側が消えても残る。
- codex-cli 0.145.0 は `-p/--profile`(`$CODEX_HOME/<name>.config.toml` を基底設定へ重ねる)と `-c` を持つ。**重ねたときに基底のallow規則を消せるかは未確認**であり、U0で測っている。

## Options Considered

### (a) 起動契機をどこに置くか

| Option | Pros | Cons |
|---|---|---|
| a-1: `common_slack/notify.yml` へ非同期起動を足す | 既存の1箇所を触るだけ。全playbookが呼ぶ | **直近の失敗9件中8件で到達しない**(上記)。捕捉と通知の経路にLLM起動という重い処理が載り、IC-010(観測が被観測を変えない)の余白を食う |
| a-2: 各playbookの `rescue` / `post_tasks` へ個別に足す | 到達点を明示できる | 38箇所の呼び出し側すべてに同じ変更が要る。新しいplaybookで書き忘れる |
| a-3: 収集器(`incident-capture-collector.py`)から起動する | 失敗ジョブの検出機構が既にある。被観測を一切触らない | 捕捉の段にLLM起動が混ざる(IC-006)。収集器は `recovery-exec` で動き、調査の実行identityと合わない。最大5分の遅延 |
| a-4: callback plugin(`v2_playbook_on_stats`)が要求をキューへ書き、systemd path unitが調査を起動する | **どこで落ちても playbook実行の最後に必ず呼ばれる**(タスク失敗・unreachableの両方)。playbook側の編集がゼロ。要求の生成は「1ファイル書くだけ」でLLMもネットワークもない。キューが無い環境では何もしない | ansible.cfg 経由で**全実行に載る**ため、壊れると影響範囲が広い。playが始まる前の失敗(YAML syntax error、Semaphoreのgit pull失敗)は拾えない |

### (b) 調査本体の形式

| Option | Pros | Cons |
|---|---|---|
| b-1: Ansible playbook | vault/`common_slack` へ素で届く。将来のSlack報告を同じ場所に書ける | 対象はquory1台のローカル完結で、多ホスト・冪等性・モジュールのいずれも効かない。LLM出力からの応答抽出をJinjaで書くことになる |
| b-2: Python + systemd oneshot(role が配備) | 既存の同型(`incident-capture-collector.py`、`recovery-probe.py`、`recovery-io.py`)と一致する。応答抽出は `recovery-io.py` の実装がそのまま参考になる | Slack報告を足すときは、`recovery-probe.py` と同じく通知用playbookを起動する形が要る |

### (c) LLMセッションの封じ込め

| Option | Pros | Cons |
|---|---|---|
| c-1: 既存 `codex-exec-wrapper` を流用 | 追加実装ゼロ | 無人セッションが復旧アクション・監視停止・muteへ到達できる状態が残る。**禁止をpromptの文言で表現することになり IC-018 に反する** |
| c-2: 読み取り専用の設定層 + 専用wrapper(`codex-investigate-wrapper`) | 既存の対話経路を一切変えずに、無人経路だけを絞れる | **U0で否定された。** 設定層のexecpolicyは `codex exec` + `approval_policy="never"` でコマンド実行を阻止しない。**採らない** |
| c-3: 調査専用のUnixユーザーを新設(quory / Codex) | 境界が**鍵の所有**になる。復旧wrapperは `recovery-exec` の鍵を読めず失敗する。調査に必要なのはSemaphoreとバンドルだけなので、**新しいSSH鍵を1本も配らずに済む**(保護対象ホストに触れない) | 新ユーザーのOAuth認証が要る(`codex login` はブラウザ操作でYoshinobu本人しかできない)。ACL(semaphore.db読み / `/home/yoshi` traverse)の追加 |
| c-4: 調査自体をansyへ移し、`claude -p` を**Bash無し**で使う | 封じ込めが**本番稼働中の実績**で担保される(月次評価と同じ機構: 書込allowlist + Bash禁止)。Bashが無いので復旧wrapperに到達する手段が存在しない。新しいidentityも認証情報も要らない。**リポジトリのソース(`roles/` `playbooks/` `docs/`)を読めるので、原因を「どのファイルか」まで書ける**。quoryはLLMフリーのまま(IC-006を改訂しなくてよい) | 証拠はミラー経由(遅延。調査側が先に `incident_sync` を回せば短縮できる)。Semaphore DBへのライブアクセスが無い(バンドルにtask-output/errors/hostsが入っているため実用上は足りる)。ansy停止中は調査も止まる(**証拠はquoryにあるので喪失ではなく遅延**)。`claude -p` はMax枠を消費する |
| c-5: quory/Codexのまま、systemdのmount namespaceで復旧wrapperを**見せない** | 依頼どおりの構成を保ったまま、境界が「能力の不在」になる。新ユーザー不要 | codex自身のbwrapと入れ子になる初物機構。同種の多層サンドボックスでは過去に4連敗の記録がある(`docs/ai/memory/lessons/`)。リポジトリのソースは依然読めない |

### (d) 実行identity

| Option | Pros | Cons |
|---|---|---|
| d-1: すべて `recovery-exec` | 収集器と同じ。sudoが要らない | `recovery-exec` が `reports/incidents/_investigations/` へ書くには新しいACLが要る。**ACL mask障害と同じクラスの操作を増やす** |
| d-2: 呼び出し側は `yoshi`、LLM呼び出しだけ `recovery-exec`(wrapper 1本に限定したsudoers) | yoshiは `reports/incidents/` の所有者であり、ACLを一切触らずに書ける。semaphore.dbも所有者として読める。Semaphoreのタスクプロセスと同じ identity なのでキューの受け渡しに権限調整が要らない | sudoers エントリが1行増える(`recovery-io` に対する既存エントリと同じ形) |

### (e) 成果物の置き場

| Option | Pros | Cons |
|---|---|---|
| e-1: バンドル内(`semaphore-<id>/investigation.md`) | 「incident reportに書き込む」の字義どおり | バンドルディレクトリは `recovery-exec` 所有。書き手を合わせるか新規ACLが要る(d-1のCons)。証拠と判断が同じディレクトリに混ざる(IC-032) |
| e-2: `reports/incidents/_investigations/` | yoshiが所有するツリー内で完結し、ACLに触れない。証拠(recovery-exec が書く)と判断(調査が書く)が物理的に分かれる。同期の除外対象(`_spool/`・`*.tmp`)に当たらないのでansyへ渡る | バンドルとの結びつきはファイル名(`semaphore-<id>`)の規約で担保する |

### (f) ジョブ番号の取得

| Option | Pros | Cons |
|---|---|---|
| f-1: Semaphoreが注入する環境変数のみ | 確実で安い | 変数名が未確定(U0 M3)。Semaphoreの版に依存する |
| f-2: playbookパスと終了時刻で `recent-failed` と突合するのみ | Semaphoreの実装に依存しない | 同一playbookが短時間に複数落ちると取り違える |
| f-3: f-1 を優先し、取れなければ f-2 へ落ちる | どちらかが壊れても成立する。取れなかった事実を記録できる | 経路が2つになる |

## Decision

- **(a) a-4** を採る。callback pluginは「失敗を検出して1ファイル書く」だけに留め、判断・LLM・ネットワークを持たせない。キューが存在しない環境(ansy等)では即座に何もせず返る。例外は内部で握り潰し、被観測playへ伝播させない。
  - **キューを消費する側は systemd path unit ではなく短周期の timer とする**(2026-07-31、実装時の変更)。当初 a-4 は path unit を想定していたが、調査は「Semaphoreがステータスと出力を確定させ、かつ証拠バンドルが揃う」まで**待って再試行する**必要がある(R3)。path unitはファイルの変化で1度発火するだけで再試行を持たないため、待ちを表現できない。timerなら未処理のキューを毎周期見直せ、取りこぼしの回復も同じ機構で済む。**検出が即時・消費が周期という非対称は意図したものである。**
  - **【2026-07-31 暫定supersede】a-4 の callback による検出は本番で発火しなかった。** Semaphoreが起動する `ansible-playbook` に `SEMAPHORE_TASK_DETAILS_*` が渡っておらず、callbackが「Semaphore以外の起動経路」とみなして早期returnしていた(quory実機で実測)。**callbackをやめ、捕捉が作る証拠バンドルの出現を起動契機にする**形へ切り替えた(`ansible.cfg` の2行を外して無効化、plugin本体は残す=可逆)。timerで周期的に走査する点は変わらない。**これは a-3(収集器から起動する)ではない** — 走査するのは別unit・別identity(`yoshi`)であり、捕捉の段は決定論的なまま(IC-006)である。引き受けた代償は「調査が捕捉に依存する」「検出が最大5分遅れる」の2点で、requirement §10 が正本。
- **(b) b-2** を採る。Ansible は**配備**(role + setup playbook)と、将来のSlack報告(P2 R14)にだけ使う。
- **(c) c-3** を採る(2026-07-31 Yoshinobu選択)。**c-1(既存wrapperの流用)・c-2(設定層で絞る)へは倒さない。** 詳細は下記。
- **(d) d-2の変形**を採る。呼び出し側は `yoshi`、LLM呼び出しだけ**新設する調査専用ユーザー**(wrapper 1本に限定したsudoers)。`recovery-exec` は使わない。
- **(e) e-2** を採る。
- **(f) f-3** を採る。**U0 M3でジョブ番号の環境変数が `SEMAPHORE_TASK_DETAILS_ID` と確定した**(semaphore v2.18.4のソースで確認)ため f-1 が主経路になる。取れなかった場合の f-2 は残し、特定できなかった事実も成果物に残す(R4)。
  - **【2026-07-31 暫定supersede】f-1 / f-2 はいずれも不要になった。** 起動契機がバンドル走査へ移り、走査対象のディレクトリ名 `semaphore-<id>` 自体がジョブ番号を持つため(捕捉側が既にSemaphoreのDBから得たidで命名している)、推定も突合も要らない。実装からは f-1 / f-2 の両経路を削除した。**ソースに環境変数が存在することと、この環境の実行時に注入されることは別である** — f-1 を主経路に選んだ判断は、後者を実測しないまま前者だけで行われていた。

> **(f) の教訓**: ジョブ番号のような外部からの入力は、**取得元をその実行環境で実測してから設計へ組み込む**。ソースコードの確認は「存在しうる」ことしか示さない。



### (c) c-3 の内容 — 境界は「鍵とトークンの所有」で作る

| 項目 | 決定 |
|---|---|
| ユーザー名 | `incident-inspect`(**名前自体が復旧能力を持たないことを示す**。`recovery-*` の名を与えない) |
| SSHの鍵 | **1本も配らない。** したがって `homelab-recover-*` / `homelab-investigate-*` は、このユーザーが起動しても鍵を読めずに失敗する。**保護対象ホストへの変更が一切発生しない** |
| ホスト状態の取得 | `homelab-investigate-*` の代わりに、**収集器がバンドルへ既に記録したスナップショット**(`summary.json` の `snapshot`)を読む。新しい到達経路を作らない |
| 読取に要る権限 | `semaphore.db` の読み取りACLと、`reports/` への traverse ACL のみ(いずれも `recovery-exec` に対して既に存在するものと同型) |
| Codexのsandbox | `network_access = **false**`。このユーザーがモデルに実行させるコマンドはすべてローカル完結であり、外へ出る必要が無い(`recovery-exec` 側が `true` なのはSSH wrapperのため) |
| execpolicy | **安全境界として数えない**(U0の結果)。2026-07-31の追測で、config.tomlに `[execpolicy]` というキーがそもそも存在せず、`.rules` へ移してもallowlistは表現できないことが確定したため、**書くこともやめて設定から削除した**(Incident参照) |
| 認証 | `codex login` を**このユーザーとして1回**行う。`recovery-exec` の `auth.json` を**複製しない**(`docs/ai/core.md`: tokenの複製を行わない) |

> **【2026-08-19 部分supersede】「読取に要る権限」行は、Semaphore 2.19.8への
> 版上げに伴う移行(`docs/ai/reviews/semaphore_query_api/2026-08-19_001_requirement.md`)
> で成立しなくなった。** `semaphore.db` の読み取りACLはこのユーザーに
> 付与されなくなり(2.19.8がSQLiteをWALモードで開き、ACLの付かない
> `-shm`/`-wal`補助ファイルが必要になったため、直読み自体が全識別子で
> 不可能になった)、代わりにR9でSemaphore API tokenファイルへのread ACLが
> 付与された。**さらにR14(同requirement)で、このユーザー自身の
> Codexセッションはそのtokenを使ったAPI呼び出しすら行わない**
> (`--sandbox read-only`が外向き通信を塞ぐため)。Semaphoreの情報は
> 別identity(yoshi、`roles/incident_investigate`)がsandboxの外で先読みし、
> このユーザー専用のcontext directoryへファイルとして渡す。**このユーザーの
> 実際の権限surfaceは「API tokenファイルのread ACL(未使用)+
> `reports/`へのtraverse ACL + 先読みcontext directoryへのtraverse ACL(`x`のみ、listは持たない)」**
> であり、この表の「semaphore.dbの読み取りACL」という記述はもう実態と
> 一致しない。恒久の決定としてこの表自体は書き換えない — 経緯と現状は
> 上記requirementおよび `docs/ai/reviews/semaphore_query_api/
> 2026-08-19_002_implement.md` が正本。

## Trade-off Analysis

**受け入れる代償**

1. **callback pluginが全ansible実行に載る。** 壊れれば影響範囲は広い。これを引き受ける理由は、載せない限り「どこで落ちても拾う」が成立しないためである(a-1/a-2はplayの停止位置に依存し、a-3は捕捉の段にLLMを持ち込む)。代わりに、この plugin には「キューの不在で即return」「例外を外へ出さない」「判断を持たない」の3つを不変条件として課す。
2. **playが始まる前の失敗は拾えない。** YAMLのsyntax error、Semaphore側のgit pull失敗などが該当する。ここはSemaphore自身のSlackアラートが拾う。**この死角を塞ぐために callback を前倒しすることはしない**(検出のためにansibleの起動プロセスへ介入することになるため)。
3. **成果物がバンドルの外に出る。** 「incident reportに書き込む」の字義からは外れる。ACL mask障害と同じクラスの操作を増やさないことを優先した。結びつきはファイル名の規約が持つ。
4. **呼び出し側の実行identityがSemaphoreのタスクプロセスと同じ `yoshi` になる。** yoshi側が行うのはキューの読み出し・LLMの呼び出し・ファイル書き込みだけで、**LLMが動くのは `incident-inspect` 側**である。
5. **新しいUnixユーザーとOAuth認証が増える。** `codex login` はブラウザ操作を伴うためYoshinobu本人しか実行できず、着手の前提になる。**headlessなquoryでのlogin手順は未確認**(`recovery-exec` で一度成立している手順を再現できるかを含め、実施時に確かめる)。
6. **調査がホストへ問い合わせる能力を持たない。** 鍵を配らないため `homelab-investigate-*` は使えず、ホストの状態は収集器がバンドルへ記録したスナップショットに限られる。**収集時点より後の状態は見えない。** 見たくなった場合に鍵を配る判断は、保護対象ホストへの変更を伴うため改めてYoshinobuの領域になる。

**受け入れない代償**

- 無人セッションが復旧アクションへ到達できる状態(c-1)。これは実装の手間の問題ではなく境界の問題であり、`docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md` が繰り返し扱ってきたクラスである。
- **設定層のexecpolicyを安全境界として数えること(c-2)。** U0で否定され、追測でキー自体が存在しないことまで確定した(AR-102)。

## Consequences

- **Policy改訂が前提。** 承認前に実装へ入らない(2026-07-31に適用・commit済み)。
- **roleは2つに分ける。** `incident_inspect`(調査専用identityとCodexの実行口)と `incident_investigate`(検出・調査本体・配備)。**`roles/recovery_exec` へは足さない** — 同roleのsetup playbookはターゲットへSSH公開鍵を配布する経路を持ち、そこへ無関係な変更を混ぜると影響範囲が横へ広がる(`docs/ai/memory/lessons/` のsetup playbook横方向クロバーの教訓)。既存の `recovery_exec`(identity + wrapper)と `recovery_io`(ブリッジ)の分け方と同型である。
- **認証は `CODEX_HOME` 単位でユーザーをまたがない**(codex-cli の `--ignore-user-config` の説明が明記、2026-07-31実測)。ユーザー作成後に、そのユーザーとして `codex login --device-auth` を1回行う。**headlessなquoryでdevice-authが成立することは実証済み。**
- **新しい常時稼働プロセスは増えない。** 増えるのは callback plugin(実行のたびにロードされる)、systemd timer + oneshot service、新ユーザー `incident-inspect` とその Codex 設定、sudoers 1行、**ACL 3件**(`/home/yoshi` traverse / `/var/lib/semaphore` traverse / `semaphore.db` read。`recovery_exec` の既存実装と同じ3点構成である。**2026-07-31、当初「2件」と書いていたのを実装の現物に合わせて訂正した**)。
- **新ユーザーのACL追加先に `reports/incidents/` が含まれる。** このツリーは 2026-07-28 の ACL mask 障害の現場であり、**`setfacl` で named entry を足すことと、`chmod`(`ansible.builtin.file` の `mode:` を含む)を一切当てないことを両方守る必要がある**(`roles/incident_capture/tasks/main.yml` 冒頭の不変条件 C1)。
- **quoryへの配備にYoshinobuの `git pull --ff-only` が要る。** quory作業ツリーの自動同期は2026-07-29に意図的に見送られている。
- **`ansible.cfg` へ callback を有効化する行が入る場合、この変更は全ホスト・全実行に効く。** U0 M2 は**確定しなかった**(状況証拠は「効いている」方向だが、Semaphore自身のVault機構の使用有無を確認するDBクエリがharnessにブロックされ停止した)。**効くことを前提にせず、配備後に一度観測して確かめる**。効いていなければ Semaphore 側の環境設定(YoshinobuのUI操作)が別途要る。
  - **【2026-07-31】観測した。** `ansible.cfg` 自体は効いていた(cwdがcheckout直下であることを実測)。効いていなかったのは callback の判定材料(`SEMAPHORE_TASK_DETAILS_*`)の方である。**この2つは症状が同じ**(callbackが痕跡を残さない)ため、ログからは区別できなかった。上記(a)の暫定supersedeにより2行は削除済みで、**現在この行は全実行に効いていない**。
- **「リポジトリのソースを読めない」ことは制約ではなく設計どおりである。** 2026-07-31のYoshinobu表明(開発=Claude Code と運用=Codex の分離と牽制)により、**コードのどこが原因かを決めるのは開発側の工程**になった。上の(c)比較表で c-4 の Pro として挙げた「ソースを読めるので原因をファイル単位まで書ける」は、この観点では**利点ではない**。なお `incident-inspect` は技術的には公開リポジトリのファイルを読めてしまう(秘密は mode 0600 で別管理されており露出しない)。そこへ踏み込ませない線は prompt と成果物スキーマで引く — **構造ではなく規約で引く線であることを明示しておく。**
- **月次評価の入力が増える**(P1 R13)。`_investigations/` を読ませる変更は `roles/knowledge_review/templates/incident-review-prompt.md.j2` の1節で済む。
- 将来の自動修正(P2 R15)は、成果物の `.json` を入力にできる。**commitがYoshinobuという承認境界は本ADRでは動かさない。**
