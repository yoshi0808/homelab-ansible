# OQ5(自動起票と月次無人実行の衝突)の決着 — requirement

- 作成: 2026-07-28 Coordinator
- 対象: Step 2(障害の自動捕捉 — ansy側で `claude -p` が第一報を起票)の**着手前に決める設計判断1件**
- 状態: **確定**(Tech Leadへの入力)
- 案件のTier: **Tier 4**。本requirementはその**調査・設計判断フェーズ**であり、実装を含まない

## 1. 問題(観測された事実のみ)

因果は組み立てない。**判断はTech Leadが現物で確かめて行うこと。**

| # | 観測 | 一次記録 |
|---|---|---|
| O1 | Step 1のrequirement §7 が OQ5 を「Step 2でIncidentを自動起票すると作業ツリーが汚れたまま残り、月次Knowledge振り返りの『作業ツリーが汚れているときは中止』と衝突する」としてStep 2へ持ち越した。**Step 1がStep 2へ持ち越した唯一の設計判断**である | `docs/ai/reviews/incident_auto_capture/2026-07-27_001_design_agreement.md`(OQ5の初出と解の方向)、同 `2026-07-27_002_requirement.md` §7 OQ5 |

> **訂正(2026-07-28 Coordinator、Tech Leadの疑義1・2による)**: 初版は O1 を「Step 1が明示的に未解決のまま残した**唯一の事項**」と書いていたが不正確だった。Step 1 requirement §7 は **OQ1を未解決**とし、OQ5は「解決済み(=Step 2へ持ち越すと決めた)」に分類している。また**OQ5の一次記録は設計合意ファイルのほう**であり、初版はそれを参照に挙げていなかった。結論には影響しないが、記録の正確性のため訂正する。
| O2 | 中止判定は `git status --porcelain` の出力が非空かどうかで行う。中止しても `fail` させず、Slack通知で「中止したこと自体」を伝える設計になっている | `roles/knowledge_review/tasks/main.yml`(「Check working tree is clean」以降) |
| O3 | 迂回変数 `knowledge_review_allow_dirty` が存在するが、**timerからは渡らない**(手動デバッグ専用) | `roles/knowledge_review/defaults/main.yml`、`roles/knowledge_review/templates/review-prompt.md.j2` |
| O4 | 月次振り返り**自身も書込のみでcommitしない**。差分は作業ツリーに残り、commitはYoshinobuが行う | 同 `review-prompt.md.j2` |
| O5 | 中止理由の文言が「**先月分の昇格結果が未commitの場合もここで止まる**」と、正常運用でも中止が起きうることを前提にしている | `roles/knowledge_review/tasks/main.yml` |
| O6 | Step 1の実測で、本番quoryのバンドルは41件、うち**約46〜49%がpve1平日シャットダウン由来**。捕捉は平日ほぼ毎日発生している | `docs/ai/reviews/incident_auto_capture/2026-07-28_031_production_status_check.md` |
| O7 | **2026-07-28時点で、ansyの作業ツリーには未commitの変更が実在する**(Coordinatorが直前の案件で書いた2ファイル)。中止条件に当たる状態は、Step 2の有無と無関係に日常的に発生している | `git status --porcelain` |

## 2. ゴール

**OQ5に決着をつけ、ADRとして残す。** Step 2のrequirementがそれを前提として書ける状態にする。

## 3. 非ゴール

- Step 2本体の設計(起票の粒度、重複排除、既知条件の判定基準、`claude -p` の起動契機と頻度、権限プロファイル)
- **quory→ansyのバンドル転送経路の設計**(未設計だが本件とは別の判断)
- あらゆる実装。roleもplaybookも変更しない

## 4. 安全境界(動かせない前提)

- **`docs/ai/core.md`「AIは `git commit`、`git push` を行わない」を、この案件で動かさない。** これを緩める案を検討してよいが、**「Yoshinobuの判断を要する案」として明示的に分離すること**。推奨に含める場合もその旨を書く。安全境界とPolicy本文の改訂はYoshinobuの領域である(`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」)
- 月次振り返りの**中止条件を外す/緩める案も同様に扱う。** 評価にあたっては、その条件が置かれた理由(進行中の変更へ書き込みを混ぜない安全弁。O2・O5)を踏まえること
- **実ホストへ触れない。**ansyの作業ツリーと `git status` の照会までとする。Ansibleを実行しない(`--check` を含む)
- 実行identityはansy上の作業ツリーのみ。**identityを昇格させない**
- `git add` / `git commit` / `git push` を行わない
- harnessの安全機構がブロックしたら、別の形で同じ結果へ到達せず、その事実を報告に含めて返す

## 5. 受入条件(Given/When/Then)

- **AC1**: Given OQ5、When 選択肢を挙げる、Then **3つ以上**を挙げ、各案について次の3点を判定できる — ①月次無人実行が止まらないか ②進行中の人の変更へ自動書き込みが混ざらないか ③**Yoshinobuの判断が要るか**
- **AC2**: Given 選択肢、When 推奨を示す、Then 推奨は1つに絞り、**採らなかった案それぞれについて却下理由**を書く
- **AC3**: Given 根拠として挙げるfile:line・モジュールの挙動、When ADRに書く、Then **すべて現物で確認済み**であること(このリポジトリでは計画の技術的引用が誤っていた前例がある)
- **AC4**: Given 決着、When Step 2のrequirementを書く者が読む、Then **何が確定し、何がStep 2に残るか**が書き分けられている
- **AC5**: Given 成果物、When 配置する、Then `docs/ai/adr/005-<slug>.md` に既存ADRと同じ書式・`**Status:** Proposed` で置く

## 6. 制約

- IPアドレス・VLAN ID・VM IDの実値、および変化の速い値(schedule・時刻・件数の実値)を書かない(`docs/ai/context-classification.md`)。**月次振り返りの期日をこのファイルへ写さない**
- 時刻表記はJST
- 分量は既存ADR(`docs/ai/adr/003` / `004`)と同水準

## 7. 成果物

1. `docs/ai/adr/005-<slug>.md` — 決着本体
2. `docs/ai/reviews/incident_auto_capture_step2/2026-07-28_002_oq5_investigation.md` — 現物確認の記録(何をどう確かめたか)

判断の根拠は成果物ファイルへ書き切ること。最終メッセージは記録として残らない。

## 8. 参照

- `docs/ai/reviews/incident_auto_capture/2026-07-27_002_requirement.md` §7(OQ1〜OQ6と解決状況)
- `docs/ai/adr/003-incident-capture-collector-runtime.md`(Step 1の実行形態。**Step 2への引き継ぎ事項**を末尾に持つ)
- `docs/ai/memory-classification.md`「月次振り返りの対象と手順」
- `skills/incident-recording/SKILL.md`(Incidentファイルの型。捕捉と昇格を分ける2段階)
