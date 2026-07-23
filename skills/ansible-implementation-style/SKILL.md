---
name: ansible-implementation-style
description: homelab-ansibleのImplementerがshell/Python/Jinja2を含むAnsible実装を書くときのスタイル基準。「実装する」「shellスクリプトを書く」「Jinja2テンプレートを書く」場面で使う。
---

# Ansible Implementation Style

Ansible専用の公式Skillは存在しないため、内部で使う個別言語ごとにベンダー公式の一次情報を直接参照する。SKILL.md形式の非公式ラッパーは導入しない(2026-07-23確定)。本文には要点のみ記載し、原文は転記しない。

## Shell

出典: Google Shell Style Guide — https://google.github.io/styleguide/shellguide.html

- shellは小規模ユーティリティ・単純なラッパースクリプトに限定して使う。
- 100行を超える、または制御フローが複雑になった場合は構造化言語(Python)へ書き直す。
- 現行core.mdの「shell責務は収集とJSON整形のみ」を補強する根拠として使う。

## Python

出典: Google Python Style Guide — https://google.github.io/styleguide/pyguide.html

- filter_plugin等のPythonコードにおける命名規則・例外設計の基準として使う。

## Jinja2 / 変数

出典: Ansible公式ドキュメント
- 変数とJinja2: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_variables.html
- テンプレーティング: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_templating.html

- `{{ foo }}` で始まる値は行全体をクォートしないとYAMLパースエラーになる。
- Jinja2のループ・条件はplaybook内では使えず、template内でのみ使う。

## 適用条件

セキュリティに関わる実装判断(shell/commandモジュールへの変数注入対策等)は`skills/ansible-security-review/SKILL.md`を参照する。本Skillは表現・スタイルレベルの基準であり、Reviewer/Testerの検査基準には拡張しない(2026-07-23確認済み)。
