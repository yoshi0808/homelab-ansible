# implement: Round 2 バッチB-1 — `check-mode-native` への変換

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §4 バッチB-1、§5 R1〜R6、§6 AC1〜AC5
テンプレート: `docs/ai/reviews/check_mode_semantics/2026-07-31_007_round2_batchA_implement.md`(手順の正本。本記録は差異と適用結果のみ書く)

対象8 playbook: `recovery_io_setup` / `recovery_push_setup` / `recovery_push_drill_setup` / `systemd_timers` / `incident_sync_timer` / `time_sync_ntp_reference` / `ca_trust_deploy` / `incident_inspect_setup`

## 1. 変更ファイル

- `playbooks/recovery_io_setup.yml`、`roles/recovery_io/tasks/main.yml`、`roles/recovery_io/handlers/main.yml`
- `playbooks/recovery_push_setup.yml`、`playbooks/recovery_push_drill_setup.yml`、`roles/recovery_push/tasks/main.yml`、`roles/recovery_push/tasks/sender_setup.yml`、`roles/recovery_push/tasks/drill_setup.yml`
- `playbooks/systemd_timers.yml`、`roles/systemd_timers/tasks/main.yml`
- `playbooks/incident_sync_timer.yml`、`roles/incident_sync/tasks/install_timer.yml`、`roles/incident_sync/handlers/main.yml`
- `playbooks/time_sync_ntp_reference.yml`、`roles/time_sync_ntp_reference/tasks/chrony_hosts.yml`
- `playbooks/ca_trust_deploy.yml`、`roles/homelab_cert_renew/tasks/deploy_ca_trust.yml`、`roles/homelab_cert_renew/handlers/main.yml`
- `playbooks/incident_inspect_setup.yml`、`roles/incident_inspect/tasks/main.yml`

`roles/recovery_exec/`・`playbooks/recovery_exec_setup.yml`・`roles/homelab_cert_renew/tasks/{issue,prepare_ca,cleanup,deploy_semaphore,deploy_proxmox,deploy_grafana}.yml`・`playbooks/cert_renew*.yml`・`playbooks/codex_update_check.yml`は一切変更していない。

`docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md`が`git status`上modifiedだが、着手前から存在した差分(Coordinatorによる訂正注記の反映)であり、本batchでは一度もEditしていない — 本batchの変更ではない。

## 2. playbookごとの判定

### 2.1 recovery_io_setup / roles/recovery_io

全12taskが破壊的(user/file/apt/command+creates:/pip/template/systemd)。相互依存する検証・報告taskが後続しないため、全taskをTS-014の個別task単位でゲートした(`roles/recovery_io/tasks/main.yml`)。`Load Slack vault variables`(include_vars、非破壊)はゲートせず常時実行のまま維持 — vaultファイルのロード可否は--check下でも検証価値がある。

handlers(`Reload systemd`/`Restart recovery-io`)は元々`check_mode: false`単独(通知元のゲートに関わらず常に実restartを強制する潜在的穴)だったため、`when: not ansible_check_mode`へ置き換えた(`check_mode: false`は併用せず削除 — バッチAが1箇所残した「効かない設定」を再現しないため)。

playbook側は`check_mode: false`のimport_roleカスケードを除去し、R2の停止assertを除去。R6該当なし(fail_msgにskip_notifications言及なし、確認済み)。

### 2.2 recovery_push_setup / recovery_push_drill_setup / roles/recovery_push(共有role)

`recovery_push_setup.yml`(main.yml + sender_setup.yml)と`recovery_push_drill_setup.yml`(drill_setup.yml)は同じ`roles/recovery_push/`を触るため、依頼の指示どおり同一実装単位内で連続して扱った。

**main.yml**: 6taskすべて独立した破壊的操作(state dir作成・script配置・.ssh dir作成・authorized_keys配置)+非破壊の`Initialize push pubkey dict`(set_fact)+`Setup sender side per target`(include_tasks、loop)。前者4つをTS-014で個別ゲート、後2つは無条件のまま(include先の各taskが自己ゲートするため)。

