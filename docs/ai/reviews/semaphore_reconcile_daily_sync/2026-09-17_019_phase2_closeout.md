# Closeout: Semaphore reconcile Phase 2(日次同期)

日付: 2026-09-17
状態: **クローズ**(独立監査 `_020` = 差戻し → 是正 → `_023` = 条件付き受入 → 指摘4点を反映)
commit: `f0f3558`(決定)/ `331e390`(実装)/ `4aae427` `bb5b9df`(記録)/ `f8c7dcf`(本番不具合の修正)

## 1. 何が変わったか

**カタログとSemaphoreの食い違いを、毎日04:00 JSTに機械が直すようになった。** それまでは日次ドリフト検査が差分を報告するだけで、直すにはYoshinobuが `semaphore_templates_setup` を押す必要があった。

| | 変更前 | 変更後 |
|---|---|---|
| template の差分 | 日次検査が `semaphore_template` として報告 → 人が押して適用 | **04:00のreconcileが適用**。ドリフト検査は `semaphore_template` を出さない |
| schedule の差分 | **検査していなかった** | 同じreconcileが適用(**新規の無人書き込み経路**) |
| 既存scheduleの `active` | — | **canonicalでは書き換えない**(人の停止判断を機械が戻さない)。**非canonicalでは常に `false`** |
| 「同期が効いているか」 | 見る手段が無い | `latest-success` marker の鮮度を日次検査が見る(24時間、`semaphore_reconcile_stale`) |
| 通知 | 差分があるたび | **起きたときだけ**(適用した / 失敗した / 拒否した / orphanが変わった / 金曜に停止がある) |

## 2. 工程

| 工程 | 担当と起動 | 成果物 | 結果 |
|---|---|---|---|
| 計画査読 | **Codex**。`spawn.sh codex reviewer --team homelab --fresh --model gpt-5.6-sol`(Implementerとは別プロセス・別モデル) | `_002` `_007` `_008` `_009` `_010` | **レビュー5本**。blocking は Critical 1 + Major 5(`_002`)/ 7(`_007`)/ 3(`_008`)/ 2(`_009`)= **18件** → `_010` で Approve |
| 実装 | **Codex Implementer**。tmux pane 1 に常駐、`--model gpt-5.6-luna`、agmsg経由で依頼 | `_003` `_012` | Phase 2 は変更18 / 新規5ファイル |
| 差分レビュー | **Claude Code subagent**(`subagent_type: reviewer`、`model: sonnet`)。**実装履歴を継承しないfresh contextで起動** | `_004` `_013` `_014` `_016` `_018` | Phase 2 は**4本**(Critical 1 / Major 1 → 差し戻し → Approve、本番修正で+1) |
| 受入検証 | **Claude Code subagent**(`subagent_type: tester`、`model: sonnet`)。**差分Reviewerとは別のcontext** | `_005` `_011` `_015` `_017` `_022` | Phase 2 は**3回**(Critical 1 = AC18 FAIL → 差し戻し → PASS、監査後の穴埋めで+1) |
| bootstrap | Yoshinobu(quory) | `_019` §3 | #1124(check)→ #1125(apply) |
| 本番不具合 | Yoshinobu が #1126 で検出 | `_018`、commit `f8c7dcf` | 同日修正、#1128 で解消確認 |
| 初回自然発火 | Coordinator(読み取りのみ) | **`_021`** | #1132(2026-09-17 04:00 JST) |
| 独立監査 | **Codex**。`spawn.sh codex auditor --fresh --model gpt-5.6-sol`。**Coordinatorの説明を渡していない** | `_020` | **差戻し** → 本書 §6 で対応 |

**集計の訂正**: 本書の初版は計画査読を「4往復・17件」、差分レビューを「3回」と書いていた。**正しくは査読5本・18件、差分レビュー4本である**(`_002` を数え落とし、本番修正の `_018` を数え落としていた)。**commit `f0f3558` のメッセージにも同じ誤った数が入っている** — メッセージは後から直せないため、ここに訂正を残す。

