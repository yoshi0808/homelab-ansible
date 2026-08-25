---
name: ansible-implementation-style
description: homelab-ansibleのImplementerがshell/Python/Jinja2を含むAnsible実装を書くときのスタイル基準。「実装する」「shellスクリプトを書く」「Jinja2テンプレートを書く」場面で使う。shellを使う全roleに適用される「check系shellの責務分離」の正本を含む。
---

# Ansible Implementation Style

Ansible専用の公式Skillは存在しないため、内部で使う個別言語ごとにベンダー公式の一次情報を直接参照する。SKILL.md形式の非公式ラッパーは導入しない。本文には要点のみ記載し、原文は転記しない。

**revision追跡**: 以下は全て公式ドキュメントの「latest」参照であり、git commitのような固定revisionを持たない。参照日は2026-07-23。Ansible公式ドキュメントはAnsibleのリリースに追従して内容が変わりうるため、Ansibleのメジャーバージョンアップ時など内容が古くなったと疑われる場合は該当URLを再確認する。Google Style Guideは更新頻度が低く、通常は再確認不要。

## Shell

出典: Google Shell Style Guide — https://google.github.io/styleguide/shellguide.html

- shellは小規模ユーティリティ・単純なラッパースクリプトに限定して使う。
- 100行を超える、または制御フローが複雑になった場合は構造化言語(Python)へ書き直す。

### check系shellの責務分離

healthcheck系に限らず、shellを使う全roleに適用される。`docs/ai/core.md`「Ansible変更の共通ゲート」の「check系shellは観測に留め、判定・分類・通知・保存をshellへ持たせない」の正本はここである。

shellスクリプト(`files/*.sh`)は収集とJSON整形のみを行い、warning/critical等の判定をしない。判定・分類・reportは常にAnsible側(`tasks/*.yml`)が行う。

check系shellは対象ホスト上でコマンドを実行し、結果をJSONに整形して標準出力へ返す。**収集とJSON整形のみ**を行い、次を行わない。

- **変更操作**(check系shellへ変更を伴う操作を一切入れない)
- 正常 / 異常の判定
- warning / criticalの分類
- host_varsとの期待値比較
- 実行継続 / 中止の判断
- 通知
- レポート保存

責務分離は次のとおり。

```text
Shell:   収集とJSON整形のみ
Ansible: 配置、実行、JSON読込、期待値比較、warning/critical分類、保存、fail制御
```

補足:

- shellが`port_1812_listen: true/false`のような観測値を返すことは許容する。
- shellが`status: critical`や`warnings: [...]`を生成することは許容しない。
- shellはhealth判定の主体ではなく、対象ホスト上の情報収集センサーとして扱う。

`proxmox_snapshot_check`の収集script(`proxmox-snapshot-collect.sh`)はこの分離を明示コメントで守っている好例(「7日の閾値はAnsible tasks側で評価する」と明記)。新規判定を追加する際もshell側を変更する必要はなく、`tasks/main.yml`側だけで完結させられる。healthcheck系role共通のパターン(warning/critical二段階閾値、tester-gateマーカーと実guardの整合、reportの保存パターン等)は`docs/ai/context/operations/healthcheck.md`を参照する。

## Python

出典: Google Python Style Guide — https://google.github.io/styleguide/pyguide.html

- filter_plugin等のPythonコードにおける命名規則・例外設計の基準として使う。

## Jinja2 / 変数

出典: Ansible公式ドキュメント
- 変数とJinja2: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_variables.html
- テンプレーティング: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_templating.html

- `{{ foo }}` で始まる値は行全体をクォートしないとYAMLパースエラーになる。
- Jinja2のループ・条件はplaybook内では使えず、template内でのみ使う。

## `-e` で空白を含む値を渡さない(playbook実行時)

`ansible-playbook -e` は**単一の `-e` 内に空白区切りで複数の `key=value` を書ける**仕様を持つ。この副作用で、**値に空白が含まれると次のkeyの開始と解釈され、値がそこで切れる**。日本語の文中にASCII語が混ざる文字列で特に踏みやすい。

```
# 壊れる
ansible-playbook p.yml -e title="検証 test" -e message="本文 body"
# 安全
ansible-playbook p.yml --extra-vars '{"title":"検証 test","message":"本文 body"}'
```

