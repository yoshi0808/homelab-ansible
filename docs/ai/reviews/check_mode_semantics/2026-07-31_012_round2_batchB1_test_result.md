# test_result: Round 2 バッチB-1 — `check-mode-native` への変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md`(訂正/決着注記反映後の本文)§6 AC1・AC3・AC4・AC5
実装記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_010_round2_batchB1_implement.md`
レビュー記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_011_round2_batchB1_review.md`(Approve)

## 対象パス

`playbooks/{recovery_io_setup,recovery_push_setup,recovery_push_drill_setup,systemd_timers,incident_sync_timer,time_sync_ntp_reference,ca_trust_deploy,incident_inspect_setup}.yml` と対応role(`roles/recovery_io/*`、`roles/recovery_push/*`、`roles/systemd_timers/tasks/main.yml`、`roles/incident_sync/*`、`roles/time_sync_ntp_reference/tasks/chrony_hosts.yml`、`roles/homelab_cert_renew/{handlers/main.yml,tasks/deploy_ca_trust.yml}`、`roles/incident_inspect/tasks/main.yml`)。`recovery_exec_setup`(B-2)・バッチCは対象外(未実行)。

## 実行環境

- 実行元: ansy(このTester sandbox)。`ANSIBLE_LOCAL_TEMP=/tmp/ansible-local`、`ANSIBLE_REMOTE_TEMP='/tmp/ansible-remote-$USER'`(skills/test-strategy/SKILL.md準拠)。
- 触れた実ホスト: ansy, quory, authy, monnie, pve2(read-only ad-hoc確認 + 対象playbookの`--check`実行)。pve1は接続試行のみ(下記参照)。
- `git add` / `git commit` / `git push` は一切行っていない。対象実装ファイルは変更していない(`git status`は本作業開始前と同一の20ファイルmodified + 2ファイルuntracked、いずれもImplementer/Reviewerの成果物)。

## 事前確認: ホスト到達性

`ansible all -i inventories/homelab/hosts.yml -m ping` を実行し、pve1のみ `UNREACHABLE`(`No route to host`、`ssh: connect to host pve1.internal port 22`)、他(pve2/authy/monnie/quory/ansy/sophos-fw/localhost)は`pong`を確認した。`cloudkey`は`cloudkey_ssh_password`未定義で別途失敗するが対象外グループのため無視した。**pve1停止は指示どおり異常ではなく、想定内の事前確認結果として記録する。**

## AC1(dry-runとして成立する): 合格

8 playbookすべてを`scripts/safe-ansible-check.sh <playbook> -i inventories/homelab/hosts.yml --check --diff`で実行した。結果:

| playbook | rc | 対象host(recap) | changed | skipped(破壊的task) |
|---|---|---|---|---|
| recovery_io_setup | 0 | ansy, quory | 0 | 各12 |
| recovery_push_setup | 0 | quory(authy/monnie はdelegate_toでquoryの統計に計上) | 0 | 28 |
| recovery_push_drill_setup | 0 | quory(同上、実体はauthy/monnie) | 0 | 4 |
| systemd_timers | 0 | quory(`connection: local`のためconnection先はこの実行元=ansy。下記参照) | 0 | 4 |
| incident_sync_timer | 0 | ansy | 0 | 3 |
| time_sync_ntp_reference | 0 | pve1, pve2, ansy, monnie, authy | 0 | 各2 |
| ca_trust_deploy | 0 | ansy, quory, monnie, authy, pve1, pve2 | 0 | 各2(quoryのみ0、slurpが`ok`) |
| incident_inspect_setup | 0 | ansy, quory | 0 | 各11 |

全8本で終了コード0、`changed=0`、破壊的taskは全て`skipping`として現れた。全ログで`RUNNING HANDLER`行が一度も出現しないことを`grep -n "RUNNING HANDLER"`で確認した(該当ゼロ)。`update-ca-certificates` / `Restart chrony` / `Reload systemd` / `Restart recovery-io` / `Reload systemd for incident sync`のいずれも発火していない。

**R5の実地確認**: `incident_sync_timer`の`Query next scheduled run`(`check_mode: false`)は`--check`下でも`ok`として実行され、`systemctl list-timers`の実出力(直近の実タイマー状態)を返した。ログ:
```
TASK [incident_sync : Query next scheduled run] ***
ok: [ansy]
TASK [incident_sync : Report next scheduled run] ***
ok: [ansy] => { "msg": ["NEXT ... ansible-incident-sync.timer ...", "1 timers listed."] }
```
これはTS-017が求める「read-onlyな診断は--check下でも本実行」の実地確認である。

