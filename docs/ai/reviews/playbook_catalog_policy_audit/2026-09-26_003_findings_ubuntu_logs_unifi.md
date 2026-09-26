# Policy↔実装 食い違い監査: ubuntu / time_sync / quory_health / log / unifi(2026-09-26)

対象Policy: `ubuntu_vm_patch_policy.md` / `time_sync_check_policy.md` / `quory_health_monthly_policy.md` / `log_observability_policy.md` / `unifi_backup_fetch_policy.md`。
確認手段はファイルの読み取りだけ(ansible実行・ssh・ネットワーク接続なし)。実行しないと分からないものは「未確認」へ分けた。

指摘: 10件 / 未確認: 7件

---

## 指摘

### F1. 方針2 node(ansy / quory)を「Ansible管理・healthcheckの対象にしない」規定に対し、monthly full-upgradeが両者を対象にしている(クラス1)

Policy側:

- `docs/ai/policies/ubuntu_vm_patch_policy.md:365` 「方針2 nodeをAnsible管理、監視、healthcheckの対象にしない。」(UV-048)
- `docs/ai/policies/ubuntu_vm_patch_policy.md:73` 「本Policy対応playbookは方針1 VMだけを対象とし、方針2 nodeをAnsible管理対象にしない。」(UV-053)
- `docs/ai/policies/ubuntu_vm_patch_policy.md:41` 「`ansy`は方針2とし、rebootのタイミングを固定時刻で決めずunattended-upgradesに委ねる。」(UV-011)/ `:44` 「`quory`は方針2とし、固定時刻に自動rebootさせ…」(UV-012)
- 同じPolicyの§3は `ubuntu_vm_full_upgrade.yml` を本Policy対応playbookとして列挙している(`:67`)。

実装側:

- `playbooks/ubuntu_vm_full_upgrade.yml:97` `hosts: dev_nodes:control_nodes:radius_servers:monitoring_servers`(dev_nodes=ansy、control_nodes=quory。`inventories/homelab/hosts.yml:21-29`)
- `roles/ubuntu_vm_full_upgrade/tasks/healthcheck.yml:39-41` `- name: Generic healthcheck (ansy/quory)` / `when: inventory_hostname in ['ansy', 'quory']`
- `roles/ubuntu_vm_full_upgrade/tasks/main.yml:47` `- node in ['ansy', 'monnie', 'authy', 'quory']`(apply対象)、`roles/semaphore_templates/defaults/main.yml:297` のapply templateのsurveyも `ansy` / `quory` を選択肢に持つ
- `roles/ubuntu_vm_full_upgrade/tasks/reboot_local.yml:13-16` ansyをapply後に同一セッションで即時 `ansible.builtin.reboot`(UV-011の「unattended-upgradesに委ねる」と異なるreboot契機)

影響: 規定どおりに読むと、ansy / quory への monthly inspect・healthcheck・manual apply・rebootはいずれも許されていない。Policy §3が同じplaybookを自分の対応playbookとして挙げているため、Policy自身の中でもUV-053と§3が両立しない。

### F2. UV-048「方針2 nodeを監視・Ansible管理の対象にしない」が、他の4 Policyが規定する ansy / quory の監視・管理と両立しない(クラス4)

Policy側:

- `docs/ai/policies/ubuntu_vm_patch_policy.md:365` 「方針2 nodeをAnsible管理、監視、healthcheckの対象にしない。」(UV-048。方針2 = ansy / quory、`:41` `:44`)
- `docs/ai/policies/quory_health_monthly_policy.md:13` 「観測対象はinventory上の`quory`だけとする。」(QHM-010)
- `docs/ai/policies/log_observability_policy.md:51` 「`ansy` / `quory` / `authy` | 各hostのrsyslogがmonnieへ転送 | `ubuntu-nodes`」(LOG-068)、`:96` 「Ubuntu senderはsender role、monnie receiverはAlloy roleで管理する。」(LOG-015)
- `docs/ai/policies/time_sync_check_policy.md:26` 比較対象に `ansy` を含む(TIME-002)

実装側(規定どおり、ansy / quory を監視・管理している):

