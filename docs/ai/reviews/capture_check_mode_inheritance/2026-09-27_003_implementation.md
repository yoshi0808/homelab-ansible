# implementation: capture check mode inheritance

日付: 2026-09-27 (JST) / Role: Implementer

## 変更

- `roles/common_slack/tasks/capture.yml` のspool作成、レコード書込み、書込み済みID更新へ `check_mode: "{{ ansible_check_mode }}"` を直接指定した。callerの `check_mode: false` を継承しても、CLIの `--check` では書込みmoduleがsimulateする。
- `set_fact` はcheck modeでも実行されるため、`--check` 時は `_capture_written_id` の代わりに専用no-op factを更新する。既存の書込み済みIDは保持され、未定義なら未定義のままである。通常実行時の `_capture_written_id: <今回のid>` は維持した。
- ヘッダと不変条件コメントを実装後のcheck mode継承規則へ更新した。
- `roles/common_slack/tests/` に、実spoolを使わず一時marker/spoolと別プロセスで実行するfixtureとrunnerを追加した。

## 検証結果

変更前のfixture測定では、通常include・`check_mode: false` 継承includeはいずれも `ok=11 changed=1 failed=0 skipped=5 rescued=0 ignored=0` で1件書込んだ。`--check` の通常includeはファイルを作らない一方でIDを設定し、継承includeは1件を書込んだ（問題の再現）。

変更後に `bash roles/common_slack/tests/run_capture_check_mode.sh` を実行した。

| ケース | spool件数 | `_capture_written_id` | recap |
|---|---:|---|---|
| 通常include | 1 | 今回のファイルID | `ok=11 changed=1 failed=0 skipped=5 rescued=0 ignored=0` |
| `check_mode: false` 継承include | 1 | 今回のファイルID | 同上 |
| `--check` 通常include | 0 | 未定義 | 同上 |
| `--check` 継承include | 0 | 未定義 | 同上 |
| markerなし | 0 | 未定義 | `ok=6 changed=0 failed=0 skipped=10 rescued=0 ignored=0` |
| spool親が通常ファイル | 0 | 未定義 | `ok=9 changed=1 failed=0 skipped=5 rescued=1 ignored=0` |

通常2ケースは変更前と同じrecapであり、`--check` の2ケースも捕捉task数を増減させずに成功した。fixtureは通常時にfooterと同じ式が `capture: <今回のid>` になることもassertする。

追加検証:

- `ansible-playbook --syntax-check roles/common_slack/tests/test_capture_check_mode.yml`: 成功
- `python3 scripts/check-doc-consistency.py`: check1〜check3 成功
- `bash roles/proxmox_evacuate_node/tests/run_failure_notification.sh`: 7シナリオ成功
- `git diff --check`: 成功

## 未解決事項

なし。実ホスト、SSH、本番spool、commit/pushには触れていない。
