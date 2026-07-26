# 実装報告: log_observability debug収集除外(LOG-070/071)

対象: `docs/ai/policies/log_observability_policy.md` v3.0(LOG-070/071)に基づく
debug severity除外の実装。系統1〜4(rsyslog受信側、config.alloy.j2の3箇所)。

種別: Ansible role変更(`roles/alloy/`)。production log pathへ影響しうる変更だが、
本段階では実host適用(APPLY)は行っていない(--check相当の構文確認まで)。

設計原則(techlead指定・全系統共通): 「labelを外す/matchを消す」のではなく、
levelを確定させたうえで`action = "drop"`により明示的にdropする。

## 系統1: rsyslog受信側(`roles/alloy/templates/observability-sources.rsyslog.j2`)

- `if ($syslogseverity == 7) { action(...) }` ブロックを削除した。
- 削除後、debugメッセージは「アドレス一致 → 各severity条件(<=3 / ==4 / 5-6)
  いずれも非該当 → `stop`」という経路をたどり、どのdestination fileへも書き込まれず
  破棄される。この経路の直前にコメントで理由(LOG-071)を明記した。
- `stop`は各`if (アドレス一致) { ... stop }`ブロックの最後にあり、後続の他ルートへの
  fallthroughは発生しない(このifブロックの外に他のルート定義は無く、本ファイル自体が
  他ファイルからincludeされる末端の設定であるため、`stop`後に処理されるルールは無い)。
- 使われなくなった`AlloyRemoteDebug` template定義を削除した。
- **参照の全文grep**: `grep -rn "AlloyRemoteDebug" .`を実行し、削除後は
  リポジトリ全体で0件であることを確認した(削除前は本ファイル内の定義行と
  参照行の2件のみで、他ファイルからの参照は元々存在しなかった)。

## 系統2: config.alloy.j2 — file source側(pve_nodes/sophos_fw/ubuntu_nodes)

- `extract_normalized_level_at_start`のregex(`^(?P<level>error|warning|info|debug)\s`)は
  そのまま維持した(debug alternationも削除していない)。
- `stage.labels`でlevelラベルが確定した直後に、`stage.match { selector = "{level=\"debug\"}"
  action = "drop" drop_counter_reason = "observability_debug_excluded" }`を追加した。
- この位置はpve_nodes/sophos_fw/ubuntu_nodesの3 source共通のJinja `{% if
  source.extract_normalized_level_at_start %}`ブロック内であり、この3 source全てに
  自動的に適用される(defaults/main.ymlでこの3 sourceだけがtrueであることを確認済み)。

## 系統3: config.alloy.j2 — CloudKey/UniFi/network-devicesのbest-effort側

- best-effort側のdebug token検出`stage.match`(現行`stage.static_labels`で
  level="debug"を付与していた箇所)を、`action = "drop"`
  `drop_counter_reason = "observability_debug_excluded"`へ変更した(selectorは無変更)。
- この`stage.match`は`{% if source.extract_level_best_effort %}`ブロック内にあり、
  `alloy_file_sources`のループ内で共有される。**defaults/main.ymlを確認し、
  `extract_level_best_effort: true`を持つのは`unifi`と`network_devices`の2
  sourceだけであることを明示確認した**。したがってこの1箇所の変更が両方に
  自動的に適用される(個別対応不要)。ローカルレンダリングで両方の
  `loki.process "unifi_pipeline"` / `"network_devices_pipeline"`に同じdrop
  stageが出力されることを確認済み(下記「自己検証」参照)。

## 系統4: config.alloy.j2 — monnie journal(priority 7 → debug relabel + 新設グローバルdrop)

- `loki.relabel`の`priority 7 → level=debug`replacementルールは変更していない
  (要求どおり維持)。
- 既存の自ノイズdrop(`alloy_observability_journal_drop_units`、LOG-027、
  unit限定でinfo/debugをdrop)とは別に、全unit対象のグローバルなdebug dropを
  同じ`loki.process "system_pipeline"`内に新設した。
  - selector: `{job="ubuntu-nodes", host="monnie", level="debug"}`(unit条件なし)。
  - `drop_counter_reason = "observability_debug_excluded"`とし、既存の自ノイズdrop
    (`"observability_info_debug"`)とは別の理由文字列にして区別可能にした。
  - 新設のグローバルdrop stageを自ノイズdropのループより前に配置した。
- **実装上の判断**: 従来`loki.process "..._pipeline"`ブロックとその
  `forward_to`分岐は`drop_info_debug_units | length > 0`の場合だけ生成される
  設計だった(list非空を前提)。グローバルdebug dropは常に必要なため、この
  条件分岐を外し、`loki.process`ブロックと`loki.source.journal`の
  `forward_to = [loki.process...receiver]`を常時生成する形に変更した(空リストの
  場合は既存unitループが単に0回実行されるだけで、既存の自ノイズdrop機能自体は
  変更していない)。
