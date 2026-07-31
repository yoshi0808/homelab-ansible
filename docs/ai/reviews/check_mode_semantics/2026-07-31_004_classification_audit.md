# risk-accepted 分類の妥当性棚卸し(2026-07-31)

Reviewer(独立subagent)による、`playbooks/`配下で`# tester-gate: risk-accepted`を宣言する全playbookの分類妥当性監査。差分レビューではない。判定基準は`docs/ai/policies/ansible_test_safety_policy.md`§2・§4・§5(TS-005〜TS-017)。

## 0. 母集団の確定

`playbooks/*.yml`全50ファイルに対し`grep -n "^# tester-gate:" playbooks/*.yml`で各ファイルのマーカー行を機械的に収集し、5分類の内訳を得た(本文中の言及ではなくヘッダのマーカー行そのもの)。各対象ファイルで`^# tester-gate:`にマッチする行が**厳密に1つだけ**、かつファイル先頭11〜37行目の間(ヘッダコメント内)にあることを確認し、他playbookの分類に言及するだけの誤検出が無いことを確かめた。

`risk-accepted`の母集団は**17件**:

```
ca_trust_deploy.yml
cert_renew.yml
cloudkey_cert_deploy.yml
codex_update_check.yml
incident_capture_setup.yml
incident_inspect_setup.yml
incident_investigate_setup.yml
incident_sync_timer.yml
proxmox_backup_restore_verify.yml
recovery_exec_setup.yml
recovery_io_setup.yml
recovery_probe_setup.yml
recovery_push_drill_setup.yml
recovery_push_setup.yml
systemd_timers.yml
time_sync_ntp_reference.yml
unifi_backup_fetch.yml
```

## 1. 判定の考え方

TS-009の条件2(「破壊的な本体操作を省いた検証には意味がない、または省く価値が乏しい」)は、対象roleが使う実際のmoduleで判定した。Ansibleの`file`/`copy`/`template`/`user`/`ansible.posix.acl`/`systemd`(enable/state)/`command`(`creates:`/`removes:`付き)は**check_mode下でも「変更されるかどうか」を正しくシミュレートする**(diffプレビューに実質的価値がある)。一方`ansible.builtin.command`/`shell`(`creates:`無し)・`ansible.builtin.uri`は非冪等かつcheck_mode非対応が既定であり、これらに依存する割合が高いほど条件2が成立しやすい(オミットしても失う情報が少ない)。

各playbookについて、ヘッダの理由文ではなく実際に呼び出すrole/tasksファイルを読んで判定した(読んだファイルは各節に明記)。

## 2. 個別判定

### 2.1 ca_trust_deploy.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/homelab_cert_renew/tasks/deploy_ca_trust.yml`(`file: state=absent` + `slurp` + `copy: content=...`)。
- 条件1: 満たす。証明書バンドル再構築のみ、サービス再起動なし、自己完結。
- 条件2: **満たさない**。`copy`はcontentの差分比較で「変わるかどうか」を`--check`でも正しく報告する。証明書は約10年不変という主張は実行頻度・変化頻度の話でありTS-011が禁じる論法(「軽いから省く価値がない」ではなく、そもそも省いても意味のある情報が残る)。
- ヘッダとの食い違い: ヘッダは「他のrisk-acceptedよりさらに安全側」という条件1側の強さのみを理由に挙げ、条件2への言及がない。
- 移行に必要な作業: 小規模。pre_tasksの`--check`拒否assertと`check_mode: false`カスケードを外すだけで、配下タスク(file/slurp/copy)は既定のcheck_mode動作で正しく機能する。`notify: update-ca-certificates`ハンドラは変更時のみ発火する構造のまま(check-mode下では通知自体スキップされるのがAnsibleの既定であり、それで問題ない)。

