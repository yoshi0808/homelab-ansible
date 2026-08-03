# review: Phase 4 Step 2 / Step 3 — `incident_sync` の退役 + 月次評価の入力移設

日付: 2026-08-03 (JST)
対象: commit `7904ba2`(1つ前 `e07e48a`)
plan: `2026-08-03_015_plan_phase4.md` §4 Step 2 / Step 3
requirement: `2026-08-02_001_requirement.md` R14b
implement記録: `2026-08-03_017_implement_phase4_step2_3.md`(現物で裏取りした上で参照。記載の判定・検証済みの主張は鵜呑みにしていない)
担当: Reviewer(独立。本変更の実装には関与していない)

## 確認範囲・手段

- `git show 7904ba2` / `git diff e07e48a 7904ba2` を全文読了(2589行)。
- `docs/ai/core.md`、`docs/ai/roles/reviewer.md`、`2026-08-03_015_plan_phase4.md` §4、`2026-08-02_001_requirement.md` R14b、`docs/ai/role-routing-index.md`「無人実行されるCoordinator」を読了。
- `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh` を読み、`bundle-list` / `bundle-show` / `investigation-show` の実装と許可リストを確認(diff外だがStep3が依存する現物)。
- `inventories/homelab/hosts.yml`、`inventories/homelab/group_vars/{dev_nodes,control_nodes}.yml`、`inventories/homelab/host_vars/quory.yml` を読み、`dev_nodes`/`control_nodes` の接続identity(`ansible_user: ann`)を確認。
- `docs/ai/reviews/dev_prod_boundary/2026-08-03_013_test_result_phase3_quory.md` で `quory-investigate` エイリアスが `dev-investigate` ユーザー・専用鍵であり `ann` ではないことをTester記録から確認。
- `roles/knowledge_review/templates/job-settings.json.j2` の現物を読み、本diffで変更されていないこと(`git diff` に当該ファイルが出現しない)を確認。
- `ansible-playbook playbooks/incident_sync_teardown.yml --syntax-check` をローカルで実行(実ホストへは一切接続しない構文検査)。
- ansy自身のローカルファイルシステム上で `reports/incidents/`・`_sync/` の所有者・パーミッションを `ls -la` / `getfacl` / `id ann` / `groups yoshi` で確認(このセッション自身がansy上で動作しており、ansible実行や他ホストへのSSHは行っていない)。
- `grep` でリポジトリ全体を横断し、`incident_sync` / `incident-sync` の残存参照を洗い出し、implement記録§7の申告と突合。
- **実行していないもの**: `incident_sync_teardown.yml` の実行(`--check`含む)、quoryへの接続、`dev-investigate`/`ann`鍵での実SSH。

## Summary

Step 2(`incident_sync`退役)とStep 3(滞留カウントのdispatch移設)はいずれも設計として妥当で、退役の消し残しは実質無く、`ann`への依存もない。取得失敗と0件の区別、`--check`時の扱い、月次prompt側の記述もrequirementの制約と整合している。**一方、`incident_sync_teardown.yml`(未実行)に、実行すれば確実に失敗する権限設計の誤りをCritical 1件検出した。** これは「実行前にここで見ておく」ことが目的の検査項目そのものであり、今のまま実行すると一部タスクが権限エラーで失敗する。Major/Minorはドキュメントの陳腐化に関するもの。

### Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `playbooks/incident_sync_teardown.yml` | 93-112(特に99-107)、および87-91 | **quory側play(`hosts: quory`)が`become: false`のまま、`ann`接続で`/home/yoshi/.ssh/`配下のファイル削除を試みる。実行すると権限エラーで失敗する。** `hosts: quory`はデフォルトで`inventories/homelab/group_vars/control_nodes.yml`の`ansible_user: ann`経由SSH接続になる(quoryから自己実行しない限り)。削除対象の`/home/yoshi/.ssh/id_incident_sync_trigger`等は、削除済み`roles/incident_investigate/tasks/sync_trigger.yml`が`become: true`(root)で生成後`owner: yoshi mode: 0700`の`.ssh`配下に置いたものであり、`ann`は「other」権限しか持たず(ACLも無い — ACLはrecovery-exec/dev-investigate専用でannには付与されていない)、`.ssh`ディレクトリへのtraverseすら不可能。100行目のコメント「quory's own yoshi, not root — no become needed」は、**「ファイルの所有者がyoshi」であることと「SSH接続identityがyoshi」であることを混同している** — 接続はannであり、yoshiではない。同型の誤りが87-91行目のansy側task(`_sync`ディレクトリ削除)にも別形で存在する: `reports/incidents/`はowner=yoshi group=yoshi mode=`drwxr-xr-x`(実機`ls -la`/`getfacl`で確認済み、ACLなし)であり、`ann`は「other」でr-xのみ、書込不可。`become: false`を明示しているため、この1taskだけ`ann`のまま実行され、親ディレクトリへの書込権が無く`_sync`削除は失敗する。<br><br>**影響**: 一度きりの後始末playbookが、意図した対象(ansy側unit・landing account・sudoers・wrapperの削除)の大部分は成功する(それらは`become: true`)が、`_sync`状態ディレクトリの削除とquory側鍵材料の削除が失敗し、非ゼロ終了で止まる。ヘッダコメント(30-35行目)の「tester-gate: check-mode-native — `--check` previews accurately with no custom gating needed」も、quory側の`.ssh`が0700である以上`--check`下でも`lstat`自体が権限エラーになりうるため、正確性が崩れている可能性が高い(未実行のため未確定だが、mode 0700への非ownerアクセスはstatの試行自体が失敗するのが通常の挙動)。<br><br>**修正の方向**: quory側playに`become: true`を追加する(quoryの`ann`は`NOPASSWD: ALL`を持つため技術的には可能。R15削除前の現時点ではこの経路が唯一の実行手段でもある)。ansy側の87-91行目も同様に`become: false`を外すか、あるいは元の設計どおり`hosts: localhost, connection: local`(yoshiとして実行)に寄せるかを検討する必要がある。 | **Critical** |

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `docs/ai/policies/incident_capture_policy.md` | §4「転送の規律」全体(IC-012〜IC-015)、IC-021、IC-031、IC-032 | `incident_sync`退役後もPolicyが「転送は周期実行」「ansy側の同期先はミラーである」等、現存しない機構を現在形で規範として述べたままになっている(実測: grepで該当文言の残存を確認)。実装スコープ外という判断自体は妥当(Policy改訂はImplementerの権限外、Coordinator/Yoshinobu判断とimplement記録§8が正しく明記している)が、**Phase 4クローズ(plan §4 Step 10)前にこの改訂要否を決めないと、規範文書が実装と食い違ったまま残る。** `document-norm-review`の観点(規範の消失・撤回した根拠の残存)に該当するため、Coordinatorへ改めて明示する。 | 規範文書の整合性 |
| 2 | `roles/knowledge_review/tasks/incident_metrics.yml` | 全体(特に210行目台のdispatch呼び出し2箇所) | 設計・実装は妥当(V3の失敗/0件区別、`last_bundle_id_seen`のロールバック回避、`--check`時の未接続維持は確認できた)。念のための指摘: `bundle-show`のoperandに使う`knowledge_review_incident_metrics_oldest_new_id`は正規表現フィルタ済みの整数のみに由来し、shell注入経路は無い(`argv:`形式でSSH側もforced commandが`SSH_ORIGINAL_COMMAND`を`read`で固定arityパースする構成であることを`recovery-investigate-dispatch-quory.sh`で確認済み)。**追加の対応は不要** — 確認結果として記録に残す。 | セキュリティ(確認のみ・問題なし) |
| 3 | `playbooks/incident_sync_teardown.yml` | 30-35(ヘッダコメント) | Critical #1の修正に伴い、`become:`構成を変えた場合はこのヘッダコメントの「no other host is touched」「every task uses a module with native check_mode support」等の記述も実態に合わせて更新すること。 | ドキュメント整合性 |

## What Looks Good

- **`ann`への依存が無い(検査項目2)**: Step 3の新規dispatch呼び出しは`knowledge_review_incident_dispatch_alias: quory-investigate`(`roles/knowledge_review/defaults/main.yml`)を使い、これは`dev-investigate`ユーザー・専用鍵(`~/.ssh/id_claude_investigate_quory`)を指すことをTester記録(`2026-08-03_013_test_result_phase3_quory.md`)で確認した。`ann`という文字列はStep 2/3の新規コード・変更コードのいずれにも出現しない。
- **取得失敗と「成功して0件」の区別(検査項目3)**: `knowledge_review_incident_metrics_bundle_list_ok`のrc判定により、失敗時は`mirror_bundle_total: null`+`bundle_fetch_error`に理由文字列、成功0件時は`mirror_bundle_total: 0`+`bundle_fetch_error: ""`と明確に分岐する設計をコードで確認した。`incident_evaluation.yml`の`FETCH_ERROR`分岐が`NO_DATA`より先に評価されるため混入しない。
- **無人Coordinatorの権限プロファイル(検査項目4)**: `roles/knowledge_review/templates/job-settings.json.j2`は本diffで一切変更されておらず(diffに出現しない)、現物を読んでも`Bash`は引き続き`deny`、allowlistも変更前と同一である。Step 3が新設したdispatch呼び出し(`ssh quory-investigate bundle-list`等)は`incident_metrics.yml`内の通常のAnsible `command`タスクとして、timerが起動する`ansible-playbook`プロセス自身が実行するものであり、`claude -p`無人セッションの内部から呼ばれるものではない(`roles/knowledge_review/tasks/main.yml`の呼び出し順で確認 — `include_tasks: incident_metrics.yml`は`claude -p`起動タスクとは別の独立タスク)。無人Coordinatorの読み書き境界は変わっていない。
- **退役の完全性(検査項目1)**: `roles/incident_sync/`一式・3 playbook・`sync_trigger.yml`の削除を確認。リポジトリ全体を`incident_sync`/`incident-sync`でgrep横断した結果、残存参照はimplement記録§7が申告した集合(経緯コメント群、新設teardown playbook、ADR 2本、status.md、未着手のPolicy改訂)と完全に一致し、申告漏れの宙ぶらりん参照は見つからなかった。削除された変数(`knowledge_review_incident_mirror_dir`、`knowledge_review_incident_heartbeat_max_age_s`)への参照も横断grepでゼロ件を確認した。`playbooks/incident_evaluation.yml`(本diff対象外)を含め、他の呼び出し元も削除済み変数を参照していない。
- **月次promptの記述精度(検査項目6)**: `incident-review-prompt.md.j2`は「このセッション自身はdispatch/SSHでquoryへ問い合わせられない」「`reports/incidents/quory/`は凍結スナップショットで新規バンドルは増えない」「読めない場合は推測で埋めず明記する」と明記しており、N2/N3(Yoshinobuが却下した「評価直前に本文を事前取得する」案の帰結として本文が読めないことは既知の受容である)の前提と一致する。虚偽・過大な主張は無い。
- 削除対象ファイルの範囲(`roles/incident_sync/`一式、3 playbook、`sync_trigger.yml`)は要求と一致し、`roles/dev_investigate`など無関係roleには触れていない。
- `--syntax-check`は全playbookで通過(自己申告どおり、本レビューでも`incident_sync_teardown.yml`を再実行し確認)。

