# Incident: `tester_mode_full_removal` AC2検証中、decoyが本番Slackへの到達を止められなかった(4回目)

日付: 2026-08-02(発生・工程内での検出とも同日)
起票: Implementer(`slack_send_optin`案件、2026-08-02)。事象自体は`2026-08-02_006_test_result.md`「残存リスク」1に自己申告済みで、`2026-08-02_007_audit.md`指摘2が「前日の同型Incidentと紐付けられていない」と指摘していたが、当時のクローズ判断は起票を見送っていた(`2026-08-02_007_audit.md`のCoordinatorクローズ判断参照)。`slack_send_optin`requirement R9でこの見送りを覆し、起票する。
状態: **解決済み**
対象: `tester_mode_full_removal`案件AC2検証(Tester相当の検証実行)、`community.general.slack`モジュールの宛先組み立て挙動、`roles/common_slack/tasks/notify.yml`の抑止設計
種別: 未遂
原因分類: #テスト不足 #設計上の欠陥

## 症状

`tester_mode_full_removal`案件のAC2検証パターン3で、decoyの`vars/slack.yml`にループバック宛の閉ポートを指す非実在URLを置いて`community.general.slack`へ渡したところ、モジュールは`token`の中身を検証せず`https://hooks.<domain>/services/<token>`(既定`domain=slack.com`)という形でURLを組み立てるため、**実際に実在の`hooks.slack.com`へHTTP POSTが送信された**(応答は汎用ドキュメントページ、HTTP 200)。有効なwebhookパスではないため、どの実チャンネルにもメッセージは配信されていない。

## 原因

**`community.general.slack`は`domain`を明示しない限り常に`hooks.slack.com`宛にリクエストを組み立てる。** これは2026-08-01の`2026-08-01_tester-slack-decoy-did-not-contain-request.md`が特定した原因とまったく同一のクラスであり、**本件は同一欠陥クラスの3回目の再現**である(初回2026-07-26は起動主体未確認、2026-08-01が2回目、本件が3回目)。

さらに根底には、`2026-07-29_tester-slack-notify-misfire.md`が特定した構造的原因が共通して存在する — 「通知を抑止する唯一の手段が実行者ごとに異なる手段(変数の付与、decoyの設計)であり、**抑止手段を1つ誤ると既定で本番へ送る**」。decoyのURL差し替えは`community.general.slack`の`domain`挙動の前ではそもそも抑止手段として成立しなかった。

## 修正内容

本Incidentの起票と同じ`slack_send_optin`案件で、`roles/common_slack/tasks/notify.yml`へ**第3の抑止条件(AIエージェントセッション検出、環境変数`CLAUDECODE`の存在)を追加した**(`docs/ai/reviews/slack_send_optin/2026-08-02_003_implement.md`)。

これにより、Tester(および他のAIエージェントセッション)由来の実行は、**decoyの設計が成立するかどうかに関係なく**既定で送信抑止される。`community.general.slack`自身の`domain`挙動そのものは変更していない — `docs/ai/reviews/slack_send_optin/2026-08-02_001_requirement.md` R10がその対症療法(`domain`明示によるdecoy修正)を明示的に不採用と判定している。個々のdecoyを直すのではなく、AIエージェント発の実行という共通点そのものを既定で止める設計に切り替えた。

## 確認方法

Implementerが2026-08-02に、decoy inventory(`ansible_connection: local`、実host名・実IPを含まない)で本Incidentと同型の呼び出し(`CLAUDECODE`設定・`--check`なし・`skip_notifications`なし)を再現し、`community.general.slack`のtaskへ到達する前に抑止されること(`debug`出力でtrigger3が効いたことを確認、`community.general.slack`のtask自体が`skipping`表示、rc=0)を確認した。`CLAUDECODE`未設定・`INVOCATION_ID`も未設定の場合に送信側へ倒れること、`slack_force_send=true`が`skip_notifications`/`ansible_check_mode`を上書きできないこと(AC5②③相当)も同じ手段で確認済み。

**Tester役によるAC1〜AC7の正式な受入確認は別途実施される**(本Incidentの解決済み判定は実装レベルの自己検証に基づく)。

## 参照

- `docs/ai/memory/incidents/2026-07-29_tester-slack-notify-misfire.md`(同系列1回目相当、構造的原因の分析)
- `docs/ai/memory/incidents/2026-08-01_tester-slack-decoy-did-not-contain-request.md`(同一欠陥クラスの前回、`domain`挙動の特定)
- `docs/ai/reviews/tester_mode_full_removal/2026-08-02_006_test_result.md`「残存リスク」1(本事象の一次記録)
- `docs/ai/reviews/tester_mode_full_removal/2026-08-02_007_audit.md`指摘2(未起票の指摘、当時は起票見送り)
- `docs/ai/reviews/slack_send_optin/2026-08-02_001_requirement.md`(本Incidentを起票させたrequirement、R9)
- `docs/ai/reviews/slack_send_optin/2026-08-02_003_implement.md`(修正の実装記録)
