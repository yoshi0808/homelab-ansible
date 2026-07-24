# Operations Context: Proxmox patch

本書は複数roleにまたがるpatch運用の順序と復旧情報を示す非規範Contextである。実行の許可、禁止、停止条件は [`proxmox_patch_policy.md`](../../policies/proxmox_patch_policy.md) が正本であり、競合時はPolicyを優先する。実行前に必ずPolicyを読み、本書だけを根拠にapplyしない。

## Mode別の処理順

### cluster外control nodeのfull flow

```text
control node確認
-> pve1 / pve2 healthcheck
-> fixed pair dry-run
-> pve2 evacuate
-> pve2 apply / 必要時reboot / post-healthcheck
-> pve2 restore / post-restore healthcheck
-> pve1 evacuate
-> pve1 apply / 必要時reboot / post-healthcheck
-> pve1 restore / post-restore healthcheck
-> summary通知
```

各矢印の続行gateはPolicyに従う。時刻は運用scheduler側の設定であり、本Contextへ固定しない。

### Proxmox上のcontrol nodeによる単一node flow

```text
control node所在確認
-> control nodeが存在しない側をtargetに選ぶ
-> targetと必要な反対nodeのhealthcheck
-> dry-runまたはre-dry-run
-> guest退避
-> apply / 必要時reboot / post-healthcheck
-> summary通知
```

もう一方のnodeは同じ実行で続けない。control nodeの所在変更は別作業である。

### MAINTENANCE_REQUIRED手動flow

通知とchangelog要約を確認し、必要な公式情報を読み、maintenance枠を確保する。対象healthcheckとguest退避を確認し、手動apply modeと明示確認を指定する。apply、必要時reboot、post-healthcheckを完了し、pve1はpve2成功後に別途判断する。

## post-healthcheck retry

reboot直後はservice起動待ちにより一時的な`CRITICAL`または、収集自体の失敗を示す`UNKNOWN`になり得る。Policyが許可する場合だけ待機後にretryする。

- retry回数は`proxmox_patch_apply_hc_retry_count`、待機秒数は`proxmox_patch_apply_hc_retry_delay`で制御し、role defaultsはそれぞれ`2`と`60`である。現在値の正本はrole defaultsとする。
- retry taskは`retry_count + 1`回を上限に実行し、各retry試行の冒頭に待機する。最大待機時間は`(retry_count + 1) × retry_delay`秒である。
- 最終判定はPolicyどおり、OKへ戻れば成功、全試行失敗なら失敗結果を維持する。
- 一時変更は実行時変数、恒久変更はrole defaultsのreview済み変更として扱う。

## evacuationとrestoreの運用像

- non-HA guestは反対nodeへ明示migrationする。
- HA guestはnode maintenanceを有効化して退避を待つ。
- 対象nodeに残ったrunning guestは最終確認で停止され得る。
- restoreではnon-HA guestをhomeへ戻し、停止guestを起動し、node maintenanceを解除する。
- HA guestはhomeへ明示relocateし、runningになるまで待つ。
- restoreの最後にpost-restore healthcheckを行う。

個々のcommand、poll条件、変数はroleを正本とする。

## host OS復旧

Policyの再インストール原則に従い、node障害時は健全なnodeを守って壊れたnodeを再構築する。

- pve2障害: pve1を保護しながらpve2を再インストールし、cluster、replication、storage、networkを再構成する。
- pve1障害: guestがpve2へ退避済みであることを確認し、pve1を再インストールしてclusterへ戻す。

再構築メモは次を対象とする。

- hostname
- managementとserver segmentのaddressing項目名
- NIC名と割当
- bridgeとsegment設定
- ZFS pool名とstorage設定
- apt repository
- SSH公開鍵
- cluster join方針
- replication設定
- `/etc/network/interfaces`
- `/etc/hosts`
- `/etc/hostname`

IP、VLAN ID、VM ID、認証情報の実値はContextへ記載せず、inventory・変数・秘密管理を正本とする。

## Sophos VM稼働時

Policyの全安全前提を満たした後も、patch対象node上のSophos VMを先に別nodeへ移動できるか確認する。移動する場合は必要なinterface / segment割当を確認し、移動後に家庭内networkの通信を確認する。停止影響を許容できるmaintenance枠でだけ行う。

本節は確認順を示すだけで、直接patchの許可や例外を作らない。

## 関連

- [Policy](../../policies/proxmox_patch_policy.md)
- [System Context](../system/proxmox.md)
- [Repository Context](../ansible/proxmox-patch.md)