- `playbooks/quory_health_monthly.yml:15` `- groups['control_nodes'] | default([]) == ['quory']`
- `playbooks/rsyslog_forward_to_monnie.yml:65` `hosts: "{{ target_hosts | default('ansy:quory:authy') }}"`
- `playbooks/time_sync_check.yml:73` `hosts: quory:pve1:pve2:ansy:monnie:authy:sophos`

影響: UV-048は文言上patch/rebootの文脈に限定されておらず、他Policyの規定とそれに従う実装を一律に禁じる形になっている。どちらを正とするかが文書から決まらない。

### F3. Status判定の「上から順に当てる」順序と、実装の判定順序が異なる(クラス1)

Policy側:

- `docs/ai/policies/ubuntu_vm_patch_policy.md:118-124` Statusの表の順序は `BLOCKED` → `MAJOR_UPGRADE_DETECTED` → `REVIEW_REQUIRED` → `UPGRADE_READY` → `NO_UPDATES`
- `docs/ai/policies/ubuntu_vm_patch_policy.md:130` 「**判定は上から順に当て、最初に該当したものを採る。** 個々の判定条件と閾値は実装を正本とし、本Policyへ写さない。」(UV-092)

実装側:

- `roles/ubuntu_vm_full_upgrade/tasks/classify.yml:136-141`
  ```
  {{ 'BLOCKED' if (…apt_update.rc != 0 or …apt_check.rc != 0 or …simulation.rc != 0)
     else 'MAJOR_UPGRADE_DETECTED' if (ubuntu_vm_full_upgrade_major_signals | length > 0)
     else 'NO_UPDATES' if (…inst | length) == 0 and (…remv | length) == 0)
     else 'BLOCKED' if (ubuntu_vm_full_upgrade_remv_blocking | length > 0)
     else 'REVIEW_REQUIRED' if …
     else 'UPGRADE_READY' }}
  ```

影響: BLOCKEDの条件のうち「重要コンポーネントのremoveで後継が確認できない」は `MAJOR_UPGRADE_DETECTED` の後ろで評価される。remove数が閾値(`defaults/main.yml:141` の30件)を超えている、またはcodename driftがある月にこの条件も成立すると、実装は `MAJOR_UPGRADE_DETECTED`(`#patches` / warning)を出す。Policyの順序どおりなら `BLOCKED`(`#alerts` / critical)になる。どちらでもapplyは拒否されるため、変わるのは通知先と重大度である。「判定条件は実装が正本」を「BLOCKEDの条件はMAJORに該当しないことを含む」と読めば食い違いは消えるが、その読み方はUV-092の「上から順に当てる」を無意味にする。

### F4. nightlyのreboot後post-checkが `OK` / `CRITICAL` 以外の `WARNING` を出し、`#info` / `ok` で通知している(クラス1)

Policy側:

- `docs/ai/policies/ubuntu_vm_patch_policy.md:251` 「post-check結果を`OK`または`CRITICAL`として通知する。」(UV-066)
- `docs/ai/policies/ubuntu_vm_patch_policy.md:317` 「nightly: reboot正常完了 | `#info` | `ok`」、`:321` 「healthcheck: `WARNING` | `#alerts` | `warning`」(UV-076)

実装側:

- `playbooks/ubuntu_nightly.yml:482-484`
  ```
  slack_channel: "{{ 'alerts' if monitoring_criticals | length > 0 else 'info' }}"
  slack_status: "{{ 'critical' if monitoring_criticals | length > 0 else 'ok' }}"
  slack_title: "[ubuntu_nightly] {{ monitoring_report.result.status }} - {{ inventory_hostname }}"
  ```
- `roles/monitoring_healthcheck/tasks/check.yml:100-102` `status: "{{ 'CRITICAL' if monitoring_criticals | length > 0 else ('WARNING' if monitoring_warnings | length > 0 else 'OK') }}"`(warningsはmemory / diskの80〜89%、`:66-71`)

影響: monnieのreboot後にmemoryまたはdiskが80〜89%だと、タイトルは `[ubuntu_nightly] WARNING - monnie`、送信先は `#info`、statusは `ok` になる。UV-066が想定しない3値目が現れ、UV-076のhealthcheck `WARNING` の宛先(`#alerts`)とも違う経路で送られる。

