---
name: requirements-analysis
description: homelab-ansibleのCoordinatorが新規案件の要求を明確化し requirement.md を書くときの構成テンプレート。「要件をまとめる」「requirementを書く」「案件を整理する」場面で使う。
---

# Requirements Analysis(要求整理フォーマット)

出典: `anthropics/knowledge-work-plugins` の `write-spec` スキル(product-management)を参考に、出力構成のみ採用したもの。
https://github.com/anthropics/knowledge-work-plugins/blob/main/product-management/skills/write-spec/SKILL.md
取り込み時点のrevision: commit `2d6f7e22dd25`(2026-03-13)。更新確認はhttps://github.com/anthropics/knowledge-work-plugins/commits/main/product-management/skills/write-spec/SKILL.md で最新commitを確認し、上記revisionと比較する。

## requirement.mdの8セクション構成

1. 問題定義
2. ゴール
3. 非ゴール(現行core.mdの「初回実装で含める範囲／除外する範囲」と同義。名称をPRD標準へ揃えたもの)
4. ユーザーストーリー
5. 要件(P0/P1/P2でMoSCoW優先順位付け: Must/Should/Could/Won't)
6. 成功指標
7. オープンクエスチョン
8. タイムライン考慮

## 受入条件

Given/When/Thenの形式で書く。Testerの`skills/test-strategy/SKILL.md`と接続しやすくするため。

### 「成功」の観測方法まで書く

「エラー終了しない」「正常に完了する」だけでは足りない。**その成否を運用上どこで観測するのか**まで`Then`に含める。書かれていない観測点は検査項目にならず、実行して初めて発覚する。

- **終了コードの期待値**(`0`か、非ゼロならその値と意味)。**スケジューラ(Semaphore / systemd timer)から起動されるplaybookでは必須**。
- 通知が飛ぶのか飛ばないのか、飛ぶなら何チャンネルか。
- 生成される成果物ファイルの有無とパス。
- **部分的な成功(一部ホストのみ処理)を成功とみなすのか失敗とみなすのか。**

異常系のACでも同じで、「明確なメッセージで停止する」と書くなら終了コードも添える。

根拠(2026-07-26、proxmox_patch_dryrun単一ノード対応): AC「playbookはエラー終了せず、pve2のみを対象とするdry-run結果を生成する」は機能要件5点すべてPASSしたが、実ホストの終了コードは`0`ではなく`4`(`RUN_UNREACHABLE_HOSTS`)だった。タスク失敗はゼロで、到達不能なhostが1台あることだけが理由である。Semaphoreは終了コードで成否を判定するため**毎営業日ジョブが赤くなり**、「pve1が停止する平日も日次dry-runを継続する」という目的は実質未達だった。「エラー終了せず」を機能の意味で読めばPASS、終了コードの意味で読めばFAIL——この曖昧さが、実装・レビュー・検証を1周した後にもう1サイクル要した直接の原因である。案件記録: `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_005_test_result.md` §13、`2026-07-26_003_implement.md` §9。

### 撤廃する案件では「配備物側にも残っていないこと」をACへ入れる

識別子・機構・フラグを**やめる**案件では、repoから消えたことをもって完了としない。**`git pull` は配備物を更新しない** — `/usr/local/` や `/etc/systemd/system/` へ置いたscript・unitは、setup playbookを実行して初めて入れ替わる(経路の正本は`docs/ai/context/operations/code-delivery-to-production.md`)。

- ACに「**配備物側にも残っていないこと**」を、確認手段つきで含める。手段はdispatchの`deployed-hash`(repo側の期待値と突き合わせられる場合)か、日次ドリフト検査の対象に入っているか。
- **どのsetup playbookの実行が要るか**を成果物に書く。実行そのものは案件のscope外でよいが、要ることが記録に残っていなければ誰も気づかない。

根拠(2026-08-02、`tester_mode`撤廃): 同じ形が**この1案件だけで2回**出た。`incident-capture-collector.py`は必須フィールド集合が旧版のまま、`recovery-probe.py`は削除したはずのdrillが両ホストで生存していた。**2回ともstatus.mdのWatchでは拾えず、実機を見て初めて気づいた** — Watchは「将来の時点で確かめること」を置く場所であり、「既に古い配備物」は時間が経っても発火しないためである。案件記録: `docs/ai/reviews/tester_mode_full_removal/2026-08-02_012_audit_r10.md`。

### playbookを増やす案件では索引の更新を成果物へ入れる

`playbooks/README.md` の更新を成果物に含める。含めておけば、**Auditorの職掌を広げずに**「受入条件の充足」の検査で拾える(`docs/ai/roles/auditor.md`はAnsible Contextを明示的に「読まないもの」としており、索引の検査を直接持たせると役割の肥大へ逆戻りする)。

対象は`playbooks/README.md`の1つだけである。`role-map.md` / `playbook-map.md` は2026-07-29に廃止済み。

## 優先度の規律

「全部がP0なら、P0は存在しないのと同じ。すべてのmust-haveを疑え」。P0は本当に初回実装に不可欠なものだけに絞る。

## 適用条件

- IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない。inventory group名・変数名・既公開ホスト名で表現する(`docs/ai/context-classification.md` §3/§4)。
- リスク欄を書く場合は`skills/risk-assessment/SKILL.md`のレジスタ形式を使う。
