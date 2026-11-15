# 配備後の観測(AC9)

観測日: 2026-11-15(Coordinator)

## AC9: 翌日のドリフト検査

- 対象ジョブ: quory の Semaphore、`SAFE: Deployment drift check`(template 33)の定期実行 #1859。2026-11-15 00:40 JST 開始、status `success`。実行コミットは `bf14039`(本案件の `4c2e586` / `3212116` を含む)。
- 確認手段: ansy から `ssh quory-investigate semaphore-query task-output 1859`。
- 結果(ジョブの "Show the drift summary" 出力):
  - `drift : 0 件`
  - `checked : quory, ansy, monnie, authy, pve1, pve2`
  - `unverified : (なし)`
- 本案件で対象に加えた配備物(`/usr/local/sbin/homelab-stale-libs` を pve1 / pve2 / authy / monnie、`/usr/local/sbin/recovery-investigate-dispatch-quory.sh` を quory)は、いずれも同ジョブの "Stat deployed files" で読まれている。
- PLAY RECAP は6ホストとも `unreachable=0` / `failed=0`。

判定: **AC9 PASS**(finding なし、対象ホストがすべて `checked`)。

## 受入条件の充足(まとめ)

| AC | 判定 | 記録 |
|---|---|---|
| AC1〜AC7、AC10 | PASS | `2026-11-14_005_test_result.md` |
| AC5a、AC8 | 実装記録・差分査読で確認 | `2026-11-14_003_implementation.md`、`2026-11-14_004_diff_review.md` |
| AC8a | PASS(配備ジョブ #1854 で4台とも、引数なしは rc 0、引数付きは sudo 層で rc 1。#1856 の再配備でも assert 8件通過) | 本節と Coordinator の確認(`semaphore-query task-output 1854` / `1856`) |
| AC9 | PASS | 本ファイル |

配備後の追加修正: 2026-11-14 の初回配備後、pve1 の `stale-libs` が `kvm` の `/dev/zero` を誤検知した。除外を `/dev/` 配下へ広げ(commit `3212116`)、#1856 で再配備した。再配備後の pve1 で `/dev/` 配下の行が0件であることを Coordinator が確認した。