- **自ノイズdrop側のselectorから"debug"を残すか外すかの判断**: 要求で
  「あなたの判断で構わない」とされていたため、既存の
  `level=~"info|debug"`はそのまま**残した**(変更していない)。理由: 新設の
  グローバルdropと重複するがdouble-dropは無害であり、diffを最小化できる。
  reviewerの意図確認事項として記録する。

## 追加で必要だった変更(4系統の指定範囲外・見つけた依存)

`roles/alloy/tasks/main.yml`の「Check the rendered Alloy pipeline contract」
assert task(config.alloy.j2の レンダリング結果を文字列countで検証する既存の
self-check)が、config.alloy.j2の変更によって**そのままでは壊れる**ことが分かった
ため、併せて修正した。要求の「4系統」には明記されていなかったが、この
assertはconfig.alloy.j2の出力を検証する目的で存在しており、テンプレート変更に
追随させないと自己検証そのものが機能しなくなるため(`--check`実行時点で
このassert taskが必ず走る)、スコープに含めて対応した。

- 旧: `alloy_candidate_config.count('action              = "drop"') ==
  (alloy_observability_journal_drop_units | length)` — 新設した3系統のdrop
  stage(合計6箇所)が同じ`action              = "drop"`という文字列パターンを
  追加で生成するため、このassertは壊れる(旧: 5件想定 → 新: 11件出力)。
- 対応: この行を削除し、代わりに次の2 assertへ置き換えた。
  1. `drop_counter_reason = "observability_debug_excluded"`の出現回数が、
     「`extract_normalized_level_at_start=true`のfile source数(3)」+
     「`extract_level_best_effort=true`のfile source数(2)」+
     「journal source数(1)」の合計(=6)と一致すること。
  2. `action              = "drop"`の総出現回数が、
     `drop_counter_reason = "observability_info_debug"`の出現回数と
     `drop_counter_reason = "observability_debug_excluded"`の出現回数の
     合計と一致すること(すべてのdrop stageが既知のreasonのいずれか一つに
     対応しており、reasonのないdrop stageが紛れ込んでいないことを保証する
     不変条件へ書き換えた)。
- 既存の`drop_counter_reason = "observability_info_debug"`件数チェックと
  `'replacement  = "debug"'`存在チェックは無変更(自ノイズdropとpriority
  relabelはどちらも変更していないため)。

## 自己検証

### AlloyRemoteDebug参照の全文grep

```text
$ grep -rn "AlloyRemoteDebug" /home/yoshi/homelab-ansible/
(出力なし)
```
→ PASS。定義・参照ともにリポジトリから完全に消滅。

### ansible-lint

```text
$ ansible-lint playbooks/alloy_setup.yml roles/alloy/
...
Failed: 1 failure(s) ... roles/alloy/tasks/main.yml:357:13
no-handler: Tasks that run when changed should likely be handlers.
  Task/Handler: Validate the restored complete rsyslog configuration
```
この指摘は`git stash`で変更前のファイルに対しても同一rule・同一task名で
再現することを確認済み(行番号のみ349→357へ移動、これは今回9行追加した
ことによるずれ)。**今回のdiffが原因ではない既存の指摘**であり、4系統の
変更やtasks/main.ymlのassert修正とは無関係。対象外として扱った。

### --syntax-check

```text
$ ansible-playbook -i inventories/homelab/hosts.yml playbooks/alloy_setup.yml --syntax-check
playbook: playbooks/alloy_setup.yml
$ ansible-playbook -i inventories/homelab/hosts.yml playbooks/rsyslog_forward_to_monnie.yml --syntax-check
playbook: playbooks/rsyslog_forward_to_monnie.yml
```
→ 両方PASS。

### river config構文相当の確認(ローカルレンダリング+assert再現)

実hostを一切介さず`hosts: localhost, connection: local`のscratch playbookで
`lookup('ansible.builtin.template', ...)`により両テンプレートをローカル
レンダリングし、`tasks/main.yml`内の「Check the rendered Alloy pipeline
contract」assertと同一条件(更新後のもの含む)をこのscratch playbook内で
再現・実行した。結果は全assert PASS(`ALL ASSERTIONS PASSED`)。
レンダリング結果を目視確認し、4系統それぞれの狙いどおりの出力になっていることを
確認した(unifi/network_devicesの両方でbest-effort debug dropがaction=drop化
されていること、pve_nodes/sophos_fw/ubuntu_nodesの3つ全てにlevel=debug drop
stageが追加されていること、system journalにグローバルdebug drop + 既存5unitの
自ノイズdropが両方出力されていることを個別に確認)。

