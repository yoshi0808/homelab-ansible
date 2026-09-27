# diff review (test files only): proxmox_patch_notifications_2b

査読者: Reviewer (差分レビュー、追加分) / 2026-09-27
対象: stage済み差分のうち、以下roleの `tests/` 配下の追加・変更ファイルのみ。
- roles/proxmox_evacuate_node/tests/run_failure_notification.sh (新規)
- roles/proxmox_evacuate_node/tests/test_failure_notification.yml (新規)
- roles/proxmox_restore_vm_placement/tests/run_failure_notification.sh (新規)
- roles/proxmox_restore_vm_placement/tests/test_failure_notification.yml (新規)
- roles/proxmox_patch_apply_node/tests/_eval_notify_case.yml (変更)
- roles/proxmox_patch_apply_node/tests/_eval_one_stop_case.yml (新規)
- roles/proxmox_patch_apply_node/tests/_eval_weekly_full_completion_case.yml (新規)
- roles/proxmox_patch_apply_node/tests/test_notify_stop_reason.yml (新規)
- roles/proxmox_patch_apply_node/tests/test_notify_warning_on_critical.yml (変更)
- roles/proxmox_patch_apply_node/tests/test_weekly_full_completion_notify.yml (新規)

経緯: `_006_fix_review.md`(再レビュー)はrole本体差分のみを対象とし、上記テストファイルは未査読のまま(`_007_audit.md`指摘3)。本ファイルはその欠落分を埋める。役割本体側(`roles/*/tasks/main.yml`、`playbooks/proxmox_patch_weekly_full.yml`)は`_004`/`_006`で査読済みのため、本ファイルは対象テストファイルと、それが役割本体を正しく写しているかの突合に絞る。

## 確認した手段

- `git diff --cached`で対象ファイルを全文読み、対応する役割本体(`roles/proxmox_evacuate_node/tasks/main.yml`、`roles/proxmox_restore_vm_placement/tasks/main.yml`、`roles/proxmox_patch_apply_node/tasks/main.yml`、`playbooks/proxmox_patch_weekly_full.yml`)の該当箇所と突合した。
- `roles/proxmox_evacuate_node/tests/run_failure_notification.sh`と`roles/proxmox_restore_vm_placement/tests/run_failure_notification.sh`を実際にlocalhostで実行し、全6シナリオPASSを確認した(`CLAUDECODE=1`が設定されるためSlack実送信は発生しない、`roles/common_slack/tasks/notify.yml`のtrigger3で確認済み)。実行後 `git status` とincident capture spool(`reports/incidents/_spool/`)を確認し、残骸が無いことを確認した。
- `roles/proxmox_patch_apply_node/tests/test_notify_stop_reason.yml`、`test_notify_warning_on_critical.yml`、`test_weekly_full_completion_notify.yml`をlocalhostで実行し、全てPASSを確認した。
- 実験的に最小限のfixture(`/tmp`、レビュー後削除済み)を作り、named blockの中の無名`ansible.builtin.fail`タスクで`ansible_failed_task.name`が空文字列になることを実測で確認した(下記Major 1の根拠)。
- 実ホスト・ssh・git add/commitは行っていない。

## 所見

### Major

**1. `proxmox_patch_apply_node`のabort系テストが、失敗task名を導出する実ロジック(dict lookup)を一切通していない。**

`roles/proxmox_patch_apply_node/tasks/main.yml`のrescueブロック(今回の差分)は、`_apply_failed_task`を次の式で決める。

```
_apply_failed_task: >-
  {{ (ansible_failed_task.name | default('', true) | trim)
     if (... | length > 0)
     else { 'control_node': '...', 'vms_not_evacuated': '...', ... }.get(_apply_abort_type, 'Unknown task during patch apply') }}
```

実測で確認した通り、各abort分岐(`control_node`、`vms_not_evacuated`、`healthcheck`、`apt_update`、`apt_check`、`sim_failed`、`maintenance_required`/`major_upgrade_detected`、`blocked_important_remove`、`manual_not_confirmed`、`download_failed`、`apply_failed`の11種)は、いずれも名前の無い`ansible.builtin.fail:`タスクをblock内で呼んでおり、`ansible_failed_task.name`は常に空文字列になる。つまりこのdict(13エントリ)は「フォールバック」ではなく、**上記11のabort種別すべてで実際に使われる唯一の経路**である(`reboot_timeout`だけは名前付きタスク`Reboot if required`が失敗するため、dictの値と名前付きタスク名がたまたま一致しているに過ぎない)。