## 未解決事項

1. Critical #1により、`incident_sync_teardown.yml`は現状のまま実行すると一部task(ansy側`_sync`削除、quory側鍵材料削除の全task)が失敗する。**実行前に`become:`の修正が必要。**
2. Suggestion #1(Policy `incident_capture_policy.md`の陳腐化)は、implement記録が既に未解決事項として認識しているものを本レビューで裏取りした。Phase 4クローズ前にCoordinator/Yoshinobuが改訂要否を判断する必要がある。
3. implement記録§4が指摘する「質的評価セッションが新規バンドルの内容を読めなくなる」という設計ギャップは、本レビューの検査項目6(promptの記述精度)の範囲では「正しく開示されている」ことのみを確認した。ギャップそのものの是非はCoordinator/Yoshinobuの判断事項であり、本レビューでは判定していない。

## Verdict

**Request Changes**(Critical #1が理由)。Step 2/3のAnsible role・playbook本体(`incident_metrics.yml`、`incident_evaluation.yml`、`incident-investigate.py`等)とrequirement/planとの整合性は問題ない。`incident_sync_teardown.yml`の`become`修正のみを行えば、Step 4完了として次工程(plan §4 Step 5以降)へ進める状態になる。

---

## Coordinator の処置(2026-08-03)

| finding | 処置 |
|---|---|
| **Critical**(`incident_sync_teardown.yml` の quory play が `become: false` のまま `/home/yoshi/.ssh/` 配下を削除しようとする。ansy 側 `_sync` 削除タスクも同型) | **指摘を現物で再現し、修正して実行した。** |

### 再現(実測、2026-08-03)

| 対象 | 実測 |
|---|---|
| ansy `reports/incidents` | `drwxr-xr-x yoshi:yoshi`。接続identityの `ann` は uid=1001 で yoshi グループに属さず、書込不可 |
| quory `/home/yoshi/.ssh` | `drwx------ yoshi:yoshi`。`ann` からは**一覧すらできない**(`Permission denied`)。削除対象の3ファイルは実在した |

**指摘のとおり、実行すれば確実に権限エラーで落ちる状態だった。** 原因は「ファイルの所有者が yoshi であること」と「SSH接続の identity が yoshi であること」の混同である。

### 修正

quory play を `become: true` へ、ansy 側 `_sync` 削除タスクから `become: false` を除去。**両方にその理由をコメントとして残した**(所有者と接続identityは別である旨)。

### 実行と検証(Coordinator が実施)

`--syntax-check` 通過後に実行。`ansy: ok=8 changed=6 / quory: ok=2 changed=2`、failed=0。

| 確認項目 | 結果 |
|---|---|
| ansy の `ansible-incident-sync.timer` / `.service` | `not-found`。残る ansible timer は `knowledge-review` のみ |
| ansy の `incident-sync-trigger` ユーザー | 削除済み(`getent passwd` で不在) |
| ansy の `_sync/` / wrapper / sudoers | いずれも削除済み |
| quory の `id_incident_sync_trigger{,.pub}` / `known_hosts_incident_sync_trigger` | 削除済み |

**quory → ansy の逆方向到達経路は、両端で閉じている** — quory 側は鍵材が消え、ansy 側は受け口ユーザーごと消えた。**片端だけでは不十分なので両方を確認した。**

**この検証は Phase 4 Step 5(鍵削除)より前に実施している。** Step 5 以降は `ssh quory` を失っており、dispatch のカタログにも `/home/yoshi/.ssh/` を読むチェックが無いため、**quory 側は今後この形で再検証できない。**

**レビューを通してから実行した判断がそのまま効いた。** 先に流していれば権限エラーで中途半端に止まっていた。