**実行して初めて出た欠陥が3件ある。** ①合算上限の判定が、実際に書き込む件数からずれていた(差分レビュー) ②カタログが書くenvironmentキーを、同じモジュールのpreflightが拒否していた(受入検証) ③鮮度チェックが、変数の定義されないplayで動いていた(**本番**)。**いずれも読解では出ていない。**

## 3. 本番で観測できたこと

| 観測 | ジョブ | 結果 |
|---|---|---|
| bootstrap(check) | #1124 | `schedule新規1件 / template変更0`、**check modeでmarkerを更新しない**(3タスクともskip) |
| bootstrap(apply) | #1125 | `schedule id=26` 作成。**5フィールドすべて期待どおり**(`cron 0 4 * * *` / `active true` / `template_id=37` / environment2値 / **`params.dry_run` 無し**) |
| 冪等性 | #1127 | template 57・schedule 25 **すべて無変更**、**通知なし**、marker publish |
| ドリフト検査 | #1128 | **drift 0件・通知なし**。鮮度チェック4タスクがquoryで実行され findingゼロ(他5ホストはprobe対象外でskip) |
| **scheduleの自然発火** | **#1132(2026-09-17 04:00 JST)** | **`user_id: None`(人が押していない)/ `params: None`(apply)**。全件無変更、`failed=0`、run reportとmarkerを原子的publish、**通知なし** |

## 4. 残ったこと

- **AC9系(canonical側で既存の `active` を保持すること)は実機未確認である。** Testerはquoryへ到達できず(EXEC-052)、fixtureでの確認に留まる。**実地で確かめられるのは、土曜のProxmox full patchを止めた週が来たときである。** 止めた翌日の04:00が戻さないことを、そのとき確認する。
- **1件の書き間違いは、この機構では止まらない。** 更新上限(4件)が守るのは「機械が壊れてwrite-setが膨らむ場合」であり、正しい件数の誤った値はcommitのレビューだけが防ぐ(P0-7に明記)。
- **Semaphore service・scheduler・quory自体が止まった場合、この機構は検出しない。** 監視する側(00:40のドリフト検査)も同じschedulerから起動されるため。**Phase 2が持ち込んだ欠陥ではなく、既存の日次ジョブすべてに等しくかかる条件である**(P0-13)。
- **`ansible-lint --profile min` はリポジトリ全体では通らない。** `common_slack` への相対path解決に伴う既存のload-failureが14件あり、**本案件の差分を外しても同じ失敗が再現する**(差分Reviewerが `git stash` で確認)。本案件の対象ファイルは production profile 相当で0 failure。
- **開発機(ansy)から本番Slackへ出る経路は、本案件の外で2つ塞いだ** — schedule 24本の非活性化と、Semaphore組み込みアラートの無効化。記録は `docs/ai/memory/incidents/2026-09-16_dev-semaphore-schedules-armed-by-a-phase1-test.md`。

## 5. 付随して変えたもの

- **Notion「バッチ処理工程管理表」**へ04:00の行を追加した(毎日の表、03:30と05:30の間)。
- **requirementの誤りを1件訂正した** — ansy側のbootstrap templateは `id=62`(`id=81` は `Semaphore db backup` だった)。

## 6. 独立監査(`_020`)への対応

Auditorは**差戻し**とし、8点を挙げた。**5点を完全に是正し、3点(AC9系 / AC10 / AC13)は未充足のケースを記録して判断した。** **再監査(`_023`)は条件付き受入**で、さらに4点の記録訂正を求めた。それも本節へ反映済みである。

