# Progress: Slack/Codex から Loki 横断ログを調査できるようにする

状態: **クローズ済み**(2026-07-29、Auditor 3回目の条件付き受入を満たして終了。`2026-07-29_012_audit_3.md`)。Tier 4(軸A=4 / 軸B は Tier 3/4 のため `+R` なし)。

**このファイルは走行中に書かれていない。** Auditor 起動直前に、会話とrepoの成果物から遡って作成した。詳細は「課題・計画外事象」の C-1。

## 発端

2026-07-29 06:07 JST の「外部到達性の回復」warning(recovery-probe)を Yoshinobu が受け、「monnie の Loki を Slack から Codex に調べさせたい」という要求として持ち込まれた。**当初の相談論点は「前後5分のログ量に Codex が耐えられるか / quory の `/tmp` へ落としてから grep すべきか」**であり、Coordinator は「Loki のサーバサイドフィルタで完結させる、`/tmp` ステージングは採らない」を推奨して合意された(理由: ①Lokiが既に持つ機能の再実装になる ②grep用wrapperが自由regexという最も危険な引数面を新設する ③`recovery-io.service` は `PrivateTmp=yes` なので人が後から読めない)。

## 調査段階(Tier 4 の1段目)

`2026-07-29_001_measurement.md`(Tester、51 tool_uses)。read-only の Loki 問い合わせ。

設計の入力として得た実測: 全job合計 70行/分、job絞りで 2.5〜24行/分、`network-devices` の2 hostに **level ラベルが付かない行が343行/15分**、retention は `retention_enabled: false` で自動削除なし。

**副産物として、06:07 の warning が外部断ではないことが判明した** — quory の `apt-daily-upgrade` 直後の systemd daemon-reexec で `recovery-probe.service` が再起動し、再起動直後1サイクル目の HEAD 失敗がそのまま「断→回復」通知になっていた。この時点で Yoshinobu 判断により、probe 側の誤検知修正は**別案件として起票**(`docs/ai/status.md` Next)。

## ゲート適用(Coordinator)

計画査読(`2026-07-29_003_plan_review.md`)で層1 PASS、層2 findings 4件(Blocker 1 / Major 1 / Informational 2)。Blocker(AR番号衝突)と Major(変更履歴の番号表記)を requirement 側で是正してから承認した。

**ゲートの確認項目を明示的に文書化せず、承認だけを宣言した**(C-2 参照)。事後に整理すると次のとおり。

| # | 確認 | 結果 |
|---|---|---|
| 1 | 並行して立てる単位の組 | 並行なし。Implementer → Reviewer → Tester を逐次 |
| 2 | 単位間のファイル競合 | 該当なし(逐次のため) |
| 3 | 査読層1(未決定の数) | 単位1=0件、単位2=1件。基準内 |
| 4 | 査読層2(技術的前提の反証) | 実施済み。Blocker 1件を実装前に検出・是正 |
| 5 | Yoshinobu の commit/push が工程上の待ちか | **待ちである**。Policy 改訂を含み、かつ配備(`recovery_exec_setup.yml`)が commit 済みコードを前提とするため、実機ACはcommit前に検証できない |

## 単位の状態

