# Playbook catalog

このディレクトリは、人間・AI・Semaphore・systemd timer から実行する Ansible
playbook の入口を置く。処理本体は原則として `roles/` に実装する。

新しい処理を作る前にこのカタログを確認し、既存 playbook / role で目的を満たせないか
確認する。新しい playbook を追加した場合は、同じ変更でこのカタログにも登録する。

## 安全区分の見方

各表の `tester-gate` は playbook ヘッダの `# tester-gate:` を転記したものであり、
この README はヘッダや承認ルールを上書きしない。実行前には必ず対象ファイルのヘッダ、
承認済み test plan、`docs/ai/policies/ansible_test_safety_policy.md` の最新ルールを確認する。

| `tester-gate` | カタログ上の意味 |
| --- | --- |
| `safe-readonly` | 状態収集・検査が中心。通常実行できるが、通知やローカル成果物などはヘッダを確認する。 |
| `role-guarded` | 副作用が role のガードで抑止される。ガード条件を確認する。 |
| `risk-accepted` | 通常実行が前提の変更系を含む。承認済みの理由と対象範囲をヘッダで確認する。 |
| `check-mode-native` | 検証時は必ず `--check` を付ける。`--check` なしは APPLY として人間判断を必要とする。 |
| `dry-run-aware` | 検証時は必ず `--check` を付け、playbook 固有の dry-run 分岐を使う。 |

`check-mode-native` / `dry-run-aware` の検証実行には、実行者を問わず
`scripts/safe-ansible-check.sh playbooks/<name>.yml --check` を使う
(`--check` が無いと即終了するため、付け忘れを機械的に防げる)。
分類の意味と実行義務の正本は `docs/ai/policies/ansible_test_safety_policy.md`。

## 監視・ログ基盤

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`alloy_setup.yml`](alloy_setup.yml) | `monitoring_servers` | Grafana Alloy、rsyslog受信振り分け、Loki転送経路の構築・更新 | `check-mode-native` | `alloy` |
| [`grafana_provisioning.yml`](grafana_provisioning.yml) | `monnie` | Grafanaダッシュボード/アラートのrepo正本化(provisioning as code)。dashboard JSONの複製、dashboard provider定義、alert ruleのprovisioning配備 | `check-mode-native` | `grafana_provisioning` |
| [`monitoring_healthcheck.yml`](monitoring_healthcheck.yml) | `monitoring_servers` | Prometheus、Grafana、Loki等の監視基盤healthcheck | `safe-readonly` | `monitoring_healthcheck` |
| [`prometheus_update_check.yml`](prometheus_update_check.yml) | `monnie` | 手動導入Prometheusの更新確認と承認された更新処理 | `check-mode-native` | `prometheus_update_check` |
| [`rsyslog_forward_to_monnie.yml`](rsyslog_forward_to_monnie.yml) | `ansy:quory:authy` | Ubuntu系ノードのjournald/syslogをmonnieへ転送 | `check-mode-native` | `rsyslog_forward_to_monnie` |

## 証明書・CA

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`ca_trust_deploy.yml`](ca_trust_deploy.yml) | `control_nodes:dev_nodes:monitoring_servers:radius_servers:proxmox` | homelab CA証明書を管理対象ノードへ配布 | `check-mode-native` | `homelab_cert_renew` |
| [`cert_renew.yml`](cert_renew.yml) | `localhost`, `quory`, `ansy`, `proxmox`, `monnie` | CA鍵準備、証明書発行、各サービスへの配備、後片付け | `check-mode-native` | `homelab_cert_renew` |
| [`cert_renew_quory.yml`](cert_renew_quory.yml) | `localhost`, `quory` | quory向け証明書の発行・配備 | `check-mode-native` | `homelab_cert_renew` |
| [`cloudkey_cert_deploy.yml`](cloudkey_cert_deploy.yml) | `localhost`（CloudKeyへ接続） | CloudKey向け証明書の発行・配備 | `risk-accepted` | `cloudkey_cert_deploy` |

