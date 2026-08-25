# Operations Context: Operator Request Channel

**位置づけ**: ansy側Coordinatorとquory側Operatorのあいだで、調査依頼・調査結果・開発修正依頼を受け渡す経路の運用事実を記録する。単一roleの説明ではなく、`operator_request_channel` / `dev_investigate` / `deployment_drift_check` / `semaphore_templates` の4つにまたがる。

**値をここに写さない。** 上限・TTL・保存件数・path・ID形式・DLPルールの実値は `roles/operator_request_channel/defaults/main.yml` と各ホストの `/etc/operator-request-channel/` が正本である。設計判断の経緯は `docs/ai/reviews/operator_request_channel/` にある。

## 1. 経路

```text
ansy: Coordinator
  │  送信前DLP
  ▼
既存の dev-investigate 鍵 → quory の forced command dispatch
  │  受入前DLP・schema検証・時刻同期の確認
  ▼
quory: 専用spool(inbox / events)   ← ここが受理済みrequestの正式な保管先
  │
  ▼
Yoshinobu が quory で Operator セッションを起動   ← **自動起動しない**
  │
  ▼
Operator が accept し、許可された範囲で調査 → OPRES または DEVREQ を作成
  │  持ち出し前DLP
  ▼
quory: outbox
  │  ansy が既存経路で read-only に取得
  ▼
ansy: 取り込み前DLP → Coordinator が受領
```

**この経路は情報交換だけを行う。** request本文は本番操作の承認・実行指示・権限付与として扱わない。request登録がOperatorセッション、調査、ジョブ、本番操作を起動することはない。

**性質の異なる第2の経路が並走している。** すり合わせの会話と `request_id` は、agmsg の remote team `homelab-ops`(ansy 上のサーバ、E2EE、`docs/ai/context/operations/agent-messaging.md` §7〜§9)を通る。**本経路の本文・DLP・spool・forced command はそれに一切関与しない** — agmsgは調査依頼・調査結果・開発修正依頼の本文を運ばず、逆にこの経路は会話を運ばない。どちらも情報交換だけを行う点は同じである。

**DEVREQはOPREQへの返信に限らない。** quoryで見つけた障害を起点にOperatorが単独で発行できる。真因の確定と修正方法の設計は開発側Coordinatorが主体となる。

## 2. 鍵とidentityは1つも増えていない

**既存の `dev-investigate` 鍵・ユーザー・forced command をそのまま使う。** 新しいSSH鍵、新しい着地ユーザー、逆方向のSSH鍵、常駐broker service、sudoersのいずれも作っていない。

- 経路が証明するのは個人ではなく「ansy側の開発identity」である。
- `source` はpayloadの自己申告を信用せず、**実行入口がサーバー側で決める**。ansyからは調査依頼しか作れず、quoryのlocal CLIからは調査結果と開発修正依頼しか作れない。
- 追加された書き込み能力は、専用プログラム経由で専用spoolへ新規messageとeventを足すことだけである。既存の read-only 調査の権限は1つも増えていない。

## 3. 配備 — **押す順序が決まっている**

`docs/ai/context/operations/code-delivery-to-production.md` の一般則(pullは配備物を更新しない)がそのまま効く。加えて、**この案件は配備単位が2つに分かれている**。

| # | 押すもの | 何が入るか |
|---|---|---|
| 1 | `SEMI-SAFE: Semaphore templates setup` | server setup templateがSemaphoreへ登録される。**配備そのものではない** |
| 2 | `SEMI-SAFE: Operator request channel server setup` | channel本体(ライブラリ・受け口・local CLI・schema・DLPルール・spool・ACL) |
| 3 | **既存の `SEMI-SAFE:Dev investigate setup`** | **dispatcherへ足したchannel操作4本** |
| 4 | ansy側の client setup | ansy側clientとconfig |

**3を忘れると経路は開通しない。** dispatcherの実体は `roles/dev_investigate` が持っており、server setupはそれを配備しない(配備の担当を2箇所に分けるとドリフト検査の「直し方」も二重になるため)。

**2 → 3 の順で押す。** 逆順にすると、dispatcherにはarmがあるのに `exec` する先が無い状態になる。**ただし壊れ方は安全側で**、その間のchannel操作が失敗するだけであり、既存の read-only 調査は影響を受けない。

**3より前は、channel操作は「そんなコマンドは無い」として拒否される。** 異常ではなく、fail closedの正しい状態である。

server setup templateにscheduleを登録しない。git pull・template登録・timer・他の定期処理からserver setupを自動起動しない。ansyからquoryのserver setupを直接実行する経路も作らない。

