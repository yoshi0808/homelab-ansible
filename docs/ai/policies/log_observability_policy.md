# Log / Observability Policy

本書はhomelabの**観測プレーン** — 集中log収集・保全・検索と、**dashboard / alert ruleの配備方式** — に関する許可、禁止、停止条件、判断軸の正本である(2026-07-30のv4.0でscopeをsyslog収集から観測プレーン全体へ拡張した。経緯はLOG-074)。current topologyとrepository構成は対応Contextを参照し、競合時は本Policyを優先する。

**発火条件の「値」は本書に書かない。** provisioning YAML自身が正本であり、本書が持つのは管理の作法だけである(LOG-078〜LOG-081)。

## 1. 目的

<!-- LOG-062 -->
homelabのsyslogを収集・正規化・保存し、**異常の能動的な検知と予兆の把握**に用いる。事後追跡だけを目的とせず、問題が顕在化する前に気づける状態を目指す。

### 検知の2系統と本Policyの範囲

<!-- LOG-063 -->
homelabの観測は次の2系統からなる。**本Policyは、両系統の収集経路と、両系統の可視化・検知定義の「配備方式」に規範を持つ**(2026-07-30改訂、v4.0)。系統ごとの**検知内容**(どのシグナルをどの条件で拾うか)の規範は系統別に置き、syslog系統は本Policy §4、metrics系統はprovisioning YAML自身が正本である(LOG-078)。

| 系統 | 収集 | 保存 | 検知の現状 |
|---|---|---|---|
| metrics | unpollerがネットワーク機器から収集 | Prometheus | **運用中**。Grafanaのalert ruleがport dropとerrorを検知して通知する。**2026-07-30以降、定義はrepoのprovisioning YAMLが正本**(LOG-078〜LOG-084) |
| syslog | rsyslogとGrafana Alloy | Loki | **未実装**。蓄積内容の事後参照に留まる |

<!-- LOG-064 -->
系統の使い分けは設計思想ではなく**パッケージの制約**による。unpollerがPrometheus形式で公開するためmetricsはPrometheusを使い、syslogを送る対象はLokiで受ける。同一機器が両系統に現れることは重複ではない。

<!-- LOG-065 -->
metrics系統では、通知の**発生頻度そのものを運用者が判断材料に使う**。少数の発火は様子見とし、同一portのdropが頻発する場合に問題ありと判断する。**この解釈は「障害判断の基準」であり、「発火条件」とは別の概念である**(用語の定義はLOG-079)。発火条件には表現されず人間の判断に属する。

**この非対称は意図的な設計であり、調整不足ではない。** 現行4ルールは「素朴な発火条件 + 人間側の障害判断」という組み合わせで成立している(2026-07-30、`docs/ai/adr/007-grafana-provisioning-as-code.md` 設計判断8)。障害判断の一部を発火条件側(`for`・rate窓・port別)へ移すことは可能だが、**移した分だけ根拠を書く義務が発火条件側へ移る**(LOG-081)。移す判断はYoshinobuが行う。

### syslog系統で将来検知したい対象

<!-- LOG-066 -->
syslog系統の検知対象として、portのflappingと接続断の繰り返しを想定する。これらはmetricsの閾値では表れにくく、ログの発生パターンとして現れるため、syslog側で扱う適性がある。

<!-- LOG-067 -->
syslog系統の検知が未実装である理由は、閾値の時期尚早な設定を避け実データの蓄積を待つためである。実装時期は蓄積状況を見て判断する。設計の起点は [Phase 3 alerting requirement](../reviews/promtail_to_alloy/2026-07-19_phase3_alerting_requirement.md) とする。

<!-- LOG-001 -->
本Policyはlogの収集・保全・検索を扱い、service障害の検知・復旧を扱うautonomous recoveryとは目的を分離する。

## 2. 対象と実行範囲

### 収集対象

<!-- LOG-068 -->
syslog系統の収集対象は次の8つとする。対象の追加・削除はrole varsの変更を伴うため、本一覧を更新したうえで行う。

