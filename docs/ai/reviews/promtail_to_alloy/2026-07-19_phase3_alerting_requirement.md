# 要求仕様: Alloy Phase 3 — Loki ログベース Grafana アラート → Slack(不調の予兆監視)

作成日: 2026-07-19
起票: claude(要件定義)
種別: 追加系(Grafana provisioning によるアラートルール + Ansible 配備)

## 目的

集中ログ(Loki)の上に、**システムの不調の予兆(leading indicator)を拾う Grafana managed アラート**を
薄く載せ、既存 Slack へ通知する。事後のダウン検知でなく「ノードが不調に転ぶ前兆」を捉えるのが趣旨。
`log_observability_policy.md` の「監視/フック平面(Phase 3)」= 別パイプラインを建てず、ラベル+
アラートルールとして収集平面の上に載せる、を実装する。

## 根拠(実データ)

- Loki 中身の read-only 棚卸し: `docs/ai/reviews/promtail_to_alloy/2026-07-19_loki_content_survey.md`
- 要点:
  - estate は現状とても静か(24h: PVE warn7/err2、Ubuntu warn99/err0。うち Ubuntu warning 93/99 は
    Livepatch "recent, not refreshing" ノイズ、PVE error は invalid-credential)。→ **生の
    warning/error アラートはノイズまみれ。除外前提。**
  - **致命シグネチャ(OOM/panic/BUG/segfault/callトレース、I/O・RO-fs・no space・ZFS異常)は7日ゼロ**
    → 「出たら即・本物・ノイズなし」= 予兆アラートの理想。
  - **自己汚染**: Loki に流れる Ansible 実行ログや調査コマンド自体が `panic`/`certificate` 等の文字列を
    含む → 全アラート式に `!~ "(?i)ansible.*invoked with"`(等価の source 制約)が**必須**。
  - **corosync/quorum は狭く撃つ**: 全マッチはノイズ。逆境サブセット
    (`lost connection with heuristics worker` / `no active links` / `waiting for quorum device`)のみ
    クリーン(7d 8件・24h 0)。
  - **recovery 二重化**: monnie/authy/sophos-fw は自律復旧が Prometheus/Grafana/Loki/Unpoller を
    再起動する → 同一事象で二重通知になり得る。**PVE は自動復旧が無い**ので PVE 系の価値が高い。
  - ラベル実態: `job`(network-devices/pve-nodes/ubuntu-nodes/unifi、7d に sophos-fw+legacy `system`)
    × `host` × `level`(error/warning/info/debug)+ `filename`/`service_name`/`unit`。
    network-devices/unifi は **level 無しが大半**(level ベースのルールは盲点)。

## 採用スコープ(Yoshinobu 決定 2026-07-19)= 推奨コア5群

| # | アラート | LogQL 骨子(全式に anti-contamination 除外を付ける) | 閾値(初期) | severity |
|---|---|---|---|---|
| 1 | カーネル致命 | `{job=~"pve-nodes\|ubuntu-nodes"} \|~ "(?i)(out of memory\|oom-kill\|kernel panic\|kernel BUG\|BUG:\|general protection\|segfault\|call trace)" !~ "(?i)ansible.*invoked with"` を host 別 count_over_time[5m] | 1件/5m | critical |
| 2 | ストレージ致命 | `... \|~ "(?i)(I/O error\|read-only file system\|No space left\|ZFS.*(DEGRADED\|FAULTED\|UNAVAIL)\|zpool.*(DEGRADED\|FAULTED))" !~ "(?i)ansible.*invoked with"` | 1件/5m(広い I/O error は 2件/10m 検討) | critical |
| 3 | PVE corosync 逆境 | `{job="pve-nodes"} \|~ "(?i)(lost connection with heuristics worker\|no active links\|waiting for quorum device)" !~ "(?i)ansible.*invoked with"` | 1件/5m warn、2件/10m or 継続で critical | warning→critical |
| 4 | サービス起動/継続失敗 | `{job=~"pve-nodes\|ubuntu-nodes"} \|~ "(?i)(Failed to start\|Failed with result)" !~ "(?i)ansible.*invoked with"` | 1件/5m warn、10m 後も失敗で critical | warning→critical |
| 5 | 認証失敗バースト | host/source/user 別 `{job=~"pve-nodes\|ubuntu-nodes"} \|~ "(?i)authentication failure" !~ "(?i)ansible.*invoked with"` の count_over_time | 5件/5m/host warn、10件/10m critical。**単発では鳴らさない** | warning→critical |

