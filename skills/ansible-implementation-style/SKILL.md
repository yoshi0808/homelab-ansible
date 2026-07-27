---
name: ansible-implementation-style
description: homelab-ansibleのImplementerがshell/Python/Jinja2を含むAnsible実装を書くときのスタイル基準。「実装する」「shellスクリプトを書く」「Jinja2テンプレートを書く」場面で使う。
---

# Ansible Implementation Style

Ansible専用の公式Skillは存在しないため、内部で使う個別言語ごとにベンダー公式の一次情報を直接参照する。SKILL.md形式の非公式ラッパーは導入しない(2026-07-23確定)。本文には要点のみ記載し、原文は転記しない。

**revision追跡**: 以下は全て公式ドキュメントの「latest」参照であり、git commitのような固定revisionを持たない。参照日は2026-07-23。Ansible公式ドキュメントはAnsibleのリリースに追従して内容が変わりうるため、Ansibleのメジャーバージョンアップ時など内容が古くなったと疑われる場合は該当URLを再確認する。Google Style Guideは更新頻度が低く、通常は再確認不要。

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

## task-level `vars:` の lookup は複数回評価されうる

task の `vars:` に `lookup('pipe', ...)` のような**副作用や時刻を伴う式**を置き、同一task内の複数箇所から参照すると、**lookupが参照回数ぶん実行される**(2026-07-27、カウンタファイルへの副作用ログで実測)。

実害の例: `date '+%s %Y-%m-%dT%H:%M:%S+09:00'` を1回呼んで epoch とRFC3339を両方得る意図で書いたが、実際は2回呼ばれており、**秒境界をまたぐとファイル名のepochと記録した時刻が1秒ずれる**状態だった。

値を1度だけ確定させたい場合は、**専用の `set_fact` task で先に確定させてから**参照する。`vars:` は「参照ごとに再評価されうる式」だと考える。

## `include_tasks` / `block` に付けられない属性

- `include_tasks` に `become` / `delegate_to` を付けると `'become' is not a valid attribute for a TaskInclude` でハードエラーになる
- `block` に `changed_when` を付けると `'changed_when' is not a valid attribute for a Block` になる

いずれも**include先またはblock配下の各taskへ個別に付ける**。動的includeのその他の制約(静的検査が届かない、構文エラーが`rescue`で捕捉できない)は `docs/ai/memory/lessons/dynamic-include-escapes-static-and-rescue.md` を参照。

## check_mode の実装上の落とし穴

出典: 旧`docs/ai/prompts/core.md` §18.3(項目1・4・5)および§18.2(項目2・3のinclude例外)から移設(2026-07-26、移行表C18-03/04/06/07/08/10)。実装時に繰り返し踏んだ／踏みかけた問題であり、新しいplaybookを書くときとレビューするときに毎回確認する。分類の意味・実行義務そのものは`docs/ai/policies/ansible_test_safety_policy.md`が正本(TS-028が本節を参照している)。

1. **moduleごとにcheck_mode挙動が3パターンに分かれる。**
   - 非対応・auto-skip: `command` / `shell` / `expect` / `uri`(`ansible-doc <module>`の`attributes.check_mode.support: none`で確認できる)
   - 対応・simulate: `copy` / `template` / `file` / `systemd` / `apt`等(`--check`下では実際に書き込まず`changed`だけ返す)
   - `command`/`shell` + `creates:`/`removes:`: ファイル存在チェックの結果に応じて「`changed: true`と報告しつつ実行しない」という第3パターンを取る
   - 「初回でも必ず実データを作りたい」場合は、上記いずれのmoduleでも`check_mode: false`を明示しないと、実行されない・simulateされるだけで終わる。
2. **`include_role` / `include_tasks`(動的include)には`check_mode:`を直接付けられない**(`'check_mode' is not a valid attribute for a IncludeRole/TaskInclude`)。`import_role` / `import_tasks`(静的)へ置き換えるか、blockで包んでblock側に置く。
3. **`block:`に`loop:`は付けられない。** そのため`loop:`付きのincludeはblock化によるカスケードが使えず、include先のタスクファイル自身へ`check_mode: false`を個別に付ける(実例: `roles/recovery_push/tasks/drill_setup.yml`)。
4. **handlerは通知元taskの`check_mode: false`を継承しない。** handler自身へ個別に付ける(実地検証済み)。
5. **`meta: end_play` / `end_host`は、それが属するblockの`always:`を丸ごとスキップする**(通常のtask失敗によるrescue/alwaysフローとは異なる)。これに依存した旧ゲート実装は、停止時にレポート保存も通知も一切残らない「無音停止」になっていた。

## ガードtaskが発火しない条件

**`run_once` + `delegate_to: localhost`のガードtaskは、同一play内の全ホストが先に失敗していると発火しない。** `run_once`は「生存しているホストのうち1台で実行する」という意味であり、生存ホストが0になればtask自体が実行対象を失う。

これは「対象が0件なら明示的に停止・通知する」という**0件ガードほど、最も発動してほしい状況(全ホスト到達不能)でこそ死ぬ**ことを意味する。素朴に書くと、ガードのつもりのコードが死んだコードになる。

- ガードを書いたら、**全ホストが失敗した状態をdecoy inventoryで再現して、実際に発火するかを確認する**。「書いてあること」を発火の根拠にしない。
- 前段のホスト失敗を跨いでガードを効かせる必要がある場合、`meta: clear_host_errors`や、ガードを別playへ切り出す(`hosts: localhost`)といった設計が要る。いずれも採用前に上記のdecoy再現で発火を実測すること。
- 関連する検証観点は`docs/ai/memory/lessons/verify-through-the-consuming-filter.md`(値の目視で終えず消費側まで通す)と同型で、対象がJinjaの値ではなくtaskの発火条件になったもの。

根拠: 2026-07-26、`proxmox_patch_dryrun`単一ノード対応の実装中に、Implementer役がdecoy inventory(閉ポート/`ansible_connection: local`)で`ping`/`fail`/`debug`/`meta: clear_host_errors`のみを使った4パターンの検証を行って発見した。ADR-002で決めた0件ガードの実装が該当し、出荷前に潰している。

## 適用条件

セキュリティに関わる実装判断(shell/commandモジュールへの変数注入対策等)は`skills/ansible-security-review/SKILL.md`を参照する。本Skillは表現・スタイルレベルの基準であり、Reviewer/Testerの検査基準には拡張しない(2026-07-23確認済み)。ただし上記「check_modeの実装上の落とし穴」はReviewerも確認対象とする(出典の§18.3が実装時とレビュー時の双方を対象としていた)。
