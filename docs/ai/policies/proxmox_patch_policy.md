# Proxmox Patch Policy

本書はProxmox VE hostのpatchに関する許可、禁止、停止条件の正本である。playbook / roleの索引は[playbook map](../context/ansible/playbook-map.md)と[role map](../context/ansible/role-map.md)、運用手順は[Operations Context](../context/operations/proxmox-patch.md)、環境事実は[System Context](../context/system/proxmox.md)を参照する。実装詳細はコードを正本とする。Contextは非規範であり、本書と競合する場合は本書を優先する。

## 1. 目的

<!-- SB-001 -->
本Policyは、Proxmox VE hostへのpatchを安全に判断、適用、停止するため、次を必須目的とする。

- 判断を人間の気分や記憶へ依存させない。
- 軽微な通常patchを自動化し、対応忘れを防ぐ。
- 重要コンポーネント更新を自動適用しない。
- pve2を先行検証nodeとし、pve1を保護する。
- host OSはrollbackでなく再インストールを復旧原則とする。
- VM / CT、replication、backupを守る。

## 2. 対象と実行範囲

### 2.1 基本範囲

<!-- SB-002 -->
Proxmox patchは通常のLinux server更新より慎重に扱う。kernel、ZFS、NIC・firmware・driver、cluster、corosync、管理面、QEMU・container、storage・replication、network stack・bridge・segmentへの影響が、家庭内network、VM稼働、cluster安定性へ直結し得ることを考慮する。

<!-- SB-003 -->
重要コンポーネントでない更新だけから成る場合は`PATCH_READY`とし、自動適用を許可する。実行scheduleの実値はscheduler設定とOperations Contextを正本とする。

<!-- SB-004 -->
重要コンポーネント更新、removeを伴う更新、major upgrade疑いは自動適用しない。`MAINTENANCE_REQUIRED`、`BLOCKED`、`MAJOR_UPGRADE_DETECTED`のいずれかとして、人間判断または別計画へ移す。

<!-- SB-005 -->
`MAINTENANCE_REQUIRED`に軽微な更新が含まれても、通常運用では部分適用しない。Proxmox更新は`apt-get dist-upgrade`による一括更新を基本とし、依存関係とpackage状態を通常flowから分岐させない。

<!-- SB-006 -->
部分適用を検討できるのは、通常patch運用から切り離した明示的な例外maintenanceだけである。

### 2.2 node順序とguest

<!-- SB-011 -->
- pve2を先に処理する。
- pve1が正常な場合のみpve2を更新する。
- pve2が壊れた場合はpve1を守り、pve1が生きている間にpve2を再インストールする。
- pve1へ進めるのは、pve2更新後のhealthcheckがOKの場合だけである。

<!-- SB-012 -->
apply前にVM / CTの所在を必ず確認する。`PATCH_READY`自動flowには退避と復帰を含める。

<!-- SB-013 -->
VM / CTのhome nodeはProxmox tagを正本とし、外部YAMLを正本にしない。tagは`prefer<node名>`形式とし、対象node名と一致するtagを持つguestだけをそのnodeへの復帰対象とする。

<!-- SB-018 -->
VM / CT migrationは`PATCH_READY`自動適用flow内で許可する。

<!-- SB-019 -->
QEMU VMのlocal disk migrationは`proxmox_evacuate_allow_local_disk_migration`と`proxmox_restore_allow_local_disk_migration`に従う。有効時はlocal diskを伴うlive migrationを行い、無効時はlocal disk optionを付けずにmigrationを試み、失敗したら停止する。無効は対象除外を意味せず、local diskの自動検出・除外は行わない。HA管理guestはmaintenance modeで退避するため、このflagの対象外である。

### 2.3 control node別の範囲

<!-- SB-047 -->
pve1 / pve2のreboot影響を受けないProxmox cluster外のcontrol nodeから実行する場合だけ、pve2からpve1までのfull flowを自動実行してよい。

<!-- SB-048 -->
control nodeがProxmox上のVMである場合、pve1 / pve2の連続自動patchを行わない。実行できるのはcontrol nodeが存在しない側の単一node patchだけであり、control node自身を同一playbook内でmigrationして続行しない。所在変更は人間が別作業として明示的に行う。

