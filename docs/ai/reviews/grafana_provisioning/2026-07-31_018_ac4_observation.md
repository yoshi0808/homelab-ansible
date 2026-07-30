# AC4 実発火時の通知本文 — 観測記録(2026-07-31)

要求: `docs/ai/reviews/grafana_provisioning/2026-07-30_001_requirement.md` §11 AC4
規範: `docs/ai/policies/log_observability_policy.md` v4.0(LOG-078〜LOG-089)
ルール定義: `roles/grafana_provisioning/files/alerting/unifi-switch-port-errors.yaml`

## 位置づけ

AC4は「実際にpacket error/dropが発生したときにしか確かめられない」ため、案件クローズの必須条件から外して `docs/ai/status.md` のWatchへ回していた項目である。**2026-07-30 22:54(JST)に実発火し、Yoshinobuが通知本文を確認した。** 本ファイルはその観測を一次記録として残し、Watch行を削除できる状態にするためのものである(status.mdの規律3「完了したら行を消す」)。

## 観測(Slack `#grafana`、Grafana v13.1.0)

| 時刻(JST) | 通知 |
|---|---|
| 2026-07-30 22:54 | `[FIRING:1] UniFi Switch TX Drop UniFi (...)` |
| 2026-07-30 23:09 | `[RESOLVED] UniFi Switch TX Drop UniFi (...)` |

本文に含まれていた要素:

- **発火時の実測値**: `Value: A=4.067796610169491, C=1`
- **機器名**: `name = usw-srv`
- **port**: `port_id = usw-srv Port 23` / `port_name = quory` / `port_num = 23`
- その他のラベル: `alertname = UniFi Switch TX Drop`、`grafana_folder = UniFi`、`instance`、`job = unifi-poller`、`site_name`、`source`

## 判定: PASS

1. **テンプレート式が値として描画された。** `{{ $values.A.Value }}` は公式ドキュメント上正しい式だが、無効な場合Grafanaは本文へエラー文字列を描画する(静かに失敗せず、しかし人が読むまで気づかない)という残存リスクを持っていた。**実数値が出たことでこの経路が塞がった。**
2. **機器名・portが本文から特定できる。** 通知だけを見て「どの機器のどのportか」が分かる状態である(R14の要求)。
3. **同一事象で1通のみ。** `[FIRING:1]` が1通、収束時に `[RESOLVED]` が1通。旧4ルール併存時のような重複は発生していない — Step 3で旧ルールを削除した効果が実発火で裏付けられた。

## 併せて分かったこと

**FIRING → RESOLVED が15分で閉じている。** 通知が出しっぱなしにならず収束側も届くことを確認した(閾値・for期間の妥当性そのものは本ACの対象外であり、調整が要る場合の手順は `docs/ai/context/operations/grafana-alerting-tuning.md` が正本)。

## 残存リスク

- 観測できたのは **TX Drop 1ルールのみ**である。同じ通知テンプレートを共有する他ルール(RX/error系)は同一の式・同一のcontact pointを使うため同様に描画される見込みだが、**実発火は未観測**である。この1件をもって全ルールの描画を実証したとは扱わない。
- 発火は自然発生であり、閾値が「意味のある異常」を捉えているかどうかの判断材料にはならない(1回の発火が15分で収束した事実のみ)。
