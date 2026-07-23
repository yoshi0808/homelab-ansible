---
name: risk-assessment
description: homelab-ansibleのTech Leadがrequirement作成時やADR内でリスクを整理するときに使う。「リスクを洗い出す」「risk registerを作る」場面で使う。
---

# Risk Assessment(リスク整理フォーマット)

出典: `anthropics/knowledge-work-plugins` の `risk-assessment` スキル(operations、Legal版`legal-risk-assessment`ではなくOperations版を採用)。
https://github.com/anthropics/knowledge-work-plugins/blob/main/operations/skills/risk-assessment/SKILL.md
取り込み時点のrevision: commit `4fa3cb92e294`(2026-02-24)。更新確認はhttps://github.com/anthropics/knowledge-work-plugins/commits/main/operations/skills/risk-assessment/SKILL.md で最新commitを確認し、上記revisionと比較する。

## リスクカテゴリ(homelab文脈への翻訳)

| カテゴリ | homelabでの意味 |
|---|---|
| Operational | システム障害・停電・プロセス障害 |
| Security | 認証情報露出・不正アクセス |
| Financial | ハードウェア/電気代等のコスト影響 |
| Compliance | (社内規約・公開リポジトリ規約への抵触) |
| Strategic | 将来の拡張・移行を妨げる設計上の負債 |
| Reputational | public GitHub公開に伴う外部からの見え方 |

## レジスタ形式

```
| Risk | Likelihood | Impact | Mitigation |
```

## 適用先

`skills/requirements-analysis/SKILL.md`(requirement.md)のリスク欄、または個別の`skills/architecture-decision-record/SKILL.md`(ADR)内。

## 適用条件

IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない(`docs/ai/context-classification.md` §3/§4)。