**sender_setup.yml**(TS-015判定の主眼): `Generate push SSH key` → `Lock down push key` → `Slurp push public key` → `Store ... in dict`の一連を1つのnamed block `Generate and read push SSH key (destructive; TS-015 chain) on {{ push_target.name }}`にまとめblock単位でゲートした。判定根拠 — `Slurp push public key`は`Generate push SSH key`が実際に(simulateでなく)走っていないと、初回ホストでは`.pub`ファイル不在によりtask失敗そのものを起こしうる(recovery_probeのfreshness verifyと同型の「後続taskの正しさが先行taskの実行に依存する」パターン)。`Create recovery config dir`(前提のディレクトリ作成、独立して冪等)はblockの外に残しTS-014の個別ゲートとした — recovery_probeが`Ensure config directory exists`を外に残したのと同じ理由。`Deploy recovery-push.sh`以降(script/unit/drop-in/known_hosts/daemon-reload)はSSH鍵チェーンと無関係な独立操作なのでTS-014個別ゲート。`Scan quory host key`(command、changed_when: false)は読み取り専用診断だが、唯一の消費者`Deploy push known_hosts`自体がゲートされ--check下では一貫してskipされるため、ゲートを追加せず`command`の既定auto-skipのまま残した(§3自己検証のdecoy testで無害を確認)。

**drill_setup.yml**: `loop:`付き`include_tasks`から呼ばれるため`block:`が使えない(skills/ansible-implementation-style/SKILL.md「check_modeの実装上の落とし穴」項目3)。2taskとも独立(daemon-reloadはunit配備の内容を読み返さない)のため、TS-014で個別task単位にゲートし、既存の`check_mode: false`(risk-accepted時代の代替カスケード手段)を`when: not ansible_check_mode`へ置き換えた。

R6: 3playbookとも該当なし。

### 2.3 systemd_timers / roles/systemd_timers

4task(template×2/loop、systemd daemon_reload、systemd enable+start/loop)全て独立した配置+enable/startのみで、後続に検証・報告taskが無い(incident_capture/incident_investigateと同型)。TS-014の個別task単位でゲートした。block化は不要と判断。

### 2.4 incident_sync_timer / roles/incident_sync

`install_timer.yml`のtemplate配備2task+`Enable and start incident sync timer`をTS-014個別ゲート(相互依存する検証・報告taskが後続しないため、systemd_timersと同型でblock不要)。末尾の`Query next scheduled run`(`systemctl list-timers`)は読み取り専用の情報表示であり、assertのように失敗しうる検証ではないため、TS-017の趣旨どおり`check_mode: false`を付けて--check下でも本実行を維持した(コメント記載済み、R5充足)。存在しないunit名に対する`systemctl list-timers`のrc=0をローカルで確認済み(§3参照)。`Report next scheduled run`(debug)は無条件。

handler`Reload systemd for incident sync`は元々`check_mode: false`単独(risk-accepted時代の独立担保)だったため、`when: not ansible_check_mode`へ置き換え、`check_mode: false`は削除した。

### 2.5 time_sync_ntp_reference / roles/time_sync_ntp_reference

`chrony_hosts.yml`の2task(`Deploy chrony conf.d drop-in` → `Restart chrony`、register/changed連動)。`Restart chrony`は既存の`when: ...changed`条件を持っていたため、`not ansible_check_mode`をANDで追加(既存条件を置換せず追加、AC2充足)。skip時のregister結果は`.changed == false`になる(§3のdecoy検証で実測済み)ため機能的には個別ゲート不要だが、R4「破壊的task全てに明示的にwhenを付ける」に従い両taskへ明記した。TS-015のblock化は見送った — assertのような失敗しうる検証ではなく、既存のregister→whenパターン(このrepoの他所のhandler相当の慣用句)であり、consistent gatingで十分安全なことをdecoy検証済み。`main.yml`(include条件のみ)は無変更。

### 2.6 ca_trust_deploy / roles/homelab_cert_renew(deploy_ca_trust.ymlのみ)

`deploy_ca_trust.yml`は`ca_trust_deploy.yml`からのみ呼ばれる(`playbooks/cert_renew.yml`・`cert_renew_quory.yml`は`tasks_from: prepare_ca/issue/deploy_semaphore/deploy_proxmox/deploy_grafana/cleanup`のみ使用し`deploy_ca_trust`は呼ばない、grep確認済み)ため、本roleを直接編集してもバッチCの`cert_renew`系には影響しないと判断し、per-task方式で編集した(呼び出し側での丸ごとゲートは不要)。

3taskのうち`Remove previously deployed intermediate CA`(file, absent)と`Deploy ROOT CA certificate`(copy)をTS-014でゲート。`Slurp ROOT CA certificate`(slurp、`ansible-doc`で`check_mode: support: full`確認済み)はゲートせず常時実行のまま維持 — CA証明書の取得元ホストからの読み取り可否を--check下でも実際に検証する。

