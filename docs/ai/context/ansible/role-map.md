# Ansible Role Map

対象は現行の `roles/*` 全ディレクトリである。入力の具体値は複製せず、defaults、inventory/vars、実行時変数を参照する。出力/副作用は地図粒度の要約であり、実行可否は利用playbookとPolicyで判断する。

| Role | 目的 | 主要入力 | 主要出力・副作用 | 主な利用元 |
| --- | --- | --- | --- | --- |
| `alloy` | monnieのremote syslog振分け、logrotate、Alloy導入・cutover | `roles/alloy/defaults/main.yml` のsource/config/service定義、既存rsyslog/Promtail | apt install、設定/unit更新、rsyslog reload、PromtailからAlloyへservice切替 | `playbooks/alloy_setup.yml` |
| `cloudkey_cert_deploy` | CloudKey証明書の発行・API配備・検証・旧世代整理 | defaults、CloudKey vars、CA資材、実行時名前解決 | 一時鍵/証明書生成、API upload/activate、条件付きdelete、検証facts | `playbooks/cloudkey_cert_deploy.yml` |
| `codex_update_check` | Codex CLI/npmの現行・最新比較と更新 | package名、registry到達性、installed version | 条件付きglobal package更新、host別結果、通知 | `playbooks/codex_update_check.yml` |
| `common_slack` | 共通Slack通知を安全ガード付きで送る | callerのchannel/status/message、通知vars、skip/tester条件 | Slack通知または抑止表示 | 多数のhealthcheck、patch、recovery、backup入口からtask include |
| `homelab_cert_renew` | CA準備、証明書発行、CA trust/service別配備、cleanup | `roles/homelab_cert_renew/defaults/main.yml`、CA資材、対象config、名前解決 | tmpfs staging、鍵/証明書生成、trust/config更新、service restart、cleanup | `cert_renew*.yml`, `ca_trust_deploy.yml` |
| `monitoring_healthcheck` | 監視service群の状態収集・判定 | defaults、収集script、report/通知共通vars | controller report、facts、異常通知、critical時fail | `monitoring_healthcheck.yml`, `ubuntu_nightly.yml`, `ubuntu_vm_full_upgrade.yml` |
| `prometheus_update_check` | 手動導入Prometheusの更新確認、更新、backup/rollback補助 | defaults、確認入力、release情報、既存install/backup | binary更新、service restart、backup、通知、rollback結果 | `playbooks/prometheus_update_check.yml` |
| `proxmox_backup_restore_verify` | backup実restoreのライフサイクル検証 | defaults、選定されたbackup/restore対象、storage、lock条件 | 一時VM restore/start/検査/stop/delete、report/通知、cleanup | `playbooks/proxmox_backup_restore_verify.yml` |
| `proxmox_evacuate_node` | patch対象ノードからVM/CTを安全条件付き退避 | defaults、target/destination、cluster/VM/HA状態 | migration、HA退避、条件付きstop、配置report | `proxmox_evacuate_node.yml`, `proxmox_patch_weekly_full.yml` |
| `proxmox_healthcheck` | Proxmoxクラスタ・ノード・VM healthcheck | defaults、収集script、期待値vars | JSON/report、判定facts、異常通知/fail | healthcheck、dry-run、evacuate、weekly patch |
| `proxmox_hw_check` | Proxmox hardware棚卸し・異常判定 | defaults、hardware収集script、期待値vars | JSON/report、hardware判定、fail | `playbooks/proxmox_hw_check.yml` |
| `proxmox_patch_apply_node` | 単一ノードapt patch、reboot判定、post-check | defaults、事前dry-run結果、対象node、apt状態 | apt cache/update/upgrade、条件付きreboot、report、healthcheck | `proxmox_patch_apply_node.yml`, weekly full import |
| `proxmox_patch_dryrun` | apt更新候補・simulation・changelog等を収集・統合 | defaults、収集/merge script、apt metadata | controller report、分類用JSON/facts。実patchなし | `proxmox_patch_dryrun.yml`, weekly full import |
| `proxmox_restore_vm_placement` | VM/CTをtag等から決まるhome nodeへ復帰 | defaults、target node、VM/CT配置・tag・cluster状態 | migration、配置検証、report | `proxmox_restore_vm_placement.yml`, weekly full import |
| `proxmox_snapshot_check` | snapshot状態を収集し期限・状態を判定 | defaults、snapshot収集script、閾値 | JSON/report、stale WARNING/CRITICALと収集問題のSlack通知。stale判定自体はfailせず、収集stdout空・閾値入力不正等はfail | `playbooks/proxmox_snapshot_check.yml` |
| `radius_healthcheck` | RADIUS service・port・認証系healthcheck | defaults、収集script、期待値vars | controller report、facts、異常通知/fail | `radius_healthcheck.yml`, `ubuntu_vm_full_upgrade.yml` |
| `recovery_exec` | 限定された復旧調査/action用Codex runnerとSSH経路を配備 | defaultsのtarget/command許可定義、files/templates、鍵生成条件 | wrapper、config、sudoers/authorized_keys、調査script、鍵素材の公開側 | `playbooks/recovery_exec_setup.yml` |
| `recovery_ha_failover` | allowlist対象VMのHA failover | target、HA/cluster状態、timeout/retry、report path | HA state変更、待機・判定、report/通知 | `playbooks/recovery_ha_failover.yml` |
| `recovery_io` | Slackと復旧実行系を橋渡しする常駐serviceを配備 | defaults、environment、service/sudoers templates | Python bridge、environment、systemd service、権限設定 | `playbooks/recovery_io_setup.yml` |
| `recovery_mute` | 自律復旧の対象別mute設定とCLIを提供 | mute対象、TTL/reason/state path | mute state更新またはCLI配備 | recovery setup、Proxmox保守、Ubuntu reboot/upgrade |
| `recovery_probe` | 対象healthをprobeし復旧ラダーを起動するserviceを配備 | defaultsのtarget/probe/action定義、service/config template | probe script/config、systemd service、handler restart | `playbooks/recovery_probe_setup.yml` |
| `recovery_push` | OnFailure push dispatchとdrill unitを配備 | defaultsのtarget mapping、鍵/endpoint、files/templates | trigger/dispatch scripts、authorized_keys、systemd units | `recovery_push_setup.yml`, `recovery_push_drill_setup.yml` |
| `recovery_service_restart` | allowlist対象serviceのrestartと復旧確認 | target、unit allowlist、retry/delay、report path | service restart、post-check、report/通知 | `playbooks/recovery_service_restart.yml` |
| `recovery_vm_reboot` | allowlist対象VMのshutdown/startと復旧確認 | target、guest-agent特性、timeout、report path | VM stop/start、post-check、report/通知 | `playbooks/recovery_vm_reboot.yml` |
| `rsyslog_forward_to_monnie` | Ubuntu nodeからmonnieへのlogging経路を配備 | defaultsの許可host/snippet、target名、既存recon | package/config/drop-in更新、validation、rsyslog/journald activation | `playbooks/rsyslog_forward_to_monnie.yml` |
| `sophos_trim` | Sophos SSD trimをdry-run awareに実行 | timeout、実行mode、接続wrapper | trimまたはdry-run、結果facts、通知/fail | `playbooks/sophos_trim.yml` |
| `systemd_timers` | Ansible定期実行用service/timerを生成・有効化 | `roles/systemd_timers/defaults/main.yml` のtimer一覧、working dir/user | unit file更新、daemon-reload、timer enable/start | `playbooks/systemd_timers.yml` |
| `time_sync_check` | 複数方式の時刻同期状態を収集・基準hostと判定 | defaultsの対象/閾値、CloudKey vars、chrony、機器別接続 | per-host結果、集約report、通知/fail。時刻設定は変更しない | `playbooks/time_sync_check.yml` |
| `time_sync_ntp_reference` | quoryを追加chrony sourceとして配備 | reference hostname、対象host一覧 | chrony drop-in更新、chrony restart | `playbooks/time_sync_ntp_reference.yml` |
| `ubuntu_vm_full_upgrade` | apt/non-apt更新をsimulation・分類し確認付き適用 | defaultsの重要component/製品/閾値、`dry_run`、target/confirmation | report/通知、条件付きfull-upgrade、reboot、post-healthcheck | `playbooks/ubuntu_vm_full_upgrade.yml` |
| `unifi_backup_fetch` | CloudKey backupを取得し鮮度・世代を管理 | defaults、CloudKey vars、保存先、保持世代 | backup file作成、atomic配置、古い世代delete、結果facts | `playbooks/unifi_backup_fetch.yml` |
| `unpoller` | UniFi Poller向けGrafana dashboard JSON資産を保持 | `roles/unpoller/dashboads/*.json` | 現行tasks/defaultsなし。Ansible副作用なし | 現行 `playbooks/*.yml` から利用なし |
