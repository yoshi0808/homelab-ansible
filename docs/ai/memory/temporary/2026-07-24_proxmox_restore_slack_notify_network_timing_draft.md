# [下書き] proxmox_restore_vm_placement 実行後のSlack通知失敗

修正・動作確認が取れ次第、`docs/ai/memory/incidents/2026-07-24_proxmox-restore-slack-notify-timing.md`(仮)として正式記録し、本ファイルは削除する(`skills/incident-recording/SKILL.md`)。

対象: `playbooks/proxmox_restore_vm_placement.yml`(pve1向け実行) → `roles/proxmox_restore_vm_placement`最終ステップの`roles/proxmox_healthcheck`(post-restore healthcheck) → `roles/common_slack`(`tasks/notify.yml`)
種別(見込み): 動作不具合
原因分類(見込み): #運用考慮ミス

## 症状

pve1の電源投入・パッチ情報取得のため`proxmox_restore_vm_placement`を実行。処理自体(VM/CT配置復元・HA relocate・post-restore healthcheck)は成功したが、最後のSlack通知ステップでエラー。

エラーログ(19:37:14〜19:37:26):
```
Attempting to send slack alert
Can't send slack alert! Error: Post "https://hooks.slack.com/services/<redacted>": dial tcp: lookup hooks.slack.com on <systemd-resolved stub resolver>:53: server misbehaving
```
(webhook URLは秘密情報のため redact 済み。元ログはagmsg会話履歴のみに存在し、本ファイルには書かない。)

## 原因(Yoshinobu所見)

`proxmox_restore_vm_placement`はHA管理VM(sophos-fw等)をrelocateで戻す際、sophos-fwが再起動する([[project_proxmox_ha_vm_relocate_reboot_accepted]]で仕様として確認済みの挙動)。sophos-fwはネットワークのゲートウェイ/DNSを兼ねるため、再起動中はインターネット疎通が失われる。post-restore healthcheckの最後のSlack通知が、この疎通断のタイミングと重なると、DNS解決(`hooks.slack.com`)が失敗し通知が送れない。

## 修正内容

未着手(2026-07-24時点)。Yoshinobu所見: sophos-fw起動後、インターネットへの疎通が回復してからSlack通知を送るようにする(通知前に疎通確認 or リトライ/待機を挟む)。実装方式(healthcheck/common_slack側での疎通確認・リトライ、実装箇所)は明日以降Tech Leadへ委任し確定させる。

## 確認方法

未実施。修正後、pve1向けの`proxmox_restore_vm_placement`(または同等の再現手順)を実行し、sophos-fw再起動を挟んでもSlack通知が最終的に成功することを確認する予定。

## 実害・影響

VM/CT配置復元・healthcheck自体は成功しており、影響はSlack通知の欠落のみ(気付きにくい点はリスクだが、緊急対応が必要な実害は発生していない)。
