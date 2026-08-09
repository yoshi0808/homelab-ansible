# Code Review: Semaphore schedules as code requirement

## Summary

既存19件を削除しないこと、idを環境間で共有しないこと、書き込み前に全templateを名前解決することは安全側である。一方、`name`同定と非削除方針の組合せがrename時の二重実行を作ること、Semaphore v2.18.4のscheduleが持つ非管理フィールドの保持要件が無いことをはじめ、本番scheduleを壊さないためのblocking gapが残る。現状のままでは受入条件を満たしても既存scheduleを壊した、または二重化した実装が合格し得る。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 22, 38, 41 | `name`をidentityにしてカタログ外を削除しない場合、UIまたはGitでschedule名を変更すると旧名のactive scheduleを同一物として認識できず、旧scheduleを残したまま新規作成する。これは「手の変更が次のapplyで戻る」という非ゴール節の主張に反し、UN-SAFEを含む定期実行を二重化し得る。schedule名を不変identityとしてrenameを拒否する、旧scheduleを明示的に停止する管理されたrename手順を設ける、または別の永続identityを採る、のいずれかを要件化し、renameの受入条件を追加する必要がある。 | Critical |
| 2 | 同上 | 37, 73, 78 | カタログ管理対象は4項目だけだが、インストール済みSemaphore v2.18.4のschedule objectには少なくとも`type`、`delete_after_run`、`repository_id`、`run_at`、`task_params`もある。v2.18.4の更新APIはrequest bodyを新しい`db.Schedule`へbindしてStoreへ渡すため、管理4項目だけのPUTは非管理フィールドをゼロ値へ落とし得る。AC3は`cron_format`と`id`しか見ないので、この破壊を検出できない。既存raw objectへのget-merge-put、非管理フィールドの実行前後同一性、書き込み直後GETによる全フィールド確認をP0とACへ追加する必要がある。特に`task_params`はschedule固有の実行引数を持ち得るため、保持漏れは実行内容を変える。 | Critical |
| 3 | 同上 | 38, 43, 85-88 | identityであるschedule名の一意性要件が無く、templateについてもR7は「一意でなければ停止」とする一方、AC5が観測するのは0件だけで複数一致を検証しない。カタログ内schedule名、API側schedule名、template名の各cardinalityを全件について書き込み前に検査し、0件・複数件の双方で全scheduleへの書き込み前に停止するACが必要。現状では重複時に誤ったscheduleを更新しても受入を通り得る。 | High |
| 4 | 同上 | 42-43, 65-68 | 同じ変更でtemplateとそれを指すscheduleを新規追加すると、`--check`ではtemplateがまだAPIに存在しないため、R7どおりならschedule側が停止して全体差分を示せない。一方applyではtemplate作成後なら解決でき、check/applyの前提状態が分岐する。「scheduleは実在済みtemplateだけを参照する」という制約、またはdesired template catalogを使ったcheck時の予測とapply時の作成後再解決、のどちらかを決め、同時追加のACを置く必要がある。 | High |
| 5 | 同上 | 13-15, 27, 37 | cron文字列の解釈timezoneが正本に含まれない。Semaphore公式仕様ではschedule timezoneはサーバ設定で、既定UTCかつ設定変更にはservice restartが要るため、同じカタログでもansy/quoryの設定差で実行時刻が変わる。現在の要件では「いつ押されるかをGitで読める」「双方へ同じ定義を反映」の事実を観測できない。カタログのcronがどのtimezoneを前提にするかを明記し、両環境の実効timezoneをread-onlyで照合する前提条件または受入条件を追加する必要がある。 | High |
| 6 | 同上 | 42-43, 70-88 | AC5が全書き込み前の停止を要求するのはtemplate未解決だけで、catalog重複、必須型、boolean、cron妥当性など他の決定的エラーは網羅していない。逐次POST/PUT中に後続entryの不正cron等が判明すると、先行scheduleだけ変更された部分適用になり得る。全catalogのschema・identity・template解決・cronを先にpreflightし、決定的エラーではPOST/PUTを1件も発行しない要件とACが必要。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 7 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 80-83 | AC4の`changedが0件`がAnsible recapかschedule diffかを明記する。既存roleは毎回timestamp付きreportと`latest.json`を`check_mode: false`で保存するため、Ansible recapのchanged=0とは両立しない。観測対象を「POST/PUT 0件、diffのnew/changedが空、GET応答不変」のように定義するとよい。 | acceptance observability / Medium |
| 8 | 同上 | 50 | 「既存template側と同じ場所・同じ形式」だけでは、既存の`semaphore-templates/latest.json`をschedule reportが上書きするのか、単一reportへ統合するのか、別ファイルにするのか決まらない。templateとscheduleの両diffを実行後も同時に読めるpath/schemaを指定する。 | report contract / Medium |
| 9 | 同上 | 21, 60, 99 | `SEMI-SAFE: Semaphore templates setup`のscheduleが19件に含まれるかが明記されず、「扱わない」と「19件が最終的にカタログに載る」が両立するか判定できない。OQ1の19/20も未解決なので、対象母集団と除外後の期待件数を確定して成功指標・AC6を同じ数え方に揃える。 | scope consistency / Medium |

