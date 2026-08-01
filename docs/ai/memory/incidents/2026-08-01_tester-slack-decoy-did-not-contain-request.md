# Incident: 検証用decoyがSlackへの実リクエストを止められなかった

日付: 2026-08-01(発生・起票とも同日)
起票: Coordinator。Tester(subagent)が `common_slack_capture_scope` 案件のAC3検証中に**自己申告**し、Auditorが「同種の前例がIncident化されているのに本件は未起票」と指摘したことを受けて起票した
状態: **解決済み**(実害なし)
対象: Tester役のdecoy設計、`community.general.slack` の挙動
種別: ヒヤリハット
原因分類: #テスト不足 #設計上の欠陥

## 症状

`common_slack_capture_scope` 案件のAC3(通知の送信経路がcaptureの有無に影響されないこと)を検証する際、Testerが**webhook URLをループバックの閉じたポートへ向けたdecoyの `vars/slack.yml`** を用意した。意図は「接続拒否で安全に失敗させ、送信経路が走ったことだけを観測する」ことだった。

**decoyは機能せず、実際の `hooks.slack.com` へHTTPSリクエストが1回送信された。**

**メッセージは配送されていない**(組み立てられたパスが不正だったため)。Tester自身がモジュールのソースを読んで気づき、その手法を中止し、ネットワークを使わないJinja評価による確認へ切り替えた。**迂回も再試行もしていない。**

## 原因

**`community.general.slack` は token に与えられたURLの形を無視し、`domain` を明示しない限り常に `hooks.slack.com` に対してリクエストを組み立てる。**

したがって「webhook URLを潰す」というdecoyの前提 —送信先を差し替えれば外へ出ない— が、このモジュールでは成立しない。決め手は `token` ではなく `domain` である。

**これは既知の欠陥クラスの再来である。** `docs/ai/reviews/incident_auto_capture_step2/progress.md` A-3 が、`ansible.posix.synchronize` について同型の事実を記録している —「`127.0.0.1` 閉ポート」のdecoyは action plugin が `C.LOCALHOST` を特別扱いするため効かず、**黙ってローカル実行に落ちる**。

> **decoyは「対象モジュールが実際にどう宛先を決めるか」を確かめない限り、成立していると仮定してはならない。** 潰したつもりの経路が、モジュールの内部で別の宛先へ組み替えられている場合がある。

## この事象が属するもう1つの系列

**Testerの検証実行が本番Slackへ到達した事象は、これが3回目である。**

| 日付 | 経緯 | 抑止に使おうとしたもの |
|---|---|---|
| 2026-07-26 | (当時の案件記録) | — |
| 2026-07-29 | `skip_notifications=true` の付与忘れ | 実行時に渡す変数 |
| **2026-08-01(本件)** | decoyの宛先差し替えが効かなかった | decoyの `vars/slack.yml` |

前2件の一次記録は `docs/ai/memory/incidents/2026-07-29_tester-slack-notify-misfire.md`。**同Incidentが特定した構造的原因は本件でも変わっていない** — 「通知を抑止する唯一の手段が、実行者が毎回渡す変数であり、**渡し忘れた場合の既定動作が本番へ送ること**」。本件は変数を忘れたのではなく別の手段を選んだ結果だが、**「既定が送信」であるために、抑止手段を1つ誤ると外へ出る**という構造は共通である。

**2026-07-29のIncidentは「`docs/ai/status.md` の Next へ起票した」と記載しているが、その行は存在しなかった**(2026-08-01にCoordinatorが確認)。同日の別Incident(`2026-07-29_global-monitoring-pause-left-on-8-days.md`)でも同じ「起票したと書いたが存在しない」が起きており、**2026-07-29のIncident起票そのものに同型の欠落が2件ある**。本件の起票と同時に、その未起票分をNextへ追加した。

## 修正内容

**本Incidentでは構造的な修正を行っていない。** 通知抑止の既定を反転させる(`--check` 実行時は既定で抑止する等)のは `roles/common_slack` の全利用箇所へ波及する設計変更であり、Incident対応として即断しない — この判断は2026-07-29のIncidentと同じである。

今回行ったのは次の3つ。

1. 事実の記録(本ファイル)。
2. **`docs/ai/status.md` の Next へ起票**(2026-07-29に起票されたはずで存在しなかったもの)。
3. decoyの前提が破れる2例目が揃ったことを、Lesson昇格候補(申し送りA-3)の根拠として Next へ反映。

## 確認方法

- **decoyの妥当性**: 対象モジュールが宛先をどう決めるかをソースで確認してから、decoyが成立していると判断する。`community.general.slack` では `domain` を設定しない限り宛先は `hooks.slack.com` に固定される。
- **再発の検知**: 本番Slackチャンネルに検証由来の投稿が現れないこと。**ただしこれは事後の検知であり、抑止ではない。** 抑止は上記「修正内容」の構造変更が入るまで、実行者の手順に依存したままである。

## 参照

- `docs/ai/memory/incidents/2026-07-29_tester-slack-notify-misfire.md`(同系列の2回目、構造的原因の分析)
- `docs/ai/reviews/incident_auto_capture_step2/progress.md` A-3(decoy定型がモジュールによって成立しない、1例目)
- `docs/ai/reviews/common_slack_capture_scope/2026-08-01_003_test_result.md`(Testerの自己申告の一次記録)
