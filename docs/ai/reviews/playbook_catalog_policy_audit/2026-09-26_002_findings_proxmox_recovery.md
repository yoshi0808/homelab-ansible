# Policy↔実装 食い違い監査: Proxmox運用 / バックアップ検証 / 自律復旧 / 障害捕捉

- 日付: 2026-09-26
- 対象Policy: `docs/ai/policies/proxmox_operations_policy.md`(SB)、`proxmox_backup_restore_verify_policy.md`(BRV)、`autonomous_recovery_policy.md`(AR)、`incident_capture_policy.md`(IC)
- 方法: ファイルの読み取りのみ。ansible / ssh / ネットワーク接続は行っていない。`docs/ai/memory/` は読んでいない。
- 結果: **指摘 23件 / 未確認 11件**
- 重大度は目安(高 = 安全境界・適用可否の判定に直結 / 中 = 規定された停止・通知・記録が欠ける / 低 = 影響が限定的または記述の食い違い)

---

## 指摘

### F01【高・クラス1】removeを伴う更新が`BLOCKED`に分類される経路が実装に無い(dry-run・apply直前re-dry-runの両方)

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:130` 「removeあり: 置換関係に応じて`MAINTENANCE_REQUIRED`または`BLOCKED`」
- `docs/ai/policies/proxmox_operations_policy.md:214` 「重要removeで置換先不明は`BLOCKED`」
- `docs/ai/policies/proxmox_operations_policy.md:248` 「後継不明の重要remove、中核packageが消えるだけに見える状態…のいずれかは`BLOCKED`とする」
- `docs/ai/policies/proxmox_operations_policy.md:147` 「`BLOCKED`なら常に停止する」/ `:337`(SB-062)「置換先のない重要removeではその更新setを適用せず」

実装:
- `roles/proxmox_patch_dryrun/tasks/main.yml:202-209` `BLOCKED`になるのは `apt_update_ok` / `apt_check_ok` / `sim_ok` のいずれかが偽のときだけ。
- `roles/proxmox_patch_dryrun/tasks/main.yml:288-289` `{%- elif _has_important_component | bool or _has_removes | bool -%} MAINTENANCE_REQUIRED` — removeは置換関係を問わず常に`MAINTENANCE_REQUIRED`。
- `scripts/codex-classify.sh:109-110` Codex出力スキーマには `important_component_removals` / `replacement_suspected` があるが、`roles/` `playbooks/` のどこからも参照されていない(grepで0件)。
- `roles/proxmox_patch_apply_node/tasks/main.yml:286-295` re-dry-runも `MAJOR_UPGRADE_DETECTED` / `MAINTENANCE_REQUIRED` / `PATCH_READY` の3値しか出さない。
- `roles/proxmox_patch_apply_node/tasks/main.yml:346-350` 手動modeで確認文字列が `_redryrun_status`(=`MAINTENANCE_REQUIRED`)と一致すれば続行する。

帰結: 置換先の無い重要removeを含む更新setでも、手動apply(確認文字列 `MAINTENANCE_REQUIRED`)で適用できる。Policyではこの集合は`BLOCKED`で、手動でも適用不可。

### F02【高・クラス1】最終Status(`MAJOR_UPGRADE_DETECTED`)とUrgencyをAI出力がそのまま決めている

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:267` 「AI分類は補助に限り、最終Statusを直接決定しない」
- `docs/ai/policies/proxmox_operations_policy.md:282` 「AIが出すUrgencyは候補に限り、Ansible tasksが本Policyの判断条件と照合して最終Status / Urgencyを確定する」
- `docs/ai/policies/proxmox_operations_policy.md:285` 「重要componentとsecurity sourceの機械判定、最終Status / Urgency、apply可否はAnsible tasks」
- `docs/ai/policies/proxmox_operations_policy.md:262` 「`URGENT`は過剰に自動昇格せず、公式advisory、changelog、人間判断で昇格する」
- `docs/ai/policies/proxmox_operations_policy.md:231-236` major疑いの条件(Proxmox major / Debian suite / repository suite変更直後 / pve-manager major 等)

