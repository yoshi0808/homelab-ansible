# Time Sync Check Policy v1.0

作成日: 2026-06-25
版: v1.0
対象: quoryを基準としたhomelab主要ホストのNTP同期状態チェック（time_sync_check
role / playbook）、および各ホストへのquory参照追加準備（time_sync_ntp_reference
role / playbook）

参照:

- docs/ai/prompts/core.md
- playbooks/cloudkey_cert_deploy.yml（vars_filesでのVault読み込みパターン）
- roles/common_slack/tasks/notify.yml
- docs/ai/reviews/time_sync_check/（要求仕様・実装・レビュー一式）

---

## 変更履歴

| 版 | 日付 | 変更内容 |
|---|---|---|
| v1.0 | 2026-06-25 | 初版。quory基準の自己報告方式によるNTP同期チェックと、quory参照追加の準備playbookを定義。 |

---

## 1. 目的

quoryを基準として、homelab内の主要ホストの時刻同期状態を定期的に確認する。
SSHで各ホストの`date`を直接比較する方式ではなく、各ホストのNTPクライアントが
報告する同期状態（offset値）を優先して使う。NTPプロトコル自体がネットワーク
遅延を補正する仕組みを持つため、SSH越しの値取得よりも正確に時刻差を測定できる
（sophos-fwのみ、自己報告手段が無いため直接比較で代替する例外）。

当初はSSHで各ホストの`date`を一回取得して差分を計算する方式を検討したが、
実機検証でSSH接続確立自体の測定誤差（数百ms〜数秒）が検出したい時刻ズレと
同程度以上になることが判明し、各ホスト自身の自己診断結果を収集する方式へ
転換した（経緯: docs/ai/reviews/time_sync_check/2026-06-23_006_implement.md）。

---

## 2. 対象と実行

| 項目 | 内容 |
|---|---|
| 基準ノード | quory（chrony、外部NTP=Ubuntu poolに同期） |
| 比較対象 | pve1, pve2, ansy, monnie, authy（chrony）、sophos-fw（独自ntpclient）、cloudkey（systemd-timesyncd） |
| 実行元 | quory（本番）/ ansy（開発・CLI） |
| 安全度 | read-only（time_sync_check.yml）。NTPクライアント設定へのquory参照追加は別playbook（time_sync_ntp_reference.yml、変更系）で実施する |

実行元ホスト自身は比較対象から動的に除外する（`time_sync_check_executor_host`、
`lookup('pipe', 'hostname -s')`で判定。比較対象を固定リストで持たないことで、
quory実行時・ansy実行時いずれでも自己比較にならない）。

## 対応するPlaybook

| Playbook | 役割 |
|---|---|
| `time_sync_check.yml` | quoryを基準にhomelab主要ホストのNTP同期状態を確認し、閾値超過・収集失敗をSlack通知する（read-only）。 |
| `time_sync_ntp_reference.yml` | pve1/pve2/ansy/monnie/authyのNTPクライアント設定にquoryを参照先として追加する準備作業（変更系）。cloudkey・sophos-fwは対象外（§3参照）。 |

---

## 3. 対象と取得方式

| 対象 | NTPクライアント | offset取得方法 |
|---|---|---|
| quory（基準） | chrony | `chronyc tracking`の`System time` |
| pve1, pve2, ansy, monnie, authy | chrony | `chronyc tracking`の`System time` |
| cloudkey | systemd-timesyncd | SSH（パスワード認証）+ `timedatectl timesync-status`の`Offset` |
| sophos-fw | 独自ntpclient（BusyBox環境、offset非公開） | SSH→Advanced Shell経由 + `date +%s%3N`によるquoryとの直接時刻比較（自己報告手段が無いための例外） |

- cloudkeyはchronyではなくsystemd-timesyncdのため`chronyc`は使えない。
- sophos-fwはchrony/ntpd/systemd-timesyncdのいずれも存在せず、`/bin/ntpclient`が
  動作している。ログ（`/var/tslog/ntpclient.log`）には絶対時刻のみが記録され
  offset値が取れないため、direct比較で代替する。
- sophos-fwの直接比較は、Advanced Shellのメニュー遷移全体（SSH接続〜メニュー
  操作〜date取得〜exit）をコントローラー側でbefore/afterブラケットして誤差を
  記録する。単純な1コマンドの往復より大きい誤差（実機計測で約1秒規模）が
  混入するため、他ホストより大きい専用閾値
  （`time_sync_check_sophos_threshold_ms`、既定5000ms）を用いる。
  `time_sync_check_threshold_ms`（既定500ms）はchrony/cloudkey共通。