### 2.2 cert_renew.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/homelab_cert_renew/tasks/{issue,deploy_semaphore,deploy_proxmox,deploy_grafana,cleanup,prepare_ca}.yml`。
- 条件1: 疑わしい。pveproxy(Proxmox管理UI)・grafana-server・semaphoreの実restartを伴う。ヘッダは「Web UIが一時的に見えなくなる程度」というが、証明書生成(openssl)や配布に不備があれば復旧に人手が要る可能性があり、「軽微・再実行で復旧」との評価は楽観的。
- 条件2: **明確に満たさない**。`issue.yml`の`cert_needs_renewal`判定(`stat`+`shell`の日数計算、共に`changed_when: false`)は副作用ゼロの純粋な診断であり、`--check`でも(明示的に`check_mode: false`を付与すれば)意味のある「更新が必要か/あと何日か」を出力できる。実際の鍵生成・署名・配布・restartだけを`when: not ansible_check_mode`で個別にゲートすれば、check-mode-nativeの型がそのまま当てはまる。
- ヘッダとの食い違い: ヘッダはquory自身(cert_renew_quory.yml)がcheck-mode-nativeであることと対比して「制御平面ではないから」risk-acceptedを正当化しているが、pveproxyもProxmox管理という点で同程度に重要な制御面であり、この対比は一貫していない。
- 移行に必要な作業: 中規模。6つのplayに分かれた`pre_tasks`の停止assertをすべて外し、各playで診断task(`stat`/`shell`日数計算)に`check_mode: false`、`deploy_*`のimport_roleおよびgrafana停止前後の`homelab-monitoring-{pause,resume}`コマンドに`when: not ansible_check_mode`を追加する。

### 2.3 cloudkey_cert_deploy.yml — 妥当、維持

- 読んだtask: `roles/cloudkey_cert_deploy/tasks/{issue,deploy}.yml`。
- 条件1: 満たす。CloudKey Web UI証明書のみが対象、再実行で復旧可能。
- 条件2: **満たす**。この一連はログイン→CSRF取得→アップロード→有効化→**実際にTLSで served証明書を再取得して検証**→旧証明書削除という、`uri`モジュール主体の非冪等API呼び出し連鎖であり、`cert_renew.yml`と違って「更新が必要かどうか」を判定する分岐が無く常に新規発行する設計。ライブAPI呼び出しと実TLSハンドシェイクでの検証こそが目的であり、それを省いた"プレビュー"には実体がない(Policyの許可条件2の想定例に近い)。
- 判定: risk-acceptedのまま妥当。

### 2.4 codex_update_check.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/codex_update_check/tasks/main.yml`。
- 条件1: おおむね満たす(Codex CLI/npm本体のみ、homelab本番サービスに直接触れない)。
- 条件2: **満たさない**。`npm list -g`/`npm view`によるバージョン取得は`changed_when: false`の純粋な収集であり、`check_mode: false`を付与すれば「更新が利用可能か」を`--check`で安全にプレビューできる。実際に更新するのは`npm install -g ...@latest`の2タスクのみで、`when: codex_update_check_needs_update`に加えて`when: not ansible_check_mode`を足すだけで済む。同種のパターン(apt dry-run)は`proxmox_patch_dryrun.yml`・`ubuntu_vm_full_upgrade.yml`で既に確立済み。
- ヘッダとの食い違い: ヘッダは「npm installを省略した検証には意味がなく...」と主張するが、実際にはバージョン比較(collect)とinstall実行は別タスクに分かれており、比較部分だけでも十分な検証価値がある。
- 移行に必要な作業: 小規模。version収集タスク群(計6個のcommand)に`check_mode: false`、2つの`npm install`タスクに`when: not ansible_check_mode`を追加。

### 2.5 incident_capture_setup.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/incident_capture/tasks/main.yml`。
- 条件1: 満たす。quory専用、既存稼働サービスへの影響なし。
- 条件2: **満たさない**。ディレクトリ作成(`command creates:`)・所有者強制(`file`、mode非設定)・ACL付与(`ansible.posix.acl`)・スクリプト/設定/unit配置(`copy`/`template`)は全てcheck_mode既定動作で安全にプレビューできる。**唯一production影響のあるタスク(timerのenable+start)は、roleの中で既に`when: not ansible_check_mode`が付与済み**(main.yml末尾)——つまりこのroleはすでにcheck-mode-native前提で書かれているが、playbook側の`pre_tasks`停止assertと`check_mode: false`カスケードがそれを握りつぶし、到達不能にしている。
- ヘッダとの食い違い: ヘッダは「破壊性はあるが自己完結」という条件1側の説明に終始し、role内部に既にcheck-mode-nativeの実装が存在する事実に触れていない。
- 移行に必要な作業: 小規模。playbook側の停止assertと`check_mode: false`カスケードを外すだけで、role内部の設計がそのまま活きる。

