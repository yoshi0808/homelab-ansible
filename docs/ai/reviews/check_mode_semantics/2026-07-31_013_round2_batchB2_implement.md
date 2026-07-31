# implement: Round 2 バッチB-2 — `recovery_exec_setup` の `check-mode-native` 変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §4 バッチB-2、§5 R1〜R6、§6 AC1〜AC5
テンプレート: `docs/ai/reviews/check_mode_semantics/2026-07-31_007_round2_batchA_implement.md`、`.../2026-07-31_010_round2_batchB1_implement.md`(手順の正本。本記録は差異と適用結果のみ書く)

対象1 playbook: `playbooks/recovery_exec_setup.yml`(role: `roles/recovery_exec/`、`tasks/main.yml` 32task + `tasks/target_setup.yml` 18task)。バッチC(`cert_renew` / `codex_update_check`)は対象外で、一切触れていない。

## 1. 変更ファイル

- `playbooks/recovery_exec_setup.yml`
- `roles/recovery_exec/tasks/main.yml`
- `roles/recovery_exec/tasks/target_setup.yml`

`roles/recovery_exec/handlers/` は存在しない(`find`で確認済み)。他のファイル(`defaults/main.yml`、`files/*`、`templates/*`)は変更していない。対象playbook自体(`--check`の有無を問わず)は一度も実行していない。

## 2. 破壊的task 50個の判定

### 2.1 main.yml(32task中30task destructive、2task無変更)

30taskすべて独立した破壊的操作(`user`/`file`/`command`+`creates:`/`template`/`copy`/`apt`/`ansible.posix.acl`)で、TS-014の個別task単位で`when: not ansible_check_mode`+`tags: [destructive]`をゲートした。block(TS-015)は使っていない — 理由は2.3節。

無変更の2task:
- **`Assert quory is part of this run when target distribution is enabled`**(task 31、ハードコードguardの一部)。`assert`は`ansible.builtin.assert`が`--check`下でも常に評価されること(ゲート不要)をdecoy検証で確認した(§4参照)。requirementの「到達してはいけない状態」に従い、この task の条件式・文言・位置を一切変更していない。
- **`Setup recovery-exec on target nodes (quory only)`**(task 32、`include_tasks: target_setup.yml`)。既存の`when:`(`recovery_exec_setup_targets`かつ`inventory_hostname == 'quory'`)を無変更のまま維持し、check_mode次元のゲートは`target_setup.yml`側の内部taskに配った。これはbatchAの`recovery_probe`(scope内role)方式(§2.3、「role内部の個々のtaskへ...を配った」)と同じ判断: `target_setup.yml`は編集可能なscope内ファイルであり、呼び出し側を丸ごとゲートする必要がない。

### 2.2 target_setup.yml(18task全て destructive またはchain依存によりゲート)

18taskすべてに`when: not ansible_check_mode`+`tags: [destructive]`(1taskのみ既存`when`とAND)を付けた。内訳:

