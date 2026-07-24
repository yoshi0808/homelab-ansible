# Repository Context: Proxmox patch

本書はProxmox patchを構成する複数playbook / roleの関係を示す非規範Contextである。許可、禁止、停止条件は [`proxmox_patch_policy.md`](../../policies/proxmox_patch_policy.md) が正本であり、競合時はPolicyを優先する。単一taskの詳細は各playbook / roleを正本とする。

## 入口と責務

| 入口 | 主role | 横断的な責務 |
|---|---|---|
| `proxmox_healthcheck.yml` | `proxmox_healthcheck` | patch前後のhealth gateとreport |
| `proxmox_patch_dryrun.yml` | `proxmox_patch_dryrun` | metadata更新、simulation、changelog収集、分類、通知。実patchなし |
| `proxmox_evacuate_node.yml` | `proxmox_evacuate_node` | 反対nodeの事前health gateとguest退避 |
| `proxmox_patch_apply_node.yml` | `proxmox_patch_apply_node` | 単一nodeのStatus再確認、apply、必要時reboot、post-healthcheck |
| `proxmox_patch_weekly_full.yml` | 複数roleを編成 | pve2からpve1までのrolling flow |
| `proxmox_restore_vm_placement.yml` | `proxmox_restore_vm_placement` | home tagに基づく復帰とpost-restore healthcheck |

安全度はPolicyのsafe、semi-safe、controlled apply、unsafeを参照する。Repository Contextは入口の実在と連携を説明するだけで、実行可否を追加しない。

## inventoryとguest分類

- Proxmox接続情報はinventoryのProxmox group変数にある。
- guest配置Policyを接続変数へ混在させず、home nodeはProxmox tagから判定する。
- `prefer<node名>`はhome node、`hacritical`はHA管理対象をroleへ伝える印として使われる。
- evacuateはnon-HA、HA、明示migration対象外を分け、restoreはhome tagへ戻す対象を選ぶ。
- reportはmigrated、force-stopped、HA対象の集計を保存する。実行時のguest識別子はContextへ転記しない。

## role間のデータflow

```text
health reports
  -> dry-run unified report
  -> classification candidate
  -> Ansible final Status / Urgency
  -> evacuate / apply / restore reports
  -> summary notification
```

- dry-run reportはpackage変更候補、remove / install / upgrade、重要component候補、security source候補、changelogを統合する。
- apply roleは事前dry-runまたは直前re-dry-runのStatusを読む。
- weekly fullは各nodeのevacuation、apply、restore reportを集約する。
- restore role内部にpost-restore healthcheckがあり、別のfinal healthcheck入口はない。

## 分類CLI契約

分類CLIはホームラボ固有のdry-run補助契約であり、汎用Skillにはしない。

入力:

- Ansibleが生成したdry-run JSON
- 現在導入版以降に限定したchangelog差分
- 新規packageでは最新changelog entry
- PolicyのStatus / Urgency判断条件

出力:

- 重要component候補と理由
- removeの置換候補
- major upgrade疑い
- security-sensitive候補と脆弱性種別
- Urgency候補と根拠・confidence
- 通知とMarkdown reportの説明候補

分類CLIの出力は候補である。Ansible tasksが機械的なpackage情報とPolicy条件を照合し、最終Status / Urgencyとapply可否を確定する。

## changelogとreport

- `apt changelog`の全文をreportへ保存し、通知には要約を載せる。
- Roadmap、公式更新手順、Security Advisory、Debian Security TrackerはPolicyが指定する条件で参照する。
- 単純な文字列検索だけを最終判定にしない。
- 旧Policyにあったcommand例、JSON例、変数値はコードまたは実行時出力を正本とし、本Contextへ複製しない。

## 関連

- [Policy](../../policies/proxmox_patch_policy.md)
- [System Context](../system/proxmox.md)
- [Operations Context](../operations/proxmox-patch.md)
- [playbook map](playbook-map.md)
- [role map](role-map.md)
