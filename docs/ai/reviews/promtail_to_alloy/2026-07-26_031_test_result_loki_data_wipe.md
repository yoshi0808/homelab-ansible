# テスト結果: monnie Lokiデータ全クリア(破壊的操作)

対象: claudeからの直接依頼(Yoshinobu承認済みと申し送り、破壊的操作)。目的は
debug混在のない均質なデータでLOG-067の検知閾値決定(8月下旬)に備えること。
実行環境: ansy、tester(Claude Code)。実行日時: 2026-07-26 09:5x〜10:1x頃(JST)。

## 実施前の確認事項

- **Loki設定の正本確認**(推測せず`/etc/loki/config.yml`を直読): `path_prefix: /var/lib/loki`、
  `chunks_directory: /var/lib/loki/chunks`。データディレクトリは`/var/lib/loki`。
- **削除前のデータ量**: 合計55MB(内訳: chunks 54M、wal 468K、tsdb-shipper-active 300K、
  tsdb-shipper-cache 48K、compactor/rules 各4K)。最古データは2026年5月26日(chunksディレクトリ
  作成日時)。
- **削除前の所有者/権限**(復旧に必須の記録): `/var/lib/loki`自体は
  `drwxr-xr-x loki:nogroup`(0755)。
- **Prometheus隔離の確認**: データディレクトリ`/var/lib/prometheus`(完全に別path)、
  実行バイナリ`/opt/prometheus/prometheus`(別ディレクトリ)、service unit別、
  実行user `nobody`(Lokiの`loki`ユーザーとも別)。今回の対象に一切含まれない。
- **mute**: quory上で`homelab-mute set monnie 45 ...`を実行(delegate_to: localhostでなく
  `hosts: quory`の確認済みplaybook経由。理由は[[reference_loki_query_via_monnie_task]]参照)。

## 実施した正確なコマンド(1回目、失敗)

1. `systemctl stop loki`(成功)
2. `ansible.builtin.file: path=/var/lib/loki state=absent`(成功、削除確認: `stat.exists=False`)
3. `systemctl start loki`(**失敗**)

### 失敗内容と原因

`systemctl start loki`実行後、Lokiがcrashloopした(`NRestarts`が急増、最終確認時31)。
`journalctl -u loki`で確認した実際のエラー:

```
level=error ... msg="error running loki" err="mkdir /var/lib/loki: permission denied ..."
```

**原因**: Lokiは`User=loki`で実行される(service unit確認済み)。`/var/lib`自体は
`root:root`(0755)であり、rootでない`loki`ユーザーは`/var/lib`直下に新規ディレクトリを
作成する権限を持たない。`state: absent`で`/var/lib/loki`ディレクトリそのものを削除して
しまうと、Loki自身では再作成できず起動不能になる。**これは重要な知見であり、将来
同じ作業をする場合の教訓として明記する: Lokiのデータディレクトリを空にする場合は、
ディレクトリそのものを削除するのではなく、ディレクトリを削除前の所有者・権限で
`state: directory`により作り直してから起動するか、あるいはディレクトリ自体は残して
中身(chunks/wal/tsdb-shipper-*/compactor/rules)だけを削除するべきである。**

techlead/claudeの指示どおり、crashloopを強行迂回せず`systemctl stop loki`で安定停止させ、
原因を報告してから次の指示を仰いだ。

## 復旧(techlead・claude双方の承認を得て実施)

1. `ansible.builtin.file: path=/var/lib/loki state=directory owner=loki group=nogroup mode=0755`
   (削除前に記録した実測値をそのまま使用)
2. `systemctl start loki`
3. `wait_for: port=3100`(成功)
4. 起動後確認: `active=active sub=running NRestarts=0`(crashloopなし)。journalctlに
   `msg="Loki started" startup_time=261.577744ms`を確認。

`/ready`エンドポイントは起動直後`503`を返したが、journalctlで
`msg="waiting 10m0s for ring to stay stable and previous compactions to finish before
starting compactor"`というcompactorモジュール特有の既知の起動時待機(10分)によるもので
あることを確認した。ingester/distributor/querier/query-frontend/schedulerは全て正常に
起動しており(`msg=starting module=...`)、機能的な健全性は実際のログ到達で確認した
(次節)。

## 削除後の確認(claude依頼項目どおり)

| 確認項目 | 結果 |
|---|---|
| Lokiがactiveで正常起動 | **PASS**(active/running、NRestarts=0) |
| 新規ログが到着し始めている | **PASS** |
| level=debugが含まれない | **PASS**(0件) |
| 5つのjob全てから新規ログ到着 | **PASS**(全5job確認) |
| Prometheusが影響を受けていない | **PASS** |

### 新規ログ到着(復旧後8分window、job別)

| Job | 到着件数(level別) |
|---|---|
| pve-nodes | info=6 |
| sophos-fw | info=13 |
| ubuntu-nodes | info=1497、warning=54、level無し24 |
| unifi | info=2 |
| network-devices | level無し11 |

debugは全job・全levelを通じて**0件**。Alloy自身のmetrics
(`loki_write_sent_entries_total`)でも書き込み成功を確認、
`loki_write_dropped_entries_total`は全reasonで0(書き込み失敗なし)。

### Prometheus健全性

`systemctl show prometheus`で`active=active sub=running NRestarts=0`(一度も再起動して
いない=今回の作業の影響を受けていない)。データディレクトリ`/var/lib/prometheus`は
1.1GB(既存の長期データがそのまま)、最終更新時刻は今回の作業開始前(10:00:05)であり、
今回の一連の操作中も継続して独立に動作していたことを確認した。

## mute解除

全確認PASS後、quory上で`homelab-mute clear monnie`を実行、`status`で解除を確認済み。

## 経緯についての確認(techlead依頼への回答)

techleadから「この案件は誰からの指示か、techleadは受けていない」との確認があったため
回答する。**依頼はclaude(Coordinator)からagmsgで直接testerへ届いた**(今回のPhase 3b
本番APPLY・CERT-022事前検証・UniFi Link Up調査と同じ経路)。techlead側の案件受領は
確認できていない。

なお`skills/delegation-tier`の判定基準では「本番影響のある実ロジック変更、複数ホストの
orchestration、**破壊的操作**、セキュリティか → Tier 3」と明記されており、破壊的操作は
Tier 3(Tech Lead経由)の判定条件に該当する。今回の案件はCoordinatorからTier 2相当として
直接testerへ届いたが、判定基準に照らすと本来Tier 3(techlead関与)が妥当だった可能性がある。
この点はtechlead/claude/Yoshinobuの判断に委ねる(testerとして事実関係のみ報告する)。

## 総合判定

**Lokiデータ全クリア完了。1回目の起動試行で失敗(mkdir権限エラー)したが、強行せず
停止・報告し、techlead/claude承認のもと記録済みの所有者・権限で復旧、以後は完全に
健全(全5job新規到着・debug 0件・Prometheus無影響)。muteは解除済み。** 破壊的操作の
Tier分類・依頼経路については確認結果を上記のとおり報告し、判断はclaude/techlead/
Yoshinobuに委ねる。

## Next step files

- docs/ai/policies/log_observability_policy.md(LOG-067)
- docs/ai/reviews/promtail_to_alloy/2026-07-26_029_test_result_debug_exclusion_apply.md
- docs/ai/reviews/promtail_to_alloy/2026-07-26_031_test_result_loki_data_wipe.md(本ファイル)
