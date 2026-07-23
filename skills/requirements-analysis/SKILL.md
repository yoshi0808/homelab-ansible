---
name: requirements-analysis
description: homelab-ansibleのCoordinator/Tech Leadが新規案件の要求を明確化し requirement.md を書くときの構成テンプレート。「要件をまとめる」「requirementを書く」「案件を整理する」場面で使う。
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

## 優先度の規律

「全部がP0なら、P0は存在しないのと同じ。すべてのmust-haveを疑え」。P0は本当に初回実装に不可欠なものだけに絞る。

## 適用条件

- IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない。inventory group名・変数名・既公開ホスト名で表現する(`docs/ai/context-classification.md` §3/§4)。
- リスク欄を書く場合は`skills/risk-assessment/SKILL.md`のレジスタ形式を使う。
