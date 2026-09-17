# 観測: 04:00 scheduleの初回自然発火(AC18の後半)

日付: 2026-09-17
観測者: Coordinator(quoryのSemaphore APIへの読み取りのみ。状態を変えていない)
対象: quory task **#1132**

## 何を確かめたか

AC18のうち、bootstrap後に残っていた「**scheduleが自分で起動し、初回の04:00実行が成立すること**」。前半(schedule作成とAPI readbackによる5フィールドの一致)は `_019` §3 の #1125 で確認済みである。

## 実測

`GET /api/project/1/tasks/1132`

| 項目 | 値 | 意味 |
|---|---|---|
| `created` | `2026-09-16T19:00:00Z` | **2026-09-17 04:00 JST**。カタログの `cron: "0 4 * * *"` と一致 |
| `status` | `success` | |
| **`user_id`** | **`None`** | **人が押していない。** 手動実行の #1124〜#1128 はいずれも `Yoshinobu` が入る |
| **`user_name`** | **`None`** | 同上 |
| **`params`** | **`None`** | native Dry Run が立っていない = **apply として走った** |
| `commit_hash` | `bb5b9df5` | 配備が最新である |

`GET /api/project/1/tasks/1132/output` から:

```
Show the diff summary
  mode           : apply
  新規作成       : 0 件
  変更           : 0 件
  無変更         : 57 件
  定義に無い既存 : 1 件(削除しない — R5)

Show the schedules diff/outcome summary
  mode     : apply
  failed   : False
  phase    : closed-world
  新規作成 : 0 件 (作成=0 件)
  更新     : 0 件 (書込=0 件、 見送り=0 件)
  無変更   : 25 件

Write run report to a unique temporary file              changed
Atomically publish the immutable run report              changed
Write latest-success marker to a temporary file          changed
Atomically publish latest-success marker after its target report exists (P0-8)   changed
```

PLAY RECAP: `quory : ok=73 changed=10 unreachable=0 failed=0 skipped=26`

**通知タスクはincludeへ到達していない**(変更・警告条件・失敗のいずれも無いため。P0-9 / AC12)。Slackにも通知は出ていない。

## 判定

**AC18の後半は成立した。**

- scheduleが**自分で**起動した(`user_id: None`)
- **apply** として走った(`params: None`。`dry_run` が混入していない)
- run report が作られ、**その後に** latest-success marker が publish された(P0-8 の順序、AC13b)
- **変更が無かったため通知が出ていない**(P0-9)

## 併記

同じ夜の日次ドリフト検査 **#1130**(2026-09-17 00:40 JST)も `success` である。これは `f8c7dcf`(鮮度チェックの修正)が入った後、**人が押していない自然実行としては初回**にあたる。
