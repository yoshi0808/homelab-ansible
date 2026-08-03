# Implement: 月次ジョブから claude -p を2本とも外し、きっかけ通知だけにする

日付: 2026-08-03 (JST)
Role: Implementer
対象: `roles/knowledge_review/`、`playbooks/knowledge_review.yml`

## 背景

2026-08-03、Yoshinobuが月次の見直しについて「私が主体的に見直します。…きっかけは
欲しいですが、ここでもclaude -pで独自に動いていただく必要はない」と決定した。
`docs/ai/policies/incident_capture_policy.md` の本日改訂(IC-005/IC-043/IC-044)が
この実装を縛る。改訂の全体像は
`docs/ai/reviews/dev_prod_boundary/2026-08-03_019_policy_revision_proposal.md`。

## やったこと

### 削除

- `roles/knowledge_review/tasks/incident_evaluation.yml`(2本目の claude -p 起動と成果物保存)
- `roles/knowledge_review/tasks/incident_index_write.yml`(`_evaluations/<date>-index.json` 書き出し)
- `roles/knowledge_review/templates/job-settings.json.j2`(本体claude -pの権限プロファイル)
- `roles/knowledge_review/templates/incident-job-settings.json.j2`(評価claude -pの権限プロファイル)
- `roles/knowledge_review/templates/review-prompt.md.j2`(本体claude -pのprompt)
- `roles/knowledge_review/templates/incident-review-prompt.md.j2`(評価claude -pのprompt)

`git rm` で削除すると同時にstageされてしまったため(`git status` の `D `列で確認)、
Implementerの禁止事項(`git add`をしない)に反すると気づき、`git reset -q --` で
対象6ファイルをunstageし直した。作業ツリー上は削除済み・indexは未staged。

### 書き換え

| ファイル | 変更内容 |
|---|---|
| `roles/knowledge_review/tasks/main.yml` | claude -p起動・作業ツリー清潔判定と中止(旧`ABORTED_DIRTY`)・auto-memoryスナップショット・Slack preflight・`Save report`・`Collect resulting diff`・`Build summary`を全削除。残るのは状態ディレクトリ確保・実行時刻記録・MEMORY.md次回期日更新(常時実行、`--check`のみ抑止)・`incident_metrics.yml`のinclude、の4手順のみ |
| `roles/knowledge_review/tasks/incident_metrics.yml` | 全面書き換え(後述) |
| `roles/knowledge_review/defaults/main.yml` | claude関連変数(`knowledge_review_claude_bin`/`_model`/`_timeout`/`_allow_dirty`)、評価成果物置き場(`knowledge_review_incident_eval_dir`)、評価用claude変数(`_incident_timeout`/`_incident_model`)を削除。新規に`knowledge_review_incident_notify_enabled`・`knowledge_review_incident_notify_state_file`・`knowledge_review_incident_retention_days`(90、`roles/incident_capture/defaults/main.yml`の複製である旨を明記)を追加 |
| `roles/knowledge_review/templates/knowledge-review.service.j2` | `TimeoutStartSec`の2本のclaude -p合計に基づく式を削除し、dispatch呼び出し(最大2往復)を前提にした固定値`300`へ |
| `playbooks/knowledge_review.yml` | ヘッダコメントとpost_tasksのSlack通知を全面書き換え(後述) |

## 契約の充足状況

### 残すもの(要求どおり)

- **systemd timer**: `roles/knowledge_review/templates/knowledge-review.timer.j2` は無変更。毎月26日07:15 JST起動のまま
- **dispatch経由の件数取得**: `tasks/incident_metrics.yml` に残した。`ssh quory-investigate`経由(`knowledge_review_incident_dispatch_alias`)であり`ann`は使っていない(`grep`で確認、変更前後とも同じalias値)
- **Slack通知**: 「見直しの時期です」+ 未レビュー件数(`bundles_new_since_last_notify`)+ 最古バンドルの経過(`oldest_bundle.age_days`)を含む(実例は下記)
- **MEMORY.md次回期日更新**: `tasks/main.yml`にAnsibleタスクとして残した(LLM不関与)。実行確認済み(下記自己検証)

### 消すもの(要求どおり)