実装:
- `roles/proxmox_patch_dryrun/tasks/main.yml:286-287` `{%- elif codex_output.status_inputs.major_upgrade_suspected | bool -%} MAJOR_UPGRADE_DETECTED` — `codex_output` は `scripts/codex-classify.sh:139` の `codex exec` の出力で、`major_upgrade_suspected` を機械的に算出する処理は `roles/proxmox_patch_dryrun/files/proxmox-dryrun-merge.py`・`proxmox-dryrun-collect.sh` のどちらにも無い(suite / major version を見るコードが無い)。
- `roles/proxmox_patch_dryrun/tasks/main.yml:296-301` `(_cve_types_all | intersect(_urgent_cve_types))` および `'URGENT' in _urgency_candidates_all` / `'HIGH' in _urgency_candidates_all` — AIの `cve_types_detected` / `urgency_candidate` を照合なしで最終Urgencyに採用している。

### F03【中・クラス2】Codexへ渡すPolicy節が「判断軸」でなく「対応するPlaybook」になっている

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:79` `## 3. 対応するPlaybook`
- `docs/ai/policies/proxmox_operations_policy.md:169` `## 4. 判断軸`(URGENT/HIGHの基準 SB-009 `:186`、SB-045 `:256-259` はこの節にある)

実装:
- `scripts/codex-classify.sh:55` `SECTION3=$(extract_section "$POLICY_FILE" "3")`(`:8` で `POLICY_FILE=…/proxmox_operations_policy.md`)
- `scripts/codex-classify.sh:75` 「パッチポリシーの URGENT / HIGH 判断基準テーブルと照合し、urgency_candidate を決定する」
- `scripts/codex-classify.sh:85` `## パッチポリシー（Section 3: 判断軸）`

帰結: プロンプトは「判断軸」と称して§3(安全度と入口の表)を渡しており、Urgency基準(§4)はCodexに届いていない。

### F04【中・クラス1】dry-run段の件数でweekly full全体を見送っている(Policyは件数判定をre-dry-run段に限る)

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:238` 「dry-run段は件数閾値を持たず、apply直前のre-dry-run段だけが件数で判定する」
- `docs/ai/policies/proxmox_operations_policy.md:434`(変更履歴 2026-09-19)「予告は`_final_status`・終了コード・通知経路を変えない」

実装:
- `roles/proxmox_patch_dryrun/tasks/apply_forecast.yml:13-22` dry-run段でnode別 `update_count` を閾値と比べ `blocking_nodes` を作る。
- `playbooks/proxmox_patch_weekly_full.yml:432-457` `when: _wf_apply_gate.blocking_nodes | length > 0` で「mute・退避・適用を開始せずに今回の自動実行を見送りました」と通知し `_weekly_full_skip: true` → `meta: end_play`。1nodeでも超過すれば両nodeとも見送る。

### F05【中・クラス1/3】`BLOCKED`時にapply timer(schedule)を止める仕組みが無く、通知にも規定項目が無い

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:226` 「`BLOCKED`は…自動apply timerを停止し、復旧・回避・再構成routeへ移す」
- `docs/ai/policies/proxmox_operations_policy.md:331` 「`BLOCKED`ではtimerを止め、apply playbookを禁止し」
- `docs/ai/policies/proxmox_operations_policy.md:374` 「`BLOCKED`: 適用禁止、timer停止、両node未適用、選択したcontingency route、復帰条件を含める」

実装:
- `playbooks/proxmox_patch_weekly_full.yml:389-401` `BLOCKED`はその回を`fail`するだけ。
- `roles/semaphore_templates/defaults/main.yml:973-978` `UN-SAFE:Proxmox Weekly Full Patch` は `cron: "00 06 * * 6"` / `active: true` のまま。`BLOCKED`でこれを無効化するタスクは実装に無い。
- `roles/proxmox_patch_dryrun/tasks/main.yml:431-446` BLOCKED通知本文は「自動パッチ適用は停止します。手動で apt の状態を確認してください。」とnode状態のみで、contingency route・復帰条件を含まない。
- 手動入口 `playbooks/proxmox_patch_apply_node.yml` は直近dry-runのStatusを読まない(F01参照。`roles/proxmox_patch_apply_node/tasks/main.yml:320-329` はdry-run JSONを差分表示用に読むだけ)ため、「apply playbookを禁止」も実装されていない。