<!-- SB-076 -->
`PATCH_READY`自動適用ではcontrol nodeをpatch対象node上に置かない。

<!-- SB-077 -->
管理対象host自身からAnsibleを実行しない。cluster内control nodeではfull flowを実行せず、同一playbook内で自己migrationしない。

<!-- SB-078 -->
reboot影響を受けないcluster外control nodeからだけ、pve2、pve1、VM復帰までのfull flowを自動実行してよい。

<!-- SB-090 -->
Ansible実行端末はansyまたはquoryに限定する。管理対象host自身から実行せず、weekly fullはProxmox nodeからの実行をpreflightで拒否する。

## 3. 対応するPlaybook

### 3.1 安全度と入口

<!-- SB-020 -->
入口は次の4安全度に固定し、自動実行範囲を分類どおりに制限する。

| 安全度 | Playbook / 作業 | 許可範囲 |
|---|---|---|
| safe | `proxmox_healthcheck.yml` | read-only状態収集。自動可 |
| semi-safe | `proxmox_patch_dryrun.yml` | package metadata更新、simulation、分類。実patchなし。自動可 |
| controlled apply | `proxmox_evacuate_node.yml`、`proxmox_restore_vm_placement.yml` | guest配置変更。条件付き可 |
| unsafe | `proxmox_patch_apply_node.yml`、`proxmox_patch_weekly_full.yml`、major / maintenance apply | OS patchを含む。明記された条件下だけ可。major / maintenanceは自動禁止 |

### 3.2 healthcheckとdry-run

<!-- SB-021 -->
healthcheckは単一nodeへの`--limit`を許可するが、結果が`WARNING`または`CRITICAL`ならpatch applyを禁止する。

<!-- SB-022 -->
quorumなし、ZFS異常、apt / dpkg異常、重要service停止、systemd failed unit、root filesystem危険域、report生成失敗のいずれかをhealthcheck失敗とする。

<!-- SB-094 -->
dry-runは到達可能かつhealthcheckがOKのnodeが1node以上あれば開始する。pve1 / pve2の両方が到達可能な場合は従来どおり両nodeのhealthcheckがOKであることを要求する。片方のnodeが通信断、`--limit`で対象外、またはhealthcheck失敗(SB-022が定めるquorum / ZFS / apt-dpkg / 重要service等の実障害)により除外された場合は、残る側のnodeのhealthcheckがOKであれば単一node dry-runとして開始し、通知で対象nodeを明示する。ただし通知文言は通信断とhealthcheck失敗を断定的に区別せず(両者ともAnsible実行上は同様に対象から脱落するため)、`--limit`による意図的な単一node実行だけは別文言で明示する。pve1 / pve2の両方が到達不能な場合は開始せず、明確なエラーで停止する(空reportやサイレント成功にしない)。package metadata更新とsimulationは行うがpackage本体を変更せず、実patchを適用しない。単一node dry-runの`PATCH_READY`は、apply側(SB-027、SB-028、SB-032)が要求する両node揃ったfixed pair dry-run条件を満たしたとはみなさない。

<!-- SB-025 -->
dry-runは次の順でStatusを決める。

- 更新なし: `NO_UPDATES`
- apt simulation失敗: `BLOCKED`
- major upgrade疑い: `MAJOR_UPGRADE_DETECTED`
- 重要コンポーネント更新: `MAINTENANCE_REQUIRED`
- removeあり: 置換関係に応じて`MAINTENANCE_REQUIRED`または`BLOCKED`
- 重要コンポーネント更新もremoveもなし: `PATCH_READY`

### 3.3 evacuate

<!-- SB-026 -->
evacuateはdestination nodeとtarget nodeのhealthcheckがともにOKで、targetが許可nodeである場合だけ開始する。non-HA migration失敗またはmaintenance mode有効化timeoutで停止する。

<!-- SB-087 -->
`target_node`はpve1またはpve2だけを許可する。`destination_node`は反対側nodeとして自動決定し、外部から指定させない。

