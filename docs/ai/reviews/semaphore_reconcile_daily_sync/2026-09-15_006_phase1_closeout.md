# Phase 1 Closeout: reconcileを信用できるものにする

日付: 2026-09-15
状態: Phase 1 完了(Phase 2 は未着手)

## 到達点

異常なread-setで書かずに止まること、比較がフィールドごとの正規形で行われることを実装した。**日次化と独立に、今日の手動applyにも効く。**

工程は requirement(`_001`)→ **計画査読(`_002`)**→ 実装(`_003`)→ 差分レビュー(`_004`)→ テスト(`_005`)。**差し戻しは4回。**

| 工程 | 検出 |
|---|---|
| 計画査読(Codex) | **Critical 1**(空/部分応答で全件newになり、日次applyが重複作成と多重登録へ進む)+ Major 5 |
| 差分レビュー(1回目) | **Critical 2**(preflightが正当なorphanと `arguments: false` を致命的エラーにする) |
| テスト(1回目) | **同じCriticalを独立に検出**。さらに影響範囲を確定(markerless行はansyにもquoryにも恒久的に存在し、`--check` すら通らなくなる) |
| 差分レビュー(2回目) | **Major 1**(直し方が穴を開け直した — markerを失った行が黙ってorphan扱いになり重複を作る) |
| テスト(2回目) | **Critical 1**(並べ替えが既存の汚染検出ガードと衝突し、schedule側が100%停止) |
| 差分レビュー(最終) | **Approve**。残りは非blockingのSuggestion 1件 |
| テスト(最終) | AC1〜AC8 / AC1a / AC5a すべてPASS |

## 判断したこと

**汚染検出ガードは「許可リストを広げる」のではなく「順序を変える」形で解いた。** `schedules_validate_config.yml` を resolve 直後へ移し、このroleが `semaphore_schedules_*` を設定するどの地点よりも先に走らせた。許可リストは元の5件のまま。**広げていれば、外部からの事前定義を検出する力がその分落ちていた。** 変更後もガードが汚染を拒否することは、Testerが `-e semaphore_schedules_observed='[]'` で実測している。

**lost-marker は `name` の衝突で止める。** markerを失った行と手作りの重複は原理的に区別できないため、**判定不能として止める**(`docs/ai/core.md`)。静かに重複を作るより、うるさく止まる方を選んだ。

## 残る弱点(非blocking)

- **lost-marker 判定は `name` だけを見る。** `name` も壊れた応答は捕まらない(他に手がかりが無いための限界)。また、**カタログの命名規則にたまたま一致する手作りtemplate**を置くと恒久的に止まる — うるさく止まる方向なので実害は小さい。
- 検査ロジックが `semaphore_templates_preflight` / `semaphore_schedules_preflight` / `readset_preflight` の3箇所に分散している(レビュー Suggestion 1)。**直さない判断** — 今回の差し戻し4回はいずれもこの分散が原因ではなく、統合すると変更範囲が広がる。

## 本番での未確認

**quoryでは一度も走らせていない。** ansyのSemaphoreでの実測(実書き込み・冪等性・中断後の再実行を含む)までが今回の範囲である。**quoryには orphan `id=37` が実在するため、AC1aが本番でも成立することは、次の `semaphore_templates_setup` の check 実行で確かめる。**

## Phase 2

`_001` の Phase 2(日次apply・`active` の分離・金曜の停止一覧・通知・生存確認)は未着手。**requirementを再度計画査読へ回してから着手する。**
