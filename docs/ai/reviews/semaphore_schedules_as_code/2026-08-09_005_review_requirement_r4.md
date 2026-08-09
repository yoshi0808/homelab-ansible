# Code Review: Semaphore schedules as code requirement 4回目査読

## Summary

R15はreconcile自身のPOSTがactiveな重複を直ちに作る経路を塞ぎ、R13/AC11、AC13、R17、cron規約も前回指摘を実質的に反映した。ただしR16は`false → true`という**reconcileが行う遷移**だけを止めるため、UIで新scheduleが先にactive化された場合の二重activeを解消できない。また、R15と既存ACの不整合、およびclosed-world移行後にansyを有効化する経路が残る。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 23, 52-53, 114-127 | R15/R16の組合せは、reconcileだけが状態を変える場合には二重activeを防ぐが、line 23が明示的に許すUI編集を含む不変条件にはなっていない。例: catalog rename後のapplyで「旧名=active、新名=false」ができた後、UIで新名をactiveにする、または次回apply前に同名scheduleをactiveで手作成すると、API上は旧名と新名が両方activeになる。次回reconcileでは新名は既に`true`なのでR16の`false → true`遷移が存在せず、catalog値とも一致するためdeactivateされない。管理外の旧名は段階フェーズではreportだけで終了コード0となり、二重activeが残り続ける。AC12もobservedがfalseのケースしか試さないためこの穴を合格させる。UI権限を維持したままstatelessなname同定を採るなら、作成直後の「有効化待ち」をcatalogの明示フィールド等で永続化し、その承認が無いscheduleはobservedがtrueでもfalseへ戻す、または管理された新規追加/renameの別identityを持つ必要がある。少なくとも「管理外あり・新規由来scheduleが既にtrue」のACを追加し、activeな重複が残らないことを直接観測する必要がある。 | Critical |
| 2 | 同上 | 49, 52-54, 74-87 | R15は新規を常に`active:false`で作るが、AC2は作成直後の`active`がcatalog値と一致すると要求する。catalogが`active:true`なら両者は同時に満たせない。さらに、そのscheduleは次回applyで初めて有効化される設計なので、AC4の「AC2直後に再実行してPUT 0件・diff空」も、closed-worldかつcatalog=trueの新規追加では成立しない。R11の「applyのたびにcatalog値へ確定」もR15/R16の例外を反映していない。AC2を「catalog値にかかわらず作成直後false」へ直し、catalog=falseなら次回から冪等、catalog=trueならcheckでpending activationを観測→別applyで有効化→その次から冪等、という2段階をACで分ける必要がある。 | High |
| 3 | 同上 | 15, 53-54, 139, 151-156 | R16がansyを守るのは管理外scheduleが残る移行期間だけである。19件をcatalogへ載せたansyは管理外0件になり、repo共通のclosed-worldフラグを立てた後はR17の`false → true`有効化条件を満たす。以後ansyへapplyすると、Restore後falseだった19件をcatalogのtrueへ更新し、まさにline 53/156が避けると述べた定期実行基盤化が起きる。フラグは同じcatalogにあるためquoryだけに作用する根拠にならない。ansy向けはclosed-world後もactivationを許さない明示的な環境別capabilityを設け、その既定・override・API接続先との結び付けをP0とACにするか、ansyは永続的に`--check`だけとする必要がある。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 4 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 54, 124-132, 154 | R17のフラグ自体を受入観測へ入れる。現ACは「管理外ありならskip」(AC12)と「closed-worldで有効化」(AC13)しかなく、**管理外0件だがフラグfalse**の境界ケースが無い。実装がフラグを無視し「管理外0件なら有効化」としても全ACを通せる。flag=falseでは管理外0件でもfalseのまま、flag=trueへ変えた次のapplyだけでtrueになるACを追加する。 | phase gate / Medium |
| 5 | 同上 | 46, 51-54 | R8/R16は1回のGET snapshotを前提に見えるが、UI編集を許すならpreflight後からfalse→trueのPUTまでに管理外scheduleが追加される競合も残る。少なくとも有効化直前にschedule集合を再GETし、preflight時の集合から変わっていたら有効化を見送る契約と競合fixtureを置く。Semaphore側のtransaction/ETagが無ければ完全な排他はできないため、その残余も明記する。 | concurrency / Medium |

