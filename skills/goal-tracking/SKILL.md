---
name: goal-tracking
description: homelab-ansibleのCoordinatorが優先順位付けや意思決定記録(Decision Memo)をまとめるときに使う。「優先順位をつける」「Decision Memoを書く」「Now/Next/Laterで整理する」場面で使う。Tech Leadの実装方式選択(ADR)とは別物であり混同しない。
---

# Goal Tracking(優先順位付け・Decision Memo)

出典: `anthropics/knowledge-work-plugins` の `roadmap-update`(RICE/MoSCoW/ICE、Now/Next/Later)と`stakeholder-update`(Decision Documentation)を参考に採用したもの(product-management)。
- https://github.com/anthropics/knowledge-work-plugins/blob/main/product-management/skills/roadmap-update/SKILL.md — 取り込み時点のrevision: commit `2d6f7e22dd25`(2026-03-13)。更新確認はhttps://github.com/anthropics/knowledge-work-plugins/commits/main/product-management/skills/roadmap-update/SKILL.md
- https://github.com/anthropics/knowledge-work-plugins/blob/main/product-management/skills/stakeholder-update/SKILL.md — 取り込み時点のrevision: commit `2d6f7e22dd25`(2026-03-13)。更新確認はhttps://github.com/anthropics/knowledge-work-plugins/commits/main/product-management/skills/stakeholder-update/SKILL.md

## 優先順位付けフレームワーク

RICE / MoSCoW / ICE のいずれかを案件の性質に応じて使う。

## Now / Next / Later

3分類で構想中の作業を整理する。core.mdの「on the horizon」的な位置づけと相性が良い。

## Decision Memo(意思決定記録)

```
## Decision Memo: [題名]
### Status
### Context
### Decision
### Consequences
  - Positive:
  - Negative:
### Alternatives Considered
```

**Tech Leadの`skills/architecture-decision-record/SKILL.md`(ADR)とは統合しない**: Decision Memoは優先順位づけ(What/When、Yoshinobuへの提言止まりで決定権を持たない)、ADRはスコープ確定後の実装方式選択(How)。権限が異なるため別Skillのまま運用する(2026-07-23確定)。

## 適用先

構想中の`iac_coverage.md`(IaC化されてない領域の棚卸し・優先順位付け)。

## 適用条件

IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない(`docs/ai/context-classification.md` §3/§4)。