### F06【高・クラス1】手動applyの「明示的確認文字列」がSemaphore surveyの既定値として事前入力されている

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:144` 「手動適用は手動apply modeと、検出されたStatusに一致する明示的確認文字列…を必須とする」
- `docs/ai/policies/proxmox_operations_policy.md:401` 「…明示的確認文字列を必須とし、確認がなければ停止する」

実装:
- `roles/semaphore_templates/defaults/main.yml:155` `{ name: proxmox_patch_apply_mode, …, default_value: manual }`
- `roles/semaphore_templates/defaults/main.yml:156-158` `proxmox_patch_apply_manual_confirm … default_value: MAJOR_UPGRADE_DETECTED`

帰結: 「UN-SAFE:Proxmox patch apply (Manual)」を既定値のまま押すと、re-dry-runが`MAJOR_UPGRADE_DETECTED`(件数>閾値)の場合に確認文字列を入力しないまま適用へ進む(`roles/proxmox_patch_apply_node/tasks/main.yml:346-350` の一致判定を既定値が満たす)。

### F07【中・クラス1】apply roleのpost-healthcheck判定がSB-022より狭く、全試行CRITICALでも正常終了する

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:101` 「quorumなし、ZFS異常、apt / dpkg異常、重要service停止、systemd failed unit、root filesystem危険域、report生成失敗のいずれかをhealthcheck失敗とする」
- `docs/ai/policies/proxmox_operations_policy.md:323` 「SSH、Proxmox API、GUIの復帰を待ってpost-healthcheckを行う。OKの場合だけ次へ進み」/ `:386` 「reboot後にSSH、Proxmox API、GUIが戻らなければ次nodeへ進まない」
- `docs/ai/policies/proxmox_operations_policy.md:270` 「全試行で`CRITICAL`なら`CRITICAL`として扱う」

実装:
- `roles/proxmox_patch_apply_node/tasks/main.yml:866-880` OK/CRITICALの判定材料は `cluster.quorate` / `apt.check_ok` / `pve_cluster` / `corosync` / `pvedaemon` だけ。ZFS・systemd failed unit・root fs・`pveproxy`(GUI)は、スクリプトが収集している(`roles/proxmox_healthcheck/files/proxmox-healthcheck.sh:163-184`)のに見ていない。`retry_healthcheck_once.yml:32-46` も同じ。
- `roles/proxmox_patch_apply_node/tasks/main.yml:1025-1033` post-hcがCRITICALでも `_notify_status` は `warning`、`:1081-1084` の再raiseは `_apply_failed` のときだけなので終了コード0。
- 補足: weekly full はapply後に `playbooks/proxmox_patch_weekly_full.yml` Step 5/9 でフルの `proxmox_healthcheck` を回すため次node進行は止まる。食い違いが効くのは手動単体applyと、apply通知の`[SUCCESS]`/`[WARNING]`判定。

### F08【中・クラス1】停止時・成功時の通知に規定項目が無い(退避・復帰の失敗は通知自体が無い)

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:365` 「停止時はsummary通知に停止理由を含め」
- `docs/ai/policies/proxmox_operations_policy.md:371` 「成功通知: 各nodeのapply・post-healthcheck、reboot要否、更新package、必要最小限のchangelog要約を含める」
- `docs/ai/policies/proxmox_operations_policy.md:372` 「pve2停止通知: 停止理由、pve1へ進んでいないこと、対応要否、失敗taskまたはhealthcheck、report pathを含める」

実装:
- `roles/proxmox_evacuate_node/tasks/main.yml` と `roles/proxmox_restore_vm_placement/tasks/main.yml` に `notify` のincludeが無い(grepで0件)。migration失敗・maintenance timeout・HA待機timeoutでの停止はSlackに出ない(reportの保存と再raiseのみ。evacuate `:264-295`)。
- weekly fullのsummary通知(`playbooks/proxmox_patch_weekly_full.yml:767-842`)は途中のplayで全host失敗すると到達しないため、停止時のsummary通知は出ない。成功時の本文も `:837` 「{{ n }}: 退避 → パッチ適用 → 復帰 完了」で、更新package・changelog要約・reboot要否を含まない。
- apply roleの通知(`roles/proxmox_patch_apply_node/tasks/main.yml:1009-1022`)は「適用パッケージ数」の件数のみでpackage名・changelog要約が無く、report path(`:1075` で保存するファイル)も「pve1へ進んでいないこと」も載らない。

### F09【中・クラス1+4】HA退避漏れ・migration失敗は強制停止されず中断する(SB-091とSB-026が両立しない)

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:308` 「残存するrunning guestは強制停止する。…migration失敗やHA退避漏れも捕捉する終端不変条件である」
- `docs/ai/policies/proxmox_operations_policy.md:136` 「non-HA migration失敗またはmaintenance mode有効化timeoutで停止する」