### F5. monthly full-upgradeのhealthcheckが authy / monnie の `WARNING` を捨てている(クラス1)

Policy側:

- `docs/ai/policies/ubuntu_vm_patch_policy.md:185` 「healthcheckが`WARNING`または`CRITICAL`なら通知対象と判定する。」(UV-056)
- `docs/ai/policies/ubuntu_vm_patch_policy.md:300` 「healthcheckが`WARNING`なら通知する。」(UV-072)

実装側:

- `roles/ubuntu_vm_full_upgrade/tasks/healthcheck.yml:102-108`
  ```
  # radius / monitoring の各roleは warnings を返さない(criticalsのみ)。
  # したがってこの一覧は現状ansy/quoryの汎用checkだけが埋める…
  - name: Consolidate healthcheck warnings across all node types
    ansible.builtin.set_fact:
      ubuntu_vm_full_upgrade_healthcheck_warnings: >-
        {{ ubuntu_vm_full_upgrade_generic_health.warnings | default([]) }}
  ```
- 実際には両roleともwarningsを返している: `roles/monitoring_healthcheck/tasks/check.yml:66` `monitoring_warnings: "{{ []`、`roles/radius_healthcheck/tasks/check.yml:50` `radius_warnings: "{{ []`

影響: full-upgradeの判定中に authy / monnie のhealthcheckが `WARNING` でも通知されない(`tasks/main.yml:133-135` の警告通知は `ubuntu_vm_full_upgrade_healthcheck_warnings` だけを見る)。コメントの前提(「warningsを返さない」)が事実と違う。

### F6. Alloy cutoverの成功条件に「real streamがLokiへ到達すること」の検証が無い(クラス1 / 3)

Policy側:

- `docs/ai/policies/log_observability_policy.md:211` 「Alloy activeだけを成功条件にせず、journal streamの実dataがLokiへ到達することを確認する。」(LOG-042)
- `docs/ai/policies/log_observability_policy.md:229` 「4. Alloyをstartしてactive、ready、runtime log、real streamを検証する。」
- `docs/ai/policies/log_observability_policy.md:232` 「Alloy startまたはruntime validationに失敗した場合はPromtailをrestoreし…」(LOG-040)

実装側:

- `roles/alloy/tasks/main.yml:775-781`
  ```
  - name: Require a healthy Alloy runtime graph after cutover
    ansible.builtin.assert:
      that:
        - alloy_runtime_active.stdout == "active"
        - alloy_runtime_ready.status | default(-1) == 200
        - alloy_runtime_journal.rc == 0
        - alloy_runtime_journal.stdout is not regex(alloy_runtime_fatal_log_pattern)
  ```
  role内にLokiへの問い合わせは無い(`grep` で `3100` / `/loki/api` を探すと、push URLの検査 `:22` と候補configの文字列検査 `:106-107` だけ)。

影響: 検証されるのはactive・ready・Alloy自身のjournalだけである。stream(labelを含む)がLokiへ届いていない状態でも成功扱いになり、LOG-040の自動restoreも発動しない。LOG-055(`:324`)「runtime validationはtester工程へ分離する」によって人の検証へ回す読み方もできるが、LOG-039の手順とLOG-040のrestore条件はcutoverの自動フローとして書かれている。

### F7. monnie journalのLoki `job` を「system stream」と規定しているが、実装のjobは `ubuntu-nodes`(クラス1)

Policy側:

- `docs/ai/policies/log_observability_policy.md:48-50` 表の列見出し「Lokiのjob」、`monnie` 行の値が「system stream」(LOG-068)

実装側:

- `roles/alloy/defaults/main.yml:126-131`
  ```
  alloy_journal_sources:
    - name: system
      …
      labels:
        job: ubuntu-nodes
        host: monnie
  ```
- `roles/alloy/tasks/main.yml:86` `- "'\"job\" = \"ubuntu-nodes\"' in alloy_candidate_config"`(jobが `ubuntu-nodes` であることを検査している)

