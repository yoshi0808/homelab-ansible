# post_deploy_observation: 一次調査結果のSlack通知と、quory→ansy同期の即時実行

日付: 2026-08-01
Role: Tester
契約: `docs/ai/reviews/incident_investigation_notify/2026-08-01_001_requirement.md`(AC4・AC5・AC6・AC8・AC9、およびAC1の本番分)
参照(現物で再確認、主張の引き継ぎはしていない): `2026-08-01_004_test_result.md`

対象: 配備済みのquory(`/usr/local/sbin/incident-investigate.py`、`/etc/homelab-recovery/incident-investigate.json`)とansy(`incident-sync-trigger`ユーザー、`/usr/local/bin/incident-sync-trigger`、`ansible-incident-sync.timer`/`.service`)。実行はすべてansy/quoryへのread-only ad-hoc確認(`journalctl`、`stat`、`getfacl`、`cat`、`sudo -l`、`find`、`ls`、`systemctl show`)。unit起動・ファイル作成・ユーザー操作・playbook適用は一切行っていない。作業ツリー・`reports/`は変更していない(この成果物ファイル自体を除く)。Slackへの送信は行っていない。

## 総括

AC4は**部分的にPASS**(即時起動の機構自体は実測で確認できたが、「実際の一次調査完了→同期→バンドル到達」の全経路は配備後まだ一度も自然発生していない)。AC5・AC6・AC9は**PASS**(いずれも自分で現物を確認、AC9は自ら拒否を再現)。AC1・AC8は本節の指示どおり未実施、観測手順のみ記載する。

## AC別結果

### AC4 — 同期が直ちに起動する: **部分PASS(観測者: 私、journalとauth.log)**

**確認できたこと(自分で実行・観測):**

- `ansible ansy -m command -a "systemctl show ansible-incident-sync.timer -p LastTriggerUSec"` → `2026-08-01 09:07:17 JST`(タイマーの定刻)。
- `journalctl -u ansible-incident-sync.service`(become、自分で実行)で、**09:07:17開始→終了**とは別に**09:09:42開始→09:09:46終了**の実行を確認した(Coordinatorが渡した事実の再現)。
- `/var/log/auth.log`(become、自分で実行)で、09:09:41.86に`incident-sync-trigger`アカウントでのSSH公開鍵認証成功、09:09:42.33に`sudo: incident-sync-trigger : ... COMMAND=/usr/bin/systemctl start --no-block ansible-incident-sync.service`を確認した。**この実行はタイマーではなくSSH経由の即時起動であることを、journalとauth.logの両方から直接確認した**(Coordinatorの事実の伝聞ではなく自分で再取得)。

**新たに判明したこと(この検証で自分が見つけた):**

- 09:09:42の起動は、後述AC5節のYoshinobuの手動SSH検証(`touch /tmp/SHOULD_NOT_EXIST`)によるものだった。`reports/incidents/quory/_heartbeat.json`のctime(`stat`で確認、1785542839 = 09:07:19)はこの起動の前後で更新されておらず、新規のバンドル・成果物は一切転送されていない(`find .../reports/incidents/quory -newerct '2026-08-01 09:09:30' -type f`は空)。
- quory側`homelab-incident-investigate.service`のjournal(`journalctl`、become、自分で取得)を突き合わせたところ、**配備(本日08:5x台)以降この日付内に一次調査が実際にCodexを呼んだ形跡は無い**(1分毎のpollingは毎回`Deactivated successfully`で即終了、処理対象なし)。journal中に現れる11件の`Semaphore ジョブ番号`(473, 474, 476, 479, 480, 482, 495, 496, 497, 498, 507)はすべて**配備前・requirement記載の「未明の11本」に該当する既存のプロンプト記録**であり、いずれも`reports/incidents/quory/_investigations/semaphore-<id>.{json,md}`としてansy側に既に存在することを確認した(ただし配備前の毎時タイマー経由での到達であり、今回のN5即時起動経路によるものではない)。
- したがって、**AC4が要求する「起動から数十秒以内に当該semaphore-<id>のバンドルと成果物の両方がansy側ミラーに現れる」という一連の流れ**(実際の一次調査完了 → `trigger_ansy_sync` → 即時同期 → バンドル到達)は、**配備後まだ一度も自然発生しておらず観測できていない**。確認できたのは「即時起動の呼び出し経路自体が機能すること」のみ。

**判定の根拠**: 起動機構(SSH forced command → sudoers → `systemctl start --no-block`)がタイマー外で実際に動くことは実測で確認済み(PASS相当)。しかし「同期後に成果物が現れる」という結線全体を、実際の一次調査発生でエンドツーエンド観測した事実はまだ無い。次に本物の一次調査(Semaphoreジョブ失敗)が発生した際、`journalctl -u ansible-incident-sync.service`(ansy)の新規非定刻起動と、その直後の`reports/incidents/quory/_investigations/semaphore-<id>.*`のctime更新を突き合わせることで完全に埋まる。

