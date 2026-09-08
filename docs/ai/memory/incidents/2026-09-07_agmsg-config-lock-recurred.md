# Incident: agmsg sync engineのstale config lock再発

日付: 2026-09-07
状態: 未解決
対象: agmsg remote team `homelab-ops` のsync engine(ansy側、リポジトリ外)
種別: 動作不具合
原因分類: #運用考慮ミス

## 症状

Semaphore DB障害のOPREQを送る前提検査で、`remote.sh status homelab-ops` がengine pidfileのPIDをdeadまたはforeignとしてstale判定した。OPREQ登録は通知不能として登録前に停止した。

Yoshinobuが通常シェルから `remote.sh sync start homelab-ops` を実行したが、`teams/homelab-ops/.config.lock` のregistry lockを10秒以内に取得できず終了した。これは `docs/ai/memory/incidents/2026-09-02_agmsg-sync-engine-dead-for-five-days.md` と同じ症状である。

2026-09-08のansy再起動後にも同じ症状が再発した。Operatorはquory側で返信済みだったが、ansy側のlocal storeへ同期されず、Coordinatorのmonitorへ届かなかった。通常ホスト側の`remote.sh status homelab-ops`でもengine staleを確認し、`sync start`は同じregistry lock timeoutで失敗した。

## 原因

`.config.lock` の残留。今回そのlockが取り残された直接原因は未判明。

## 修正内容

各発生時にYoshinobuが通常シェルから、空ディレクトリにしか成功しない `rmdir` でstale lockを除去し、sync engineを再起動した。lockが残る直接原因への恒久修正は未実施であり、再起動後には再発を前提にstatusを確認する。

## 確認方法

`remote.sh status homelab-ops` でengine PIDの稼働と、2026-09-07T04:57:18.536Zの初回同期成功を確認した。続いて `scripts/oprc-submit.sh` がOPREQの登録とOperatorへのagmsg通知を完走した。

2026-09-08の再発では、通常shellからの再起動直後にengine PIDの稼働を確認し、その後Operatorの`配送確認OK`がansy側へ同期され、同じCoordinator threadへmonitorで自動配送された。
