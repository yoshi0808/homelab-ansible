# dispatch read-only語彙追加 実装記録

## 対象と変更

- class Q: `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh` に `pkg-list [pattern]` と `semaphore-query schedule-list <n>` を追加した。
- class P/G: `roles/recovery_exec/templates/recovery-investigate-dispatch-pve.sh.j2` と `roles/recovery_exec/templates/recovery-investigate-dispatch.sh.j2` に `pkg-list [pattern]` を同じ検証・実行契約で追加した。
- helper: `roles/recovery_exec/files/homelab-semaphore-query` に `schedule-list` のquery、usage、`1..200`範囲、API取得・id昇順・JSON出力を追加した。
- 語彙カタログ: `docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md` に§10と総数を追加した。

## 実装判断

- `pkg-list` は `dpkg-query -W` を使い、patternは`^[A-Za-z0-9._+*-]{1,64}$`で検証してから、引用した単一引数として渡す。省略時は全件、一致0件はdpkg-queryのrc=1をrc=0・空stdoutへ正規化する。入力不正・arity超過ではdpkg-queryを起動しない。
- `schedule-list` は既存 `template-list` の `QUERIES` / `QUERY_RANGE_QUERIES` / usage / main dispatchの対応関係を踏襲した。APIの配列要素がobjectで、idが整数であることだけを検証し、id昇順で先頭n件を1行1 JSONとして出力する。他フィールドはAPI応答のまま保持し、次回実行時刻を合成しない。
- 実装記録で確認した配備入口は、Qが`playbooks/dev_investigate_setup.yml`から`roles/dev_investigate/tasks/main.yml`のcopy task、P/Gが`playbooks/recovery_exec_setup.yml`から`roles/recovery_exec/tasks/target_setup.yml`のtemplate task、helperが同playbookから`roles/recovery_exec/tasks/main.yml:442-451`のcopy taskである。配備は行っていない。

## 自己検証

- `bash -n`でQ dispatchを検査し、P/GはJinja2でfixture値を描画した後のスクリプトを`bash -n`で検査した。
- helperをPythonのcompile検査に通し、`schedule-list`のfixture API応答を使って、id昇順・先頭n件・APIオブジェクト保持を確認した。`n=0` / `201` / 非数は既存の範囲・usage契約で非zeroになることを確認した。
- Q/P/G dispatchをローカルで`SSH_ORIGINAL_COMMAND`に与えて実行し、`pkg-list`の無指定・正常pattern・一致0件、無効pattern、65文字pattern、arity超過を確認した。Qのschedule-list実API呼出しはTOKEN/APIが必要なため、実host/APIへは接触していない。
- 3 dispatchの既存probe（`journal-unit`のoperand過多、`semaphore-query`のarity超過）は非zero拒否を維持することを確認した。
- `ansible-playbook --syntax-check playbooks/dev_investigate_setup.yml` と `recovery_exec_setup.yml`、shell/python構文検査、`scripts/check-doc-consistency.py`、`git diff --check`はすべて成功した。

## 差分レビュー・Tester結果の反映

- Testerのansy Semaphore API実測（`_004_test_result.md`）で、schedule一覧のフィールドは`active` / `cron_format` / `delete_after_run` / `id` / `name` / `project_id` / `repository_id` / `template_id` / `tpl_name` / `type`に確定した。`task_params`と次回実行時刻相当のフィールドは含まれないため、カタログへ「読めるもの・読めないもの」を追記した。
- 空白を含むpatternはpattern regexへ到達せず、既存parserのarity経路で拒否される。拒否結果と`dpkg-query`未実行は要件を満たすため、この挙動は変更しないと判断した。

## 未確認事項

- 実host上のdpkg-query出力、quoryへの配備後hash、翌日drift検査は未確認。Tester/配備工程で確認する。
