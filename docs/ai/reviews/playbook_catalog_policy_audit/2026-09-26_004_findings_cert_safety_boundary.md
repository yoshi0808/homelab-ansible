# Policy↔実装 照合: cert_renew / cert_renew_cloudkey / ansible_test_safety / execution_boundary

- 日付: 2026-09-26
- 対象Policy: `docs/ai/policies/cert_renew_policy.md`、`docs/ai/policies/cert_renew_cloudkey_policy.md`、`docs/ai/policies/ansible_test_safety_policy.md`、`docs/ai/policies/execution_boundary_policy.md`
- 方法: ファイルを読んだだけである(ansible / ssh / ネットワーク接続は行っていない)。横断規定(TS-014 / TS-030 / TS-031 / TS-036)は、`playbooks/*.yml` と `roles/*/tasks/*.yml` をYAMLとして走査した上で、該当した箇所を目で確かめた。`ansible_check_mode` の値の出どころは、ローカルにインストールされた ansible-core のソース(`/usr/lib/python3/dist-packages/ansible/utils/vars.py:213-235`)で確認した。CLIの `--check`(`context.CLIARGS['check']`)から作られるので、taskに付けた `check_mode: false` では変わらない。
- 件数: 指摘8件、未確認7件

## 指摘

### F1. CloudKeyの実行元: Policyは「quoryのみ・開発側からの経路は無い」と書くが、実装はansyでの実行を明示的に許している。さらにPolicyが根拠に挙げた機構は、この経路を塞いでいない(クラス1 / クラス4)

Policy側:
- `docs/ai/policies/cert_renew_cloudkey_policy.md:20` 「| 実行元 | quory のみ | quory（Semaphore Task Template）のみ |」
- `docs/ai/policies/cert_renew_cloudkey_policy.md:50-51` 「開発側（ansy）からの実行経路は無い。実行はquoryのSemaphore Task Templateのみである。実行境界の正本は`docs/ai/policies/execution_boundary_policy.md`（EXEC-005）である。」
- `docs/ai/policies/cert_renew_cloudkey_policy.md:46` 「通信先はAnsible管理対象ホスト（ann + SSH）ではなく**外部のCloudKey API**である。」

実装側:
- `playbooks/cloudkey_cert_deploy.yml:6-7` 「# 実行元: quory (本番 / Semaphore) または ansy (開発 / CLI)。」
- `playbooks/cloudkey_cert_deploy.yml:45-51` 「- name: Ensure this playbook is running on quory or ansy / assert: that: - ansible_facts['hostname'] in ['quory', 'ansy']」
- `roles/cloudkey_cert_deploy/tasks/issue.yml:4` 「# All material is generated locally on the executor (quory / ansy) as yoshi.」

Policy同士の関係:
- CCK-003は「経路が無い」の根拠にEXEC-005を挙げる。しかしEXEC-005が扱うのはSSH鍵である(`execution_boundary_policy.md:36` 「**鍵を用途で分け、`id_ann` は ansy から削除した**」)。一方CloudKeyへの通信はHTTPS APIで、CCK-003自身が`:46`でそう書いている。
- `execution_boundary_policy.md:53-54` では、「UniFi機器」は「保護対象」の行にあり、「到達手段が無い」の行(`pve1` / `pve2` / `authy` / `quory` / `sophos-fw` / `monnie`)には無い。つまりEXEC側は、UniFi機器を「届くが承認を要する相手」として扱っている。この表とCCK-003の「経路は無い」は両立しない。

補足:
- ansyからの実行を実際に止めうるのは、中間CA秘密鍵がansyに無いことである(`roles/homelab_cert_renew/defaults/main.yml:10-12` 「中間CAの秘密鍵は cert_renew_ca_host(quory)にしか置かない。ansy へ複製しない」)。ただしPolicyはこれを根拠に挙げていない。実装のassertも、この前提を落としたままansyを許している。

### F2. CloudKeyの配信検証: Policyが名指しする手段(`openssl s_client -showcerts`を収集用shellとして使うこと、`get_certificate`で指紋を取ること)が、実装に存在しない(クラス1 / クラス2)

Policy側:
- `docs/ai/policies/cert_renew_cloudkey_policy.md:171-173` 「リーフ指紋一致: `community.crypto.get_certificate` で配信リーフの指紋を取得し、アップロードAPIレスポンスの fingerprint と正規化照合」
- `docs/ai/policies/cert_renew_cloudkey_policy.md:174-177` 「3階層順序一致: `openssl s_client -showcerts` で配信チェーンを取得（収集のみ）し、証明書単位の順序付きリストに分割して…」
- `docs/ai/policies/cert_renew_cloudkey_policy.md:181-182` 「`openssl s_client` を使う shell は情報収集のみで、判定と fail 制御は Ansible tasks 側に置く」