handler`update-ca-certificates`は`roles/homelab_cert_renew/handlers/main.yml`内で`deploy_ca_trust.yml`だけがnotifyする(grep確認済み。同ファイルの`restart semaphore`/`restart pveproxy`はcert_renew系task fileがnotifyし、本batchでは変更していない)。`when: not ansible_check_mode`を追加し、既存の`check_mode: false`は削除した。編集後`playbooks/cert_renew.yml`・`cert_renew_quory.yml`の`--syntax-check`が引き続き通ることを確認した(§3)。

### 2.7 incident_inspect_setup / roles/incident_inspect

11task全て独立した破壊的操作(user/file/template/apt/acl)で、相互依存する検証・報告taskが無い。TS-014の個別task単位でゲートした。handlers/main.ymlは存在しない(find確認済み)。

## 3. R1〜R6充足状況

| # | 内容 | 充足 |
|---|---|---|
| R1 | ヘッダを`check-mode-native`へ変更、TS-009条件1・2の両方に言及 | 8playbook全て実施(§2参照)。批A同様「条件1は満たすが条件2は満たさない」の構成 |
| R2 | Round1の`--check`停止assertを除去 | 8playbook全て除去 |
| R3 | role importの`check_mode: false`カスケードを除去 | 8playbook全て除去。import_role/include_tasksへの置換`when:`は付けていない(leaf taskが自己ゲートするため、recovery_probe方式) |
| R4 | 破壊的task全てにwhen+tags | §2の各roleで実施。§4自己検証で全task一覧を機械的に確認 |
| R5 | check_mode非対応moduleの診断taskにcheck_mode: false+理由コメント | `incident_sync/tasks/install_timer.yml`の`Query next scheduled run`に付与(コメント付き)。他roleに該当taskなし |
| R6 | 停止assert除去に伴うskip_notifications案内の除去 | 8playbook全てで該当なし(fail_msgに記載なし、grep確認済み)。ただしrecovery_io_setup/incident_inspect_setupに残っていたRound1の「vars: skip_notifications removed」コメント(R1のstop-assert削除に伴い前提が失効するダングリング参照)は併せて削除した |

## 4. 自己検証

- 8role・handlerの全taskを通しで読み、破壊的moduleの有無を確認した(§2の判定根拠)。
- `--syntax-check`: 8playbook全てrc=0(最終確認済み、`playbooks/cert_renew.yml`・`cert_renew_quory.yml`も併せて確認)。
- `bash scripts/check-tester-gate.sh`: `OK (46 playbooks)`(AC4)。
- `grep -h "^# tester-gate: risk-accepted" playbooks/*.yml | wc -l`: 14→6(AC5充足)。残る6本は非ゴール3本(`cloudkey_cert_deploy`/`proxmox_backup_restore_verify`/`unifi_backup_fetch`)+B-2(`recovery_exec_setup`)+バッチC(`cert_renew`/`codex_update_check`)、想定どおり。
- `ansible-lint`: 変更前後でrule集合をparseable出力(`-p`)で比較し、新規に導入した違反が無いことを確認した。1件だけ新規違反(`name[template]`、`roles/recovery_push/tasks/sender_setup.yml`の新設blockの名前でJinjaが末尾に無い)を検出し、blockの名前を`Generate and read push SSH key (destructive; TS-015 chain) on {{ push_target.name }}`(Jinjaを末尾へ)に修正して解消した。残る違反は全て既存debt(var-naming、既存task名のJinja位置等)で行番号シフトのみ。
- **値の目視で終えず、実際に完走させる検証**として、`/tmp`のscratchpad上でdecoy playbook(`ansible_connection: local`、実host名なし)を4パターン作成・実行し削除した:
  1. `register`されたtaskが`when: not ansible_check_mode`でskipされたとき、その結果は`.changed == false`として定義される(`slurp`/`command`いずれの後続消費でも安全)ことを実測(`time_sync_ntp_reference/chrony_hosts.yml`の設計根拠)。
  2. `file`(dir作成)→`command`+`creates:`(鍵生成)→`slurp`(公開鍵読取)→`set_fact`の4taskを個別に`when: not ansible_check_mode`でゲートした場合、新規ホスト(状態ゼロ)でも`--check`がrc=0で完走し、slurpのfile-not-foundエラーが起きないことを実測。
  3. `import_role` + `when: not ansible_check_mode` + `tags: [destructive]`が、role内の非破壊的診断task(debug)も含めて丸ごとskipすること(wholesale gatingを採らなかった理由の裏付け)を実測。
  4. **sender_setup.yml と同一構造**(`include_tasks`+`loop`から呼ばれるtask fileの中に`delegate_to`付きtaskを含むTS-015 block)を再現し、新規ホストでの`--check`(rc=0、全skip、`_push_pubkeys`は空辞書のまま)→通常実行(鍵生成・スラープ成功、辞書が正しく埋まる)→既存状態での`--check`(rc=0、再度全skip)の3段階で完走することを実測した。
