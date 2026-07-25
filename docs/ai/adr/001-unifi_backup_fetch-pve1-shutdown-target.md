# ADR-001: unifi_backup_fetch.yml の実行host選定方式(pve1夏季シャットダウン対応)

**Status:** Accepted

## Context

`playbooks/unifi_backup_fetch.yml`は`hosts: pve1`固定で、CloudKey Gen2 PlusのUniFi OSバックアップを取得しSynology NFS(`/mnt/pve/Synology-nfs/user-backup/unifi`)へ保存する。tester-gateは`risk-accepted`(常に本実行、dry-runモード無し)。

pve1は夏季平日シャットダウン運用中([[project_pve1_weekday_shutdown_status]]相当、docs/ai/context/system/proxmox.mdも参照)で、日中は電源オフが既定状態になった。この結果、本playbookが対象ホスト到達不可で実行できない。

保存先`/mnt/pve/Synology-nfs/...`は`/mnt/pve/`prefixから明らかにProxmoxのstorage.cfg経由のcluster storageであり、Ansibleではこのリポジトリのどのinventory/host_varsからも管理されていない(grep確認済み、host_vars配下に該当設定なし)。Proxmoxのcluster storageはcluster全体へ自動適用される設計のため、pve2にも同一パスで同じマウントが存在する可能性が高いが、このリポジトリのコードからは断定できず実機確認が必要。

Yoshinobuから提示された方向性:
- (a) pve1が使えない場合はpve2へフェイルオーバーして同じNFS経由で保存する。
- (b) バックアップサイズが小さいため、PVE経由のNFSに依存せずquoryへ直接保存先を持たせる。

判断はTech Lead(techlead)に委任された。

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| (a) pve1/pve2間で動的フェイルオーバー | 保存先パスその他は無変更。新規インフラ不要(Proxmox cluster storageは既にcluster全体へ適用される設計)。変更範囲がplaybookのhost選定ロジックのみに閉じる。CloudKey/quory間のnetwork reachabilityも既存のまま(pve1もpve2もLAN上でcloudkey.internalへ到達可能という前提は同一)。 | pve1・pve2が同時に到達不能な場合(将来の同時保守等)は依然として実行できない。実行hostが動的に変わるため、フェイルオーバー検出ロジック(preflight)を新規実装する必要がある。 |
| (b) quoryへ直接保存先を新設 | Proxmoxクラスタの状態(pve1/pve2どちらの起動状態)に一切依存しなくなる。quoryは既に他playbook(proxmox_patch_weekly_full等)で「クラスタ外の常時稼働制御点」として扱われており、設計思想として一貫する。 | quoryに新規NFS client mountを構築する必要がある(このリポジトリに再利用できる既存roleパターンなし、新規インフラ)。Synology NFSエクスポート側の許可クライアント範囲を確認・追加する必要がある可能性(未確認、実機作業)。変更範囲が本playbookに閉じず、quoryのシステム構成(mount)にも及ぶ。 |

## Decision

**Option (a): pve1/pve2間の動的フェイルオーバーを採用する。**

## Trade-off Analysis

- 保存先NFSパスがProxmox cluster storageである以上、pve1・pve2はどちらも「同じストレージへの入口」に過ぎない。フェイルオーバー対象を同一cluster内に留めることは、新しい依存関係やインフラを増やさずに素直に解決できる。
- pve1の停止は障害ではなく意図された運用状態であり、pve2は常に稼働している前提(VM/CTは既にpve2へ全移行済み、[[project_pve1_weekday_shutdown_status]])。したがって「pve1優先、居なければpve2」という単純な優先順位付きフェイルオーバーで実運用上の問題を解消できる。
- Option (b)はより将来的に強い解(Proxmoxクラスタ全体が使えなくても動く)だが、「バックアップサイズが小さい」以外のメリットに対して、新規NFS mount構築・エクスポート許可確認という実コストが不釣り合いに大きい。今回の引き金は「pve1が運用上意図的に停止している」ことであり、「pve1もpve2も同時に使えない」事態は現時点で想定されていない。過大な工程を避ける([[feedback_process_weight_must_match_change_risk]])判断として、必要になった時点でOption (b)へ切り替える方が合理的。
- pve1/pve2両方に到達できない場合は、フェイルオーバーでは解決しないため、原因追跡可能な明確な失敗メッセージで停止する(無言のUNREACHABLEにしない)。

## Consequences

- `playbooks/unifi_backup_fetch.yml`に、pve1→pve2の順で到達可能な1ホストを選ぶpreflightロジックを追加する。両ノード到達時にbackupを二重実行・二重ローテーションしないよう、選定後は単一hostにのみ対して本処理を実行する。
- `roles/unifi_backup_fetch`本体(tasks/main.yml、defaults/main.yml)は変更不要と見込む(host非依存の実装のため)。実装時に依存が見つかれば個別対応する。
- 将来「pve1・pve2が同時に長期不在」というシナリオが実際に発生した場合は、本ADRをSupersedeしOption (b)へ切り替える判断を別途行う。
- `docs/ai/context/system/proxmox.md`は今回は更新しない(本変更は単一playbookの実行host選定の話であり、Proxmox全体のSystem Contextを書き換えるほどの一般化されたパターンではないと判断)。同種の要望が他playbookでも繰り返し出た場合はOperations Context化を再検討する。