## What Looks Good

- R3/R4はansyとquoryで異なるidをカタログへ持ち込まず、project/templateを適用先で解決するため、環境複製を検証土台に使える。
- R5とAC2/AC6は初回adoptionでカタログ外scheduleを削除しないことを複数の観測点で要求している。件数だけでなくAC2が内容不変、AC6がid集合も見る点はよい。
- R6はGETと差分計算をcheck modeでも実行し、POST/PUTだけをgateする境界を明示している。AC1もAPI GETの実行前後比較とSlack非通知を要求しており、dry-runが外部状態を変えないことを直接観測できる。
- AC3のid不変は、通常の更新が削除・再作成ではないことの有効な観測点である。ただしFinding #2の非管理フィールド比較を加える必要がある。
- AC5は少なくともtemplate未解決を全書き込み前に検出するfail-closed順序を要求している。Finding #3/#6の全preflightへ一般化すれば安全境界として使える。
- 段階適用でSAFEから始め、ansyでcheck/applyしてからquoryへ進む順序は、既存19件を一度に管理下へ入れるリスクを抑える。
- duplication/reuse: 新playbookを作らず既存`semaphore_templates` roleとsetup playbookへ統合する方針は既存資産の再利用になっている。ただしreport namespaceはFinding #8の整理が必要。
- security: tokenをcatalogへ置く要求はなく、既存token読取・`no_log`・TLS検証経路を再利用する前提である。shell/command、信頼できない変数のshell展開、`delegate_to`、secret転載を要求する箇所はない。
- Reviewer定型観点: requirement段階のため多層エスケープとrc規約は対象なし。`--check`で評価されない書き込み分岐はR6/AC1で明示されているが、同時template追加時のcheck/apply分岐はFinding #4。無音化・例外吸収を要求する記述はなく、名前解決はfail-closedを志向している。

## 確認範囲

- `docs/ai/core.md`、`docs/ai/roles/reviewer.md`、`docs/ai/role-context-matrix.md`
- `skills/code-review/SKILL.md`、`skills/duplication-reuse-check/SKILL.md`、`skills/ansible-security-review/SKILL.md`
- 査読対象requirement全文と着手時の`git status`/対象diff
- `docs/ai/context/system/overview.md`、`docs/ai/context/system/semaphore.md`、`docs/ai/context/operations/code-delivery-to-production.md`
- `playbooks/semaphore_templates_setup.yml`、`roles/semaphore_templates/defaults/main.yml`の接続設定・report設定、`roles/semaphore_templates/tasks/{main,resolve,read,reconcile,report,apply}.yml`
- ansyにインストールされたSemaphore package versionが`2.18.4`であることをread-only確認
- Semaphore UI v2.18.4 upstreamの[`api/projects/schedules.go`](https://github.com/semaphoreui/semaphore/blob/v2.18.4/api/projects/schedules.go)と、同系列の[`db/Schedule.go`](https://github.com/semaphoreui/semaphore/blob/develop/db/Schedule.go)、公式の[Schedules timezone仕様](https://docs.semaphoreui.com/user-guide/schedules/)
- 実ホストへのAnsible実行、Semaphore APIのPOST/PUT/DELETE、commit、pushは未実施

## 未確認事項

- ansyのSemaphore APIをGETだけで照会しようとしたが、実行環境の安全機構がnetwork socketを拒否し、昇格要求も承認されなかった。迂回していないため、ansy v2.18.4の実GET応答フィールド、19件の内容、schedule/template名の重複、schedule固有`task_params`の有無は未確認。
- OQ1の19/20、OQ2のrestore後active変化、OQ3のquory API/SQLite一致、OQ4のtemplate削除時挙動はrequirement記載どおり未解決。OQ1は成功指標の母数に影響し、OQ3と非管理フィールド実態は初回書き込み前のread-only gateとして解消が必要。
- upstream `db/Schedule.go`はv2.18.4 tagのページ取得に失敗したため、同じフィールド集合を持つdevelop版を参照した。v2.18.4のAPI handler現物とansy package versionは確認済みだが、最終的なpayload契約はansyのread-only GETおよび書き込みを許可されたTesterの隔離検証で確定する必要がある。

## Verdict

Request Changes