影響: 「system」はAlloy componentの名前(`loki.source.journal "system"`)であって、Lokiのjob labelではない。表どおりに `{job="system"}` などで問い合わせると、monnieのjournalには当たらない。

### F8. 「syslog系統からの通知は未実装」と規定しているが、Lokiを読んでSlackへ送る週次ダイジェストが実装済み(クラス1)

Policy側:

- `docs/ai/policies/log_observability_policy.md:242` 「**syslog系統からの通知は未実装である。**」(LOG-047)
- 同じPolicyの `:20`(LOG-063)は、週次ダイジェストが `#info` へ送ると書いている

実装側:

- `roles/syslog_weekly_digest/tasks/main.yml:76-79`
  ```
  - name: "Send syslog weekly digest to Slack #info (AC1/AC5: 常に送る、無通知にしない)"
    ansible.builtin.include_tasks: "{{ playbook_dir }}/../roles/common_slack/tasks/notify.yml"
    vars:
      slack_channel: "info"
  ```

影響: LOG-047の第2段落は「未実装かどうかはalert ruleのdatasourceがLokiを参照しているかで判断する」と基準を限定しており、その基準では今も「未実装」になる。ただし第1文は無条件であり、LOG-063と実装に照らすと成立しない。「通知」と「検知(alert)」の区別が条文上ついていない。

### F9. UniFi backup fetchの週次cronが、毎月28日の Proxmox backup restore verify と同時刻に重なる(クラス1)

Policy側:

- `docs/ai/policies/unifi_backup_fetch_policy.md:60-61` 「他の定常jobと衝突しない時間帯に、quory の systemd timer で**週次**実行する(Semaphore UI 導入後は Schedule へ移行)。」(UNIFI-014)

実装側:

- `roles/semaphore_templates/defaults/main.yml:941-943` `name: "SEMI-SAFE:Unifi backup fetch"` / `cron: "30 18 * * 5"`
- `roles/semaphore_templates/defaults/main.yml:934-936` `name: "SAFE:Proxmox backup restore verify"` / `cron: "30 18 28 * *"`

影響: cronのday-of-monthとday-of-weekは別々に発火するため、28日が金曜の月は両ジョブが同じ18:30に起動する。どちらもpveノード上で同じSynology NFSを使う(`roles/unifi_backup_fetch/defaults/main.yml:15`、`roles/proxmox_backup_restore_verify/defaults/main.yml:31` 「vzdump backup source storage on the NFS (Synology) share.」)。Semaphoreが同時に走らせるか、直列に並べるかは読むだけでは分からない(未確認U5)。

### F10. 実行元を「quoryのみ」と規定しているが、playbookのヘッダは ansy からの実行も想定している(クラス1)

Policy側:

- `docs/ai/policies/time_sync_check_policy.md:27` 「実行元 | quory(本番・CLIとも)」(TIME-002)
- `docs/ai/policies/unifi_backup_fetch_policy.md:50` 「実行元 | quory(本番・週次・手動とも)」(UNIFI-003)

実装側:

- `playbooks/time_sync_check.yml:13-14` 「実行元はquoryまたはansy。実行元ホスト自身は比較対象から動的に除外する」、`roles/time_sync_check/defaults/main.yml:7` `# Host actually running ansible-playbook (quory or ansy).`
- `playbooks/unifi_backup_fetch.yml:13` 「実行元: quory(本番 / Semaphore 週次)または ansy(開発 / CLI)。」

影響: どちらのplaybookにも、実行元を強制する仕組みは無い(`prometheus_update_check.yml:68-74` にあるようなhostname assertが無い)。ansyから実行すると、`time_sync_check` はansyを比較対象から外して走る(`defaults/main.yml:19-21`)。規定と実装が想定する実行元の集合が一致していない。

---

## 未確認

