# Incident: proxmox_patch_dryrun単一ノード対応で、実バグ4件を工程内で検出・修正した

日付: 2026-07-26
状態: 解決済み
対象: `roles/proxmox_patch_dryrun`、`playbooks/proxmox_patch_weekly_full.yml`(既存・無変更だが相互作用)、`docs/ai/policies/proxmox_patch_policy.md`(SB-094)
種別: 未遂
原因分類: #製造ミス #テスト不足 #要件定義ミス

## 症状

pve1の夏季平日シャットダウン運用中も日次dry-runを継続できるようにする単一ノード対応(P0)で、Tier 4フルサイクル(Tech Lead / Implementer / Reviewer / Tester をすべてsubagentで実施)を回した結果、**本番影響が出る前に4件の実バグを検出・修正した**。

| # | 欠陥 | 検出者 | 影響 |
|---|---|---|---|
| 1 | `_node_reachability_note`のNone化クラッシュ | Tester(実ホスト実行) | **両ノードが健全なあらゆる通常実行で発生**。Statusの内容に関わらず毎回クラッシュするため、日次スケジュール実行が全面停止する。AC2(fixed-pair回帰なし)を実測レベルで破っていた |
| 2 | apply gateの非対称性(`_dryrun_missing_nodes`不在) | Reviewer(decoy実証) | AC5「単一ノードdry-runの`PATCH_READY`はapply gateを満たさない」という不変条件が、reportにもfactにもマーカーを持たず、`run_once`+`delegate_to: localhost`のfact伝播というAnsible内部挙動に依存していた。単一ノードの`PATCH_READY`がweekly_fullのgateを通過しうる |
| 3 | 到達不能とhealthcheck失敗を区別しない通知文言 | Reviewer(decoy実証) | healthcheck失敗(ZFS縮退・quorum喪失等の実障害)も一律「意図しない通信断」と表示され、**実障害を通信の問題と誤読させる**。対応の優先度判断を誤らせる |
| 4 | 終了コード`4`(`RUN_UNREACHABLE_HOSTS`) | Tester(実ホスト実行) | play自体は完走するがrc=4のため、**Semaphoreが毎営業日ジョブを失敗表示する**。赤が常態化すれば本物の障害と区別できなくなり、「pve1停止中も日次dry-runを継続する」という機能の目的が実質未達だった |

## 原因

**#1(製造ミス + テスト不足)**: 静的テキストを持たないJinjaのelse分岐がAnsible templarでNoneになり、`| length`でクラッシュした。decoy検証を行っていたが、**目視でテンプレート出力を見るだけでフィルタまで通していなかった**ため、None と空文字列の差を見逃した。実ホスト実行で初めて顕在化。

**#2(要件定義ミス)**: AC5は不変条件を**文言としては**定義していたが、それを機械的に検証する手段(ノード数マーカー)を要求していなかった。実装はAnsibleの副次的挙動に依存した状態で「充足」に見えていた。なおReviewerは初回レビューで「先頭host脱落方向のみ脆弱」と記述したが、再検証で**両方向とも脆弱**と自己訂正している(`run_once`で設定したfactは既に失敗したhostのhostvarsにも伝播する)。

**#3(要件定義ミス)**: `SB-094`が単一ノードdry-runの発生理由を「通信断」「`--limit`」の2経路しか想定しておらず、**healthcheck失敗による片方除外という3つ目の経路**がPolicy文面から欠落していた。実装はその経路を通るため、文言と実挙動が乖離した。

**#4(要件定義ミス)**: 受入条件が「playbookはエラー終了せず」とだけ書かれ、**その成否を運用上どこで観測するのか**(プロセスの終了コードか、タスク失敗数か、スケジューラのジョブ色か)を定義していなかった。機能の意味で読めばPASS、終了コードの意味で読めばFAIL。この曖昧さが、実装→レビュー→実ホスト検証を1周した後にもう1サイクルを要した直接の原因。

## 修正内容

- #1: Jinja分岐に静的テキストを与えNone化を解消。Implementerが修正、Reviewerがdecoy end-to-endで解消確認、Testerが実ホスト(両ノード健全)で再検証しAC2をPASSへ更新
- #2: `_dryrun_missing_nodes`を導入し、単一ノード結果でgateが確実にfailすることをdecoyの両方向シナリオで実証
- #3: 原因を断定しない文言へ変更(「到達不能または健全性チェック失敗のため今回の結果に含まれません」)
- #4: `ignore_unreachable: true` + play冒頭3タスクでrc=`0`化。pve1停止継続中の実ホスト再検証でrc=0を実測し、機能面の劣化がないことをタイムスタンプ正規化後の`diff`で機械確認

記録: `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_002〜005`。#4の教訓は`docs/ai/memory/lessons/acceptance-criteria-need-observable-success.md`へ、#1の検証手法は`docs/ai/memory/lessons/verify-through-the-consuming-filter.md`へ昇格済み。

## 確認方法

- AC1: pve1手動シャットダウン中の実ホスト実行で、play中断なし・pve2単独のStatus/report/通知生成・rc=0 を実測(2026-07-26 16:42 JST)
- AC2: 両ノード健全の実ホスト実行で完走、通知文言が修正前と完全一致することを確認
- AC3: `--limit pve2`をpve1稼働中・停止中の両方で計3回実行し完走を確認
- AC5: decoyで両方向(先頭host脱落・2番目host脱落)を再現し、いずれもgateがnon-zero終了することを確認
- Reviewer最終Verdict: Approve

## 備考: この記録が2026-07-27に遡って作成された理由

当時のIncident記録ルールは「修正して正常動作の確認が取れた時点で1回記録する」であり、**本番影響が出ずに工程内で解決した事象は起票対象と解釈されなかった**ため、当日は起票していない。2026-07-27に`種別: 未遂`が新設された際、この案件が定義に合致するとして遡及作成した。

作成にあたり、Coordinatorのauto-memory(`project_proxmox_patch_dryrun_single_node_status`)は検出バグを**「2件」と記録していたが、`docs/ai/reviews/`の一次記録では4件**であることが判明した。要約が件数を落としていたため、本ファイルは一次記録に基づいて作成している。