| 単位 | 状態 | 実績 | 備考 |
|---|---|---|---|
| 調査(Tester) | 完了 | 51 tool_uses | `001_measurement.md`。AC1〜AC4 充足。06:07 の真因も特定 |
| 計画査読(Reviewer) | 完了 | 33 tool_uses | `003_plan_review.md`。層1 PASS、層2 Blocker 1件検出 |
| 実装(Implementer) | 完了 | 73 tool_uses | `004_implement.md`。**単位1と単位2をまとめて1 subagentへ委任**(C-3 参照) |
| 差分レビュー(Reviewer) | 完了 | 35 tool_uses | `005_review.md`。Critical 0 / Approve。Suggestion 3件中1件(AR-098文言)を Coordinator が是正 |
| 実機検証(Tester) | 完了 | 38 tool_uses | `006_test_plan.md` / `007_test_result.md`。AC1/2/3/5 PASS、AC7 到達不能(Yoshinobu へ移譲) |
| AC7(Yoshinobu 手動) | 完了 | — | Slack から2回。1回目は誤結論、2回目で PASS(**C-5** 参照)。一次証跡は `010_ac7_evidence.md` |
| 追加改修(Coordinator、Tier 2) | 完了 | — | 切り詰め通知へ「読めた範囲」を追加、AGENTS.md へ引き直し指示を追記 |
| 追加改修の検証(Tester) | 完了 | 44 tool_uses | `008_test_result_followup.md`。全項目 PASS |
| Auditor 1回目 | 完了(クローズ不可) | 32 tool_uses | `009_audit.md`。指摘2件(AC7の参照誤り、AC7一次証跡の欠如)。是正済み |
| Auditor 2回目 | 完了(クローズ不可) | 25 tool_uses | `011_audit_2.md`。1回目の是正を確認。新規指摘1件は**事実認定が誤り**(C-7)。ただし記録が両様に読める状態だったことは Coordinator の欠陥 |
| Auditor 3回目 | 完了(条件付きクローズ可) | 20 tool_uses | `012_audit_3.md`。2回目の誤りを `git show` で独立に検出。新規指摘2件はいずれも記帳の遅れ(C-8)。本更新で反映しクローズ |

## 課題・計画外事象

- **C-1(工程逸脱)**: **`progress.md` を走行中に一度も更新しなかった。** Auditor の起動条件が「`progress.md` と番号付き成果物が出揃った時点」であることを、Auditor 起動を検討する段になって初めて確認したため。これは `docs/ai/roles/coordinator.md` が 2026-07-28 の事故(`incident_auto_capture/progress.md` 課題 I-3)を受けて明文化した規律そのものの再発である。**規範は存在し、参照されなかった。** 本ファイルは遡って作成したものであり、走行中の記録ではない。

- **C-2(工程逸脱)**: 計画受領時のゲートについて、承認の宣言はしたが**確認項目を文書化しなかった**。上記「ゲート適用」の表は Auditor 起動前に事後整理したものである。

- **C-3(計画からの逸脱)**: requirement §8 は単位1(Policy/Context)と単位2(実装)に分けていたが、**実装は1 subagent へまとめて委任した**。単位1が逐語指定で未決定0件であり分離の実益が無いと判断したためだが、**この判断でゲートを再適用していない**。結果的に問題は生じていない。

- **C-4(最も重要)**: Coordinator の採番根拠が誤っていた。Policy の `## 7.` だけを読んで `AR-052`〜`AR-058` を空き番号と推測したが、実際は `AR-001`〜`AR-094` が連番で全て使用済みだった。そのまま commit されていれば `AR-055`(monnie の flapping 閾値)等の既存参照が意味的に破壊されていた。**計画査読の層2 が実装前に検出した** — 層2 が本体である、という規範の妥当性を実証した事例。

- **C-5(出荷後に実運用で発覚)**: Tester が AC2 を PASS と判定した後、**Yoshinobu の AC7 実行(1回目)で Codex が誤った結論を出した**。`direction=forward` + 最古N件保持のため、切り詰めで落ちるのは常に**窓の後ろ側**であり、Codex は「05:55–06:10 を見た」つもりで実際には 06:03 頃までしか読めていない状態で「error なし」と報告した。窓の後半に目的の事象があった。
  - **Tester の AC2 検証がこれを検出できなかった理由**: AC2 が「行数が上限を超えないこと」「特定の行が含まれること」を問う形だったため、Tester が選んだ窓ではたまたま事象が最古300行に入っていた。**「上限に当たったとき、要求範囲のどこを読めていないか」を問う受入条件が無かった。**
  - 是正: 切り詰め通知へ「要求した範囲」と「実際に読めた範囲」を併記(221文字、300文字上限内)。AGENTS.md へ「切り詰めが出たら引き直してから結論する」を追記。Tester 再検証で PASS。

- **C-6(副産物、別案件へ)**: AC7 の実行過程で、**global pause が8日間解除されずに自律復旧が全停止していた**ことが発覚した(2026-07-21 18:49 〜 2026-07-29)。Incident 起票済み(`docs/ai/memory/incidents/2026-07-29_global-monitoring-pause-left-on-8-days.md`)。監視は Yoshinobu が再開し、Tester が再開の実効を確認済み。構造的な再発防止(TTL または未解除通知)は `docs/ai/status.md` Next へ起票し、本案件では実施しない。