**空白を含みうる値はJSON形式の `--extra-vars` で渡す。** 2026-07-27に別々のTesterが同日中に2回踏み、うち1回は実際のSlack通知がタイトル・本文とも**値の中の最初の半角スペースで切断された状態**で本番チャンネルへ送信された(現物をYoshinobuが確認)。文字化けではなく切断であり、**送信自体は成功するため送り手側では気づきにくい**。実装・検証のどちらでも起こる。

## 手動適用・ロールバック系playbookのCLI引数規約

新規に「適用して、戻せる」形のplaybookを書くときは、既存に合わせる。

- **CLI表面は `-e rollback=true` / `-e rollback_to=X.Y.Z` で統一する**(打ちやすさ優先の共通muscle memory)。
- **role内部では必ず `<role>_rollback` / `<role>_rollback_to` へmapして参照する**(例: `prometheus_update_check_rollback: "{{ rollback | default(false) | bool }}"`)。`-e` はグローバル最優先で撒かれるため、汎用名のままroleロジックへ渡すと複数role読込時に衝突する。
- **意味論も共通とする**: 無指定は直近backupへ復帰 / `rollback_to=X` は特定backupを選択(無ければfail-closed) / `--check` 併用は対象表示のみ。**戻す前に現物も退避する**(rollback自体も可逆にする)。backup不在はfail-closed。
- **`-e` はコンマ区切り不可。** `-e rollback=true -e rollback_to=3.12.0`(別々)か `-e "rollback=true rollback_to=3.12.0"`(スペース)。`-e rollback=true,rollback_to=3.12.0` は `rollback` に文字列全体が入る誤りになる。

既存の実装例は `roles/prometheus_update_check`(`upgrade.yml` / `manual_rollback.yml` / `discover_backups.yml`)。

## 時刻はJST(+09:00)で書く。オフセットの表記は必ず変換の結果であること

このリポジトリが生成する時刻(Slack通知、レポートJSON、ファイル名、ログ)は**JST(`+09:00`)を正**とする。

**守るべきことは1つ** — **オフセットの表記は、実際に行った変換の結果でなければならない。** 時計が返した値に、望む表記をあとから貼り付けない。これを破る書き方が2つあり、どちらも**出力は一見正しく、値だけが9時間ずれる**ため、目視でもテストでも気づけない。

```
# 詐称: UTCの値にJSTのラベルを貼っている
date -u '+%Y-%m-%dT%H:%M:%S+09:00'
# 詐称: ローカル時刻にUTCのラベル(Z)を貼っている
date '+%Y-%m-%dT%H:%M:%SZ'
```

repoで確立している書き方は次の2つで、新規実装もこれに倣う。

| 文脈 | 書き方 |
|---|---|
| shell / Ansibleの`lookup('pipe', ...)` | `TZ='Asia/Tokyo' date '+%Y-%m-%dT%H:%M:%S+09:00'` — **`TZ=` で変換してからリテラルを付けている**ので嘘にならない |
| Python | `datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z")` — `%z` が**実オフセットを出す** |

**別TZの値を扱うときは、変換してから整形する。** `roles/recovery_exec/files/recovery-loki-helper` が両方向の実例で、Lokiへ渡す側は `astimezone(timezone.utc)` してから `Z` を付け、出力側は `astimezone(JST)` してから `+09:00` を付けている。**先に変換、あとで表記。**

**掃引は「貼られたラベル」の側から引く。** `grep -rn 'date -u'` だけではクラス2(ローカル時刻にリテラル`Z`を貼る)が`-u`を持たないため引っかからない。次の2本を使う。

```
grep -rnE "date [^|]*%SZ" roles playbooks scripts   # リテラルZ → -u か TZ=UTC を伴っているか確認
grep -rn -- '+09:00' roles playbooks scripts        # リテラル+09:00 → TZ='Asia/Tokyo' を伴っているか確認
```

**引用符の形を決め打ちしたパターンを書かない。** `date '+...%SZ'`(単一引用符)・`date +"...%SZ"`(二重引用符)・`date +...%SZ`(無引用)の3通りがあり、どれか1つの形に合わせて書くと残り2つを取りこぼす。上の1本目は3通りとも拾うことをfixtureで確認済み(2026-08-03)。

