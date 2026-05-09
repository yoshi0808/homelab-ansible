# Ubuntu VM Patch Policy v1.0

作成日: 2026-05-09
版: v1.0
対象: homelab 環境の Ubuntu VM 全般

---

## 1. 目的

この文書は、homelab 環境における Ubuntu VM のパッチ運用方針を定義する。

Proxmox ホストとは異なり、Ubuntu VM は Ubuntu Pro による自動パッチ適用を基本とする。

Ansible の役割は、パッチ適用そのものではなく以下に限定する。

- VM の特性に応じた reboot タイミングの制御
- センシティブな VM における reboot 後のサービス疎通確認
- センシティブな VM の日次 healthcheck
- 異常・reboot 実行時の通知

---

## 2. 対象 VM と特性

### 2.1 基本的な考え方

VM の特性に応じて、以下の 2 つの方針を使い分ける。

1. Wi-Fi 認証や管理系サービスなどダウンすると困るサービスを保有する VM については、深夜の計画的 reboot を Ansible で管理する。
2. 開発環境・バックアップ機能・検証環境等の VM は自動 reboot とする。

### 2.2 VM 一覧

| VM | 役割 | reboot 方針 | healthcheck | 理由 |
|---|---|---|---|---|
| `authy` | FreeRADIUS / WPA3 Enterprise / EAP-TLS 認証基盤 | 深夜に計画的 reboot（Ansible 管理） | あり | サービス停止が家庭内 Wi-Fi 認証断につながる |
| `ansy` | Ansible 開発環境 | 自動 reboot（unattended-upgrades 任せ） | なし | 開発 VM で再構築可能。コードは GitHub、VM は Proxmox バックアップで保護済み |

将来 Ubuntu VM が追加された場合は、本表に追記し、どちらの方針を採用するかを明記する。

---

## 3. パッチ適用方針

### 3.1 Ubuntu Pro に任せる

パッケージの更新は Ubuntu Pro + unattended-upgrades が自動で行う。

Ansible はパッケージ更新を行わない。

対象:

- セキュリティパッチ（`${distro_id}:${distro_codename}-security`）
- ESM パッチ（`${distro_id}ESM:${distro_codename}-infra-security`）
- ESM Apps パッチ（`${distro_id}ESMApps:${distro_codename}-apps-security`）

### 3.2 サービス自動再起動について

パッケージ更新時、apt の post-install スクリプトによりサービスが自動再起動される場合がある。

例として、freeradius パッケージ更新時には `freeradius` サービスが再起動され、数秒〜十数秒の停止が発生し得る。

以下の理由で許容する。

- 更新は深夜帯に行われる
- 深夜帯はサービスへの需要がほぼない
- homelab 環境として実害がほぼない

サービスを Package-Blacklist に追加して手動管理に切り替えることは、対応忘れのリスクが高いため採用しない。

---

## 4. reboot 方針

### 4.1 計画的 reboot（方針1のVM）

`Unattended-Upgrade::Automatic-Reboot "false"` に設定する。

reboot のタイミングは Ansible が制御する。

深夜（02:00 頃）に `ubuntu_nightly.yml` が reboot_required を確認し、必要な場合のみ reboot する。

reboot 後、対象 VM のサービス状態と疎通を確認する。

例: authy の場合は freeradius の状態と 1812/udp・1813/udp の Listen を確認する。

### 4.2 自動 reboot（方針2のVM）

`Unattended-Upgrade::Automatic-Reboot "true"` に設定する。

unattended-upgrades が reboot_required を検出した場合、自動で reboot する。

Ansible による管理・監視・healthcheck は行わない。

例: ansy の場合は Ansible コードが GitHub に、VM 自体が Proxmox バックアップで保護されているため、自動 reboot で問題ない。

### 4.3 reboot 判定（方針1のVMのみ）

以下のいずれかを満たす場合、reboot が必要と判定する。

- `/var/run/reboot-required` が存在する
- `needrestart` が reboot 要と判定する

---

## 5. Playbook 構成

方針1のVM（authy など）のみを対象とする。方針2のVM（ansy など）は Ansible 管理対象としない。

