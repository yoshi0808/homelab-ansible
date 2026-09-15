# Code Review: semaphore_reconcile_daily_sync Phase 2 計画再々査読後の再査読

## Summary

`_008` Blocking #1の計画/payload分離は、現行のtemplate POST結果とschedule名前解決を二段に分ければ成立し、AC11/AC11aも相反実装を落とせるため解消した。Blocking #2はimmutable run reportへmarker publish結果を記録する順序が自己矛盾し、Blocking #3はrole defaultをreserved-name guardのallowlistから外すと通常実行まで拒否するため未解消である。

## Critical Issues

該当なし。

## Blocking Issues

| # | File | Line | Issue | Severity | 必要な対応 |
|---|---|---:|---|---|---|
| 1 | `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_001_requirement.md` | 74-99, 188-191 | run reportをmarkerより先にimmutable publishし、そのreport自身へ`marker_published`を記録する契約は成立しない。先にpublishする時点ではmarker更新結果がまだ無いため、`false`で保存すればmarker成功時に誤り、`true`で保存すればmarker失敗時にAC13aの`false`を満たさない。marker後に同じreportを差し替えれば「毎回・不変」に反し、markerを先にすればAC13bの「参照先は常に既存」に反する。2ファイルを同時に原子的publishする機構も現行のcopy/rename単位には無い。 | Major | `marker_published`をimmutable run reportから外してmarkerの有無/内容そのものを結果の正本にする、またはpublish前のdraftと最終reportを別path/別成果物にする等、単一ファイルのimmutability・参照先の先行存在・marker結果の記録を同時に満たす状態遷移へ変更する。marker失敗時のrc非ゼロ・通知・旧marker維持は現記述のまま維持できる。 |
| 2 | 同上 | 148-161, 197-209 | `semaphore_schedules_canonical_api_base_url`をallowlistから外すだけでは`-e`だけを拒否できない。この変数はrole defaultとして実行開始時から定義済みであり(`roles/semaphore_templates/defaults/main.yml:1070-1100`)、guardは変数の出所を見ず、定義済みの`(_)?semaphore_schedules_*`全体からliteral allowlistの補集合を拒否する(`schedules_validate_config.yml:55-68,95-130`)。したがって105/125行のallowlist要素を削ると、`-e`無しの通常実行でもdefault自身を検出して必ずfailする。P0-14のschedule環境も同変数を参照するため、変数を単に削除する案でも閉じない。 | Major | extra-varsとrole defaultをguardで識別できるという前提を捨て、canonical値を外部変数名前空間から除くなら、filter plugin内の非上書き定数/関数等の実際にoverride不能な正本へ移し、P0-14のtask_paramsも同じ正本から値を得る設計を決める。別方式を採る場合も、通常実行は通り、canonical値の`-e`指定だけがwrite前に非ゼロとなることをAC19eで実証できる仕組みを具体化する。 |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_001_requirement.md` | 89 | P0-8aは表が7ケース、AC13も7ケースなので、見出しの「6ケース」を「7ケース」へ揃える。 | Documentation |
| 2 | 同上 | 161 | `semaphore_schedules_would_newly_activate`はdesired=falseなら発火せず、desiredをtrueのままにした場合もfresh active=trueには発火しない。非canonical既存active=trueの倒し忘れを止める完全な不変条件ではないため、「false→trueの混入を止める防御」と責務を限定すると実装者が過信しない。 | Correctness |

## `_008` Blocking 3件の解消判定

| `_008` # | 判定 | 根拠 |
|---:|---|---|
| 1 計画/payload分離 | **解消** | write前計画はschedule名の存在、現行detail、catalog参照名、今回作成予定template名から対象と件数を確定できる。新規templateの数値idだけをpendingにし、template POST/verify後に埋めればよい。現行POST結果はidを返し保持する(`roles/semaphore_templates/tasks/apply.yml:40-79,113-126`)。計画時に未解決かつ今回作成予定でない参照を拒否するP0-7と、混在5件・同時追加を固定するAC11/AC11aにより、資源別判定や従来R10を壊す実装も落ちる。 |
| 2 marker保存失敗 | **未解消** | 失敗時のrc・通知・旧marker維持は確定したが、先行publishされるimmutable reportが後続markerの成否を正しく持つことはできない(Blocking #1)。 |
| 3 canonical判定 | **未解消** | effective active=falseとAC19の6ケースは具体化されたが、提案したallowlist削除はdefault自身も拒否する(Blocking #2)。 |

## What Looks Good

- P0-7は「write-setの対象/件数」と「新規template idを含むpayload」を分離し、未解決参照を今回作成予定templateに限定した。現行preflightをそのまま前倒しするのではなく、計画用判定とapply後の厳格なid確定に分ける必要が明瞭である。
- AC11はtemplateのみ、scheduleのみ、2+3混在の5件を列挙し、資源別上限という誤実装を落とす。AC11aは同一変更での新規template+参照scheduleについて、上限内の到達性と上限超過時0 writeの双方を固定した。
- P0-15/AC19は非canonicalのeffective activeをdiff・POST/PUT・verifyの全段でfalseとし、既存active=trueだけが差分のケースもchangedへ数える。`semaphore_schedules_would_newly_activate(False)`はfalseを返すため、この変換後の正常経路とR2 helper自体は矛盾しない(`filter_plugins/semaphore_schedules.py:873-881`)。
- canonicalではfresh active保持、非canonicalではfalse強制という優先関係が明示され、AC9とAC19を同時に適用して相反する余地は無い。
- run idのミリ秒+task id/manual PIDは前回Suggestionを解消している。
- 新しいshell/command、秘密値の複製、既存ロジックの別実装は要求しておらず、セキュリティおよび重複・再利用観点の追加findingは無い。

## 確認済み事項

- `schedules_preflight`の現行③は全catalog参照を実在template一覧へ即時解決するため、そのままwrite前へ移動することはできない(`roles/semaphore_templates/filter_plugins/semaphore_schedules.py:519-535`)。P0-7は今回作成予定参照をpendingにする計画段を新設するため、この点を意図的に変更対象としている。
- template POSTは各結果の`json.id`を検証し、作成結果とid一覧を保持する(`roles/semaphore_templates/tasks/apply.yml:40-79,113-126`)。payload確定に必要な実idをtemplate apply後に利用できる。
- reserved-name guardは定義元を区別せず、prefix一致した全変数名からallowlistを除外する式である。同じallowlist literalがmessage側とwhen側に重複している(`roles/semaphore_templates/tasks/schedules_validate_config.yml:95-130`)。
- 現行helperはdesired=falseを常に「newly activateではない」とし、before=true/desired=trueもfalseを返す(`roles/semaphore_templates/filter_plugins/semaphore_schedules.py:873-881`)。したがってfalse変換と矛盾はしないが、既存active=trueのfalse変換漏れを単独では検出しない。
- 本査読では実ホスト、Semaphore API、Slack、Notionへ接触していない。

## 未確認事項・残存リスク

- P0-7の計画用filter/taskとapply後payload確定は未実装であり、実装差分レビューではpending参照、部分template失敗後の再実行、check modeの経路を確認する必要がある。
- schedule起動時のsurvey既定値適用とcatalog外bootstrap template参照可否は、P0-14が指定するansyでの実装前観測待ちである。
- Phase 2実装後の本番apply/readback、04:00実行、通知、鮮度findingはRequirement所定の後続検証が必要である。

## Verdict

**Request Changes**

Major 2件がblocking。`_008` Blocking #1は閉じたが、run report/markerのpublish順序とcanonical値のoverride不能な正本を実装可能な形へ直してからPhase 2へ進む。