### 3.4 apply

<!-- SB-027 -->
apply nodeは指定した単一nodeに限り、`PATCH_READY`の自動適用または`MAINTENANCE_REQUIRED`の手動適用だけを許可する。`MAINTENANCE_REQUIRED`は手動apply modeと正しい明示的確認文字列を必須とする。

<!-- SB-028 -->
対象nodeのhealthcheck、利用する反対nodeのhealthcheck、事前dry-runまたは直前re-dry-runのStatus、control node分離、guest退避の全条件を満たさなければ停止する。`BLOCKED`または`MAJOR_UPGRADE_DETECTED`なら停止する。

<!-- SB-031 -->
apply node単体ではguest退避、別nodeへの自動続行、home nodeへの最終復帰、`BLOCKED`解除を行わず、`MAJOR_UPGRADE_DETECTED`を適用対象にしない。

<!-- SB-088 -->
apply対象はpve1またはpve2として指定した単一nodeに限定し、apply前に対象node上へrunning guestが残っていないことを確認する。

### 3.5 weekly fullとrestore

<!-- SB-032 -->
weekly fullは、cluster外control node、両nodeのhealthcheck OK、dry-run `PATCH_READY`、guest退避・復帰可能、明示的に許可されたcontrollerという全条件を要求し、pve2から開始する。許可controllerの既定はquoryだけとし、別のcluster外hostを使う場合は`proxmox_patch_weekly_full_allowed_controllers`を実行時変数で明示overrideする。

<!-- SB-033 -->
control node、healthcheck、Status、evacuate、apply、node復帰、post-healthcheckの各gateで失敗したら停止する。pve2がNGの状態でpve1へ進まない。

<!-- SB-034 -->
restoreはhome tagの対象だけを戻す。non-HA migration失敗、maintenance mode解除timeout、HA guest復帰timeout、post-restore healthcheck NGのいずれかで停止する。

<!-- SB-035 -->
`MAINTENANCE_REQUIRED`は人間のmaintenance判断、`MAJOR_UPGRADE_DETECTED`は別project、`BLOCKED`はContingency Planへ移し、これらを通常自動flowで処理しない。

## 4. 判断軸

### 4.1 StatusとUrgency

<!-- SB-007 -->
| Status | 条件の要旨 | 自動適用 |
|---|---|---|
| `NO_UPDATES` | 更新候補なし | 不要 |
| `PATCH_READY` | 重要コンポーネントでない通常更新のみ | 可 |
| `MAINTENANCE_REQUIRED` | 重要コンポーネント更新または許容可能なremove | 不可 |
| `BLOCKED` | 通常更新計画として信用できない | 禁止 |
| `MAJOR_UPGRADE_DETECTED` | major upgrade疑い | 禁止 |

<!-- SB-008 -->
Urgencyは人間が判断・対応する速度を表す別軸であり、自動適用の許可条件ではない。

<!-- SB-009 -->
認証なしRCE、管理画面RCE、公開済みexploit、ransomware悪用、VM escape、認証bypass、root権限取得可能なLPE、backup・token・secret漏えいのいずれかは`URGENT`として即対応する。

<!-- SB-010 -->
local user必須、特定機能有効時だけ、DoSだけ、XSSだけ、物理access必須、特定CPU・deviceだけの条件は、LPEか、機能利用有無、可用性、管理面露出、家庭環境、該当hardwareをそれぞれ確認して`HIGH`候補を判断する。

### 4.2 重要コンポーネントとStatus詳細

<!-- SB-036 -->
次を重要コンポーネントとする。

- `proxmox-ve`
- `proxmox-kernel-*`
- `pve-manager`
- `pve-cluster`
- `pve-ha-manager`
- `qemu-server`
- `pve-container`
- `libpve-*`
- `corosync`
- `zfsutils-linux`
- `zfs-zed`
- `ifupdown2`
- `firmware-*`
- `intel-microcode`
- `amd64-microcode`
- `systemd`
- `udev`

