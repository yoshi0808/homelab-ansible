# test_result: Round 2 バッチB-2 — `recovery_exec_setup` の `check-mode-native` 変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md`(訂正/決着注記反映後の本文)§6 AC1・AC3・AC4・AC5
実装記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_013_round2_batchB2_implement.md`(§6差し戻し対応含む)
レビュー記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_014_round2_batchB2_review.md`(Approve)

## 対象パス

`playbooks/recovery_exec_setup.yml`、`roles/recovery_exec/tasks/main.yml`、`roles/recovery_exec/tasks/target_setup.yml`。バッチC(`cert_renew` / `codex_update_check`)は対象外で一切実行していない。

## 実行環境

- 実行元: ansy(このTester sandbox)。`ANSIBLE_LOCAL_TEMP=/tmp/ansible-local`、`ANSIBLE_REMOTE_TEMP='/tmp/ansible-remote-$USER'`(skills/test-strategy/SKILL.md準拠)。
- 触れた実ホスト: ansy, quory(playbookの`--check`実行対象)。authy, monnie, pve2(`--check`実行前後のread-only ad-hoc状態確認、`-m ping`/`-m shell`)。pve1は接続試行のみ(到達不能、下記参照)。
- `roles/recovery_exec/tasks/target_setup.yml`を無効化せず(`-e recovery_exec_setup_targets=false`を渡さず)有効なまま`--check`を実行した。承認済みscopeどおり。
- 対象実装ファイルはTesterとして一切変更していない。`git status`は作業開始前と同一(4ファイルmodified + 2ファイルuntracked、いずれもImplementer/Reviewerの成果物)。`git add` / `git commit` / `git push` は行っていない。

## 事前確認: ホスト到達性

`ansible all -i inventories/homelab/hosts.yml -m ping --limit "authy,monnie,pve1,pve2,quory,ansy"` を実行し、**pve1のみ`UNREACHABLE`**(`ssh: connect to host pve1.internal port 22: No route to host`)、他(authy/monnie/pve2/quory/ansy)は`pong`を確認した。承認済み前提どおり、pve1停止は異常ではなく想定内の観測として記録する。

## AC1(dry-runとして成立する): 合格

`scripts/safe-ansible-check.sh playbooks/recovery_exec_setup.yml --check --diff -l ansy,quory` を実行した(`hosts: dev_nodes:control_nodes` = ansy + quory を明示指定し、target_setup.yml の`inventory_hostname == 'quory'`ゲートが通る状態で実行)。

結果: **終了コード0**。

```
PLAY RECAP
ansy   : ok=3  changed=0  unreachable=0  failed=0  skipped=31  rescued=0  ignored=0
quory  : ok=4  changed=0  unreachable=0  failed=0  skipped=48  rescued=0  ignored=0
```

- `ok`になったtaskはGathering Facts、`[migration] tester_mode is deprecated...`assert、`Assert quory is part of this run when target distribution is enabled`assert(両ホストとも)、およびquoryのみ`Setup recovery-exec on target nodes (quory only)`(`include_tasks`自体の評価)の計3〜4件で、いずれもrequirementの想定どおり無変更のまま維持されているtaskである。
- **破壊的taskはすべて`skipping`に現れた。** main.yml側30task、target_setup.yml側18task(block化した鍵生成4taskは1blockとして・非block14taskは個別に)、計48taskがゲートどおりskipped。ログを`grep -n "^TASK\|ok:\|changed:\|failed:\|fatal:"`で走査し、`ok:`以外の完了ステータスが現れないことを確認した。
- **`delegate_to`付き全taskがskipされたことの確認。** `target_setup.yml`の18task(authy/monnie/pve1/pve2への`delegate_to`を持つ)はすべて`skipping: [quory] => (item=...)`の形でログに現れ、delegate先(authy/monnie/pve1/pve2)へのSSH接続自体が発生していないことを、後述のfingerprint比較(不変)と合わせて確認した。**pve1(接続不能)であっても、この`--check`実行はpve1への接続を試みる前にtaskがskipされるため、`RUN_UNREACHABLE_HOSTS`(rc=4)は発生しなかった** — pve1のUNREACHABLE状態と本実行のrc=0は矛盾ではなく、構造的に接続していないことの帰結である(batchB1と同型の観測)。
- **block単位ゲートと個別taskゲートの両方で、破壊的taskが`skipped`に現れることの確認。** main.ymlの`Generate and lock down recovery-exec SSH keys (destructive; TS-015 chain)`block(鍵生成3task+chmod1task)はblock全体が`skipping`として一括で現れ、target_setup.ymlの個別ゲート14task(slurp3・authorized_keys配布2・known_hosts関連3を含む)もそれぞれ独立に`skipping`として現れた。両方式とも`--check`下で破壊的操作を一切実行しないことをログで確認した。
- **handler非発火の確認。** `roles/recovery_exec/`に`handlers/`は存在しない(`find roles/recovery_exec -iname '*handler*'`で再確認、該当なし)。ログにも`RUNNING HANDLER`行は一度も出現しない(`grep -c "RUNNING HANDLER"` = 0)。role構造上notify対象が無いため、handler非発火は構造的に保証されている。

## AC3(部分適用が起きない): 合格

`--check`実行の**前後**でホスト状態を比較した。対象は承認済みscopeが要求する「各ターゲットの`authorized_keys`」を含む、recovery-exec関連の全体像(ユーザー/グループ存在、`.ssh`配下の全ファイルのmtime・size・owner:group・mode・md5、sudoers.d配下、配布済みスクリプト一覧)。

