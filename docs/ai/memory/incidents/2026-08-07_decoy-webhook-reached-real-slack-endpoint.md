# Incident: decoyのwebhook URLが実在のSlackエンドポイントへ届いた

日付: 2026-08-07
状態: 解決済み
対象: `community.general.slack` を使う検証全般 / `playbooks/incident_investigate_notify.yml` の decoy 手順
種別: 未遂
原因分類: #テスト不足

## 症状

一次調査の通知記録(`docs/ai/reviews/incident_investigation_notify/2026-08-07_001_requirement.md` AC2)の decoy を組む過程で、Implementer が**送信先を偽装したつもりの webhook URL** を与えたところ、`community.general.slack` が**実在の `hooks.slack.com` へ HTTP リクエストを1回送出した**(応答 302)。

**メッセージは配信されていない**(有効なトークンではないため)。実害は無いが、`docs/ai/core.md`「subagentが共通して守ること」の「**本番Slackへ通知が送られた状態で報告を返さない**」に触れかけた。

## 原因

**`community.general.slack` は `domain` 引数を無視する。** 宛先は `slack.com` / `slack-gov.com` にモジュール内でハードコードされており、引数から組み立て直されない。したがって **URL やドメインを差し替える形の decoy はこのモジュールに対して成立しない。**

これは `docs/ai/core.md` が decoy について既に警告している性質そのものである — 「**対象モジュールが宛先を実際にどう決めるか(引数をそのまま使うのか、別のパラメータから組み立て直すのか)を確かめない限り、decoyが成立していると仮定しない**」。今回は宛先を差し替えられる前提を確かめずに置いた。

**「completes without error」で decoy の成立を判定できない**点も同じ形である。302 が返ってモジュールは失敗し、狙っていた「失敗経路」自体は再現できてしまう。**目的の観測は得られるのに、宛先の偽装だけが成立していない**ため、出力を見ているだけでは気づけない。

## 修正内容

decoy を、**ネットワークへ出る前にモジュール側の検証で落ちるトークン形**へ変更した(URL の差し替えではなく、送信そのものが起きない形にした)。以降の AC2 / AC5 の検証はこの形で行い、実在エンドポイントへの到達は発生していない。

**再利用可能な知見として残すこと**: `community.general.slack` を含む検証では、**宛先を差し替える decoy を作らない。** 送信そのものが起きない形(モジュール側の引数検証で落とす / `--check` / 抑止変数)を使う。宛先の偽装が効くかどうかは、モジュールが宛先をどう決めるかを読んでからでなければ判定できない。

## 確認方法

- 変更後の decoy でモジュールがネットワークへ出ないこと(リクエストが発生しないこと)を実行して確認済み。
- 該当の一次記録は `docs/ai/reviews/incident_investigation_notify/2026-08-07_002_implement.md` §3-1。
