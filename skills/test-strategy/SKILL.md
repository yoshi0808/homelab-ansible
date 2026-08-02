---
name: test-strategy
description: homelab-ansibleのTesterがtest_plan.mdを書くときのカバレッジ配分の型。「test planを書く」「テスト戦略を決める」場面で使う。
---

# Test Strategy(テスト計画の型)

出典: `anthropics/knowledge-work-plugins` の `testing-strategy` スキル(engineering)。カバレッジ配分の型のみ採用。
https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/testing-strategy/SKILL.md
取り込み時点のrevision: commit `4fa3cb92e294`(2026-02-24)。更新確認はhttps://github.com/anthropics/knowledge-work-plugins/commits/main/engineering/skills/testing-strategy/SKILL.md で最新commitを確認し、上記revisionと比較する。

## カバレッジ配分

unit / integration / e2e の3層でtest planを構成する。

## Ansible文脈への翻訳

「e2e」に相当する段階を次の3段階に対応させる。

1. dry-run(`--check`または該当playbookのdry-runモード)
2. apply(限定対象への実適用)
3. 事後健全性チェック(healthcheck系roleでの確認)

## 実行コマンドの組み立て

Testerが自分のsandboxからplaybookを実行する際は、temp pathを実行ユーザーごとに分離する。
固定パスにすると別ユーザー(`ann` / `yoshi`)の残骸と衝突してUNREACHABLEになる。

```
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local \
ANSIBLE_REMOTE_TEMP='/tmp/ansible-remote-$USER' ansible-playbook ...
```

`ANSIBLE_REMOTE_TEMP`は**シングルクォート必須**である。ダブルクォートにすると`$USER`が
実行元で先に展開され、リモート側で意図しないパスになりUNREACHABLEになる。2026-07-26の
`ca_trust_deploy`適用時に実際にこの誤りでansyが初回UNREACHABLEとなり、再実行で解消した。

## 適用先

`test_plan.md`のテンプレート構造。

## 対象外(別途自作が必要)

境界値分析・property-based testingは本Skillに含まれない。

## 適用条件

IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない(`docs/ai/context-classification.md` §3/§4)。
