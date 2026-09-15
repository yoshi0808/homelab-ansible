# Code Review: semaphore_reconcile_daily_sync Phase 2 計画再査読

## Summary

前回Finding 1の残存リスクとFinding 2の監視範囲は、判断を回避せず明示できている。`active`分離と曜日判定も実装・試験可能な粒度になった。一方、更新上限の実効値、最終reportと通知の失敗時状態、鮮度閾値、撤去対象識別子、04:00 scheduleの実値、orphan baselineがまだ未決定であり、AC9〜AC18だけでは複数の相反する実装を合格にできるため、実装着手前の変更を求める。

## Critical Issues

該当なし。

## Blocking Issues

| # | File | Line | Issue | Severity | 必要な対応 |
|---|---|---:|---|---|---|
| 1 | `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_001_requirement.md` | 57-59, 94 | 更新上限の目的と、1件の誤記をcommit reviewだけに残す判断は明記されたため、前回Finding 1を言い換えて回避したものではない。ただし既定値を「通常の作業で発火しない値」としか制約しておらず、catalog全件以上の値でも文面を満たす。その場合、想定する「比較ロジックの破損で全件changed」を止められず、追加したgateが目的を果たさない。AC11にも既定境界の具体値または選定基準を検証するcaseがない。 | Major | Yoshinobuが受容する具体的な既定件数、またはcatalog規模に依存しない十分狭い上限規則を決定し、defaultsの値と境界値`N`/`N+1`をAC11で固定する。1件の意味的誤記は対象外という残存リスクは現記述のまま維持してよい。combined countをtemplate applyより前に確定し、超過時にscheduleを含む全writeが0件となる実行順も実装記録・testへ要求する。 |
| 2 | 同上 | 60-64, 95-97 | P0-8は「最終run reportを1つ」としながら、success reportは全apply/verify成功後だけ更新すると定め、同じreportへ失敗status・部分適用・通知結果も求めている。失敗runではsuccess reportを更新できず、report保存失敗自身をそのreportへ記録することもできない。さらにP0-9/AC13は5ケースの対応を「定める」と書くだけで、通知試行、rc、latest successの維持、失敗runの証跡を実際には定めていない。`common_slack`のevidence capture自体もbest-effortで失敗を吸収する(`roles/common_slack/tasks/notify.yml:44-51`)ため、「evidenceが生成されたこと」を通知ありの必須条件にすると既存経路のままでは成立しない。 | Major | immutableな各run reportと原子的なlatest-success markerを分ける等、成果物と役割を確定する。path、publish条件、失敗時に前回successを維持するか、report-save失敗の代替証跡をACへ明記する。5ケースにevidence-capture失敗も加え、各行の通知include到達、evidence有無、Slack試行、rc、run report、latest-successを具体的な表として本文へ置く。既存2つの`latest.json`は資源別diff/outcomeとして残すのか廃止するのかを決め、aggregate reportとの正本関係を明記する。 |
| 3 | 同上 | 67-70, 99, 109 | P0-13は同一Semaphore故障を検出しないと明記しており、「reconcile scheduleだけの故障を検出する」機構として誤った安心は生んでいない。しかし鮮度閾値は「次のdrift checkで検知なら位相差に合わせる」という未決定の条件文のままで、AC16も単に「閾値」としか書かない。したがって24時間、48時間、無期限のどれでもACを満たし得る。また§7は旧番号P0-10を鮮度監視として参照しており、現P0-10は秘密保護なので決定記録が誤参照になった。 | Major | 04:00成功を00:40のどの回までに検知するかSLOを決め、そこから閾値の実値と境界時刻を固定する。AC16に直前/一致/超過の時刻caseを置く。§7の参照をP0-13へ直し、Semaphore/quory全停止は非対象という決定も同じ表に残す。 |
| 4 | 同上 | 66, 100 | P0-12は識別子を「名指しする」と要求するだけで、`semaphore_template`、`semaphore_probe_error`、`checked_counts.semaphore_templates`のどれを撤去・維持・置換するか決めていない。AC17も「P0-12で名指しした識別子」という循環参照になっており、現状ではtemplate比較を旧probeと新reconcileの両方に残す重複実装も、probe全体を消して接続失敗とchecked-countを失う実装も合格し得る。 | Major | 3識別子それぞれについてremove/keep/replaceを本文で決定し、追加する鮮度findingのcategory名も固定する。AC17は具体的なcategory/keyを列挙し、旧template diffが出ないこと、接続失敗の観測と維持対象checked-countが残ることをassertできる形にする。 |
| 5 | 同上 | 71-73, 101 | P0-14はscheduleの5フィールドを「カタログで確定する」としたが、requirementには実際のname、template名、cron、active、task_paramsが記載されていない。AC18のreadbackも期待値を持たないため、04:00以外のcronやcheck相当のtask_paramsを誤って登録しても「5項目を確認した」だけで通る。bootstrap主体と初回確認の順序は閉じたが、前回Finding 5の運用identityは未解決である。 | Major | 5フィールドの期待値をrequirementへ列挙する。少なくともcronはJST 04:00、activeは初回日次runを成立させる値、task_paramsはapplyで起動する値であることを構造化して固定し、AC18のAPI readbackをその値との一致判定にする。catalog外templateを参照できることの事前確認についても、誰がどの無害な環境または既存API readbackで確認し、どの記録を実装gateとするかを指定する。 |
| 6 | 同上 | 65, 98 | orphan比較を`name / playbook`へ移しidを除外した点は前回Finding 6を正しい方向へ直したが、baselineの格納場所・実値・文字列正規化が未定である。また「集合」を数学的setとして実装すると、同じ正規化keyを持つorphanが1件から2件へ増えても集合は変わらず通知できない。AC15の「追加」はこの重複追加を明示しておらず、複数の解釈が残る。 | Major | baselineの変数/pathと期待する`name`/`playbook`の組をrequirementで固定し、trim・大小文字・path表現などの正規化契約を定める。比較対象は重複を保持するsorted list/multisetとするか、重複keyをpreflight失敗にする。AC15へ同一keyの重複追加とbaselineの欠落・型違いを加える。 |
| 7 | `docs/ai/context/system/semaphore.md` | 依存関係、§7 | P0-5は既存scheduleの`active`を同期対象から外すが、対象System Contextは現在も「UIの一時変更は次の適用で戻る」「管理する5項目にactiveを含む」と規定している。requirementのPhase 2作業範囲にこのContext更新がなく、実装後に運用者が誤った復元挙動を前提にする。 | Major | Phase 2の成果物にSystem Contextの`active`契約更新を含め、既存更新では4項目同期+fresh active保持、新規作成ではcatalog active使用、金曜一覧で停止を観測する、という新しい責務を一貫させる。 |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_001_requirement.md` | 92 | AC9へ、`active`だけが異なる場合に通常changed=0かつ金曜一覧には載るcaseと、`active: false`かつcron差のPUT後verifyでfalseを保つcaseを明記すると、diff・通知・write・verifyの4経路をまとめて固定できる。 | Correctness / test gap |
| 2 | 同上 | 96-97 | token/API失敗文のnegative assertionは、通知本文と新run reportに加えて既存template/schedule report、console log、notification evidenceも対象として列挙すると、scrub済みwrapperから別成果物への再露出を防ぎやすい。 | Security / test gap |

## What Looks Good

- **前回Finding 1の判断は回避ではない。** P0-7は機械起因のfan-outを更新上限で止め、1件の意味的誤記はcommit reviewだけが防ぐ残存リスクとして分離した。後者をYoshinobu了承済みとした境界は明瞭である。blockingは上限の実効値が未決定な点だけである。
- **前回Finding 2の故障範囲は正直に限定された。** P0-13はreconcile schedule単独故障だけを対象とし、Semaphore service・scheduler・quory停止では監視側も走らないことを明記した。このscope決定自体はApproveできる。
- P0-5/AC9は既存更新のfresh `active`保持、新規作成のcatalog値、非canonicalでの有効作成拒否を分離した。diff後の競合caseもACへ入った。
- P0-6/AC10は`Asia/Tokyo`、金曜の停止あり/なし、金曜以外のnegative caseを固定した。
- P0-10/AC14はscrub済み情報だけを通知wrapperへ渡す境界を明示し、既存の漏えい防止構造と整合する。
- P0-11は数値idを診断情報へ限定し、baselineの自動学習を禁じた。P0-14/AC18は本番適用をYoshinobuへ限定し、API readback、初回04:00 run、Notion closeoutまでbootstrap工程へ含めた。

## 確認済み事項

- 現行task順はtemplate diff/report/applyの後にscheduleのread/diff/applyへ進む(`roles/semaphore_templates/tasks/main.yml:58-75,142-160`)。P0-7の合算上限を両資源のwrite前に判定するには、この順序を再構成する必要がある。
- template `latest.json`はapply前、schedule `latest.json`はschedule blockの`always`から成功・失敗ともに保存される。新しいaggregate成果物と同じ成功意味を持たないため、役割を明記すれば共存自体は重複欠陥ではない。
- `common_slack`はevidence capture失敗とSlack送信失敗をそれぞれ吸収する。include到達、evidence生成、配送成功は別々の観測である。
- 現行orphanは観測行を保持するため`name`と`playbook`を比較材料にできるが、reconcile結果は重複を含み得るlistである。
- 本再査読では実ホスト、Semaphore API、Slack、Notionへ接触しておらず、requirement、対象Context、現行role/playbookだけを静的に照合した。

## 未確認事項・残存リスク

- catalog外のbootstrap templateをscheduleが参照できることは、今回のReviewer権限では実APIで再確認していない。P0-14が実装前gateとして要求する観測は未実施である。
- Phase 2実装後の初回apply/readback、04:00実行、通知evidence、鮮度findingはYoshinobu起動とTester/Operatorの観測が必要である。
- P0-13が明示的に対象外としたSemaphore/quory全停止には、本案件による新しい検知経路はない。

## Verdict

**Request Changes**

Major 7件がblocking。前回Finding 1のリスク分離とFinding 2のscope縮小は妥当だが、Finding 1の上限実効値、Finding 3〜6の具体的な契約、および変更後のSystem Context整合を確定してからPhase 2を再査読する。