- 全ルール **per-host ラベル**で発火(どのノードかが即わかる)。LogQL の正確形は実データで tester が微調整。
- 認証失敗は**収集では消さない**(セキュリティ信号)。benign な既知 rhost/user はアラート式の除外で扱う。

## 実装方式(Yoshinobu 決定)= IaC(Grafana provisioning を Ansible 管理)

### 最重要の設計制約:ルールだけ provision、ポリシー/contact point は触らない

- Grafana file provisioning(`provisioning/alerting/*.yaml`, `apiVersion: 1`)で **alert rule group だけ**を配備する。
- **notification policy tree と contact point は provisioning で定義しない**。理由: 既存の TX Drop アラートと
  Slack contact point は **UI/DB 管理**(調査 2026-07-18_unpoller_source_ip_investigation で確認)。
  policy tree を provision すると**既存ルーティングを丸ごと上書きして壊す**。→ 新ルールは**既存の Slack
  contact point へルーティング**する(既存 default policy or ラベルマッチで届く形。policy tree は不変)。
- **datasource は UID 参照**(名前参照は禁止)。Grafana 13.1 で name ベース fallback が廃止された事故
  ([[project_monnie_monitoring_stack]] の grafana 13.1 incident)を踏まえ、Loki datasource UID を pre-deploy で
  確定して rule に焼く。
- アラートルールは専用 folder に置く。provisioned rule は UI で read-only になる(UI 管理の TX Drop と共存)。
- 配備は既存の grafana/monnie の Ansible 経路(ダッシュボードが file provisioning 済み)に載せる。alerting
  provisioning dir は現状 sample.yaml のみなので新規に足す。

### 確定値(grounding 調査 2026-07-19_grafana_alerting_grounding.md で確定)

- **Grafana 13.1.0・unified alerting 有効**。alerting provisioning dir = `/etc/grafana/provisioning/alerting/`
  (現状 sample.yaml のみ=全コメント)。
- **Loki datasource UID = `ffn86ietu7jeoc`**(rule の datasourceUid / model 内 datasource UID に使う。
  name 参照は禁止)。参考 Prometheus UID=`ffn83gysyghs0c`。両 datasource は DB/UI 管理。
- **Slack contact point = `slack-homelab`**(type slack、integration UID `cfoig7vuapczkf`)。DB/UI 管理。
- **★root notification policy の receiver = `empty`(route/ matcher 無し)**。→ **severity 等のラベル付けでは
  Slack に届かない**。既存 UniFi 4ルール(RX/TX Drop/Error)は **rule ローカルの
  `notification_settings.receiver: slack-homelab`** で送っている。**Phase 3 も同じ rule ローカル方式**。
- 既存 alert rule 4件は folder `UniFi`。Phase 3 は**専用 folder/group + 一意 UID**(既存 4 UID
  `bfoii89j7l88wf`/`dfoiiku15evi8e`/`dfoih9pbfckxsf`/`dfoiihloh6hogd` と衝突させない)。

### provisioning YAML の厳守事項(policy 非上書き)

- top-level key は **`apiVersion: 1` と `groups` のみ**。`policies` / `resetPolicies` / `contactPoints` /
  `deleteContactPoints` / `deleteRules` 等、既存 notification resource を変更/削除する key は**一切書かない**。
- 各 rule に **`notification_settings.receiver: slack-homelab`** を明示(rule ローカルルーティング)。
- reload: ファイル配置だけでは反映されない → **`grafana-server` restart**(新規 admin 認証を作らない・
  既存 monitoring mute + メンテ枠で)か、既存 Basic Auth があれば `POST /api/admin/provisioning/alerting/reload`。