| 対象 | 到達経路 | Lokiのjob |
|---|---|---|
| `monnie` | 自ホストのjournalをlocal Alloyが読む | system stream |
| `ansy` / `quory` / `authy` | 各hostのrsyslogがmonnieへ転送 | `ubuntu-nodes` |
| `pve1` / `pve2` | 同上 | `pve-nodes` |
| `sophos-fw` | 同上 | `sophos-fw` |
| CloudKey | applianceがmonnieへ送信 | `unifi` |
| UniFiネットワーク機器 | applianceがmonnieへ送信 | `network-devices` |

<!-- LOG-069 -->
UniFiネットワーク機器はmetrics系統にも現れるが、metricsは機器の稼働状態、syslogは機器が出力したイベント本文を扱うため役割が異なる。

### 収集するseverity

<!-- LOG-070 -->
収集するlevelは`error`、`warning`、`info`の3値とする。`info`は予兆監視のために保持する。

<!-- LOG-071 -->
`debug`は収集しない。当初はlogが出力されない事象の切り分けのために収集していたが、その必要は解消した。debugを要する事象が再発した場合は、一時的に収集を有効化して再現させる方式をとり、常時収集へ戻さない。

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

### 可視化・検知定義の対象範囲

<!-- LOG-088 -->
配備方式(LOG-078〜LOG-086)が対象とするresourceは次のとおりである。対象の追加・削除はrole varsの変更を伴うため、本一覧を更新したうえで行う(収集対象のLOG-068と同じ規律)。

| resource | 対象ホスト | 正本の場所 | provider / 配備単位 |
|---|---|---|---|
| UniFi metrics dashboard 7枚 | `monnie` | `roles/grafana_provisioning/files/dashboards/unifi-*.json` | dashboard provider `unifi`(folder `UniFi`) |
| syslog統合dashboard 1枚 | `monnie` | `roles/grafana_provisioning/files/dashboards/infra-syslog-all-nodes.json` | dashboard provider `infra-syslog`(folder = root) |
| UniFi switch port alert rule 4件 | `monnie` | `roles/grafana_provisioning/files/alerting/unifi-switch-port-errors.yaml` | alerting provisioning(folder `UniFi`) |

<!-- LOG-089 -->
**dashboard providerの名前を変更しない。** Grafanaはprovider名を `grafana.app/managerId` としてリソースの所有者識別子に使う(2026-07-30実測)。改名すると既存リソースとの所有関係が切れ、孤児化・UID変化・folder所属の変化を招きうる。

source、現行stream、管理ownerの具体構成は [System Context](../context/system/monitoring.md) を参照する。playbook / roleは`playbooks/*.yml`・`roles/*`を直接参照する(`docs/ai/context/ansible/repository-overview.md`)。config、template、dashboard JSONの実体はcodeを正本とする。

## 3. 対応するPlaybook

次の3入口を関連indexとして列挙する。列挙自体はAPPLYの許可を意味せず、各tester-gateと人間gateを満たす場合に限る。

| Playbook | 主role | Policy上の役割 |
|---|---|---|
| `alloy_setup.yml` | `alloy` | monnie receiver、Alloy config、validated cutover |
| `rsyslog_forward_to_monnie.yml` | `rsyslog_forward_to_monnie` | Ubuntu senderのsingle-host rollout |
| `grafana_provisioning.yml` | `grafana_provisioning` | **dashboardとalert ruleのrepo正本化・配備**(2026-07-30追加、LOG-078〜LOG-086) |

<!-- LOG-032 -->
**3入口すべてcheck-mode-nativeである。** APPLYはproduction logging pathまたは観測プレーンの定義を変更するためYoshinobuの明示判断を必要とする。

<!-- LOG-087 -->
**`grafana_provisioning.yml` の起動はタグで用途が分かれ、restartの有無が変わる。** `--tags dashboards` はdashboard JSONの複製のみでrestartを伴わない。provider定義とalerting YAMLの配備はrestartを伴い、**`--tags provider,alerting` を1回で実行する**(別々に流すとrestartが2回発生する)。alerting配備は `never` タグにより明示指定がない限り実行されない。起動例の正本はplaybookのヘッダコメント。

