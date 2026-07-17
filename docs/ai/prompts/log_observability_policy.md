# Log / Observability Policy v2.0

- 対象システム: monnie を中心とする集中ログ基盤（UniFi/pve/Sophos の syslog → Loki → Grafana）と、その将来拡張（エラーフック/アラート）。
- 起案: 2026-07-16（claude 設計・Yoshinobu 承認）。Phase 1 実機 PASS。
- 監査証跡: `docs/ai/reviews/promtail_to_alloy/`（現状調査・要件・実装・レビュー・テスト）。

## 変更履歴

- v1.0 (2026-07-16): 新規。promtail(EOL)→Grafana Alloy 移行 Phase 1 完了を機に、ログ観測基盤の方針を正本化。
- v2.0 (2026-07-17): Phase 2。Loki 書き込みを monnie ローカルに限定したまま、pve/Sophos の rsyslog ファネル合流と `level` 標準化を正本化。

## 1. 位置づけ

本書は monnie を中心とするログ収集・観測基盤の正本。`autonomous_recovery_policy.md`（サービス障害の検知→復旧ラダー）とは目的が異なる。本書は「ログの収集・保全・検索」と「（将来の）ログベースのエラーアラート」を扱う。core.md §10 に従い、本システムを扱う AI は core.md に加えて本書を必ず参照する。

## 2. アーキテクチャ（2平面）

- **収集平面**: 全ソース → Loki。ラベルで区別。DRY のため収集経路は1本に統一する（目的別に別パイプラインを建てない）。
- **監視/フック平面（将来 Phase 3）**: Loki/Grafana のルールでエラーを拾い Slack へ。別パイプラインではなく、ラベル＋アラートルールとして収集平面の上に薄く載せる。

エージェントは **Grafana Alloy に統一**（promtail は EOL）。

### 2.1 ソースクラス（能力別）

- **アプライアンス（syslog しか出せない）**: UniFi(AP/switch)、Sophos、他ネット機器 → syslog(UDP514) → monnie の集約点。
- **monnie**: ローカル Alloy が journald と rsyslog 出力ファイルを読み、localhost の Loki へ push する。
- **リモート Linux ホスト**: pve1/pve2 → journald → ローカル rsyslog → UDP514 → monnie の集約点。アプライアンスと同じ受信ファネルへ合流する。

**Loki への書き込みは monnie ローカルの Alloy だけが行う。** リモートホストへ Alloy/Loki credential や Grafana repository を広げず、未認証 Loki port をネットワークへ公開しない。

### 2.2 syslog 集約の方式（D1 決定 2026-07-16）

**rsyslog を syslog 集約役（UDP514 受信・source-IP allowlist・振り分け）に残し、Alloy が生成ファイルを tail する。** 理由: rsyslog は多ソースの受信・allowlist・RFC3164/5424 混在を堅牢にこなす。Alloy 直受信（`loki.source.syslog`）で rsyslog を廃止する案は採らない（受信層の作り直しリスクが高い）。

## 3. 現状構成（Phase 2 設計）

```
pve1/pve2: journald → rsyslog → UDP514 ────────────────┐
Sophos: GUI 管理の syslog 送信 → UDP514 ──────────────┼→ monnie rsyslog(imudp)
UniFi機器/コントローラ → UDP514 ──────────────────────┘
  → source-IP allowlist で振り分け
     ├ CloudKey源   → /var/log/unifi.log
     ├ switch/AP源  → /var/log/unifi-devices.log
     ├ pve1/pve2    → /var/log/pve-nodes.log
     └ Sophos       → /var/log/sophos-fw.log
  → Alloy(loki.source.file ×4) + Alloy(loki.source.journal)
  → loki.write localhost:3100/loki/api/v1/push → Loki → Grafana
```

