# 観測: Semaphore テンプレートの現状(2026-08-04)

取得: `ssh quory-investigate "semaphore-query template-list 200"`(read-only)

**このファイルは観測の生データであり、正本ではない。** 定義の正本は
`roles/semaphore_templates/defaults/main.yml`(本案件で新設)である。
転記による誤りを避けるため、クエリ出力をそのまま貼っている。

```text
CREATE TABLE project__template (
                                   id                            INTEGER PRIMARY KEY AUTOINCREMENT,
                                   project_id                    INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
                                   inventory_id                  INTEGER REFERENCES project__inventory(id),
                                   repository_id                 INTEGER NOT NULL REFERENCES project__repository(id),
                                   playbook                      VARCHAR(255) NOT NULL,
                                   arguments                     TEXT NULL,
                                   name                          VARCHAR(100) NOT NULL,
                                   description                   TEXT NULL,
                                   type                          VARCHAR(10) NOT NULL DEFAULT '',
                                   start_version                 VARCHAR(20) NULL,
                                   build_template_id             INTEGER REFERENCES project__template(id),
                                   view_id                       INTEGER REFERENCES project__view(id) ON DELETE SET NULL,
                                   survey_vars                   TEXT NULL,
                                   autorun                       INTEGER NULL DEFAULT 0,
                                   allow_override_args_in_task   INTEGER NOT NULL DEFAULT 0,
                                   suppress_success_alerts       INTEGER NOT NULL DEFAULT 0,
                                   app                           VARCHAR(50) NOT NULL,
                                   tasks                         INTEGER NOT NULL DEFAULT 0,
                                   git_branch                    VARCHAR(255) NULL,
                                   task_params                   TEXT NULL,
                                   runner_tag                    VARCHAR(50) NULL,
                                   allow_override_branch_in_task INTEGER NOT NULL DEFAULT 0
, allow_parallel_tasks boolean not null default false)
1|1|1|1|playbooks/proxmox_healthcheck.yml|[]|SAFE: Proxmox healthcheck|||||||0|0|0|ansible|77||{}||0|0
2|1|1|1|playbooks/radius_healthcheck.yml|[]|SAFE: Authy healthcheck|||||||0|0|0|ansible|67||{}||0|0
3|1|1|1|playbooks/monitoring_healthcheck.yml|[]|SAFE: Monitoring healthcheck|||||||0|0|0|ansible|67||{}||0|0
4|1|1|1|playbooks/proxmox_hw_check.yml|[]|SAFE: Proxmox hardware check|||||||0|0|0|ansible|68||{}||0|0
5|1|1|1|playbooks/ubuntu_nightly.yml|[]|SEMI-SAFE: Ubuntu nightly reboot if required|||||||0|0|0|ansible|67||{}||0|0
6|1|1|1|playbooks/proxmox_patch_dryrun.yml|[]|SEMI-SAFE: Proxmox patch dry-run|||||||0|0|0|ansible|12||{}||0|0
7|1|1|1|playbooks/proxmox_patch_weekly_full.yml|[]|UN-SAFE:Proxmox Weekly Full Patch|||||||0|0|0|ansible|13||{}||0|0
8|1|1|1|playbooks/proxmox_patch_apply_node.yml|[]|UN-SAFE:Proxmox patch apply (Manual)||||||[{"name":"target_node","title":"target_node","required":true,"type":"enum","description":"pve1 or pve2","values":[{"name":"pve1","value":"pve1"},{"name":"pve2","value":"pve2"}]},{"name":"proxmox_patch_apply_mode","title":"proxmox_patch_apply_mode","required":true,"default_value":"manual"},{"name":"proxmox_patch_apply_manual_confirm","title":"proxmox_patch_apply_manual_confirm","required":true,"type":"enum","values":[{"name":"MAINTENANCE_REQUIRED","value":"MAINTENANCE_REQUIRED"},{"name":"MAJOR_UPGRADE_DETECTED","value":"MAJOR_UPGRADE_DETECTED"}],"default_value":"MAJOR_UPGRADE_DETECTED"}]|0|0|0|ansible|13||{}||0|0
9|1|1|1|playbooks/proxmox_evacuate_node.yml|[]|UN-SAFE:Proxmox evacuate node(Manual)||||||[{"name":"target_node","title":"target_node","required":true,"type":"enum","values":[{"name":"pve1","value":"pve1"},{"name":"pve2","value":"pve2"}]}]|0|0|0|ansible|21||{}||0|0
10|1|1|1|playbooks/proxmox_restore_vm_placement.yml|[]|UN-SAFE:Proxmox restore vm placement(Manual)||||||[{"name":"target_node","title":"target_node","required":true,"type":"enum","values":[{"name":"pve1","value":"pve1"},{"name":"pve2","value":"pve2"}]}]|0|0|0|ansible|20||{}||0|0
11|1|1|1|playbooks/cert_renew.yml|[]|SEMI-SAFE:Cert_renew (only on Quory)||||||[{"name":"force_renew","title":"force_renew","default_value":"true"}]|0|0|0|ansible|21||{}||0|0
12|1|1|1|playbooks/sophos_trim.yml|[]|SEMI-SAFE:Sophos trim|||||||0|0|0|ansible|5||{}||0|0
14|1|1|1|playbooks/cloudkey_cert_deploy.yml|[]|SEMI-SAFE:Cloudkey_cert_deploy|||||||0|0|0|ansible|3||{}||0|0
15|1|1|1|playbooks/proxmox_backup_restore_verify.yml|[]|SAFE:Proxmox backup restore verify|||||||0|0|0|ansible|4||{}||0|0
16|1|1|1|playbooks/unifi_backup_fetch.yml|[]|SEMI-SAFE:Unifi backup fetch|||||||0|0|0|ansible|9||{}||0|0
17|1|1|1|playbooks/proxmox_snapshot_check.yml|[]|SAFE:Proxmox snapshot check|||||||0|0|0|ansible|7||{}||0|0
19|1|1|1|playbooks/time_sync_check.yml|[]|SAFE: Time sync check|||||||0|0|0|ansible|43||{}||0|0
20|1|1|1|playbooks/recovery_ha_failover.yml|[]|UN-SAFE:Recovery ha failover(Manual)||||||[{"name":"target","title":"target","required":true,"type":"enum","values":[{"name":"authy","value":"authy"},{"name":"sophos-fw","value":"sophos-fw"}]}]|0|0|0|ansible|0||{}||0|0
21|1|1|1|playbooks/recovery_service_restart.yml|[]|UN-SAFE:Recovery service restart(Manual)||||||[{"name":"target","title":"target","required":true,"type":"enum","values":[{"name":"authy","value":"authy"},{"name":"monnie","value":"monnie"}]}]|0|0|0|ansible|0||{}||0|0
22|1|1|1|playbooks/recovery_vm_reboot.yml|[]|UN-SAFE:Recovery vm reboot(Manual)||||||[{"name":"target","title":"target","required":true,"type":"enum","values":[{"name":"authy","value":"authy"},{"name":"monnie","value":"monnie"},{"name":"sophos-fw","value":"sophos-fw"}]}]|0|0|0|ansible|0||{}||0|0
23|1|1|1|playbooks/codex_update_check.yml|[]|SEMI-SAFE:Codex update check(Only on Quory)|||||||0|0|0|ansible|6||{}||0|0
24|1|1|1|playbooks/ubuntu_vm_full_upgrade.yml|[]|SEMI-SAFE:Ubuntu vm full upgrade(dry_run=true)||||||[{"name":"dry_run","title":"dry_run","required":true,"description":"アップグレードせずに情報収集を行います","default_value":"true"}]|0|0|0|ansible|3||{}||0|0
25|1|1|1|playbooks/ubuntu_vm_full_upgrade.yml|[]|UN-SAFE:Ubuntu vm full upgrade(Manual)||||||[{"name":"dry_run","title":"dry_run","required":true,"description":"実際にアップグレードを適用します","default_value":"false"},{"name":"node","title":"node","required":true,"type":"enum","description":"対象ノードを指定します","values":[{"name":"ansy","value":"ansy"},{"name":"monnie","value":"monnie"},{"name":"authy","value":"authy"},{"name":"quory","value":"quory"}]},{"name":"ubuntu_vm_full_upgrade_confirm","title":"ubuntu_vm_full_upgrade_confirm","required":true,"description":"アップグレードの対象ノードを指定します"}]|0|0|0|ansible|12||{}||0|0
26|1|1|1|playbooks/prometheus_update_check.yml|[]|UN-SAFE:Prometheus update(Manual)||||||[{"name":"dry_run","title":"dry_run","required":true,"description":"update適用","default_value":"false"}]|0|0|0|ansible|3||{}||0|0
27|1|1|1|playbooks/prometheus_update_check.yml|[]|SAFE:Prometheus update check||||||[{"name":"dry_run","title":"dry_run","required":true,"description":"チェックのみ","default_value":"true"}]|0|0|0|ansible|3||{}||0|0
28|1|1|1|playbooks/prometheus_update_check.yml|[]|UNSAFE:Prometheus rollback(Manual)||||||[{"name":"dry_run","title":"dry_run","required":true,"description":"ロールバック実行","default_value":"false"},{"name":"rollback","title":"rollback","description":"ロールバック指定","default_value":"true"},{"name":"rollback_to","title":"rollback_to","description":"指定バージョンへのRollback"}]|0|0|0|ansible|0||{}||0|0
29|1|1|1|playbooks/recovery_monitoring_check.yml|[]|SAFE:Recovery monitoring check|||||||0|0|0|ansible|3||{}||0|0
30|1|1|1|playbooks/recovery_vm_reboot.yml|[]|SANDBOX: Recovery vm reboot||||||[{"name":"target","title":"target","type":"enum","values":[{"name":"sandbox","value":"sandbox"}],"default_value":"sandbox"}]|0|0|0|ansible|4||{}||0|0
31|1|1|1|playbooks/recovery_ha_failover.yml|[]|SANDBOX: Recovery ha failover (check)||||||[{"name":"target","title":"target","type":"enum","values":[{"name":"sandbox","value":"sandbox"}],"default_value":"sandbox"}]|0|0|0|ansible|0||{}||0|0
32|1|1|1|playbooks/recovery_service_restart.yml|[]|SANDBOX: Recovery service restart||||||[{"name":"target","title":"target","type":"enum","values":[{"name":"sandbox","value":"sandbox"}],"default_value":"sandbox"}]|0|0|0|ansible|0||{}||0|0
33|1|1|1|playbooks/deployment_drift_check.yml|[]|SAFE: Deployment drift check|||||||0|0|0|ansible|1||{}||0|0
34|1|1|1|playbooks/incident_investigate_setup.yml|["-l quory"]|SEMI-SAFE:Incident investigate setup|||||||0|0|0|ansible|4||{}||0|0
35|1|1|1|playbooks/recovery_exec_setup.yml|[]|SEMI-SAFE:Recovery exec setup|||||||0|0|0|ansible|1||{}||0|0
36|1|1|1|playbooks/dev_investigate_setup.yml|[]|SEMI-SAFE:Dev investigate setup|||||||0|0|0|ansible|1||{}||0|0
```