## 4. 判断軸

### streamとlabel contract

<!-- LOG-072 -->
Lokiへは`job`と`host`と`level`をlabelとして与え、**本文はmessageだけを保存する**。labelは検索の軸であり、本文へ重複させない。`job`はsourceの種別を、`host`は発生元を、`level`はseverityを表す。

`host`の与え方はsourceによって2通りある。単一機器から届くstreamは固定値を与え、複数hostが1つのfileへ合流するstreamはlog本文から抽出する。以下のLOG-016からLOG-021がその割り当てである。

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
`level`は`error`、`warning`、`info`の3値に限定する(LOG-070、LOG-071)。

<!-- LOG-023 -->
journal priorityは定義済みの対応により上記3 levelへ分類する。debug相当のpriorityは収集しない。

<!-- LOG-024 -->
normalized sourcesはrsyslogがlevelを行頭へ確定し、Alloyが抽出する。

<!-- LOG-025 -->
UniFi sourcesは明示severityを安全に認識できる場合だけbest-effortでlevelを付与し、不明な行を誤分類しない。

<!-- LOG-075 -->
LOG-025の帰結として、**UniFi由来の行の多くは`level`ラベルを持たない**。2026-07-26の実測で、monnieのrsyslogは受信時に行を書き換えており、送信元が持っていたseverity(`daemon.notice`等)は保存される行から消える。したがってbest-effort判定が参照できるseverityトークンが存在せず、Lokiでは`detected_level`が`unknown`になる。これは仕様どおりの動作であり異常ではない。

<!-- LOG-076 -->
LOG-075の帰結として、`level`を条件に含むLogQLセレクタは**UniFi / network-devices由来のイベントを一切返さない**。LogQLのlabel matcherはlabelが存在するstreamにしか適用されないため、Severityで何を選んでも該当しない。LOG-066の検知を設計する際は`level`でフィルタせず、`job`と`host`とmessage本文で特定する。実測の詳細は [Link Up/Down調査](../reviews/promtail_to_alloy/2026-07-26_030_investigation_unifi_linkup_level_match.md) を参照する。

<!-- LOG-077 -->
統合dashboardは、`level`を持つsource(Ubuntu / PVE / Sophos / CloudKey)と持たないsource(UniFi network devices)をpanel単位で分離する。前者はSeverityフィルタを適用し、後者は適用しない。両者を同一panelへ混在させるとSeverityフィルタの意味が曖昧になり、かつLOG-076によりnetwork-devices側が常に非表示になる。Event Timelineも同様に2系列へ分け、network-devices側を`level`非依存とする。

<!-- LOG-026 -->
normalized file sourcesはlevel / hostをlabel化した後、Lokiへmessage本文だけを保存する。

<!-- LOG-027 -->
monnie journalは観測stackのexact unitかつ`info`の場合だけ収集前にdropする。観測stack自身のnoiseを抑えるための限定的な例外であり、unit名を明示せずまとめてdropしない。

<!-- LOG-028 -->
warning / errorは保持し、remote file sourcesへmonnie固有self-noise dropを適用しない。

<!-- LOG-030 -->
統合dashboardはquery / display上限とwarning+error defaultを維持し、`info`を利用者が明示選択できるようにする。

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

sender rolloutは一度に1 hostだけを対象にし、前段のend-to-end確認後に次hostへ進む。具体順序とsingle-task実装はcodeを正本とする。

## 6. 通知方針

<!-- LOG-047 -->
**syslog系統からの通知は未実装である。** Loki を参照する alert rule、Loki ruler、Alertmanagerのいずれも配備していない。dashboardに記載されたPhase 3のalert説明は将来設計のnoteであり、現行の通知契約ではない。

