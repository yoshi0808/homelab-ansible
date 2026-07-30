# test_result: Grafanaダッシュボード/アラートのrepo正本化 — Step 2実機検証(AC3)

作成: 2026-07-30 / Tester(独立subagent)
対象: `docs/ai/reviews/grafana_provisioning/2026-07-30_004_plan.md` §3 U4
参照: `001_requirement.md` §11 AC3(受入条件の正本)、`004_plan.md` §1-6・§3、`009_implement_u3.md`、`010_review_u3.md`(Approve)、`008_test_result_step1.md`(Step 1、PASS済み)
対象playbook: `playbooks/grafana_provisioning.yml`(`# tester-gate: check-mode-native`、冒頭コメントで確認済み)
対象host: monnie(接続identity `ann`)
前提: R8手順1(旧4ルールのUI削除)はYoshinobuが本セッション以前に完了済みとCoordinatorがDBで確認済み(削除前の`alert_rule`総件数=4件、タイトル・UID一致)。この確認を根拠に`alert_rules_predecessor_confirmed=true`を指定した。

## 総括

**AC3: PASS。** 単一コマンドで実行し、終了コード0・service active・`configuration_hash`不変・4ルールのDB存在・ログ上のprovisioningエラー無し・muteの発動・手順5/6の実行(省略ではない)をすべて実測で確認した。**パネル7枚の目視確認とUI上のProvisioned表示確認はTesterの範囲外であり、Yoshinobuへの依頼事項として本ファイル末尾に明記する。**

## 実行したコマンド(requirement/plan/playbookヘッダの指定どおり、`--tags provider`と`--tags alerting`を分離していない)

```
ansible-playbook playbooks/grafana_provisioning.yml \
  --tags provider,alerting -e alert_rules_predecessor_confirmed=true
```

## 実測結果

### 終了コード

`${PIPESTATUS[0]}`で直接取得。**実測値: `0`**(期待値`0`と一致)。

### PLAY RECAP

```
monnie : ok=23  changed=4  unreachable=0  failed=0  skipped=1  rescued=0  ignored=0
```

`changed=4`の内訳(タスク名で特定): provider yaml配置(`Deploy dashboard provider yaml to monnie`)、alerting YAML配置(`Deploy alerting YAML to monnie`)、mute設定(`Recovery mute | set/extend mute atomically under flock (monnie)`)、`grafana-server`のrestart(`Restart grafana-server`)。`skipped=1`は「alertingが配られなかった場合のNoteタスク」で、このrunではalertingが配られたため**このタスク自身がskipされた**(=手順5/6は実行された。詳細は下記「手順5・6」節)。

preflight(nameベースdatasource参照検査、repo↔ホストSHA256比較、alerting top-levelキー検査)はすべて`ok`で完走し、7枚とも`match: true`(Step 1と同一のSHA256、変化なし)。

### `grafana-server` がactiveであること

playbook完了直後、`ansible monnie -m systemd -a "name=grafana-server" -b`で独立に確認(read-only)。

```
ActiveState: active
ActiveEnterTimestamp: Thu 2026-07-30 19:04:18 JST
```

restart時刻(ログのshutdown記録 19:04:18)と一致し、restart後に再度活性化していることを確認した。

### `alert_configuration.configuration_hash` の不変性

playbook内のassert(`grafana_provisioning_expected_configuration_hash`との比較)がPASSした(`ok`、fail無し)ことに加え、**Testerが独立にread-only(`mode=ro`)で再クエリして実測値を記録する**(要求どおり)。

```
python3 -c "import sqlite3; conn = sqlite3.connect('file:/var/lib/grafana/grafana.db?mode=ro', uri=True); ..."
→ c6c0ff263e3ebf225d478e187c42cd99
```

**期待値`c6c0ff263e3ebf225d478e187c42cd99`と完全一致。** policy treeとcontact pointに触れていないことの機械的証拠が独立クエリでも裏付けられた。

### 4ルールが`alert_rule`テーブルに存在すること

playbook内のassert(`count == 4`)がPASS。Testerが独立にuid/titleを再クエリ:

```
('dfoih9pbfckxsf', 'UniFi Switch TX Drop')
('bfoii89j7l88wf', 'UniFi Switch RX Drop')
('dfoiihloh6hogd', 'UniFi Switch TX Error')
('dfoiiku15evi8e', 'UniFi Switch RX Error')
```

4件とも存在し、旧UIDとタイトルの記録(requirement R4)と一致する。**旧ルールが残っている(重複)兆候は無い** — 4件ちょうど。