- **U1. NVMe取得ツールのsetup入口(QHM-011 / QHM-020)**: Policyは「パッケージ導入は別のquory限定setup入口で…」(`quory_health_monthly_policy.md:16`)、「ツール導入が必要な場合のsetup入口は観測から分離する」(`:21`)と書く。`playbooks/quory_nvme_setup.yml` は存在せず、`git log` ではcommit `fae340e`「…remove unused NVMe setup」で削除されている。`roles/quory_nvme_setup/` は空のディレクトリ(`defaults/` と `tasks/` だけで中身が無い)で、git管理外。Policyの書き方は「必要な場合」の条件付きなので、quoryに `nvme-cli` が入っていて入口が不要なのか、入口が宙に浮いているのかは、quoryの実機を見ないと判断できない。
- **U2. `Unattended-Upgrade::Automatic-Reboot` の実効値(UV-040 / UV-046 / UV-050)**: この設定を配るroleはリポジトリに無く(`sandbox_auto_patch` を除く)、実装側を引用できない。参考として `docs/ai/reviews/sandbox_auto_patch/2026-09-04_001_requirement.md:28` に「**`ansy` でも実効値は `Automatic-Reboot "false"` である** — 本番は月次playbookと03:30の条件付きrebootが再起動を担う」という記述がある。事実なら UV-046(方針2はtrue)・UV-011 / UV-049(ansyはunattended-upgradesの自動rebootに委ねる)と食い違う。ただしこれはreview文書であり、実機では確認していない。
- **U3. Alloy cutover前のmute(LOG-043)**: `log_observability_policy.md:235` 「production cutover等の変更前にはmonnieのautonomous recoveryをmuteし…」。`roles/alloy/tasks/main.yml` にも `playbooks/alloy_setup.yml` にも `recovery_mute` の呼び出しは無い(同じPolicyのLOG-086が求めるgrafana restartのmuteは `roles/grafana_provisioning/tasks/restart_and_verify.yml:43-48` に実装されている)。LOG-043がコードで行うことを求めているのか、人の手順(Operations Context)なのかは条文から判断できない。
- **U4. quoryのNTP状態を「収集できない」ときのstatus(TIME-020)**: 表(`time_sync_check_policy.md:164`)は「quory自身のNTP同期異常(Phase 1で中断) | #alerts | critical」だけを持つ。実装は「未同期」を `critical`(`roles/time_sync_check/tasks/main.yml:63`)、「未収集」を `error`(`:35`)に分けている。TIME-009(`:129-130`)はPhase 1の中断条件に「未収集」を含めているが、表の行が「未収集」も覆うつもりなのかは読み取れない。
- **U5. F9の同時起動が実害になるか**: Semaphoreが同じprojectのジョブを並行で走らせるか、キューで直列化するかは、カタログを読むだけでは分からない。実行時の設定か実績(ジョブ履歴)の確認が要る。
- **U6. quory health monthlyの `UNKNOWN` のSlack表示**: `roles/quory_health_monthly/tasks/report.yml:71` は `slack_status` に `health | lower` を渡すため、`UNKNOWN` は `unknown` になる。`roles/common_slack/tasks/notify.yml` の色の対応表は `unknown` を持たず、既定の `good`(緑)に落ちる。本文の見出しは「[判定不能]」になり、ジョブは非0で終わる(`report.yml:87`)ので、QHM-031「全体`OK`に畳まない」に反するとまでは言えない。Policyは短報の色・statusを規定していないため、判断を保留した。
- **U7. 実装側コメントが存在しないPolicy節を指している(対象クラス外の参考)**: `playbooks/ubuntu_vm_full_upgrade.yml:69` 「(see patch policy §3.3)」、`roles/ubuntu_vm_full_upgrade/tasks/apply.yml:13` 「(ubuntu_vm_patch_policy.md §3.2)」。現行の `ubuntu_vm_patch_policy.md` には§3.2 / §3.3 が無い(該当する内容はUV-023 / UV-024とUV-016)。向きが「実装→Policy」なので依頼のクラス2(Policyが名指しするもの)には当てはまらないが、記録しておく。

---

## 読んだ範囲

規範・入口:
- `AGENTS.md`、`docs/ai/core.md`(1-80行)、`docs/ai/policies/execution_boundary_policy.md`(1-60行)

Policy(全文):
- `docs/ai/policies/ubuntu_vm_patch_policy.md`
- `docs/ai/policies/time_sync_check_policy.md`
- `docs/ai/policies/quory_health_monthly_policy.md`
- `docs/ai/policies/log_observability_policy.md`
- `docs/ai/policies/unifi_backup_fetch_policy.md`

