# Infra Syslog（All Nodes）ダッシュボード取り込みメモ

## 対象ファイル

`docs/ai/reviews/promtail_to_alloy/2026-07-17_grafana_infra_syslog_all_dashboard.json`

既存のPVE / Sophos版を変更せず、Ubuntu / PVE / Sophosの3 jobを横断する新規ダッシュボードとして作成した。

## Grafana UIでのImport

1. Grafanaへログインする。
2. **Dashboards** → **New** → **Import**を開く。
3. 対象JSONをuploadする（またはJSON内容を貼り付ける）。
4. datasource選択を求められた場合は、既存ダッシュボードと同じLoki datasourceを選択する。
   - datasource UID: `ffn86ietu7jeoc`
5. titleとUIDが次の値であることを確認してImportする。
   - title: `Infra Syslog (All Nodes)`
   - UID / metadata.name: `infra-syslog-all-nodes-v1`

## Import後の確認

- `Host`変数に`monnie / ansy / quory / authy / pve1 / pve2 / sophos-fw`が現れること。
- `Severity`変数で`error / warning / info / debug`を選択できること（実ログに存在する値が表示対象）。
- `Keyword`で任意文字列を絞り込めること。
- **Event Timeline**がhost別barsで表示されること。
- **Infra Events (Ubuntu / PVE / Sophos)**が3 jobのログを1枚で表示すること。

利用するjob selector:

```logql
{job=~"pve-nodes|sophos-fw|ubuntu-nodes"}
```

Phase 3のerror閾値alertを作る際は、Timelineの次の形を下敷きとし、`level="error"`と評価window / thresholdへ置き換える。

```logql
sum by(host) (
  count_over_time(
    {job=~"pve-nodes|sophos-fw|ubuntu-nodes", host=~"$host", level=~"$level"}
      |= "$search" [$__interval]
  )
)
```
