# Incident: proxmox_restore_vm_placement実行後のSlack通知失敗(Sophos再起動によるネットワーク断)

日付: 2026-07-24
対象: `playbooks/proxmox_restore_vm_placement.yml` → `roles/proxmox_restore_vm_placement`最終ステップの`roles/proxmox_healthcheck`(post-restore healthcheck) → `roles/common_slack`(`tasks/notify.yml`)
種別: 動作不具合
原因分類: #運用考慮ミス

## 症状

`proxmox_restore_vm_placement`実行時、VM/CT配置復元・HA relocate・post-restore healthcheck自体は成功するが、最後のSlack通知ステップでDNS解決エラーにより失敗する。

- 2026-07-24 19:37:14〜19:37:26(初回発生、pve1電源投入・パッチ情報取得時):
  ```
  Attempting to send slack alert
  Can't send slack alert! Error: Post "https://hooks.slack.com/services/<redacted>": dial tcp: lookup hooks.slack.com on <systemd-resolved stub resolver>:53: server misbehaving
  ```
  (webhook URLは秘密情報のためredact済み)
- 2026-07-25 08:22:18〜08:25:29(pve1パッチ適用後の再現、recovery-probeの「外部到達性の回復」通知で断を確認)。
- 2026-07-25(修正前コードでの3回目の再現): 修正未commit状態でansyから対話SSHシェル経由で`proxmox_restore_vm_placement`を直接実行したところ、Sophos再起動中の断でSSHセッション自体が切断(ansy自身の経路もSophos依存のため)。recovery-probeが約4分間の断を検知・通知。Proxmox側のHA relocateはSSH切断後も非同期に継続し、最終的にSophos/Authyはpve1へ正常に戻った(実害なし)。

## 原因

`roles/proxmox_restore_vm_placement/tasks/main.yml`の「Wait for HA-managed VMs to return to target node」(HA relocate完了待ち)は、Proxmoxが返す`status`フィールド(VMプロセスがrunningか)だけを確認しており、ゲストOS(Sophos Firewall)自体が起動を終えて実際にルーティングを再開したかどうかは確認していなかった。この直後に無条件で`proxmox_healthcheck`(→Slack通知)が実行されるため、Sophos再起動中のネットワーク断(実測で約3〜4分)とタイミングが重なると、Slack webhookへのPOSTがDNS解決エラーで失敗していた。

対照として`roles/recovery_probe/files/recovery-probe.py`の`external_reachable()`は、同種の断を検知した上で通知をqueueに保留し、疎通回復後にflushする設計を既に持っていた(このIncidentとは無関係の別コンポーネント)。この設計が、今回の修正の参考実装になった。

## 修正内容

`roles/proxmox_restore_vm_placement/tasks/main.yml`の「HA VM復帰待ち」(Proxmox `status`確認)と`proxmox_healthcheck`実行の間に、実際の外部到達性を確認するゲートを追加した。

- チェック方法: `recovery-probe.py`の`external_reachable()`と同種のHTTP HEADリクエストを、target_node上で実行する固定Pythonヘルパー(monotonic deadline方式、netrc/proxy/auth handlerを一切参照しないカスタムURL opener)。
- リトライ間隔・タイムアウトはrole defaultsで設定可能(初期値15秒間隔・5分程度)。
- 疎通確認が失敗(タイムアウト)した場合はhealthcheckへ進まず、「HA復帰は確認できたがSophos経由の外部到達性が確認できなかった」ことが明確に分かる専用メッセージで停止し、`recovery_vm_reboot.yml -e target=sophos-fw`の手動実行を案内する。
- `docs/ai/policies/autonomous_recovery_policy.md` §5「経路分離」・AR-083「manual layerは人間の判断責任で直接起動できる」に基づき、このplaybookから`recovery_vm_reboot.yml`等の自律復旧actionを自動呼び出しすることは行わない(現行Policyでは無権限の第4経路になるため)。Policy改訂は今回のスコープ外。

実装・レビューはtechlead2(implementer2/reviewer2)へ委任。初回レビューでmust-fix 2件(Ansible retry式のタイマー計算誤差、`uri`モジュールの`use_netrc: true`既定によるセキュリティ懸念)を検出、固定Pythonヘルパーへの置換で解消し再レビューApprove。詳細: `docs/ai/reviews/proxmox_restore_vm_placement/`配下(2026-07-25_001〜007)。

## 確認方法

1. **構造テスト(`--check`)**: 2026-07-25、`scripts/safe-ansible-check.sh playbooks/proxmox_restore_vm_placement.yml -i inventories/homelab/hosts.yml -e target_node=pve2 --check`をYoshinobuが実行。tester-gate lint・syntax-check・`git diff --check`全てPASS。生成レポート(`reports/proxmox-restore/20260725T094907_pve2_restore.json`)がtest planの合格条件9項目全てと一致(`result: PLAN_ONLY`等)。ただし新ゲート自体はcheck modeでskipされるため、この時点ではロジックの実地確認にはなっていない。
2. **実地確認**: 2026-07-25、修正をcommit・quory反映後、pve1に対して`proxmox_evacuate_node.yml`→`proxmox_restore_vm_placement.yml`を実行。Sophosの実際のHA relocateにより10:32〜10:35(約3分)の断が発生(recovery-probeの「外部到達性の回復」通知で確認、これは本Incidentの修正対象とは独立した別経路)。**今回はpost-restore healthcheckのSlack通知がエラーにならず、正常に完了した**。新ゲートが疎通回復を待ってから後続処理に進んだことを実地で確認。

## 実害・影響

いずれの発生でもVM/CT配置復元・healthcheck自体は成功しており、実害はSlack通知の欠落のみだった(3回目のSSH切断も、Proxmox側のHA relocateは非同期に継続し実害なし)。修正後は通知欠落も解消。