実装側:
- `roles/cloudkey_cert_deploy/tasks/deploy.yml:110-111` 「NOTE: get_certificate does NOT expose a `fingerprints` key; the served leaf fingerprint is derived separately via x509_certificate_info below.」
- `roles/cloudkey_cert_deploy/tasks/deploy.yml:112-116` 「community.crypto.get_certificate: … get_certificate_chain: true」
- `roles/cloudkey_cert_deploy/tasks/deploy.yml:147-153` チェーンは `cloudkey_served.unverified_chain` から組み立てる。ロールのどこにも `openssl s_client` は無い(`roles/cloudkey_cert_deploy/tasks/*.yml` をgrepで確認した)。

影響: 判定がtask側にあるという原則は守られている。食い違っているのは収集手段の記述だけである。とはいえ、Policyの「指紋は`get_certificate`で取得する」は、実装コメントが「そのモジュールは指紋を返さない」と書いている事実と真っ向から矛盾する。

### F3. cert_renew_quory.yml は `--check` 下でも、CA秘密鍵をtmpfsへ展開し、鍵生成と署名を本実行する。同じtask fileを、cert_renew.yml は破壊的操作としてゲートしている(クラス1)

Policy側:
- `docs/ai/policies/ansible_test_safety_policy.md:23` 「`check-mode-native` | read-onlyな診断・検証部分は`--check`でも常に本実行し、実際の破壊的操作(またはそれに依存する後続処理)だけを`ansible_check_mode`でゲートする」
- `docs/ai/policies/ansible_test_safety_policy.md:88` 「read-onlyな診断taskには`check_mode: false`、破壊的task(またはそれをまとめたblock)には`when: not ansible_check_mode`と`tags: [destructive]`を付ける。」

実装側:
- `playbooks/cert_renew_quory.yml:12-15` 「# tester-gate: check-mode-native — prepare_ca / issue / cleanup は --check の有無にかかわらず常に本実行する(CA鍵のtmpfs展開・削除やCA側での鍵生成のみで…)」
- `playbooks/cert_renew_quory.yml:50-51`(`tasks_from: prepare_ca` + `check_mode: false`)、`:60`(`force_renew: true`)、`:66-67`(`tasks_from: issue` + `check_mode: false`)、`:87-88`(`tasks_from: cleanup` + `check_mode: false`)
- 同じtask fileを、もう一方の入口と役割側は破壊的と呼んでいる。
  - `playbooks/cert_renew.yml:28-31` 「鍵生成・証明書配布・サービス再起動(issue_apply / prepare_ca_apply / … / cleanup)はすべて `when: not ansible_check_mode` + `tags: [destructive]` でゲートする。」
  - `roles/homelab_cert_renew/tasks/prepare_ca_apply.yml:2-6` 「stages the CA cert/key onto tmpfs … so this destructive part can be gated」
  - `roles/homelab_cert_renew/tasks/issue_apply.yml:2-7` 「generates the EC key, CSR, and signs the certificate … so this destructive part can be gated」

影響: cert_renew_quory.yml に `--check` を付けると、中間CA秘密鍵のtmpfsへのコピーと、新しいリーフ鍵の生成・署名が実際に行われる(`force_renew: true` が固定なので毎回)。TS-005 / TS-014 の定義では、`--check` で本実行してよいのはread-onlyな部分だけである。同一のtask fileを、ある入口では「破壊的」、別の入口では「read-only扱いで常時本実行」としており、分類の根拠が1つに定まっていない。

### F4. cert_renew Policy が処理の所在として名指しするファイル(`prepare_ca.yml` / `issue.yml`)は、主入口の cert_renew.yml からは実行されない(クラス2)

Policy側:
- `docs/ai/policies/cert_renew_policy.md:131` 「prepare_ca.yml の実行時に home_tls_ca.crt の残存日数を確認する。」
- `docs/ai/policies/cert_renew_policy.md:242` 「生成タイミング: issue.yml の署名タスク直後に quory（tmpfs）上で cat 連結して作成する。」

