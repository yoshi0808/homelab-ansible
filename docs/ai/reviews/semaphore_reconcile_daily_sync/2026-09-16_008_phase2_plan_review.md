# Code Review: semaphore_reconcile_daily_sync Phase 2 計画再々査読

## Summary

前回 Major 7件のうち、#3(鮮度閾値)、#4(probe識別子)、#5(04:00 schedule)、#6(orphan baseline)は閉じた。#1は具体値を、#2は成果物分離を、#7は新しい`active`方針を決めた点までは前進したが、現行実行経路と両立する事前計画、`latest-success`保存失敗時の状態、`-e`で上書きできないcanonical判定根拠が未確定であり、相反する実装がAC9〜AC19を通過しうる。

## Critical Issues

該当なし。

## Blocking Issues

| # | File | Line | Issue | Severity | 必要な対応 |
|---|---|---:|---|---|---|
| 1 | `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_001_requirement.md` | 58-60, 160 | P0-7は両資源のdiffをtemplate apply前に完了させるが、現行schedule diffはtemplate apply後のfresh template一覧から`template_id`を解決する設計である(`roles/semaphore_templates/tasks/schedules_read.yml:2-7,14-17`、`schedules_preflight.yml:17-25`、`filter_plugins/semaphore_schedules.py:519-535`)。同一変更でtemplateとそれを参照するscheduleを追加すると、先にschedule diffを完成できず、template applyもまだ許されないため停止する。これは現行カタログが明記する「templateとscheduleを同じ変更で追加し、templateを先に適用する」経路(`defaults/main.yml:719-725`)との衝突である。またAC11はtemplateだけ5件・scheduleだけ5件を試すが、2+3件を合算せず各資源別上限で判定する誤実装も通過できる。 | Major | 書き込み前に確定する「計画」と、POST後にしか得られない新規template idを使うschedule payloadを分離する等、同時追加を壊さず合算更新数を確定する実行モデルを決める。AC11へtemplate+scheduleの混在5件、および同一変更で新規templateを参照する新規scheduleの経路を追加し、上限超過時0 writeと上限内の到達性を固定する。 |
| 2 | 同上 | 63-84, 161-162 | P0-8aはrun report保存失敗を定めたが、別成果物である`latest-success` markerの保存失敗を定めていない。全apply/verify成功後、immutableなrun reportを先にpublishしてからmarker更新が失敗すると、最終rcを非ゼロにする実装では保存済みreportの`status=success`と最終結果が食い違い、rc=0にする実装では生存確認が更新されない失敗を成功扱いにする。markerを先に書けば、まだ存在しないrun reportを一時的に参照しうる。いずれも現在の6ケース/AC13だけでは合否を決められない。 | Major | `latest-success` publish失敗を独立ケースとして追加し、notify include、最終rc、run reportのstatus/内容、旧markerの維持を固定する。run reportが最終statusと通知試行結果を持ち、markerが存在するreportだけを参照するよう、temp作成・publish・marker差替えの順序と失敗時状態を実装可能な形で決める。 |
| 3 | 同上 | 133-137, 168 | P0-15/AC19は`-e semaphore_schedules_canonical_api_base_url=<ansy>`でもansyを非canonicalのまま扱うが、現行R2の判定値は実接続URLとその上書き可能な変数の比較だけである(`schedules_canonical_check.yml:47-51`、`filter_plugins/semaphore_schedules.py:900-916`)。したがって現物のままでは両方をansyへ上書きするとcanonicalになる。さらに既存R2はtrueを書こうとした時にfailする(`schedules_apply_new_item.yml:29-52`、`schedules_apply_item.yml:87-118`)のに対し、P0-15は非canonicalではdesired/payloadをfalseへ変えて書く契約であり、単なるゲート延長では整合しない。AC19も既存`active:false`の更新しか固定せず、非canonicalで既存`active:true`かつ他差分あり、またはactiveだけtrueのときにfalseへ倒すかを判定できない。 | Major | 外部overrideから独立した「production/canonical接続先」の正本を1つ決め、実接続先との比較方法を定める。非canonical時のeffective desiredをdiff・POST/PUT・verifyの全てでfalseにするのかを明記し、少なくとも新規、既存false+他差分、既存true+他差分、既存trueのみ、canonical変数上書き、`semaphore_target=ansy`の各caseをAC19へ置く。既存`would_newly_activate`は、この変換後も防御として残すのか、責務を置き換えるのかを明記する。 |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_001_requirement.md` | 72 | manual runが同時または同一時刻に始まってもimmutable run reportのpathが衝突しないよう、開始時刻の精度または追加suffixを固定するとよい。 | Correctness |

## 前回 Major 7件の解消判定

| `_007` # | 判定 | 根拠 |
|---:|---|---|
| 1 更新上限 | **未解消** | 既定4件とN/N+1は確定したが、現行R10との衝突と混在合算caseが残る(Blocking #1)。 |
| 2 run report / latest-success / 通知 | **未解消** | 2成果物への分離と6ケースは確定したが、marker保存失敗の最終状態が無い(Blocking #2)。 |
| 3 鮮度閾値 | **解消** | P0-13/AC16が20:40、境界24:00、欠測後44:40とcategoryを固定した。 |
| 4 probe識別子 | **解消** | P0-12/AC17がremove/keep/addと具体的なcategory/keyを固定した。 |
| 5 04:00 schedule | **解消** | P0-14/AC18が5フィールド、apply条件、readback、事前観測gateを固定した。 |
| 6 orphan baseline | **解消** | P0-11/AC15が格納先、実値、正規化、重複保持、異常baselineを固定した。 |
| 7 `active`契約 / Context | **未解消** | 更新対象Contextは名指しされたが、P0-15を成立させるcanonical判定根拠と既存active=trueの契約が未確定(Blocking #3)。 |

## What Looks Good

- P0-7の固定値4はcatalog規模へ比例せず、1件の意味的誤記を対象外とする残存リスクも明記されている。
- P0-13は「04:00の1回欠測を次の00:40で検出」というSLOから24時間境界を導き、Semaphore/quory全停止を検出しない範囲も誇張していない。
- P0-12、P0-14、P0-11は、前回相反実装を許していた識別子・実値・比較表現を具体化した。
- P0-10/AC14は既存のscrub済み経路を再利用し、通知、各report、console、evidenceまでnegative assertionの対象にした。新たなshell/command、無引用変数、秘密値の複製を要求していない。
- 既存の資源別`latest.json`をdiff/outcomeとして残し、aggregateの生存確認正本と分離するため、既存成果物の無用な再実装・削除は避けられている。

## 確認済み事項

- 現行順序はtemplate diff/report/applyの後にschedule read/preflight/diff/applyへ進む(`roles/semaphore_templates/tasks/main.yml:58-75,142-161`)。
- schedule preflightは、実在するtemplate名を1件の数値idへ解決できなければ失敗する(`roles/semaphore_templates/filter_plugins/semaphore_schedules.py:519-535`)。
- 現行R2は`semaphore_schedules_canonical_api_base_url`を外部設定allowlistに含め(`roles/semaphore_templates/tasks/schedules_validate_config.yml:103-108,115-128`)、実接続URLとの一致だけをcanonical判定に使う。
- `semaphore_schedules_would_newly_activate`はdesired=falseなら常に「有効化ではない」と返す(`roles/semaphore_templates/filter_plugins/semaphore_schedules.py:873-881`)。P0-15をeffective desired=falseとして先に適用するなら、現行R2は拒否ではなく防御的な不変条件へ役割が変わる。
- Incidentの直接原因記述は現物と一致する。新規はcatalog activeをPOST payloadへそのまま入れ、既存更新もfresh GETへcatalog activeを上書きする一方、canonical変数をansyへ上書きするとR2は通過する(`schedules_apply_new_item.yml:29-65`、`schedules_apply_item.yml:87-132`)。
- 本査読では実ホスト、Semaphore API、Slack、Notionへ接触していない。

## 未確認事項・残存リスク

- schedule起動時のsurvey既定値適用と、catalog外bootstrap templateの参照可否は、P0-14が指定するansyでの実装前観測待ちである。
- Phase 2実装後の初回本番apply/readback、04:00実行、通知、鮮度findingは、Requirementが定めるYoshinobu/Tester側の検証が必要である。
- P0-13が明示的に対象外としたSemaphore service・scheduler・quory全停止には、本案件による検知経路は無い。

## Verdict

**Request Changes**

Major 3件がblocking。前回7件のうち4件は閉じたが、更新上限の事前計画、成果物publish失敗の全状態、P0-15の非迂回canonical判定を確定してからPhase 2実装へ進む。
