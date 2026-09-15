# Incident: 開発機のSemaphoreが本番と同じscheduleで自動実行を始め、本番Slackへ偽のERRORを出した

日付: 2026-09-16
状態: 解決済み(発火は停止。**恒久対処は `semaphore_reconcile_daily_sync` Phase 2 の P0-15 で実装する**)
対象: ansyのSemaphore(project 3)、`roles/semaphore_templates`(schedule reconcile)
種別: 動作不具合
原因分類: #運用考慮ミス #テスト不足

## 症状

2026-09-16 00:40〜05:50 JST、Slackの `#semaphore` と `#alerts` に、**本番と同じ名前のジョブのERRORが7本**並んだ。

| ansyのtask | 時刻(JST) | 結果 |
|---|---|---|
| #21 Deployment drift check | 00:40 | success。ただし**全6ホストが「到達できず」**で、`semaphore_probe_error` を含むDRIFT 1件を通知 |
| #22 Ubuntu nightly | 03:30 | error |
| #23〜#26 healthcheck 4本 | 05:30〜05:45 | error |
| #27 Time sync check | 05:50 | error(「quory の chronyc tracking 結果を収集できなかった」) |

**本番(quory)側の同名ジョブは同じ時間帯にすべて success している**(#1116〜#1122)。Slackの通知は本文にインスタンスを持たないため、**execution番号(本番は#1116台、ansyは#21台)だけが両者を区別する手がかりだった。**

**本番ホストへは1台も到達していない。** 7本すべてSSH接続の時点で落ちている。

```
ann@authy.internal: Permission denied (publickey).
no such identity: /home/yoshi/.ssh/id_ann: No such file or directory
```

## 原因

**ansyのSemaphoreにも動くschedulerがあり、activeなscheduleは実際に発火する。** この性質が設計上どこにも織り込まれていなかった。

事実の連なりは3つである。

1. **2026-09-15 15:06〜15:11 JST、Phase 1の受入テストがansyのSemaphoreへschedule 24本を書いた**(created/updated。project eventログで確認)。テストは書き込み経路の実機検証を目的としており、`-e semaphore_schedules_canonical_api_base_url=https://ansy.internal:3000/api` を付けている(`docs/ai/reviews/semaphore_reconcile_daily_sync/2026-09-15_005_test_result.md:94-97`)。
2. **この上書きは、非canonical接続先での `active: true` 作成を拒否するゲート(R2)を無効にする。** 拒否メッセージ自身が検証目的の上書きとして案内している経路であり、**ゲートは壊れていない。** 結果、カタログの `active: true` がそのまま書かれた。
3. **最初の発火は書き込みの直後の cron**(2026-09-15T15:40Z = 00:40 JST)である。それ以前、8/24のテスト以降は1本も発火していない。**書き込みがschedulerをarmしたことになるが、その機構(PUT/POSTがschedulerへどう反映されるか)は未確認である。**

**見落としの本体は「到達できないこと」と「静かであること」を同じものとして扱っていた点にある。** `docs/ai/policies/execution_boundary_policy.md` EXEC-052 はansyのSemaphoreを「SSH鍵を持たずどのホストへも到達できずcloneもできない」から検証環境として直接使えるとしている。**この無害さは到達についてのもので、自分で発火しないこと・本番の通知経路へ出ないことは、そこから導けない。**

## 修正内容

**(1) 発火の停止(2026-09-16 06:2x JST、Yoshinobuが実行)。** ansyのSemaphore APIで、schedule 24本すべてを `active: false` にした。**Coordinatorは実行できない** — auto modeの分類器がSemaphore APIへの書き込みを `Modify Shared Resources` として拒否するため、スクリプトを用意してYoshinobuが打った。

**(2) 恒久対処は未実装。** `semaphore_reconcile_daily_sync` Phase 2 の **P0-15 / AC19** として要求化した。

- **接続先がcanonicalでないとき、新規作成・既存更新のいずれでも `active` は `false` として書く。**
- **`-e` によるcanonical URLの上書きは、この強制を解除しない。** 上書きが変えるのは「どこへ書いてよいか」であって「発火してよいか」ではない。**書き込み経路の実機検証は `active: false` のままで成立する。**
- EXEC-052の根拠(鍵が無い)は変えないが、**そこから静かさを導けないことを `docs/ai/context/system/semaphore.md` へ明記する。**

## 確認方法

- **停止の確認**: API で `schedule 24本 / active 0本`。
- **発火が止まったことの実測**: 直後の06:30 JSTは `SAFE:Recovery monitoring check`(cron `30 6 * * *`)の発火時刻だったが、06:32時点でansyの最新taskは #27 のままで #28 は作られていない。**前夜は同じ経路で7本が連続発火していたため、これは静穏ではなく停止の結果である。**
- **本番への影響が無いことの確認**: ansyの7本すべてがSSH接続前に失敗(上記)。quory側は同時間帯の7ジョブすべて success。

## 残っている弱点

- **Slackの通知は、どのSemaphoreインスタンスが出したのかを本文に持たない。** 今回はexecution番号の桁で見分けた。**本番と開発が同じチャンネルへ出せる状態は続いている。**
- **ansyのSemaphoreが「静かである」ことを継続的に確かめる手段は無い。** 今回の停止は状態であって機構ではなく、次にテストが書けば同じ状態へ戻りうる(P0-15が入るまで)。