実装側:
- `playbooks/cert_renew.yml:66`(`tasks_from: prepare_ca_check`)、`:71`(`tasks_from: prepare_ca_apply`)、`:85` / `:94`(`issue_check` / `issue_apply`)。`prepare_ca.yml` / `issue.yml` は使っていない。
- 実処理の所在は次のとおりである。残存日数の確認は `roles/homelab_cert_renew/tasks/prepare_ca_check.yml:42-70`、fullchainの連結は `roles/homelab_cert_renew/tasks/issue_apply.yml:77-84` にある。
- `roles/homelab_cert_renew/tasks/prepare_ca.yml:2-9` と `issue.yml:2-10` は、「cert_renew_quory.yml と main.yml のために残した」ラッパーだと自ら書いている。

影響: 挙動は同じである。ただしPolicyの参照を辿ると、主入口では実行されないラッパーへ着地する。

### F5. TS-036違反: role内のファイルに、tester-gateの分類名と条件の理由文が複製されている(クラス1)

Policy側:
- `docs/ai/policies/ansible_test_safety_policy.md:153` 「roleやtask fileへ`tester-gate`の分類名と理由を複製しない。**参照に留める**…TS-009条件1/条件2の説明文を複製しない。…分類・理由の複製が既に無いか確認する方法は`grep -rn "^# tester-gate:" roles/`。」

実装側(`roles/semaphore_templates/defaults/main.yml`):
- `:131-133` / `:138-141` 「apt-get updateでパッケージリストを更新するため厳密にはread-onlyではないが、パッケージ状態は変わらない(tester-gate: safe-readonly)。」
- `:216-218` / `:223-225` 「復元先VMIDは999に固定(assertで他の値を拒否)、NIC切断で起動し判定後に破棄する。既存VMには影響しない(tester-gate: risk-accepted)」。これはTS-009条件1(実害なし)の理由文にあたる。
- `:335` 「(tester-gate: role-guarded、TS-005。…)」
- `:365-368` 「(tester-gate: role-guarded — 副作用はSlack通知のみで、common_slackの抑止guard〔TS-031〕で止まる。…)」
- 境界例: `roles/ubuntu_vm_full_upgrade/tasks/main.yml:18-19` 「tester-gate: check-mode-native, see the playbook header」。分類名だけの複製である。

補足: TS-036が挙げる確認方法(`grep -rn "^# tester-gate:" roles/`)は、行頭の完全なマーカー形式しか拾わない。上に挙げた行内埋め込みの複製は、この方法では検出されない。同じ役割にある `playbooks/proxmox_backup_restore_verify.yml` ヘッダが既に書き換わった場合、この`class_reason`は機械検査の外で古くなる。

### F6. TS-018: sophos_trim(dry-run-aware)の2値通知に、check-mode(dry-run)の分岐が無い(クラス1)

Policy側:
- `docs/ai/policies/ansible_test_safety_policy.md:107` 「2値分岐(`ok` / `error`等)の通知・レポートには、plan-only / check-modeの分岐を必ず含める。…`--check`実行時は結果分岐にもcheck_modeを考慮する。」

実装側:
- `roles/sophos_trim/tasks/main.yml:39-51`: `trim_status` は `'SUCCESS'` / `'FAILED'` の2値で、`ansible_check_mode` を見ていない。
- `roles/sophos_trim/tasks/main.yml:53-58` 「slack_status: "{{ 'error' if trim_status == 'FAILED' else 'ok' }}" / slack_title: "[Sophos Trim] {{ trim_status }} - {{ inventory_hostname }}"」

影響: `--check`(fstrim `--dry-run`)が成功すると `[Sophos Trim] SUCCESS` / `ok` になる。notify.ymlが送信を抑止するので、この結果はdebug出力に出るだけである。とはいえ、trimを実行していない実行と実際のtrim成功を、出力から区別できない。

### F7. TS-005は `safe-readonly` を「完全read-only」と定義するが、`safe-readonly` と宣言したplaybookに、対象ホストの状態を変える `apt-get update` が含まれる。TS-027はこれを容認するようにも読め、同じPolicy内の2条が両立していない(クラス1 / クラス4)

Policy側:
- `docs/ai/policies/ansible_test_safety_policy.md:20` 「`safe-readonly` | 完全read-only(収集・観測のみ)。ゲート不要、常に本実行してよい」
- `docs/ai/policies/ansible_test_safety_policy.md:156` 「`safe-readonly`であっても、冪等なscript配置、localhostへのreport保存、条件付きSlack通知などの副作用を持つ場合がある。」