### 2.6 incident_inspect_setup.yml — 誤分類、`check-mode-native`推奨(最も明確)

- 読んだtask: `roles/incident_inspect/tasks/main.yml`。
- 条件1: 満たす(むしろ17件中最も無害)。デーモンが一切無く、systemd unitも存在しない。
- 条件2: **明確に満たさない**。全タスクが`user`/`file`/`template`/`apt`/`ansible.posix.acl`のみで構成され、破壊的操作(サービス再起動、非冪等コマンド)がそもそも1つも存在しない。「本体操作を省く価値が乏しい」という条件2の前提(=省くべき本体操作がある)自体が成立しない。
- ヘッダとの食い違い: ヘッダは「サービス再起動を一切伴わない」ことを理由に risk-accepted としているが、この理由づけは条件1(実害の軽さ)の説明にしかなっておらず、条件2を検討した形跡がない。
- 移行に必要な作業: 最小。停止assertと`check_mode: false`を外すだけで完了(role側の追加変更は不要)。

### 2.7 incident_investigate_setup.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/incident_investigate/tasks/main.yml`。incident_capture_setupと同型(`file`/`copy`/`template`のみ、timerのenable+startは既に`when: not ansible_check_mode`付き)。
- 条件1: 満たす。条件2: **満たさない**(2.5と同じ理由)。
- 移行に必要な作業: 小規模、2.5と同様。

### 2.8 incident_sync_timer.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/incident_sync/tasks/install_timer.yml`。`template`(service/timer unit)+`systemd`(enable/start、ゲート無し)+`command`(`systemctl list-timers`、`changed_when: false`)。
- 条件1: 満たす。ansy専用、新規timerでOnCalendarまで即時実行なし。
- 条件2: **満たさない**。`systemd: enabled/state`はcheck_mode既定動作で「有効化・起動されるか」を正しく報告する。ヘッダは「配置される内容の正しさはsystemctl show等で見るしかない」と主張するが、これは"配置後の実観測"と"配置前の`--check --diff`によるプレビュー"を混同している——`--check`はunit内容の変更有無を見せることはできる。
- ヘッダとの食い違い: ヘッダは`playbooks/systemd_timers.yml`と同じ判断根拠を援用しているが、その根拠自体が2.15で述べる通り誤り。
- 移行に必要な作業: 小規模。停止assertと`check_mode: false`を外すのみ。

### 2.9 proxmox_backup_restore_verify.yml — 妥当、維持

- 読んだplaybook本体(役割はrole `proxmox_backup_restore_verify`に委譲、ヘッダから存在意義を確認)。
- 条件1: 満たす。使い捨てVMID 999固定、NIC切断隔離、always:で確実に破棄。
- 条件2: **満たす**。本playbookの存在意義そのものが「実際にqmrestoreして起動できるかの実地検証」であり、これはPolicy TS-009の条件2が明示する例(「バックアップのリストア検証など、本体操作自体が検証の目的そのものであるケース」)にそのまま該当する。
- 判定: risk-acceptedのまま妥当。

### 2.10 recovery_exec_setup.yml — 誤分類、`check-mode-native`推奨(既往インシデントあり)

