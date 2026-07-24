# Repository Context: Proxmox backup restore verification

本書はbackup restore verificationを構成するplaybook / roleの横断関係を示す非規範Contextである。許可、禁止、停止条件は [`proxmox_backup_restore_verify_policy.md`](../../policies/proxmox_backup_restore_verify_policy.md) が正本であり、競合時はPolicyを優先する。単一taskのcommand、判定式、既定値はplaybook / role / varsを正本とする。

## 入口と実行境界

| 入口 | 主role | 横断的な責務 |
|---|---|---|
| `proxmox_backup_restore_verify.yml` | `proxmox_backup_restore_verify` | 対象選定、dynamic group作成、backup実restore、boot / health、cleanup、report、通知 |

playbookは対象選定を行うPlayと、動的に選ばれたrestore nodeでroleを動かすPlayから成る。tester-gateは`risk-accepted`で、`--check`時もroleを`check_mode: false`で実行するため、本入口はdry-runにならない。`tester_mode=true`は入口で拒否される。

## 対象選定とデータflow

```text
cluster resources / VM tags / config
  -> monthly rotation or manual target
  -> restore node / agent expectation
  -> dynamic brv_restore_targets group
  -> restore verification role
```

- cluster resourcesから`verify` tag付きQEMU VMを抽出し、VM ID順と現在月からmonthly対象を決定する。
- `target_vmid`が指定された場合はmonthly rotationだけを迂回し、対象の存在確認は維持する。
- restore nodeは`prefer<node>` tag、health expectationは本番VM configのagent設定から決める。
- 選定結果はdynamic groupへ渡し、inventory / group vars / host varsを対象決定のために変更しない。
- backup storage未指定時のstorage discovery、latest backupのctime選定、restore先storageと専用restore VMIDの実値はcode / varsを正本とする。

## role lifecycle

```text
minimal lock
  -> preexisting residue guard
  -> latest backup selection
  -> restore and owner stamp
  -> NIC removal
  -> start and health
  -> rescue
  -> always: cleanup -> unlock -> report -> notify -> conditional re-fail
```

- roleはrestore試行前にcleanup判定用flagを初期化し、restore command前にattempted状態へ移す。
- agent対応時はguest agent情報、agent無し時はsettle後のrunning状態をhealth結果として扱う。
- lifecycle本体の失敗はrescueでverification failureとして記録し、alwaysを必ず通す。
- destructive commandの条件、OK / NG、failはAnsible taskが管理し、別shell scriptへ判断を移さない。

この節は処理の横断順序を示すもので、単一task実装を複製しない。許可、停止、cleanup条件はPolicyを参照する。

## lock、ownership、cleanup

- lockはpmxcfs上のempty directoryをatomicに作成するminimal guardである。取得できない場合はwaitせず本体を停止する。
- lockを取得したrunだけがunlockを試みる。現行roleのunlockはbest-effortで、失敗単独ではcleanup failureまたはnon-zeroにならない。
- 開始時に専用restore VMが存在する場合はpreexisting residueとして本体を停止し、cleanup対象にしない。
- restore成功後にrun固有owner tokenをdescriptionへ刻印する。cleanup時はown token、未刻印、other tokenを分ける。
- 未刻印はrestore途中失敗の回収経路、other tokenはdestroy skip経路である。現行roleではother token分岐だけで`cleanup_ok=false`にはしない。
- cleanup blockのfailure、特にdestroy失敗は`cleanup_ok=false`へ到達する。stopはbest-effortである。
- 最終re-failはverification failure OR cleanup failureである。other-owner、unlock、reportの失敗条件を追加しない。

lockの存在は本番危害防止の根拠ではない。専用restore VMIDのhard guard、開始前residue、owner tokenが独立して破壊対象を制限する。

## reportと通知

- roleはverification、health、cleanup、ownershipの実行結果をJSON reportへまとめ、実行コントローラ側へ保存する。
- report保存はbest-effortであり、失敗単独では最終終了codeを変更しない。
- common Slack taskへpriority、channel、status、結果要約を渡す。通知もbest-effortである。
- report directory、lock path、storage名、専用restore VMID、poll / settle値の実値はdefaults / vars / taskを正本とし、本Contextへ固定しない。

## 関連

- [Policy](../../policies/proxmox_backup_restore_verify_policy.md)
- [System Context](../system/proxmox.md)
- [playbook map](playbook-map.md)
- [role map](role-map.md)
- [Phase 1 investigation](../../reviews/policy_standardization/2026-07-24_017_investigation_proxmox_backup_restore_verify_policy_rewrite.md)