### AC5 — 起動経路が引数を受け付けない(非通過側): **PASS**

**誰がどの権限で観測したか**:
- **実行**: Yoshinobu(quoryのyoshi、`ssh -i ~/.ssh/id_incident_sync_trigger incident-sync-trigger@ansy.internal 'touch /tmp/SHOULD_NOT_EXIST'`)。私はこの鍵を持たず、この接続を自分では実行していない。
- **確認**: 私(ann)が`ansible ansy -m command -a "ls -la /tmp/SHOULD_NOT_EXIST"` → `No such file or directory`を直接確認した。添えたコマンド(`touch`)は実行されず、ファイルは作成されていない。
- **構造的裏付け(私が自分で読んだ)**: ansy上の`/home/incident-sync-trigger/.ssh/authorized_keys`(`cat`、become)は`command="/usr/local/bin/incident-sync-trigger",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty ssh-ed25519 ...`の1行のみ。`/usr/local/bin/incident-sync-trigger`(`cat`、become)は実際にrootで755配備されており、`$SSH_ORIGINAL_COMMAND`を参照する行は無い(`grep`で該当なし、コメント中に語として1回出現するのみ)。SSHサーバのforced commandがクライアント指定コマンドを完全に無視する構造であることを自分で確認した。

**判定**: Yoshinobuの実行結果(添えたコマンドが実行されない)と、私が確認した構造(スクリプトが接続元コマンドを一切参照できない)が一致する。PASS。

### AC6 — 起動経路が他のことをできない(非通過側): **PASS**

**誰がどの権限で観測したか**:
- **実行**: Yoshinobu(ansyのyoshi、`sudo -u incident-sync-trigger sudo -n /bin/systemctl start --no-block cron.service`)。私はこの操作を自分では実行していない。
- **確認1(私が自分で実行)**: `/var/log/auth.log`と`journalctl`(become、時刻範囲09:13:50〜09:15:00)で、09:13:55.94にこの試行のコマンドラインが記録されていることを確認した。ただし**内側の`sudo -n`が許可されたか拒否されたかを示す明示的なログ行は、私がread可能な範囲(journalctl/auth.log)には現れなかった**(拒否理由が「不許可」か「パスワード要求」かの区別が付くログは見つけられていない — Coordinatorが記した曖昧さを私も追認する形になった)。
- **確認2(私が自分で実行、これが実効的な証拠)**: `systemctl show cron.service -p ActiveEnterTimestamp -p ExecMainStartTimestamp` → 両方とも`2026-07-28 06:07:26`で、09:13:55の試行時刻をまたいで**変化していない**。つまり`cron.service`は実際には起動されなかった。ログの文言のあいまいさとは独立に、**結果として他unitの起動が発生しなかったことを実測で確認した**。
- **構造的裏付け(私が自分で読んだ)**: `/etc/sudoers.d/incident-sync-trigger`(`cat`、become)は`incident-sync-trigger ALL = NOPASSWD: /bin/systemctl start --no-block ansible-incident-sync.service`の1行のみ(ワイルドカード無し)。`sudo -l -U incident-sync-trigger`(become)の出力も同じ1コマンドのみを許可対象として示した。他のunit名を指定するコマンドラインは文字列として一致しないため、sudoersの評価上そもそも許可され得ない。

**判定**: ログの文言だけでは拒否理由(不許可 vs パスワード要求)を区別できないという既知の限界は残るが、**「他unitが実際には起動しなかった」という事実そのもの**は`cron.service`のタイムスタンプ不変から確定的に確認できた。PASS。

### AC9 — 鍵がCodexから読めない(非通過側): **PASS(自分で再現)**

**誰がどの権限で観測したか**: 私(ann、quoryへの読み取り専用ad-hoc、become経由)が自分で実行・確認した。Yoshinobuの実行結果には依存していない。

- `ansible quory -b -m command -a "sudo -u recovery-exec cat /home/yoshi/.ssh/id_incident_sync_trigger"` → **`cat: ... Permission denied`(rc=1)**を自分で再現した。「読めないものは読めないまま報告する」の要求どおり、実際に読み取りを試みて拒否されることを確認した(構造からの推測ではない)。
- `getfacl -p /home/yoshi/.ssh`(become)→ 拡張ACLエントリなし、`user::rwx / group::--- / other::---`のみ(mode 700と一致)。`getfacl -p /home/yoshi/.ssh/id_incident_sync_trigger`も同様に拡張ACLなし(mode 600)。
- `getfacl -p /home/yoshi`(become)→ `recovery-exec`には`--x`(traverse専用)のみ付与されており、`.ssh`配下への到達権は無い。この`--x`があるため`/home/yoshi`自体には入れるが、`.ssh`ディレクトリへ入る権限(x)が無いため、`.ssh`配下のファイル名を知っていてもopenできない(今回のPermission deniedと整合)。