- 読んだtask: `roles/recovery_exec/tasks/{main,target_setup}.yml`。
- 条件1: **疑わしい**。ヘッダ自身が追記(2026-07-11)している通り、2026-07-08に本roleのtarget配布タスク(`authorized_keys.j2`のテンプレート配置——**check_mode native module**)が原因で、quory本番のrecovery-exec SSH経路が**3日間**切断される実インシデントが発生している。「サービス再起動を伴わないから軽微」という当初の条件1評価は、実際に起きた被害の大きさ(3日間の本番断)と整合しない。
- 条件2: **満たさない**。`user`/`file`/`template`(authorized_keys含む)/`ansible.posix.acl`/`command`(`ssh-keygen ... creates:`)/`known_hosts`——すべてcheck_mode下で安全にプレビュー可能なモジュール構成。特に事故の原因となった`authorized_keys.j2`のtemplateタスクは、`--check --diff`を使えば「どのホストの鍵に置き換わるか」を実行前に見ることができ、この事故の再発防止に直接資する。
- ヘッダとの食い違い: 2026-07-11の追記は「横方向の影響を見落としていた」ことを認めつつ、対策をrole内のホスト固定assert(quoryのみ配布可)に限定し、「risk-acceptedの分類は継続する」と結論づけている。しかし本件の後知恵は「実害が軽微」という条件1の前提を崩す実例そのものであり、条件2も併せて満たさないため、分類そのものの見直しが必要だったケース。
- 移行に必要な作業: 小〜中規模。停止assertと`check_mode: false`を外す。`ssh-keygen`(`creates:`)・`user`・`file`・`template`・`acl`・`known_hosts`は既定のcheck_mode動作で問題なく機能するため、追加のゲートはほぼ不要と見込まれる(実装時に個別確認要)。

### 2.11 recovery_io_setup.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/recovery_io/tasks/main.yml`、`roles/recovery_io/handlers/main.yml`。
- 条件1: 満たす(単一機能ブリッジ、他自動化に影響なし)。
- 条件2: **満たさない**。`user`/`file`/`apt`/`command(creates: venv)`/`pip`/`template`/`systemd`のみで構成。`pip`モジュールはcheck_mode対応。
- 移行に必要な作業: 小規模。停止assertと`check_mode: false`カスケードを外す。ハンドラ(`Reload systemd`・`Restart recovery-io`)は現在明示的に`check_mode: false`を持つため、`when: not ansible_check_mode`へ置き換えるか削除する必要がある(handlerはcascadeの対象外——`incident_sync`のhandlerコメントが同じ注意を残している)。

### 2.12 recovery_probe_setup.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/recovery_probe/tasks/main.yml`、`roles/recovery_probe/handlers/main.yml`、`roles/recovery_mute/tasks/deploy_cli.yml`。
- 条件1: 満たす。
- 条件2: **満たさない**。このroleは既にcheck-mode-native的な作り込みが部分的にある——`systemd`によるユニット状態収集タスクは明示的に`check_mode: false`(副作用なし診断のため)、`enable and start`タスクは`when: recovery_probe_service_enabled | bool`のみ(`not ansible_check_mode`が無い)。deploy_cli.ymlは`command creates:`+`copy`のみ。
- 移行に必要な作業: 小〜中規模。「Enable and start recovery-probe」タスクとhandler「Restart recovery-probe」(現在明示的に`check_mode: false`)の両方に`not ansible_check_mode`条件を追加する必要がある。「Verify the running daemon is not older...」ブロックはpost-deploy検証であり、check-mode下ではdaemonが再起動されない前提でこの検証自体も`when: not ansible_check_mode`でスキップすべき。

### 2.13 recovery_push_drill_setup.yml — 誤分類、`check-mode-native`推奨(条件2が最も明確に不成立)

- 読んだtask: `roles/recovery_push/tasks/drill_setup.yml`。
- 条件1: 満たす。ヘッダ自身が「起動/enableは範囲外、サービス再起動・実際のdrill発火を一切伴わない」と明言。
- 条件2: **明確に満たさない**。タスクは`copy`(unit配置)+`systemd daemon_reload`のみで、いずれもcheck_mode既定で安全。しかも、この2タスクには現在**すでに**`check_mode: false`が明示個別付与されている(playbook側のカスケードとは独立に、role側でも強制している)——つまり「起動を伴わない静的配置のみ」という実態そのものが条件2の不成立を裏付けている。
- 移行に必要な作業: 最小。停止assertを外し、role内の2箇所の`check_mode: false`を削除する(既定のcheck_mode動作に任せてよい)だけ。