| task | 種別 | ゲートした理由 |
|---|---|---|
| Slurp investigate public key | 読み取り専用(slurp) | **本来ならR5でcheck_mode:falseを検討する対象だが、逆にゲートした。** `ansible.builtin.slurp`はcheck_modeをネイティブ支援し`--check`下でauto-skipされない(`command`/`shell`のcreates無し版と違う)。main.ymlの鍵生成task(3,4,5)が`--check`でゲートされ未生成のまま(fresh host想定)だと、ungatedなslurpは実際にファイル読み込みを試みて`File not found`でtask失敗しplaybook全体が非0で止まる(§4のdecoy検証で実測)。ゲートして鍵生成taskと同じ条件で揃えることで、fresh hostでも`--check`が完走する |
| Slurp action public key | 同上 | 同上 |
| Slurp PVE investigate public key | 同上 | 同上 |
| Create recovery-exec user on target nodes | 破壊的(user, delegate_to, loop) | 独立した破壊的操作 |
| Create .ssh directory on target nodes | 破壊的(file, delegate_to, loop) | 独立 |
| Deploy investigate dispatch script on target nodes | 破壊的(template, delegate_to, loop) | 独立 |
| Deploy recovery-loki-helper on target nodes with Loki | 破壊的(copy, delegate_to, loop) | 独立。既存の`when: "'loki' in target_item.investigate_services"`は置換せずlistでAND追加(R4の「既存whenへの追加、置換ではない」を厳守) |
| Deploy action script on target nodes | 破壊的(template, delegate_to, loop) | 独立 |
| Deploy sudoers for recovery-exec on target nodes | 破壊的(template+validate, delegate_to, loop) | 独立 |
| **Deploy authorized_keys on target nodes** | 破壊的(template, delegate_to, loop) | **2026-07-08にquoryで3日間のSSH障害を起こした当のtask。** `authorized_keys.j2`が`_investigate_pubkey.content`/`_action_pubkey.content`(上記slurp)を参照するため、slurpと同じ条件でゲート。**インシデント再発防止の実体はmain.ymlのハードコード`quory`guardであり、この`when:`は check-mode の dry-run/apply 切替のみを担う** — 混同しないようコメントで明記した |
| Create recovery-exec user on pve target nodes | 破壊的(user, delegate_to, loop) | 独立 |
| Create .ssh directory on pve target nodes | 破壊的(file, delegate_to, loop) | 独立 |
| Deploy investigate dispatch script on pve target nodes | 破壊的(template, delegate_to, loop) | 独立 |
| Deploy sudoers for recovery-exec read-only investigation on pve target nodes | 破壊的(template+validate, delegate_to, loop) | 独立 |
| Deploy authorized_keys on pve target nodes | 破壊的(template, delegate_to, loop) | `_investigate_pve_pubkey`を参照するため、対応するslurpと同じ条件でゲート(上記と同じ理由) |
| Add target host keys to recovery-exec known_hosts | 破壊的(known_hosts, loop) | `key:`引数が`lookup('pipe', 'ssh-keyscan -H ' + target_item.host)`という生きたネットワークプローブを埋め込んでいる。`when:`はtask引数のtemplating前に評価されるため、ゲートするとssh-keyscan自体が発火しないことをdecoy検証で確認(§4)。また後続の「Set known_hosts ownership」がこのtaskの生成物(known_hostsファイル)に依存するため、同条件で揃えた |
| Add pve target host keys to recovery-exec known_hosts | 同上 | 同上 |
| Set known_hosts ownership | 破壊的(file, implicit state=file) | 上記2taskが`--check`でゲートされ未生成の場合、対象パスが存在せず`state=file`のfileタスクが失敗しうる(§4のdecoy検証で確認)。同条件でゲートし、揃って skip させる |

### 2.3 block(TS-015)を使わなかった理由

`recovery_push/sender_setup.yml`(batchB1)は`Generate→Lock→Slurp→Store`という**連続した**4taskを1つのnamed blockでゲートした。本roleでも同型の依存(鍵生成→chmod→slurp→配布)が存在するが、**依存元と依存先がファイル内で連続していない**:

- main.yml内: 鍵生成(task 3,4,5)→chmod(task 6)は連続しているため block化も可能だったが、**両者ともそれ自体が破壊的taskであり、TS-014の個別ゲートでも同じ条件を共有すれば挙動は同一**(§4のdecoy検証で確認)。diffを最小に保つため個別ゲートを採用し、コメントで依存関係を明記した。
- target_setup.yml内: slurp(task 1,2,3、ファイル冒頭)→authorized_keys配布(task 10,15、ファイル後半)の間に、依存しない6独立task(create user/ .ssh dir/ dispatch script/ loki helper/ action script/ sudoers)が挟まっている。これらをblockでまとめるには依存task同士を隣接させる**再配置**が必要になり、`.ssh`ディレクトリ作成(task 5)がauthorized_keys配布(task 10)より先に実行される、という正しさに必要な既存の実行順序を崩すリスクがある。requirementのAC2(通常実行の不変)と「最小差分」を優先し、個別ゲート+コメントによる依存関係の明示を選んだ。

いずれのケースも、**依存元・依存先が同一の`when: not ansible_check_mode`条件を共有していれば、block化と個別ゲートは`--check`下の実行結果として等価**であることを§4のdecoy検証(fresh host / 既存host双方)で確認した上での判断である。

## 3. R1〜R6充足状況

