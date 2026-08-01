# Operations Context: Proxmox operations

本書は複数roleにまたがるpatch運用の順序と復旧情報を示す非規範Contextである。実行の許可、禁止、停止条件は [`proxmox_operations_policy.md`](../../policies/proxmox_operations_policy.md) が正本であり、競合時はPolicyを優先する。実行前に必ずPolicyを読み、本書だけを根拠にapplyしない。

## control node条件別の処理順

### cluster外control nodeのfull flow

```text
control node確認
-> pve1 / pve2 healthcheck
-> dry-run
-> pve2 evacuate
-> pve2 apply / 必要時reboot / post-healthcheck
-> pve2 restore / post-restore healthcheck
-> pve1 evacuate
-> pve1 apply / 必要時reboot / post-healthcheck
-> pve1 restore / post-restore healthcheck
-> summary通知
```

各矢印の続行gateはPolicyに従う。時刻は運用scheduler側の設定であり、本Contextへ固定しない。

**両nodeが揃わなくても実行される**(2026-08-01改訂)。到達できたnodeだけを対象に進み、片方が到達不能でも開始しない理由にはならない。ただし単一node運転では退避先が無いため、対象nodeにrunning guestがあれば適用を見送る。全nodeが到達不能なときだけ停止する。条件の正本はPolicyのSB-094・SB-012・SB-088。

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

### 手動applyが要る局面と、確認文字列

**2026-08-01の改訂で、手動applyが要る範囲は狭まった。** `MAINTENANCE_REQUIRED` でも**removeを伴わなければ自動適用される**ため、毎週の手作業は不要になった。

手動applyと明示確認が要るのは次の2つだけである。判定は実装側の `_redryrun_requires_confirmation` に集約されており、条件の正本はPolicy(SB-027・SB-028・SB-031)。

| 局面 | `proxmox_patch_apply_manual_confirm` に渡す値 |
|---|---|
| `MAINTENANCE_REQUIRED` かつ **removeあり** | `MAINTENANCE_REQUIRED` |
| `MAJOR_UPGRADE_DETECTED` | `MAJOR_UPGRADE_DETECTED` |

**確認文字列は、検出されたStatusと一致していなければならない。** 一致しなければ停止する(不一致時のエラーメッセージには渡すべき値が埋め込まれて出る)。確認が不要な局面で値を渡しても比較自体が評価されないため無害である。

`proxmox_patch_apply_mode=manual` と併せて指定する。Semaphoreのテンプレートでは確認文字列を上表の2値のENUMとして持たせている(**Semaphoreの設定はリポジトリ外にあり、ここからは確認できない**)。

手順そのものは従来どおり。通知とchangelog要約を確認し、必要な公式情報を読み、maintenance枠を確保する。対象healthcheckとguest退避を確認してからapply、必要時reboot、post-healthcheckを完了し、pve1はpve2成功後に別途判断する。

> **`MAJOR_UPGRADE_DETECTED` は、確認文字列を渡せば通る種類の作業ではない。** Policy SB-041は「通常patchから除外し、**別project化**する。Roadmap / Release Notesを参照してpve2検証計画を作り、pve1を最後にする」と定めている。確認文字列はゲートの一部にすぎず、本体はこの計画のほうである。ENUMで選べる形にした分、この要求が形骸化しやすいことに注意する。
>
> **この経路は2026-08-01の新設で、実運用でまだ一度も通っていない。** 現状の根拠はdecoyでの一致・不一致の検証のみ。

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

Sophos VMは他のguestと同じく退避対象である。退避時は必要なinterface / segment割当を確認し、移動後に家庭内networkの通信を確認する。HA relocateはVM再起動を伴いinternet接続が切断されるため、停止影響を許容できるmaintenance枠でだけ行い、自律復旧のmuteが設定されていることを確認する。

本節は確認順を示すだけで、直接patchの許可や例外を作らない。

## 関連

- [Policy](../../policies/proxmox_operations_policy.md)
- [System Context](../system/proxmox.md)
- [Repository Overview](../ansible/repository-overview.md)(playbook・roleは `playbooks/*.yml`・`roles/*` を直接参照)