### restart後のログにprovisioningエラーが無いこと

playbook内のassert(`provisioning`と`error`を同一行に含む行が0件)がPASS。Testerが独立に同じ論理(`grep -iE provisioning | grep -iE error`、パイプで両条件のAND)を`journalctl -u grafana-server --since '10 minutes ago'`に対して再実行し、**マッチ0件(grep終了コード1=不一致)を確認した。**

ログには通常のprovisioning関連の`info`行(`module stopped module=provisioning`、`Shutting down workers... logger=provisioning-repository-controller`など、いずれも正常シャットダウン記録)と、無関係な`error`行(elasticsearch/zipkin datasourceプラグインプロセスの正常終了時のerror表記、`signal: terminated`)が別々に存在するが、**両語を同一行に含む行は無い。**

### muteが張られたこと

タスク`Recovery mute | set/extend mute atomically under flock (monnie)`が`changed`(実測)。理由文字列(`recovery_mute_reason`)は`"grafana_provisioning: grafana-server restart for provider/alerting deploy"`、対象`monnie`、`{{ grafana_provisioning_mute_minutes }}`(defaults上15分)。**mute自体の中身(値)は機密情報ではないため記録した。**

### 手順5・6が「省略」ではなく「実行」されたこと

タスクリストで直接確認した。

- `Count the 4 provisioned alert rules in alert_rule table (read-only)`: **`ok`**(実行された)
- `Assert all 4 provisioned alert rules exist`: **`ok`**
- `Fetch grafana-server log since restart (read-only)`: **`ok`**
- `Assert no provisioning error appears in the post-restart grafana-server log`: **`ok`**
- `Note: alert rule / log verification was skipped (alerting was not deployed in this run)`: **`skipping`**(このNoteタスク自体がskipされた=否定条件`not grafana_provisioning_alerting_deployed_this_run`が偽だった、すなわち**alertingは配られた**)

「省略しました」というdebugメッセージは出ていない。異常は無い。

## 再実行しなかったこと・実施しなかったこと

- **再度同じコマンドを実行して冪等性(2回目`changed=false`)を確認することはしなかった。** AC3の受入条件はこの1回の実行の結果を問うものであり、requirementが要求する観測項目をすべて満たした時点で追加の実行は工程の積み増しと判断した。冪等性はplan §1-6が構造的に導出しており(providerもalertingも内容一致で`changed=false`になる設計)、今回の初回実行がchangedになったこと自体が想定どおり(初回のprovider/alerting配備)である。
- **`sqlite3`のCLIバイナリはmonnie上に存在しない**(`rc=127 not found`)。playbook自体はCLIを使わずpython3の`sqlite3`モジュールを使っており影響は無いが、Tester独立確認でも同じpython3手法を用いた(結果は上記のとおり)。

## Yoshinobuへ依頼した項目 — **2026-07-30に両方OKで完了**(Coordinator追記)

Yoshinobu回答(2026-07-30): 「1。OK、2。OK。**Provisionedというのは初めてみた。**」

- **1: 7枚のパネル描画 → OK。** 07-12はサービスactiveのまま全パネルがdatasource未解決だったため、`active`では代替できない確認だった。これでStep 2のAC3が全項目PASSとなり、**Step 2はクローズ可能**になった。
- **2: UI上のProvisioned表示 → OK。** DB側の `provenance_type` が `('<uid>', 'alertRule', 'file')` を4件持つことはCoordinatorが別途read-onlyで確認済みであり、**UI表示がそれに追随していることが目視で裏付けられた。** 「Provisionedを初めて見た」という反応は想定どおり — 本案件が導入した状態であり、これ以降アラート4件はUIから編集できない(それが目的)。

### 以下は依頼時点の記述(経緯として保持)

## Yoshinobuへ依頼が必要な項目(Testerは判定しない)

1. **7枚のパネル描画の目視確認。** admin資格情報を新設しない設計のため、Testerは機械化できない(requirement AC3が明記)。Step 1のAC2検証で判明したとおり、Grafanaの内部状態(`resource`テーブルの`generation`/`sourceTimestamp`)で反映自体は確認可能だが、**「意図どおりに見えるか」はUI目視でしか判定できない。**
2. **UI上で4ルールがProvisioned表示になっていることの確認(R8手順3)。** DB上の存在とログの健全性はTesterが確認したが、Grafana UIのProvisioned badge表示そのものはブラウザ操作を要するためTesterの範囲外。

## 残存リスク・未解決事項