- `systemctl list-timers <存在しないunit名> --all --no-pager`のrcをこの開発機で直接確認し、0であることを確認した(`incident_sync`の`Query next scheduled run`が新規ホストでも失敗しないことの裏付け)。
- 参照した全パス・行番号(各role tasks/handlers、`docs/ai/policies/ansible_test_safety_policy.md`、`skills/ansible-implementation-style/SKILL.md`、`docs/ai/reviews/check_mode_semantics/2026-07-31_007_round2_batchA_implement.md`)は実在をRead/grepで確認済み。
- decoyディレクトリと一時ファイルは検証後に削除済み(`/tmp/claude-1000/.../scratchpad/decoy`ほか)。

**行っていない検証(Testerの領域、AC1〜AC3):** 対象8playbookそのものを`--check`付き/無しで実行し、終了コード・`PLAY RECAP`・ホスト状態の前後比較を確認すること。契約上、対象playbookの実行は禁止されているため行っていない。

## 5. OQ1についての所見

`systemd_timers`と`recovery_push_drill_setup`を実際に変換した結果:

- `systemd_timers`: 4task全てが破壊的で、`when: not ansible_check_mode`でゲートした。診断・検証として残せるread-onlyな要素は無い(現在有効なtimerエントリは`cert-renew-quory`1件のみで、残りは全てコメントアウト済み)。`--check`実行は「4taskとも`skipped`」以外の情報を出さない。
- `recovery_push_drill_setup`(`drill_setup.yml`): 2task(unit配備・daemon-reload)とも破壊的で、同様に全skip。daemon-reloadはunitの中身を読み返さないため、そもそも検証的な意味を持つ余地が薄い。

いずれも「`--syntax-check`+変数解決確認」以上の実質的な dry-run 情報を`--check`が提供しない、というOQ1の懸念は現物でも成立していると見える。ただし、これは`check-mode-native`のラベルが誤りだという意味ではない — TS-009条件2(本体操作を省いた検証には価値がない)は「本体操作以外に検証すべき診断が無いこと」を理由にrisk-acceptedを選ぶ根拠にはならない(TS-010: 条件2を満たさなければcheck-mode-native)。`check-mode-native`は「`--check`が本物のdry-runとして機能する(破壊的操作を実行しない)」ことを保証するラベルであり、「`--check`が追加の診断情報を提供する」ことまでは約束していない。したがって分類そのものは正しいと考えるが、**「`--check`で何が得られるか」の期待値(単なる安全確認か、意味のある検証結果か)がplaybookによって大きく異なる**という実態は、OQ1が指摘した通り残る。`safe-readonly`寄りの別の扱いが要るかどうかはCoordinatorの判断に委ねる。

## 6. 未解決事項

1. **AC1「skippedに現れる」以上の検証情報がsystemd_timers/recovery_push_drill_setupには無い**(§5参照)。requirement AC1の文言上は「終了コード0で完走し、破壊的taskがskippedに現れる」を満たすため形式的には充足するが、実質的なdry-run価値の評価はCoordinator/Reviewerに委ねる。
2. **`roles/recovery_push`のACL/mask等、対象外の副作用履歴は確認していない**(incident_capture roleにあったようなACL mask巻き戻り事故のクラスは、recovery_pushには存在しない — `ansible.posix.acl`モジュール自体を使っていないため該当なし。念のため記載)。
3. **`sender_setup.yml`のTS-015 block内`Slurp push public key`は`ansible.builtin.slurp`(check_mode: support full)だが、block全体をゲートしたため--check下では実行されない。** ca_trust_deployのslurpとは異なり、こちらは`Generate push SSH key`(creates:)の実行結果に直接依存するため、単独でungateすると鍵が無いホストでfile-not-foundになりうる(§3の decoy test 2で確認した通り、依存元も併せてゲートすれば安全)。この非対称(ca_trust_deployのslurpはungate、recovery_pushのslurpはgate)は意図的な設計判断であり、バグではない。

以上、対象8 playbook・関連roleの変換は完了。実ホストでの`--check`/通常実行(AC1〜AC3)はTesterの領域として未実施。