### 2.14 recovery_push_setup.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/recovery_push/tasks/{main,sender_setup}.yml`。
- 条件1: 満たす。ヘッダ自身「対象サービス自体の再起動・reloadは一切発生しない」。
- 条件2: **満たさない**。`file`/`copy`/`template`/`command(creates:/changed_when:false)`/`systemd(daemon_reload)`のみ。ただし`push-authorized_keys.j2`のtemplate配置はquory側recovery-execの受信鍵を上書きする操作であり(2.10と同種の形——ただし対象はquory自身のみで横方向拡散は無い)、`--check --diff`によるプレビューの価値がある。
- 移行に必要な作業: 小規模。

### 2.15 systemd_timers.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/systemd_timers/tasks/main.yml`。
- 条件1: 満たす。timer armedのみで即時実行なし。
- 条件2: **満たさない**。`template`(unit)+`systemd(daemon_reload)`+`systemd(enabled/state started、ループ)`のみで構成され、いずれもcheck_mode既定で安全にプレビュー可能。「.timerをstartしても即座の実行がない」という理由は、なぜrisk-acceptedにしてよいかではなく、なぜ`check-mode-native`で`when: not ansible_check_mode`のゲートすら実質不要になるほど安全か、を示しているに過ぎない。TS-009の枠組みでは「条件2を満たすから risk-accepted」ではなく、「そもそも条件2が要求する"省く価値の乏しい破壊的本体"が存在しない」ケースであり、`check-mode-native`(あるいは実質的にゲート不要)側に分類すべき。
- ヘッダとの食い違い: incident_sync_timer.ymlのヘッダが本playbookを先例として引用しているが、先例自体が同じ誤りを含んでいた。
- 移行に必要な作業: 最小。停止assertと`check_mode: false`を外すのみ。

### 2.16 time_sync_ntp_reference.yml — 誤分類、`check-mode-native`推奨

- 読んだtask: `roles/time_sync_ntp_reference/tasks/{main,chrony_hosts}.yml`。
- 条件1: 満たす。chrony再起動は設定変更時のみ、他サービスに影響なし。
- 条件2: **満たさない**。`copy`(content比較)による真の冪等 + `systemd restart`は`when: dropin.changed`でゲート済み。`copy`の`changed`判定はcheck_mode下でも正しく計算される(実際に書き込まなくても差分の有無は判定できる)ため、「設定が変わるかどうか」を`--check`で正確にプレビューできる。ca_trust_deployと全く同型の構成でありながら同じ誤り方をしている。
- 移行に必要な作業: 最小。停止assertと`check_mode: false`を外すのみ——`when: dropin.changed`のガードは`systemd`モジュールのcheck_mode既定動作と組み合わせてそのまま機能する。

### 2.17 unifi_backup_fetch.yml — 妥当、維持

- 読んだplaybook本体(役割はrole `unifi_backup_fetch`に委譲。ヘッダで明示的に`proxmox_backup_restore_verify`と同じ理由を援用)。
- 条件1: 満たす。CloudKey側の設定変更なし、バックアップ生成API呼び出しのみ。
- 条件2: **満たす**。バックアップ生成・ダウンロード・鮮度検証という一連の非冪等API操作そのものが検証対象であり、cloudkey_cert_deployと同じ理由でPolicy条件2の想定例に該当する。
- 判定: risk-acceptedのまま妥当。ただし世代ローテーション(既定8世代)への影響という運用上の注意はヘッダの記載どおり有効。

## 3. 母集団全体の分布

