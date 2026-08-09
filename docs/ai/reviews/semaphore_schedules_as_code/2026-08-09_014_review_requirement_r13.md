# Code Review: Semaphore schedules as code requirement 13回目査読

## Summary

前回分類1の2件は解消した。R8-2/R8-3/R16-2は段階別desired stateと検証値が一致し、`true → false`は第1段階で即時反映される。第2段階直前の管理項目driftも非ゼロ・残り有効化中止へ確定し、AC23がその分岐を識別する。**分類1は0件**であり、requirementを確定して実装へ進めてよい。

## Critical Issues

### 分類1: requirement段階で直す必要があるもの（0件）

なし。

## Suggestions

### 分類2: implementまたはtest_planへ送ってよいもの（6件）

第9節に送り先とともに記載された6件を、後続依頼へ引き継ぐこと。

| # | 引継ぎ先 | 内容 | 判定 |
|---|---|---|---|
| 1 | implement | PUT round-trip、DB構造、19件`task_params`、deep equality、型保持/OQ7 | 後続可 |
| 2 | test_plan | AC15のreachable mockまたはURL判定unit test | 後続可 |
| 3 | test_plan | 結果へ影響しないACの3軸fixture表記統一 | 後続可 |
| 4 | Tester(初回quory) | OQ1の20/19とOQ3のAPI/SQLite突合 | 後続可 |
| 5 | implement | OQ5のtransaction/ETagと残余競合fixture | 後続可 |
| 6 | test_plan | OQ8の孤児行増加・冪等時非増加・cleanup別判断 | 後続可 |

## What Looks Good

- R8-2とR8-3は、第1段階のdesired `active`を「新規false、既存はcatalog falseならfalse、それ以外は観測値」で統一した。第1段階では有効化せず、`true → false`だけを即時に反映できる。
- 第1段階の管理4項目とdesired activeは直後GETで検証され、不一致なら第2段階へ進まない。危険な`task_params`が保存されなかったscheduleを有効化しない順序保証が成立している。
- 第2段階はR12の4条件を再確認し、直前GETで管理4項目が検証済み値のままかつactive falseであることを確認する。PUTはminimal payloadではなく、単一GETをmerge元とする全フィールド送信で、論理差分だけがactiveになる。
- 第2段階直前driftは、当該scheduleを有効化せず、残りの有効化PUTを中止して非ゼロ終了する。AC23は管理項目変更、active false維持、PUT 0件、差分メッセージを観測し、成功終了や無言skipを許さない。
- AC17ケース②は第1段階の即時無効化を、ケース③とAC6は独立した第2段階の有効化とその後の冪等を観測する。AC21はAPIによる値の黙示破棄をHTTP成功と区別する。
- 移行期間は新規作成を拒否し、closed-worldは管理外をpreflightで拒否する。新規scheduleは常にinactiveで作成され、明示許可とcanonical本番URLが揃わない限り有効化されない。
- rename非対応、DELETE禁止、管理外検出、全preflight完了前の書き込み禁止、単一GETを使ったfull round-tripにより、既存19件を段階移行する安全境界が明示されている。
- duplication/reuse: 既存`semaphore_templates` playbookとreportを再利用し、schedule固有の同定・payload・競合契約だけを追加する方針である。
- security: 秘密候補と判定不能のpreflight停止、canonical URL allowlist、token非記録、TLS非弱化、DELETE禁止が維持されている。
- Reviewer定型観点: requirement段階のため多層エスケープとshell rc規約は対象なし。`--check`外のPOST/PUT、段階別write-after-read、有効化、競合分岐はAC群に割り当てられている。判定不能を成功扱いする例外吸収は要求されていない。

## 確認範囲

- 第13稿requirement全文、前回`2026-08-09_013_review_requirement_r12.md`、着手時のworktree status/diff
- R8/R8-2/R8-3/R12/R16/R16-2とAC3/AC6/AC16/AC17/AC21/AC22/AC23の状態遷移・API call順序
- 移行期間/closed-world、新規/既存、catalog active/観測active、許可/不許可、管理項目drift/集合driftの境界
- Semaphore System Context、Ansible test safety policy、既存`semaphore_templates` role/playbook/reportの接続箇所
- duplication/reuseおよびAnsible security観点

## 未確認事項

- Semaphore APIへのGETを含め、API呼出しは行っていない。本文の2.18.4実測値は今回再測定していない。
- Ansibleは実ホスト・decoy・syntax-checkのいずれも実行していない。
- 実装コード、mock方式、deep equality、`task_params` schema、競合注入手段は後続工程の確認対象である。
- 第9節の6件とOQ1/OQ3/OQ5/OQ7/OQ8は、requirementのblocking findingではないが後続工程で未解決である。
- commit、pushは行っていない。

## Verdict

**Approve** — 分類1は0件。requirementを確定し、第9節の6件を明示的に引き継いで実装・test_planへ進めてよい。
