# Ubuntu VM Patch Policy

本書はhomelabのUbuntu nodeに対するpatch、reboot、healthcheck、通知の許可、禁止、停止条件、判断軸の正本である。環境事実と実装・運用詳細は対応Contextを参照し、競合時は本Policyを優先する。

## 1. 目的

<!-- UV-001 -->
homelabのUbuntu nodeに対するpatch運用方針を定義する。

<!-- UV-002 -->
Ubuntu nodeはUbuntu Proによる自動patch適用を基本とする。

Ansibleの役割はpatch適用そのものではなく、次の範囲に限定する。

<!-- UV-003 -->
- nodeの特性に応じたreboot timingを制御する。
<!-- UV-004 -->
- sensitive VMのreboot後にservice疎通を確認する。
<!-- UV-005 -->
- sensitive VMの日次healthcheckを行う。
<!-- UV-006 -->
- 異常時とreboot実行時に通知する。

## 2. 対象と実行範囲

nodeごとに方針1「計画的reboot」または方針2「自動reboot」を選ぶ。

<!-- UV-007 -->
停止影響の大きいserviceを持つVMは方針1とし、深夜の計画的rebootをAnsibleで管理する。

<!-- UV-008 -->
開発、backup、検証、infra管理node等は方針2とし、自動rebootとする。

<!-- UV-009 -->
`authy`は方針1とし、`reboot_required`の場合だけ計画的にrebootしてhealthcheckする。

<!-- UV-010 -->
`monnie`は方針1とし、`reboot_required`の場合だけ計画的にrebootしてhealthcheckする。

<!-- UV-011 -->
`ansy`は方針2とし、rebootのタイミングを固定時刻で決めずunattended-upgradesに委ねる。`ubuntu_nightly.yml`の管理対象にしない。

<!-- UV-012 -->
`quory`は方針2とし、固定時刻に自動rebootさせ、`ubuntu_nightly.yml`の管理対象にしない。

<!-- UV-013 -->
Ubuntu nodeを追加する場合はSystem Contextの対象表へ追記し、方針1または方針2のどちらを採用するか明示する。

<!-- UV-014 -->
security patch、ESM patch、ESM Apps patchの定常更新はUbuntu Proとunattended-upgradesが自動実行する。

<!-- UV-025 -->
non-apt productはgeneric registryへ登録済みの対象だけを、`dry_run=true`のmonthly実行時に確認する。

<!-- UV-026 -->
non-apt productの初期対象は`monnie`へmanual installされたPrometheusだけとする。

## 3. 対応するPlaybook

次の5入口を本Policyに関連する索引として列挙する。列挙自体は変更操作の許可を意味せず、実行可否は本Policyの各UV規範、playbook先頭のtester-gate、入力gateをすべて満たす場合に限る。

| Playbook | Policy上の役割 |
|---|---|
| `radius_healthcheck.yml` | `authy`のread-only healthcheck |
| `monitoring_healthcheck.yml` | `monnie`のread-only healthcheck |
| `ubuntu_nightly.yml` | 方針1 VMのreboot lifecycleに従属する条件付きrebootとpost-check |
| `ubuntu_vm_full_upgrade.yml` | monthly read-only判定と確認付きsingle-node manual apply |
| `prometheus_update_check.yml` | non-apt Prometheusの確認・manual update・rollbackの専用入口。UV-035〜UV-039が許可・禁止境界を定める |

`prometheus_update_check.yml`はmonnieのnon-apt Prometheusを対象に、確認(`dry_run=true`)・manual apply(`dry_run=false`)・rollback(`rollback=true`)を1本のplaybookで扱う。旧Policy §3.4は実装拡張前の「確認+通知のみ」設計を凍結した規範であり、実装がその範囲を超えて拡張された結果、不一致が生じていた。本書はこの不一致を実装に合わせて解消し、UV-035〜UV-039を現行実装の許可・禁止境界として再定義する。

<!-- UV-053 -->
本Policy対応playbookは方針1 VMだけを対象とし、方針2 nodeをAnsible管理対象にしない。

<!-- UV-054 -->
方針1 VMには、そのVMが提供するserviceに応じた専用healthcheck playbookを用意する。

<!-- UV-058 -->
healthcheck playbookはmanualで単体実行してよい。

<!-- UV-059 -->
`ubuntu_nightly.yml`は方針1 groupだけを対象とする共通の深夜reboot入口とする。

## 4. 判断軸

### Monthly full-upgradeとnon-apt

<!-- UV-018 -->
Ubuntu Pro / unattended-upgradesの対象外となる通常更新はmonthlyにnode単位で判定し、`#patches`へ通知する。

<!-- UV-021 -->
hold packageはread-onlyで収集し、1件以上ある月だけphasing保留の直後に件数とnameを表示する。

<!-- UV-022 -->
hold一覧をStatus、重要package、件数閾値、apply判断に使用しない。

<!-- UV-023 -->
`unpoller`の同一version文字列候補は既知のrepository metadata事象として候補表示に残す。

<!-- UV-024 -->
同一version文字列だけを根拠とする専用除外判定を設けない。