重要更新は`MAINTENANCE_REQUIRED`、重要removeで置換先不明は`BLOCKED`、重要removeでも後継・置換が同時に見える場合は`MAINTENANCE_REQUIRED`とする。

<!-- SB-037 -->
`NO_UPDATES`は通知とreport保存だけを行い、applyしない。

<!-- SB-038 -->
`PATCH_READY`にはhealthcheck OK、`apt-get check`成功、simulation成功、removeなし、major疑いなし、重要更新なしのすべてが必要である。pve2へ先行適用し、post-healthcheck OKの場合だけpve1へ進む。NGならpve1へ進まず停止・通知する。

<!-- SB-039 -->
`MAINTENANCE_REQUIRED`は自動適用も部分適用もせず、毎週dry-runで再評価し、保留期間に固定上限を設けない。人間がmaintenance枠を確保してpve2から手動実施するか判断する。

<!-- SB-040 -->
`BLOCKED`は両nodeへの適用と部分適用を禁止し、自動apply timerを停止し、復旧・回避・再構成routeへ移す。復帰条件を満たすまでapplyを禁止する。

<!-- SB-041 -->
次のいずれかに該当する場合は`MAJOR_UPGRADE_DETECTED`とする。

- Proxmox major versionが変わる疑いがある。
- Debian suiteが変わる疑いがある。
- repository suiteを変更した直後である。
- base packageが大量に更新される。
- install / removeが大量にある。
- `pve-manager`のmajor versionが変わる疑いがある。

`MAJOR_UPGRADE_DETECTED`は通常patchから除外し、自動適用せず別project化する。Roadmap / Release Notesを参照してpve2検証計画を作り、pve1を最後にする。

### 4.3 remove

<!-- SB-042 -->
removeを検出しても即`BLOCKED`にはしない。simulation成功、後継・置換packageの同時install、major疑いなし、中核packageが単に失われる状態でない、という全条件を満たす場合は`MAINTENANCE_REQUIRED`とし、自動適用せず人間が判断する。

<!-- SB-043 -->
simulation失敗、`apt-get check`失敗、後継不明の重要remove、中核packageが消えるだけに見える状態、repository / dependency破綻疑いのいずれかは`BLOCKED`とする。

### 4.4 Urgency詳細

<!-- SB-044 -->
UrgencyはStatusと分離し、simulation出力だけで決めない。security repository由来、changelog / NEWS、分類結果、公式Security Advisory、SSH・TLS・auth・QEMU・kernel・firewall・network exposureとの関係を材料にする。

<!-- SB-045 -->
- `LOW`: timezone、editor、documentation、小規模utility等の軽微な通常更新。
- `NORMAL`: bug fix、minor package、routine maintenance、security要素が明確でない重要コンポーネント更新。
- `HIGH`: security repository由来、CVE等の明記、公式advisory関連、`openssl`、`openssh`、`curl`、`libc`、`apt`、`dpkg`、QEMU、kernel等のsecurity-sensitive package、firewall・network service・authentication・TLS関連。
- `URGENT`: 重大脆弱性または既知悪用が疑われ、RCE、認証bypass、VM escape、internet exposureへ重大な影響がある更新。

<!-- SB-046 -->
`URGENT`は過剰に自動昇格せず、公式advisory、changelog、人間判断で昇格する。Urgencyが`HIGH`または`URGENT`でも、Statusが`MAINTENANCE_REQUIRED`、`BLOCKED`、`MAJOR_UPGRADE_DETECTED`なら自動適用しない。

### 4.5 reboot、情報源、AI分類

<!-- SB-024 -->
AI分類は補助に限り、最終Statusを直接決定しない。

<!-- SB-030 -->
許可されたpost-healthcheck retryでOKへ戻れば`SUCCESS`、全試行で`CRITICAL`なら`CRITICAL`として扱う。

<!-- SB-066 -->
週次dry-runでは対象packageのchangelogを最優先し、major / minor疑いまたは中核packageが広範囲に動く場合はRoadmap / Release Notesを参照する。changelog全文をreportへ保存し通知は要約とし、人間が全文を毎回読む運用にしない。単純grepだけで重要該当性やUrgencyを決めず、Ansible tasksが機械結果と構造化分類をもとに最終Statusを決める。