一方、`test_notify_stop_reason.yml`は`cases`に`failed_task: "Abort if VMs remain on target node"`のように**期待値をそのまま入力として与えて**`_eval_one_stop_case.yml`→`_eval_notify_case.yml`(通知本文組み立てテンプレートのみ)を評価している。実ロジック(上記dict)を経由するrescueブロックそのものは、`_eval_notify_case.yml`にも`_eval_one_stop_case.yml`にも存在しない。したがって、この新設テストが検証しているのは「`_apply_failed_task`という変数の値が正しく本文へ表示されるか」だけであり、「`_apply_abort_type`から正しい`_apply_failed_task`の値が導出されるか」は検証していない。dictのkeyと実際の`_apply_abort_type`文字列(例: `vms_not_evacuated`)が将来ずれても、このテストはPASSし続ける。

現時点でdictのkeyと実際に設定されている`_apply_abort_type`の13種は目視突合で一致を確認したが、この一致を機械的に保証する仕組みが無い。`test_notify_warning_on_critical.yml`が持つ「roleの式をgrepで突き合わせる」parity check(下記2参照)と同種の仕組みをこのdictにも設けるか、rescueブロックそのものを通す形にfixtureを組み替える必要がある。

**2. `test_notify_warning_on_critical.yml`のgrep-parityチェックは、今回追加された断片(package notes・failed_task/停止行・report行)を対象にしていない。**

同ファイル末尾の「Confirm the WARNING-subject branch is unchanged in main.yml」「Confirm the notify_status warning branch is unchanged in main.yml」タスクは、`roles/proxmox_patch_apply_node/tasks/main.yml`から2つの断片を`grep -F`で突き合わせる、まさに「roleの式を写している箇所が現在のroleと一致しているかを確かめる仕組み」である(前案件`proxmox_patch_judgment_2a`由来)。しかし今回`_eval_notify_case.yml`へ追加された次の断片には、この仕組みが適用されていない。

- 適用パッケージ一覧のループ(`{% for package in _apply_package_notes[:...] %}...{% endfor %}`、「ほかN件」行)
- 失敗task/停止scope行(`失敗task: {{ _apply_failed_task }}` / 「このnodeで停止しました。...」)
- report行(`report: {{ _apply_report_filename if ... else 'report保存失敗' }}`)

これらは`_eval_notify_case.yml`冒頭のコメントで「role本体と同一」と主張されているだけで、grep等による自動突合が無い。手動での`diff`確認はTester記録(`_005`)に残っているが、それは実行時点のスナップショットであり、以後の役割本体側の変更を継続的に検知しない。Major 1と合わせ、このrole全体で「fixtureのコピーが実ロジックからずれても検出できない」経路が複数残っている。

### Minor

**3. AC7(check mode)は、`run_failure_notification.sh`のコメント上「対象」と書かれているが、実際に`--check`を通すシナリオが無い。**

`roles/proxmox_evacuate_node/tests/run_failure_notification.sh`・`roles/proxmox_restore_vm_placement/tests/run_failure_notification.sh`双方の冒頭コメントは「Runs test_failure_notification.yml (... AC1 / AC1b / AC1c / AC3 / AC7) for every scenario」と書くが、`CASES`配列の6シナリオ(`healthcheck_fail`/`migrate_partial_fail`/`success`/`notify_body_fail`/`notify_include_fail`/`report_save_fail`)はいずれも`--check`を付けずに実行している。AC7自体は`_005_test_result.md`が「`--check`かつ`CLAUDECODE`を一時的にunsetして実行」というアドホックな手順でPASS判定を記録しており実施はされているが、その手順はこのスクリプトに組み込まれておらず、以後の回帰では再実行されない。ヘッダコメントの「AC7」は実態と一致しない(スクリプト単体を将来動かした人が「AC7もこれでカバーされている」と誤解する)。コメントを実態に合わせて修正するか、`--check`シナリオを1件追加することが望ましい。

