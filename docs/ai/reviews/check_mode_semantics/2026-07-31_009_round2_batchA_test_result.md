# test_result: Round 2 バッチA — `check-mode-native` 変換

日付: 2026-07-31
契約: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md`(§5 R1〜R6、§6 AC1〜AC5。AC1/AC2は訂正後の本文で判定)
実装記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_007_round2_batchA_implement.md`
レビュー記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_008_round2_batchA_review.md`

対象パス:
- `playbooks/incident_capture_setup.yml`(role: `roles/incident_capture`)
- `playbooks/incident_investigate_setup.yml`(role: `roles/incident_investigate`)
- `playbooks/recovery_probe_setup.yml`(role: `roles/recovery_probe`。`roles/recovery_mute`のinclude_role呼び出しも含む)

触れたホスト: `quory`(3playbookとも対象)、`ansy`(`recovery_probe_setup.yml`のみ、`hosts: dev_nodes:control_nodes`のため)。いずれもTester Role・Policy上の保護対象ホストではない。Proxmox/Sophos/UniFiには触れていない。

## AC別の合否

### AC1(dry-runとして成立する) — 合格

`scripts/safe-ansible-check.sh <playbook> --check --diff` で3本とも実行した(TS-024どおりwrapper経由)。

| playbook | 対象host | rc | ok | changed | skipped | unreachable/failed |
|---|---|---|---|---|---|---|
| `incident_capture_setup.yml` | quory | 0 | 2 | 0 | 15 | 0/0 |
| `incident_investigate_setup.yml` | quory | 0 | 2 | 0 | 8 | 0/0 |
| `recovery_probe_setup.yml` | ansy | 0 | 6 | 0 | 10 | 0/0 |
| `recovery_probe_setup.yml` | quory | 0 | 6 | 0 | 10 | 0/0 |

3本とも終了コード0で完走し、破壊的task(`Deploy homelab-mute CLI`のinclude_role丸ごと、`recovery_probe`の`Deploy, activate, and verify recovery-probe`named block丸ごと、`incident_capture`/`incident_investigate`の全破壊的task)が`skipping`として現れた。`recovery_probe`のread-only診断task(`Assert recovery_probe_pve_hosts...`、`Check whether recovery-probe is already running`、`Record whether recovery-probe was running before this deploy`)は`--check`下でも`ok`のまま本実行された(check-mode-nativeの設計どおり)。AC1訂正後の文言(`changed`の件数はAC判定材料にしない)に従い、`changed=0`であること自体は不合格理由にしていない。

### AC2(通常実行の不変) — 実行せず、静的検証のみ

契約により`--check`なしの実行はAPPLY(本番適用)でありTester役は行わない。実行以外の方法で以下を確認した。

- 3role・3playbook全ての追加`when:`条件を`git diff`で読み、いずれも「既存条件を置き換える」形ではなく「既存条件へ`not ansible_check_mode`をANDで追加する」形になっていることを確認した(リスト形式`when: [not ansible_check_mode, 既存条件]`、または複合Jinja式`not ansible_check_mode and (既存条件)`のいずれか)。通常実行では`ansible_check_mode`は常に`False`のため`not ansible_check_mode`は常に`True`となり、論理積の結果は元の条件と同値になる。
- 新規に条件が追加されたことで通常実行時に実行対象から外れるtaskが無いことを、全追加箇所(`roles/incident_capture/tasks/main.yml`15箇所、`roles/incident_investigate/tasks/main.yml`8箇所、`roles/recovery_probe/tasks/main.yml`4箇所+handler1箇所、`playbooks/recovery_probe_setup.yml`1箇所)について1件ずつ確認した。
- `roles/recovery_probe/handlers/main.yml`の`Restart recovery-probe`も同様に、既存条件`recovery_probe_service_enabled | bool or recovery_probe_running_before | default(false) | bool`全体を括弧で囲んだ上で`not ansible_check_mode and (...)`としており、既存条件を壊していないことを確認した。

**未実施と理由:** 実際に`--check`なしで起動し「変換前と同じ結果になる」ことを実行して確かめることはできていない(契約上の明示的禁止)。上記は差分の静的読解による論理的検証であり、実行による検証の代替であって同等ではない。

### AC3(部分適用が起きない) — 合格

`--check`実行の前後でホスト状態を比較した。対象は次の3群。

1. **quory**: `reports/incidents/`・`_spool/`のACL(`getfacl -p`)、`reports/incidents/_investigations/`ディレクトリ、`/etc/homelab-recovery/`配下3ファイル、`/etc/systemd/system/`のincident-capture/investigate関連4unit、`recovery-probe.service`・`recovery-probe.py`のmd5、`homelab-incident-capture.timer`/`homelab-incident-investigate.timer`のenable/active状態、`recovery-probe`の`ExecMainStartTimestamp`。
2. **ansy**: `/etc/homelab-recovery/recovery-probe.json`・`/usr/local/sbin/recovery-probe.py`・`/etc/systemd/system/recovery-probe.service`のmd5、`recovery-probe`のenable/active状態と`ExecMainStartTimestamp`、`/usr/local/bin/homelab-mute`、`dnsutils`のdpkg状態、`/var/lib/homelab-recovery/probe/`配下。

結果: **前後で差分なし。** md5は全ファイルで完全一致、`recovery-probe`の`ExecMainStartTimestamp`はquory・ansyともに実行前後で同一時刻のまま(quory: `Fri 2026-07-31 06:16:37 JST`、ansyは元々`inactive`のまま変化なし)、`dnsutils`はansyで`--check`前後とも未インストール(`un`)のまま、timerのenabled/activeも変化なし。quoryの`reports/incidents/`直下では`semaphore-*`/`spool-*`という既存の運用中プロセス(recovery-exec、本バッチと無関係の別自動化)が生成したディレクトリの増減が見られたが、これは`--check`実行前から存在していたエントリであり、比較対象からは意図的に除外した(件数・タイムスタンプとも本テストの実行時刻と無関係)。

**handlerが`--check`中に発火しないこと**: 3本の実行ログいずれにも`RUNNING HANDLER`が一度も出現しなかった(`grep -n "RUNNING HANDLER"`で確認、0件)。`recovery-probe`の`ExecMainStartTimestamp`が前後不変であることも、handler(`Restart recovery-probe`)が実restartを行っていないことの直接証拠になる。

**block単位ゲート/task単位ゲートの両方で破壊的taskがskippedに現れること**: `recovery_probe`の`Deploy, activate, and verify recovery-probe (destructive; TS-015 chain)`はblock全体が1回の`skipping`(配下の全taskがそのまま展開されず消える)として現れ、`incident_capture`/`incident_investigate`はtask単位で個々に`skipping`が現れた。両パターンとも実行ログで確認済み。

### AC4(lintが通る) — 合格

`bash scripts/check-tester-gate.sh` を実行し `[tester-gate-lint] OK (46 playbooks)`(rc=0)を確認した。3playbookとも`ansible-playbook <playbook> --syntax-check`が通ることも確認した。

### AC5(母集団が減っている) — 合格

`grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l` は **14**(Round 1完了時の17から、Round 2バッチAで3本減)。バッチA対象3本(`incident_capture_setup.yml`/`incident_investigate_setup.yml`/`recovery_probe_setup.yml`)は`grep`で`check-mode-native`に変わっていることを確認した。最終目標の3本(非ゴール3本)にはバッチB・C完了が必要で、本バッチの検証範囲外。

## 観測できなかった項目とその理由

1. **AC2の実行確認**: 契約により`--check`なし実行はAPPLYでありTester役が行わないため、実行しての確認は一切していない。上記の静的差分読解で代替した。実装記録・レビュー記録も同様に実行していない旨を明記しており、この案件を通じてAC2は誰も実行で確認していない状態にある(3工程共通の制約)。
2. **`ansible.posix.acl`のネイティブcheck_mode simulateの精度**: 本バッチの設計は破壊的taskを丸ごと`skipping`にするため、simulate精度に依存しない。実装記録が残した未解決事項と同じ理由で今回も未検証(検証しても本バッチの合否には影響しない設計のため優先度を上げなかった)。
3. **`recovery_probe_setup.yml`のオーケストレータ側`hosts: dev_nodes:control_nodes`に含まれる他ホストの有無**: インベントリ確認では`dev_nodes`=ansy、`control_nodes`=quoryの2ホストのみであることを`ansible-inventory`で確認済みで、他に対象ホストは存在しない。未実施ではなく確認済み。

## 残存リスク

- AC2は本案件全体(Implementer/Reviewer/Tester)を通じて一度も実行による確認がされていない。静的読解による論理的同値性の確認に留まる。将来この設計へ変更を加える際、既存`when:`条件へのAND追加という前提が崩れる編集(例: 既存条件ごと上書きする形の変更)が入ると、AC2は静かに壊れうる。次回のレビューまたはメンテナンス時に、通常実行での実地確認(risk-accepted相当のholdoutではなく、限定対象への実適用が許可された機会)を一度は行うことを推奨する。
- `reports/incidents/`直下は`recovery-exec`による無関係の運用ジョブ(semaphore実行記録・spool)が本テスト実行中も増減しており、この場所を将来同種の前後比較に使う場合は、本テストと同様に無関係エントリの除外基準を明示する必要がある。
- バッチB・C未着手のため、AC5の最終値(3本)はまだ達成されていない。本バッチはその一部(17→14)の検証に留まる。

## 実行したコマンド一覧(検証目的、書込みなし)

```
ansible-playbook playbooks/incident_capture_setup.yml --syntax-check
ansible-playbook playbooks/incident_investigate_setup.yml --syntax-check
ansible-playbook playbooks/recovery_probe_setup.yml --syntax-check
bash scripts/check-tester-gate.sh
grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l
grep -l "^# tester-gate: risk-accepted" playbooks/*.yml
ansible-inventory --list -y
ansible quory -m shell -a '<read-only ls/getfacl/systemctl/md5sum/systemctl show>' -b --become-user=root   # 前後2回
ansible ansy   -m shell -a '<同上>' -b --become-user=root                                                    # 前後2回
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ANSIBLE_REMOTE_TEMP='/tmp/ansible-remote-$USER' \
  scripts/safe-ansible-check.sh playbooks/incident_capture_setup.yml -l quory --check --diff
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ANSIBLE_REMOTE_TEMP='/tmp/ansible-remote-$USER' \
  scripts/safe-ansible-check.sh playbooks/incident_investigate_setup.yml -l quory --check --diff
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ANSIBLE_REMOTE_TEMP='/tmp/ansible-remote-$USER' \
  scripts/safe-ansible-check.sh playbooks/recovery_probe_setup.yml -l quory,ansy --check --diff
```

いずれも`--check`付き(`safe-ansible-check.sh`経由)またはread-onlyのad-hocコマンドのみで、`--check`なしでの対象playbook起動、`git add`/`git commit`/`git push`、対象実装ファイルの変更は一切行っていない。検証用に`/tmp`のscratchpad配下へ実行ログ・状態スナップショットのテキストファイルを一時的に作成したが、検証完了後にすべて削除し、リポジトリ作業ツリー外に何も残していないことを確認した(同scratchpad配下に前工程由来と見られる`ansible_connection: local`/実host名なしのdecoy playbook 2件も見つかったため、あわせて削除した)。