## Proxmox

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`proxmox_backup_restore_verify.yml`](proxmox_backup_restore_verify.yml) | `proxmox`, 動的restore対象 | 月次バックアップの実restore検証 | `risk-accepted` | `proxmox_backup_restore_verify` |
| [`proxmox_evacuate_node.yml`](proxmox_evacuate_node.yml) | `localhost`, 移動先、`target_node` | 対象ノードからVMを退避 | `check-mode-native` | `proxmox_evacuate_node`, `proxmox_healthcheck` |
| [`proxmox_healthcheck.yml`](proxmox_healthcheck.yml) | `proxmox` | クラスタ・ノード・VMのhealthcheck | `safe-readonly` | `proxmox_healthcheck` |
| [`proxmox_hw_check.yml`](proxmox_hw_check.yml) | `proxmox` | ハードウェア状態の収集・判定 | `safe-readonly` | `proxmox_hw_check` |
| [`proxmox_patch_apply_node.yml`](proxmox_patch_apply_node.yml) | `target_node` | Proxmox単一ノードへのパッチ適用 | `check-mode-native` | `proxmox_patch_apply_node` |
| [`proxmox_patch_dryrun.yml`](proxmox_patch_dryrun.yml) | `proxmox` | パッチ候補の収集・シミュレーション | `safe-readonly` | `proxmox_patch_dryrun`, `proxmox_healthcheck` |
| [`proxmox_patch_weekly_full.yml`](proxmox_patch_weekly_full.yml) | `proxmox`, `localhost` | 退避、パッチ、healthcheck、配置復元を含む週次オーケストレーション | `check-mode-native` | 関連Proxmox playbookを順次import |
| [`proxmox_restore_vm_placement.yml`](proxmox_restore_vm_placement.yml) | `localhost`, `target_node` | 退避後のVM配置を対象ノードへ戻す | `check-mode-native` | `proxmox_restore_vm_placement` |
| [`proxmox_snapshot_check.yml`](proxmox_snapshot_check.yml) | `proxmox` | VM snapshotの状態確認 | `safe-readonly` | `proxmox_snapshot_check` |

## 自律復旧

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`recovery_exec_setup.yml`](recovery_exec_setup.yml) | `dev_nodes:control_nodes` | recovery-exec、Codex runner、SSH鍵生成経路を配備 | `check-mode-native` | `recovery_exec` |
| [`recovery_ha_failover.yml`](recovery_ha_failover.yml) | `pve1` | 承認された対象のHA failover | `check-mode-native` | `recovery_ha_failover` |
| [`recovery_io_setup.yml`](recovery_io_setup.yml) | `dev_nodes:control_nodes` | Slack I/O bridgeを配備 | `check-mode-native` | `recovery_io` |
| [`recovery_monitoring_check.yml`](recovery_monitoring_check.yml) | `control_nodes` | 自律復旧が有効か（global pause継続・probe停止）の日次確認 | `safe-readonly` | playbook内tasks, `common_slack` notify tasks |
| [`recovery_probe_notify.yml`](recovery_probe_notify.yml) | `localhost` | recovery probeのSlack通知 | `role-guarded` | `common_slack` notify tasks |
| [`recovery_probe_setup.yml`](recovery_probe_setup.yml) | `dev_nodes:control_nodes` | recovery probeとmute CLIを配備 | `check-mode-native` | `recovery_probe`, `recovery_mute` |
| [`recovery_probe_sandbox_setup.yml`](recovery_probe_sandbox_setup.yml) | `control_nodes` | recovery probeの**検証用第2インスタンス**を配備(unit/設定/state_dirのみ分離、daemon本体は本番と共有。既定でenableしない) | `check-mode-native` | `recovery_probe` |
| [`deployment_drift_check.yml`](deployment_drift_check.yml) | `control_nodes:dev_nodes:monitoring_servers:radius_servers:proxmox` | 配備物がrepoとずれていないかを検査(hash / unit状態 / forced command構造 / reports所有権 / /etc/hosts)。差分時のみ通知、正常時は無通知・rc0 | `safe-readonly` | `deployment_drift_check` |
| [`recovery_push_drill_setup.yml`](recovery_push_drill_setup.yml) | `quory` | recovery push drill用unitを配備 | `check-mode-native` | `recovery_push` drill tasks |
| [`recovery_push_setup.yml`](recovery_push_setup.yml) | `quory` | recovery push triggerを配備 | `check-mode-native` | `recovery_push` |
| [`recovery_service_restart.yml`](recovery_service_restart.yml) | `pve1` | 承認された対象サービスの復旧restart | `check-mode-native` | `recovery_service_restart` |
| [`recovery_vm_reboot.yml`](recovery_vm_reboot.yml) | `pve1` | 承認された対象VMの復旧reboot | `check-mode-native` | `recovery_vm_reboot` |