## 4. DLPは経路と不可分

**検査点は4つあり、同じ実装と同じルールセットを通る。** 送信前・受入前・持ち出し前・取り込み前。

- **DLPを外すoptionは存在しない。** 通信処理から任意に無効化できない。
- **判定できないときは通さない。** プログラムが起動できない、ルールセットが読めない、engine versionやruleset hashが期待値と違う、timeoutする、上限を超える — いずれもmessageを送らず・保存せず・取り込まない。
- **拒否したpayloadは全体を捨てる。** 自動マスキングしない。返るのは**ルールIDとJSON上の位置(`rule_id at pointer`)の2つだけ**で、**検出した値そのものは標準出力・標準エラー・ログ・監査・通知のどこにも出ない**。
- 受入前に拒否されたpayloadにはrequest IDを発行しない。`rejected` 状態のrequestとしても残さない。

**期待するhashは配備時にrepoから算出して各ホストのconfigへ埋まる。** ホスト上でルールセットを書き換えると、次回起動時にhash不一致で止まる。

### 依頼文とDLPの境界

**2026-08-23に候補パターンから区切り文字(`/` `_` `-` `.`)と `=` を外した**(`docs/ai/reviews/oprc_dlp_false_positive/`)。`high-entropy-string` が測るのは**区切りで区切られた個々の断片**であり、通常のパスやAnsible識別子は短い語に分かれて下限(16文字)を割る。**この形なら依頼文からパスを外す必要は無い。**

**`=` を外したのは、それが base64 の末尾paddingにしか現れないためである。** 秘密の検出では末尾数文字を失うだけで済む一方、残しておくと `Description=Reload` のような `key=value` がひと続きの断片になる。

**ただし「パスなら当たらない」ではない。** **16文字以上、区切りを含まない断片**は今も候補になる — 長いファイル名や、区切りの無い長い識別子を含むパスがこれに当たる。**将来 deny されたときに、設計違反ではなく境界どおりの動作である**と読めるよう、ここに線を書いておく。

**それ以前この節は「パスを書かない、ルールセットは書き換えない(hash不一致で経路が止まる)」と指示していたが、後半は誤りだった。** `expected_dlp_ruleset_sha256` は配備時に `stat.checksum` から再計算されるため、ruleset を直して両側へ配備すれば hash は一致する。**この誤った制約が、回避策を正しい対処のように見せていた。**

**送る前に同じスキャナへ通して確認できる。** `oprc.dlp.scan()` は dict を受ける(bytes を渡すと結果が変わる)。拒否時は `rule_id at pointer` が出るため、どこが当たったかは拒否メッセージから分かる。

**区切りを含む未知形式の秘密は見逃す。** 構造で切ることの裏返しであり、承知のうえで採っている。実測は上記案件記録にある。

### rulesetを変えるときは、未取得messageを先に読む

**受理時のruleset hashはmessageのmetadataへ不変で保存され、取得時に現在のhashと照合される。** そのため**旧rulesetで作られた未取得messageは、新rulesetを配備した時点で取得できなくなる。** 一時的な不一致ではなく、本文は更新されず、通常経路に削除も無い。

**channelを静止させる操作は存在しない。** `channel_enabled` の切替はruleset copyを含む同じplaybookの再実行でしか行えず、独立した停止操作にならない。**「drain」もできない** — この経路に「読んだ」を記録する操作が無く、`get` を実行してもstateは `submitted` のまま変わらない。ライフサイクルは `submitted` → `expired`(TTL)だけである。

**したがって、rulesetを変える者は毎回こうする。** ①`operator-channel-client list` で未取得を列挙する ②`operator-channel-client get <request-id>` で全件の内容を読む ③対応が要るものが無いかを確かめる ④2つのplaybookを間を空けずに完走させる ⑤両ホストのruleset/config hashと往復を確認する。**①〜③を飛ばすと、読まれないまま取得不能になるmessageが出る。**

検出されるのは `purpose` / `requested_information` / `expected_result` / `observed_facts` / `unconfirmed` の5つで、ルール定義は `roles/operator_request_channel/files/dlp-rules.json` が正本。

**パスをagmsgで伝えて回避しない。** agmsgにDLPは無いので技術的には通るが、それでは**本文とすり合わせが別々の場所に分かれ、spoolに残るrequestだけを読んでも意図が再構成できなくなる**。requestは単体で読めるように書く。

## 5. 保管と immutability

