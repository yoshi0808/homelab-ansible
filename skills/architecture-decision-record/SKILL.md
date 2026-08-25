---
name: architecture-decision-record
description: homelab-ansibleのCoordinatorが技術選択(実装方式の決定)を記録するときに使う。「ADRを書く」「技術選択を記録する」「実装方式を決める」場面で使う。Coordinatorの優先順位付け(Decision Memo)とは別物であり混同しない。
---

# Architecture Decision Record(ADR)

出典: `anthropics/knowledge-work-plugins` の `architecture` スキル(engineering)を参考に、ADRの型のみ採用したもの。
https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/architecture/SKILL.md
取り込み時点のrevision: commit `2d6f7e22dd25`(2026-03-13)。更新確認はhttps://github.com/anthropics/knowledge-work-plugins/commits/main/engineering/skills/architecture/SKILL.md で最新commitを確認し、上記revisionと比較する。

## 型

```
# ADR-[番号]: [題名]
**Status:** Proposed | Accepted | Superseded

## Context
[背景・制約]

## Options Considered
| Option | Pros | Cons |

## Decision
[選択した結論]

## Trade-off Analysis
[選んだ理由・捨てた理由]

## Consequences
[今後への影響]
```

## 用途例

Molecule採用可否、Codex/Claude Code固定化の判断など、技術選択の軽量な意思決定記録。

## 適用先

`docs/ai/adr/`。

**`skills/goal-tracking/SKILL.md`(Decision Memo)とは統合しない**: ADRはスコープ確定後の実装方式選択(How)を扱う。優先順位づけ(What/When)はCoordinatorのDecision Memoが扱う。

## 適用条件

IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない(`docs/ai/context-classification.md` §3/§4)。
