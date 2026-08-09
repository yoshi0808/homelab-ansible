# Operations Context: コードが本番へ届くまで

作成日: 2026-08-03

**位置づけ**: ansyで書いたコードがquoryの本番実行へ届くまでの経路と、その各区間で「何が更新され、何が更新されないか」を記録する。単一roleの説明ではなく、**すべてのrole・playbookの配備に共通する事実**である。

値(timer間隔、閾値、パス)はここに写さない。正本は `roles/worktree_sync/defaults/main.yml` と各roleのdefaults。

## 1. 経路

```text
ansy(開発)
  │  git commit / git push  ← Yoshinobuの都度承認(ask)。ここが唯一の人間ゲート
  ▼
GitHub(origin/main)= 確定済みコードの正本
  │  git pull --ff-only     ← quoryのtimerが自動で行う(worktree_sync)
  ▼
quory /home/yoshi/homelab-ansible(作業ツリー)
  │  setup系playbookの実行   ← **自動ではない。人がSemaphoreから流す**
  ▼
/usr/local/sbin/, /usr/local/bin/, /etc/systemd/system/ ...(配備物)
  │
  ▼
Semaphore schedule / systemd timer が実行
```

**承認は `git push` の1回に畳まれている。** 「コードを確定してよい」と「いま本番へ入れてよい」を分けない判断(2026-08-03、`docs/ai/reviews/quory_worktree_sync/`)。pushした内容は次のtimer周期でquoryへ入る。

## 1.1 日常の流れ — 変更1つに対して、人は何回押すか

| # | 起きること | 誰が |
|---|---|---|
| 1 | ansyで修正してstage | AI |
| 2 | **pre-commitが「配備が要る: `playbooks/X_setup.yml`」と予告する**(カタログに載る`copy`配備物を触った場合。§2) | 自動 |
| 3 | `git commit` / `git push` | **人が承認**(AIが実行) |
| 4 | quoryが作業ツリーをpull(1分間隔)。Semaphoreはジョブ実行時に`/opt`へ自分でcloneする(§3) | 自動 |
| 5 | **配備物はまだ古い** | — |
| 6 | Semaphoreで該当templateを押す。**テンプレートから新規に起動する**(過去のタスクの再実行では古いcommitが走る。§3.1) | **人** |
| 7 | 押し忘れた場合、翌00:40の日次ドリフト検査がSlackへ「食い違い + 直し方」を出す(§2) | 自動 |
| 8 | 直すまで毎朝再通知される(エッジ抑止が無い) | 自動 |

**打鍵が要るのは3と6だけで、どちらも「判断」である。** コマンドを組み立てる作業は残っていない — 状態を変えない確認はAIがdispatch経由で行い、本番への適用はSemaphoreのボタンが担う。

**逆に、3と6を自動化してはならない。** そこが人間のゲートそのものである(`docs/ai/core.md`「人間の権限と安全境界」)。2026-08-04に、配備をansy側から起動できるようにする案を検討して**却下した** — ansyに本番へのroot適用を発火する能力を与えることになり、能力の不在で作った境界が消えるため。

### 何が守られていて、何が守られていないか

| 対象 | 日次検査 |
|---|---|
| `copy` 配備物の**内容** | ある(sha256で比較) |
| systemd unit の enabled / active | ある。**timerが止められたことはここでしか分からない** |
| forced command 鍵の構造(エントリ数・`command=`始まり) | ある |
| `/etc/hosts` の網羅 / `reports/` の所有権 | ある |
| **`template` 配備物の内容** | **無い**(Tier 2、未着手)。unit本体・sudoers・dispatch script等が該当 |
| **Semaphore template / schedule の内容** | **無い**(未実装)。定義の正本は`roles/semaphore_templates/`だが、UIで書き換えられても**次にreconcileを流すまで検出されない**。流せば差分として出る(§7) |
| Semaphore の inventory / environment | 無い。カタログの対象外である |

## 2. 最も重要な事実 — `git pull` は配備物を更新しない

**作業ツリーが最新になっても、そこから配備されたものは古いままである。**

`/usr/local/sbin/` や `/etc/systemd/system/` にあるscript・unitは、setup系playbookが**コピーした結果**であり、gitの管理下にない。repoを直してpullしても、**playbookを流すまで実物は変わらない**。

**この形は実際に5回起きている。**

