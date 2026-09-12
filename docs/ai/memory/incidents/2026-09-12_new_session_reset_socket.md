# Incident: new-session --reset が制御ソケット待ちで停止

日付: 2026-09-12
状態: 未解決
対象: new-session.sh（Git管理外のローカル起動補助）
種別: 動作不具合

## 症状

ユーザーの `./new-session.sh --reset` が agmsg bridge 2件を停止した後、制御ソケット解放待ちで失敗した。

## 原因

停止できなかった直接原因は未判明。`ss -xlpn` と sandbox 外の `ps` により、PID 1397387（9月9日起動、親PID 1、`codex -c features.code_mode_host=true app-server --listen unix://`）が制御ソケットを保持していることを確認した。`codex app-server daemon version` は status=running、CLI=0.154.0、server=0.153.4 を返した。ユーザーsystemdの Codex unit は0件。版差が原因であるとは未確認。

`stop_app_server_for_restart` は `remote-control stop --json` の出力を破棄し、失敗を `|| true` で吸収するため停止理由が見えない。現在の対話との接続関係が未確認のため、当該serverの停止は実行していない。

## 修正内容

`stop_app_server_for_restart` が `remote-control stop --json` の失敗を吸収せず、停止失敗時は既存tmux sessionを残して終了するよう変更した。ただし、当初のdaemonが停止しなかった原因そのものは修正できたと断定しない。

## 確認方法

上記の読み取り確認後、Yoshinobuが更新後の `./new-session.sh --reset` を実行し、Coordinator / Implementer / Reviewer / Auditorの新しいtmux構成が起動した。ただし当初の停止不能を同条件で再現しておらず、直接原因も未確定のため、調査はここで打ち切って未解決とする。再発時は `remote-control stop --json` の保持した出力を起点に調査する。