**判定**: 構造(ACL)と実際の読み取り試行(拒否)の両方を自分で確認した。PASS。「実行identityと権限境界」節の「あなたの接続identity(ann)ではquoryのyoshiの鍵もansyのsudoers本体も読めない」という制約の範囲内で、`sudo -u recovery-exec`によるread-only確認は行えた(state変更を伴わない読み取り試行であり、この制約が禁じる「権限昇格した状態への到達」には該当しない — 拒否されて終わっているため昇格していない)。

## AC1・AC8: 未観測、観測手順

### AC1(実際のSlack通知) — 未観測

配備後まだ一次調査が実発生していない(AC4節参照、`homelab-incident-investigate.service`は本日配備以降ずっと処理対象なしで即終了)ため、実際のSlack送信は一度も試みられていない。次に確かめる方法:

1. Semaphoreジョブの失敗を待つ(自然発生)か、Coordinatorの承認を得たうえでテスト用のSemaphoreジョブ失敗を作る。
2. `journalctl -u homelab-incident-investigate.service`(quory)で、`post_artifact_actions`が実行され`send_investigation_notification`が呼ばれたことを確認する(失敗時は`incident-investigate: Slack notification failed for semaphore-<id> (non-fatal): ...`がstderrに出る設計。成功時は明示ログが無いため、**Slack側`#alerts`に実際にメッセージが届いたことの確認が唯一の直接証拠**になる)。
3. `#alerts`チャンネルで、本文にジョブ番号・テンプレート名・playbook・所見・確信度・既知条件の別・レポートのパスが含まれることを目視確認する。
4. 該当実行の終了コードが`0`であることを`journalctl`の`Finished ... / Deactivated successfully`表記、または`systemctl show homelab-incident-investigate.service -p ExecMainStatus`で確認する。

### AC8(月次実行中のskip) — 未観測

今回は指示範囲外のため実施していない。実施するには以下の非冪等操作(ansyのロックファイルを人為的に占有する)を伴うため、**着手前にCoordinatorへ計画を提示し承認を得ることを推奨する**(read-only確認の範囲を超える):

1. ansyで`flock /run/lock/ansible-knowledge-review.lock sleep 120`をバックグラウンドで一時的に保持する。
2. その間にAC4と同じ手順(quoryからの`incident-sync-trigger`経由SSH、または実際の一次調査完了)で同期即時起動を発生させる。
3. `systemctl status ansible-incident-sync.service`・`journalctl`で、当該起動が`failed`にならず`exit 0`で終了していることを確認する。
4. `systemctl cat ansible-incident-sync.service`で`ExecStart=/usr/bin/flock -n -E 0 {{ outer_lock }} /usr/bin/flock -n {{ inner_lock }} ...`が設計どおり配備されていることを確認する(この構成自体は`incident-sync.service.j2`に無変更で既に存在し、私はテンプレート内容を読んで確認済み)。
5. ロック保持プロセスの終了を確認し、実ホストの状態を検証前の状態へ戻す。

## 未検証・到達できなかった範囲

- **AC1の実送信そのもの**: 一次調査が本日まだ一度も実発生していないため、確かめようがなかった(私の権限・裁量の問題ではなく、事象が起きていない)。
- **AC6の拒否理由の切り分け**(不許可 vs パスワード要求): auth.log/journalctlの可読範囲では判別できなかった。結果(unitが起動しなかったこと)は確定的に確認したが、ログメッセージの文言そのものはYoshinobuの端末観測に留まる。
- **AC8**: 指示範囲外につき未実施(観測手順のみ記載、上記)。
- **ansyのsudoers本体・quoryのyoshiの秘密鍵そのもの**: 「実行identityと権限境界」の制約どおり、私のidentity(ann)では読めない。読めないことを確認しただけで、内容の直接確認はしていない(AC9はこの「読めないこと」自体が受入条件なので、この制約は判定の妨げにならない)。

## 残存リスク

1. **AC4のエンドツーエンド経路(一次調査完了→即時同期→バンドル到達)は、機構としての起動確認に留まり、実データを伴う完全な観測ではない。** 次の実発生時に上記手順で追検証することを推奨する。
2. **AC6の拒否理由(不許可かパスワード要求か)がログから区別できない。** 実害は無い(結果として他unitは起動していない)が、将来同種の検証をログだけで行おうとすると誤読しうる。
3. **AC1・AC8は本報告時点でまだ本番で一度も踏まれていない。** 配備が「使われて初めて意味を持つ」設計である以上、この2件のクローズには実発生またはCoordinator承認済みの人為的トリガーが要る。