| 判定 | 件数 | 対象 |
|---|---|---|
| `risk-accepted`を維持すべき | 3 | cloudkey_cert_deploy.yml, proxmox_backup_restore_verify.yml, unifi_backup_fetch.yml |
| `check-mode-native`へ移すべき | 14 | ca_trust_deploy.yml, cert_renew.yml, codex_update_check.yml, incident_capture_setup.yml, incident_inspect_setup.yml, incident_investigate_setup.yml, incident_sync_timer.yml, recovery_exec_setup.yml, recovery_io_setup.yml, recovery_probe_setup.yml, recovery_push_drill_setup.yml, recovery_push_setup.yml, systemd_timers.yml, time_sync_ntp_reference.yml |

維持すべき3件に共通するのは、破壊的操作(実際のqmrestore/実際のCloudKey API発行・アップロード・活性化・served証明書の実TLS検証)そのものが検証対象であり、それを省いた"プレビュー"に実体が無いという点。移すべき14件に共通するのは、実際のタスク構成が`file`/`copy`/`template`/`user`/`acl`/`systemd`/`command(creates:)`など、Ansibleの既定check_mode機構だけで「変更が起きるかどうか」を正しくプレビューできるモジュールでほぼ完結しており、ヘッダの分類理由がTS-009条件1(実害の軽さ)のみを論じて条件2(本体操作を省く価値)を検討していない、という2026-07-06一括移行時の系統的な見落としである。

このうち4件(incident_capture_setup.yml、incident_investigate_setup.yml、recovery_probe_setup.yml、time_sync_ntp_reference.yml)は、role内部に**既に**`when: not ansible_check_mode`相当のゲートが部分的に実装されており、check-mode-native化はplaybook側の停止assertと`check_mode: false`カスケードを外すだけで大部分が完成する。逆にrecovery_exec_setup.ymlは、2026-07-08に実際に本番3日間断を起こした`authorized_keys`上書きタスクを含み、当時の「実害が軽微」という条件1判断そのものが後の実インシデントと整合しないまま、条件2の検討も行われずrisk-accepted継続の結論に至っている点で、最も優先度の高い再分類候補と考える。

## 4. 判定が割れた・迷った点

- **cert_renew.yml と cloudkey_cert_deploy.yml の線引き**: 両者とも「証明書更新」だが、前者は`stat`/`shell`による冪等な要否判定(`cert_needs_renewal`)を持ち破壊的操作と分離可能なのに対し、後者は要否判定を持たず`uri`ベースの非冪等API連鎖(ログイン→アップロード→活性化→実TLS検証→削除)が一体不可分という構造差で判定を分けた。この構造差の解釈は監査者の判断であり、Yoshinobuまたは実装担当による再確認が望ましい。
- **systemd_timers.yml / recovery_push_drill_setup.yml**: 「本体操作(timer start)自体がcheck_mode既定で安全なので、`check-mode-native`に移してもゲート(`when: not ansible_check_mode`)がほぼ不要」という結論に至ったが、これは「危険な本体操作が無いのでそもそもrisk-accepted自体が過剰」という評価であり、TS-009の運用上は`check-mode-native`への分類変更で正しいはずだが、実装時に「ゲートすべき対象が実質ゼロ」という珍しいケースの扱い(それでも`check-mode-native`ラベルを付けるのか、あるいは`safe-readonly`寄りに近い性質なのか)はPolicy制定側の判断を仰ぐ余地がある。

## 5. 未解決事項

- 各playbookの実装作業(role側への`when: not ansible_check_mode`追加、handlerの見直し等)は本監査のスコープ外であり、Implementerが個別に着手する前提。特にcert_renew.ymlとrecovery_exec_setup.ymlは既往の実運用影響(pveproxy/grafana restart、2026-07-08 SSH断インシデント)があるため、実装前にYoshinobuの確認を挟むことが望ましいと考える(監査者の推測)。
- ca_trust_deployとtime_sync_ntp_referenceで挙げた「copyの`changed`判定はcheck_mode下でも正しく計算される」という前提は、本監査ではAnsibleモジュールドキュメント上の一般的挙動として確認したのみで、本リポジトリでの実機`--check --diff`実行による検証は行っていない(read-only監査の制約、および実行識別子の境界により対象playbookの実行自体を避けた)。実装・再分類の際にはTester役による実地確認が必要。
