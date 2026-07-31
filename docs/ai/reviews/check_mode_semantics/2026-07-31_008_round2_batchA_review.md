# review: Round 2 バッチA — `check-mode-native` 変換

日付: 2026-07-31
対象: `playbooks/incident_capture_setup.yml` / `playbooks/incident_investigate_setup.yml` / `playbooks/recovery_probe_setup.yml`、`roles/incident_capture/tasks/main.yml`、`roles/incident_investigate/tasks/main.yml`、`roles/recovery_probe/tasks/main.yml`、`roles/recovery_probe/handlers/main.yml`
契約: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §5 R1〜R6、§6 AC1〜AC5(AC1は2026-07-31訂正後の本文で判定)
実装記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_007_round2_batchA_implement.md`

## Code Review: Round 2 バッチA (`incident_capture` / `incident_investigate` / `recovery_probe`)

### Summary

7ファイルの差分を現物で通読し、`command`/`shell`/`uri`モジュールの網羅性・`when:`ゲートの伝播・handlerの独立ゲートを個別に確認した。破壊的taskの取りこぼしとAC2回帰は見つからなかった。TS-015(相互依存する破壊的task列はblock単位でゲートする)への不整合が1件、および元requirementの母集団計算に1本(`incident_inspect_setup.yml`)の不整合を見つけた。いずれもblockingではないが、バッチB・Cへ進む前にCoordinatorが判断すべき事項として報告する。

### Critical Issues

なし。

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `roles/recovery_probe/tasks/main.yml` | 76-144 | Deploy probe config/daemon/unit → enable+start → flush_handlers → freshness verify は明確に相互依存する一連の破壊的操作(config/daemon/unit配備が無ければenable+startの意味がなく、enable+start/restartが起きなければfreshness verifyの前提が崩れる)。TS-015は「複数の破壊的taskが相互依存する場合...一連をまとめて1つのnamed blockにしblock単位でゲートする」を明示的に推奨しているが、本diffはこの一連を個別task単位の`when: not ansible_check_mode`(または複合条件)で分散してゲートしている。機能的には等価(単一run内で`ansible_check_mode`は変化しないため各taskの判定は揃う)だが、TS-015が指定する実装パターンから外れている。バッチB(`recovery_io_setup`等)がこの一連依存パターンを含む場合、個別task方式と block方式のどちらを「正しい変換テンプレート」として再現すべきかが曖昧になる。Coordinatorに、この乖離を許容するか、block化へ直すかを判断してほしい | consistency |
| 2 | `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` | §4 | `risk-accepted`宣言playbookは変更前17本。非ゴールの3本(`cloudkey_cert_deploy`/`proxmox_backup_restore_verify`/`unifi_backup_fetch`)+バッチA(3本、本diff)+バッチB(8本)+バッチC(2本)=16本にしかならず、`playbooks/incident_inspect_setup.yml`(現物確認: ヘッダは条件1のみに言及し条件2への言及なし)がどちらの集合にも属していない。AC5(最終的に3本になる)を満たすには、この1本の扱い(バッチBまたはCへ追加、あるいは4本目の例外として明記)をバッチB着手前に決める必要がある。バッチAの実装対象には含まれておらず本diffの欠陥ではないが、requirementの母集団計算そのものの不整合として報告する | scope-gap |

### What Looks Good

- **R1(ヘッダ変更)**: 3playbookとも`check-mode-native`へ変更され、理由文にTS-009条件1(実害軽微)・条件2(本体操作省略に検証価値なし)の両方へ「条件2を満たさないから移す」という形で明記されている(`incident_capture_setup.yml:20-36`、`incident_investigate_setup.yml:35-52`、`recovery_probe_setup.yml:16-30`)。旧ヘッダ(diff左側)と読み比べ、条件1しか評価していなかった旧分類の弱点を正しく引き継いでいる。
- **R2(停止assert除去)**: 3playbookとも`[migration] --check has no dry-run here...`のassertが削除されている。`tester_mode`廃止案内assertは残り、文言も`--check`推奨へ更新されている。`git diff`で確認。
- **R3(role importの`check_mode: false`カスケード除去)**: `incident_capture_setup.yml`・`incident_investigate_setup.yml`の`import_role`から`check_mode: false`が消えている。`recovery_probe_setup.yml`は`block:`+`check_mode: false`の構造自体を解体し、`recovery_mute`(role外scope)へのinclude_roleと`recovery_probe`のinclude_roleを独立2taskへ分けている。いずれも確認。
- **R4(破壊的task全件へのゲート)**: `roles/incident_capture/tasks/main.yml`・`roles/incident_investigate/tasks/main.yml`を全行読み、両role内の全task(それぞれ11task・7task)に`when: not ansible_check_mode`+`tags: [destructive]`が付いていることを確認した。`recovery_probe/tasks/main.yml`も同様に全8破壊的taskを確認した。取りこぼしは見つからなかった。特に、実装記録が「見つけた穴」として挙げていた`Enable and start recovery-probe (production only)`(旧`when: recovery_probe_service_enabled | bool`のみでゲート欠如)は、現物でも該当箇所(`roles/recovery_probe/tasks/main.yml:108-125`)に確かにゲートが欠けていたことを変更前diffで確認済みであり、実装記録の主張は裏取りできた。
- **R5(check_mode非対応moduleの診断taskへのcheck_mode: false)**: `grep -rnE "ansible\.builtin\.(command|shell|uri|expect)"`で対象role配下を再検索し、実装記録が挙げた箇所(`incident_capture`の`command`2箇所、`recovery_probe`の`shell`1箇所、`recovery_mute/tasks/deploy_cli.yml`の`command`1箇所)以外に存在しないことを独立に確認した。前者2つ(mkdir系)は「作成する」破壊的taskであり読み取り専用ではないため`when: not ansible_check_mode`でのスキップが正しい(`check_mode: false`は不要)。後者(recovery_probeのfreshness shell)は既存の`check_mode: false`のまま変更されておらず、`Check whether recovery-probe is already running`(`roles/recovery_probe/tasks/main.yml:27-38`、既存の`check_mode: false`)と合わせて、`--check`下でも読み取りを継続する設計が保たれている。
- **R6(該当なし)**: 削除されたfail_msgに`skip_notifications`の案内が元々含まれていなかったことを、削除前のdiff左側テキストで確認した。
- **AC2(通常実行の不変)**: 追加された`when:`条件はすべて既存条件へ`not ansible_check_mode`をANDで追加する形(`when: [not ansible_check_mode, 既存条件]`または複合Jinja式)であり、通常実行(`ansible_check_mode`は常にfalse)では元の条件がそのまま効く。新規に条件を追加したことで通常実行時に実行されなくなるtaskは見当たらない。
- **AC4(lint)**: `bash scripts/check-tester-gate.sh`を実行し`OK (46 playbooks)`を確認(自分で再実行、実装記録の主張の裏取り)。3playbookとも`ansible-playbook <playbook> --syntax-check`が通ることも独立に確認した。
- **AC5(母集団)**: `grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l`相当のgrepで現在14本であることを確認(17→14、バッチAの3本減と一致)。ただしSuggestion #2の母集団計算の不整合は別途指摘。
- **handlerの独立ゲート(2.4節主張の検証)**: `roles/recovery_probe/handlers/main.yml`の`Restart recovery-probe`に`not ansible_check_mode`が追加されていることを確認。通知元task(`Deploy probe config`等)が全て`when: not ansible_check_mode`でゲートされているため、`--check`下ではこれらのtaskが`changed`を報告せずhandlerは原理上notifyされないが、handler自身の`when`にも同条件が独立に足されており、通知元ゲートへの依存が二重化されている。`roles/incident_capture`・`roles/incident_investigate`のhandler(`daemon_reload: true`のみ)は通知元が全てゲート済みのため追加のゲートを持たない、という判断も現物(`roles/incident_capture/handlers/main.yml`・`roles/incident_investigate/handlers/main.yml`)を読んで妥当と判断した。
- **role外scope(`recovery_mute`)のゲート設計**: `recovery_probe_setup.yml`が`recovery_mute`の`deploy_cli`を`include_role`する箇所に`when: not ansible_check_mode`+`tags: [destructive]`を直接付け、呼び出し単位で丸ごとゲートしている。**この「`when:`を動的includeの呼び出しtask自体に付けると配下の全taskへ伝播するか」を、対象playbookを実行せず`hosts: localhost`+`connection: local`のscratch playbook(実host名なし、副作用は`/nonexistent-marker-file-for-test`へのcommand+creates:のみ)で独立に実測した**: 通常実行では`changed=1`でrole内taskが実行され、`--check`実行では`skipping: [localhost]`のみが出て配下task自体が展開されず`changed=0`。`recovery_mute/tasks/deploy_cli.yml`に読み取り専用診断taskが無いことも現物(`command`+`creates:`のmkdirと`copy`のみ)で確認しており、呼び出し単位ゲートの設計は妥当と判断した。検証用の一時ファイルはレビュー後に削除済み。

### Verdict

Approve(Suggestion 2件は blocking ではないが、バッチB着手前にCoordinatorが解消方針を決めることを推奨する)

## 未解決事項(Coordinatorへ)

1. Suggestion #1: TS-015のblock化推奨と本diffの個別task方式の乖離を、次バッチのテンプレートとして許容するか。
2. Suggestion #2: `incident_inspect_setup.yml`がrequirementのバッチ分割・非ゴールいずれにも属さず、AC5の最終目標(3本)の算数が現状合わない。バッチB・Cどちらに含めるか、または4本目の例外として明記するかを決める必要がある。
3. 実装記録が残した未解決事項(AC1の`changed`件数解釈、`recovery_mute`role自体の将来分類、ACLモジュールのネイティブsimulate精度の未実測)は、いずれも本レビューの確認範囲では新たな懸念を生まないと判断した(AC1は訂正済み文言で判定材料から除外、`recovery_mute`は将来課題として明記済み、ACL simulateは今回「丸ごとskip」設計のため実害なし)。ただし対象playbookそのものの`--check`実行によるAC1〜AC3の実地検証はTester領域であり、本レビューでは行っていない。

## 自己検証

- 対象7ファイル全てを`git diff`+`Read`で通読し、変更前後を1行ずつ突き合わせた。
- `grep -rnE "ansible\.builtin\.(command|shell|uri|expect)"`を対象role配下へ再実行し、実装記録の「network性の穴」主張(command/shell/uri箇所の網羅)を独立に裏取りした。
- `bash scripts/check-tester-gate.sh`、`ansible-playbook <playbook> --syntax-check`(3本)、`grep -h "^# tester-gate:"`集計を自分で再実行し、実装記録の数値主張(46 playbooks OK、17→14)を裏取りした。
- `hosts: localhost`+`connection: local`のscratch playbook(実host名なし、対象システムに影響しないダミーrole)を作成し、`include_role`への`when:`が配下taskへ伝播することを通常実行/`--check`実行の両方で実測した。検証後にscratchファイルを削除し、リポジトリ作業ツリー外に何も残していないことを確認した。
- 対象playbook本体(`incident_capture_setup.yml`等)そのものは一度も実行していない(`--check`の有無を問わず)。
- 参照した全ファイルパス・行番号は本レビュー作成時点の`Read`/`grep`結果に基づき実在を確認済み。`docs/ai/policies/ansible_test_safety_policy.md`のTS番号(TS-009〜TS-032)は同ファイルの現物から引用した。

## 確認範囲

- `git status`/`git diff`で対象7ファイルの全差分。
- `docs/ai/core.md`、`docs/ai/roles/reviewer.md`、`docs/ai/policies/ansible_test_safety_policy.md`§4・§5、`skills/code-review/SKILL.md`、`skills/duplication-reuse-check/SKILL.md`、`skills/ansible-security-review/SKILL.md`、`skills/ansible-implementation-style/SKILL.md`「check_modeの実装上の落とし穴」節。
- `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md`(§5訂正後のAC1本文含む)、`2026-07-31_007_round2_batchA_implement.md`。
- `roles/recovery_mute/tasks/deploy_cli.yml`(scope外roleだが、呼び出し側ゲート設計の妥当性判断に必要なため現物を確認)。
- `roles/incident_capture/handlers/main.yml`、`roles/incident_investigate/handlers/main.yml`(未変更だが、変更不要という実装判断の裏取りに必要なため現物を確認)。

セキュリティレビュー観点(`skills/ansible-security-review/SKILL.md`)では、本diffは既存の変数参照パターン(`shell`のfreshness collectorは変更前から不変、`quote`フィルタ不要な固定文字列のみ)を変えておらず、新たな注入面・機密露出面は見当たらなかった。重複・再利用チェック(`skills/duplication-reuse-check/SKILL.md`)では、`when: not ansible_check_mode`+`tags: [destructive]`という表現は既存の複数`check-mode-native` playbook(`grep`結果に見える`knowledge_review_timer`等)と同じ語彙を再利用しており、新規の独自表現を作っていない。

---

## Coordinatorの処理(2026-07-31)

| Suggestion | 扱い |
|---|---|
| #1 `recovery_probe` のゲートがTS-015に反し個別task単位で分散している | **同意・是正。** Implementerへ差し戻した。機能的に等価という評価は受け入れるが、**バッチAは以降11本の変換テンプレートになる**ため、テンプレート自身が2通りの書き方を含むことは本案件の目的(playbookごとに考え方が違う状態の是正)を損なう。相互依存の括り方の判定はImplementerに委ね、レビュー側の見立てと異なる結論を採る場合は理由を実装記録へ書かせる |
| #2 requirementの母集団計算が合わない(`incident_inspect_setup` が未割当) | **同意・是正。Coordinator側の欠陥である。** バッチ分割がA=3 / B=8 / C=2 の計13本で、非ゴール3本と足しても16本にしかならず母集団17本と合っていなかった。`incident_inspect_setup` をバッチBへ追加(B=9、合計14本)。requirement §4 に訂正の記録を残し、「分割を変えるときは 非ゴール3 + A + B + C = 17 が成り立つことを毎回確かめる」旨を明記した |

**#2について**: この欠陥は、私がバッチ分割を棚卸し結果の14本と突き合わせずに書いたことによる。分類棚卸しの成果物(`2026-07-31_004_classification_audit.md`)には14本が正しく列挙されており、**一次記録は正しく、それを写した先で落ちた**。Round 1の execpolicy Incident と同じ形(正本は正しいが、要約した層で事実が失われる)である。