実装側:
- `playbooks/proxmox_patch_dryrun.yml:2` 「# tester-gate: safe-readonly — 実patchなし（apt-get update/check、-s dist-upgrade）…」
- `roles/semaphore_templates/defaults/main.yml:138-141` 「厳密にはread-onlyではないが…Policy §7「分類名から副作用ゼロを推定しない」の範囲内」。実装側は、TS-027を根拠にこの状態を受け入れている。

影響: TS-027が例として挙げる副作用は、いずれもcontroller側か通知である。pveノードのパッケージ索引を更新する操作がその「など」に含まれるかは、Policyから読み取れない。TS-005の「完全read-only」と、TS-027の容認範囲のどちらかを揃える必要がある。

### F8. TS-005は `role-guarded` を「副作用がSlack通知のみで、notify.ymlの抑止guardで止まる」と定義するが、notify.yml自体が抑止判定より前に証跡を書き込む(クラス1)

Policy側:
- `docs/ai/policies/ansible_test_safety_policy.md:21` 「`role-guarded` | 副作用がSlack通知のみで、`roles/common_slack/tasks/notify.yml`の抑止guard(TS-031)で止まる」

実装側:
- `roles/common_slack/tasks/notify.yml:44-47`: `capture.yml` のincludeを、抑止判定(`:59-83`)より前に無条件で行う。
- `roles/common_slack/tasks/capture.yml:246-247` 「when: "(capture_collector_marker | default('/etc/homelab-recovery/incident-capture.json')) is exists"」、`:305-310` でspoolレコードを `ansible.builtin.copy` で書く。

影響: collectorが配備されたcontroller(quory)では、`role-guarded` のplaybook(`recovery_probe_notify.yml` / `semaphore_update_check.yml` / `syslog_weekly_digest.yml` / `worktree_sync_notify.yml`)を `-e skip_notifications=true` で本実行しても、Slack以外の副作用(spoolへの書き込み)が起きる。抑止guardでは止まらない。`--check` 下では、`file` / `copy` がシミュレーションになるので書かれない(`capture.yml:183-185`)。

## 未確認

1. **CERT-023「pve1 / pve2 が到達不能なら終了コード0」**(`cert_renew_policy.md:167`)。実装は `ignore_unreachable: true` を付けたpingと `meta: end_host` の組である(`playbooks/cert_renew.yml:119-141`)。ただし、この組でPLAY RECAPの `unreachable` が計上されずrc=0になるかは、実行しないと確かめられない。実装コメントは、decoyで実測したと書いている。
2. **check_mode: false を継承した状態でcapture.ymlが書き込むか**。`check_mode: false` のblockの中からnotify.ymlをincludeしている箇所は次のとおりである。`roles/recovery_ha_failover/tasks/main.yml:15-16` → `:210`、`roles/recovery_service_restart/tasks/main.yml:14` → `:170`、`roles/recovery_vm_reboot/tasks/main.yml:15` → `:242`、`roles/ubuntu_vm_full_upgrade/tasks/main.yml:81-93` → `:101` / `:133` / `:338`。TS-013(`ansible_test_safety_policy.md:69`)によれば `check_mode: false` はinclude先へ伝わるので、`--check` 下でも capture.yml の `copy` が本実行されうる。これは `capture.yml:156-157`「always false in practice because this file never sets check_mode: false」の前提と食い違う。Slackへの送信そのものは、`ansible_check_mode` がCLI由来なので抑止される(ansible-coreのソースで確認済み)。書き込みが実際に起きるかは、実行と、quoryにcollectorのmarkerがあるかどうかに依存する。
3. **`scripts/cloudkey_cert_deploy.sh`**(依頼が対象とするplaybook / roleの範囲外)。このスクリプトは、検証の結果に関係なく旧証明書を削除する(`:148-152`で不一致を警告するだけで、`:155-163`へ進む)。削除候補(`:120`)にはactiveなuploaded証明書も含む。CCK-010 / CCK-011(`cert_renew_cloudkey_policy.md:153-164`)と正反対の挙動である。ヘッダ(`:8-11`)は「参考スクリプト、本番運用はplaybook」と書くが、CCK-003の「実行経路は無い」がこのCLI経路を含むのかは、Policyから判断できない。
4. **EXEC-005「`monitoring_servers` を対象にする playbook 12本」**(`execution_boundary_policy.md:38`)。`hosts:` に `monitoring_servers` を含むplaybookは7本、monnieへ届く(`monnie` の名指しと `target_hosts` の既定値を含む)ものは13本数えられ、「12本」がどの集合を指すかを特定できなかった。数え方にかかわらず、該当するplaybookはすべて `semaphore_templates_catalog` に載っていた。
5. **EXEC-011「`sandbox` … 他に何もこのホストへ流さない」**(`execution_boundary_policy.md:58`)。quoryのSemaphoreには、sandboxを対象とするtemplateが3本ある(`roles/semaphore_templates/defaults/main.yml:379-399`)。`recovery_probe_sandbox_setup.yml` と `sandbox_auto_patch.yml` もある。EXEC-052(`:120`)はこれらを前提にしているので、「他に」が何を除いた残りを指すのかによって、食い違いになるかどうかが変わる。
6. **CERT-006 / CCK-022(quoryにルートCA秘密鍵が無いこと)と EXEC-003(ansyにある鍵ファイル)**。いずれもリポジトリの外にある事実であり、ファイルを読むだけでは確かめられない。
7. **cert_renew_quory.yml ヘッダ `:9-10`「通知: 証明書更新結果をメールで通知する」**。実装はSlack通知で(`:118-135`)、CERT-011(`cert_renew_policy.md:309`「完了Slack通知を送る」)とも一致している。Policyと実装は食い違っていないので指摘には入れていない。ヘッダコメントだけが古い。

