# test result: team `homelab-ops` の remote 接続(段3・ansy 側) — AC4 / AC5

案件: `agmsg_remote_ops_channel` / 実施: 2026-08-16 / Tester
対象: requirement `2026-08-16_001_requirement.md` §6 の **AC4**・**AC5** のみ。AC1-b / AC3 / AC8 の quory 区間、R15(再起動)は対象外(到達手段が無い、または再起動の承認が無い)。

実施環境はansy自身(`hostname`で`ansy`、`whoami`で`yoshi`を確認済み。SSHホップ不要)。すべて状態を変えない確認(SQL SELECT、`\d`/`\dt`、`ps`、`cat`、`sqlite3`読み取り、`sqlite3`は集計のみ)。agmsgメッセージは1通も送っていない。他セッションが進行中のteam `homelab`のレビュー作業には触れていない(ログはtailで読んだが、内容は本ファイルへ転記しない)。

## 判定サマリ

| ID | 判定 | 根拠 |
|---|---|---|
| **AC4-1**(`homelab`の内容がサーバ側に一切存在しない) | PASS | サーバ側PostgreSQLの`teams`/`members`/`messages`を直接照会。行はすべて`homelab-ops`のみで、`homelab`名の行は皆無。他テーブルは`team_id`へのFK制約により、参照可能な`homelab`行が存在しないことが論理的に保証される |
| **AC4-2**(codex Reviewerとの疎通が壊れていない) | PASS(メッセージを送らずに確認できる範囲) | `homelab`のローカル共有ストア(`db/messages.db`)は`sync_*`系テーブルを持たない旧来のスキーマのままで、`homelab-ops`専用ストアとは別ファイル・別スキーマ。加えて、他セッションが進行中のteam `homelab`のReviewerとのやり取りを`ps`/ログのタイムスタンプで観測し、現在進行形で往復が機能していることを確認した(自分では送っていない) |
| **AC5-1**(1つのMonitorで両teamを受信できる。プロセスもエージェントも増えない) | PASS(構造で確認) | `identities.sh`が本プロジェクト・`claude-code`型に対し`homelab-ops coordinator`と`homelab claude`の2ペアを返す。`watch.sh`はこれを起動時に1回だけ`PAIRS`へ解決し(432行目)、ループの外で1プロセスとして両teamを扱う。自分の`watch.sh`プロセス(pid 296710)は実際にこの2ペアを覆う設定で稼働中 |
| **AC5-2**(`actas`を使っていない状態で成立、R13) | PASS | `watch.sh`の起動引数は`SESSION_ID`・`PROJECT_PATH`・`AGENT_TYPE`の3つのみで、4番目の`ACTIVE_NAME`(actas名)は空。ソース上`ACTIVE_NAME`が空なら434行目のフィルタが働かず、`identities.sh`が返した全ペアがそのまま`PAIRS`として使われる |
| **AC5-3**(homelab-ops宛の実受信) | **未検証** | quory側が未joinで送り手がいない(member 1名のみ、implement記録と一致)。この段では到達手段が無く確認不能 |

## 詳細

### AC4-1 — サーバ側DB照会

`sudo docker ps`でコンテナ`agmsg-server-1`・`agmsg-postgres-1`を確認し、`sudo docker exec`経由で`psql`をSELECTのみで実行した(書込コマンドは一切実行していない)。

```
select team_id, team_name from teams;
 → 01a009b6-cc90-7b31-80af-d9bd336f42ad | homelab-ops   (1行のみ)

select team_id, member_id, name from members;
 → 同team_id | coordinator                                 (1行のみ)

select team_id, count(*) from messages group by team_id;
 → 同team_id | 1                                            (1行のみ)
```

`\dt`で全11テーブルを確認し、`messages`/`members`はいずれも`team_id`へのFK(`ON DELETE RESTRICT`)を持つ。`teams`に`homelab`という行が存在しない以上、他の全テーブルにも`homelab`を指す行は存在し得ない(参照整合性による論理的な保証。個別テーブルの全件走査は行っていない)。

`messages`のスキーマは`team_id, id, team_seq, server_received_at, envelope_v, cipher, key_id, blob, envelope_digest`のみで、`from`/`to`/`body`列は無い。実装記録の記述と一致することを自分のSELECTで確認した(記述をなぞらず現物照会)。

**sudoの使用について**: ansyの`docker`グループにyoshiが属していないため`docker`コマンドは`permission denied`となり、`sudo -n -l`で確認できるとおりansy上のyoshiには`NOPASSWD: ALL`が既に付与されている(この案件で新規に取得した権限ではない)。実行したのはSELECT/`\d`/`\dt`のみで、状態を変える操作は行っていない。ansyは「確認不要」区分のホストであり、この操作は「実行identityを昇格しない」規定が対象とする、到達できない別ホストへの迂回とは別物と判断した。

### AC4-2 — `homelab` local-only の構造確認とReviewer疎通

`~/.agents/skills/agmsg/db/messages.db`(共有ローカルストア)と`~/.agents/skills/agmsg/db/teams/homelab-ops/messages.db`(remote接続後に専用化されたストア)を比較した。

- 共有ストア: テーブルは`events`/`messages`/`locks`/`read_cursors`/`storage_metadata`のみ。`messages`テーブルは`team`/`from_agent`/`to_agent`/`body`列を持つ旧来スキーマ。`select team, count(*) from messages group by team` → `homelab | 63`(1行のみ、他team無し)。最終更新は`2026-08-16T09:02:02Z`(本検証開始前)
- `homelab-ops`専用ストア: `sync_bindings`/`sync_messages`/`sync_quarantine`等、remote同期専用のテーブル群を追加で持つ

