# Phase 2 TODO 2-2 System Context 実装記録

作成日: 2026-07-22
担当Role: `implementer`

## 実装概要

`docs/ai/context/system/`を新設し、homelab全体、Proxmox、RADIUS、monitoring、Semaphoreの5領域を分割して記録した。各文書には、領域の役割、ノードの役割、依存関係、可用性、安全上の注意、想定読者Roleを含めた。

変動しやすい実ゲスト配置、閾値、scheduleの有効状態を固定事実として書かず、現在のinventory・playbook・role・UIで確認すべき情報として区別した。

## 作成ファイルと情報源

| 作成ファイル | 主な情報源 |
|---|---|
| `docs/ai/context/system/overview.md` | `docs/ai/core.md`、`docs/ai/role-routing-index.md`、`inventories/homelab/hosts.yml`、旧core §1–4、計画書TODO 2-2/2-4 |
| `docs/ai/context/system/proxmox.md` | Proxmox health/hardware/snapshot/patch系playbook、対応roleの`tasks`/`defaults`、`proxmox_patch_weekly_full.yml`、inventory、移行表C16-02 |
| `docs/ai/context/system/radius.md` | `playbooks/radius_healthcheck.yml`、`roles/radius_healthcheck/tasks/{main,check}.yml`、defaults、inventory、Proxmox patchのrecovery mute連携 |
| `docs/ai/context/system/monitoring.md` | `playbooks/monitoring_healthcheck.yml`、`roles/monitoring_healthcheck/tasks/{main,check}.yml`、defaults、`playbooks/cert_renew.yml`、inventory |
| `docs/ai/context/system/semaphore.md` | inventoryの`control_nodes`/`semaphore_servers`、`roles/systemd_timers/defaults/main.yml`、`playbooks/cert_renew*.yml`、`roles/homelab_cert_renew/tasks/deploy_semaphore.yml`、Proxmox health/hardware summary実装 |

書き方と粒度の参考には`docs/ai/context/operations/healthcheck.md`を使用した。背景は`docs/ai/reviews/agent_skills_reorganization_plan.md`のTODO 2-2とRole別Contextマトリクスだけを参照し、過去reviewはSemaphore UI移行の現行コード注釈を補う必要最小限の記録だけを確認した。

## 自己検証

- [x] 5ファイルすべてに役割、ノードの役割、依存関係、可用性、安全上の注意を記載した。
- [x] 5ファイルすべての末尾に「想定読者Role」を1行記載した。
- [x] `docs/ai/context/ansible/`配下を作成・変更していない。
- [x] ホスト表現をinventory group/host名または`ansible_host`相当のFQDNに限定した。
- [x] IPアドレスを記載していない。
- [x] VLAN IDを記載していない。
- [x] VM IDを記載していない。
- [x] password、token、private key本文、認証情報、秘密情報を記載していない。
- [x] 変化しやすい閾値とschedule時刻をSystem Contextへ固定していない。
- [x] 実ホスト操作、Semaphore UI変更、inventory変更、commit、pushを行っていない。

確認には、対象6ファイルのdiff確認、IPv4 literal候補の検索、禁止語と識別子表現の目視確認を用いる。文書内で禁止対象そのものを説明する語（`IPアドレス`、`VLAN ID`、`VM ID`、`password`、`token`等）は安全注意・検証項目として意図的に記載しているが、値は記載していない。

## 未確認事項

- Semaphore UI上のjob template、schedule、extra variables、現在のenabled状態はリポジトリ外の状態であり未確認。`systemd_timers`のコメントは「UIへ移行済み」というコード上の意図を示すが、現在のUI状態の保証には使わない。
- `authy`、`monnie`、`ansy`等の現在のProxmoxゲスト配置は未確認。配置は変動情報としてSystem Contextへ固定せず、保守時のruntime preflightを正とした。
- RADIUSおよびmonitoringのinventory上の対象は各1ホストだが、リポジトリ外の冗長経路や外部監視の有無は未確認。
- 実環境の現在のservice状態、quorum、replication、名前解決、到達性は未確認。本作業は文書作成のみであり、実ホストへ接続していない。

## 読込プロセスの所感

`core.md`と`role-routing-index.md`からRoleと安全境界を先に確定し、計画書のTODO 2-2で文書の目的と完了条件を絞った後、対象inventory groupから対応playbook・roleへ辿る流れは有効だった。領域別Contextを分けることで、RADIUS案件にProxmox patch実装の詳細を毎回読ませるような過剰読込を避けられる。

一方、Semaphoreのschedule実態はUIというGit外状態にも存在するため、コードと過去記録だけでは「現在有効」を断定できない。System Contextには安定した実行経路と停止条件だけを残し、UIの現在状態は作業時に確認する設計が適切である。また、healthcheck ContextとSystem Contextは一部接点があるが、前者は実装パターン、後者は環境の役割・依存・可用性を扱うことで重複を抑えた。

## 未対応事項・注意点

- Tier 4 Phase 1の調査・叩き台であり、reviewで事実誤認や粒度の指摘があれば修正する。
- System Contextの運用開始後、inventoryや実行経路が変わった場合は、コード変更と同時に該当領域だけを更新する。
- 本作業の対象外であるAnsible Repository Contextは別チームの成果物を正とし、本実装では先回りして作成しない。