## 障害記録・振り返り

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`incident_capture_setup.yml`](incident_capture_setup.yml) | `quory` | 障害証拠バンドル収集器(collector)を配備。有効化オプション時のみtimerをenable+start | `check-mode-native` | `incident_capture` |
| [`incident_inspect_setup.yml`](incident_inspect_setup.yml) | `dev_nodes:control_nodes` | 一次調査専用ユーザー(incident-inspect)とCodex起動口(wrapper)のみを配備。検出・調査本体・成果物書き出しは持たない | `check-mode-native` | `incident_inspect` |
| [`dev_investigate_setup.yml`](dev_investigate_setup.yml) | `quory` | 開発環境(Claude Code)向けread専用SSHランディングアカウント(dev-investigate、sudoなし)を配備。障害バンドル/レポート/quory自身の状態を読む20チェックのforced command dispatchのみ | `check-mode-native` | `dev_investigate` |
| [`operator_request_channel_server_setup.yml`](operator_request_channel_server_setup.yml) | `quory` | Operator Request Channelの本番側(共通ライブラリ、SSH受け口、Operator local CLI、schema、DLPルールセット、専用spoolとACL、監査ログ)を配備。**dispatcherの追加armは含まない** — 反映には`dev_investigate_setup.yml`の再実行が要る(`docs/ai/context/operations/operator-request-channel.md` §3) | `check-mode-native` | `operator_request_channel` |
| [`operator_request_channel_client_setup.yml`](operator_request_channel_client_setup.yml) | `ansy` | Operator Request Channelの開発側client、共通ライブラリ、schema、DLPルールセット、configを配備。message storeは持たない | `check-mode-native` | `operator_request_channel` |
| [`incident_investigate_setup.yml`](incident_investigate_setup.yml) | `quory` | 一次調査本体(バンドル走査・LLM呼び出し・成果物書き出し・同期起動鍵生成)のsystemd timer/oneshotを配備。有効化オプション時のみtimerをenable+start | `check-mode-native` | `incident_investigate` |
| [`incident_investigate_notify.yml`](incident_investigate_notify.yml) | `localhost` | 一次調査1件完了ごとに`#alerts`へプレーンテキストで通知(incident-investigate.pyから起動される) | `check-mode-native` | playbook内tasks(`community.general.slack`直接呼び出し) |
| [`incident_sync_teardown.yml`](incident_sync_teardown.yml) | `dev_nodes`, `quory` | **一度きりの後始末。** 退役した`incident_sync`(quory→ansy証拠バンドルのミラー同期)が残したsystemd unit・専用ユーザー・状態ディレクトリ・quory側鍵material を除去する。timerには載せない | `check-mode-native` | playbook内tasks |
| [`knowledge_review.yml`](knowledge_review.yml) | `localhost`（ansy専用） | 月次Knowledge見直しの**きっかけ**をSlackへ通知する(障害バンドルの滞留件数と最古バンドルの残り日数を添える)。無人LLMセッションは起動しない | `check-mode-native` | `knowledge_review` |
| [`knowledge_review_timer.yml`](knowledge_review_timer.yml) | `dev_nodes` | 月次Knowledge振り返り用systemd timerを配置 | `check-mode-native` | `knowledge_review` timer tasks |

## ホスト保守・定期運用

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`codex_update_check.yml`](codex_update_check.yml) | `localhost`, `ansy:quory` | Codex CLIの更新確認・更新 | `check-mode-native` | `codex_update_check` |
| [`radius_healthcheck.yml`](radius_healthcheck.yml) | `radius_servers` | FreeRADIUS/RADIUS基盤のhealthcheck | `safe-readonly` | `radius_healthcheck` |
| [`serial_getty_mask.yml`](serial_getty_mask.yml) | `ansy:monnie:quory:authy` | 未使用`serial-getty@ttyS0`の停止・mask | `check-mode-native` | playbook内tasks |
| [`sophos_trim.yml`](sophos_trim.yml) | `sophos` | Sophos Firewall SSDのtrim | `dry-run-aware` | `sophos_trim` |
| [`time_sync_check.yml`](time_sync_check.yml) | `quory:pve1:pve2:ansy:monnie:authy:sophos` | 各ホストのNTP同期状態を確認 | `safe-readonly` | `time_sync_check` |
| [`time_sync_ntp_reference.yml`](time_sync_ntp_reference.yml) | `pve1:pve2:ansy:monnie:authy` | quoryを追加NTP参照先として設定 | `check-mode-native` | `time_sync_ntp_reference` |
| [`ubuntu_nightly.yml`](ubuntu_nightly.yml) | `radius_servers`, `monitoring_servers` | reboot-required判定、条件付き再起動、サービス確認 | `check-mode-native` | playbook内tasks、`monitoring_healthcheck` tasks |
| [`ubuntu_vm_full_upgrade.yml`](ubuntu_vm_full_upgrade.yml) | `dev_nodes:control_nodes:radius_servers:monitoring_servers` | Ubuntu VMの更新判定と手動full-upgrade | `check-mode-native` | `ubuntu_vm_full_upgrade` |