| # | 内容 | 充足 |
|---|---|---|
| R1 | ヘッダを`check-mode-native`へ変更、TS-009条件1・2の両方に言及 | 実施。条件1(実害は単一ホストのローカル変更+guard済みtarget distributionに限定)は満たすが条件2(本体操作を省いた検証には価値がない)は満たさない、の構成。2026-07-11に追記されたインシデント経緯・ハードコードguardの記述はそのまま保持し、「このguardは今回の変換で一切変更していない」旨を追加した |
| R2 | Round1の`--check`停止assertを除去 | 実施。`"[migration] --check has no dry-run here — refuse and stop before any changes"`のassertを削除した |
| R3 | role importの`check_mode: false`カスケードを除去 | 実施。playbookの`import_role`から`check_mode: false`を削除した |
| R4 | 破壊的task全てにwhen+tags | main.yml 30task、target_setup.yml 18task、計48taskに適用(§2)。既存の`when:`(lokiヘルパー1箇所)はlistでAND追加、置換していない |
| R5 | check_mode非対応moduleの診断taskにcheck_mode: false+理由コメント | **該当なし。** 本roleに`creates:`/`removes:`無しの`command`/`shell`/`uri`は存在しない(3つのssh-keygenと mkdir はいずれも`creates:`あり)。代わりに、通常ならR5の対象になりそうな`slurp`(read-onlyだがcheck_modeをネイティブ支援するためauto-skipされない)を**逆に明示的ゲートする**必要があることが本batch固有の発見であり、§2.2・§4で詳細に検証・記録した |
| R6 | 停止assert除去に伴うskip_notifications案内の除去 | 該当なし(fail_msgに`skip_notifications`の言及なし、grep確認済み)。ただし停止assert(R2で削除)を前提にしていた`vars:`セクションの死んだコメント(`# skip_notifications: "{{ ansible_check_mode }}" removed 2026-07-31 (R2...)`、3行)は、batchB1の`recovery_io_setup`/`incident_inspect_setup`と同じ理由(ダングリング参照の放置回避)で併せて削除した |

## 4. 自己検証

- main.yml 32task・target_setup.yml 18task、計50taskを通しで読み、`delegate_to`付きtask(target_setup.ymlの15task)、`loop:`付きtask(main.yml 6task・target_setup.yml 12task)、`include_tasks`(main.yml末尾)を含め、破壊的分類とゲート漏れの有無を確認した。handler・`always:`・`rescue:`は本roleに存在しない(`find roles/recovery_exec -iname '*handler*'`で確認、`rescue:`/`always:`は`grep`で不在確認)。
- `ansible-playbook playbooks/recovery_exec_setup.yml --syntax-check`と、3ファイルの`python3 -c "yaml.safe_load(...)"`がいずれも成功することを確認した。
- `bash scripts/check-tester-gate.sh`が`OK (46 playbooks)`(AC4)。
- `grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l`が6→5になったことを確認した(AC5、最終値。残る5本は非ゴール3本+バッチC2本、想定どおり)。
- `ansible-lint`を変更前後(`git stash`で比較)で実行し、新規に導入した違反が無いことを確認した。3件の`var-naming[no-role-prefix]`(`_investigate_pubkey`等)は変更前から存在する既存debtで、行番号がシフトしただけ(内容は同一)。
- **実装対象playbookそのものは実行禁止のため**、`/tmp`のscratchpad上にansible_connection: local・実host名なしのdecoy playbookを作り、以下を実測した(すべて実行後に削除、実行した事実をここに残す):
  1. **`owner:`/`group:`に存在しないローカルユーザー名を指定した`file`/`copy`taskは、`--check`下では失敗せず`changed`を報告するだけ**(chown解決は警告止まりで、実際のchownを試みるのはcheck_modeでない時だけ)。通常実行では実際に失敗する(`chown failed: failed to look up user`)ことも確認した。これはmain.yml/target_setup.ymlの大半のtaskが`recovery_exec_user`という(fresh hostではまだ存在しない)ユーザーをowner/groupに指定していても、個別ゲートだけで安全な理由の根拠。
  2. **`ansible.posix.acl`は`entity:`に存在しないユーザーを指定すると`--check`下でも`setfacl`呼び出し自体が失敗する**(`setfacl: Option -m: Invalid argument`)。これがmain.ymlのACL grant task(4箇所)に「Create recovery-exec user」と同じ条件でゲートを揃えることが必須である根拠。
  3. **`ansible.builtin.slurp`は存在しないファイルに対し`--check`下でも実際に読み込みを試みて失敗する**(`command`/`shell`の`creates:`無し版のような自動skipが効かない)。これがtarget_setup.ymlの3 slurp taskを明示的にゲートする根拠。
  4. **`file`モジュールの暗黙`state: file`(pathが存在しない)は、依存元task(鍵生成)と依存先task(chmod)が同一の`when: not ansible_check_mode`でともにゲートされていれば、`--check`下で両方ともskipされ失敗しない**ことを確認した(block不要の根拠)。
  5. **`when:`は`false`のとき、モジュール引数内の`lookup('pipe', ...)`を含め他の引数のtemplatingごと評価せずtaskをskipする**ことを、存在しないコマンドへの`lookup('pipe', ...)`を仕込んだdecoy taskで確認した(known_hosts taskのゲートがssh-keyscanの発火自体を防ぐ根拠)。
  6. **`ansible.builtin.assert`は`--check`下でも常に評価される**(ゲート不要)ことを、`that: [false]`のassertが`--check`下でも`fatal`になることで確認した(main.ymlのquoryハードコードguardを無変更のまま残せる根拠)。
  7. **エンドツーエンドの再現**(main.yml+target_setup.ymlの構造を模した7taskのdecoy playbook、user/file/command+creates/acl/slurp/copyの連鎖): (a) fresh host(状態ゼロ)での`--check` → rc=0、対象6task全てskip、クラッシュなし。(b) 同じfresh hostでの通常実行 → rc=0、実際に鍵生成・ACL付与・authorized_keys相当ファイル生成が成功。(c) provisioned済みhostでの`--check`再実行 → rc=0、全skip、冪等。
