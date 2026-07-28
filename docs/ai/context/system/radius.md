# System Context: RADIUS

## 領域の役割

`radius_servers` groupの`authy` (`authy.internal`)は、FreeRADIUSによるネットワーク認証基盤である。`radius_healthcheck.yml`と`radius_healthcheck` roleは、サービスとRADIUSの待受、journal、memory、root filesystemを観測し、結果を分類する。

## ノードの役割

- `authy`: inventory上のRADIUS対象ホスト。FreeRADIUSサービスを提供し、healthcheckと関連する保守の対象になる。
- `quory`: 本番AnsibleおよびSemaphore jobの実行基盤。healthcheckのreport保存・通知経路の起点になり得る。
- `pve1` / `pve2`: `authy`が仮想ゲストとして稼働し得る基盤。配置は変化するため固定せず、Proxmox保守では実行時に確認する。

## 依存関係

- ネットワーク機器やクライアントの認証は`authy`のFreeRADIUSサービスとネットワーク到達性に依存する。
- `radius_healthcheck`は収集scriptを対象へ配置し、Ansible側でサービス、待受、journal、resource使用量をWARNING/CRITICALへ分類する。reportは実行コントローラ側へ保存し、異常時は共通通知経路を利用する。
- Proxmox patch playbookは保守中の自動復旧競合を避けるため`authy`をrecovery mute対象にする。これは配置を固定する情報ではなく、認証停止の波及が大きいことを示す依存である。
- 認証方式や証明書の秘密情報はinventory外の適切なsecret管理に依存する。本Contextは値や保管場所の詳細を正本にしない。

## 可用性

- inventory上のRADIUS対象は`authy`の1ホストである。このリポジトリからRADIUSサービスの冗長化を前提にしてはならない。
- サービス停止や待受異常は認証利用者へ直接波及し得る。journalやresourceのWARNINGも障害予兆として扱う。
- healthcheck成功は、その時点の対象ホスト内の観測結果であり、すべてのネットワーク機器からのend-to-end認証成功を保証しない。
- Proxmox保守や`authy`自身のpatch/rebootでは、認証停止時間と復旧確認を独立して考える。

## 安全上の注意

- `radius_healthcheck.yml`は`safe-readonly`だが、冪等なscript配置、local report保存、異常通知を含む。Testerは通知抑止guardを含めてmarkerと実装を確認する。
- healthcheckの収集scriptへ正常・異常判定、通知、report保存を混ぜない。判定と副作用はAnsible側の責務である。
- healthcheckをpatch/rebootの許可と読み替えない。変更系playbookは別の安全分類と人間判断を必要とする。
- 認証に関するcertificate、private key、password、token、共有secretを表示・記録・複製しない。
- IPアドレス、VLAN ID、VM IDを記載せず、`authy`または`authy.internal`で表す。

想定読者Role: Coordinator=認証依存と停止影響を詳細確認(2026-07-29、Tech Lead廃止に伴い統合)、Implementer/Reviewer/Tester=RADIUS案件時に詳細確認、その他=概要のみ。
