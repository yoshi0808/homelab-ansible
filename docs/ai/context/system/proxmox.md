# System Context: Proxmox

本書は環境事実を記録する非規範Contextである。patchの許可、禁止、停止条件は [`proxmox_patch_policy.md`](../../policies/proxmox_patch_policy.md)、backup restore verificationの許可、禁止、停止条件は [`proxmox_backup_restore_verify_policy.md`](../../policies/proxmox_backup_restore_verify_policy.md) を正本とし、競合時は該当Policyを優先する。

## 領域の役割

`proxmox` groupは`pve1` (`pve1.internal`)と`pve2` (`pve2.internal`)から成るProxmox VEクラスタである。ゲストの稼働基盤であり、healthcheck、hardware check、snapshot check、patch dry-run、単一ノードpatch、rolling patchの対象になる。

## ノードの役割

- `pve1`: 通常稼働の中心となるメインノード。rolling patchでは`pve2`の検証完了後に処理する。
- `pve2`: セカンダリノード。先行検証、縮退運用、退避先として扱い、rolling patchでは先に処理する。
- `quory`: `control_nodes`のクラスタ外制御点。`proxmox_patch_weekly_full.yml`は実行元が許可された外部制御ノードであり、Proxmoxノード自身またはクラスタ上のゲストではないことをpreflightで確認する。

## 依存関係

- `proxmox_healthcheck`はquorum、ZFS、主要サービス、systemd失敗、root filesystem、apt/dpkg、reboot要否、レプリケーションを確認し、patch前後のgateにも使われる。
- `proxmox_hw_check`はCPU、memory、ZFS、disk、NICと収集成否をreport化する。`proxmox_snapshot_check`はsnapshot収集と経過時間の重大度分類を行う。
- patch系はhealthcheckとdry-runの結果に依存する。単一ノードpatchは、対象上の稼働ゲストと制御ノードを実行時に検出し、退避未完了なら停止する。
- rolling patchは両ノードのhealthcheckとdry-runを通過後、`pve2`の退避・patch・post-healthcheck・復帰を完了してから、`pve1`を同順序で処理する。
- `authy`、`monnie`、`sophos-fw`はProxmox保守時に影響を受け得るサービスとしてrecovery mute対象になる。実際のゲスト配置は変化し得るため、この文書へ固定しない。
- healthcheckとhardware checkは、Semaphore jobから結果を読める1行summaryを出力する。詳細reportは実行コントローラ側へ保存される。

## 可用性

- 2ノードを同時に保守せず、`pve2`から`pve1`へ順番に処理することが基本である。
- patch続行には、両ノードの事前healthcheck、対象ノードからのゲスト退避、各ノードのpost-healthcheck成功が必要である。`pve2`の復帰と健全性を確認できない状態で`pve1`へ進めない。
- quorum、レプリケーション、ZFS、主要サービスの異常はクラスタ全体へ波及し得る。WARNINGもpatch前に確認し、CRITICALは続行条件を満たさない。
- `quory`をクラスタ外の制御点として維持する。`ansy`の配置は変化し得るため、対象ノード上の制御系ゲストはコードが実行時に検出する。

## 安全上の注意

- `proxmox_healthcheck.yml`、`proxmox_hw_check.yml`、`proxmox_snapshot_check.yml`はread-only診断を意図するが、収集script配置やlocal report保存を含む。通知抑止条件も含めて各`tester-gate`を確認する。
- `proxmox_patch_dryrun.yml`は実patchなし(package metadataの更新とシミュレーションのみ)であり、上記3つと同じ「収集のみ」ではない。`apt-get update`でpackage metadataを更新するため、完全な無変更のread-only診断と同一視しない。`tester-gate`を確認する。
- `proxmox_patch_apply_node.yml`と`proxmox_patch_weekly_full.yml`は変更系である。`--check`ではread-only preflightが実行されても、apply・reboot・migrationを本番実行したことにはならない。逆に`--check`なしの実行は本番適用であり、人間の明示判断なしに行わない。
- 単一ノードpatchでも、退避を済ませたという説明だけを信頼せず、playbookの実行時guardを維持する。
- `pve2`先行の順序を変えない。`pve1`へ進む判断はdry-runと先行ノードの結果を確認した後に行う。
- snapshot report等に実行時のゲスト識別子が含まれ得るが、それをContextやレビュー文書へ転載しない。
- IPアドレス、VLAN ID、VM ID、認証情報、秘密情報を記載しない。到達先はinventory名またはFQDNで表す。

## patch分類とcontrol nodeの配置

- patch dry-runで使う分類CLIはansy、quory、またはmacOS側で動き、Proxmox hostへは配置しない。
- ansyはProxmox上のVMとして動く開発・限定実行環境、quoryはcluster外の本番Ansible実行基盤である。
- weekly fullはcluster外control nodeを前提とする。ansyの実際の所在は変化し得るため、実行時preflightの検出を正本とする。
- 導入時期や到着前後の経緯は現行構成ではなく案件履歴なので、本書へ固定しない。

## backup restore verificationの環境事実

- monthly productionの制御点は`quory`、development / manual CLIの制御点は`ansy`である。
- 検証対象とrestore nodeはProxmox側のVM tagを情報源とし、Ansible inventoryへ対象VMを固定列挙しない。
- backup sourceはvzdump backupを提供するstorageである。明示指定がない場合に参照するstorage種別とcontent条件はRepository Contextとcodeを正本とする。
- restore先は検証専用storageと専用固定restore VMIDである。storage名と数値VM IDはvars / codeを正本とし、本Contextへ固定しない。
- backup restore verificationは本番VMのconfigを選定情報として参照するが、restore / boot / cleanupの変更対象は使い捨ての専用restore VMに分離される。

想定読者Role: Tech Lead=依存とrolling順序を詳細確認、Implementer/Reviewer/Tester=Proxmox案件時に全体を詳細確認、その他=概要のみ。
