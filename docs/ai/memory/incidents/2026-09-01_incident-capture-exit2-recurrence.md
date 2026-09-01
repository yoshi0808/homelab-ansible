# Incident: incident-capture collector が exit 2 で2回失敗した(status.mdでは解決済みとされていた失敗モード)

日付: 2026-09-01
状態: 調査中
対象: `homelab-incident-capture.service`(quory、`roles/incident_capture`、`incident-capture-collector.py`)
種別: 動作不具合
原因分類: #運用考慮ミス

## 症状

2026-09-01、`quory` の `homelab-incident-capture.service` が2回失敗した。

| 時刻(JST) | 終了コード | 所要 |
|---|---|---|
| 05:55:11 | `status=2/INVALIDARGUMENT` | 約8秒(05:55:03 起動) |
| 06:10:12 | 同上 | — |

- `EXIT_COLLECTION_ERRORS = 2`(`incident-capture-collector.py:109`)。**クラッシュではなく「収集ステップの一部が失敗した」という設計された信号**である。内部エラーは `EXIT_INTERNAL_ERROR = 3` で別扱い
- **継続していない。** 5分間隔のtimerだが失敗は2回のみで、間隔も連続tickではない(15分空き)。同日17:30の実行は `status=0/SUCCESS`
- **新しいバンドルは作られていない。** `bundle-list` の最新は `semaphore-802`(2026-08-22)
- 直前の05:50に Semaphore task 915(`SAFE: Time sync check`)が起動している。関連は**未確認**

## この記録を起こした理由

**`docs/ai/status.md` は、同じ失敗モード(`status=2` で5分ごとに失敗し続ける)を「配備を境に緑になった」と記録している**(一次調査の先読み経路の案件、2026-08-19の配備)。同じ終了コードが再発したのか、別要因で同じコードが出たのかは判明していない。

## 発見の経緯(この経緯自体が知見)

**定期的に見る仕組みが無いため、偶然見つかった。**

Yoshinobu提起(同日)「monnieのLokiにwarning/errorが溜まっているが誰も見ていない」を受けて `loki-errors` 語彙を追加し(`docs/ai/reviews/loki_investigate_vocabulary/`)、**配備後の受入検証で初回に実行した24時間分の結果に含まれていた。**

- syslog系統の検知は `docs/ai/policies/log_observability_policy.md` §4 が「未実装。蓄積内容の事後参照に留まる」と明示しており、**設計どおり誰も気づかない状態だった**
- syslog週次ダイジェスト(`docs/ai/reviews/syslog_weekly_digest/`)が保留中であり、**本件はその必要性の実例である**

## 原因

**判明した**(quory側Operatorへの調査依頼 `req-20260901T174604+0900-66c1523d12020082` の回答、2026-09-01)。

**Semaphoreジョブの失敗とは無関係だった。** 当日Semaphoreジョブは1件も失敗していない(Yoshinobu指摘)。この指摘が切り分けの決め手になった。

`_runs/` に両周期のrun reportが残っており、次が読み取られた。

| 周期 | run report | global `collection_errors` | 個別(bundle)の `collection_errors` |
|---|---|---|---|
| 05:55:10 | `run-1788209710.json` | **空** | spool record(`Time sync check (per-host NTP self-report)`)に相関するSemaphore jobが無く、**host `quory` 向けの named investigate operation が利用できない** |
| 06:10:11 | `run-1788210611.json` | **空** | spool record(`Send recovery probe notification`)に相関するSemaphore jobが無く、**host `localhost` 向けの named investigate operation が利用できない** |

**collectorはbundle個別の `collection_errors` でも exit 2 にする。** global が空であることから、Semaphoreへの問い合わせ(`semaphore_query_ok`)は成功していたと判断される — ただし**これは実装からの推定で、直接の記録値ではない**(下記「未確認」)。

したがって失敗の連鎖はこうである。

1. spool にレコードが入る(Semaphoreジョブの失敗を伴わない経路)
2. collector が相関するSemaphore jobを探すが、見つからない
3. 対象host(`quory` / `localhost`)向けの named investigate operation を試みるが、**利用できない**
4. これが個別 `collection_errors` に記録され、exit 2 になる

**断続的だった理由もこれで説明が付く** — 常時発生するのではなく、**相関するジョブを持たないspool recordが到着したときだけ**起きる。当日はその条件が2回成立した。

**2026-08-19の配備で解消したとされる事象とは別物である。** あちらは先読みディレクトリのtraverse不足で5分ごとに継続的に失敗していた。今回は断続的で、原因も別。**終了コードが同じ `2` であるために同一に見えていた。**

## この事象から見えた設計上の論点(未決)

- **`_runs/` の run report は `semaphore_query_ok` を保存していない。** 終了コードを決める3つの要素のうち1つが記録に残らないため、事後に直接確認できない
- **`quory` / `localhost` 向けの named investigate operation が無い。** collectorがこれらのhostを調査しようとする経路が存在するのに、対応する手段が用意されていない
- **exit 2 が「収集の一部が失敗した」と「捕捉すべき異常があった」を区別しない。** 今回のように「捕捉対象は無いが収集に失敗した」場合も同じコードになる

## 修正内容

**未着手。** 原因は判明したが、何を直すべきか(あるいは直すべきか)は未決である。上記「設計上の論点」の3点はいずれも独立した判断を要する。

**この失敗は再発する。** 相関するSemaphore jobを持たないspool recordが到着するたびに同じ条件が成立するため、一度きりの事象として扱わない。

## 確認方法

(未定)

## 参照

- 調査依頼: OPREQ `req-20260901T174604+0900-66c1523d12020082` / 回答 OPRES `req-20260901T175504+0900-4842eb3295282a21`
- 発見の経路: `docs/ai/reviews/loki_investigate_vocabulary/`(`loki-errors` の受入検証で偶然検出した)

## 未確認

- 05:50のSemaphore task 915(`SAFE: Time sync check`)との因果関係は未確認。時刻が近いだけで、確かめていない
- `semaphore_query_ok` の値は実装からの推定であり、直接確認できていない(run reportが保存しないため)
- **spool record がSemaphore jobへ相関しなかった理由**は、今回の依頼範囲では調べていない