**4. `run_failure_notification.sh`の一時ディレクトリ後始末は、`STAGE`のみ`trap`で保護され`REPORT_DIR`は保護されていない。**

`STAGE="$(mktemp -d)"`には`trap 'rm -rf "${STAGE}"' EXIT`が張られ、シナリオループ内での異常終了やSIGINTでも確実に消える。一方`REPORT_DIR="$(mktemp -d)"`は、ループ終了後の`rm -rf "${REPORT_DIR}"`という素の行でしか消えない。スクリプトがループ途中で中断(SIGINT等)された場合、`REPORT_DIR`だけ`/tmp`に残り得る。実害は小さい(`/tmp`配下の空/小容量ディレクトリで、システムの定期clean対象)が、`STAGE`と同じ`trap`にまとめる方が一貫する。evacuate/restore両スクリプトで同型。

## 確認した観測範囲(AC別)

- AC1/AC1b/AC1c/AC3/AC7の一部(evacuate): `run_failure_notification.sh`(evacuate)を実行しPASSを確認。通知本文の内容、成功分のみの一覧化、body/include失敗時の原失敗維持を確認。AC7は前述の通り本スクリプトではカバーされていない。
- AC2/AC1c(restore側)/AC3: `run_failure_notification.sh`(restore)を実行しPASSを確認。
- AC4: `test_notify_warning_on_critical.yml`を実行しPASSを確認。package毎の表示・CVE列挙・新規install表示・上限超過時の「ほかN件」表示を確認。ただし`_apply_package_notes`はfixtureの固定入力であり、これを生成する`roles/proxmox_patch_apply_node/files/proxmox-patch-changelog-collect.py`自体を呼ぶ委託テストは`tests/`配下に無い(`_005`のアドホック確認のみで、リグレッションとして残らない。今回のレビュー対象はテスト側の`tests/`ファイルのみのためこの`.py`自体は査読対象外だが、AC4の「何を観測していないか」として記録する)。
- AC5: `test_notify_stop_reason.yml`を実行しPASSを確認。ただしMajor 1の通り、失敗task名の導出ロジック(dict)自体は未検証。
- AC6: `test_weekly_full_completion_notify.yml`を実行しPASSを確認。`_eval_weekly_full_completion_case.yml`の式は`playbooks/proxmox_patch_weekly_full.yml`の該当箇所と`diff`相当の目視突合で一致を確認したが、Major 2と同様、自動parity checkは無い。
- AC8/AC8b: 各roleのreport行が basenameのみを参照していること、`report_save_fail`シナリオで`report保存失敗`が出ることを実行で確認。
- AC9: 本レビューでは対象外(`_005`/`_007`が扱う)。

## 未確認事項

- 退避・復帰roleの強制停止(force-stop)側loopの部分成功パターンは、いずれのfixtureにも無い(`_005`が既に記録済みの既知ギャップで、今回の追加ファイルもこれを埋めていない)。
- `proxmox-patch-changelog-collect.py`自体のtimeout分岐・実際の`apt-cache changelog`呼び出しは、`tests/`配下のいずれのファイルからも呼ばれていない。

## 総合判定

Major 2件(いずれもnon-Critical: 実ホスト・本番影響は無いが、AC5の中核ロジックとAC4/AC6のfixture-role同期を保証する仕組みが欠けており、将来の役割本体側の変更をテストが検知できない)。Minor 2件。テスト自体は現時点でPASSしており実行安全性(残骸・実送信無し)にも問題は無い。Major 2件の解消をCoordinatorの判断でクローズ条件に含めるか検討されたい。

---

## Coordinatorの対応(2026-09-27)

4件とも同意し、Testerが修正した(`_005` の2026-09-27追記)。Major 1は停止通知のテストがrole内の辞書を実際に通る形になり(15 cases)、Major 2はparity checkを `_eval_notify_case_parity.yml` と weekly full完了通知のテストへ入れた。Minor 3・4は `run_failure_notification.sh` にcheck modeのシナリオとREPORT_DIRのtrapを足した。Coordinatorが全テストを再実行して通ることを確かめた(evacuate / restore の実行スクリプトは各7シナリオPASS・rc=0、apply / dryrun / healthcheck の各testは `failed=0`、比較検証・収集失敗・codex_classifyもOK)。