<!-- SB-068 -->
Roadmap / Release Notes、Proxmox公式更新手順、Proxmox Security Advisories、Debian Security Trackerを、それぞれrelease全体像、公式更新方法、Proxmox security、Debian package securityの確認に用いる。changelogだけでは変更の全体像が見えない場合もRoadmap / Release Notesを参照する。

<!-- SB-071 -->
AIはchangelog分類と説明生成を補助するが、実行engineでも最終適用判断者でもない。

<!-- SB-072 -->
AIが出すUrgencyは候補に限り、Ansible tasksが本Policyの判断条件と照合して最終Status / Urgencyを確定する。

<!-- SB-074 -->
simulation・収集はAnsible / shell、changelog意味分類と説明候補はAI、重要componentとsecurity sourceの機械判定、最終Status / Urgency、apply可否はAnsible tasks、実patchはAnsibleが担う。

<!-- SB-089 -->
dry-run時の`reboot_expected`は推定、apply後の`reboot_required`は事実として区別する。reboot要否はreboot-required fileだけでなく、実行中kernelと導入済みkernel packageの差も使って判定する。

## 5. ライフサイクル・処理フロー

### 5.1 標準flow

1. control nodeの配置と対象を確認する。
2. pve1 / pve2のhealthcheckを行う。
3. fixed pair dry-runでStatusを確定する。
4. `PATCH_READY`だけ自動flowへ進める。
5. pve2をevacuate、apply、必要ならreboot、post-healthcheck、restoreする。
6. pve2の全gateがOKの場合だけpve1を同じ順序で処理する。
7. 結果を通知する。

control node条件別の詳細手順は[Operations Context](../context/operations/proxmox-patch.md)を参照する。

<!-- SB-014 -->
guestはtagにより分類する。`prefer<node名>`があり`hacritical`がないguestはnon-HAとして明示migrationする。`hacritical`があるguestはHA管理としてmaintenance modeで退避し、復帰時は明示relocateする。tagなしguestは明示migration対象にしない。

<!-- SB-091 -->
退避完了後、対象nodeにrunning状態のguestを残さない。tagの有無や分類に関わらず、残存するrunning guestは強制停止する。これはtagなしguest向けの個別処理ではなく、migration失敗やHA退避漏れも捕捉する終端不変条件である。

<!-- SB-015 -->
pve2 apply前にdestination nodeとpve2のhealthcheck OK、guest分類・退避完了、pve2がapply / reboot可能という全条件を満たす。

<!-- SB-016 -->
pve1 apply前にpve1のrunning guest一覧化、必要guestのpve2退避、pve2が健康な退避先であること、pve1がapply / reboot可能という全条件を満たす。

<!-- SB-017 -->
各nodeのpatch、reboot、post-healthcheck完了後にそのnodeをrestoreし、最終的にhome配置、running状態、post-restore healthcheck OKのすべてを確認する。

<!-- SB-029 -->
post-healthcheck retryを許可するのは、reboot実施済みで結果が`CRITICAL`または`UNKNOWN`の場合だけである。rebootを伴わない`CRITICAL` / `UNKNOWN`はretryせず実障害として扱う。

<!-- SB-057 -->
`PATCH_READY`適用後にreboot-requiredを検出した場合は対象nodeを自動rebootし、SSH、Proxmox API、GUIの復帰を待ってpost-healthcheckを行う。OKの場合だけ次へ進み、`WARNING` / `CRITICAL`なら進まない。

<!-- SB-058 -->
`MAINTENANCE_REQUIRED`の週は自動・部分適用せず、毎週dry-runで再評価する。Urgencyが高くても、人間がmaintenance枠を確保してpve2から手動実施するか判断する。

### 5.2 BLOCKEDからの復帰

<!-- SB-060 -->
`BLOCKED`ではtimerを止め、apply playbookを禁止し、両nodeへ適用しない。Sophos稼働nodeを固定して不要な移動をせず、pve1の安定を最優先する。

