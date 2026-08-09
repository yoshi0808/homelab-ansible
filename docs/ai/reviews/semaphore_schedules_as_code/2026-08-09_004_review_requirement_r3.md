# Code Review: Semaphore schedules as code requirement 3回目査読

## Summary

前回のtimezone観測トポロジ、`active`/reportのP0化、実測の再現手段は解消した。一方、rename対策は段階適用中に旧名と新名のactive scheduleを実際に並存させて終了コード0とするため、前回Criticalの「二重実行を防ぐ」は未解消である。加えて、全件管理後の管理外検査が書き込み前である契約、既存scheduleの`active`/template更新、ansy検証時のinactive維持がACで閉じていない。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 40, 51, 111-114, 134-140 | 前回Critical #1は未解消。R2はrenameの帰結を明記したが、AC10は段階適用中のcatalog renameに対し、旧名を`active`のまま残して新名も作成し、終了コード0とすることを明示的に合格させる。これは検出ではあっても防止ではなく、line 10のUN-SAFE scheduleを含む定期実行を二重化し得る。UI側で既存nameを変更した場合も、catalog側の旧名が「新規」、UI側の新名が「管理外」に見えるため同じ経路になる。段階適用は本件の必須タイムラインなので「全件管理後にだけエラー」では移行期間を保護しない。永続identityを置かない方式を採るなら、少なくとも管理外scheduleが存在する段階ではactiveな新規作成を禁止する、新規を必ず`active=false`で作り別工程で有効化する、または明示的な新規追加の承認情報をcatalogに持たせる等、**旧activeと新activeが同時に成立しないP0不変条件**が必要。AC10も二重activeを期待する形ではなく、その不変条件を直接観測する必要がある。 | Critical |
| 2 | 同上 | 46, 51, 116-119 | 全件管理後のR13エラーがR8のpreflight項目に入っておらず、AC11も「非ゼロ」「管理外を削除しない」しか観測しない。実装が新名をPOSTした後に旧名を管理外として検出して非ゼロ終了しても、AC11を満たしながら二重scheduleを残せる。既存template roleの順序を流用する意図だけではrequirementの契約にならない。管理外集合のclosed-world検査をR8の全件preflightへ含め、AC11はPOST/PUT/DELETEが0件かつ実行前後のAPI状態が一致することを要求する必要がある。 | High |
| 3 | 同上 | 39, 49, 71-84 | R1/R11は既存scheduleの対象template、cron、`active`を管理するが、更新ACは「cronだけが異なる」ケースしか作らず、Thenでもcronしか確認しない。新規作成AC2で`active`/`template_id`を見るだけなので、既存scheduleの`active`変更を無視する実装、または対象template変更を無視する実装が全ACを通過できる。特に`active`は停止・開始そのものである。既存scheduleについて、template変更、`active: true→false`、`false→true`をそれぞれ入力差分にし、id維持・管理値反映・非管理フィールド維持を観測するACが必要。 | High |
| 4 | 同上 | 15, 49, 126, 134-140 | ゴールは同じcatalogをansy/quoryへ反映し、R11はcatalogの`active`へ確定する一方、OQ2はansyの19件が全てinactive、quoryは全てactiveと記録し、タイムラインはansyで`--check`後にapplyする。このままquoryの正本値をcatalogへ入れると、検証applyがansyのscheduleをactive化して定期起動を開始する。ansyにSSH/GitHub鍵が無いことは到達先変更を抑えるが、繰り返しjobを起動しないことや、controller-local playbookが一切作用しないことの代替にはならない。ansyでは新規・更新を常にinactiveへ強制する、active更新だけはapplyしない専用検証modeにする、またはansyでは`--check`までに限定する等、検証用複製を定期実行基盤へ変えないP0契約とACが必要。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 5 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 51, 116-119 | 「catalogが19件を網羅した時点」を実装がどう判定するかを固定する。単なる`length == 19`なら将来20件目を正規追加した時にclosed-world検査が解除され、名前集合の「網羅」を判定するなら比較元の集合が別途必要になる。明示的かつ単調なphase flag、または`length >= 19`等、後から安全側の検査が戻らない条件を要件とACにする。 | phase invariant / Medium |
| 6 | 同上 | 46, 96-99 | R8/AC7の「cronが不正」の判定規約を、対象Semaphore版が受理するcron grammarとして定義する。フィールド数、descriptor、timezone接頭辞等の扱いが未指定だと、実装ごとにvalid/invalidが分かれ、AC7のfixture自体を任意に選べる。既存19件を全てvalidとし、Semaphoreが拒否する代表値をinvalidとするfixture集合まで要件化すると観測可能になる。 | validation contract / Medium |

