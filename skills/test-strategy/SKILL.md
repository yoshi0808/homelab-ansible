---
name: test-strategy
description: homelab-ansibleのTesterがtest_plan.mdを書くときのカバレッジ配分の型。「test planを書く」「テスト戦略を決める」場面で使う。
---

# Test Strategy(テスト計画の型)

出典: `anthropics/knowledge-work-plugins` の `testing-strategy` スキル(engineering)。カバレッジ配分の型のみ採用。
https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/testing-strategy/SKILL.md

## カバレッジ配分

unit / integration / e2e の3層でtest planを構成する。

## Ansible文脈への翻訳(2026-07-23、自作)

「e2e」に相当する段階を次の3段階に対応させる。

1. dry-run(`--check`または該当playbookのdry-runモード)
2. apply(限定対象への実適用)
3. 事後健全性チェック(healthcheck系roleでの確認)

## 適用先

`test_plan.md`のテンプレート構造。

## 対象外(別途自作が必要)

境界値分析・property-based testingは本Skillに含まれない。

## 適用条件

IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない(`docs/ai/context-classification.md` §3/§4)。
