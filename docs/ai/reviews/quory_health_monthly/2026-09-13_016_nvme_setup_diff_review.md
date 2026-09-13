## Code Review: quory NVMe CLI setup 差分

### Summary

012要求・013計画（014承認）・QHM Policyに照らした独立レビュー。専用入口、観測との分離、Semaphoreテンプレート1件追加とschedule非追加は確認できたが、対象不在時の空成功と、通常実行のAPT cache更新による非冪等性が残る。実ホスト・Semaphore APIには接触していない。

### Critical Issues

なし。

### Major Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `playbooks/quory_nvme_setup.yml` | 28–34 | `hosts: quory`しかなく、事前のinventory/対象件数guardが無い。`quory`を欠くinventoryで`ansible-playbook -i 'localhost,' --list-hosts playbooks/quory_nvme_setup.yml`を実行すると、`Could not match supplied host pattern`の警告と`hosts (0)`を出してrc=0になる。実ジョブも対象0件ならsetup・readbackをせず成功終了し得るため、「判定できないときは止める」（core）とAC-S2の導入成功判定に反する。localhost側preflight等で対象が正確にquory 1件と確認できない場合は非0停止させる必要がある。 | Major (blocking) |
| 2 | `roles/quory_nvme_setup/tasks/main.yml` | 4–10 | `ansible.builtin.apt`に`update_cache: true`、`cache_valid_time`未指定（既定0）を置いている。ローカルのAnsible apt module `/usr/lib/python3/dist-packages/ansible/modules/apt.py` 1404–1443行では、通常実行でcache更新条件が常に成立し、`cache.update()`を行う。パッケージ導入済みの再実行でもAPT package listを書き換え、cache更新を`changed`へ反映するため、P0の冪等な導入と「nvme-cliに導入対象を限定」の意図から外れる。初回更新が必要なら導入時だけに限定するか、有効期間を定めて不要な再更新を避け、再実行時の状態・changed判定を検証する必要がある。 | Major (blocking) |

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---:|---|---|
| 1 | `roles/quory_nvme_setup/tasks/main.yml` | 12–24 | `nvme version`はCLI実行可否のreadbackとして妥当だが、NVMe deviceへの`id-ctrl`/`smart-log`取得成功は証明しない。AC-S3の月次ヘルス`--check`を独立に観測し、`tool_unavailable`が消えたことと新たな失敗理由を分けて記録する。 | Test/運用確認 |

### What Looks Good

- setup playbookは`check-mode-native`を宣言し、観測playbook・roleを変更していない。APT moduleの現行実装では`module.check_mode`時に`cache.update()`を呼ばず、インストールもpreviewに留まる。`nvme version`のreadback blockは通常実行だけで動き、`command`の既定rc非0失敗を維持する。collectorも`become: true`であり、readbackの実行権限は揃っている。
- Semaphore catalogには専用`SEMI-SAFE` templateを1件追加し、scheduleの差分は無い。READMEとOperations Contextは配備順と未確認事項を示している。既存setupと同じtemplate表現を再利用しており、重複したreconcileロジックは無い。shell補間・秘密値のログ露出・不審なdelegate/lookupは新規差分に見当たらない。

### 検証範囲と未確認事項

- 読んだもの: 012要求、013計画、014査読、015実装記録、QHM/実行境界/Ansible test safety Policy、対象playbook・role・template catalog差分・README・Operations Context、既存health collectorとquory inventory/host vars。`--list-hosts`はlocalhostだけの合成inventoryで実行し、実ホストへAnsibleを実行していない。
- AC-S1: 静的にはcheck時のapt/CLI境界を確認。実Semaphore `--check`のrc、対象・導入見込み表示、通知/report非生成は未確認。特に対象欠落のnegative caseはfinding #1。
- AC-S2: apt導入と`nvme version`の失敗伝播を静的確認。実quoryでの初回適用・変更不要時・部分失敗後の再実行、CLI readbackは未実施。変更不要時の冪等性はfinding #2。
- AC-S3: この差分は健康collectorを変更しない。setup後の月次health `--check`と`tool_unavailable`解消は未確認で、実機観測が必要。
- AC-S4: catalog上のtemplate追加は1件、schedule追加は0件。実Semaphoreのtemplate/readbackとsyntax-checkの独立再実行は未実施（015記録ではsyntax-check rc0）。

### Verdict

Request Changes。Major #1・#2の解消後に差分再レビューが必要。実機ACは配備工程まで未判定とする。