- claude -pの起動2本 → `grep -n "claude" roles/knowledge_review playbooks/knowledge_review.yml`で残るのは説明コメントのみ、実行タスク(`argv: [..., claude_bin, ...]`)は0件
- 権限プロファイル・prompt4ファイル → 削除済み。参照(`src:`/`dest:`)も0件
- auto-memoryスナップショット → `main.yml`から該当taskを削除
- 作業ツリー清潔判定と中止(`ABORTED_DIRTY`) → `main.yml`から`Check working tree is clean`/`Decide whether to abort`を削除。`git status`を見るtaskは本role内にもう存在しない
- `_evaluations/`置き場と`incident_evaluation.yml`/`incident_index_write.yml` → 削除済み。置き場を指す変数(`knowledge_review_incident_eval_dir`)も defaults から削除

### 通知の中身(IC-043/IC-044)

- **IC-044(差分の取りこぼし防止)**: 旧`_evaluations/<date>-index.json`スキャンに代えて、単一の状態ファイル
  `knowledge_review_state_dir/incident-notify-state.json`(repo外、`~/.local/state/knowledge-review/`)に
  `{generated_at, last_bundle_id_seen}`だけを持ち越す設計にした。バンドルIDの取得に失敗した回は
  前回値をそのまま引き継ぐため(`incident_metrics.yml`「次回比較の基準として持ち越すid」)、通知が
  ある回失敗しても次回の差分計算は取りこぼさない。
- **IC-043(保持期間満了の警告)**: 旧実装は「前回見直し以降の新着バンドルのうち最古」だけを見ていたが、
  保持期間はレビュー済みかどうかに関わらず経過日数だけで切れるため、**現存する全バンドルのうち
  最古のもの**(`bundle_ids | min`)を対象に設計し直した。`knowledge_review_incident_retention_days`
  (90)との差分`remaining_days`をSlack本文に含める。

### V4(取得失敗と成功0件の区別)

`incident_notify_index.bundle_fetch_error`が非空のときは専用の文面(「取得エラー: …」+
「件数・経過日数は取得できていません(0件ではなく取得失敗です)」)を出し、成功0件のときは
「バンドル総数: 0 件」「最古のバンドル: なし(バンドル0件)」という別の文面になる(実例は下記)。

## 通知本文の実例(自己検証。実Slack送信は抑止)

`/tmp`配下にdispatch呼び出しのdecoyスタブ(実quoryへは一切接続しない、固定出力を返すだけの
シェルスクリプト)を作り、`knowledge_review_incident_dispatch_ssh_bin`と
`knowledge_review_automemory_dir`/`knowledge_review_state_dir`を`-e`で上書きして
`ansible-playbook playbooks/knowledge_review.yml -i localhost, -c local`を実行した。
Bashツール実行環境は`CLAUDECODE=1`が立っており、`common_slack/tasks/notify.yml`の
suppression trigger3(AIエージェントセッション検出)が働いて実送信は自動的に抑止される
(`Send Slack notification`taskが`skipping`になることを確認済み)。実行はansy上のリポジトリ
作業ツリーと`/tmp`に閉じており、Coordinator/Testerが行う実ホスト検証ではない。

### シナリオ1: 通常(バンドル5件、前回以降3件新着、最古1件)

```
月次Knowledge見直しの時期です。判断はYoshinobuが対話セッションと行います
(このタイマーは、きっかけを通知するだけです。無人LLMは起動していません)。

対象:
- docs/ai/memory/incidents/ の滞留(状態: 調査中)・打ち切り(状態: 未解決)の再検討
- Coordinatorのauto-memoryの3分類仕分け(手順→skills / 環境固有の事実→lessons・context / 考え方→decisions)
- 工程を何周も往復した案件記録

次回のきっかけ通知予定: 2026-09-26
手順の正本: docs/ai/memory-classification.md「月次振り返りの対象と手順」

---
障害バンドルの滞留状況(quoryへのdispatch経由でのライブ取得):
バンドル総数: 5 件
前回通知(2026-07-26)以降の新着: 3 件
最古のバンドル: semaphore-10(63日前作成)
保持期限(90日)まであと27日
```

### シナリオ2: dispatch取得失敗(V4)

```
---
障害バンドルの滞留状況(quoryへのdispatch経由でのライブ取得):
取得エラー: bundle-list dispatch failed rc=255 stderr=ssh: connect to host quory port 22: Connection refused
件数・経過日数は取得できていません(0件ではなく取得失敗です)。
```

### シナリオ3: 成功して0件(V4、シナリオ2と区別できることを確認)

```
---
障害バンドルの滞留状況(quoryへのdispatch経由でのライブ取得):
バンドル総数: 0 件
前回通知(初回)以降の新着: 0 件
最古のバンドル: なし(バンドル0件)
```