- CloudKey の送信先設定: `ace.setting` の key=`rsyslogd`（サイト単位、enabled、宛先 monnie:514/UDP）。UniFi GUI 管理（Ansible 直接編集はしない）。
- Sophos の送信先設定は SFOS GUI 管理（monnie:514/UDP）。repo は受信準備までを管理する。
- pve の rsyslog package、journald drop-in、転送設定は **手動管理**。参照設定と適用・巻き戻し手順の正本は `docs/ai/reviews/promtail_to_alloy/2026-07-17_009_implement.md`。Ansible の管理対象にはしない。
- **収集5系統のラベル契約**:
  - `unifi`: `/var/log/unifi.log` → `job=unifi`, `host=uckg2`
  - `network-devices`: `/var/log/unifi-devices.log` → `job=network-devices`、log 行の2番目トークンを `host` に抽出
  - `pve-nodes`: `/var/log/pve-nodes.log` → `job=pve-nodes`、正規化済み行の2番目トークンを `host` に抽出
  - `sophos-fw`: `/var/log/sophos-fw.log` → `job=sophos-fw`, `host=sophos-fw`
  - `system`(journal): `job=system`, `host=monnie`、`__journal__systemd_unit` → `unit` relabel
- **severity 契約**: `level` は `error|warning|info|debug` の4値。journal は priority 0--3/4/5--6/7 を順に対応させる。pve/Sophos は monnie rsyslog の受信テンプレートで行頭へ確定値を書き、Alloy が抽出する。既存 UniFi 2系統は明示 severity を安全に認識できる行だけ best-effort で付与し、不明行は誤分類せず `level` 無しとする。
- Loki push: `http://localhost:3100/loki/api/v1/push`（認証なし）。

## 対応するPlaybook

- `playbooks/alloy_setup.yml`（role: `alloy`）: monnie(`monitoring_servers`) の rsyslog 受信振り分け、logrotate、Alloy source/config を管理する。tester-gate: `check-mode-native`。**APPLY は本番ログ経路変更のため人間ゲート（Yoshinobu の明示判断）必須**。

## 4. Alloy 運用方針

- **導入**: apt（既存 Grafana Labs リポ `apt.grafana.com stable main`）。手動運用でなく role 管理（config は git 正本、ホスト直編集禁止）。role の apt は `state: present`（版上げしない）。
- **版上げ**: 月次 `ubuntu_vm_full_upgrade`（apt）が担う。`alloy_setup.yml` は版上げ用ではなく、冪等な cutover/再プロビジョン用（再実行しても版は上がらない）。**Alloy はメジャー更新で River config 構文が変わり得る**ため、monnie の重要パターン（`ubuntu_vm_full_upgrade_important_per_node.monnie`）に `alloy.*` を登録し、月次更新時に REVIEW_REQUIRED（人間レビュー）へ上げる。
- **config**: `/etc/alloy/config.alloy`（`root:alloy 0640`）。収集ソースは role defaults の `alloy_file_sources` / `alloy_journal_sources` 変数。storage: `/var/lib/alloy/data`（実 unit を正本とする）。HTTP listen: loopback `localhost:12345`。
- **rsyslog**: 既存 `/etc/rsyslog.d/10-unifi.conf` は変更しない。Phase 2 source は別 config で名前を実行時解決した source-IP allowlist、専用2ファイル、4値 severity 行頭テンプレートを管理する。新規ファイルは送信開始前に存在しなくても正常とする。配備済み config は解決済みIPを保持し、DNSを自動再解決しない。DHCP/DNS変更後は `alloy_setup.yml` を再実行して allowlist を更新する。
- **cutover 安全則**: install は auto-start 抑止(`policy_rc_d: 101`) → 実 unit/user/storage/CLI contract と `alloy validate` を assert → 合格時のみ promtail stop+disable → alloy start。二重 tail を残さない。start 失敗時は rescue で promtail を復元。promtail の package/config/positions は削除せず rollback 用に維持する。
- **positions**: Alloy 自身の storage で管理（promtail positions は移植しない）。file source は `tail_from_end=true`。cutover 境界の小さな gap/overlap は許容。
- **journald 読取**: alloy user は `adm` + `systemd-journal` 所属が必要。alloy active だけでなく、Loki に journal stream の実データが出ることを検証する（active だけを成功条件にしない）。
- **本番変更前の mute**: monnie は自律復旧対象（recovery_probe が pull 監視）。cutover 等の本番変更前は `homelab-mute set monnie <分>` で mute する（promtail 自体は復旧対象外だが monnie ノードとして念のため）。