- **通知の実発火(AC4)は本Stepの対象外。** requirement §11がAC4を「次回実発火時のWatch」として案件クローズの必須条件から除外済み。今回の配備で発火条件・通知先(`notification_settings.receiver: slack-homelab`)自体は変更していないため、次に実際のpacket error/dropが発生した時点で機器名・port・実測値を含む通知本文になっているか(annotations実測値追加の効果)が初めて確認できる。
- **Q3(alerting provisionerが`unifi` providerの作った`folder: UniFi`を参照できるか)は今回の実行結果から「参照できた」と読める。** 4ルールがDBに存在し、folder参照失敗を示すログ・DB不在のいずれも観測されなかったため、計画§1-4が懸念していた失敗モードは発生しなかった。ただしこれは1回の実行結果からの推論であり、Grafana公式ドキュメントでの裏付けが取れていない点は計画時点から変わっていない(未確認のまま残る、と明記しておく)。
- **mute窓(15分)の間、通知が一時的に抑制される。** これは意図された挙動(自律復旧の誤発火を防ぐ)であり、Slack通知そのもの(alertルール発火時の通知)を抑制するものではない — 抑制対象は`recovery_push_targets`側の自律復旧処理であり、Grafana alertingの評価・通知そのものはmuteの影響を受けない(requirement/planの設計上の理解。今回の検証ではこの区別自体を実地で確かめてはいない)。
- **`journalctl`のエラー検出パターン(`provisioning`+`error`同一行)は、実際の失敗ログでの検証がまだ無い。** 今回は「エラーが無いこと」の確認に留まり、意図的に失敗させてパターンが機能することを確かめる検証は行っていない(計画・レビューが明記している既知の制約と同じ)。

## 判定に迷った点(結論を作らず記録)

- **mute設定タスクが`changed`だったことをどう解釈するか。** `recovery_mute/tasks/set.yml`は「新規設定または延長」を`changed`として扱う設計であり、今回が新規設定だったのか延長だったのかをタスク出力から区別していない(register出力を詳細に見ていない)。AC3の受入条件自体は「muteが張られたこと」であり新規/延長の区別を要求していないため今回はここで止める。区別が必要になった場合はCoordinatorへ判断を委ねる。
- **journalctlの検索窓を「10分前から」で独立確認した点。** playbookの実装は`restart_and_verify.yml`内で`date`コマンドにより取得したrestart開始時刻を`--since`に使っており、Testerの独立確認は簡易的に「10分前」を使った。今回はrestart自体が数分前だったため実害は無いが、より長い時間が経過してからの事後検証では時刻の取り違えに注意が必要(次回以降の検証者への申し送り)。

## 到達してはいけない状態の確認

- **配備は完了した**(途中停止なし)。
- `/etc/grafana/provisioning/`以外のGrafana設定、`grafana.db`への書き込みは発生していない(`grafana.db`への確認クエリはすべて`mode=ro`のread-only、`/etc/grafana/provisioning/{dashboards,alerting}/`への書き込みのみがplaybookのcopyタスクで発生)。
- **repoの作業ツリーに、本ファイル以外の変更は生じていない。** `git status --short`は空。実装差分(U3)は本セッション開始前にYoshinobu自身によって既にcommit済み(`a2b0367 grafana dashboard deploy step2`、2026-07-30 19:02:55、本playbook実行より前)であることを確認した — Coordinatorが用意した「stageされている差分」は本検証開始前に既にcommit状態へ移行しており、本検証ではstage操作・commit操作を一切行っていない。
- `git add`/`commit`/`push`は行っていない。
- Grafana資格情報・Slack webhook値は本ファイルに記載していない。journalctlの抜粋にはリモートアドレス(IPv4)を含む行があったため、**該当行は転記から除外し、IPを含まない行のみ抜粋した。**

  **ただし当初、この除外を説明する文そのものに実IPを書いていた**(2026-07-30、Coordinatorがstage時の機械検査で検出し削除)。`docs/ai/memory/lessons/` に相当する既知の欠陥クラスであり、**「IPを書いていない」と宣言する文が違反する**という形で現れた。ログ転記時は宣言ではなく `grep -E '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'` で機械的に確認する。

## 対象パス一覧

- 対象playbook: `/home/yoshi/homelab-ansible/playbooks/grafana_provisioning.yml`
- 対象role: `/home/yoshi/homelab-ansible/roles/grafana_provisioning/`
- 対象host: monnie(inventory: `/home/yoshi/homelab-ansible/inventories/homelab/hosts.yml`)
- 本ファイル: `/home/yoshi/homelab-ansible/docs/ai/reviews/grafana_provisioning/2026-07-30_011_test_result_step2.md`