- `git status`/`git diff --stat`で変更が`playbooks/recovery_exec_setup.yml`・`roles/recovery_exec/tasks/main.yml`・`roles/recovery_exec/tasks/target_setup.yml`の3ファイルのみであることを確認した。`roles/recovery_exec/tasks/target_setup.yml`内の`quory`リテラル2箇所(`'quory' in ansible_play_hosts_all`、`inventory_hostname == 'quory'`)は`grep`で無変更を確認した。
- decoyディレクトリと一時ファイルはすべて検証後に削除済み(`/tmp/claude-1000/.../scratchpad/decoy/`配下)。

**行っていない検証(Testerの領域、AC1〜AC3):** `playbooks/recovery_exec_setup.yml`そのものを`--check`付き/無しで実行し、終了コード・`PLAY RECAP`・実ホスト(ansy/quory/authy/monnie/pve1/pve2)状態の前後比較を確認すること。契約上、対象playbookの実行(`--check`の有無を問わず)は禁止されているため行っていない。特にAC3(部分適用が起きないこと)は、target_setup.ymlが`delegate_to`でauthy/monnie/pve1/pve2という保護対象ホストに副作用を作るため、実ホストでの検証はTesterが慎重に計画すべき領域として明確に残す。

## 5. 未解決事項

1. **AC1「skippedに現れる」以上の検証情報について。** 本playbookは`--check`下で50task中48taskがskipされ(main.ymlの2task、assertとinclude_tasksの条件評価のみ動く)、batchB1が`systemd_timers`/`recovery_push_drill_setup`で指摘したのと同種の「`--check`が構文・変数解決以上の診断価値を提供しない」ケースに該当する。バッチB1の§5の所見(分類そのものは正しいが診断価値は薄い)がそのまま当てはまる。
2. **block不使用の判断についてReviewerの確認を求める。** §2.3で述べた通り、依存元・依存先を同一条件で個別ゲートする設計は、decoy検証で block と機能的に等価であることを確認したが、TS-015の文言(「相互依存する一連はblock単位でゲートする」)を字義通り読むと、target_setup.ymlのslurp→authorized_keys配布の依存もblock化を要求しているとも読める。再配置なしでblock化する代替案(例: target_setup.ymlをさらに分割し、依存関係のあるtaskだけを別ファイルにして`include_tasks`する)は検討したが、diffが大きくなる割に安全性上の追加の利益がないと判断し採用しなかった。この判断の当否はCoordinator/Reviewerの確認を求める。
3. **`Deploy recovery-loki-helper on target nodes with Loki`のloop変数スコープ。** 既存の`when: "'loki' in target_item.investigate_services"`は文字列条件のままlist内の1要素として残し、`not ansible_check_mode`を2つ目の要素として追加した(AND評価)。動作は変わらないはずだが、他のbatchでこの形の複合when(文字列+bool式の混在list)を使った前例が無いため、念のため記録する。

以上、対象1 playbook・関連role 2ファイルの変換は完了。実ホストでの`--check`/通常実行(AC1〜AC3)はTesterの領域として未実施。

## 6. 差し戻し対応(2026-07-31 独立レビュー)

独立レビューで、`roles/recovery_exec/tasks/main.yml`の次の4task——`Generate investigation SSH key` / `Generate action SSH key` / `Generate PVE investigation SSH key` / `Lock down SSH key permissions`——が**ファイル上で連続しており**(間はコメントのみ)、バッチB-1の`roles/recovery_push/tasks/sender_setup.yml`がblock化した`Generate → Lock → Slurp → Store`と同型の連鎖であるにもかかわらず、個別ゲートのままだった点を指摘された。以下、本節のみ追記する(§1〜5は書き直していない)。