**2026-07-30の改訂で「本Policy対象の2 playbook / 2 roleでは配備しない」という限定を外した。** `playbooks/grafana_provisioning.yml` が alert rule を配備するようになったため、「配備しないplaybook」を数え上げる形の記述では未実装であることを表現できなくなった。**未実装であるかどうかは、配備されている alert rule の datasource が Loki を参照しているかで判断する** — 現行の4ルールはすべてPrometheus参照(metrics系統)である。

<!-- LOG-073 -->
**退番(2026-07-30、v4.0)。再利用しない。** 旧内容は「metrics系統の検知ルールと通知経路の規範は本書で定義せず将来別Policyで扱う」「alert ruleの実体はGrafana UI側にありGit管理外であるため、リポジトリ内の記述をもって現在有効な検知内容と判断しない」だった。**後半は2026-07-30に事実として偽になった** — alert ruleはrepoのprovisioning YAMLが正本になり、Grafana UIからは編集できない(`provenance = file`)。前半の方針もYoshinobu判断で撤回した(LOG-074)。

<!-- LOG-074 -->
**方針を変更した(2026-07-30、v4.0)。** 旧内容は「収集を扱う本Policyへ検知ルールを追記せず、検知と通知を扱う別Policyへ集約する」だった。

Yoshinobu判断(2026-07-30): 「policyファイルは更新しておいた方が良いと思います。`log_observability_policy.md`は、今は基盤の話であり、ダッシュボードの概念はここに含めても良いのではないでしょうか」

**別Policyへ分離せず、本Policyのscopeを観測プレーン全体へ広げる。** 判断根拠は3つある。

1. ファイル名が `log_observability_policy` であり、**Observabilityを名乗りながら本文がsyslog収集に限定されていた**。scope拡張は名称との整合を回復する方向である。
2. **dashboardの規範は既に本Policyに存在していた**(LOG-030 / LOG-031 / LOG-077、および§2末尾「dashboard JSONの実体はcodeを正本とする」)。ただし対象はsyslog統合dashboardに限られ、UniFi metrics dashboard 7枚はどのPolicyにも現れていなかった。
3. 通知経路(Grafana)は両系統で共通であり、配備方式も共通化された(単一role `roles/grafana_provisioning`)。**規範を分けると同じことを2箇所に書くことになる。**

**ただし本Policyが持つのは「配備方式」と「管理の作法」だけであり、発火条件の値は持たない**(LOG-078〜LOG-081)。

### 観測プレーンの配備方式(2026-07-30新設、v4.0)

設計判断の正本は `docs/ai/adr/007-grafana-provisioning-as-code.md`。案件記録は `docs/ai/reviews/grafana_provisioning/`。

<!-- LOG-078 -->
**Grafanaのdashboardとalert ruleは、repoを正本としAnsibleのfile provisioningで配る。** 実装は単一role `roles/grafana_provisioning` と入口 `playbooks/grafana_provisioning.yml`。**手作業のUI importとホストへの直接配置を経路として認めない。** provisioning YAML / dashboard JSON そのものが定義の正本であり、Policyへ値を複製しない(`docs/ai/core.md`「値を二重に持たない」)。

<!-- LOG-079 -->
**「発火条件」と「障害判断の基準」を別の概念として扱い、どちらも単に「閾値」と呼ばない。** 1つの語が2つの世界を指すことが、この論点を曖昧にしていた(2026-07-30 Yoshinobu提起)。

| 用語 | 何を決めるか | 正本 | 属する世界 |
|---|---|---|---|
| **発火条件** | PromQL / LogQL、比較値、評価間隔、`for` | provisioning YAML(repo) | **仕様**。根拠つきでrepoに残す |
| **障害判断の基準** | 発火の頻度を見て障害扱いにするか | 人間の判断(LOG-065) | **運用**。Policyにも仕様にも書かない |

<!-- LOG-080 -->
**発火条件は仕様として管理する。** 「Policyに値を書かない」は「管理しない」ではない — **provisioning YAML そのものが仕様書**であり、git管理・レビュー・diffの対象になる。Policyが規定するのは管理の作法(正本の所在、根拠の併記義務、UI編集を認めないこと)だけである。