## 5. Phase ロードマップ

- **Phase 1（完了 2026-07-16）**: monnie の promtail → Alloy 1:1 移植。rsyslog/Loki/Grafana 不変。
- **Phase 2（実装 2026-07-17、実機検証待ち）**: pve1/pve2 と Sophos を monnie rsyslog 集約へ追加し、全ソースの **severity(`level`) ラベルを4値へ標準化**。動的 host 抽出と静的 host の同時指定禁止も role で assert。
- **Phase 3**: エラーフック（Grafana 管理アラート、必要なら Loki ruler + Alertmanager）→ Slack。既存 recovery/Slack 経路と統合し二重化しない（例: `pve replication error` ログ → Slack → recovery 調査の入口）。

## 6. 制約・禁止事項

- **syslog 転送は平文 UDP 514**（全ソース: UniFi/CloudKey/pve/Sophos）。暗号化・認証なし。
  同一 LAN 上での盗聴・送信元偽装が理論上可能で、**rsyslog の source-IP allowlist は
  ルーティング振り分けであって認証ではない**。経路は homelab 内部 LAN に閉じている
  （2026-07-17 に Yoshinobu へ提示済み。将来オプション: pve→monnie は両端 rsyslog のため
  homelab CA + TLS(6514/TCP) へ上げられる。アプライアンス側は TLS 非対応のため平文が残る）。
- 収集は Loki 一本に統一。目的別の別収集パイプラインを建てない。
- rsyslog を syslog 集約役として維持する（Alloy 直受信で置換しない）。
- Loki/UFW を Phase 2 では変更しない。Loki 3100 をリモートへ公開しない。
- Alloy config はホスト直編集禁止（role/git を正本とする）。
- 本番 cutover/変更を伴う APPLY は人間ゲート（Yoshinobu）。tester は既定で APPLY しない。
- 秘密・IP をリポジトリに書かない。実機検証は tester 工程。

## 7. 不採用の代替案と管理境界

- **pve ローカル Alloy + Loki リモート push**: UFW 3100 開放、認証なし Loki の露出、Grafana repository/package をハイパーバイザへ追加する必要があるため不採用。unit 精度や配送保証が将来必須になった場合だけ再検討する。
- **systemd-journal-remote**: monnie に別 listener/port と取込経路が必要になるため不採用。
- **Alloy の syslog 直受信**: 確立済み rsyslog allowlist/振り分けを再構築するリスクがあり不採用。
- **管理境界**: monnie の rsyslog/Alloy/logrotate は Ansible + Git 管理。pve の rsyslog/journald 転送は Yoshinobu の手動管理で、設定正本は本 policy と Phase 2 implement 文書。Sophos/UniFi の送信設定は各 GUI 管理。

## 8. 実機検証状況

- **2026-07-16 Phase 1**: monnie で APPLY PASS（alloy `1.17.1-1`、`ok=33 changed=7 failed=0`、rescue なし）。3系統の Loki 実データ（cutover 後 timestamp）・journald 実読・service 排他（promtail inactive/disabled・二重 tail 無し）・rsyslog 非回帰（UDP514 継続・2ファイル増加）を確認。監査: `docs/ai/reviews/promtail_to_alloy/2026-07-16_001..006`。
- **既知の非ブロッキング**: 起動時に `remotecfg "noop client"` の error 1行（remote config 未使用の local deploy では正常。以降 ready・全 component 評価・3-stream push・positions 生成が成功）。将来の継続監視で反復しないか確認する価値あり。
