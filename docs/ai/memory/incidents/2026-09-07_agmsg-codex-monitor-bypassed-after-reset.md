# Incident: clean start後にCodexのapp-server経路が成立しない

日付: 2026-09-07
状態: 解決済み
対象: `new-session.sh` / Codex app-server / agmsg Codex monitor (`homelab`, `homelab-ops`)
種別: 動作不具合
原因分類: #製造ミス #テスト不足 #運用考慮ミス

## 症状

`./new-session.sh --reset`でCoordinatorをclean startした後、quoryのOperatorから
`homelab-ops/coordinator`宛に届いた返信がansyのローカルstoreには同期されたが、
人が見ているCodexスレッドへ自動配送されなかった。

`delivery.sh status codex`は`homelab/coordinator`と
`homelab-ops/coordinator`の両方についてseat未記録・app-server不在を報告し、
`/tmp/new-session-boot.log`にはseat記録が30秒で失敗した記録が残っていた。

Codex 0.153.4への更新後、macOS/iPhoneアプリからCoordinatorセッションへも
接続できなくなった。`codex doctor --all`ではBackground Serverが
`running (ephemeral mode)`で、remote-control daemonのsettingsとpidfileは
存在しなかった。`codex remote-control start --json`は、現セッションの
ephemeral app-serverが稼働中のためdaemonへ切り替えられないとして停止した。

native remote-controlを優先する最初の修正ではtmux pane 0をhost shellへ変えたため、
Coordinator TUIがtmux外で起動される形になった。スマホからは接続できても、SSH切断後に
`tmux attach`で同じCoordinator TUIへ戻れず、SSH経由の会話継続性を失った。

## 原因

gitignoredのローカル`new-session.sh`が、monitor設定後のpane 0で`exec codex`を
実行していた。この非対話シェルでは`.bashrc`の`codex()` monitor関数は利用できず、
PATHも実Codex (`~/.local/bin/codex`)をagmsg shimより先に解決する。このため
`codex-monitor.sh`を通らず、seat記録に必要なapp-serverが作られなかった。

その後Codex 0.153.4では、`codex remote-control start`が永続app-serverを
managed daemonとして起動することを確認した。agmsg monitorも独自に
`codex app-server --listen ws://...`を起動する。
両者は同じCodex control socketを使用し、daemon管理外のapp-serverが存在すると
`remote-control start`は`app server is running but is not managed by codex app-server
daemon`で停止する。逆順でもagmsg側のapp-serverがcontrol socketを取得できない。

したがってnative remote-control daemonと現行agmsg monitorのapp-serverを
**2プロセス同時に**使う構成は成立しない。`new-session.sh`へ両方を順番に起動する
処理を入れたことが、今回のclean start失敗の直接原因だった。

ここから「スマホアプリにはmanaged daemonが必須で、monitorのapp-serverでは
疎通できない」と結論したのは未検証の推論だった。2つのapp-serverプロセスを
同時に立てることと、monitor中にスマホから接続できることは別の問いである。
2026-09-08、monitorのapp-serverだけを動かした状態でスマホアプリから同じ
Coordinator threadと会話できることを実測し、この推論が誤りだったと確認した。

## 修正内容

いったんnative daemonを優先して`turn`へ変更した。Stop hookによる取得自体は
成立したが、返信時点で待機中のCoordinatorを起こせず、次のturn終了と60秒の
cooldownまで表示されなかった。local Reviewerとの協調には適さないため、
2026-09-08にYoshinobuが従来のmonitorへ戻すと判断した。

`new-session.sh`はfresh create時に`delivery.sh set off`で旧bridgeを停止し、
`codex remote-control stop`でmanaged daemonを停止してから`set monitor`へ切り替える。
`homelab/coordinator`と`homelab-ops/coordinator`のseatを現在の同一threadへ記録し、
不在または不一致なら停止する。tmux pane 0はPATHやshell functionに依存せず
`codex-monitor.sh ... resume <thread>`を明示実行する。

これによりtmuxが保持する可視Coordinator TUIとbridgeの配送先を同じthreadにした。
Reviewer / Tester / Auditorも従来どおりtmuxに常駐する。

## 確認方法

- `bash -n new-session.sh`: PASS。
- `new-session.sh`はgitignoredのローカルhelperであることを確認。
- 別SSH shellから`./new-session.sh --reset`を実行し、同じCoordinator threadがtmux
  pane 0へresumeした。
- ReviewerのREADY、往復試験`MONITOR往復OK`、AuditorのREADYが、手動inboxなしで
  このthreadへ新しいturnとして届いた。local monitor配送は成立した。
- 今回のmonitor起動後、スマホアプリから同じCoordinator threadと会話できた。
- SSHから`tmux attach -t homelab`を実行し、スマホで継続していた同じCoordinator
  TUIへ戻れることを確認した。
- ansyの通常shellで`homelab-ops`のstale config lockを除去してsync engineを再起動し、
  Operatorの`配送確認OK`が同じCoordinator threadへmonitorで自動配送された。