対象ホスト: ansy, quory, authy, monnie, pve2(pve1は到達不能のため対象外、下記参照)。

```
$ diff pre_snapshot.txt post_snapshot.txt
(差分なし、diff exit code 0)
```

- 5ホストすべてで`--check`実行前後のスナップショットが完全一致した。
- **authorized_keysの個別確認**: authy(md5=0ca87773...、mtime 1783723332)、monnie(md5=0ca87773...、mtime 1783723333)、pve2(md5=4bf1a061...、mtime 1783723338)、quory(md5=e69c60b0...、mtime 1783026470)のいずれも、`--check`実行前後でmd5・mtime・owner:group・modeが完全一致した。
- **pve1は対象外**: AC1の観測どおり、`--check`実行はpve1へ一度も接続しない(delegate先task自体がゲートでskipされる)ため、pve1側のスナップショット取得(pre/post比較)は実施していない。到達性確認(`-m ping`)で`UNREACHABLE`だったこと以外、pve1に関する追加の状態確認は行っていない。
- **本番適用状態が生じていないことの確認**: 「いずれかのホスト(quory/ansy/authy/monnie/pve1/pve2)に、対象playbookの適用結果が生じている状態」に到達していないことを、上記の完全一致するdiffで確認した。`changed=0`(AC1のPLAY RECAP)とホスト側のファイルシステム比較(AC3)の両方向から、部分適用が起きていないことを確認した——片方向だけでは機構が効いた証明にならないという指示に沿い、実行結果の申告(changed=0)とホスト側の実測(diff一致)を独立に突き合わせた。

## AC4(lintが通る): 合格

```
$ bash scripts/check-tester-gate.sh
[tester-gate-lint] OK (46 playbooks)
rc=0
```

## AC5(母集団が減っている): 合格

```
$ grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l
5
$ grep -l "^# tester-gate: risk-accepted" playbooks/*.yml
playbooks/codex_update_check.yml
playbooks/cloudkey_cert_deploy.yml
playbooks/cert_renew.yml
playbooks/unifi_backup_fetch.yml
playbooks/proxmox_backup_restore_verify.yml
```

`playbooks/recovery_exec_setup.yml`は`risk-accepted`のリストから外れており、ヘッダのマーカーも`# tester-gate: check-mode-native`に変わっていることを確認した。内訳は要件どおり: 非ゴール3本(`cloudkey_cert_deploy` / `proxmox_backup_restore_verify` / `unifi_backup_fetch`)+バッチC未着手2本(`cert_renew` / `codex_update_check`)= 5本。バッチB-1完了時点の6本から、本バッチ(`recovery_exec_setup`1本)の変換で5本へ、要件どおり1本減少した。

## 未実施項目とその理由

- **AC2(通常実行の不変)**: 契約により実行していない(本番適用にあたるため、依頼文で明示的に除外)。「到達してはいけない状態」の指示に従い、`--check`なしでの起動は一度も行っていない。
- **pve1へのAC1/AC3観測**: 構造的に接続されないため実施していない(上記のとおり)。pve1が稼働している場合に本playbookの`--check`が実際にpve1へ到達した際の挙動(SSH接続そのものの成否含む)は、本検証では確認できていない。ただしこれはmain.ymlの`quory`ハードコードguardおよびtarget_setup.ymlの全taskゲートという構造上、pve1への接続試行自体が`--check`下で常に起きない設計であり、pve1稼働の有無が本playbookの`--check`安全性判定に影響する余地は構造的に無いと考える(推測であり実測ではない)。
- **block単位ゲートと個別taskゲートの「意図どおりか」という設計判断そのものの当否**: 実装記録§6・レビュー記録が既に指摘・是正・Approve済みの論点(TS-015の字義解釈)であり、本test_resultでは「両方式とも`--check`下でskippedに現れる」という実行結果の事実確認に留め、設計判断の当否そのものの再評価は行っていない(Coordinator/Reviewerの領域として先行記録に委ねる)。

## 残存リスク

1. **pve1稼働時の実挙動は今回も未検証。** batchB1に続き、pve1が停止中だったため、pve1が実際に`--check`実行の対象として接続を試みられた場合の挙動(guardの効き方含む)はまだ実地で確認できていない。次回pve1稼働中の検証機会で確認する価値がある。
2. **AC2は今回も未実施。** `when: not ansible_check_mode`のand合成が既存`when:`を破壊していないことは実装記録・レビュー記録がdiffの構造から確認済みだが、Testerとして通常実行を走らせての確認はしていない。
3. **2026-07-08インシデントの再発防止機構(quoryハードコードguard)自体は、本検証で「無変更であること」をgrep確認したのみで、guardが実際に機能する境界条件(例: `-l ansy`単独実行時にassertで停止すること)は`--check`実行では起こらない経路のため、本バッチのTester検証では再現していない。** これはguardの機構自体が本バッチの変更対象外(無変更)であり、Round1以前の検証範囲であるため、新規リスクではなく既存の確認範囲の外にあることの明示として記録する。

以上、AC1・AC3・AC4・AC5は全て合格。作業ツリー・実ホストとも、`--check`実行前後で意図しない変更は確認されなかった。scratchpad上の一時ファイル(snapshotログ・実行ログ)は`/tmp/claude-1000/.../scratchpad/b2test/`配下のみに存在し、作業ツリー外・リポジトリには一切影響しない。`git add` / `git commit` / `git push`は行っていない。