quoryへのNTPサーバー機能追加は不要（`/etc/chrony/chrony.conf`に
homelab管理ネットワーク向けのallow設定が既に設定済み・123/udp稼働確認済み）。

### CloudKeyのNTPサーバー一覧はGUI管理（time_sync_ntp_referenceの対象外）

CloudKeyのNTPサーバー設定はUniFi OSのGUIで管理されており「Auto」設定がある。
再起動・GUI保存操作で`/etc/systemd/timesyncd.conf`が再生成される可能性があり、
Ansibleでの直接ファイル編集はGUI管理と衝突しうる（sophos-fwと同様の判断）。
このため`time_sync_ntp_reference.yml`はcloudkeyを対象にしない。quory参照の
追加が必要な場合は、ユーザーがGUIから手動で登録する運用とする
（2026-06-25実施: `ntp.nict.jp`/`ntp.jst.mfeed.ad.jp`/`quory.internal`）。

`time_sync_check.yml`側のcloudkey判定（`timedatectl timesync-status`の数値
Offset取得）はNTPサーバー一覧の管理方法に関わらず動作する。

---

## 4. ライフサイクル（time_sync_check.yml）

```text
Phase 1  quory自身のchronyc trackingを確認。未収集/未同期ならここで中断し、
         他ホストへは一切接続しない（基準が信頼できないため）。
Phase 2  pve1/pve2/ansy/monnie/authyのchronyc trackingを確認
         （quoryが正常な場合のみ）。
Phase 3  sophos-fwとquoryのdate直接比較
         （SSH/メニュー往復をbefore/afterブラケットし誤差を明記）。
Phase 4  cloudkeyのtimedatectl timesync-status数値Offset確認。
Phase 5  結果集約・閾値判定・Slack通知。
```

shell / Ansible の責務分離: 各ホストでの時刻・offset情報の取得は
command/expectで行い、差分計算・閾値判定・fail制御はAnsible tasks側に置く
（core.md §7）。

---

## 5. 通知方針

`roles/common_slack/tasks/notify.yml`を`include_tasks`で呼ぶ（best-effort）。

| 状況 | チャンネル | status |
|---|---|---|
| 全ホスト閾値内 | 通知なし | — |
| 閾値超えホストあり | #alerts | warning |
| quory自身のNTP同期異常（Phase 1で中断） | #alerts | critical |
| 個別ホストへの接続失敗 | #alerts | error |

---

## 6. 制約・禁止事項

```text
- time_sync_check.yml は read-only。対象ホストの時刻・NTP設定の変更は行わない。
- NTPクライアント設定へのquory参照追加は time_sync_ntp_reference.yml（変更系）
  で別途実施する（core.md §9: 読み取り専用ロールと変更系ロールの分離）。
- 秘密情報（cloudkeyのSSHパスワード、sophos-fwのSSH鍵）を扱うタスクには
  no_log: true を設定する。
- IPリテラルをファイルに書かない（core.md §3）。quory.internal等の名前解決は
  sophos-fw（社内DNS）に依存する前提を許容する。
- NTP設定そのものの自動補正は行わない（異常検知のみ）。
- 時刻ズレの履歴管理・トレンド分析は行わない。
- Sophosのserial0コンソール経由での確認は対象外（別件）。
```

---

## 7. 構成ファイル

| ファイル | 役割 |
|---|---|
| `playbooks/time_sync_check.yml` | 入口（read-only）。 |
| `roles/time_sync_check/tasks/main.yml` | Phase 1〜5のライフサイクル本体。 |
| `roles/time_sync_check/tasks/check_chrony.yml` | chrony共通の収集・判定（quory/pve1/pve2/ansy/monnie/authyで共用）。 |
| `roles/time_sync_check/defaults/main.yml` | 既定パラメータ。 |
| `playbooks/time_sync_ntp_reference.yml` | 入口（変更系、準備作業）。 |
| `roles/time_sync_ntp_reference/tasks/main.yml` | chronyホストへのquory参照追加（conf.d drop-in）。 |
| `inventories/vars/cloudkey.yml`（Vault） | `cloudkey_ssh_user`/`cloudkey_ssh_password`。 |

---

## 8. スコープ

### 初回実装（実装済み）

quory自身の同期健全性ゲート、各ホストの自己報告offset取得・閾値判定、
sophos-fwの直接比較フォールバック、実行元ホストの動的除外、Slack通知、
chronyホストへのquory参照追加準備playbook。

### 除外（対象外）

- NTP設定そのものの自動補正（異常検知のみ、修正はしない）。
- 時刻ズレの履歴管理・トレンド分析。
- Sophosのserial0コンソール経由での確認（別件）。
- cloudkeyへのquory参照追加（GUI管理のため対象外。§3参照）。