| 指摘 | 対応 |
|---|---|
| #1132の初回自然発火が本書の地の文にしかない | **`_021` として観測成果物を作成**(`user_id: None` / `params: None` / diff summary / publish順 / 通知なしの実測値) |
| AC10の実測が無い | **`_022` で実測した。** 「金曜以外は停止があっても一覧を出さない」は**実機PASS**(木曜・停止25件)。曜日判定ロジックは production module を直接importして7パターン確認しPASS |
| AC13の残り5ケース | **`_022` で3ケース実機PASS**(全成功・変更なし / run report保存失敗 / **template途中失敗**は真の部分適用 `status=partial`・`writes_applied=2` を再現)。**Slack送信失敗もPASS**(閉ポートへの実POST失敗、rc不変)。**「evidence生成失敗」は未確認**(下表) |
| AC14の残り | **`_022` で実機PASS。** token読取不能とAPI到達不能(閉ポート)の両方を実行し、**tokenの値が console / run report / 資源別レポートのいずれにも無いことを grep で確認(0件)。接続失敗の詳細はscrub済み診断として出力され、Authorization値とAPI応答本文は露出しない。**(初版は「生の失敗文もgrep 0件」と書いていたが、`_022` の実測範囲はここまでである) |
| AC17の `semaphore_probe_error` 分岐 | **`_022` で実機PASS。** 接続断を作り、当該findingが出ること、`semaphore_template` が出ないこと、`checked_counts.semaphore_templates` がキーごと残ること(値0)を実測 |
| 査読回数・差分レビュー回数の集計誤り | **§2 で訂正**(査読5本18件、差分レビュー4本)。commitメッセージの同じ誤りもそこに明記 |
| 工程の独立性がrepoから再構成できない | **§2 の表へ起動方法・モデル・contextの独立性を明記** |
| `status.md` が本書と食い違う / Next表にPhase 1で解消した欠陥が残る | **`status.md` を更新。** Next表の `false` / `{}` の畳み込みの行は、**2026-09-17に現物で解消を確認**(`filter_plugins/semaphore_templates.py` に該当パターンのヒット0)し、解消済みとして印を付けた |

### Coordinatorの判断(未充足を受容するもの)

**次の3点は実測できていない。実測しないまま閉じる判断と、その理由を残す。**

| 未充足 | 理由 | 扱い |
|---|---|---|
| **AC9 / AC9a / AC9b**(canonical側で既存の `active` を保持すること) | **Testerはquoryへ到達できない**(EXEC-052)。ansyは非canonicalであり、そこでの挙動は逆(常に `false` を書く)なので代替にならない | **fixtureでの確認をもって受容する。** 実地で確かめられるのは**土曜のProxmox full patchを止めた週**が来たときであり、そのとき翌日04:00が戻さないことを確認する |
| **AC10のうち「金曜・停止あり」「金曜・停止0件」** | `schedules_friday.yml` は曜日を実行時に固定する手段を持たず、`-e` での注入は reserved-name guard が拒否する(`_022` で実測) | **2026-09-18(金)の #1143 で「停止0件」は本番PASS。「停止あり」は停止中のscheduleが無く条件が発生せず、期限を置かない申し送りへ移した**(`_024`) |
| **AC13の「evidence生成失敗」** | `_022` が確認したのは **capture taskが構造的にskipされたこと**であり、**能動的に失敗させてはいない**(ansyに収集器の設定ファイルが無いため)。**skipは生成失敗ではない** | **受容する。** `common_slack` がevidence capture失敗とSlack送信失敗をそれぞれ吸収し、include到達・evidence生成・配送成功が別々の観測であることは計画査読が現物で確認している(`_007`「確認済み事項」)。**実測は未実施**であり、注入手段を作る手間に見合わないと判断した |
| **AC13の「schedule途中失敗」** | schedule側のpreflight(①〜⑦ + readset preflight)が、name空・cron不正・template未解決・DLPアローリストをすべて事前に拒否するため、**「preflightを通り、APIが拒否する」入力を安全に構成できなかった**(`_022`) | **受容する。** これは欠陥ではなく**preflightが堅牢であることの証跡**であり、同じ経路の部分適用は template 側で実測済み(`status=partial`) |

**このうち期限があるのはAC10だけで、2026-09-18(金)に観測する。** 残る3つは条件が揃ったときに確認する申し送りとする。

### 再監査(`_023`)が求めた4点

1. **AC13「evidence生成失敗」を未充足として扱う** — 上表へ追加し、`_022` の集約も訂正した(同ファイル末尾のCoordinator訂正)
2. **是正件数の数え方を揃える** — 「**5指摘を完全是正、3指摘は未充足を記録して判断**」で `_019` と `status.md` を統一した
3. **AC14の記述を実測範囲どおりに直す** — 上表のとおり訂正した
4. **完了したNext行を消す** — `status.md` のNext表から当該行を削除した(打消し線で残さない。statusの規律は「完了したら消す」)