## 読んだ範囲

- 共通: `AGENTS.md`、`docs/ai/core.md`
- Policy: `docs/ai/policies/cert_renew_policy.md`、`docs/ai/policies/cert_renew_cloudkey_policy.md`、`docs/ai/policies/ansible_test_safety_policy.md`、`docs/ai/policies/execution_boundary_policy.md`(参照先の存在だけを確かめたもの: `proxmox_operations_policy.md` SB-095、`unifi_backup_fetch_policy.md` UNIFI-007、`docs/ai/context/system/autonomous-recovery.md`「検証用target」、`skills/ansible-implementation-style/SKILL.md` の見出し)
- playbook(全文): `cert_renew.yml`、`cert_renew_quory.yml`、`cloudkey_cert_deploy.yml`、`ca_trust_deploy.yml`、`test_ca_env.yml`、`sophos_trim.yml`、`semaphore_db_backup.yml`(1-240行)
- playbook(部分): `time_sync_check.yml`(ヘッダ)、`proxmox_patch_dryrun.yml`(ヘッダ)、`proxmox_backup_restore_verify.yml` / `unifi_backup_fetch.yml`(play構成とassert)、`sandbox_auto_patch.yml`(ヘッダ)、`proxmox_patch_weekly_full.yml`(import_playbook箇所)。全playbookについて `# tester-gate:` 行を読み、YAMLとして走査した(notifyのincludeの位置、`check_mode: false` の継承、role import)
- role: `roles/homelab_cert_renew/`(tasks全12本、defaults、handlers、templates)、`roles/cloudkey_cert_deploy/`(tasks 3本、defaults)、`roles/common_slack/tasks/notify.yml`、`roles/common_slack/tasks/capture.yml`(1-200行と各taskの行)、`roles/sophos_trim/tasks/main.yml`、`roles/semaphore_templates/defaults/main.yml`(1-70、125-260、328-446、555-575、700-830、1075-1108行)、`roles/systemd_timers/defaults/main.yml`(cert-renew-quory)、`roles/systemd_timers/templates/ansible-timer.timer.j2`(Persistent)、`roles/deployment_drift_check/defaults/main.yml`(authorized_keys)、`roles/proxmox_exec_node/tasks/main.yml` / `roles/proxmox_reachable_nodes/tasks/main.yml`(使っているmoduleの一覧)、`roles/recovery_ha_failover/tasks/main.yml`(1-30、195-225行)、`roles/ubuntu_vm_full_upgrade/tasks/main.yml`(10-25、75-105行)、`roles/time_sync_check/tasks/main.yml`(sophos分岐)
- inventory: `inventories/homelab/hosts.yml`、`inventories/homelab/group_vars/*.yml`(鍵の参照行)、`inventories/homelab/group_vars/sophos.yml`
- scripts: `scripts/check-tester-gate.sh`、`scripts/safe-ansible-check.sh`、`scripts/git-pre-commit-check.sh`(100-140行)、`scripts/cloudkey_cert_deploy.sh`
- ansible-core: `/usr/lib/python3/dist-packages/ansible/utils/vars.py`(`load_options_vars`)、`playbook/play_context.py`(`update_vars`)
