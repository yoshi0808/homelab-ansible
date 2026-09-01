# Incident: incident-capture collector が exit 2 で2回失敗した(status.mdでは解決済みとされていた失敗モード)

日付: 2026-09-01
状態: 調査中
対象: `homelab-incident-capture.service`(quory、`roles/incident_capture`、`incident-capture-collector.py`)
種別: 動作不具合
原因分類: (未判明)

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

**未判明。**

現時点の手段では確定できない。

- **unitのjournalは行数上限で直近しか返らない** — `journal-unit homelab-incident-capture.service 24h` は5分間隔の正常ログで埋まり、05:55は返却窓の外だった。終了コードはLoki側に残っていたため取得できた
- これ以上の切り分けには**収集スクリプト自身のエラー出力**が要る。どの収集ステップが失敗したかは、現在Coordinatorが使える語彙では取得できない

## 修正内容

(未着手)

## 確認方法

(未定)