| 事例 | 症状 |
|---|---|
| `incident-capture-collector.py` | 必須フィールド集合が旧版のまま |
| `recovery-probe.py` | 削除したはずのdrillが両ホストで生存 |
| `recovery-investigate-dispatch-quory.sh`(2026-08-03) | repoに追加したチェックが使えない |
| `homelab-semaphore-query`(2026-08-03) | 同上 |
| `incident-investigate.py`(2026-08-04) | 退役した `incident_sync` の受け口を叩き続け、Slack通知が**もう作られないansy側ミラーのパス**を案内する |

**前2件はWatchでは拾えず、実機を見て初めて気づいた。5件目は日次ドリフト検査が自動で拾った**(初稼働の翌朝、`copy` 配備物であったため)。

**変更が配備物へ届いていない期間は、repoと本番が「別々の世界を前提に動く」状態になりうる。** 5件目がその実例で、ansy側の受け口は撤去済みなのに quory の旧スクリプトはそれを呼び続けていた。個々の失敗はnon-fatalに設計されていても、**両側を同時に変える案件では、退役側を消す前後どちらで配備するかが挙動を決める。**

### 突合の手段

`deployed-hash` が固定の名前対応表を持っており、**説明ではなく現物のsha256で比較できる**。

```bash
sha256sum roles/<role>/files/<script>              # repo側
ssh quory-investigate "deployed-hash <name>"       # quory側
```

対応表にあるのは `recovery-probe` / `incident-capture-collector` / `incident-investigate` / `recovery-push-dispatch` / `reports-helper` / `bundle-helper` / `semaphore-query` / `investigate-dispatch-quory`。**ここに無いものは、この手段では確かめられない。**

**識別子や機構を撤廃する案件では、受入条件に「配備物側にも残っていないこと」を含める**(`skills/requirements-analysis/`)。

### 気づくための2点(2026-08-04 新設)

**commit する時点** — `roles/*/files/` 配下のうちドリフト検査のカタログに載っているものを stage すると、pre-commit が「**配備が要る**」と、流すべきplaybookを添えて出す(`scripts/check-deploy-needed.py`)。**commitはブロックしない** — 配備はcommitの後の工程だからである。`roles/*/templates/` の変更は「配備が要る可能性」として**推定で**別枠に出る(下記のとおり内容までは検査できないため)。

**ドリフトが検出された時点** — 通知とJSONレポートの各findingに `直し方: ansible-playbook <playbook> -l <host>` が載る。

この2つは**同じカタログ**(`roles/deployment_drift_check/defaults/main.yml`)を読む。対応表を二重に持たないための設計であり、片方だけを直さない。

**「直し方」が載らないfindingがある。** 流しても直らないものには意図的に書いていない — playbookが `enabled` しか管理せず `active` を戻さない場合や、無効化のtask自体が存在しない場合である。**書いてあれば直る、書いていなければ自分で調べる**、と読むこと。判断根拠は `docs/ai/reviews/deploy_awareness/2026-08-04_002_implement.md`。

### 日次のドリフト検査が拾う範囲

`playbooks/deployment_drift_check.yml`(`safe-readonly`、日次 00:40)が**自動で突合する**。対象カタログは `roles/deployment_drift_check/defaults/main.yml` が正本。

**`copy` 配備物は内容まで見るが、`template` 配備物は見ない。** 期待値を得るのに描画が要るためで、dispatch script・sudoers・unit本体・`worktree-sync.sh` などが該当する(Tier 2、未着手)。**この穴は特定のroleの問題ではなく、配備方式で決まる。** `template` で配備したものは、日次検査に守られていないと考えること。

unit の `enabled` / `active` は別軸で見ており、**timerが止められたことはここでしか検出できない** — 同期が呼ばれなくなっても、それ自体は通知を出さないため。

## 3. 自動同期(`worktree_sync`)が行うこと・行わないこと

**行うこと**は `git pull --ff-only` だけである。

**行わないこと**を明示する。

- **作業ツリーが汚れていたら、直さずに止まる。** `git checkout` / `restore` / `stash` / `reset` / `clean` は実行経路のどこにも存在しない。**quoryではリポの内容を直接修正しない。必ずansyで修正したものを配布する**(2026-08-03 Yoshinobu明示)ため、汚れている状態は起きてはならない異常であり、自動で解消しにいくのが誤りである。
- **履歴が分岐していたら、rebaseもmergeもしない。** 分岐は「quoryにansyを通っていないcommitがある」ことを意味し、汚れと同じ規範違反である。通知の文面も分けてある。
- **配備はしない**(§2)。

### Semaphoreジョブとの関係