2026-07-13の横断修正では計9箇所が出て、うち1箇所がクラス2だった。同じバグが4サブシステムに散っていた — **コピペ元を間違えると伝播する。**

注意点2つ。

- **Semaphoreの保存はUTCである**(`docs/ai/context/system/semaphore.md`)。`reports/` 配下はJSTなので、**障害バンドルは両者を混在させる。** どちらの時刻を見ているかを、読む側が判断できるようにする。
- **Jinjaの`strftime`フィルタは既定が`utc=False`**で、コントローラのシステムTZに従う。`%z`を使っていれば実オフセットが出るのでTZが変わっても嘘にはならないが、**出力そのものはTZに依存して動く。** 該当箇所は`roles/proxmox_snapshot_check/tasks/main.yml`と`playbooks/recovery_monitoring_check.yml`の2つで、既知として`docs/ai/status.md`のNextに載せてある。**新しく`strftime`フィルタを使うときは`utc=True`の要否をその場で判断し、判断をコメントに残す**(後者は既にそうしている)。

## task-level `vars:` の lookup は複数回評価されうる

task の `vars:` に `lookup('pipe', ...)` のような**副作用や時刻を伴う式**を置き、同一task内の複数箇所から参照すると、**lookupが参照回数ぶん実行される**(2026-07-27、カウンタファイルへの副作用ログで実測)。

実害の例: `date '+%s %Y-%m-%dT%H:%M:%S+09:00'` を1回呼んで epoch とRFC3339を両方得る意図で書いたが、実際は2回呼ばれており、**秒境界をまたぐとファイル名のepochと記録した時刻が1秒ずれる**状態だった。

値を1度だけ確定させたい場合は、**専用の `set_fact` task で先に確定させてから**参照する。`vars:` は「参照ごとに再評価されうる式」だと考える。

## `include_tasks` / `block` に付けられない属性

- `include_tasks` に `become` / `delegate_to` を付けると `'become' is not a valid attribute for a TaskInclude` でハードエラーになる
- `block` に `changed_when` を付けると `'changed_when' is not a valid attribute for a Block` になる

いずれも**include先またはblock配下の各taskへ個別に付ける**。

あわせて、動的includeは**静的検査も実行時の`rescue`も届かない**。`--syntax-check`と`ansible-lint`はinclude先の中身を検証せず、include先のYAML構文エラーはパースがtask実行ループより前に失敗するため`rescue`で捕捉できない(playが即死する)。**ファイルが存在しない場合だけは`rescue`で捕捉できる**ので、この2つを混同しない。したがって**動的includeを1つ足すことは、include元の全呼び出し経路へハード依存を1つ足すこと**であり、予防の層はcommit前のゲート(`scripts/check-staged-yaml.py`)しか無い。追加する前にinclude元が何箇所から呼ばれるかを数える。

## check_mode の実装上の落とし穴

実装時に繰り返し踏んだ／踏みかけた問題であり、新しいplaybookを書くときとレビューするときに毎回確認する。分類の意味・実行義務そのものは`docs/ai/policies/ansible_test_safety_policy.md`が正本(TS-028が本節を参照している)。

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
- これは「値の目視で終えず、その値を消費する側まで通す」と同型の観点であり、対象がJinjaの値ではなくtaskの発火条件になったものである。
- **防御・ガードを意図的に置かなかった箇所には、置かない理由をコメントに残す。** 書き忘れと区別が付かないと、後から善意で足される。逆に、既知の欠陥を直さないと判断した箇所も同じ扱いにする。

根拠: 2026-07-26、`proxmox_patch_dryrun`単一ノード対応の実装中に、Implementer役がdecoy inventory(閉ポート/`ansible_connection: local`)で`ping`/`fail`/`debug`/`meta: clear_host_errors`のみを使った4パターンの検証を行って発見した。ADR-002で決めた0件ガードの実装が該当し、出荷前に潰している。

## 適用条件

セキュリティに関わる実装判断(shell/commandモジュールへの変数注入対策等)は`skills/ansible-security-review/SKILL.md`を参照する。本Skillは表現・スタイルレベルの基準であり、Reviewer/Testerの検査基準には拡張しない。ただし上記「check_modeの実装上の落とし穴」はReviewerも確認対象とする。
