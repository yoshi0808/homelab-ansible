# Log / Observability Policy

本書はhomelabの集中log収集、保全、検索に関する許可、禁止、停止条件、判断軸の正本である。current topologyとrepository構成は対応Contextを参照し、競合時は本Policyを優先する。

## 1. 目的

<!-- LOG-001 -->
本Policyはlogの収集・保全・検索を扱い、service障害の検知・復旧を扱うautonomous recoveryとは目的を分離する。

<!-- LOG-002 -->
現行scopeはlogの収集・保全・検索である。log-based alertは現行scopeに含めない。

## 2. 対象と実行範囲

<!-- LOG-003 -->
collection pathはLokiへ至る一本に統一し、目的別の別collection pipelineを建てない。

<!-- LOG-005 -->
log agentはGrafana Alloyに統一し、EOLのPromtailを現行agentとして扱わない。

<!-- LOG-006 -->
syslogだけを送信できるapplianceはmonnieのaggregation pointへ送る。

<!-- LOG-007 -->
monnieではlocal Alloyがjournalとrsyslog outputを読み、local Lokiへpushする。

<!-- LOG-008 -->
remote Linux hostはjournaldからlocal rsyslogを経てmonnieの同一受信funnelへ合流する。

<!-- LOG-009 -->
Lokiへwriteするagentはmonnie local Alloyだけに限定する。

<!-- LOG-012 -->
CloudKeyのsender settingはGUI管理とし、Ansibleが直接編集しない。

<!-- LOG-013 -->
Sophosのsender settingはGUI管理とし、repositoryはreceiver readinessまでを管理する。

<!-- LOG-014 -->
Proxmox nodeのsender configurationはmanual管理とし、Ansible管理対象へ含めない。

<!-- LOG-015 -->
Ubuntu senderはsender role、monnie receiverはAlloy roleで管理する。

<!-- LOG-029 -->
Lokiへのpushはmonnie localhostへ限定する。

source、現行stream、管理ownerの具体構成は [System Context](../context/system/monitoring.md)、playbook / role / configの横断関係は [Repository Context](../context/ansible/log-observability.md) を参照する。

## 3. 対応するPlaybook

次の2入口を関連indexとして列挙する。列挙自体はAPPLYの許可を意味せず、各tester-gateと人間gateを満たす場合に限る。

| Playbook | 主role | Policy上の役割 |
|---|---|---|
| `alloy_setup.yml` | `alloy` | monnie receiver、Alloy config、validated cutover |
| `rsyslog_forward_to_monnie.yml` | `rsyslog_forward_to_monnie` | Ubuntu senderのsingle-host rollout |

<!-- LOG-032 -->
両入口はcheck-mode-nativeである。APPLYはproduction logging pathを変更するためYoshinobuの明示判断を必要とする。

## 4. 判断軸

### streamとlabel contract

<!-- LOG-016 -->
CloudKey streamは`unifi`のlabel contractで扱う。

<!-- LOG-017 -->
network-device streamはlog本文からhostをdynamic抽出する。

<!-- LOG-018 -->
Proxmox streamはnormalized lineからhostをdynamic抽出する。

<!-- LOG-019 -->
Sophos streamはstatic host contractを使う。

<!-- LOG-020 -->
Ubuntu remote streamはnormalized lineからhostをdynamic抽出する。

<!-- LOG-021 -->
monnie journalはsystem streamとし、systemd unitをrelabelする。

<!-- LOG-022 -->
`level`は`error`、`warning`、`info`、`debug`の4値に限定する。

<!-- LOG-023 -->
journal priorityは定義済みの対応により4 levelへ分類する。

<!-- LOG-024 -->
normalized sourcesはrsyslogがlevelを行頭へ確定し、Alloyが抽出する。

<!-- LOG-025 -->
UniFi sourcesは明示severityを安全に認識できる場合だけbest-effortでlevelを付与し、不明な行を誤分類しない。

<!-- LOG-026 -->
normalized file sourcesはlevel / hostをlabel化した後、Lokiへmessage本文だけを保存する。

<!-- LOG-027 -->
monnie journalは観測stackのexact unitかつ`info`または`debug`の場合だけ収集前にdropする。

<!-- LOG-028 -->
warning / errorは保持し、remote file sourcesへmonnie固有self-noise dropを適用しない。

<!-- LOG-030 -->
統合dashboardはquery / display上限とwarning+error defaultを維持し、info/debugを利用者が明示選択できるようにする。

<!-- LOG-031 -->
dashboardのhost / search filtersとhostを含むline formatを維持する。

### version、resolution、cutoverの合格条件

<!-- LOG-034 -->
Alloy major update疑いはmonthly apt判断でhuman reviewへ上げる。

<!-- LOG-037 -->
sender nameはdeployment時にresolveし、配置済みallowlistがDNSを自動再解決する前提を置かない。

<!-- LOG-039 -->
package / unit / user / storage / CLI contractとcandidate config validationが合格した場合だけPromtail停止とAlloy開始へ進む。