**ca_trust_deployのslurp非対称の実地確認**: `Slurp ROOT CA certificate from source host`(`delegate_to: quory`, `run_once: true`)は`--check`下でも`ok: [quory]`として実行され、破壊的2task(`Remove ...`/`Deploy ROOT CA certificate ...`)のみ`skipping`となった。実装記録が主張する非対称(ca_trust_deployのslurpはungate/recovery_pushのslurpはgate)を実行結果で確認した——`recovery_push_setup`のログでは`Slurp push public key from {authy,monnie}`が該当のTS-015 blockごと`skipping`に現れている。

**recovery_push の`Scan quory host key`(ungated command)の実地確認**: 明示的な`when:`が無いにもかかわらず`--check`下では`skipping: [quory]`(delegate先ホストラベルで表示)として現れた——`command`モジュールのネイティブauto-skipが実際に効いていることを確認した(実装記録・レビュー記録の主張どおり)。

**pve1到達性と終了コードの関係(区別して記録)**: `time_sync_ntp_reference`・`ca_trust_deploy`ともpve1を含む play で終了コード0、`unreachable=0`だった。ログを確認すると、pve1に対して実行されたのは`pre_tasks`の`ansible.builtin.assert`(action pluginがローカル評価でありSSH接続を要さない)のみで、実変更を行う各taskは`when: not ansible_check_mode`によりpve1への接続を試みる前にskipされている。**つまりこの2本の`--check`実行は、pve1が到達不能である事実そのものを一度も検出していない**(SSH接続を試行していないため)。事前確認の`ansible ... -m ping`でのUNREACHABLEと、対象playbookの`--check`実行でのrc=0/unreachable=0は矛盾ではなく、後者が構造的にpve1へ接続していないことの帰結である。`RUN_UNREACHABLE_HOSTS`(rc=4)は本バッチのいずれの実行でも発生しなかった——観測結果として区別して記録する。

**systemd_timersの`connection: local`についての注記**: プレイブック冒頭のコメントのとおり、`target_hosts`はinventoryグループ選択のみに使われ、`connection: local`のためtaskの実行(≒実際に書き込まれる先)は常にこのplaybookを起動したホスト(今回はansy)である。既定値`target_hosts=control_nodes`(quory)で実行してもPLAY RECAPのホストラベルは"quory"だが、実際に触れるファイルシステムはansyのものである。これは実装・レビュー時点で変更されていない既存の設計であり、本バッチが変えたものではない。

## AC3(部分適用が起きない): 合格(pve1を除く到達可能ホストで)

各playbookのdiffから抽出した「新規に触れる/触れうるパス・ユーザー・ACL・systemd unit」を`PATH:` / `USER:` / `UNIT:` / `ACL:` のトークンで列挙し(下記「フィンガープリント対象」参照)、読み取り専用のfingerprintスクリプト(`ansible.builtin.script`でread-onlyに転送・実行、`--become`)で`--check`実行の**前後**それぞれにスナップショットを取得、`diff`で突合した。

対象ホスト: ansy(25項目)、quory(24項目)、authy(13項目)、monnie(16項目)、pve2(5項目)。

```
=== ansy ===   diff pre/post → IDENTICAL
=== quory ===  diff pre/post → IDENTICAL
=== authy ===  diff pre/post → IDENTICAL
=== monnie === diff pre/post → IDENTICAL
=== pve2 ===   diff pre/post → IDENTICAL
```

全ホスト・全項目でpre/postのsha256(ファイル内容+mode+owner:group+mtime、ディレクトリはツリー全体のstat集約)、`getent passwd`、`systemctl show`(ActiveState/SubState/UnitFileState/ActiveEnterTimestamp)、`getfacl`の出力が完全一致した。`/etc/ssl/certs/ca-certificates.crt`(update-ca-certificatesが再構築する証明書バンドル)のハッシュも不変であり、handlerが発火していないことをファイルシステム側からも裏付けた。

**フィンガープリント対象の設計根拠**: 各roleのdiffを読み、`template`/`copy`/`file`/`user`/`pip`/`apt`/`ansible.posix.acl`/`systemd`が触れる具体パス・ユニット名・ユーザー名を実装のdefaults変数から実値へ展開して列挙した(例: `recovery_io_install_dir=/opt/recovery-io`、`recovery_push_key_path=/etc/homelab-recovery/push-key`等、`roles/*/defaults/main.yml`から採取)。網羅性は「diffに現れた変更対象パスをすべて含める」ことで担保し、無関係パスの追加はしていない。

**pve1は対象外**: AC1の観測どおり、`--check`実行はpve1へ一度も接続しないため、pve1側のfingerprint取得(pre/post比較)も実施していない——実施しても`--check`実行の影響を観測する意味がない(そもそも触れていないことがAC1側の観測で確定している)。事前確認のUNREACHABLE以外、pve1に関する追加の状態確認は行っていない。

## AC4(lintが通る): 合格

```
$ bash scripts/check-tester-gate.sh
[tester-gate-lint] OK (46 playbooks)   rc=0
```

## AC5(母集団が減っている): 合格

