# Code Review: semaphore_schedules_as_code implementation re-review

## Summary

前回の対象finding 7件はすべてclosedと判定した。修正の主要な状態遷移は成立しているが、失敗時レポートを`always:`へ移した制御フローに、token scrubを迂回するHighの新規回帰と、レポート失敗が元エラーを置き換えるMediumの新規回帰があるため、VerdictはRequest Changesとする。

## Finding Status

| Previous finding | Status | Evidence |
|---|---|---|
| Critical 1 | closed | stage 1 desiredをPUT直前GETから再計算し、payload・管理5項目検証・stage2用検証済みstateへ同じ値を渡している。古い`item.after`は書き込みに使われない。 |
| Critical 2 | closed | task入口で認識可能tokenだけをnative boolの別変数へ正規化し、下流参照は`*_bool`へ統一。filterもnon-boolを不許可にする。ローカル実行で文字列`false/false`→`False/bool`、`true/true`→`True/bool`、`bogus`→rc 2を確認した。 |
| High 3 | closed | schedule blockの成功・失敗とも`always:`からreportへ到達し、未定義値はdefaultで扱う。元の指摘である「失敗時に既適用分レポートが全く作られない」経路は解消した。ただし新しい失敗処理の欠陥は下記New Issuesに分離する。 |
| High 4 | closed | token pathのper-target/`~`分岐は撤去され、両対象でroot所有0600の同一絶対pathを使うコードへ戻った。環境配置はCoordinator disposition §2の完了記録を確認した。Reviewer権限境界により実ホストの所有者/modeは再観測していない。 |
| High 5 | closed | Coordinator disposition §3に異議なし。R10はtemplateを先に適用する二段階を入力側の制約として明記しており、その制約違反をcheckでfail-closedにする現実装は要件と整合する。 |
| High 6 | closed | `semaphore_schedules_nonmanaged_diff()`が管理5項目以外のキー和集合を厳密比較し、stage1/stage2双方のPUT直前・直後GETへ配線された。追加・欠落・値/型差の単体テストもある。 |
| High 7 | closed | `task_params`はtop-level・nested key・値型のallowlistへ変更され、未知形を拒否し、findingへ候補値を含めない。実測4形状とnegative casesがテストされている。 |

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `roles/semaphore_templates/tasks/main.yml` | 98 | **新しいschedule側rescueが外側のtoken scrubより先に元エラーを再送出し、`always:`のレポートもその未scrubbedメッセージをmode 0644で保存する。** line 99-104の`ansible.builtin.fail`は`ansible_failed_result.msg`をそのまま表示するため、`no_log: true`のURI失敗結果にAuthorization値が含まれる最悪ケースでは、この時点でコンソールへ露出する。さらに`schedules_report.yml:50-54,140-142`は再送出後のmessageを`failed_msg`へ入れる。外側の既存scrub(line 112以降)はその後なので間に合わない。ローカルnested block decoyでも、original messageのsentinelがinner rescueのfail出力と`always:`から見える`ansible_failed_result.msg`の双方へ残ることを確認した。inner rescueでtokenをno-logのfactへscrubしてから、コンソール再送出とreportの双方がscrub済み値だけを使う必要がある。 | High |
| 2 | `roles/semaphore_templates/tasks/main.yml` | 108 | **`always:`内のレポート保存が失敗すると、元のschedule失敗がreport失敗へ置き換わる。** 現構造はinner rescueが元失敗を再送出した後に`always:`を実行する。ローカルdecoyで、original failure→rescueのforward failure→alwaysのreport failureとした場合、外側rescueから見える`ansible_failed_task/result`はreport failureだけになることを確認した。ディスク容量・権限・copy失敗時に、部分適用を生んだ本来の原因と既適用outcomeが外側の診断から失われる。元のscrub済みfailureを専用factへ固定し、report failureが起きても元failureとreport failureの両方を保持して非ゼロにする必要がある。 | Medium |

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `scripts/tests/semaphore_schedules/` | 1 | nested rescue/alwaysを実際に通し、(a)失敗message中のsentinelがコンソール/JSONへ残らない、(b)report write失敗時もoriginal failureとreport failureの双方が観測できる、をassertするtask層テストを追加する。現行92テストはfilter単体で、この新しい制御フローを通らない。 | Security / test gap |

## What Looks Good

- PUT直前GETからのstage 1 desired再計算は、stage 1で`false -> true`を起こさず、成功後にstage2 precheck用stateも更新する構成になっている。
- raw flagから`*_bool`への別名正規化はextra-vars優先順位を踏まえており、生の2変数を下流で使う箇所は残っていない。filter側の型検査と二重化されている。
- 非管理フィールド比較は管理5項目の検証と責務を分け、stage1/stage2の双方で書き込み直後にfail-closedする。
- `task_params`のallowlistは提示された実測事実(environment内は文字列、params内はnative型)と整合し、未知値を成功側へ倒さない。
- High 5の扱いはR10の明記された運用制約を維持しており、実装側へ別の仮想template-id経路を増やしていない。
- 定型観点: Jinja/extra-varsの多層評価は`*_bool`へ正規化されている。shell/command追加はなくrc規約の新規論点は無い。check-modeのwrite gateは維持されている。例外経路では成功への吸収は無いが、未scrubbed再送出とfailure置換をNew Issues #1/#2とした。

確認実績:

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/tests/semaphore_schedules/run-tests.py` — 92 tests, OK
- `ansible-playbook playbooks/semaphore_templates_setup.yml --syntax-check` — 既定/`semaphore_target=ansy`とも成功
- `/tmp`のlocalhost decoyでflag正規化3ケースとnested `block/rescue/always`の失敗変数伝播を確認
- 実ホスト、Semaphore API、Slackには未到達。POST/PUTは未実施

未確認事項はCoordinator disposition §4のとおりであり、cron grammar、新規POST契約、AC1〜AC23のtask層integration、実API round-trip、OQ1/OQ3/OQ5/OQ8が残る。

## Verdict

Request Changes