### pre-deploy で tester に再確認させる(焼き込み前・reload 前後)

1. Loki UID `ffn86ietu7jeoc` と contact point `slack-homelab`(UID `cfoig7vuapczkf`)の実在(webhook 値は触らない)。
2. Phase 3 YAML の top-level が `apiVersion`+`groups` のみ・全 rule に `notification_settings.receiver`・
   UID が既存4件と非衝突。
3. 各 LogQL が現状ほぼゼロ基線を返し、`!~ ansible.*invoked with` 除外が効くこと(誤発火しない)。
4. **reload 前後で policy tree の serialized hash・既存4 rule・`slack-homelab` UID が不変**(read-only 比較)。

## 制約

- **収集平面(Alloy/rsyslog/Loki 書き込み)は変更しない**。Phase 3 は監視/フック平面のみ。
- **recovery パイプラインと二重通知しない**: monnie/authy のサービス失敗系は**即 critical でなく warning/継続
  失敗で上げる**設計にし、recovery が復旧すれば無駄鳴りを避ける。将来 recovery 状態との相関(mute)を検討。
- **計画メンテ中の抑止**: corosync/サービス失敗は patch/evacuate 中に鳴る。Grafana mute timing 等での抑止を
  検討(patch playbook の recovery mute とは別レイヤーなので要設計)。初期は「メンテ時間帯は人手で了解」でも可。
- **自己汚染除外を全式に必須**(上記)。
- 秘密情報・IP をリポに書かない(webhook は既存 Slack 管理、rule には焼かない)。時刻 JST。
- ダッシュボード(2026-07-17 統合)や既存 policy を壊さない。

## 初回実装スコープ

- Grafana alerting provisioning ファイル(rule group ×5、専用 folder、Loki datasource UID 参照、
  anti-contamination 除外、per-host、severity/threshold は上表)+ Ansible 配備タスク(既存 grafana 経路)。
- 既存 Slack contact point へのルーティング(policy tree 非上書き)。

## 初回除外スコープ

- cert/TLS・PVE/Ubuntu error フォールバック(今回のコア外。後で追加可)。
- network-devices/unifi の level パーサ改善(別タスク)。
- recovery 状態との自動相関 mute の作り込み(将来)。stream-absence(sophos/unifi 無音)アラート
  (recovery pull/push と二重化リスク → 見送り)。
- 実 Slack へのページング作り込み以外の通知経路。

## テスト観点(tester 向け)

- pre-deploy: 上記4点(datasource UID / contact point・policy / provisioning 有効 / 各 LogQL の基線ゼロ+除外)。
- provisioned rule が Grafana にロードされ、Loki datasource で評価されること(UI で read-only 表示)。
- **合成テスト**: 各シグネチャに一致する benign なテストログを1行注入(または Grafana のルールテスト)して
  該当ルールが Fire → **既存 Slack contact point へ届く**ことを確認 → resolve。実 estate を汚さない範囲で、
  テスト用チャンネル or 一時ラベルを使う。自己汚染除外が効き Ansible ログで誤発火しないことも確認。
- 既存 TX Drop アラートと Slack ルーティングが**非回帰**(policy tree 不変)。
- per-host ラベルが通知に出る。閾値どおり単発 auth では鳴らない。

## shell / Ansible 責務分離

- Ansible: provisioning ファイル配置 + grafana reload(provisioning の再読込。サービス restart 要否を確認)。
- 判定ロジックは LogQL(Grafana 側評価)。shell 判定なし。

## 関連

- 実データ: `docs/ai/reviews/promtail_to_alloy/2026-07-19_loki_content_survey.md`
- 正本: `docs/ai/prompts/log_observability_policy.md`(Phase 3 で v2.2 相当に更新予定)
- 統合ダッシュボード: `docs/ai/reviews/promtail_to_alloy/2026-07-17_grafana_infra_syslog_all_dashboard.json`
- datasource UID 教訓 / 監視スタック: [[project_monnie_monitoring_stack]]
- 認証失敗は消さない方針: [[project_promtail_to_alloy_migration]]