<!-- SB-061 -->
simulation失敗時は通常flowを停止してrepository / apt sourceを修正し、dry-runが`PATCH_READY`または`MAINTENANCE_REQUIRED`へ戻るまでapplyしない。

<!-- SB-062 -->
置換先のない重要removeではその更新setを適用せず、repository / dependencyを修正し、重要remove予定が消えるまでapplyしない。

<!-- SB-063 -->
`apt-get check`失敗時は通常flowを停止してapt / dpkgを修復し、check成功までapplyしない。

<!-- SB-064 -->
major upgrade疑いでは通常flowを停止し、`MAJOR_UPGRADE_DETECTED`として別計画へ移し、pve2検証計画を作り、pve1を対象外にする。

<!-- SB-065 -->
通常patchへ戻すには、`apt-get check`成功、simulation成功、重要remove予定なしまたは置換として`MAINTENANCE_REQUIRED`分類可能、major疑いなし、healthcheck OK、dry-run Statusが`PATCH_READY`または`MAINTENANCE_REQUIRED`、という六条件をすべて満たす。

### 5.3 手動適用と復旧

<!-- SB-080 -->
cluster外control nodeからのfull flow、Proxmox上control nodeからの単一node flow、`MAINTENANCE_REQUIRED`手動applyはいずれも、該当するcontrol node条件(§2.3)、healthcheck、Status、guest退避、必要な明示確認、post-healthcheckを満たす。pve1はpve2成功後にだけ別途判断する。

<!-- SB-081 -->
Proxmox host OSのrollbackは原則行わない。壊れた場合は再インストールする。

<!-- SB-082 -->
node別の復旧手順と再構築に必要な情報を準備し、host設定はfile rollbackでなく再構築する。具体的な再構築情報は[Operations Context](../context/operations/proxmox-patch.md)を参照する。

<!-- SB-085 -->
Sophos停止によるnetwork影響を許容できる時間帯だけpatchし、必要なnetwork interface / segment割当を確認し、Sophos VM移動後に通信を確認する。手順は[Operations Context](../context/operations/proxmox-patch.md)を参照する。

## 6. 通知方針

<!-- SB-056 -->
停止時はsummary通知に停止理由を含め、週末中に対応する。

<!-- SB-069 -->
`NO_UPDATES`、`PATCH_READY`成功、`PATCH_READY`のpve2停止、`MAINTENANCE_REQUIRED`、`BLOCKED`、`MAJOR_UPGRADE_DETECTED`を通知する。停止・BLOCKED・MAJORは成功より強い表示にする。

<!-- SB-070 -->
- 成功通知: 各nodeのapply・post-healthcheck、reboot要否、更新package、必要最小限のchangelog要約を含める。
- pve2停止通知: 停止理由、pve1へ進んでいないこと、対応要否、失敗taskまたはhealthcheck、report pathを含める。
- `MAINTENANCE_REQUIRED`: Status、Urgency、理由、重要component、remove / install / upgrade関係、changelog要約、Roadmap要否、推奨action、分類結果を含める。
- `BLOCKED`: 適用禁止、timer停止、両node未適用、選択したcontingency route、復帰条件を含める。

changelog全文はreportへ保存し、通知本文には要約だけを載せる。

## 7. 制約・禁止事項

### 7.1 共通禁止と停止条件

<!-- SB-050 -->
applyが失敗したら次nodeへ進まない。

<!-- SB-051 -->
reboot後にSSH、Proxmox API、GUIが戻らなければ次nodeへ進まない。

<!-- SB-052 -->
post-healthcheckが`WARNING`または`CRITICAL`なら次nodeへ進まない。

<!-- SB-053 -->
apt / dpkg失敗、systemd failed unit、cluster・corosync・ZFS・replication異常のいずれかがあれば次nodeへ進まない。

<!-- SB-054 -->
VM / CTの退避失敗、復帰への影響、稼働への影響のいずれかがあれば次nodeへ進まない。

<!-- SB-055 -->
control nodeがtarget node上にあり継続不能なら次nodeへ進まない。

<!-- SB-059 -->
`MAINTENANCE_REQUIRED`をplaybookで手動applyする場合、playbook規定形式の明示的確認文字列を必須とし、確認がなければ停止する。

