---
name: duplication-reuse-check
description: homelab-ansibleのReviewerが実装差分の重複・再利用漏れを確認するときに使う。「重複がないか確認する」「既存roleを再利用しているか確認する」場面で使う。全リポジトリ横断検索は行わない軽量な照合に限定する。
---

# Duplication / Reuse Check(重複・再利用確認)

出典: `anthropics/knowledge-work-plugins` の `tech-debt` スキル(engineering)。「Code debt」カテゴリの定義のみ採用。
https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/tech-debt/SKILL.md
取り込み時点のrevision: commit `4fa3cb92e294`(2026-02-24)。更新確認はhttps://github.com/anthropics/knowledge-work-plugins/commits/main/engineering/skills/tech-debt/SKILL.md で最新commitを確認し、上記revisionと比較する。

## Code debtの定義

Duplicated logic、poor abstractions、magic numbers → バグ・開発速度低下の原因になる。

## homelab-ansibleでの運用手順

- **発見・指示はCoordinatorが担う**: requirement作成・タスク分解時に、既存のfilter_plugin/role/他playbookとの重複可能性を洗い出し、再利用対象をrequirementへ明記する。
- **Reviewerは照合のみ**: 「指定された既存資産を実装が実際に使ったか」を確認する軽量な検査に限定する。全リポジトリ横断検索はReviewerに行わせない。

## 適用先

`skills/code-review/SKILL.md`のレビュー出力(Suggestionsまたは Critical Issues)に1行追加する形で報告する。
