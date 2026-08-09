# Code Review: Semaphore schedules as code requirement 5回目査読

## Summary

R18は、移行期間を既存19件の書き写しに限定し、未実在名をpreflightで弾くという方針としては、前回Criticalの「reconcile由来のrename二重active」を閉じられる。しかし旧来のR2/R15/AC10が残っており、同一の移行中renameに対して「非ゼロ・書き込み0」と「終了0・新規作成」の両方を要求している。またR19のansy恒久ガードは、接続先との結び付けと、それを識別できる受入観測が不足している。このままでは実装者が一意な挙動を決められず、安全機構を実証できない。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 40, 52, 54, 63, 89-97, 139-142 | **R18とR2/R15/AC10が同一入力に相反する結果を要求する。** 移行期間にcatalogの既存名を新名へ変えると、新名はAPIに存在しないため、R18/AC2bではpreflight非ゼロ・POST/PUT/DELETE 0でなければならない。一方R2/R15/AC10は旧名を残して新名を`active:false`で作り、終了0とする。さらにclosed-worldでは旧名が管理外になるためR13/AC11が書き込み前に止め、R14はrenameを将来扱いとしている。したがって現要件ではrenameが許されるフェーズは無い。R18を採用するなら、R2/R15のrename作成説明とAC10を削除または「移行中renameはR18で拒否されAPI完全一致」に改め、R18末尾も「新規追加はclosed-world、renameはR14まで非対応」とする必要がある。なおAC1の広いGivenも移行中の未実在名を含み得て終了0を要求するため、AC1を「preflightが成立する既存scheduleの管理値差分」に限定する必要がある。 | Critical |
| 2 | 同上 | 55, 109-112, 159-162, 169-172 | **AC15は「ansyでは常に有効化不許可」を観測できない。** Whenで明示的な有効化許可を渡していないため、接続先を一切見ず、R19の既定値falseだけを実装してもAC15を通る。加えてAC4b/AC13の成功側はAPI接続先をquoryに限定しておらず、AC2からansyを選ぶとAC4bの有効化成功とR19が衝突する。既存playbookは`hosts: quory`のままAPI base URLだけを`-e`でansyへ切り替えるため、inventory hostでは接続先を識別できない。R19に「書き込みと同じ正規化済みAPI base URLを基にansyを判定する」等の結び付けを定義し、AC15をcatalog=true/observed=false・closed-world・管理外0・**明示許可=true**でもPUT 0へ強化する。AC4b/AC13の有効化成功側はquory・明示許可=trueとする。 | High |
| 3 | 同上 | 51, 67-73, 149-152 | **「UI由来の二重activeを見つけたら書き込みを止める」という保証境界が、移行期間のR13/AC12と一致しない。** 移行中にUIで別名のactive scheduleが追加された場合、それは管理外として検出されるが、R13は終了0で処理を続け、AC12は他のcron/template更新を実際に適用するよう要求する。closed-worldならR13が停止するため、line 67の保証はclosed-worldに限れば成立する。保証文をフェーズ別に分け、移行中は「管理外を報告し、有効化だけ見送る。その他の管理更新は継続」、closed-worldでは「全書き込みを停止」と明記する必要がある。UI権限維持・非削除のためUI由来の二重active自体を自動解消しない、という線引きは妥当である。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 4 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 109-112, 149-157, 169-172 | phase、接続先、有効化許可の組合せで結果が変わるACには、その前提をGiven/Whenへ明記する。特にAC12は`closed-world=false`、AC4bの②とAC13の③は`closed-world=true`・管理外0・quory・明示許可=trueが必要である。これによりAC単体で期待結果が一意になる。 | acceptance precision / Medium |

## What Looks Good

- R18の「移行中はAPIに既にある名前だけを採用し、未実在名は全書き込み前に拒否する」という不変条件は、残存する矛盾を除けば、前回Criticalのrename経路を検出ではなく防止で閉じる。
- R19の実行ごとの許可・既定不許可という二重ゲートは、quoryの意図しない有効化を防ぐ安全側の既定である。ansy恒久不許可も方針としては前回Highを解消する。
- R20/AC16はpreflight後のschedule追加を再GETで検出し、有効化を見送ってレポートする。transaction/ETagが無い残余も過大保証せず明記している。
- AC2/AC4/AC4bは、新規をfalseで作るapplyと、別applyでの有効化、その後の冪等を分離し、前回Highの即時冪等との矛盾を解消した。
- AC14はclosed-world=false・管理外0の境界を直接観測し、前回Mediumのフラグ無視実装を通す穴を解消した。
- duplication/reuse: 既存playbookとtemplate側のget-then-merge-then-send、名前解決、report/apply分離を再利用し、schedule固有の状態規則だけを追加する方針を維持している。
- security: token値の記録、TLS検証の弱化、shell/command経由の変数展開、DELETEは要求していない。今回の確認でもAPIアクセスとAnsible実行は行っていない。
- Reviewer定型観点: requirement段階のため多層エスケープとshellのrc規約は対象なし。check modeでは通らない分岐はPOST、PUT、true→false、条件付きfalse→trueであり、AC2/AC3/AC4b/AC12-AC16に現れているが、Finding #1/#2の前提衝突を解く必要がある。有効化や競合の見送りは終了0でも理由をreportへ出すため、無音の例外吸収にはしていない。

## 確認範囲

- 改訂後requirement全文、前回`2026-08-09_005_review_requirement_r4.md`全文、現在のworktree status/diff
- R2/R13/R15-R20とAC1/AC2/AC2b/AC4b/AC10-AC16を、移行/closed-world、rename/new、ansy/quory、明示的有効化許可の状態遷移として突合
- `playbooks/semaphore_templates_setup.yml`の`hosts: quory`と、ansy向けにAPI base URLだけをextra varsで切り替える既存実行形態
- `roles/semaphore_templates/tasks/main.yml`のread/reconcile/report/apply順序とcheck-mode gate
- `docs/ai/context/system/semaphore.md`のansy/quory役割分離、UI状態がGit外で変化し得ること
- duplication/reuseおよびAnsible security観点。対象はrequirementであり実装差分ではないため、実装固有のmodule引数、secretログ、権限、入力サニタイズは未判定
- 着手時と完了時の`git status`およびrequirementのSHA-256。指定成果物以外は変更していない
- 実ホストへのAnsible、Semaphore APIのGET/POST/PUT/DELETE、commit、pushは未実施

## 未確認事項

- OQ1の20/19不一致、OQ3のquory API/SQLite突合は未解決である。
- ansyを恒久不許可と判定する実装方式は未確定である。既存実行形態ではinventory hostでなくAPI base URLが実際の接続先を決める。
- Semaphore APIのtransaction/ETag不存在は本文記載を前提とし、独立確認していない。R20後からPUTまでの競合残余は解消しない。
- `run_at`等の自然変化フィールドがGET完全一致ACへ与える影響は独立確認していない。

## Verdict

Request Changes