## What Looks Good

- 前回High #2: R10/AC9は設定ファイルではなく、書き込み先と同じAPI baseの`GET /api/info`から`schedule_timezone`を読むため、API接続先と観測対象のずれを構造的に解消した。
- 前回High #3、Medium #5: `active`とreport共存契約をP0へ移し、P0だけで管理4項目とAC1のreport要件を満たす優先度になった。
- 前回Medium #4: R8の文言は「preflight完了するまで書き込みゼロ」へ修正された。
- 前回Medium #6: ansyのAPI GETとOperator照会IDを、引用した実測ごとの再現手段として記録した。
- R7のget-then-merge-then-send、R8のcatalog/API重複と全件preflight、R9のtemplate先行適用、R12の既存report非上書きは維持されている。
- duplication/reuse: template側で実証済みのraw object保持・`combine`・既存playbookを再利用する方針を維持しており、新たな重複実装を要求していない。
- security: tokenのrepo保存、TLS検証の弱化、shell/commandへの変数展開、secretのreport出力を要求していない。API観測はGETに限定されている。
- Reviewer定型観点: requirement段階のため多層エスケープとrc規約は対象なし。`--check`で評価されない書き込み分岐はR6/AC1で扱われるが、apply側だけで発生する`active`/template更新はFinding #3、ansyのactive化はFinding #4として列挙した。例外吸収・無音化を要求する記述はなく、既知のpreflight失敗は非ゼロを要求している。

## 確認範囲

- 改訂後requirement全文、前回`2026-08-09_003_review_requirement_r2.md`全文、現在のworktree diff
- 前回Critical #1、High #2/#3、Medium #4-#6と、改訂R2/R8/R10-R13、AC9-AC11、OQ2/OQ4/OQ6、タイムラインの対応
- `playbooks/semaphore_templates_setup.yml`の`hosts: quory`、ansy向けAPI override、check-mode gate
- `roles/semaphore_templates/tasks/main.yml`のread/reconcile/report/apply順序、既存template側get-then-merge-then-send実装
- `docs/ai/context/system/semaphore.md`のansy/quory分離、ansyの鍵不在による検証境界、scheduleがGit外状態であること
- Semaphore公式v2.18.4 tagの存在とschedule modelの公開一次情報を参照したが、実API payloadの独立再取得には用いていない
- 着手時の`git status`。requirement、status、先行reviewは他者成果物として変更していない
- 実ホストへのAnsible、Semaphore APIのGET/POST/PUT/DELETE、commit、pushは未実施

## 未確認事項

- ansy Semaphore API GETは前回安全機構に拒否された操作であり、今回も再試行・迂回していない。requirementが引用する実GET payload、19件の内容、名前重複、`task_params`等の実値は独立確認していない。
- OQ1の「回答20、列挙19」とOQ3のquory API/SQLite突合は未解決。requirementは母集団19で進める判断を明記しているが、ReviewerはOperator回答本文やquory APIを独立取得していない。
- `run_at`等がactive scheduleの実行に伴い自然変化するかは独立確認していない。実行前後のGET完全一致を受入観測に使う際は、自然変化するフィールドがあるなら比較対象を分ける必要がある。

## Verdict

Request Changes
