# Implementation: incident-capture unregistered host

## Result

- `failure_snapshot_ops` に登録のない有効な `play_host` は、追加snapshotを取らない理由を `summary.snapshot.host.not_collected` として残し、`collection_errors` には積まないようにした。spool単独とSemaphore相関bundleは同じ後段処理を通る。
- 空文字列・非文字列の `play_host` と、登録済みだが空リストのhostはfail-closedでcollection errorに残す。登録済みの非空操作は従来どおりhost snapshotを取得し、host wrapper不在はexit 2のままとした。
- `incident_capture_failure_snapshot_ops` の値を変更せず、コメントとcollectorの旧契約を説明するdocstring/commentを新しい契約へ更新した。終了コード定数とservice unitは変更していない。

## Self-verification

- `python3 scripts/tests/incident_capture_exit_semantics/run-tests.py -v`: 17 tests passed。
- 実関数を通すオフラインfixtureで、未登録の `quory` / `localhost` / `ansy` がexit 0・journal無出力・非エラー位置への記録になること、Semaphore相関bundleでも同じことを確認した。
- 未登録hostのerror通知は `no correlated Semaphore job` のみでexit 2、空文字列・整数・list・objectと登録済み空リストはexit 2、登録済み非空操作はhost snapshot結果をsummaryへ残すことを確認した。
- 既存のbundle-level error testはhost snapshot wrapper不在へ置換し、base snapshot wrapper不在の既存テストとは別経路を維持した。実ホスト、SSH、Semaphore、Ansible、本番Slackには触れていない。

## Delivery note

- collector scriptを本番へ反映するには、別途 `playbooks/incident_capture_setup.yml` の配備が必要。本実装では実行していない。

## 差し戻し対応

- `host_cache` のキーを型付きにし、文字列 `"[]"` とlist `[]` が同じ周期に現れても共有しないようにした。回帰fixtureで前者を非エラーnote、後者をcollection error・exit 2として確認した。
- 新規fixtureでは、`summaries[0]` を参照する前にsummary件数をassertするようにした。
