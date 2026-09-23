# Implementation: incident-capture exit semantics

## Result

- 相関先のない notable spool record の生成箇所で、`slack_status` が文字列の
  `info` または `warning` に完全一致するときだけ、相関不一致を新設した
  `correlation_notes` へ記録するようにした。単独バンドルは従来どおり作る。
- `collection_errors` は常に保持するため、同じバンドルへ後段の wrapper 不在や
  named operation 不在などが追加された場合は従来どおり exit 2 になる。
- non-notable 判定にも文字列型確認を入れた。これにより list/object のような
  unhashable な `slack_status` は内部例外にせず、従来どおり相関不一致の
  collection error として exit 2 になる。
- exit 定数と service template は変更していない。

## Self-verification

- `python3 scripts/tests/incident_capture_exit_semantics/run-tests.py -v`:
  11 tests passed. 実際の `main()` を temporary spool/state/bundle と mock した
  named-query/snapshot 呼出しで通し、ネットワーク・実ホスト・Ansible・Slackは
  使用していない。
- info / warning 単独は exit 0、journal 出力なし、`collection_errors` 空、
  tolerance (`90s`) を含む `correlation_notes` を確認した。
- error / critical、info+error、spool退避失敗、info bundleへの後段 error は
  collection error と exit 2 のままを確認した。後段 error の場合、note と
  `collection_errors` が同じ bundle summary に共存することも確認した。
- AC10相当として unknown文字列、欠落、整数、JSON list、JSON object を通し、
  全て exit 2 で、list/object が exit 3 に化けないことを確認した。
- 内部例外は subprocess で exit 3、Semaphore bundle の既存 summary shape、
  定数 `0/2/3` と service unit の `flock -n -E 75` を確認した。
- `python3 -m py_compile` と `git diff --check` を通過した。

## Delivery note

- 新設テストは `scripts/tests/incident_capture_exit_semantics/` に置いた。この
  リポジトリの `.gitignore` は `scripts/tests/*` を無視するため、Coordinator は
  commit対象に含める際にこの3ファイルを明示的に force-add する必要がある。
- script変更を本番へ反映するには、別途 `incident_capture_setup.yml` の配備が必要。
  本実装では実行していない。

## Follow-up

- 終了コードのモジュール契約節へ、`info` / `warning` の相関不一致を
  `correlation_notes`へ記録してexit 0とする限定例外と、他のnotable値を
  fail-closedでcollection errorへ残すことを追記した。
- AC11のもう一方の例であるwrapperバイナリ不在を、
  `append_missing_binary_errors`を通すfixtureとして追加した。info noteと
  wrapper errorが同じbundle summaryに共存し、exit 2となることを確認する。
