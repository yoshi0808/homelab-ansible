# review: Round 2 バッチB-2 — `recovery_exec_setup` の `check-mode-native` 変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §4 バッチB-2、§5 R1〜R6、§6 AC1〜AC5
対象diff: `playbooks/recovery_exec_setup.yml`、`roles/recovery_exec/tasks/main.yml`、`roles/recovery_exec/tasks/target_setup.yml`
実装記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_013_round2_batchB2_implement.md`(先に現物を独立判定した後に突き合わせた)

## Summary

3ファイルの`git diff`全量を通読し、`main.yml`32task(30 destructive)・`target_setup.yml`18task(全destructive/chain依存)のゲート網羅性を1件ずつ突き合わせた。`--syntax-check`・`ansible-lint`・`scripts/check-tester-gate.sh`は全て通過し、`ansible_connection: local`のdecoyで技術的主張3件(slurpの`--check`下での実読み取り失敗、`when: false`が`lookup('pipe', ...)`の発火自体を防ぐこと、`file`モジュールの暗黙`state: file`が存在しないパスで失敗すること)を独立に再現・確認した。**blocking findingは無い。** 2026-07-08インシデントの当該task(`Deploy authorized_keys on target nodes`)を含め`delegate_to`付きtask全てにゲートが付いており、main.ymlの`quory`ハードコードguard(2箇所、行482・501)は無変更を確認した。一方、TS-015のblock化判断について、`main.yml`の鍵生成→chmodの連続チェーンがbatchB1の`sender_setup.yml`と構造的に同型でありながらblock化しなかった点は、バッチ間の一貫性の観点でSuggestionとして指摘する。

## Critical Issues

なし。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `roles/recovery_exec/tasks/main.yml` | 42–95 | 鍵生成3task(`Generate investigation/action/PVE investigation SSH key`)→`Lock down SSH key permissions`は、batchB1の`roles/recovery_push/tasks/sender_setup.yml`の`Generate → Lock → Slurp → Store`と構造的に同型(ファイル内で連続・後続taskが先行taskの実ファイル生成に依存)だが、B1はblock化し本batchは個別ゲート(同一`when:`の共有)に留めた。実装記録§2.3は「両者とも破壊的taskで条件を共有すれば挙動は同一」と理由を書いているが、この論法はB1のsender_setup.ymlにも等しく成立したはずで、なぜB1はblockを選びB2は選ばなかったのかの説明になっていない。decoy検証によれば`--check`下の実行結果としてblockと個別ゲートは機能的に等価であり、安全性上の欠陥ではない。ただしrequirementが明記する目的の1つ(「playbookごとに考え方が違う状態の是正」)に照らすと、バッチ間で同型パターンへの適用が割れている状態自体が是正対象であり、バッチC着手前に「いつblock化必須か」の基準をSkillまたはrequirementへ明文化することを勧める。 | consistency |

## `slurp`の扱いについての判定

`target_setup.yml`の3 slurp task(`Slurp investigate/action/PVE investigate public key`)は、TS-017の通常パターン(`command`/`shell`/`uri`のようにcheck_mode非対応でauto-skipされるmoduleに`check_mode: false`を付けて診断価値を残す)とは**逆方向**の判断——明示的にゲートして`--check`下でauto-skipさせている。これを現物とdecoy実行で独立に検証した結果、この判断は妥当と判定する。

- `ansible.builtin.slurp`は`command`/`shell`の`creates:`無し版と異なり、check_modeをネイティブに支援するため`--check`下でもauto-skipされず実際にファイル読み取りを試みる。存在しないファイルに対して`--check`下で`slurp`を実行し、`File not found`で`failed=True`になることをdecoyで確認した(本レビュー実施、上記自己検証参照)。
- 本role内では、slurpの読み取り対象(`{{ recovery_exec_investigate_key }}.pub`等)は同じrole内の鍵生成task(`command` + `creates:`)が生成するファイルであり、その鍵生成task自体が本バッチの変換で`when: not ansible_check_mode`によりゲートされている。したがって、鍵未生成の(未配備、または再構築後の)ホストでは、slurpをゲートしない場合`--check`実行そのものがtask失敗で止まる——値の目視では見えない「消費側まで通すと壊れる」パターンであり、decoyで実際に再現・確認した。
- AC1は「`--check`が終了コード0で完走すること」を要求しており、診断価値(TS-017が本来守ろうとするもの)より完走保証が優先される場面である。ユーザーの指摘通り「既に配備済みのホストでは、ゲートしなければ`--check`でも読めて診断価値がある」というトレードオフは実在するが、この`recovery_exec_setup`は`import_playbook`されるオーケストレータではなく単体playbookとして任意のホスト状態(未配備を含む)で`--check`が呼ばれうる。実装記録がTS-017の「通常パターンの裏返し」として明示的にコメントを残している点(`target_setup.yml`12–23行目)も含め、判定は妥当と考える。
- なお、`roles/homelab_cert_renew/tasks/deploy_ca_trust.yml`のSlurp ROOT CA(batchB1)はungateされているが、これは読み取り元がplaybook内で新規生成されるファイルではなく既存の外部ソースである点で非対称の理由があり、矛盾しない(batchB1レビューでも確認済みの区別と整合する)。

## TS-015適用についての判定

`target_setup.yml`のslurp→`Deploy authorized_keys`の依存は、ファイル内でslurp(冒頭)と配布task(後半)の間に依存しない6独立taskが挟まっており、隣接していない。実装記録§2.3は、block化には依存task同士を隣接させる再配置が必要で、`.ssh`ディレクトリ作成(先)→`authorized_keys`配布(後)という既存の実行順序を壊すリスクがあるとして個別ゲート(同一条件の共有)を選んでいる。

この判断を独立に検証した結果、**妥当と判定する**。

- 現物(`target_setup.yml`)を読み、slurp(1–3task目)と`Deploy authorized_keys on target nodes`(10task目)・`Deploy authorized_keys on pve target nodes`(15task目)の間に、user作成・.sshディレクトリ作成・dispatch script配布・loki helper配布・action script配布・sudoers配布という、authorized_keys配布と依存関係を持たない6taskが実際に挟まっていることを確認した。
- これらをblock化するには、target_setup.ymlをファイル内で並べ替えるか、依存task群を別ファイルへ分離する必要があり、AC2(通常実行の不変)に対するリスクを増やす。requirementの非ゴール「`--check`なしの通常実行の挙動変更」を守るためには、現状の実行順序を変えない個別ゲートの方が安全側である。
- decoy検証(`file`モジュールの暗黙`state: file`が依存元task未実行時に失敗すること)により、個別ゲートでも依存元・依存先が同一条件を共有していれば`--check`下でblockと機能的に等価であることを確認した。
- 一方、この判断はTS-015の文言(「相互依存する一連は...block単位でゲートする」)を字義通り適用したものではなく、実装記録も未解決事項として明示的にCoordinator/Reviewerの確認を求めている。安全性・AC充足の観点では問題ないが、**この判断を最終的に承認するかどうかはCoordinatorの裁量に委ねる**(Reviewerとして「妥当」と判定するが、TS-015の文言をどこまで厳密に適用するかというPolicy解釈の確定はCoordinator/Yoshinobuの領域)。

## What Looks Good

- **ゲート網羅性(50task)。** `main.yml`の30 destructive taskと`target_setup.yml`の18taskすべてに`when: not ansible_check_mode`(または既存`when:`とのAND)+`tags: [destructive]`が付いていることを`grep -c`で機械的に確認した(それぞれ30件・18件、diffの追加行数と一致)。無変更の2task(`Assert quory...`のassertと`Setup recovery-exec on target nodes`のinclude_tasks)は理由が明記されており、assertが`--check`下でも常に評価されること(ゲート不要)をdecoyで独立に確認した。
- **`delegate_to`付きtaskの網羅。** `target_setup.yml`内の15 delegate_to task(authy/monnie/pve1/pve2向け)全てにゲートが付いていることを確認した。2026-07-08にquoryで3日間のSSH障害を起こした`Deploy authorized_keys on target nodes`(154行目)も含め漏れはない。
- **`quory`ハードコードguardは無変更。** `main.yml`482行目(`'quory' in ansible_play_hosts_all`)・501行目(`inventory_hostname == 'quory'`)のリテラル`quory`は、`git show HEAD:...`との比較および現物のgrepで無変更を確認した。変数・引数・`-e`で差し替え可能な形になっていないことを独立に確認した。
- **AC2(通常実行不変)の構造的根拠。** 変更前に`when:`を持っていたのは`roles/recovery_exec/tasks/target_setup.yml`の`Deploy recovery-loki-helper...`(`"'loki' in target_item.investigate_services"`)のみで(`git show HEAD:...`との比較で確認)、既存条件は置換されずlistの2要素目として`not ansible_check_mode`が追加されている。他の47taskは新規追加のみで既存`when:`は元々無かった。role importの`check_mode: false`カスケードもR3どおり除去されている。
- **`register`→消費の条件一致。** `_investigate_pubkey`/`_action_pubkey`/`_investigate_pve_pubkey`を消費する`Deploy authorized_keys on {target,pve target} nodes`は、生成元のslurpと同一条件(`not ansible_check_mode`)でゲートされており、片方だけskipされる非対称は無い。
- **技術的主張の独立検証(decoy)。** 実装記録が挙げた3つの技術的主張——(1) `slurp`は`--check`下でもauto-skipされず実読み取りを試みて存在しないファイルで失敗する、(2) `when: false`は他の引数の`lookup('pipe', ...)`テンプレート評価自体を防ぐ(known_hostsタスクのssh-keyscanが`--check`下で発火しないことの根拠)、(3) `file`モジュールの暗黙`state: file`は対象パス不在時に失敗する——をいずれも本レビューで独立に`ansible_connection: local`のdecoy playbookで再現し、実装記録の記述と一致することを確認した(鵜呑みにせず現物で裏取りした)。
- **R6の副次確認。** 停止assert除去に伴う死んだコメント(`vars:`セクションの`skip_notifications ... removed`)が削除されていることを確認した(`grep -n skip_notifications`でヒットなし)。`fail_msg`に`skip_notifications`の言及が元々無いこともgrepで確認した。
- **機械チェック・変更範囲。** `ansible-playbook playbooks/recovery_exec_setup.yml --syntax-check`はrc=0、`ansible-lint`の指摘は`var-naming[no-role-prefix]`3件(`_investigate_pubkey`等)のみで`git show HEAD:...`比較により変換前から存在する既存debtであることを確認した。`bash scripts/check-tester-gate.sh`は`OK (46 playbooks)`。`risk-accepted`宣言数は5本(非ゴール3 + バッチC 2本)で、B-1完了時点の6からB-2完了で1減、AC5の想定と一致する。`handlers/`・`rescue:`・`always:`はrole内に存在しないことを確認した(対象外)。変更ファイルは3つのみ(`git status`で確認、対象外ファイルへの変更なし)。

## 自己検証(実施内容)

- `docs/ai/core.md`・`docs/ai/roles/reviewer.md`・`docs/ai/policies/ansible_test_safety_policy.md`§4・§5、`skills/code-review/SKILL.md`、`skills/ansible-security-review/SKILL.md`を読んだ。requirement本体、batchA・batchB1のimplement記録(テンプレート)、batchB2のimplement記録を通読した。
- `git diff playbooks/recovery_exec_setup.yml roles/recovery_exec/tasks/main.yml roles/recovery_exec/tasks/target_setup.yml`の全量、および`Read`で両taskファイルの現物全文を通読した。
- `grep -c "tags: \[destructive\]"`で48task分のゲート付与を機械的に確認し、`main.yml`/`target_setup.yml`のtask数(32/18)と突き合わせた。
- `git show HEAD:roles/recovery_exec/tasks/{main,target_setup}.yml | grep -n "when:"`で変更前の既存`when:`箇所を洗い出し、置換でなく追加になっていることを確認した(AC2回帰チェック)。
- `grep -n "quory"`で`main.yml`のハードコードguard2箇所を特定し、`git show HEAD:...`との比較で無変更を確認した。
- **実行して確かめる検証**(値の目視で終わらせない): `/tmp`のscratchpadに`ansible_connection: local`のdecoy playbookを3本作成し、実行後すべて削除した。
  1. 存在しないファイルへの`slurp`を`--check`で実行し、`failed=True`・`File not found`になることを確認(target_setup.ymlのslurpゲート判断の裏付け)。
  2. 存在しないコマンドへの`lookup('pipe', ...)`を仕込んだtaskを`when: not ansible_check_mode`でゲートし、`--check`下では`skipping`(pipe未発火)、通常実行では`lookup_plugin.pipe(...)returned 127`で実際に発火することを確認(known_hostsタスクのssh-keyscanゲート判断の裏付け)。
  3. 存在しないパスへの`file`(暗黙`state: file`)を`--check`で実行し、`file (...) is absent, cannot continue`で失敗することを確認(`Set known_hosts ownership`のゲート判断の裏付け)。
  - decoyディレクトリ・一時ファイルはすべて削除済み(作業ツリー外に残留なし)。
- `ansible-playbook playbooks/recovery_exec_setup.yml --syntax-check`、`ansible-lint roles/recovery_exec/tasks/main.yml roles/recovery_exec/tasks/target_setup.yml playbooks/recovery_exec_setup.yml`、`bash scripts/check-tester-gate.sh`をそれぞれ再実行し、実装記録の主張と一致することを確認した。
- `grep -h "^# tester-gate: risk-accepted" playbooks/*.yml`で現在5本(非ゴール3+バッチC2本)であることを確認した(AC5)。
- `find roles/recovery_exec -iname '*handler*'`・`grep -rn "rescue:\|always:" roles/recovery_exec/tasks/`でいずれも該当なしを確認した。
- 対象playbook自体(`--check`の有無を問わず)は一切実行していない。実host・ansyへの適用も行っていない。`git add`/`git commit`/`git push`は行っていない。作業ツリー外への残留ファイルなし。

## 未解決事項

- Suggestions #1(main.ymlの鍵生成→chmodチェーンとbatchB1 sender_setup.ymlのblock化判断の不一致)はblockingではないが、バッチC着手前に「block化必須の基準」をSkill/requirementへ明文化することを推奨する。
- target_setup.ymlのTS-015非block判断(実装記録の未解決事項2)は、本レビューでは「妥当」と判定したが、TS-015文言の厳密な適用可否というPolicy解釈の最終確定はCoordinator/Yoshinobuの領域として残す。
- AC1〜AC3の実host確認(quory/authy/monnie/pve1/pve2)はTesterの領域であり本レビューでは行っていない。特にAC3(部分適用が起きないこと)は、`target_setup.yml`が保護対象ホストへ`delegate_to`する構造上、Testerが慎重に計画すべき領域として実装記録・本レビューとも一致して指摘している。
- `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md`(AC1・バッチ分割・OQ1の訂正/決着注記)はCoordinator/Implementerの記録であり、依頼の除外指定どおり本レビューの対象外として扱った。

## Verdict

**Approve**

---

## Coordinatorの処理(2026-07-31、Auditor指摘により追記)

本ファイルはCoordinatorの処理節を欠いたまま次工程へ進んでいた。**Auditor(`2026-07-31_022_audit.md` 指摘#1)がこれを検出したため、経緯を後から補う。**

| Suggestion | 扱い |
|---|---|
| `main.yml` の鍵生成3task→chmodがバッチB-1の同型チェーンと違いblock化されていない(一貫性説明が不十分) | **同意・是正。** Implementerへ差し戻し、当該4taskを1つのnamed block(`Generate and lock down recovery-exec SSH keys (destructive; TS-015 chain)`)へまとめてblock単位でゲートさせた。`target_setup.yml` の非連続な依存(slurp → `authorized_keys` 配布)は個別ゲートのまま維持した |

**この指摘は個別の是正で終わらせず、判定基準そのものをPolicyへ制度化した。** 「block化するかは依存taskがファイル上で連続しているかで分ける。非連続なら並べ替えず個別ゲートにし、理由をコメントに書く」を **TS-033** として新設した(同日)。基準が曖昧だったこと自体がCoordinator側の不備であり、同型の判断が担当ごとに割れる余地を残していた。
