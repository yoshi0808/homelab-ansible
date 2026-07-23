---
name: code-review
description: homelab-ansibleのReviewer roleがレビュー結果を報告するときの出力フォーマット。「レビューして」「reviewとして返す」「findingsをまとめる」といった場面で使う。レビューの観点・判断基準そのものは docs/ai/roles/reviewer.md が正本であり、このSkillは出力の型だけを定める。
---

# Code Review (出力フォーマット)

出典: `anthropics/knowledge-work-plugins` の `code-review` スキル(engineering/skills/code-review)を参考に、homelab-ansible向けに出力フォーマットのみを採用したもの。レビューの運用ロジック・重大度判断・エスカレーション条件は `docs/ai/roles/reviewer.md` が優位する。このSkillはそれらを重複記載しない。
https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/code-review/SKILL.md
取り込み時点のrevision: commit `2d6f7e22dd25`(2026-03-13)。更新確認はhttps://github.com/anthropics/knowledge-work-plugins/commits/main/engineering/skills/code-review/SKILL.md で最新commitを確認し、上記revisionと比較する。

## 出力フォーマット

```
## Code Review: [対象playbook/role/PR]

### Summary
[全体所見を1-3文]

### Critical Issues
| # | File | Line | Issue | Severity |

### Suggestions
| # | File | Line | Suggestion | Category |

### What Looks Good
[確認済みで問題ない点]

### Verdict
[Approve / Request Changes / Needs Discussion]
```

## 適用条件

- 重大度分類・エスカレーション基準は `docs/ai/roles/reviewer.md` を参照する。
- IPアドレス・VLAN ID・VM ID・認証情報などの実値はSeverity/Issue欄にも書かない。inventory group名・変数名・既に公開済みのホスト名(例: pve1、quory)で表現する(`docs/ai/context-classification.md` §3/§4)。
- Verdictが `Request Changes` の場合、対象Tech Leadへの返却先は `docs/ai/roles/reviewer.md` の「成果物と返却先」に従う。