### 7.2 AIと実行場所

<!-- SB-067 -->
AI分類結果は最終判断の入力に限る。AIに`apt-get dist-upgrade`、`BLOCKED`解除、patch適用判断をさせない。

<!-- SB-073 -->
AIにupgrade、reboot、Proxmox host上の直接実行、Proxmox設定変更、`BLOCKED` / `MAJOR_UPGRADE_DETECTED`解除、Policyに反するStatus上書き、pve1 / pve2へのapply判断、apply timer有効化をさせない。

<!-- SB-075 -->
分類CLIはansy、quory、macOSだけで実行する。pve1、pve2、authy、Sophos Firewall VMでは実行・導入せず、Proxmox patch apply中に導入・更新しない。

<!-- SB-079 -->
control nodeがpatch対象node上にいる場合はapplyを停止する。control nodeがpve1 / pve2の両方のsequence中に停止し得る場所にある場合はfull flowを実行しない。

### 7.3 Sophos安全前提

<!-- SB-092 -->
Sophos Firewall VMも他のguestと同じ退避規則(SB-012、SB-018)に従う。稼働中であれば反対nodeへ退避してからpatchし、Sophos専用の退避除外や個別の移動可否判断を設けない。

<!-- SB-093 -->
Sophos Firewall VMのHA relocateはstop → migrate → startであり、VM再起動を伴う。この間はinternet接続が切断される。これは退避・復帰の仕様であり障害ではない。切断中はicmp / dns probeが連続失敗し得るため、自律復旧の誤発火防止は[autonomous_recovery_policy.md](autonomous_recovery_policy.md)が定めるmute契約に依拠する。patch系playbookの自動muteが設定されていることを確認し、muteなしでSophos稼働nodeのpatchを進めない。

## 8. 変更履歴

| 日付 | 変更 |
|---|---|
| 2026-07-26 | 夏季pve1平日シャットダウン運用でdry-runが機能しない問題を受け、SB-023(pve1 / pve2固定pair限定、単一node実行禁止)を廃止し、到達・healthcheck OKなnodeが1node以上あれば開始する条件分岐へ改めたSB-094へ置き換え。両node到達不能時は明確なエラーで停止すること、単一node dry-runの`PATCH_READY`がapply側fixed-pair gate条件(SB-027、SB-028、SB-032)を満たさないことをSB-094内に明記。apply側(SB-027、SB-028、SB-032)の両node要求(drift回避)は変更していない。退番: SB-023(再利用しない) |
| 2026-07-25 | 移行完了済みのSophos前提(SB-083、SB-001の1 bullet、SB-060 / SB-085の条件節)を削除し、退避の一般規則で足りるSB-084とUrgency判断境界のないSB-086を廃止。代わりにHA relocateによるVM再起動・internet断とautonomous_recovery_policyのmute契約への依拠をSB-092 / SB-093として明記。定義が存在しない`Mode A` / `Mode B`参照および汎用形の「Mode別」表記を条件記述へ統一(Operations Contextの該当見出しも同時に改称)。冗長かつ曜日が事実誤りのSB-049を削除。SB-014を分類規則と終端不変条件(SB-091)へ分離。退番: SB-049 / SB-083 / SB-084 / SB-086(再利用しない) |
| 2026-07-24 | v2.0の安全境界を維持したまま標準8節へ再編。実装、運用、環境、時点依存計画をContext / reviewへ分離し、旧§22を付録Aへ移した |
| 2026-05-09 | v2.0作成 |

## 付録A 出典

- [Proxmox VE System Software Updates](https://pve.proxmox.com/wiki/System_Software_Updates)
- [Proxmox VE Roadmap / Release Notes](https://pve.proxmox.com/wiki/Roadmap)
- [Proxmox Security Advisories Forum](https://forum.proxmox.com/threads/official-proxmox-security-advisories-forum-available.149771/)
- [Debian Security Tracker](https://security-tracker.debian.org/)
- [Codex CLI](https://developers.openai.com/codex/cli)
- [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive)