## 自動化基盤・バックアップ・開発補助

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`agmsg_server_setup.yml`](agmsg_server_setup.yml) | `ansy` | agmsg リファレンスサーバ(Docker + nginx TLS終端)を常駐配備。到達範囲はquoryのみに限定(R2)、証明書は既存fullchainを参照(R11)し置き換わりを検知してnginxをreload(R10)。team作成・E2EE・remote接続は対象外(段3) | `check-mode-native` | `agmsg_server` |
| [`semaphore_db_backup.yml`](semaphore_db_backup.yml) | `pve1`/`pve2`（選定）、quory(delegate_to) | quoryのSemaphore(semaphore.db / projects export JSON / config.json)を3点1世代でSynology NFSへ退避、原子的確定・世代ローテーション | `risk-accepted` | `semaphore_db_backup` |
| [`semaphore_templates_setup.yml`](semaphore_templates_setup.yml) | `quory` | Semaphoreの「押せるボタン」定義(名前・playbook・引数・survey vars)をリポジトリのカタログからSemaphore REST APIへ冪等にreconcile。削除はしない | `check-mode-native` | `semaphore_templates` |
| [`systemd_timers.yml`](systemd_timers.yml) | `target_hosts`（既定`control_nodes`） | Ansible定期実行用systemd timerを管理 | `check-mode-native` | `systemd_timers` |
| [`unifi_backup_fetch.yml`](unifi_backup_fetch.yml) | `pve1`（CloudKeyへ接続） | CloudKeyのUniFiバックアップを取得・保存 | `risk-accepted` | `unifi_backup_fetch` |
| [`test_ca_env.yml`](test_ca_env.yml) | `localhost` | CA関連環境変数のローカル表示テスト | `safe-readonly` | playbook内tasks |
| [`worktree_sync_setup.yml`](worktree_sync_setup.yml) | `quory` | quoryの作業ツリーをorigin/mainへ追随させる`git pull --ff-only`をsystemd timerから起動する仕組みを配備(Semaphoreジョブ実行中は見送り) | `check-mode-native` | `worktree_sync` |
| [`worktree_sync_notify.yml`](worktree_sync_notify.yml) | `localhost` | `worktree_sync`の同期結果をSlackへ通知(worktree-sync.shから起動される) | `role-guarded` | `common_slack` notify tasks |

## 探し方

- 対象機器から探す: 上のカテゴリ表の「対象」を確認する。
- 処理名から探す: `rg -n '<keyword>' playbooks roles` を使う。
- 安全区分から探す: `rg -n '^# tester-gate:' playbooks/*.yml` を使う。
- 実装本体から入口を探す: role名を `rg -n '<role_name>' playbooks` で検索する。
- 定期実行を確認する: `roles/systemd_timers/defaults/main.yml` とSemaphore側の
  Task Templateを確認する。Semaphoreの登録内容はこのリポジトリだけでは確定しない。

## 更新ルール

1. playbook追加時は、ファイルヘッダへ有効な `# tester-gate:` を記載する。
2. このカタログの該当カテゴリへ1行追加する。
3. 対象、用途、安全区分、主なroleが実装と一致することを確認する。
4. `scripts/check-tester-gate.sh` とsyntax checkを実施する。
5. playbookを改名・移動する場合は、systemd timer、Semaphore、回復処理、ポリシー、
   実行例などの参照元も確認する。

`update-ssh-prompt.yml.bak` のようなバックアップファイルは実行入口ではないため、
このカタログには含めない。