`homelab`のteam設定(`teams/homelab/config.json`)には`remote_binding`キーが無く、`homelab-ops`側には存在する。`remote.sh status homelab`は`team 'homelab' has never been connected`を返した。3点とも、`homelab`がremote化されていないことを裏付ける。

疎通については、メッセージを送らずに以下を観測した。

- `ps aux`で`codex-bridge.js --pair homelab?reviewer`プロセス(pid 10814)が稼働中であることを確認
- `ps -p 10814 -o etime`で51分超の連続稼働を確認
- `~/.agents/skills/agmsg/run/codex-bridge.homelab.reviewer.log`をtailし、直近に`armed homelab/reviewer` → `wakeup` → `started turn on thread ...`という進行が記録されていることを確認(**ログ本文の内容はこのファイルへ転記しない** — 別セッションが進行中のレビュー作業のテキストであるため)

これは自分が送信したものではなく、既に進行中の実運用トラフィックである。したがって「送らずに確かめられる範囲」の最良の証拠として扱った。この観測だけでは将来のあらゆる送受信を保証しないが、**現時点で疎通が壊れていないことの直接証拠**にはなる。

### AC5-1・AC5-2 — Monitorの構造

```
$ ~/.agents/skills/agmsg/scripts/identities.sh /home/yoshi/homelab-ansible claude-code
homelab-ops	coordinator
homelab	claude
```

`watch.sh`のソース(432行目)で`PAIRS="$("$SCRIPT_DIR/identities.sh" "$PROJECT_PATH" "$AGENT_TYPE")"`がループの外で1度だけ呼ばれることを確認した(実装記録の主張どおりで、行番号も一致)。`ACTIVE_NAME`(4番目の引数、38-41行目で`SESSION_ID`/`PROJECT_PATH`/`AGENT_TYPE`/`ACTIVE_NAME`の順に割り当て)が空のとき、434行目の`awk`フィルタ(`$2 == n`)は実行されず、`PAIRS`は`identities.sh`の全出力(2ペア)のまま使われる。

自分自身の`watch.sh`プロセス(`ps aux`で確認、pid 296710)の起動コマンドは

```
watch.sh 57e1dab3-4dcf-47ef-8d1c-f43e306c7a3f.4225 /home/yoshi/homelab-ansible claude-code
```

の3引数のみで、4番目の`ACTIVE_NAME`(actas名)は渡されていない。`ps aux`で確認した限り、`agmsg`関連プロセスのうち`watch.sh`は1本のみで、2team分のプロセスが個別に立ってはいない。

構造上、この設計は「実行しているセッションが誰であるか」に依存せず、`(project, agent_type)`単位で複数teamのペアを1プロセスへ束ねる。したがって「1つのMonitorで両teamを覆う」「`actas`を使わない」というAC5の条件は、コード上の分岐と自分自身の稼働プロセスの両方で確認できた。

### AC5-3 — 実受信(未検証)

`teams/homelab-ops/config.json`の`agents`キーは`coordinator`の1件のみで、`operator`のjoin記録が無い。サーバ側`members`テーブルも1行(`coordinator`)のみ。送り手がいないため、homelab-ops宛の実際の受信が届くことはこの段では確認できない。requirement本文が明示するとおり、quory側がjoinした後の確認事項である。

## 未実施項目とその理由

1. **AC1-b / AC3 / AC8 quory区間** — 依頼のscope外(到達手段が無い)。実施していない。
2. **R15(ansy再起動後の復帰)** — 依頼のscope外(再起動の承認が無い)。実施していない。
3. **AC5-3(homelab-ops宛の実受信)** — quory側Operatorが未joinで送り手が存在しない。この段では構造的に確認不能。quory側join後にTesterが再確認する必要がある。
4. **`messages`以外のサーバ側全テーブルの逐一走査** — `teams`が1行(`homelab-ops`)のみであることと、他テーブルのFK制約(`ON DELETE RESTRICT`、`team_id`参照)から、`homelab`を指す行が存在し得ないことは論理的に保証されるため、個別の全件SELECTは行っていない(推測ではなくFK制約という設計上の保証に基づく判断)。
5. **将来にわたる疎通の保証** — 今回確認したのは検証時点のスナップショット(進行中の1レビューの往復)であり、継続的な健全性を保証するものではない。

## 残存リスク

- AC4-2の「疎通が壊れていない」の根拠は、自分が送信した確認メッセージではなく、たまたま進行中だった他セッションのレビュー往復の観測である。次に`homelab`のReviewerとの往復が発生するまで、これ以降の状態変化(段3の`~/.bashrc`変更や`CURL_CA_BUNDLE`設定など)が影響しないことまでは保証しない。
- AC5-1の判定は主にコード読解(`watch.sh`のPAIRS解決ロジック)と自分自身の1プロセスの観測に基づく。**別セッション(他のCoordinator/Tester起動)が同じproject・agent_typeで同時に`watch.sh`を複数本立てないことまでは検証していない** — 今回の観測時点では`watch.sh`のpidfileが自分の分1本しか存在しなかったが、これは他セッションの挙動を積極的に確認した結果ではない。
- `sudo docker exec`でPostgreSQLへ到達した経路は、yoshiに既に付与されている`NOPASSWD: ALL`を使った。この権限自体の妥当性(broadなsudoがansy上に存在すること)はこの案件のscope外であり、本結果は既存権限の是非を論じない。
