# Incident: 月次aptの後、monnieのjournalがラベルを失った系列でLokiへ入っていた

日付: 2026-09-26
状態: 解決済み
対象: `roles/alloy`(`alloy_journal_sources`)/ monnie
種別: 動作不具合
原因分類: #運用考慮ミス

## 症状

2026-09-03 08:09、月次の `ubuntu_vm_full_upgrade` がmonnieで `apt-get full-upgrade` を実行した。**その直後(08:05〜08:10の5分窓)から**、monnie自身のjournalが `job=ubuntu-nodes, host=monnie` ではなく `job=loki.source.journal.system` の系列でLokiに入っている。`ubuntu-nodes/monnie` は2026-09-03を最後に0件である。

- 行数: 切替前は1日約7千行。切替後は約6万行になり、その後も毎日増えている(2026-09-16 81,186 → 2026-09-25 124,336)
- repoの設定(`roles/alloy/defaults/main.yml` `alloy_journal_sources`)は `labels: {job: ubuntu-nodes, host: monnie}` を付ける形のままである
- `monnie-investigate` の `loki-window` は `job` を固定の一覧から選ぶ作りのため、**切替後のmonnieのjournalは開発側から本文を読めない**(件数は `loki-count` で見える)
- 現在の版は `alloy 1.19.2-1`(`pkg-list alloy`、2026-09-26)。導入時(2026-07-16)の記録は1.17.1-1

気づいた経緯: Alloy Phase 3に向けて、Lokiに溜まったデータの分布を61日分(2026-07-27〜09-25)の `loki-count` で取っていて見つけた。

確認した手段: `ssh monnie-investigate loki-count`(日単位・時間単位・5分単位)、`loki-window ubuntu-nodes`(切替時刻前後の本文)、`pkg-list alloy`。

未確認: 9/3にどの版からどの版へ上がったか。ラベルが外れる仕組み。行数が増え続ける理由。

## 原因

**Alloy 1.19.0 の回帰。** `loki.source.journal` が `labels` の `job` を無視し、コンポーネントID(`loki.source.journal.<name>`)で上書きする(upstream PR grafana/alloy#6982「Dont override configured job label」、回帰の起点は #6508)。`host` は残る。修正は main へ 2026-08-27 にマージされ、`release/v1.19` へのbackport(#6998)は 1.19.3 に載る予定だったが、**1.19.3 は未リリース**(release PR #6999 は open、2026-09-26時点)。**monnie の 1.19.2 は修正を含まない。** v1.20.0(2026-09-25リリース)は修正を含む(`gh api compare` で確認)。

月次の `apt-get full-upgrade` が、Grafana の apt リポジトリから入っている alloy を 1.19 系へ上げた。9/3以前の版は未確認(1.19.2 のリリースは 2026-08-26)。

**行数が増えたのは同じ原因の二次効果である。** `loki.process` の drop 規則(全unitの debug、観測スタック自身の info/debug)は selector に `job="ubuntu-nodes", host="monnie"` を含む(`roles/alloy/templates/config.alloy.j2`)。job が変わったため一致しなくなり、これまで捨てていた行がすべて Loki へ入っている。切替後の系列に debug が現れていることと整合する。日ごとに増え続ける理由は未確認。

## 修正内容

**alloy を 1.20.0 へ上げた**(2026-09-26、Semaphore `UN-SAFE: Ubuntu vm full upgrade (Manual)` #1249、`node=monnie`)。Yoshinobu の判断で、repo 側の回避(`loki.process` で job を付け直す)ではなく版上げを採った(急ぐものではないため)。同じ適用で grafana 13.2.0 → 13.2.2 ほか計16パッケージが上がった。

1.20.0 の互換性のない変更は OpenTelemetry・Kafka・k8s・Windows の部品に限られ、本設定が使う `loki.process` / `loki.relabel` / `loki.source.file` / `loki.source.journal` / `loki.write` は含まれない(upstream CHANGELOG v1.20.0)。

**2026-09-03 〜 09-26 12:5x の monnie の journal は `job=loki.source.journal.system` のまま Loki に残る。** この期間の分布を見るときは別扱いにする。

## 確認方法

`monnie-investigate` で観測した(2026-09-26)。

- `pkg-list alloy` → `1.20.0-1`(適用前は `1.19.2-1`)
- `loki-count` 5分窓: 12:45 は `loki.source.journal.system` 195 / `ubuntu-nodes/monnie` 0 → 12:50 は両方が混在(465 / 259、切替の窓)→ **12:55 は 0 / 165**
- 他の系列(`ubuntu-nodes` の他ホスト、`pve-nodes`、`sophos-fw`、`network-devices`)は切替の前後で途切れていない。ただし **12:45〜12:50 の窓だけ `network-devices` が3行**(前後は約2,200)で、適用中の再起動の間に UDP syslog を取りこぼしたと見ている(未確認)