<!-- LOG-081 -->
**発火条件を新設・変更するときは、値とあわせて根拠を残す。** 根拠とは算出クエリ・観測期間・**反実仮想の発火回数**(「この条件なら直近N日で何回発火していたか」)である。値だけを残すと、次に見た人が「なぜこの値か」を再構成できない — 本案件が解消した属人性がそのまま再発する。**調整の手順は [Operations Context: Grafana発火条件の調整サイクル](../context/operations/grafana-alerting-tuning.md) を参照する**(非規範。誰が何を決めるかの分担を含む)。

<!-- LOG-082 -->
**配備は複製に限り、配備時の変換・生成を行わない。** `ansible.builtin.copy` を使い `template` を使わない。gitにあるものとホストにあるものが一致する状態を保ち、SHA256突合を成立させる。**上流ダッシュボードのdatasource参照書き換え(UID化)は「取り込み時」の工程であり、配備時ではない。**

<!-- LOG-083 -->
**nameベースのdatasource参照を配備前に機械的に拒否する。** `${DS_...}` プレースホルダと、文字列型の `.datasource` 値の両方を検出したらpreflightで停止する。2026-07-12にGrafana 13.1でnameベースfallback解決が廃止され全パネルが描画不能になった事故と同一の欠陥クラスであり、**復旧はProxmox VMバックアップからの復元を要した**。この環境ではdatasourceの登録名を変更できないため(unpollerが送りprometheusとして登録される)、UID参照が唯一の正しい形である。判定条件の詳細は `docs/ai/reviews/grafana_provisioning/2026-07-30_001_requirement.md` R3の判定表。

<!-- LOG-084 -->
**notification policy treeとcontact pointをprovisioningで変更しない。** alerting YAMLのtop-levelキーは `apiVersion` と `groups` のみとし、`policies` / `resetPolicies` / `contactPoints` / `deleteContactPoints` を書かない。Slackへの到達は各ruleの `notification_settings.receiver` で行う(root policyの receiver は `empty` で child route を持たないため、labelによるroutingは成立しない)。非回帰は `alert_configuration.configuration_hash` の不変で機械的に示す。

<!-- LOG-085 -->
**Grafanaのexport機能で既存のdashboard正本を作り直さない。** ディスク上にclassic形式の原本が存在するdashboardについて、Grafana UIのexportはschema移行後の内容を出す(2026-07-30実測: UniFi Switchesで18パネル中15枚のpanel型が書き換わり、`links`・`timeFrom`・`cacheTimeout` 等が消える)。クエリは保たれるが**体裁設定が気づかれにくい形で失われる**。**正本はディスク上の原本であり、Grafanaの出力ではない。** exportを使うのは、classic原本が存在しないdashboardをclassic化する場合に限る。

<!-- LOG-086 -->
**reloadはサービスrestartで行い、admin資格情報やservice account tokenを新設しない。** 反映機構は配る物ごとに異なる — dashboard JSONはproviderが `updateIntervalSeconds` 間隔でpollするため**restart不要**、provider yamlとalerting YAMLは起動時読み込みのため**restart必要**。restart前には `roles/recovery_mute` でmonnieのmute窓を張り、自律復旧の誤発火を防ぐ(monnieは `recovery_push_targets` で `grafana-server` を復旧対象に含む)。実行時刻は `ubuntu_nightly` のmonnie処理時間帯と重ねない。

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

### 時点履歴を現行契約に昇格させない

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

## 8. 変更履歴