**訂正(2026-08-04、Yoshinobu明示)**: **Semaphoreは `/home/yoshi/homelab-ansible` を使っていない。** ジョブ実行のたびに**GitHubから自分で clone し、`/opt` 配下**で実行する(このcloneにSemaphoreのrepository設定が持つgithub鍵が要る)。`/home/yoshi/homelab-ansible` は**人が手でコマンドを叩くとき**と、`reports/` の置き場として使われる。

したがって、以下の「同じ作業ツリーを共有する」という前提に立つ記述は**成り立たない**。`worktree_sync` が実行中タスクを見て同期を見送る仕組みは現に動いているが、**それが防いでいるとされたハザードは、この前提の上に立っていた**。仕組み自体の要否は再検討の対象であり、`docs/ai/status.md` に置いた。

**AIはquoryの `/opt` を観測できない**(dispatchにファイルを見るチェックが無い)。ここはYoshinobuの明示によって知られている事実であり、観測で裏を取ったものではない。

### 3.1 再実行(relaunch)は commit を固定する — **押し方で実行される版が変わる**

**過去のタスクを再実行すると、そのタスクが走ったときの commit が引き継がれる。** repoを直してpushしても、再実行では**古いコードが走る**。

2026-08-06に実測した。#587(テンプレートから新規起動)と #588(#587の再実行)のジョブログ:

| | #587 | #588 |
|---|---|---|
| ログ | `Get current commit hash` / `Get current commit message` | `Checkout repository to f90f4e88...`(detached HEAD) |
| 意味 | ブランチのHEADを解決した | **commitが固定されていた** |

#588 は `f90f4e8..c99d249  main -> origin/main` と**新しいcommitを取得したうえで**、`f90f4e8`(#587 が走った時点のHEAD)を checkout していた。結果、カタログの更新が反映されず、`new: []` で終わった。

**この経路がいちばん自然に踏まれるのは、失敗したジョブを直したときである。** 「ジョブが失敗 → コードを直してpush → 失敗したジョブを再実行」の流れをたどると、直した版は走らない。**同じ失敗が再現し、「直っていない」と読み違える。**

- **repoの変更を反映させたいときは、テンプレート一覧から新規に起動する。**
- 再実行が正しいのは、**同じ版をもう一度走らせたいとき**(一時的な到達不能のリトライなど)だけである。
- **ジョブログの `Checkout repository to <sha>` の有無で、どちらだったかが後から判別できる。** 新規起動なら `Get current commit hash` が出る。

以下は訂正前の記述である。**判断の根拠に使わないこと。**

> Semaphoreは**同じ作業ツリー**を使う。ジョブ実行中にpullが走ると、ansible-playbookが「一部は旧版、一部は新版」のツリーを読みうる。**これは「古いまま走る」より悪い** — 古いだけならその版として一貫しているが、混ざったものはどの版としても正しくない。

そのため同期は `semaphore.db` を直接読み、実行中のタスクがあれば**見送る**(待たない・殺さない・強行しない)。判定は終端status語彙(`success` / `error` / `stopped`)の**否定**で書いてあり、未知の値が現れても安全側へ倒れる。

**確認とpullのあいだにジョブが始まる競合は消せない。** Semaphoreは我々の管理下になく、lockを尊重させられない。これは受容した残存リスクである。

**`flock` はこの排他とは別物。** unitの `ExecStart` を包む `flock -n` が防ぐのは同期unit自身の多重起動だけである。混同しない。

## 4. 稼働の確認 — Slackの沈黙を根拠にしない

**異常系の通知はエッジ検出であり、同じ状態が続くあいだは一定間隔でしか再通知しない。** したがって**「鳴らない」は「正常」と「抑止中」の両方を意味する**。

一次情報はjournalである。

```bash
ssh quory-investigate "journal-unit worktree-sync.service 24h"
ssh quory-investigate "semaphore-query running 20"   # 見送りが続く理由の調査
```

**この抑止は1分間隔のtimerに対する設計である。** 人が直すまで続く状態(汚れた作業ツリー等)を毎周期通知すると、1時間に60通になる。初回と、別の異常へ変わったときは即通知されるので気づきは遅れない。

### 閾値を回数で持たない

見送りの閾値は**経過時間**で持つ。回数で持つと閾値の意味がtimer間隔に依存し、**間隔を変えたときに黙って壊れる**。実際、5分間隔前提の「3回」を1分間隔へ移すと3分で発火し、数分かかるのが普通のhealthcheck系ジョブで毎朝鳴る状態になっていた(実装中に発見、`docs/ai/reviews/quory_worktree_sync/2026-08-03_004_implement_1min.md`)。**周期に依存する閾値は、周期を変えたときに検算する。**

## 5. 壊れ方はすべて安全側