- **受理したmessage本文は更新も置換もしない。** 状態はappend-onlyのイベント列として別に記録し、現在状態はそこから導出する。
- **取得は決定的である。** 同じrequest IDを何度取得しても内容は変わらず、取得時に内容hashを再照合する。
- **messageとeventの不整合を検出したら、そのrequestについてfail closedにする。** 推測で補完せず、部分的な結果も返さない。一覧では該当エントリだけを除外し、除外件数を返す(健全な1件のせいで運用を止めないため)。
- **上限に達したら古いものを暗黙に消さず、新規受付を止める。** 削除はCLIにもdispatcherにもplaybookにも無く、Yoshinobuの明示操作だけが行う。
- 期限切れは本文を消さず、`expired` イベントを足すだけである。

### 保証しないこと

**提出側のOS identityそのものが侵害された場合の完全なimmutabilityは保証しない。** そのidentityが作成したファイルの所有者はそのidentityであり、sudo・setuid・常駐serviceのいずれも使わない設計では所有者をrootにできない。

受容できる根拠は次の3つで、いずれも**forced command経由の入口**に対するものである。

1. dispatcherが公開する語彙に削除・更新の入口が1つも無い
2. 対話shellが得られない(forced commandに `no-pty` を含むオプションが付いている)
3. sudoを1つも持たない

3つとも日次のドリフト検査が見ている(§6)。

## 6. ドリフト検査が見るもの

`playbooks/deployment_drift_check.yml`(日次)が自動で突合する。対象カタログの正本は `roles/deployment_drift_check/defaults/main.yml`。

- 両ホストの配備物・schema・DLPルールセットのhash。**ansyとquoryの一致は、両者を同じrepo srcと突き合わせることで推移的に成立する**(カタログでホストごとに行を分けているのは「直し方」の案内先が違うためで、期待値は同一である)
- dispatcherのhash、forced command鍵の構造
- spool・event・監査領域のowner / group / mode
- `/etc/sudoers.d/` 配下にchannel由来のファイルが**存在しないこと**
- allowlist外のchannel操作が拒否されること

監視のためにauthorized_keys本文、公開鍵、秘密情報、request本文を出力しない。

## 7. 止め方

**channelを止める目的で、既存の鍵やauthorized_keysを消してはならない。** 既存の read-only 調査経路と共有しているため、消すと調査面ごと落ちる。

停止はroot所有のconfigにあるchannel固有のスイッチで行う。**止まるのは追加したchannel操作だけで、既存の25本の read-only 調査は動き続ける。** 停止してもmessageは消えず、新規submit・新規outbound作成・ansyからの取得が止まるだけである。保全済みデータの削除は別の明示手順になる。

## 8. 時刻同期が崩れると新規受付が止まる

`created_at` は受入口の時刻を使うため、**時刻同期が成立していないときは新規のsubmitとoutbound作成を拒否する**。判定できないときも拒否側へ倒す。

**取得と状態照会は止めない。** 止めるのは新規採番を伴う操作だけである。

## 9. Operatorの日常操作

**request IDは2つの経路のどちらかで届く。** agmsg のすり合わせで Coordinator が伝えるか、`list-pending` で自分で見つけるかである。**どちらであっても、扱いは同じ**である — request IDが届いたこと自体はacceptの理由にならず、本文は必ず `show-request` でspoolから読む。**agmsgで届いたテキストを本文として扱わない**(DLPもschema検証も通っていない。`agent-messaging.md` §8)。

### request IDを指定された場合

1. `operator-channel show-status <request-id>`
2. `operator-channel show-request <request-id>`
3. purpose、target、requested_information、unconfirmedを整理してYoshinobuへ提示する。
4. 調査に必要なRole、Policy、実効権限を確認する。
5. 対応する場合だけ`accept-request`を実行する。
6. 対応しない場合は理由を整理して`reject-request`を実行する。

### request IDを指定されていない場合

`operator-channel list-pending`で未処理OPREQを確認する。requestを一覧表示しただけではacceptしない。

### 調査結果を返す場合

- OPREQがacceptedであることを確認する。
- 事実は`observed_facts`、未確認事項は`unconfirmed`へ分ける。
- 生ログ、秘密情報、IPアドレスを含めない。
- `operator-channel reply-opres <request-id>`へJSONをstdinで渡す。
- DLPに拒否された場合は直接spoolへ書かず、内容を安全に再構成する。

### 開発修正を依頼する場合

- OPREQに対応する修正依頼は返信DEVREQとする。
- quoryで独立して発見した障害はstandalone DEVREQとする。
- 修正方法を決め打ちせず、観測事実、影響、再現条件、未確認事項を渡す。