| 版 | 日付 | 変更 |
|---|---|---|
| v1.0 | 2026-07-16 | PromtailからAlloyへのPhase 1移行を契機にPolicyを新設 |
| v2.0 | 2026-07-17 | remote syslog funnelと4-value severity contractを追加 |
| v2.1 | 2026-07-18 | Ubuntu sources、self-noise suppression、message-only body、dashboard defaultsを更新 |
| v2.2 | 2026-07-25 | 標準8節へ再編しcurrent factsをContextへ分離。notificationは未実装と明記 |
| v3.0 | 2026-07-26 | Yoshinobuとの対話で目的を確定し全面補強。§1へ「異常の能動的検知と予兆把握」という目的と、metrics系統(運用中・本Policy対象外)とsyslog系統(未実装・本Policy対象)の2系統分離を新設(LOG-062〜067)。§2へ収集対象8つの一覧とseverity契約を新設し、`debug`を収集対象から除外(LOG-068〜071)。§4冒頭へlabel contractの前提となる全体規約を追加(LOG-072)。§6を実態に合わせ、metrics系統が運用中である事実とGit管理外である制約、将来の検知Policy分離方針を明記(LOG-073、LOG-074)。変更履歴の後ろに浮いていたLOG-004 / 044 / 045 / 046 / 061を§7へ移動。severity 4値→3値に伴いLOG-022 / 023 / 027 / 030を修正。退番: LOG-002(「log-based alertは現行scopeに含めない」は新しい目的と矛盾するため削除、再利用しない) |
| v3.1 | 2026-07-26 | UniFiスイッチのLink Up/Down実測(Normal設定)を受け、LOG-025の帰結を明文化。monnieのrsyslogが受信時に行を書き換えるためseverityトークンが消え、UniFi由来の行の多くが`level`未設定になる事実をLOG-075として記録。LOG-030の既定フィルタと組み合わせると既定表示に現れないため、LOG-066の検知設計では`level`でなく`job`/`host`/message本文で特定すべきことをLOG-076として明記。構造・実装の変更はなし |
| v3.2 | 2026-07-26 | UniFiスイッチのLink Up/Downを実dashboardで確認できるようにした対応を反映。LOG-076を実態に合わせて修正(既定フィルタの問題ではなく、`level`条件を含むセレクタが該当streamを一切返さない)。`level`保有source と非保有source をpanel単位で分離する規範をLOG-077として追加。実装は`infra_syslog_all_nodes.json`のpanel分割(Infra Events (Ubuntu / PVE / Sophos/uckg2) と Network Device Events)およびEvent Timelineの2系列化。旧`network_device_syslog.json`は役割を統合dashboardへ移したため削除。Lokiの全データをクリアし3値契約のみで再蓄積を開始(記録: 031) |
| **v4.0** | **2026-07-30** | **scopeをsyslog収集から観測プレーン全体へ拡張**(Yoshinobu判断: 「`log_observability_policy.md`は、今は基盤の話であり、ダッシュボードの概念はここに含めても良いのではないでしょうか」)。冒頭とLOG-063を書き換え、metrics系統の配備方式を対象に含めた。**LOG-073を退番**(「metrics系統の規範は本書で定義せず将来別Policyで扱う」および「alert ruleの実体はGrafana UI側にありGit管理外」 — 後者は本改訂の契機となった案件で**事実として偽になった**)。**LOG-074を方針変更**(別Policyへの分離を撤回し、本Policyへ統合。理由3点を条項内に明記)。LOG-065へ「発火条件」と「障害判断の基準」の区別を追加(非対称は意図的な設計であり調整不足ではない)。LOG-047の「本Policy対象の2 playbook / 2 roleでは配備しない」という限定を外し、**Loki参照かどうかで未実装性を判断する**形へ変更(`grafana_provisioning.yml`がalert ruleを配備するようになったため、playbookを数え上げる形では表現できなくなった)。§3へ`grafana_provisioning.yml`を追加しLOG-032を3入口へ更新、LOG-087で起動とrestartの関係を明記。§2へ**LOG-088**(可視化・検知定義の対象範囲一覧)と**LOG-089**(provider名を変更しない)を追加。**LOG-078〜LOG-086を新設**(配備方式、用語定義、根拠併記義務、複製に限る原則、nameベース参照の拒否、policy tree非改変、export禁止、reload方式)。設計判断の正本は`docs/ai/adr/007-grafana-provisioning-as-code.md`、案件記録は`docs/ai/reviews/grafana_provisioning/` |
