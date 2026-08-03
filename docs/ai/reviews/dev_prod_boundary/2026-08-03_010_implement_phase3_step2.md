# implement: Phase 3 Step 2 — 新 role `dev_investigate`(quory の read 専用受け口)

日付: 2026-08-03 (JST)
依頼: Coordinator → Implementer(このsubagent)
契約の正本: `docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md`(D5承認済み)
plan: `2026-08-03_007_plan_phase3.md` §1.3 / §1.4 / §2 Step 2

## 1. 対象パス(今回作成・変更したもの)

- `roles/dev_investigate/defaults/main.yml`(新設)
- `roles/dev_investigate/tasks/main.yml`(新設)
- `roles/dev_investigate/templates/recovery-investigate-dispatch-quory.sh.j2`(新設)
- `roles/dev_investigate/templates/authorized_keys.j2`(新設)
- `roles/dev_investigate/files/dev-investigate.pub`(依頼時点で配置済み。変更なし)
- `playbooks/dev_investigate_setup.yml`(新設)
- `playbooks/README.md`(「障害記録・振り返り」表へ1行追加。`incident_inspect_setup.yml`の直後)

`roles/recovery_exec/` を含む上記以外のファイルには一切触れていない(`git status --short`で確認。並行して動いている別subagentの未追跡ファイル・変更 — `recovery-reports-helper`のFILE_RE修正、`incident-bundle-helper`/`homelab-incident-bundle`新設、`claude-investigate*.pub`など — は現状のまま)。

## 2. 契約の充足状況

| 要素 | 実装 |
|---|---|
| ユーザー | `dev-investigate`(defaults変数`dev_investigate_user`)。sudoers作成taskは1つも存在しない(`tasks/main.yml`に`/etc/sudoers.d/`へ触れるtaskが無いことで担保) |
| 受け口 | `authorized_keys.j2`が1エントリのみ描画。forced commandは`dev_investigate_dispatch_dest`(`/usr/local/sbin/recovery-investigate-dispatch-quory.sh`固定)、オプションは`no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty`——`roles/recovery_exec/templates/authorized_keys.j2`と文字列まで同一。公開鍵は`lookup('file', 'dev-investigate.pub')`(role files/ からcontroller側で読む。ホスト側slurpは不要 — この鍵はrepo資産でありホスト固有生成物ではないため) |
| dispatch | `recovery-investigate-dispatch-quory.sh.j2` → `/usr/local/sbin/recovery-investigate-dispatch-quory.sh`。カタログ§1の20チェック(Q1〜Q12 + Q-C共通8種)を全実装。**Q-Cの8種はrecovery-investigate-dispatch.sh.j2の該当ブロックと中身を書き換えず移植**(差分は「宣言arity超過をどう拒否するか」という枠組みの違いのみ — 元は`case`のリテラル完全一致で拒否、こちらは固定arityの`read`で拒否。実行内容の文言・引数は無変更) |
| ACL | `/home/yoshi`にtraverse(x)、`/var/lib/semaphore`にtraverse(x)、`semaphore.db`にread(r)。`recovery-exec`/`incident-inspect`の既存付与と同一path・同一etype・同一permissions |
| playbook | `playbooks/dev_investigate_setup.yml`、`hosts: quory`のみ。`# tester-gate: check-mode-native`(理由文はヘッダに記載。`incident_inspect_setup.yml`と同型の論拠 — 条件1は成立、条件2は不成立、`user`/`file`/`template`/`apt`/`ansible.posix.acl`はいずれもcheck_modeでpreview可能) |
| 索引 | `playbooks/README.md`の「障害記録・振り返り」表へ、`incident_inspect_setup.yml`の直後に1行追加 |

### 契約に明記の無い追加判断: `systemd-journal`グループ

`tasks/main.yml`のユーザー作成taskに`groups: systemd-journal`(+`append: true`)を付けた。依頼のACL表には無い項目だが、Q-Cの`journal-system`/`dmesg`とQ9の`journal-unit`が`journalctl -u`/`-k`を(sudo無しで)読むには、`recovery-investigate-dispatch.sh.j2`が前提にしているのと同じ`systemd-journal`グループ所属が要る(`roles/recovery_exec/tasks/target_setup.yml`のauthy/monnie向け`recovery-exec`ユーザー作成が同じ理由で同じグループを付けている実例)。sudoではなくUnixグループでの読み取り権であり、書込・特権昇格は伴わない。契約表に無い判断のため、Reviewerに明示しておく。

## 3. 自己検証(V1〜V7)

すべて**decoy/scratchのみ**(`/tmp`のscratchpad配下)で実施。実ホストへのansible実行・接続は一切行っていない。

