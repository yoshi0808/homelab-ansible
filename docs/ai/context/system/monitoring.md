# System Context: Monitoring

## 領域の役割

`monitoring_servers` groupの`monnie` (`monnie.internal`)は、Prometheus、Grafana、Loki、unpollerを稼働させ、homelabのmetrics、dashboard、logs、ネットワーク観測を担う。`monitoring_healthcheck.yml`と`monitoring_healthcheck` roleは、これらのサービス、待受、memory、root filesystemを観測する。

## ノードの役割

- `monnie`: inventory上の監視対象ホスト。収集・可視化・ログ基盤とそのhealthcheckを担う。
- `quory`: 本番AnsibleとSemaphore jobの実行基盤。healthcheck reportやjob結果を集約する実行元になり得る。
- `pve1` / `pve2`: `monnie`が仮想ゲストとして稼働し得る基盤。配置は変化するためContextへ固定しない。

## 依存関係

- Grafanaは可視化、Prometheusはmetrics収集、Lokiはlogs、unpollerはネットワーク機器の観測を担い、いずれかの停止は監視範囲または表示能力を狭める。
- `monitoring_healthcheck`は収集scriptを対象へ配置し、Ansible側でサービス、待受、resource使用量をWARNING/CRITICALへ分類する。reportは実行コントローラ側へ保存し、異常時は共通通知経路を使う。
- 証明書更新では`monnie`のGrafana証明書配置とservice restartがあり、更新前後にmonitoring pause/resumeを実行する。
- Proxmox patch playbookは保守中の自動復旧競合を避けるため`monnie`をrecovery mute対象にする。
- unpollerの観測は`cloudkey_devices`側の管理情報へ依存し得るが、CloudKeyの構成詳細は本Contextの対象外である。

## 可用性

- inventory上の監視対象は`monnie`の1ホストである。このリポジトリから監視基盤自体の冗長化を前提にしてはならない。
- 監視基盤が停止すると、管理対象が稼働していても可視性が失われる。したがって「alertがない」ことだけを正常の根拠にしない。
- healthcheckは`monnie`内部の主要サービスとresourceを確認するが、全exporter、全dashboard、全log送信元のend-to-end正常性までは保証しない。
- Grafanaの証明書更新やservice restartは一時的にUIの可用性へ影響するため、pause/resumeと更新結果を確認する。

## 安全上の注意

- `monitoring_healthcheck.yml`は`safe-readonly`だが、冪等なscript配置、local report保存、異常通知を含む。通知抑止guardを含めて`tester-gate`と実装を照合する。
- 収集scriptは収集とJSON整形に限定し、重大度分類、通知、report保存はAnsible側で行う。
- monitoring pauseは観測を意図的に抑止する操作であり、変更作業の終了時にresumeできたことを確認する。監視停止を長時間放置しない。
- 証明書や通知経路のprivate key、password、tokenを表示・記録・複製しない。
- IPアドレス、VLAN ID、VM IDを記載せず、`monnie`または`monnie.internal`で表す。

想定読者Role: Tech Lead=観測喪失の波及を詳細確認、Implementer/Reviewer/Tester=監視案件時に詳細確認、その他=概要のみ。
