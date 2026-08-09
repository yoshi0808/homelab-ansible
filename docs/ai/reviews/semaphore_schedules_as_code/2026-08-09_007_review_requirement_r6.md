# Code Review: Semaphore schedules as code requirement 6回目査読

## Summary

全面改稿により、rename、フェーズ別の管理外処理、ansyの明示許可テストに関する前稿の文書内矛盾は解消した。一方、本番19件を壊さないための中核であるR8は、schedule PUTの対象版契約を未確認のままraw GET object全体を送り返す設計になっており、server-managedであり得る`run_at`も含む。さらに、移行期間そのものを有効化禁止条件にする要件がR12〜R17から欠落し、ansy保護がdenylist型URL判定でfail-openになり得るため、実装前の修正が必要である。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 73, 126-139, 191-205 | **R8の「GETしたraw objectへcombineし、全フィールドをPUTする」方式は、対象版schedule APIの書き込み契約で裏付けられておらず、既存19件を壊さない保証になっていない。** 公式APIリファレンスのschedule PUT例は `id / cron_format / project_id / template_id / name / active` の6項目で、`run_at / task_params / type / delete_after_run / repository_id`を更新requestの一部として示していない([Semaphore UI API Reference](https://api.semaphoreui.com/))。一方、本文自身がOQ6で`run_at`の自然変化を未確認としている。GET後にSemaphoreが`run_at`を進めた場合、古いraw値をPUTできるAPIならlost updateになり、requestで受け付けないAPIなら更新自体が失敗する。template endpointで同方式が動いた事実はschedule endpointの契約を証明しない。ansy上の対象版で、GET response fieldとPUT request fieldを分離し、各非管理フィールドについて「省略しても保持されるか」「送信可能か」「server-managedか」を実測してpayload allowlistを確定するまで、quory適用へ進めない要件とACが必要である。 | Critical |
| 2 | 同上 | 20-25, 82-86, 92, 176-179 | **移行期間であること自体を`false → true`の禁止条件にするP0要件が無い。** R12は有効化条件をR13〜R16だけとするが、R13は新規作成、R14は管理外の有無、R15は明示許可と接続先、R16は競合だけを扱う。したがって移行期間でも、管理外0件・quory・明示許可・集合不変なら要件本文上は有効化できる。フェーズ表とAC14はそれを禁止しているため、期待結果は読めるが、R12の列挙と実装要件が不一致である。R12またはR17へ「`false → true`はclosed-worldでのみ許可」を明記し、R12の条件参照へ含める必要がある。 | High |
| 3 | 同上 | 85, 181-184 | **「ansyでは常に不許可」をansy URLの否定判定で実現すると、別名・alias・別表記のURLでfail-openになる。** 正規化は末尾slash等の表記差を減らすだけで、同一サーバへ到達する別のDNS名まで同一化しない。AC15も既知のcanonical ansy URLしか試さないため、実装が「URLがansyの既知値でなければ有効化可」としても合格する。本番有効化はdenylistではなく、**正規化済みAPI base URLがcanonical quory URLと完全一致するときだけ許可し、それ以外はすべて不許可**というallowlist型にする。ACは未知URL/別名でもPUT 0、quoryだけが許可される境界を観測する必要がある。 | High |
| 4 | 同上 | 111-119, 126-139, 151-159, 171-205 | **GET応答の完全一致は、API書き込み0を観測する手段として成立するか未確定である。** OQ6のとおり`run_at`がscheduler自身により変化するなら、AC1/AC5/AC9/AC13等はreconcileが無書き込みでも不一致になり得る。一方`run_at`を単に比較から外すと、reconcileがそれを壊しても検出できない。AC4/AC17の非管理フィールド保持も同じ問題を持つ。API request capture等でPOST/PUT/DELETE件数を直接観測し、状態比較は「reconcileが管理または保持責任を持つ安定フィールド」と「server-managedフィールド」に分ける必要がある。OQ6を未解決のままtest_planへ送らず、Finding #1の対象版payload契約と同時に確定する。 | High |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 5 | `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` | 109, 116-119, 141-164, 171-174 | 「各ACにフェーズ・接続先・有効化許可を明記する」という文書内規約をAC2/AC7-AC11/AC13も満たす形にする。失敗が有効化より先に起きるケースでも、preflight順序とfixtureを一意にし、AC単体の前提を推測不要にできる。 | acceptance precision / Medium |

## What Looks Good

- フェーズ表を単一の入口にし、移行中はreport+限定継続、closed-worldではfail-closedと分けたため、前稿の保証境界とR13/AC12の矛盾は解消した。
- renameは全フェーズ非対応で一貫している。移行中はcatalogの未実在名としてR6/AC2が拒否し、closed-worldでは旧名が管理外としてR18/AC13が全書き込み前に拒否する。
- AC15はansy・closed-world・管理外0・明示許可あり・observed false/catalog trueを揃え、単なる既定不許可の実装を通さない点まで改善した。Finding #3は接続先判定のfail-openだけを扱う。
- AC3/AC6は、新規をfalseで作るapply、有効化を見送るapply、明示許可による有効化、その後の冪等を分離している。
- R9とAC7-AC10/AC13は、決定的preflight errorを部分適用前に非ゼロ化する。判定不能を空・成功へ落とす無音化は要求していない。
- R16/AC16はschedule追加競合を再GETで検出し、終了0でも理由をreportへ出す。transaction/ETagが無いという残余を過大保証していない。
- duplication/reuse: 既存playbook、名前解決、report/apply分離、template側のmerge方式を再利用候補として明記している。ただしschedule endpointへの再利用可否はFinding #1のとおり独立確認が要る。
- security: token値の保存・表示、TLS検証弱化、DELETE、shell/commandでの変数展開は要求していない。API base URLによるcapability判定はFinding #3のallowlist化を除けば、既存の接続先切替構造を正しく参照している。
- Reviewer定型観点: requirement段階のため多層エスケープとshell rc規約は対象なし。`--check`で通らない分岐はPOST、PUT、true→false、条件付きfalse→trueでありAC3/AC4/AC6/AC12/AC14-AC17が扱うが、payload契約とフェーズgateを先に確定する必要がある。有効化・競合の見送りは理由をreportへ出すため「該当なし」と「判定不能」を無音で同一化していない。

## 確認範囲

- 全面改稿後requirement全文、前回`2026-08-09_006_review_requirement_r5.md`、着手時のworktree status/diff
- フェーズ表とR2/R6/R12-R18、AC2/AC3/AC6/AC12-AC17を、migration/closed-world、new/rename、managed/unmanaged、ansy/quory、明示許可の状態遷移として照合
- `playbooks/semaphore_templates_setup.yml`の`check-mode-native` marker、`hosts: quory`固定とAPI base URL override
- `roles/semaphore_templates/tasks/main.yml`のread/reconcile/report/apply順序、`roles/semaphore_templates/tasks/apply.yml`のtemplate側get-then-merge-then-send
- `docs/ai/policies/ansible_test_safety_policy.md`のcheck-mode-native要件
- Semaphore UI公式APIリファレンスのschedule PUT request例。対象インスタンスの2.18.4実挙動とは独立に突合できていないため、差異そのものをFinding #1の停止条件とした
- duplication/reuseおよびAnsible security観点。requirement査読のため、未実装schedule taskのmodule引数、secretログ、権限、入力サニタイズは未判定
- 実ホストへのAnsible、Semaphore APIのGET/POST/PUT/DELETE、commit、pushは未実施

## 未確認事項

- OQ1の20/19不一致とOQ3のquory API/SQLite突合は未解決である。
- 対象版schedule PUTが受け付けるfield、省略fieldの保持、`run_at`の更新主体は未確認である。
- Semaphore APIのtransaction/ETagの有無は未確認であり、R16後からPUTまでの競合残余は解消しない。
- API base URLに対して別名・aliasで同一インスタンスへ到達できる実際の経路は探索していない。Finding #3はその有無に依存せずfail-closedにする提案である。

## Verdict

Request Changes