<!-- UV-027 -->
non-apt versionはcurrentとlatestをread-only GETし、両方を数値versionとして取得できた場合だけ比較する。

<!-- UV-032 -->
両方の取得成功と数値比較によりupdateありが確定した場合だけ、Statusを最低`REVIEW_REQUIRED`へ昇格し、reasonを追加する。

<!-- UV-033 -->
既存の`BLOCKED`または`MAJOR_UPGRADE_DETECTED`をnon-apt結果によって降格させない。

<!-- UV-034 -->
取得、JSON parse、version比較の失敗はbest-effort / fail-quietとして通知とreportだけに残し、Statusを変更せずplaybookも失敗させない。

<!-- UV-084 -->
方針1 VMの主力serviceに影響するpackageがmonthly full-upgrade候補に含まれる場合、通知でその影響を明示し、他候補に埋没させない。対象serviceと具体的package patternはrole defaultsを正本とする。

### Rebootとhealthcheck

<!-- UV-042 -->
方針1はnightlyで`reboot_required`を確認し、必要な場合だけrebootする。

<!-- UV-047 -->
方針2はunattended-upgradesが`reboot_required`を検出した場合に自動rebootする。

<!-- UV-051 -->
方針1ではreboot-required fileが存在すればreboot要と判定する。

<!-- UV-052 -->
方針1ではneedrestartがreboot要と判定した場合もreboot要とする。UV-051と本条件の関係はORである。

<!-- UV-056 -->
healthcheckが`WARNING`または`CRITICAL`なら通知対象と判定する。

## 5. ライフサイクル・処理フロー

### 定常更新とmanual apply

<!-- UV-016 -->
aptのpost-install scriptによるservice自動restartは、更新を深夜の低需要時に行いhomelabでの実害がほぼないことを条件に許容する。

monthly full-upgradeはhealthcheck、simulation、分類、通知の順に判定し、manual applyでは確認gateを先に通す。実装の詳細はcodeと`playbooks/README.md`、運用順序はOperations Contextを参照する。

### 方針1のreboot

<!-- UV-040 -->
方針1 VMは`Unattended-Upgrade::Automatic-Reboot`をfalseにする。

<!-- UV-041 -->
方針1 VMのreboot timingはAnsibleが制御する。

<!-- UV-043 -->
reboot後は対象VMのservice状態と疎通を確認する。

<!-- UV-044 -->
`authy`のpost-checkはFreeRADIUSの状態と1812/udp、1813/udpのlistenを確認する。

<!-- UV-045 -->
`monnie`のpost-checkはPrometheusの9090/tcp、Grafanaの3000/tcp、Lokiの3100/tcpのlistenを確認する。

### 方針2のreboot

<!-- UV-046 -->
方針2 nodeは`Unattended-Upgrade::Automatic-Reboot`をtrueにする。

<!-- UV-049 -->
`ansy`は再構築とbackupを前提に自動rebootを許容する。

<!-- UV-050 -->
`quory`は自身がAnsible実行基盤であるためnightlyで管理せず、`Automatic-Reboot-Time`を固定する。

### Nightlyとhealthcheck

<!-- UV-055 -->
healthcheckはread-onlyでservice状態を収集、判定、reportする。

<!-- UV-057 -->
朝のhealthcheckで前夜reboot後のservice稼働を確認する。

<!-- UV-060 -->
nightlyは最初に`reboot_required`を確認する。

<!-- UV-061 -->
`reboot_required=false`ならrebootせず、通知もしない。

<!-- UV-062 -->
`reboot_required=true`ならreboot実行前に開始通知する。

<!-- UV-063 -->
開始gate通過後にrebootを1回実行する。

<!-- UV-064 -->
reboot後は起動完了を待つ。

<!-- UV-065 -->
起動後に対象VMのservice状態を確認する。

<!-- UV-066 -->
post-check結果を`OK`または`CRITICAL`として通知する。

### Scheduler

<!-- UV-079 -->
systemd timerを使う場合は`quory`上で実行する。定常job(nightly reboot判定、healthcheck等)の実行基盤(systemd timerまたはSemaphore Schedule)と正確な時刻はOperations Contextを正本とし、実行基盤の変更はpatch / reboot許可を拡張しない。

<!-- UV-080 -->
`authy`のnightly reboot判定(`ubuntu_nightly.yml`)は日次で自動実行する。

<!-- UV-081 -->
`authy`のhealthcheck(`radius_healthcheck.yml`)は日次で自動実行する。

<!-- UV-082 -->
monitoring healthcheck(`monitoring_healthcheck.yml`)は日次で自動実行する。

## 6. 通知方針

<!-- UV-020 -->
monthly判定の通知にはinstall、remove、phasing保留の件数とpackage別versionを表示する。

<!-- UV-028 -->
non-apt updateありの場合はcurrentからlatestへの変化とmanual updateが必要であることを通知し、reportへ保存する。

<!-- UV-029 -->
non-apt latestの場合はcurrent versionとlatest状態を通知し、reportへ保存する。

<!-- UV-030 -->
non-apt取得または比較失敗の場合はcurrent / latestのreturn codeを通知し、reportへ保存する。