実装:
- `roles/proxmox_evacuate_node/tasks/main.yml:192-209` HA退避の待機は `retries`/`until` で、300秒で尽きるとタスク失敗 → `:264` の `rescue` へ飛ぶ。
- `roles/proxmox_evacuate_node/tasks/main.yml:242-258` の強制停止はその後ろにあり、HA退避漏れ・migration失敗(`:138` のコマンド失敗)のどちらでも実行されない。

Policy側: SB-026はmigration失敗で「停止」、SB-091は同じ事象を強制停止で「捕捉」するとしており、同一playbookについて両立しない。実装はSB-026側に従い、HA退避漏れ(SB-026に無い停止)でも止まる。

### F10【低・クラス1】apply roleの「control node」検出がquoryでなく`ansy`を探している

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:77` 「本番のProxmox nodeを対象とするAnsible実行端末はquoryに限定する」
- `docs/ai/policies/proxmox_operations_policy.md:415` 「control nodeがpatch対象node上にいる場合はapplyを停止する」/ `:147` 「control node分離…の全条件を満たさなければ停止する」

実装:
- `roles/proxmox_patch_apply_node/defaults/main.yml:6` `proxmox_patch_apply_control_node_name: "ansy"`
- `roles/proxmox_patch_apply_node/tasks/main.yml:108-118` `selectattr('name', 'search', proxmox_patch_apply_control_node_name)` — 実行中のcontrollerではなく名前`ansy`のVMを探す。weekly fullは別途 `hostname -s` で検査している(`playbooks/proxmox_patch_weekly_full.yml:135-171`)が、手動単体applyの分離検査は実行端末と無関係な名前に固定されている。

### F11【低・クラス1】「ZFS異常」の判定がpool stateの`DEGRADED`/`FAULTED`だけ

Policy:
- `docs/ai/policies/proxmox_operations_policy.md:101` 「…ZFS異常…のいずれかをhealthcheck失敗とする」

実装:
- `roles/proxmox_healthcheck/tasks/main.yml:42-45` `_zfs_bad_pools` は `state == 'DEGRADED'` と `state == 'FAULTED'` のみ。`UNAVAIL` / `SUSPENDED` 等のpool stateや、`zpool status` のエラー件数行は異常扱いにならない(`zfs.collection_ok` が偽のときのみ別途CRITICAL `:52-53`)。

### F12【中・クラス1】restore nodeを`prefer<node>`で決められないとき、停止せず別nodeへ復元する

Policy:
- `docs/ai/policies/proxmox_backup_restore_verify_policy.md:65` 「restore nodeは対象VMの`prefer<node>` tagで決定し、決定できなければ停止する」
- `docs/ai/policies/proxmox_backup_restore_verify_policy.md:92` 「restore nodeを対象VMの`prefer<node>` tagから決定できなければ停止する」

実装:
- `playbooks/proxmox_backup_restore_verify.yml:158-170` preferred nodeが到達不能なら `groups['proxmox'] | … | selectattr('pen_reachable', 'equalto', true) | … | first` へフォールバックし `_brv_restore_fallback` を立てて続行する。
- `roles/proxmox_backup_restore_verify/tasks/main.yml:471` 通知に「(preferred: … が到達不能なため代替)」と載せる。停止するのはtag自体が無いとき(`playbooks/proxmox_backup_restore_verify.yml:150-156`)だけ。

### F13【低・クラス1】report directory作成の失敗が、通知なしの非ゼロ終了になる

Policy:
- `docs/ai/policies/proxmox_backup_restore_verify_policy.md:235` 「JSON reportを…保存する。保存失敗だけを新しい非ゼロ終了条件にしない」
- `docs/ai/policies/proxmox_backup_restore_verify_policy.md:160` 「other-owner分岐、lock解放失敗、report保存失敗を新しい失敗条件へ追加しない」

実装:
- `roles/proxmox_backup_restore_verify/tasks/main.yml:49-55` `Ensure report directory exists`(`delegate_to: localhost`)は `:60` の `block` より前にあり、`ignore_errors` も `rescue` も無い。ここで失敗するとlifecycle・通知(`:458-477`)に到達せずplayが失敗する。保存本体(`:417-447`)には `ignore_errors: true` がある。

### F14【低・クラス1】実装側の前提が「手動実行はansyから」になっており、quory限定を強制していない

Policy:
- `docs/ai/policies/proxmox_backup_restore_verify_policy.md:22` 「実行元は`quory`に限定する(monthly schedule・手動のいずれも)」

実装:
- `roles/proxmox_backup_restore_verify/defaults/main.yml:11-13` 「the monthly run is a single scheduled run from quory, and any manual run from ansy is made by a human who ensures it does not overlap」
- `roles/proxmox_backup_restore_verify/tasks/main.yml:66` 「manual run (ansy): a human ensures it does not overlap the monthly run」
- 実行ホストを検査するタスクはplaybook・roleのどちらにも無い(weekly fullの `hostname -s` 検査に相当するものが無い)。

### F15【低・クラス1】手動復旧3本の対象allowlistに、Policyに無い`sandbox`が入っている

Policy:
- `docs/ai/policies/autonomous_recovery_policy.md:63` 「manual service restartは`authy` / `monnie`だけを対象とし」
- `docs/ai/policies/autonomous_recovery_policy.md:66` 「manual VM rebootは`authy` / `monnie` / `sophos-fw`だけを対象とする」
- `docs/ai/policies/autonomous_recovery_policy.md:69` 「manual HA failoverは`authy` / `sophos-fw`だけを対象とし」

実装:
- `playbooks/recovery_service_restart.yml:65` `target in ['authy', 'monnie', 'sandbox']`
- `playbooks/recovery_vm_reboot.yml:69` `target in ['authy', 'monnie', 'sophos-fw', 'sandbox']`
- `playbooks/recovery_ha_failover.yml:68` `target in ['authy', 'sophos-fw', 'sandbox']`
- `roles/semaphore_templates/defaults/main.yml:380-399` `SANDBOX` classの3テンプレート(`target` 既定 `sandbox`)

### F16【低・クラス1】手動service restartが`reset-failed`を行わない

Policy:
- `docs/ai/policies/autonomous_recovery_policy.md:155` 「service restartを行う場合はrestart前にreset-failedを行い、start-limit raceを回避する」(節は「Pull ladder」配下)

実装:
- `roles/recovery_service_restart/tasks/main.yml:92-102` `ansible.builtin.systemd: state: restarted` のみで `reset-failed` が無い。
- 対照: push/Codex経路の `roles/recovery_exec/templates/recovery-action.sh.j2:8` は `sudo systemctl reset-failed {{ svc }}.service || true` を行っている。

### F17【中・クラス1】authy / monnie の`authorized_keys`が「2 entryだけ」でなく3 entry

Policy:
- `docs/ai/policies/autonomous_recovery_policy.md:222` 「`authy` / `monnie`の`authorized_keys`はinvestigate / actionの2 entryだけをtemplateで排他的に管理する」

実装:
- `roles/recovery_exec/templates/authorized_keys.j2:1-3` investigate(`_investigate_pubkey`)、action(`_action_pubkey`)に加え、3行目に `lookup('file', 'claude-investigate.pub')` の開発側調査鍵を同じ `recovery-investigate-dispatch.sh` へ着地させるentryがある。

### F18【中・クラス1】push経路にSlack通知もreport保存も無い。pull経路のstart/flapping等の分岐もreportを残さない

Policy:
- `docs/ai/policies/autonomous_recovery_policy.md:182` 「各経路はreport保存とSlack通知を行う」
- `docs/ai/policies/autonomous_recovery_policy.md:185` 「trigger受理時、各ladder段の試行結果、最終escalation時にJSTで通知する」
- `docs/ai/policies/autonomous_recovery_policy.md:198` 「`recovery-exec`は…Slack tokenを持たず」

実装:
- `roles/recovery_push/files/recovery-push-dispatch.sh:14-19,48-51` 受理・mute skip・lock skip・起動を `${STATE_DIR}/dispatch.log` へ書くだけで、Codexは `recovery-exec`(Slack token無し)として起動される。`dispatch.log` を読む実装は `roles/` `playbooks/` に無い(grepで0件)。Codexへの指示 `roles/recovery_exec/templates/AGENTS.md.j2:413` も「report in Japanese」で、出力先はSSHの標準出力。
- `roles/recovery_probe/files/recovery-probe.py:299-360` flapping(`:300-308`)、pve到達不能(`:323-330`)、stopped→start(`:331-353`)、not-found(`:354-360`)の各分岐は `queue_notify` のみでreportを保存しない(reportはplaybookを呼ぶ reboot / failover 段だけ)。

### F19【低・クラス1】自動muteの契約に無いplaybookが、個別最適化した15分のmuteを張る

Policy:
- `docs/ai/policies/autonomous_recovery_policy.md:119` 「自動muteは次の契約を維持する。段階単位のplaybookは一律120分とし、待ち時間を個別に最適化しない。」(列挙はProxmox 3本・`ubuntu_nightly.yml`・`ubuntu_vm_full_upgrade.yml`)

実装:
- `roles/grafana_provisioning/tasks/restart_and_verify.yml:43-48` `recovery_mute_target: monnie` / `recovery_mute_minutes: "{{ grafana_provisioning_mute_minutes }}"`
- `roles/grafana_provisioning/defaults/main.yml:73` `grafana_provisioning_mute_minutes: 15`

### F20【中・クラス1】捕捉が被観測playのタスク結果件数を変えている

Policy:
- `docs/ai/policies/incident_capture_policy.md:47` 「捕捉は、被観測playの**終了コード・タスク結果の件数・所要時間のいずれも変えない。**」

実装:
- `roles/common_slack/tasks/notify.yml:44-51` 通知のたびに `capture.yml` をblock/rescueでincludeする。
- `roles/common_slack/tasks/capture.yml:246-331` 収集器配備済みのcontrollerでは通知1回ごとに4タスク(`ok`)を追加する。実装自身が `:85-96` で「T1-added `ok` bucket +5」、`:17-20` で「The PLAY RECAP `failed` counter still goes 0→1 … the 0→1 degrade is accepted」と、件数の変化を受容済みとして記録している。

### F21【中・クラス1】見直し通知の差分基準が「前回の見直し」でなく「前回の通知実行」で、送信前に基準を進めている

Policy:
- `docs/ai/policies/incident_capture_policy.md:136` 「見直しのきっかけを出す通知は「前回の見直し時点からの差分」を数える。通知が1回飛ばなくても、次の通知が取りこぼしを含むこと。」

実装:
- `roles/knowledge_review/tasks/incident_metrics.yml:158-172` 新着は「前回実行で見た最大バンドルid」より大きいもの(`bundles_new_since_last_notify`)。
- `roles/knowledge_review/tasks/incident_metrics.yml:317-323` この基準(`last_bundle_id_seen`)をrole内で永続化する。Slack送信は後段の `playbooks/knowledge_review.yml:32-74`(post_tasks)で、`common_slack` はbest-effort(送信失敗はrescueで無視、`roles/common_slack/tasks/notify.yml:153-158`)。送信が失敗しても基準は進み、次回通知はその分を新着に含めない。

### F22【低・クラス1】`reports/`直下の書込禁止の根拠として書かれた「パッチ適用ゲートの入力」が実装と合わない

Policy:
- `docs/ai/policies/incident_capture_policy.md:61` 「`reports/` 直下には `proxmox_patch_apply_node` がパッチ適用ゲートの入力として読む成果物が含まれるため、そこへの書込権を持つidentityは**パッチ適用の可否を書き換えられる**」

実装:
- `roles/proxmox_patch_apply_node/tasks/main.yml:320-335` `reports/proxmox-dryrun/*_unified_dryrun.json` を読むのは `_redryrun_status != 'PATCH_READY'` のときだけで、用途は通知本文の差分表示(`_new_vs_dryrun` / `_unchanged_vs_dryrun`)。適用可否は直前re-dry-run(`:217-317`)で決まり、weekly fullの続行判定もメモリ上のfact(`playbooks/proxmox_patch_weekly_full.yml:365-380`)を使う。`reports/` のファイルを適用ゲートの入力にしている箇所は見当たらない。

(禁止そのもの — `reports/incidents/` 以外へ権限を与えない — は `roles/incident_capture/tasks/main.yml:127-180` で守られている。食い違うのは前提の記述。)

### F23【低・クラス2】IC-026が名指しする「`recovery.io` allowlist」に対応する実装が無い

Policy:
- `docs/ai/policies/incident_capture_policy.md:139` 「…`recovery.io` allowlistの拡張 — は、要件段階でYoshinobuの判断を要する」

実装:
- `roles/recovery_io/defaults/main.yml:1-13` Slack bridgeのroleにallowlist変数は無く、`roles/recovery_io/templates/*` にもallowlistを持つ記述が無い(grepで0件)。
- 実装上のallowlistの正本は `recovery_exec_targets`(`roles/recovery_exec/defaults/main.yml:66-`、AR-027 `docs/ai/policies/autonomous_recovery_policy.md:239`)。IC-026がどれを指すか実装から一意に決まらない。

---

## 未確認

- U01(AR-085 JST): `roles/recovery_probe/files/recovery-probe.py:33,150` は `datetime.now().astimezone()`(ホストのローカルTZ)で時刻を作り、`playbooks/recovery_probe_notify.yml:34` は末尾が `+09:00` のときだけ「JST」へ置換する。quoryのTZがAsia/Tokyoかはリポジトリから確定できない。
- U02(SB-070 `MAINTENANCE_REQUIRED`/MAJOR通知の内容): 本文は `codex_output.mail_body`(`roles/proxmox_patch_dryrun/tasks/main.yml:403-410`)でAI生成。Status・Urgency・重要component・remove/install関係・Roadmap要否・推奨actionを毎回含むかは実行しないと分からない。
- U03(SB-085 許容時間帯): weekly fullは土曜06:00(`roles/semaphore_templates/defaults/main.yml:975`)。これが「Sophos停止によるnetwork影響を許容できる時間帯」かの基準はリポジトリ外(工程管理表)にあり判定できない。
- U04(SB-011 pve2単独適用): 実装はpve1が不在のときpve2だけに適用する(`playbooks/proxmox_patch_weekly_full.yml` summary本文「pve1 が到達不能または不健全だったため、pve2 のみに適用しました」)。Policyは単一node適用をpve1単独の場合しか明記しておらず(`:40`, `:158`)、SB-011の「pve1が正常な場合のみpve2を更新する」(`:43`)が両node利用可能時に限る制約かどうかで結論が変わる。
- U05(SB-048/SB-090 quoryの所在): F10の前提として、quoryがProxmox上のVMでないことは `playbooks/proxmox_patch_weekly_full.yml:6` のコメントでしか確認していない。inventory上の事実としては未確認。
- U06(BRV-020 agent判定): 実装は `agent == '1'` または `'enabled=1' in agent`(`playbooks/proxmox_backup_restore_verify.yml:191`)。`1,fstrim_cloned_disks=1` のような形式はagent無し扱いになる。Policy文言(`:95`)がこの形式をagent期待に含めるつもりかは読み取れない。
- U07(AR-016): probe実行accountは `yoshi`(`roles/recovery_probe/defaults/main.yml:17-18`「repo・vault パスワード・SSH 鍵を持つ」)。「global pauseを読むために必要な権限だけを与える」(`:204`)が、probe account全体の権限を制限する規定なのか、pause読取りに関する追加付与を制限する規定なのか判断できない。
- U08(AR-050の適用範囲): pull ladderは `pvesh create /nodes/{node}/qemu/{vmid}/status/start` を実行する(`recovery-probe.py:262-274`)。AR-050(`:332`)の「`pvesh`の書込み動詞を構造的に実行不能」が§7「Proxmox調査」節の調査経路だけを指すのか、pull ladderにも及ぶのかは本文から確定できない(前者ならAR-060と整合)。
- U09(IC-009とIC-027): `roles/proxmox_healthcheck/tasks/main.yml:250-252` は `skip_notifications` が真だと `notify.yml` 自体をincludeしないため捕捉も起きない。IC-009(`:44`「抑止フラグは捕捉をスキップする理由にせず」)に反するのか、IC-027(`:50`「捕捉できない死角は受け入れ」)で許容される死角なのか、Policy側で決まらない。
- U10(IC-013): quoryからansyへの書込経路(agmsg、Operator Request Channel等)がIC-013(`:36`)の「ansy側のファイルシステムへ書ける経路」に当たるかは、各サービスの実挙動を見ないと判定できない。
- U11(IC-018等のlesson参照): IC-018(`:108`)・§9が名指す `docs/ai/memory/lessons/*.md` は、依頼により読んでいないため実在を確認していない。

---

## 読んだ範囲

規範・索引:
- `AGENTS.md`(system-reminder経由)、`docs/ai/core.md`、`docs/ai/policies/execution_boundary_policy.md`
- `docs/ai/policies/proxmox_operations_policy.md`、`docs/ai/policies/proxmox_backup_restore_verify_policy.md`、`docs/ai/policies/autonomous_recovery_policy.md`、`docs/ai/policies/incident_capture_policy.md`
- `docs/ai/policies/ansible_test_safety_policy.md`(TS番号の実在のみgrep)
- `playbooks/README.md`、`roles/semaphore_templates/defaults/main.yml`、`.gitignore`

playbook:
- `proxmox_backup_restore_verify.yml`、`proxmox_patch_apply_node.yml`、`proxmox_evacuate_node.yml`、`proxmox_restore_vm_placement.yml`、`proxmox_patch_weekly_full.yml`、`proxmox_patch_dryrun.yml`、`proxmox_healthcheck.yml`、`proxmox_hw_check.yml`、`proxmox_snapshot_check.yml`、`proxmox_storage_monthly.yml`
- `recovery_monitoring_check.yml`、`recovery_probe_notify.yml`、`recovery_service_restart.yml`、`recovery_vm_reboot.yml`(allowlist行)、`recovery_ha_failover.yml`(allowlist行)
- `knowledge_review.yml`、`incident_investigate_notify.yml`(ヘッダ)、`ubuntu_nightly.yml`(mute部分)、`cert_renew.yml`(pause/resume部分)

role / script:
- `roles/proxmox_backup_restore_verify/{defaults,tasks}/main.yml`
- `roles/proxmox_patch_apply_node/defaults/main.yml`、`tasks/main.yml`(1-620, 780-1084)、`tasks/retry_healthcheck_once.yml`、`files/proxmox-patch-apply-collect.sh`
- `roles/proxmox_patch_dryrun/{defaults/main.yml,tasks/main.yml,tasks/apply_forecast.yml,files/proxmox-dryrun-merge.py}`、`files/proxmox-dryrun-collect.sh`(grep)
- `scripts/codex-classify.sh`
- `roles/proxmox_evacuate_node/{defaults,tasks}/main.yml`、`roles/proxmox_restore_vm_placement/{defaults,tasks}/main.yml`
- `roles/proxmox_healthcheck/{defaults/main.yml,tasks/main.yml,files/proxmox-healthcheck.sh}`、`roles/proxmox_reachable_nodes/tasks/main.yml`
- `roles/proxmox_storage_monthly/{defaults/main.yml,tasks/collect.yml,tasks/report.yml,library/storage_archive.py}`
- `roles/recovery_probe/{defaults/main.yml,files/recovery-probe.py}`、`roles/recovery_mute/tasks/set.yml`
- `roles/recovery_push/{defaults/main.yml,files/recovery-push-dispatch.sh,files/recovery-push.sh,templates/push-authorized_keys.j2}`
- `roles/recovery_exec/templates/{authorized_keys.j2,authorized_keys-pve.j2,AGENTS.md.j2(該当箇所),recovery-action.sh.j2(grep)}`、`roles/recovery_exec/defaults/main.yml`(targets部分)、`roles/recovery_exec/tasks/main.yml`(ACL部分)、`roles/recovery_exec/files/homelab-recover-authy`
- `roles/recovery_service_restart/{defaults,tasks}/main.yml`、`roles/recovery_ha_failover/tasks/main.yml`(1-120)、`roles/recovery_vm_reboot/tasks/main.yml`(grep)、`roles/recovery_io/defaults/main.yml`
- `roles/grafana_provisioning/{defaults/main.yml,tasks/restart_and_verify.yml}`(mute部分)、`roles/ubuntu_vm_full_upgrade/{tasks/apply.yml,defaults/main.yml}`(mute・閾値部分)
- `roles/common_slack/tasks/{notify.yml,capture.yml}`
- `roles/incident_capture/{defaults/main.yml,tasks/main.yml,templates/*.j2}`、`files/incident-capture-collector.py`(grep)
- `roles/incident_investigate/{defaults/main.yml,templates/*.j2}`、`files/incident-investigate.py`(1-60, 600-900, grep)
- `roles/incident_inspect/{defaults/main.yml,templates/codex-config.toml.j2,templates/codex-investigate-wrapper.j2,templates/sudoers-incident-inspect.j2,templates/AGENTS.md.j2(該当箇所)}`
- `roles/knowledge_review/{defaults/main.yml,tasks/main.yml,tasks/incident_metrics.yml,templates/knowledge-review.timer.j2}`
- `roles/semaphore_templates/filter_plugins/semaphore_schedules.py`(`active`の扱いをgrep)
