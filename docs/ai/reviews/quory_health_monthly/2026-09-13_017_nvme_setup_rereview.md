## Code Review: quory NVMe CLI setup 差し戻し再査読

### Summary

016のMajor #1/#2に対する修正を012 AC-S1/S2・013計画と照合した。対象欠落の一部経路と直近1時間内のAPT cache再更新は抑えたが、空成功と時間経過後の非冪等な再実行が残る。

### Critical Issues

なし。

### Major Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `playbooks/quory_nvme_setup.yml` | 29–50 | 016 #1は部分解消のみ。preflightは`'quory' in hostvars`でinventory内の存在を確認するが、実際の後段対象（`--limit`適用後）を確認しない。`ansible-playbook -i inventories/homelab/hosts.yml --limit localhost playbooks/quory_nvme_setup.yml --check`をローカル限定で実測すると、assertは`ok`、setup playは`skipping: no hosts matched`、全体rc=0。CLI readbackも導入見込みも無いまま成功し、AC-S1の対象・導入見込み表示と013の事前対象検査を満たさない。`hostvars`上の存在だけでなく、後段playがquoryを実際に1件対象にすることを確認できない場合は非0停止させる必要がある。 | Major (blocking) |
| 2 | `roles/quory_nvme_setup/tasks/main.yml`, `roles/quory_nvme_setup/defaults/main.yml` | 8–9, 3–9 | 016 #2は直近1時間の再実行だけ抑止した。`update_cache: true`と`cache_valid_time: 3600`では、APT cacheが1時間より古い通常再実行で、パッケージが既に導入済みでも`cache.update()`し、cache更新を`changed`へ反映する。ローカルのAnsible apt module 1404–1443行の条件から確定する経路で、012 P0の「冪等に導入する」契約を時間経過後に満たさない。defaultの説明にある「same-day re-run idempotent」も1時間の閾値とは一致しない。導入済み時の不要なcache更新を避け、時間を空けた再実行でも変更なしを確認する必要がある。 | Major (blocking) |

### Suggestions

なし（016の`nvme version`と実NVMe取得の区別は引き続き配備時の確認事項）。

### What Looks Good

- `-i 'localhost,'`の対象欠落時はpreflightがrc=2で停止することをローカル限定で再実測した。修正前の無条件の空成功は、この経路では閉じている。
- APTの現行実装ではcheck mode時にcache更新・パッケージ導入を行わず、readbackは`when: not ansible_check_mode`で抑止される。`nvme version`のrc非0は既定の失敗として伝播する。新たなshell補間・秘密露出・再利用漏れは見当たらない。

### 未確認事項

- 実quoryへの接続、Semaphore API、setupの実機`--check`/apply/readbackは未実施。AC-S1/S2の実機成立、AC-S3の`tool_unavailable`解消、AC-S4の実Semaphore readbackは未判定。
- `--limit localhost`の検証は実inventoryを読んだが、実行対象をlocalhostに限定し、quoryには接続していない。015の検証記録は現物とローカル実測で照合した。

### Verdict

Request Changes。016 Major #1/#2ともblocking残存。修正後の差分を再レビューする。
