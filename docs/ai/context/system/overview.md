# System Context: homelab全体概要

## 役割

このリポジトリが扱うhomelabは、Git管理されたAnsibleコードを開発する`ansy`、確定済みコードを取得して本番実行する`quory`、仮想化基盤の`proxmox`、認証の`radius_servers`、観測の`monitoring_servers`を中心に構成される。Semaphoreは`quory`を本番実行基盤とするGUI・定期実行の入口であり、`ansy`にも開発側のSemaphoreがある。

AI作業は`role-routing-index.md`に従い、Coordinator、Tech Lead、Implementer、Reviewer、Testerが分担する。System Contextは、Tech Leadが対象領域と依存を選び、各Roleが実環境への影響と安全境界を判断するための地図である。現在のコード、inventory、対象Policyが常に優先される。

## ノードの役割

| inventory group | host | 役割 |
|---|---|---|
| `dev_nodes` | `ansy` (`ansy.internal`) | Ansibleの開発・レビュー・検証環境 |
| `control_nodes` | `quory` (`quory.internal`) | Gitから取得した確定済みコードの本番Ansible実行基盤。SemaphoreとProxmoxクラスタ外の制御点 |
| `semaphore_servers` | `ansy`, `quory` | 開発側・本番側のSemaphore実行環境 |
| `proxmox` | `pve1`, `pve2` (各`.internal`) | Proxmox VEクラスタ。ゲストの稼働、レプリケーション、段階的な保守を担う |
| `radius_servers` | `authy` (`authy.internal`) | FreeRADIUSによるネットワーク認証基盤 |
| `monitoring_servers` | `monnie` (`monnie.internal`) | Prometheus、Grafana、Loki、unpollerによる収集・可視化・ログ基盤 |

必要な案件に限り、ネットワーク境界の`sophos`とネットワーク機器管理の`cloudkey_devices`を依存先として扱う。これらの詳細は本System Contextの対象外である。

## 依存関係

- `ansy`で作られた変更はGitで確定され、`quory`が本番実行に使う。作業ツリーを直接本番の正本にしない。
- `quory`はProxmoxクラスタ外からrolling patchや証明書更新を制御する。制御ノードが保守対象クラスタ上へ載っていないことが、長時間のクラスタ保守では重要である。
- `authy`と`monnie`は、それぞれ認証と観測を提供する単独のinventory対象である。Proxmox保守時の実際のゲスト配置は固定文章で決めず、playbookが実行時に確認する。
- healthcheckのreport、通知、Semaphore job表示は相互補完であり、どれか一つだけを可用性の根拠にしない。
- 内部ホストはFQDNまたはinventory名で参照し、名前解決は実行環境側で担保する。

## 可用性

- Proxmoxは2ノードを順番に保守できる設計だが、quorum、レプリケーション、退避先の健全性、外部制御点の維持が前提である。
- RADIUSと監視はinventory上それぞれ1ホストであり、このリポジトリだけから冗長化を前提にしてはならない。
- `ansy`と`quory`は用途を分離している。両方が`semaphore_servers`に属していても、開発系と本番系が自動的に相互フェイルオーバーすることはコードから確認できない。
- 変化しやすいゲスト配置、scheduleの有効状態、サービスの現在状態は、この文書ではなく実行時のread-only確認と対象UIで確認する。

## 安全上の注意

- 本番適用、patch、reboot、migration、firewall・inventory変更、commitは人間の明示判断を必要とする。
- healthcheckと変更系処理を同じ安全分類として扱わない。各playbook先頭の`tester-gate`と対象Policyを読む。
- リポジトリへIPアドレス、VLAN ID、VM ID、認証情報、秘密情報を記載しない。ホストはinventory名またはFQDNで表す。
- `quory`上でコードを直接編集・commitせず、Gitの確定済み内容を本番実行の正本とする。
- System Contextの記述と現在のinventory・コードが異なる場合は、現在のコードを確認し、勝手に統合せずTech Leadへ不一致を報告する。

想定読者Role: Tech Lead=全体を詳細に確認、他Role=概要を確認してから対象領域のみ詳細に読む。