- **C-7(記録の再構成可能性の欠陥、Auditor 2回目で発覚)**: 差分レビューの Suggestion 1 を受けた **AR-098 の文言是正は、commit 前の作業ツリー上で行われた**。このため `a0945b7` には最初から是正後の文言だけが入っており、**「是正前の状態」と「是正が行われた事実」がgit履歴のどこにも現れない**。

  結果として、repo だけを読む者には `2026-07-29_005_review.md` Suggestion 1 の引用と現行 Policy が食い違って見え、「Reviewer が誤引用した」とも「文言が是正された」とも読める。Auditor 2回目は前者に倒し、**2つの誤った事実認定**を行った(①AR-098は是正されていない ②Reviewerが既存のAR-047の文言をAR-098の引用として誤提示した)。いずれも `git show a0945b7:...` と現行 AR-047 の照合で反証できる。**Auditorの結論は誤りだが、記録が両様に読める状態を作っていたのはCoordinatorであり、検出そのものは妥当である。**

  記録のため、是正の before / after を残す。

  before(Implementer が requirement §9-2 の当時の逐語案どおりに適用したもの。`005_review.md` が引用しているのはこれ):

  ```
  出力量はLokiへのlimit、行数、行長の3点で固定する。parameter検証と出力量制限はdispatchを正本、wrapperをmirrorとする。
  ```

  after(`a0945b7` に入っている現行):

  ```
  出力量はLokiへのquery limit、返す行数、1行の長さの3点で固定し、対象host側で強制する。quory側wrapperへ出力量制限を置かない — logが認可境界を越えた後の切り詰めは防御にならず、二層あるという誤解だけを生む。二層で検証するのはparameterであり、出力量ではない。
  ```

  是正理由: 二層で守れるもの(parameter 検証)と、一層でしか守れないもの(出力量)を1文に混ぜていた。wrapper は Loki 応答を見ないため出力量を mirror しようがなく、元の文言のままでは後任が quory 側に効かない切り詰めを足して「二層ある」と誤認する。requirement §9-2 も同時に更新済み。

- **C-8(監査が自分自身を追い越す構造、3回目で発覚)**: Auditor 3回目の指摘2件は、いずれも「`progress.md` と `docs/ai/status.md` が Auditor の実施回数を反映していない」だった。**この指摘は放置すると無限に再生産される** — 4回目を回せば「3回目が記録されていない」が指摘され、それを直せば「4回目が記録されていない」が続く。監査の実施そのものが記録を古くする。

  **クローズの判断**: 3回目が「この2件を反映すればクローズしてよい」と条件付きで明示したため、反映をもって終了とし、4回目は起動しない。`docs/ai/roles/coordinator.md` が求めるのは「クローズ前に Auditor を1回起動して受入を受ける」ことであり、無条件受入の取得までは求めていない。**この判断はCoordinatorが行った**ものであり、Auditorが下したものではない。

  根本原因は C-1(走行中に `progress.md` を書かない)と同じである。単位完了ごとに書いていれば、監査時点で古くなるのは高々1行である。

## 後続への申し送り

- **受入条件に「上限に当たったときの挙動」を書く場合、上限が発動する前提での正しさだけでなく「発動したことが利用者側からどう見えるか」を問う形にする。** C-5 は、上限そのものは正しく効いていたのに、利用者が誤った結論に至った事例である。
- **`progress.md` は Auditor 起動時ではなく単位完了ごとに書く**(C-1)。規範は既にそう定めている。
- 自由文字列フィルタ(grep 相当)は初版で意図的に非ゴールとした。実運用で必要性が見えたら、`|~` ではなく `|=` の固定文字列 + 厳格な charset で検討する(requirement §11)。
- 切り詰め通知の行そのものには構造的な長さ上限がかかっていない(現在221文字、上限300)。書式を変更する際は長さを再確認すること(`008_test_result_followup.md` の残存リスク)。