## What Looks Good

- 前回Critical #1に対し、R15はPOST payloadをcatalog値から切り離して必ずinactiveにするため、catalog/UI renameをnewとして解釈してもreconcile自身が旧activeと新activeを同時に作る直接経路は塞いだ。
- 前回High #2: R13をR8 preflightへ含め、AC11はclosed-worldでPOST/PUT/DELETE 0件とAPI状態完全一致を要求するため、書き込み後に検出しても合格する穴は解消した。
- 前回High #3: AC13は既存scheduleのtemplate変更、activeの両方向、id維持、非管理フィールド維持を観測し、管理項目更新の取りこぼしを塞いだ。
- 前回Medium #5: closed-worldを件数ではなく明示的・単調なrepo flagで表すR17は、20件目追加で検査が解除される問題を設計上解消した。Finding #4はAC不足だけを扱う。
- 前回Medium #6: cron grammarは対象版で実測し、既存19件と拒否値をtest fixtureに固定する契約になった。
- R16はobservedがfalseで管理外が存在するケースについて、activeだけを見送り、cron/templateの段階適用を継続するAC12を持つ。この限定された状態遷移は安全側である。
- duplication/reuse: template側のraw object保持・`combine`・既存playbookの再利用方針を維持し、新しい照合ロジックだけをschedule固有の不変条件として分離している。
- security: token保存、TLS弱化、shell/command変数展開、secretのreport出力は要求していない。API観測はGET、書き込みは既存Ansible URI経路に限定されている。
- Reviewer定型観点: requirement段階のため多層エスケープとrc規約は対象なし。`--check`で評価されないapply分岐は、R15の作成、R16/R17の有効化、AC10-AC13として列挙されているが、Finding #1-#4の状態が未観測である。例外吸収はR16の「有効化見送り+成功終了」に相当し、判定不能ではなく管理外の存在を理由付きreportへ出すため無音化はしていない。

## 確認範囲

- 改訂後requirement全文、前回`2026-08-09_004_review_requirement_r3.md`全文、現在のworktree diff
- R15/R16/R17とAC2/AC4/AC10-AC13を、catalog rename、UI rename、UI active変更、段階移行、closed-world移行、ansy/quoryの各状態遷移として照合
- `playbooks/semaphore_templates_setup.yml`の`hosts: quory`、ansy向けAPI override、check-mode gate
- `roles/semaphore_templates/tasks/main.yml`のread/reconcile/report/apply順序と、template側get-then-merge-then-sendの再利用契約
- `docs/ai/context/system/semaphore.md`のansy/quory分離、ansyの鍵不在、UI/API設定がGit外で変化し得ること
- 着手時の`git status`とrequirementのSHA-256。requirement、status、先行reviewは他者成果物として変更していない
- 実ホストへのAnsible、Semaphore APIのGET/POST/PUT/DELETE、commit、pushは未実施

## 未確認事項

- requirementが引用するansy API payload、19件の内容、名前重複、`task_params`等の実値は今回も独立取得していない。
- OQ1の20/19不一致とOQ3のquory API/SQLite突合は未解決のままである。
- Semaphore APIがschedule更新に対するETag・revision・transaction等の競合制御を提供するかは確認していない。Finding #5は利用可能と仮定せず、再GETと残余明記を提案している。
- `run_at`等がactive schedule実行に伴い自然変化するかは独立確認していない。GET完全一致を使うACでは自然変化フィールドがあれば比較対象を分ける必要がある。

## Verdict

Request Changes
