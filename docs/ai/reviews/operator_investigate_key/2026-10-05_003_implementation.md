# Implementation: Operator専用調査鍵

## Result

- quoryの`yoshi`用に通常host用とPVE用を分離した調査鍵を生成する。各private keyは既存時に再生成せず、`yoshi`所有・`0600`へ収束する。秘密鍵・公開鍵の実値はリポジトリへ追加していない。
- authy / monnieの`authorized_keys`は4行、pve1 / pve2は3行を排他的に描画する。Operator行は既存のCoordinator調査行と同じread-only forced commandおよび制限オプションを使い、action dispatchには追加していない。
- 通常／PVE双方の既存`homelab-investigate-<host>`は実行identityで鍵とknown_hostsを固定選択する。`recovery-exec`の選択は従来どおりで、`yoshi`は専用鍵と専用known_hostsを使う。任意callerや鍵path／known_hosts pathを引数で渡す形は受け付けない。
- Operator用known_hostsの生成・所有権設定と、日次drift検査の期待本数(通常4、PVE3)を追加した。Operator Request Channelとdispatchカタログの鍵到達性の記述も更新した。

## Self-verification

- `PYTHONDONTWRITEBYTECODE=1 python3 roles/recovery_exec/tests/test_operator_investigate_key.py -v`: 6 tests passed。両wrapperをrenderし、fake SSH argvで`recovery-exec`／`yoshi`の鍵・known_hosts・strict checkingを確認した。authorized_keysの既存行の文字列、Operatorのread-only行、引数拒否、key generationの再実行不変性と`0600`も確認した。
- `ansible-playbook -i roles/recovery_exec/tests/inventory_operator_investigate_key.yml playbooks/recovery_exec_setup.yml --check --extra-vars '{"recovery_exec_pve_targets":[{"name":"decoy-pve","host":"127.0.0.1"}]}'`: `changed=0, failed=0`。Operator鍵生成、public keyのslurp、authorized_keys配備、known_hosts更新がskipされ、target setup includeとloopback TCP probeまでは到達した。
- `git diff --check`を通過した。実ホスト、SSH、Semaphore、本番Slack、git commit/pushには触れていない。

## Delivery note

- 反映にはYoshinobuがquoryのSemaphoreから`playbooks/recovery_exec_setup.yml`を実行する必要がある。pve1が停止中なら、稼働日に再実行して鍵を配備する。