- **手段**: `roles/dev_investigate/templates/recovery-investigate-dispatch-quory.sh.j2`をscratchへコピーし、`exec`先の3絶対パス(`incident-bundle-helper`/`recovery-reports-helper`/`homelab-semaphore-query`)だけをscratch内のstubスクリプトへ`sed`で差し替えたテスト用コピーを作成(元テンプレートは無変更)。stubは受け取った引数をechoするだけ。
- **V1**(20チェック全件がcaseとして存在し、カタログのoperand検証と一致): 20チェック全件を正経路で実行し、正しいsubcommand/operandでstub/実コマンドへ委譲されることを確認(pass 22/22。`deployed-hash`は8 nameすべてでname→path解決を確認 — sedがdeployed-hashの内部テーブルも書き換えてしまったため、そのうち3件はstub先の絶対パスを、残り5件は本来の`/usr/local/sbin/*.py`等を指し`sha256sum: No such file`で終わる=「denied」ではない正常な失敗であることを確認)。
- **V2**(カタログに無い文字列は`denied:`+非ゼロ終了): 未知check・SQL/コマンドインジェクション風文字列で確認、全件`denied:`+rc=1。
- **V3**(宣言operand数超過は実行前に拒否): 全checkへ余剰tokenを付けて確認(トップレベルの`extra`超過、および各checkのarity guardの両方が発火することを確認。1件、期待した拒否メッセージの文言が"too many"でなく"invalid parameter count"だったが、これはテスト側の期待値の誤り — 拒否そのものは正しく発生している。arity 2の`semaphore-query`に3個目のtokenを渡すとcheck固有のarity guardが先に発火する設計であり、トップレベルguardは4個目以降にのみ対応する)。
- **V4**(改行・復帰を含む入力の拒否): `$'\n'`/`$'\r'`混入コマンドで確認、両方`denied: command contains a line break`。
- **V5**(unit/query/window/ext/ファイル名のenumのみ通す): 不正unit、不正window、不正query、非数字n、不正file名、不正id、`../`混入id、絶対パスid、不正ext、`../`混入name、で全件`denied: invalid <param>`を確認。
- **V6**(`eval`皆無、書込語彙皆無): `grep`で静的走査。`eval`はコメント中の1件のみ(コードとしては不使用)。`pvesh create/set/delete`・`systemctl start/stop/restart/enable`・`qm start/stop`・`tee`/`rm`/`mv`/`cp`はコメント以外に出現せず、唯一のリダイレクトは`resolvectl status 2>/dev/null`(stderrを`/dev/null`へ捨てるのみで、任意ファイルへの書込ではない。既存`recovery-investigate-dispatch.sh.j2`の`network`チェックと同一行)。
- **V7**(syntax-check・lint通過): `bash -n`(テンプレート自体、Jinja変数を含まない純粋な静的bashのため直接検査可能)、`ansible-playbook playbooks/dev_investigate_setup.yml --syntax-check`、`scripts/check-tester-gate.sh`(52 playbooks全件OK)、`ansible-lint playbooks/dev_investigate_setup.yml roles/dev_investigate`(0 failure / 0 warning)をすべて実施しPASS。

### Jinjaレンダリングの実地確認(追加で実施)

`ansible.builtin.template`が実際に`lookup('file', 'dev-investigate.pub')`をroleの`files/`から解決できるかを、`hosts: localhost` / `connection: local` / `become`無し / 出力先`/tmp`限定のscratch playbookで確認した(本物のroleファイルはコピーのみで無変更)。

- `authorized_keys`の描画結果: `command="/usr/local/sbin/recovery-investigate-dispatch-quory.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty ssh-ed25519 AAAA... claude@homelab-ansible` — 1行のみ、鍵内容も正しく埋め込まれた。
- `recovery-investigate-dispatch-quory.sh`の描画結果: Jinja変数を含まないため、テンプレート原文と`diff`で完全一致(IDENTICAL)。`bash -n`で構文OK。

## 4. 未解決事項・引き継ぎ

- **実配備は行っていない。** quoryへの`ansible-playbook playbooks/dev_investigate_setup.yml -l quory`実行はCoordinator/Tester側の作業として残る。
- Q1〜Q7・Q11が実際に動くには、`roles/recovery_exec`側(並行して別subagentが実装中)の`incident-bundle-helper` / `recovery-reports-helper`(FILE_RE修正込み) / `homelab-semaphore-query`がquoryへ配備済みであることが前提。今回のrole・playbookはこれらを再配備しない(依頼どおり)。
- ansy側の秘密鍵生成・`~/.ssh/config`のalias追加(plan §1.3・§2 Step 4)は本タスクのscopeに含まれず、未着手。これが無いと `ssh` 経由でのforced command到達確認(AC8/AC9/AC10/AC19/AC20)はTester段階でも別途鍵材が要る。
- 3節に書いた`systemd-journal`グループ追加は契約のACL表に明記が無い判断のため、Reviewerでの確認を要する(妥当性の根拠は3節・`roles/dev_investigate/tasks/main.yml`のコメント参照)。
- カタログ外のチェック追加は行っていない(`bundle-grep`等、カタログが明示的に除外したものは実装していない)。