```
$ grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l
6
$ grep -l "^# tester-gate: risk-accepted" playbooks/*.yml
playbooks/cloudkey_cert_deploy.yml
playbooks/cert_renew.yml
playbooks/codex_update_check.yml
playbooks/proxmox_backup_restore_verify.yml
playbooks/recovery_exec_setup.yml
playbooks/unifi_backup_fetch.yml
```

内訳は要件どおり: 非ゴール3本(`cloudkey_cert_deploy` / `proxmox_backup_restore_verify` / `unifi_backup_fetch`) + B-2(`recovery_exec_setup`、未着手) + バッチC(`cert_renew` / `codex_update_check`、未着手)。バッチB-1の8本は全て`check-mode-native`へ移っていることを確認した。8本すべての`# tester-gate:`行を個別に`grep`し、`check-mode-native`であることも確認した。

## 追加の静的確認(補助)

- `--syntax-check`: 対象8 playbookに加え`playbooks/cert_renew.yml`・`playbooks/cert_renew_quory.yml`(バッチC対象、影響が及んでいないことの確認)を含め全rc=0。
- R2(停止assert除去): `grep -l "has no --check dry-run" playbooks/{対象8}.yml` はヒットなし——旧`risk-accepted`の停止assertが8本とも除去済み。
- R3(`check_mode: false`カスケード除去): 対象8 playbook・対応roleを`grep`し、残存する`check_mode: false`は`roles/incident_sync/tasks/install_timer.yml`の`Query next scheduled run`(R5の正当なungate)1箇所のみであることを確認した。
- R6(`skip_notifications`案内の除去): 対象8 playbookに`skip_notifications`の文字列は残っていない。
- 独立レビューが主張した「`deploy_ca_trust.yml`変更は`cert_renew.yml`/`cert_renew_quory.yml`へ届かない」という主張を、`grep -n "tasks_from\|notify" playbooks/cert_renew*.yml roles/homelab_cert_renew/tasks/*.yml roles/homelab_cert_renew/handlers/main.yml`で独立に再確認した——両playbookは`tasks_from: deploy_ca_trust`を使わず、`update-ca-certificates`をnotifyするのは`deploy_ca_trust.yml`の2taskのみ(他の`issue.yml`等6ファイルはnotifyしていない)。**主張どおり漏れていないことをTester自身のgrepで確認した(実装者・レビュー担当の主張の追認ではなく独立実施)。**

## 未実施項目とその理由

- **AC2(通常実行の不変)**: 契約により実行していない(本番適用にあたるため)。到達可能な範囲での確認として、以下を静的に確認した——(1) 全8 playbookで新規`when: not ansible_check_mode`は既存の`when:`を置換せず`and`合成(唯一該当する`time_sync_ntp_reference/chrony_hosts.yml`の`Restart chrony`で確認)。通常実行では`ansible_check_mode`が常にFalseのため`not ansible_check_mode`は常にTrueとなり、ゲート追加前と到達可能性が変わらない。(2) role importの`check_mode: false`カスケード除去は、除去後もtask単位の`when:`ゲートで到達性が保たれているため通常実行への影響がない。これは実行して確かめた事実ではなく、diffの構造から導いた推測であることを明記する。
- **pve1へのAC1/AC3観測**: 上記のとおり構造的に接続されないため、pve1固有の状態比較は実施していない。pve1が起動している場合に`--check`が正しく動くかどうかは、この検証では確認できていない(未実施)。
- **B-2(`recovery_exec_setup`)・バッチC(`cert_renew`/`codex_update_check`)**: 依頼のscope外のため未実施。

## 残存リスク

1. **pve1の`--check`挙動は今回未検証。** 構造上(assertのみ・全taskゲート)問題は起きにくいと推測するが、pve1稼働時に実際に`--check`を通した実績はまだない。次回pve1稼働中の検証機会で確認する価値がある。
2. **AC2は構造的推論のみで、実行による確認ではない。** `when:`のand合成という設計自体は健全だが、実行時変数(`recovery_push_targets`のloop等)が絡む経路まで完全に静的解析で保証したわけではない。
3. **systemd_timersの`connection: local`実行は、今回ansyから行ったためquory自体には一切触れていない。** quory上で`--check`を実行した場合の挙動(quoryのローカルファイルシステムに対する動作)は本検証の対象に含まれていない——ただし対象diffの構造(全taskが`when: not ansible_check_mode`で同一にゲートされている)から見て、実行元が変わることで`--check`の安全性判定が変わる要素はないと考える。

以上、AC1・AC3・AC4・AC5は全て合格。作業ツリー・実ホストとも、`--check`実行前後で意図しない変更は確認されなかった。scratchpad上の一時ファイル(fingerprintスクリプト・snapshotログ)は`/tmp/claude-1000/.../scratchpad/`配下のみに存在し、作業ツリー外・削除不要(session-scoped scratchpadであり、リポジトリには一切影響しない)。`git add` / `git commit` / `git push`は行っていない。