<!-- LOG-041 -->
positionsはPromtailから移植せず、既存sourceと新規sourceで定義されたtail startを使い、cutover境界の小さなgap / overlapを受容する。

<!-- LOG-042 -->
Alloy activeだけを成功条件にせず、journal streamの実dataがLokiへ到達することを確認する。

## 5. ライフサイクル・処理フロー

<!-- LOG-033 -->
Alloyはexisting Grafana repositoryからrole管理でinstallし、setup入口のpackage stateはpresentとしてversion-upを行わない。

<!-- LOG-036 -->
existing UniFi rsyslog configurationを変更せず、追加sourceは別configurationで管理する。

<!-- LOG-038 -->
sender addressが変わった場合はsetup入口を再実行してallowlistを更新する。

receiver cutoverは次の順序を維持する。

1. package auto-startを抑止する。
2. runtime contractとcandidate configurationを検証する。
3. 合格時だけPromtailをstop / disableする。
4. Alloyをstartしてactive、ready、runtime log、real streamを検証する。

<!-- LOG-040 -->
Alloy startまたはruntime validationに失敗した場合はPromtailをrestoreし、Promtail package / config / positionsをrollback用に維持する。

<!-- LOG-043 -->
production cutover等の変更前にはmonnieのautonomous recoveryをmuteし、終了後の確認と解除は既存Operations Contextに従う。

sender rolloutは一度に1 hostだけを対象にし、前段のend-to-end確認後に次hostへ進む。具体順序とsingle-task実装はRepository Contextとcodeを正本とする。

## 6. 通知方針

<!-- LOG-047 -->
該当なし（未実装）。

## 7. 制約・禁止事項

<!-- LOG-010 -->
remote hostへAlloy / Loki credentialやGrafana repositoryを広げず、unauthenticated Loki portをnetworkへ公開しない。

<!-- LOG-011 -->
rsyslogをsyslog aggregationとsource allowlist / routingに維持し、Alloy direct syslog receiveへ置換しない。

<!-- LOG-035 -->
Alloy configurationはGit / roleを正本とし、hostで直接編集しない。

<!-- LOG-048 -->
syslog transportはplaintextであり、eavesdroppingとsender spoofingのriskがある。source allowlistはroutingであってauthenticationではない。

<!-- LOG-049 -->
TLSは対応可能なsenderだけのfuture optionであり、applianceのplaintext transportが残ることを認識する。

<!-- LOG-050 -->
collectionはLoki一本に統一する。

<!-- LOG-051 -->
rsyslogをaggregation roleとして維持する。

<!-- LOG-052 -->
現scopeでLoki / UFWを変更せず、Loki endpointをremoteへ公開しない。

<!-- LOG-053 -->
Alloy configurationのhost直接編集を禁止する。

<!-- LOG-054 -->
production APPLYはhuman gateとし、testerは既定でAPPLYしない。

<!-- LOG-055 -->
secretまたはIP literalをrepositoryへ記載せず、runtime validationはtester工程へ分離する。

<!-- LOG-056 -->
log volumeとmonitoring nodeのcapacityを継続観測し、retention / capacity変更を別reviewで扱う。

<!-- LOG-057 -->
Proxmox node local Alloy + remote Loki push案は採らない。unit精度またはdelivery guaranteeが必須になった場合だけ再検討する。

<!-- LOG-058 -->
systemd-journal-remote案は採らない。

<!-- LOG-059 -->
Alloy direct syslog receive案は採らない。

<!-- LOG-060 -->
monnie receiverはAnsible / Git、Proxmox senderはmanual、appliance senderは各GUIというmanagement boundaryを維持する。

## 8. 変更履歴

| 版 | 日付 | 変更 |
|---|---|---|
| v1.0 | 2026-07-16 | PromtailからAlloyへのPhase 1移行を契機にPolicyを新設 |
| v2.0 | 2026-07-17 | remote syslog funnelと4-value severity contractを追加 |
| v2.1 | 2026-07-18 | Ubuntu sources、self-noise suppression、message-only body、dashboard defaultsを更新 |
| v2.2 | 2026-07-25 | 標準8節へ再編しcurrent factsをContextへ分離。notificationは未実装と明記 |

<!-- LOG-004 -->
log-based Slack alertはlabels / alert rulesをcollection plane上へ載せるPhase 3構想であり、現行機能ではない。

<!-- LOG-044 -->
2026-07-16のPhase 1完了はhistorical resultとして保持し、現行notification contractにしない。

<!-- LOG-045 -->
2026-07-17時点のPhase 2実装済み / validation待ち状態は時点履歴として本書の現行状態へ固定しない。

<!-- LOG-046 -->
2026-07-17から18のPhase 2 extension稼働・是正は時点履歴として扱う。

<!-- LOG-061 -->
過去の実機PASSとknown non-blocking事象は [Phase 1 investigation](../reviews/policy_standardization/2026-07-25_021_investigation_remaining_policies_rewrite.md) に保持し、現行の許可条件へ昇格させない。