playbook:
- `playbooks/README.md`
- `playbooks/ubuntu_nightly.yml`、`playbooks/ubuntu_vm_full_upgrade.yml`、`playbooks/radius_healthcheck.yml`、`playbooks/monitoring_healthcheck.yml`、`playbooks/prometheus_update_check.yml`
- `playbooks/time_sync_check.yml`、`playbooks/time_sync_ntp_reference.yml`(1-60行)
- `playbooks/quory_health_monthly.yml`
- `playbooks/alloy_setup.yml`、`playbooks/rsyslog_forward_to_monnie.yml`、`playbooks/grafana_provisioning.yml`、`playbooks/syslog_weekly_digest.yml`
- `playbooks/unifi_backup_fetch.yml`
- `playbooks/proxmox_backup_restore_verify.yml`(`hosts:` 行のみ)

role:
- `roles/ubuntu_vm_full_upgrade/`: `tasks/main.yml`、`tasks/healthcheck.yml`、`tasks/classify.yml`、`tasks/collect_nonapt_product.yml`、`tasks/evaluate_nonapt_product.yml`、`tasks/apply.yml`(1-60行とgrep)、`tasks/reboot_local.yml`(1-40行)、`tasks/reboot_quory.yml`(grep)、`defaults/main.yml`(1-80行とgrep)
- `roles/prometheus_update_check/`: `tasks/main.yml`、`defaults/main.yml`、`tasks/upgrade.yml`・`tasks/notify.yml`(grep)
- `roles/monitoring_healthcheck/tasks/check.yml`・`tasks/main.yml`、`roles/radius_healthcheck/tasks/main.yml`・`tasks/check.yml`(40-92行とgrep)
- `roles/common_slack/tasks/notify.yml`、`roles/common_slack/tasks/capture.yml`(1-40行とgrep)
- `roles/time_sync_check/`: `tasks/main.yml`、`tasks/check_chrony.yml`、`defaults/main.yml`
- `roles/quory_health_monthly/`: `defaults/main.yml`、`tasks/collect.yml`、`tasks/report.yml`、`files/quory_collect.py`、`library/quory_health_archive.py`、`library/quory_health_notion.py`(1-80行)、`module_utils/quory_health.py`(`short_summary` / `markdown`)
- `roles/quory_nvme_setup/`(ディレクトリ構成のみ。ファイル無し)
- `roles/alloy/`: `defaults/main.yml`、`templates/config.alloy.j2`、`tasks/main.yml`(grepと700-790行)
- `roles/grafana_provisioning/`: `tasks/main.yml`、`tasks/preflight_dashboards.yml`、`tasks/deploy_alerting.yml`、`tasks/restart_and_verify.yml`(1-40行とgrep)、`tasks/deploy_dashboards.yml`・`tasks/deploy_provider.yml`(grep)、`defaults/main.yml`、`files/dashboards-provider-*.yml`、`files/alerting/unifi-switch-port-errors.yaml`(grep)、`files/dashboards/`(一覧)
- `roles/rsyslog_forward_to_monnie/tasks/main.yml`(grep)
- `roles/syslog_weekly_digest/`: `tasks/main.yml`、`defaults/main.yml`
- `roles/unifi_backup_fetch/`: `tasks/main.yml`、`defaults/main.yml`
- `roles/proxmox_exec_node/tasks/main.yml`(grep)
- `roles/proxmox_backup_restore_verify/defaults/main.yml`(grep)
- `roles/semaphore_templates/defaults/main.yml`(template catalog 60-330行、schedule catalog 715-1106行)
- `roles/systemd_timers/defaults/main.yml`(`unifi` のgrepのみ。該当なし)

その他:
- `inventories/homelab/hosts.yml`、`inventories/vars/`(一覧のみ)
- `docs/ai/reviews/quory_health_monthly/`(`quory_nvme_setup` のgrep結果のみ)、`docs/ai/reviews/sandbox_auto_patch/`(`Automatic-Reboot` のgrep結果のみ)
- `git log`(`playbooks/quory_nvme_setup.yml` の履歴)、`git show --stat HEAD`
