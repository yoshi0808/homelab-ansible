# prep-agent.sh/new-session.shの実地テストは実在するidentity名を使うと本番を壊す

**分類**: Lesson
**由来**: Phase8 TODO8-3(2026-07-23)、新`prep-agent.sh`の実地検証中に発生した実際の事故と復旧。

## 何が起きたか

新しい`prep-agent.sh`の`tester`向けメッセージを検証するため、本番の`homelab`セッションには触れず、隔離した別tmuxセッション+別agmsgチーム(`homelab-phase8test`)で`tester`という同名identityを`join.sh`させてテストした。

しかし`prep-agent.sh`は`SESSION=homelab`が固定値で、実際のメッセージ送信(`send.sh`)は常に`homelab`チーム宛に飛ぶ。さらにテスト用codexプロセスが`/agmsg actas tester`を実行した際、`homelab`チームの`tester`ロールセッション記録(team+agentがキー)まで新しいスレッドIDで上書きしてしまい、**本番testerペインの実際のbridgeプロセスが自動的にkillされ、無関係な(テスト側の)スレッドへ差し替わった**。本番testerのCodexプロセス自体は生存していたが、bridge(agmsg配送の実体)を失い、メッセージを受け取れない状態になっていた。

## 気づいた経緯

`agmsg_role_session_uuid homelab tester`が返すスレッドIDが、会話中に記録していた本番の値と食い違っていたことで発覚。`ps aux`で`codex-bridge.js --pair homelab?tester`の実体を確認すると、本番スレッド宛のbridgeが消え、テスト由来の新スレッド宛のbridgeだけが残っていた。

## 復旧方法

`agmsg_role_session_record`(`scripts/lib/role-session.sh`)で`homelab`+`tester`のレコードを本番の正しいスレッドIDへ書き戻すと、常駐しているbridge-launcher(2秒間隔でポーリングし、記録スレッドとの不一致を検知して自動的にbridgeを再起動する設計、`codex-bridge-launcher.sh`参照)が自動的に誤ったbridgeをkillし、正しいスレッド宛のbridgeを再起動して復旧した。手動でbridgeを直接操作する必要はなかった。

## 適用条件(今後この種のテストをする場合)

1. **本番で実際に使われているidentity名(reviewer/reviewer2/implementer/implementer2/tester/tester2/techlead2)をテストで再利用しない**。別agmsgチームで`join.sh`しても、`prep-agent.sh`のチーム固定・codex側の登録挙動により本番のロールセッション記録まで書き換わりうる。
2. どうしても特定roleのメッセージ内容(case分岐)を検証したい場合は、**実際にagmsg経由で送信・kickする代わりに、静的にメッセージ文字列を抽出して内容を確認する**(本ファイルの由来となった検証では、静的確認は事前に完了していた)。
3. 実際にend-to-endで送受信まで検証したい場合は、本番に存在しない架空のidentity名(例: `tester-canary`)を使う。ただしその場合`prep-agent.sh`のcase分岐は汎用メッセージにフォールバックするため、role固有メッセージの実地検証にはならない。
4. 異変に気づいたら、まず`scripts/lib/role-session.sh`の`agmsg_role_session_uuid <team> <agent>`で現在の記録スレッドを確認し、本番の既知スレッドIDと突き合わせる。ズレていたら`agmsg_role_session_record`で正しい値へ書き戻せば、bridge-launcherが自動修復する。
