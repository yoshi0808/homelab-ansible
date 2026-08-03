# 調査: ACPI shutdown の `ignore_errors` 非対称は欠陥か

日付: 2026-08-03 (JST)
起票: `docs/ai/reviews/dev_prod_boundary/2026-08-02_003_implement_phase1_repo.md` §2.9(`sandbox` 検証の副産物)
状態: **クローズ。欠陥ではない。**

## 1. 何が疑われていたか

`roles/recovery_vm_reboot/tasks/main.yml` の Phase 2 は、2つの shutdown 手段でエラー時の扱いが非対称である。

| タスク | `ignore_errors` |
|---|---|
| L84 guest agent shutdown(authy / monnie) | あり |
| L95 ACPI shutdown(sophos-fw ほか) | **なし** |

§2.9 の予測は「**ACPI shutdown がタイムアウトではなくエラーを返すと play がそこで落ち、L136 の強制電源断フォールバックへ到達しない**」であった。`sophos-fw` は guest agent を持たず ACPI 一択であり、VM が locked(バックアップ・マイグレーション中)や paused のときに該当しうる、とした。

§2.9 は**欠陥と断定せず**、「locked 中に強制停止を撃つより失敗して人間へ上げるほうが正しい場面もある」として、判断の要る非対称として `docs/ai/status.md` の Next へ送っていた。

## 2. 検証の制約 — なぜ Tester へ出せなかったか

**Coordinator も Tester も実行できない。** 2つの独立した理由がある。

1. **能力が無い。** Phase 4 以降、ansy は pve1 / pve2 への認証情報を1つも持たない。届くのは read 専用の forced command dispatch のみで、そこに `pvesh create` の語彙は無い(カタログ不変条件 I-1)。
2. **規範でも禁じられている。** `docs/ai/roles/tester.md` L36「`check-mode-native` を `--check` なしで実行しない」。`recovery_vm_reboot.yml` は `check-mode-native` であり、当該タスクは `when: not ansible_check_mode` に守られているため、`--check` では狙った経路を通れない。

**したがって測定は Yoshinobu が pve2 上で直接行った**(2026-08-03)。Coordinator はコマンド列を用意し、結果を受け取って解釈した。

## 3. 測定結果

対象は `sandbox`(使い捨て検証用VM、pve2 上)。**VM ID は本リポジトリへ記載しない。**

| # | 状態 | 実行 | 出力 | `rc` | VMの実際 |
|---|---|---|---|---|---|
| 1 | `--lock backup` | `pvesh create .../status/shutdown` | `VM is locked (backup)` + UPID | **0** | 停止せず(pid 据え置き、uptime 継続) |
| 2 | `--lock backup` | `pvesh create .../status/stop` | `VM is locked (backup)` + UPID | **0** | 停止せず |
| 3 | stopped | `pvesh create .../status/shutdown` | `VM <vmid> not running` + UPID | **0** | 変化なし |

**3件とも `rc=0`。** 拒否のメッセージは標準出力に出るが、終了コードには載らない。

## 4. 結論 — §2.9 の予測は成立しない

**前提が満たされない。** `pvesh create` は非同期タスクを作る API であり、**要求が受理されれば UPID を返して `rc=0` で戻る。** 拒否は非同期タスク側の失敗として現れ、`pvesh` の終了コードには現れない。

したがって「ACPI shutdown がエラーを返して play が落ちる」という経路は、**VMの状態に起因する拒否では踏めない。** L84 / L95 の `ignore_errors` の非対称はコード上に残るが、到達可能な失敗様式を持たない。

### ロックされた VM に対して実際に起きること

1. ACPI shutdown 発行 → `rc=0`、何も起きない
2. 停止待ち(L108)→ `ignore_errors: true` があるので落ちず、`_rvr_vm_stopped = false`
3. 強制電源断(L136)→ `rc=0`、何も起きない
4. **強制停止後の停止待ち(L149)→ `ignore_errors` が無い。** 12回×5秒で `until` を満たせず**タスク失敗 → play 失敗**

role 全体が `always` 付きブロック(L15)なので、**失敗しても report が保存され Slack 通知が飛ぶ**(L200 で失敗詳細を捕捉、L206 で再送出)。

**タイムアウトを消化したうえで大声で失敗する。** 黙って成功したことにはならない。ロック中(バックアップ・マイグレーション中)の VM に強制電源断を撃たず人間へ上げる挙動であり、§2.9 が「そちらが正しい設計でもありうる」と述べていた側そのものである。**修正は不要。**

## 5. 波及 — `pvesh create` の rc に依存している箇所は無い

repo 内の `pvesh create` 呼び出しは2箇所で、**どちらも rc を成功判定に使っていない。**

| 箇所 | 判定方法 |
|---|---|
| `roles/recovery_vm_reboot/tasks/main.yml` L87 / L97 / L138 / L170 | `pvesh get /cluster/resources` を `until` でポーリングし、**実状態**で判定 |
| `roles/recovery_probe/files/recovery-probe.py:339` | 戻り値を `wait_for_recovery()`(実プローブ)と **AND** している。偽の `True` は else 分岐へ落ち critical エスカレーションになる |

**既に正しい形になっており、今回の測定はそれを裏づけた。** この不変条件を将来壊さないよう、**環境事実として `docs/ai/context/system/proxmox.md` へ明記した**(「`pvesh create` の終了コードは、要求の受理であって実行の成功ではない」)。

## 6. 未測定として残すもの

- **paused(`qm suspend`)状態は測っていない。** locked と stopped の2状態で一貫して `rc=0` であり、拒否が非同期タスク側で起きるという機構が判明したため、追加測定の必要が無いと判断した。**機構からの推論であり、実測ではない。**
- `pvesh create` が VM の状態**以外**の理由(ノード到達不能、VM 不在、権限)で非ゼロを返すかは対象外。いずれも §2.9 が想定した状況ではなく、また前段のタスクが先に失敗する。

## 7. 副産物 — 空振りの取り違えが1回起きた

後始末の確認に `grep -E "^\| (status|lock)"` を使わせたが、`pvesh` の表出力の形と合わず**何も出力されなかった**。これは「ロックが消えた」証拠にならないのに、そう読める形で返っていた。素の出力を見て確認し直した。

**同じセッション中に同型の取り違えが3回起きている**(①`journal-system` が `-p warning..err` で絞っていて空だった ②掃引 grep を存在しないディレクトリで実行して0件だった ③本件)。いずれも `docs/ai/memory/lessons/distinguish-nothing-found-from-not-run.md` の範疇である。**検査の出力が空のとき、それが「無い」なのか「見ていない」なのかを、出力の形そのものから判定できるようにしておくこと。**
