# Code Review: Semaphore schedules as code requirement 再査読

## Summary

前回9件のうち、非管理フィールド保持、一意性、同時template追加、timezone前提、全件preflight、冪等性の観測、report分離、対象母集団の8件は要件またはACへ実質的に反映された。一方、`name`を不変と宣言しただけではrenameを検知・拒否できず、二重実行経路は残る。また、timezone照合の対象とAPI接続先を同一Semaphoreへ結び付ける実行契約、およびP0/P1の優先度に新たな穴がある。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 20, 23, 40, 62 | 前回Finding #1は未解消。`name`を「不変」と宣言しても、APIに見えるのは変更後の名前だけなので、UI renameまたはcatalog renameを検知して拒否する手掛かりがない。reconcileには「正当な新規schedule」と「旧active scheduleのrename」を区別できず、R5により旧名を残して新名をPOSTする。R14をP2へ送る間も二重実行経路は存在し、line 23の「手の変更が次のapplyで戻る」もnameについては成立しない。初回scopeでrenameを扱わないなら、少なくともname変更は戻らないことを明記し、catalogの既存name変更を機械的に拒否できるidentity/台帳または全件管理後の集合不変条件をP0に置く必要がある。 | Critical |
| 2 | 同上 | 15, 25, 48, 111-114, 133-135 | R10/AC9は「対象ホストの実効timezone」を要求するが、既存playbookは`hosts: quory`固定で、現行コメント上のansy検証はAPI baseだけをansyへ向ける。これでは実行ホストquoryの設定を読んでansyのSemaphore timezoneを合格させ得る。さらにtimezoneはconfig、`SEMAPHORE_SCHEDULE_TIMEZONE`、既定UTCのいずれからも決まり得るが、実効値の観測元と優先順位が未指定である。ansy/quoryそれぞれについて「API接続先のSemaphore process」と「timezone観測対象」が同一であること、実効値をどのread-only情報から確定するか、token pathを含む実行方法をP0とACへ明記しないと、AC9の観測は主張する事実を観測しない。 | High |
| 3 | 同上 | 39, 54, 76-84 | `active`はR1の管理4項目かつAC2/AC3の必須観測なのに、値を確定するR11だけがP1「初回に入れたい」に置かれている。P1を省略した初回実装でもP0を満たした扱いになり、既存19件の有効/無効を正本化できない。`active`は定期実行の停止・開始そのものなのでR11をP0へ移し、全4管理項目のdiff/applyを初回必須にする必要がある。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 4 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 46 | R8の「preflightを完了してから、書き込みを1件も発行しない」は、字義どおりにはpreflight完了後も書き込み禁止になる。「全preflightを完了する**まで**書き込みを1件も発行しない」へ直す。AC7の意図は正しいため、文言修正で解消できる。 | requirement wording / Medium |
| 5 | 同上 | 44, 55, 71-74 | R6/AC1は初回から差分reportを必須にする一方、template reportと共存させるpath/schema契約のR12はP1である。P1を省略すると既存`latest.json`を上書きしてもP0/AC1を満たす余地が戻るため、R12をP0へ移す。 | priority consistency / Medium |
| 6 | 同上 | 22, 48, 120-125 | 改訂で追加された「現行19件に対象templateのscheduleは0件」「ansyの実効timezoneはAsia/Tokyo」という実測は、requirement内に照会IDや観測手段がなく、Reviewer側でもAPI GETが安全機構に拒否され独立確認できなかった。設計を変えるblocking issueではないが、後続が同じ事実を再確認できるread-only観測の参照を記録する。 | traceability / Medium |

## What Looks Good

- 前回Finding #2: R7とAC3にget-then-merge-then-send、非管理フィールドの実行前後一致、直後GETが入り、管理4項目だけのPUTを合格させる穴は解消した。
- 前回Finding #3/#6: R8、AC5、AC7、AC8がcatalog/APIのschedule名重複、templateの0件/複数件、cron・型・必須項目を全件preflightし、決定的エラー時のGET完全一致と書き込み0件を観測する。Finding #4の「完了してから」は文言上の修正だけが残る。
- 前回Finding #4: R9でscheduleは実在済みtemplateだけを参照し、同時追加を2段階に分けたため、check/applyの前提分岐は解消した。
- 前回Finding #5: カタログtimezone、適用前照合、不一致停止、OQ4とタイムライン0が追加された。timezoneをGit外の暗黙前提にした問題は設計上認識されたが、Finding #2の実行トポロジ・観測元を補う必要がある。
- 前回Suggestion #7: AC4はAnsible recapを明示的に除外し、POST/PUT 0件、diffのnew/changed空、GET一致を観測するため、冪等性の主張を直接観測できる。
- 前回Suggestion #8: R12は既存`latest.json`を上書きせず両reportを同時に読めることを要求している。内容は解消しており、Finding #5は優先度だけの問題。
- 前回Suggestion #9: 対象templateを指すscheduleが現行19件に含まれないことを明記し、成功指標の母数を19へ固定したため、要件内部の数え方は整合した。OQ1の20という回答は未確認事項として正直に残されている。
- AC2はcatalog外scheduleの件数と内容、AC6は件数とid集合を見るため、段階adoption中の管理外scheduleを削除しない観測は維持されている。
- duplication/reuse: template側で実証済みのraw object保持と`combine`パターンをR7で再利用し、新playbookを増やさない方針を維持している。
- security: tokenをrepoへ保存する要求、TLS検証の弱化、shell/commandへの変数展開、secretのreport出力は追加されていない。timezone観測はread-onlyに限定されている。
- Reviewer定型観点: requirement段階のため多層エスケープとrc規約は対象なし。`--check`で評価されない分岐はR6/R9とAC1で扱われ、書き込みはcheck modeでgateされる。例外吸収・無音化を要求する記述はなく、preflight失敗は非ゼロでfail-closedとなる。

## 確認範囲

- 改訂後requirement全文、前回review全文、両者のworktree diff
- 前回Critical 2 / High 4 / Medium 3の各findingと改訂R2/R7-R10/R12/R14、AC3-AC9、OQ1/OQ4/OQ6、タイムラインの対応
- `playbooks/semaphore_templates_setup.yml`の実行host、ansy向けoverrideコメント、tester-gate
- 前回確認済みのSemaphore v2.18.4 schedule payload/更新handler、公式timezone仕様、template側get-then-merge-then-send実装
- 着手時の`git status`。既存のrequirement/status/前回reviewの変更は他者成果物として変更していない
- 実ホストへのAnsible、Semaphore API GET/POST/PUT/DELETE、commit、pushは未実施

## 未確認事項

- 前回、安全機構がansy API GETを拒否し昇格も承認されなかったため、同じ操作を再試行・迂回していない。実GET payload、schedule/task_params、名前重複、追加された2つの実測事実は未確認。
- requirement記載のOQ1-OQ6は引き続き未解決。特にOQ4のquory timezoneとOQ6のquory versionはカタログ確定・payload契約の先行条件である。
- renameを機械的に拒否する方式と、ansy向けに既存playbookを安全にどのinventory/connectionで実行するかは未決定であり、Critical #1 / High #2の解消に必要。

## Verdict

Request Changes
