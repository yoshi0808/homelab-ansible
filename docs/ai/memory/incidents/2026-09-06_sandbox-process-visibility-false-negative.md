# Incident: sandbox のプロセス不可視を停止と誤判定

日付: 2026-09-06
状態: 解決済み
対象: agmsg remote sync の稼働確認
種別: 未遂
原因分類: #運用考慮ミス

## 症状

Codex のツール実行から `remote.sh status homelab-ops` を実行すると、pidfile が指す PID を `dead or foreign process` として `engine stale` が返った。同じ sandbox 内の `ps` でも該当 PID は見えなかったため、Coordinator は agmsg の remote 通知と OPREQ の新規送信が利用不能だと誤って判断した。

同じホストの通常シェルから確認すると、同じ PID の engine は `running` であり、`last successful sync` も直近に更新されていた。実害はなく、OPREQ も利用可能だった。

## 原因

エージェントの sandbox からホスト側プロセスを観測できないことを、ホスト上でプロセスが存在しないことと同一視した。`remote.sh status` は PID の生存だけでなくコマンドラインが対象 engine と一致することも確認するため、観測主体がその情報を読めない場合は、稼働中でも `stale` へ倒れる。

## 修正内容

`docs/ai/context/operations/agent-messaging.md` の落とし穴へ、sandbox 内の否定結果では停止を断定せず、通常シェルからの `remote.sh status` と直近の `last successful sync` で確定する手順を追記した。

## 確認方法

通常シェルから `remote.sh status homelab-ops` を実行し、同じ PID について `engine running`、直近の `last successful sync`、`encryption: age-v1, key present` が表示されることを確認した。

さらに ansy の `coordinator` から quory の `operator` へ agmsg で疎通確認を送り、`operator` から `疎通確認OK` の返信を受信して、双方向の配送が成立することを確認した。