<!-- UV-031 -->
reportの`nonapt`にはname、current、latest、state、current / latest return code、HTTP status、noteを保存する。

<!-- UV-067 -->
nightlyで`reboot_required=false`なら通知しない。

<!-- UV-068 -->
reboot後のpost-checkが`OK`なら、reboot実施と`OK`を通知する。

<!-- UV-069 -->
reboot後のpost-checkが`NG`なら`CRITICAL`を通知する。

<!-- UV-070 -->
full-upgradeのmonthly dry-runとmanual applyはnode単位で通知し、通常は`#patches`、`BLOCKED`の場合だけ`#alerts`を使う。

<!-- UV-071 -->
healthcheckが`OK`なら通知しない。

<!-- UV-072 -->
healthcheckが`WARNING`なら通知する。

<!-- UV-073 -->
healthcheckが`CRITICAL`なら通知する。

<!-- UV-074 -->
深夜通知は翌朝確認する運用を許容する。

<!-- UV-075 -->
Slack通知は`common_slack` role経由で行い、WebhookはAnsible Vaultで管理する。

<!-- UV-076 -->
nightly、full-upgrade、healthcheckを次のchannel / statusへ割り当てる。

| 状況 | channel | status |
|---|---|---|
| nightly: reboot開始 | `#info` | `info` |
| nightly: reboot正常完了 | `#info` | `ok` |
| nightly: service異常 | `#alerts` | `critical` |
| nightly: reboot timeout | `#alerts` | `critical` |
| full-upgrade: monthly dry-run / manual apply | 通常`#patches`、`BLOCKED`だけ`#alerts` | Statusに応じた`info` / `ok` / `warning` / `critical` |
| healthcheck: `WARNING` | `#alerts` | `warning` |
| healthcheck: `CRITICAL` | `#alerts` | `critical` |

<!-- UV-077 -->
通知失敗はbest-effortとして扱い、呼出元playを停止しない。

<!-- UV-078 -->
Slack移行済みtaskからmail varsを参照せず、mail moduleを使用しない。

## 7. 制約・禁止事項

### Patch適用

<!-- UV-015 -->
Ansibleで定常的な自動patch適用を行わず、Ubuntu Pro対象外の通常更新だけをmonthly判定と確認付きmanual applyで扱う。

<!-- UV-017 -->
serviceを`Package-Blacklist`へ追加してmanual管理へ切り替える方式を採用しない。

<!-- UV-019 -->
monthly実行は`dry_run=true`のread-only判定に限定し、実適用は確認文字列を伴うsingle-node manual applyだけを許可する。

### Non-apt Prometheusの許可・禁止境界

次の5条件は`prometheus_update_check.yml`による非apt Prometheus管理の許可・禁止境界である。

<!-- UV-035 -->
定期実行(`dry_run=true`)はPrometheus artifactのdownloadを一切行わない。downloadは`dry_run=false`による明示的なmanual apply実行時にだけ発生する。

<!-- UV-036 -->
Prometheusのupdateは`dry_run=false`という明示的なextra-var指定なしには発生しない。`dry_run`未指定はfail-closedでassert失敗し、自動updateを構造的に防止する。

<!-- UV-037 -->
Prometheusのservice restartは、`dry_run=false`かつ`not ansible_check_mode`によるbinary swap成功後にだけ発生する。確認専用実行(`dry_run=true`)および`--check`実行ではrestartを一切行わない。

<!-- UV-038 -->
Prometheusのupdateとrollbackは、人間が`prometheus_update_check.yml`を`-e dry_run=false`(update)または`-e rollback=true -e dry_run=false`(rollback)で明示的に実行することで行う。実行判断は人間が行うが、artifactのdownload・検証・backup・binary差し替え・restart・health確認は本playbookが一括して行う。update失敗時はbackupから自動でrollbackする。手動でrollbackするPlaybookを用意する。

<!-- UV-039 -->
`dry_run=false`のapt full-upgrade適用経路(`ubuntu_vm_full_upgrade.yml`)ではnon-apt Prometheusのcheckを実行しない。

### Rebootと対象境界

<!-- UV-048 -->
方針2 nodeをAnsible管理、監視、healthcheckの対象にしない。

## 8. 変更履歴

| 日付 | 変更 |
|---|---|
| 2026-05-09 | 初版作成 |
| 2026-07-17 | 旧v1.5へ更新 |
| 2026-07-24 | Git HEADの旧289行版を標準8節へ再編。Policy核を維持して非規範のSystem / Repository / Operations情報をContextへ分離し、§3.4の既知実装不一致を未解決のまま見える化 |
| 2026-07-25 | UV-035〜UV-039を`prometheus_update_check.yml`の現行実装(dry_run gate・manual update・rollback)に合わせて再定義し、Policy/実装不一致を解消 |
| 2026-07-25 | UV-079〜UV-082をSemaphore移行済みの実態に合わせて再定義し、具体的な時刻表記をOperations Contextへ委譲。単独で浮いていたUV-083をUV-079へ統合し削除。主力product明示の規範としてUV-084を追加し、`ubuntu_vm_full_upgrade`のunpoller対応(実装)と対応付け |