### 6.1 何が誤りだったか

§2.3の「block不使用の理由」は、main.ymlの鍵生成4taskとtarget_setup.ymlのslurp→authorized_keys配布の**2つの異なるケースをまとめて1つの理由で説明していた**。後者(6つの独立taskが間に挟まる非連続な依存)には「再配置が必要」という理由が成立するが、前者(4taskが完全に連続している)には成立しない——再配置なしでそのままblockにできる。この見落としが差し戻しの原因である。指摘は妥当と判断した。

§4の自己検証項目4(「file モジュールの暗黙 state: file は、依存元task と依存先task が同一の when: not ansible_check_mode でともにゲートされていれば...block不要の根拠」)は、**個別ゲートでも`--check`下でクラッシュしない**という機能的な等価性を示した点では誤りではないが、TS-015が block を要求するのは「クラッシュを防げるかどうか」ではなく「連続した依存チェーンを1つの単位として明示するかどうか」という別の基準であることを、この差し戻しで理解した。今回の是正はこの基準(2026-07-31 Coordinatorが明文化したPolicy改訂: 連続していて先行の実行に依存する連鎖はblock、非連続なら個別+コメント)に沿う。

### 6.2 実装内容

`roles/recovery_exec/tasks/main.yml`の該当4task(旧: 個別に`when: not ansible_check_mode`+`tags: [destructive]`を保持)を、1つのnamed block `Generate and lock down recovery-exec SSH keys (destructive; TS-015 chain)` に統合した。

- block自体: `when: not ansible_check_mode` + `tags: [destructive]`。
- block内の4taskからは個別の`when:`/`tags:`を除去した(block conditionが自動でAND評価される——batchAのrecovery_probe実測・batchB1のsender_setup.yml実測と同じ前提)。
- block直前のコメントを、「なぜblockを使わなかったか」から「なぜblockを使うか」へ書き替え、target_setup.ymlの非連続ケースとの対比を明記した。

`target_setup.yml`は無変更。差し戻しの再確認条件どおり、slurp→authorized_keys配布の非連続な連鎖は個別ゲートのまま維持した(依頼文で「妥当と評価している」と明示されている)。ゲートの網羅性・`quory`ハードコード検査・既存`when:`へのAND追加も指示どおり触っていない。

### 6.3 §2.3・§5の記述の扱い

- §2.3の「main.yml内: ...両者ともそれ自体が破壊的taskであり、TS-014の個別ゲートでも同じ条件を共有すれば挙動は同一」という記述は、**target_setup.ymlのケースの説明としては引き続き有効**だが、main.ymlの鍵生成4taskについては本節6.2の是正で上書きされている。§2.3本文は書き直していないため、読む際は本節を優先すること。
- §5の未解決事項2(「block不使用の判断についてReviewerの確認を求める」)は、**main.ymlの部分について本差し戻しで解消した**(block化した)。target_setup.ymlの非連続ケースについては、依頼文で「個別ゲートのままでよい」「レビューもその判断を妥当と評価している」と確認が得られたため、これも解消したものとして扱ってよい。

### 6.4 自己検証

- `ansible-playbook playbooks/recovery_exec_setup.yml --syntax-check`を再実行し、通ることを確認した。
- `python3 -c "import yaml; yaml.safe_load(open('roles/recovery_exec/tasks/main.yml'))"`で構文を再確認した。
- `bash scripts/check-tester-gate.sh`を再実行し、`OK (46 playbooks)`のままであることを確認した。
- `grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l`が引き続き5であることを確認した(AC5は本是正で変わらない)。
- `ansible-lint roles/recovery_exec/tasks/main.yml roles/recovery_exec/tasks/target_setup.yml`を`git stash`前後で比較し、新規violationが無いことを確認した(既存3件のvar-naming、行番号のみ変化)。
- `git status`/`git diff --stat`で、変更ファイルが引き続き`playbooks/recovery_exec_setup.yml`・`roles/recovery_exec/tasks/main.yml`・`roles/recovery_exec/tasks/target_setup.yml`の3つのみであることを確認した(`docs/ai/policies/ansible_test_safety_policy.md`の変更と`2026-07-31_014_round2_batchB2_review.md`はCoordinator/Reviewer側の並行編集であり、本Implementerセッションでは一切触っていない)。
- `roles/recovery_exec/tasks/target_setup.yml`の`quory`リテラル2箇所は本是正で無変更(そもそも編集していない)。

以上、差し戻し対応は完了。target_setup.ymlは無変更のため再検証していない。