## 自己検証で確認したこと

| # | 確認内容 | 手段 | 結果 |
|---|---|---|---|
| V1 | `roles/knowledge_review/`・`playbooks/knowledge_review.yml`のどこからも`claude`が起動されない | `grep -n "claude"` で全マッチを目視、`argv:`/`cmd:`行に`claude`が無いことを確認 | 満たす(説明コメントのみ残存) |
| V2 | 消したprompt/権限プロファイルへの参照が残っていない | `grep -rln "job-settings.json\|review-prompt.md\|incident-job-settings\|incident-review-prompt"` をrole全体+対象playbookに実施 | 満たす(ヒットなし) |
| V3 | 通知本文が件数・最古バンドル・残り日数を含んで正しく描画される | decoyスタブでの実プレイブック実行(上記シナリオ1)、`debug`出力の`message`フィールドを直接確認 | 満たす |
| V4 | 取得失敗時に成功0件と区別できる本文になる | decoyスタブでのシナリオ2・3の実行比較 | 満たす |
| V5 | `--check`と通常実行の双方で構文・lintを通る | `ansible-playbook --syntax-check`(pass)、`ansible-lint playbooks/knowledge_review.yml roles/knowledge_review`(4件のfatal分類だが、いずれも変更前から存在した種別: 契約factの`var-naming[no-role-prefix]`2件・`install_timer.yml`の`command-instead-of-module`1件・`common_slack/tasks/notify.yml`の`yaml[line-length]`1件。変更前は同roleで8件、うち新設カテゴリはゼロ。git stashで変更前後を比較して確認)。`--check`実行はdecoyスタブ経由で完走し`changed=0`、state file/MEMORY.mdとも無変更(diffで確認) | 満たす(新規lint違反ゼロ、pre-existing分類のみ残存) |
| V6 | 終了状態をパイプ越しに測っていない | `grep -n "| head\||head\| | tail\||tail"` を対象ファイル全体に実施 | 満たす(該当なし。全てのrc判定は`register`の`.rc`属性を直接参照) |

## 未解決事項(Coordinatorへの申し送り)

**`playbooks/incident_evaluation.yml` が壊れた状態になっている。** このplaybookは
「障害の自動評価だけを手動で回す」ための専用エントリで、本roleの
`tasks_from: incident_metrics` → `tasks_from: incident_evaluation` →
`tasks_from: incident_index_write` を`include_role`で個別に呼ぶ構造だった。

今回、後半2つのtasks(`incident_evaluation.yml`/`incident_index_write.yml`)を削除し、
前提変数`knowledge_review_incident_eval_enabled`も`knowledge_review_incident_notify_enabled`
へ改名したため、このplaybookは実行時に確実に失敗する。実際に
`ansible-playbook playbooks/incident_evaluation.yml -i localhost, -c local -e knowledge_review_allow_dirty=true`
を試行し、

```
Error while evaluating conditional: 'knowledge_review_incident_eval_enabled' is undefined
```

で即座に失敗することを確認した(`--syntax-check`は動的includeのため素通りする — このリポジトリの
既知の制約、`skills/ansible-implementation-style/SKILL.md`)。

このファイルは依頼のscope外(`roles/knowledge_review/`でも`playbooks/knowledge_review.yml`でもない)
のため変更していない。このplaybookの唯一の存在理由(削除した評価段の手動起動)自体が
無くなったため、**削除が妥当と考えられる**が、判断はCoordinatorに委ねる。

その他の未解決事項:

- `roles/knowledge_review/tasks/incident_metrics.yml`のIC-043実装は「現存する全バンドルのうち
  最古のもの」を対象にする設計へ変更した(旧実装は「前回見直し以降の新着のうち最古」)。
  これは要求文言「最古のバンドルがあと何日で消えるか」への私の解釈であり、Policy本文には
  数値的な意図の記載が無い。Yoshinobuの意図と異なる場合は再設計が要る。
- `remaining_days`が負値(保持期間超過)になりうる設計のまま実装した(clampしていない)。
  意図的な設計判断(超過そのものが有用な情報になりうるため)だが、明示の要求ではない。
- Slackステータス色は`incident_notify_summary`が`FETCH_ERROR`のときのみ`warning`/`alerts`とし、
  `remaining_days`が小さい(保持期限が近い)ケースでの自動エスカレーションは実装していない
  (要求・Policyのいずれにも閾値の指定が無いため、恣意的な閾値を持ち込まなかった)。