| 異常 | 何が起きるか |
|---|---|
| `git fetch` が失敗(GitHub到達不可) | pullされない。エッジ検出つきのerror通知 |
| `semaphore.db` が読めない・スキーマが違う | 判定が失敗し、**「実行中」とみなして見送る** |
| 作業ツリーが汚れている / 履歴が分岐 | `--ff-only` を試す前に止まり、通知 |
| 同期unitが多重起動しかけた | `flock -n` が弾き、`SuccessExitStatus=75` で正常終了として扱う |

**黙って古いまま進む経路も、黙って壊れたコードを配る経路も無い。** ただし§4のとおり、**沈黙は稼働の証明にならない。**

## 6. `playbook自身にGit更新を行わせない`

`docs/ai/core.md` の原則。同期は素のシェルスクリプトが行い、通知だけをAnsible playbookへ委ねている。**playbookが自分の走っている作業ツリーを更新すると、実行途中でroleやtemplateが差し替わりうる。** §3のSemaphore同時実行と同じ危険である。

新しく「gitを触る自動化」を作るときは、この分離を崩さない。

## 7. Semaphore の template / schedule はどう届くか(2026-08-10 新設)

**ここだけ配備の形が違う。** §2 が扱うのはファイルのコピーだが、こちらは **Semaphore の REST API へ reconcile する**。届け先はディスクではなく Semaphore の DB である。

正本は `roles/semaphore_templates/defaults/main.yml`。**「どの playbook をボタンにするか」(template)と「いつ押されるか」(schedule)の両方**がここにある。

### 届くまで

| # | 起きること | 誰が |
|---|---|---|
| 1 | カタログを直して commit / push | **人が承認**(AIが実行) |
| 2 | quory が作業ツリーを pull | 自動 |
| 3 | `SEMI-SAFE: Semaphore templates setup` を **Dry Run つき**で押し、差分を読む | **人** |
| 4 | 差分が意図どおりなら、Dry Run を外して押す | **人** |

**起動ダイアログの Dry Run が `--check` に対応する。** この template の `arguments` は空で、`--check` は引数として埋め込まれていない。読み取り(token・名前解決・GET・差分計算・レポート保存)は Dry Run でも本実行され、**API への書き込みだけが抑止される**。

**押すまで Semaphore 側は変わらない。** §2 の配備物と同じで、pull だけでは届かない。**そして §1 の表のとおり、押し忘れを日次検査が拾う仕組みは無い。**

差分は `reports/semaphore-templates/` と `reports/semaphore-schedules/` の `latest.json` に残る(quory 側)。AI は `report-show` で読める。

### schedule を触るときの規則

- **UI で一時的に変えてよい。** 禁じる仕組みではなく、**一時的な変更が恒久化しない**ことを保証するのが目的である(Yoshinobu、2026-08-10)。次の適用でカタログの値へ戻る
- **戻る対象は cron・対象 template・`task_params`・無効化の4つ。** `false → true`(有効化)だけは別扱いで、下記の4条件が揃わない限り発行されない
- **削除は行わない。** カタログに無い schedule に DELETE を出す経路が存在しない
- **closed-world フェーズに入っている**(2026-08-10)。カタログに無い schedule を検出したら、**preflight で書き込みを1件も出さずに停止する**。消さずに知らせる形である
- **新しい playbook を足すときは、template と schedule を同じ変更で決め、既存の実行時刻と競合しない cron を選ぶ。** schedule を先に作ってはならない — schedule が指す template は適用時点で実在している必要があり、同一変更で両方を足す場合は **template を先に適用する2段階**になる

有効化の4条件: closed-world フェーズであること / 管理外が0件であること / **実行ごとの明示的な許可**(`-e semaphore_schedules_allow_activation=true`、既定は不許可)/ 書き込み先の API URL がカタログの canonical な本番 URL と完全一致すること。

### Git から復元できる範囲

**「定義」は戻せるが、「動いている状態」までは戻らない。**

- 新規作成は**常に無効**で行われる。復元後に定期実行を再開させるには、上記4条件を満たす別の実行が要る
- **template を先に戻す必要がある**(schedule の解決先が実在しないと停止する)
- **`run_at` / `type` / `delete_after_run` は管理していない。** cron スケジュールでは使われておらず(実測で全件 NULL / 空)、失われる値が無いためである
- **この復元経路は一度も通っていない。** 19件はすべて既存で、POST を発行したことがない。**新規作成時の必須フィールドは未確認**(`docs/ai/reviews/semaphore_schedules_as_code/2026-08-10_025_closeout.md` §3)。20件目を足すときが初回になる