| Playbook | 目的 | 実行タイミング | 変更有無 |
|---|---|---|---|
| `radius_healthcheck.yml` | FreeRADIUS 稼働確認・日次レポート | 朝（06:00 頃） | なし |
| `ubuntu_nightly.yml` | reboot_required 確認 → 条件付き reboot → サービス確認 → 通知 | 深夜（02:00 頃） | あり（reboot） |

healthcheck は VM が提供するサービスに応じた専用 playbook を用意する。

`ubuntu_nightly.yml` は方針1の VM 共通の深夜 reboot playbook とする。

### 5.1 healthcheck playbook

read-only。各 VM のサービス稼働状態を収集・判定・レポートする。

正常以外（WARNING / CRITICAL）の場合は通知する。

朝の healthcheck で「前夜に reboot した・サービスは生きている」を確認できる。

手動での単体実行も可。

### 5.2 ubuntu_nightly.yml

深夜専用の複合 playbook。

処理フロー:

```text
1. reboot_required を確認する
2. reboot_required = false の場合、何もしない（通知なし）
3. reboot_required = true の場合:
   a. reboot 実行通知を送る
   b. reboot する
   c. 起動完了を待つ
   d. 対象 VM のサービス状態を確認する
   e. 確認結果を通知する（OK / CRITICAL）
```

healthcheck playbook とは別ファイルとして切り出す。

理由:

- read-only と変更系を同じ入口に混在させない（`core.md` Section 17 方針）
- healthcheck playbook は昼間の手動実行でも使う

---

## 6. 通知方針

### 6.1 通知条件

| 状況 | 通知 |
|---|---|
| ubuntu_nightly: reboot_required = false | なし |
| ubuntu_nightly: reboot 実行 → サービス確認 OK | あり（reboot した旨 + OK） |
| ubuntu_nightly: reboot 実行 → サービス確認 NG | あり（CRITICAL） |
| healthcheck: OK | なし |
| healthcheck: WARNING | あり |
| healthcheck: CRITICAL | あり |

### 6.2 通知タイミングと確認

深夜の通知はスマートフォンの睡眠モード中に送信される。

翌朝に確認する運用で問題ない。

### 6.3 通知方法

`inventories/vars/mail.yml` の SMTP 設定を使い、`community.general.mail` モジュールで送信する。

Proxmox パッチ通知と同じ仕組みを使う。

---

## 7. systemd timer 設定方針

Semaphore UI 導入前は、quory（到着後）または ansy 上の systemd timer で実行する。

| timer | 実行対象 | 実行時刻 |
|---|---|---|
| `ubuntu-nightly.timer` | `ubuntu_nightly.yml` | 毎日 02:00 |
| `radius-healthcheck.timer` | `radius_healthcheck.yml` | 毎日 06:00 |

`RandomizedDelaySec` を設定し、実行時刻を若干ばらつかせる。

Semaphore UI 導入後は、systemd timer から Semaphore UI の Schedule へ移行する。

---

## 8. 現在の設定確認（2026-05-09 時点）

### authy

`needrestart` 実行結果:

```
Running kernel seems to be up-to-date.
No services need to be restarted.
No containers need to be restarted.
No user sessions are running outdated binaries.
```

Ubuntu Pro の自動パッチが正常に機能しており、reboot 不要・サービス再起動不要の状態を確認済み。

`50unattended-upgrades` の重要設定:

```
Unattended-Upgrade::Automatic-Reboot "false";
```

この設定を維持する。変更する場合は本文書を更新すること。

---

## 9. 今後の実装順序

1. `radius-healthcheck.sh` に `reboot_required` を追加（`/var/run/reboot-required` 確認）
2. `radius_healthcheck` role の tasks に `reboot_required` の fact 化と通知条件への組み込み
3. `radius_healthcheck.yml` に通知 task を追加（WARNING / CRITICAL / reboot_required 時）
4. `ubuntu_nightly.yml` と対応 role を新規作成
5. ansy で手動実行テスト
6. quory 到着後に systemd timer 化
7. Semaphore UI 導入後に Schedule へ移行