補足: このrender+assert再現に使ったIPv4値はscratch playbook専用のダミー値
(RFC 5737のドキュメント用予約帯)であり、リポジトリには一切含まれない
(scratch fileは`/tmp`配下のみに存在し、gitでは追跡されていない)。

`alloy validate`バイナリはこのマシンに存在せず、River文法としての厳密な
構文検証(Alloy公式パーサ)は実施できなかった。実rendered configの
`alloy validate`実行は`roles/alloy/tasks/main.yml`の既存フロー
(`Validate the deployed Alloy configuration before cutover`)がAPPLY時に
実行するため、tester委譲とする。

### rsyslog構文の目視確認 + ローカルrsyslogd検証の制約

ローカルレンダリングした`observability-sources.rsyslog.j2`の出力を目視確認し、
削除箇所以外に構文上の異常(不整合な波括弧、テンプレート参照切れ)がないことを
確認した。

`rsyslogd -N1 -f <rendered file>`によるバイナリ検証を試みたが、このセッションの
実行環境ホスト(`ansy`、`hostname`コマンドで確認、homelab inventoryの実ホストの
一つ)ではAppArmor confinementにより`/tmp`配下の任意パスをrsyslogdが開けず
(`Permission denied`、sudo併用でも同様)、失敗した。`/etc/rsyslog.d/`配下への
一時ファイル設置はansy上の実rsyslogサービス(現在active)に影響しうるため、
Implementerの権限で行うべきでないと判断し実施しなかった(ファイル書込み・
サービスへの影響は一切発生していない)。バイナリでの`rsyslogd -N1`検証は
tester委譲とする(`roles/alloy/tasks/main.yml`の既存の
`Validate the staged Phase 2 rsyslog snippet`ステップがAPPLY経路で実行する)。

### git diff --check

```text
$ git diff --check -- roles/alloy/tasks/main.yml roles/alloy/templates/config.alloy.j2 roles/alloy/templates/observability-sources.rsyslog.j2
(出力なし、exit=0)
```
→ PASS。

### warning/errorの経路が無変更であることの確認

3ファイルのdiffを全文確認し、`AlloyRemoteError`/`AlloyRemoteWarning`
template、`$syslogseverity <= 3`/`== 4`/`== 5 or == 6`の各action、
`stage.match`のerror/warning/info判定(best-effort側・CEF側とも)、
`loki.relabel`のerror/warning/info replacementルールのいずれも変更して
いないことを確認した(diffのhunkに一切含まれない)。

## 作成・更新したファイル一覧

| ファイル | 種別 | 内容 |
|---|---|---|
| `roles/alloy/templates/observability-sources.rsyslog.j2` | 更新 | 系統1: severity==7ブロックとAlloyRemoteDebug templateを削除。 |
| `roles/alloy/templates/config.alloy.j2` | 更新 | 系統2〜4: 3箇所のdebug明示dropを追加、冒頭コメントを3値severityへ更新。 |
| `roles/alloy/tasks/main.yml` | 更新 | config.alloy.j2の変更に伴い壊れる既存assertを修正し、新設drop stage数の検証assertを追加(依存として発見・対応)。 |
| `docs/ai/reviews/promtail_to_alloy/2026-07-26_026_implement_debug_exclusion.md` | 新規 | 本ファイル。 |

`playbooks/`は無変更。`docs/ai/policies/log_observability_policy.md`は
本タスク開始前から作業ツリーに存在した既存の未commit差分(v3.0本体、他者による
更新)であり、今回変更していない。

## 未対応事項 / 注意点

- **実host適用は未実施**。本報告はレンダリング結果のローカル検証と静的解析
  までであり、実際のmonnieへの`alloy_setup.yml` APPLY(またはcheck-mode実行)は
  行っていない。
- `alloy validate`バイナリでのRiver構文検証、`rsyslogd -N1 -f`での実バイナリ
  構文検証はいずれも未実施(上記「自己検証」参照)。tester委譲。
- 実際のdebugログがLokiへ流れ込まなくなること、既存のerror/warning/infoが
  引き続き到達すること、`drop_counter_reason`によるドロップ件数の可観測性
  (Alloyのメトリクス`loki_process_dropped_lines_total`等)は実機でのみ
  確認可能。
- 自ノイズdrop側selectorの`"debug"`を残す判断は「あなたの判断で構わない」との
  指示に基づく選択であり、reviewerに意図確認を委ねる(上記「系統4」参照)。

## Next step files
- docs/ai/policies/log_observability_policy.md
- docs/ai/reviews/promtail_to_alloy/2026-07-26_026_implement_debug_exclusion.md
