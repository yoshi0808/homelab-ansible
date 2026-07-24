# 残り6文書の標準構造書換 Phase 1 調査

## 1. 調査範囲とsnapshot

- requirement: `2026-07-25_020_requirement_remaining_policies_rewrite.md`
- snapshot commit: `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`
- Phase 1の編集: 本021の新規作成だけ
- 未実施: 6文書、Context、playbook、role、config、map、requirementの編集、実機・Ansible実行

| 文書 | HEAD blob | 行数 | Phase 2方針 |
|---|---|---:|---|
| `docs/ai/core.md` | `b856a4efc9fbb237c878a3dd2bcab9f8413207e4` | 92 | 現構造を維持し、変更履歴だけを追加 |
| `log_observability_policy.md` | `c1a67206d89749cf3987e5395a085067ffb84bbf` | 117 | 標準8節へ全量再編 |
| `cert_renew_cloudkey_policy.md` | `400c591fd1ae8f8e7ecd739e5d52213f33858490` | 275 | 標準8見出しへ統合、意味変更なし |
| `cert_renew_policy.md` | `f54bc62f80c36f476089bc01c90b4f93bb2cf327` | 253 | 標準8見出しへ統合、意味変更なし |
| `time_sync_check_policy.md` | `6422d22e35fa26bf00d2f4a845d6b7390107beba` | 176 | 標準8見出しへ統合、意味変更なし |
| `unifi_backup_fetch_policy.md` | `8445dd53ac1ae189815955975d04e48032fc8b91` | 217 | 標準8見出しへ統合、意味変更なし |

行番号はすべて上記HEAD snapshotの1始まりである。IP、VLAN ID、VM ID、認証情報、秘密情報の実値は本書へ転載しない。既存文書にあるaccount名、credential保管path、秘密資材pathはPhase 2で変数名またはcode / Vaultを正本とする表現へ置き換え、許可・禁止・停止条件は維持する。

## 2. core.md

### 2.1 構造計画

個別Policy用の標準8節は適用しない。現行の9見出し、順序、本文を維持し、末尾へ `## 変更履歴` だけを追加する。対応Playbook、ライフサイクル、通知方針は個別業務を定義しないため該当なしであり、見出しを新設しない。

| 現行見出し | 現行行 | Phase 2 |
|---|---:|---|
| 目的と正本 | L5-14 | 見出し・内容維持 |
| 人間の権限と安全境界 | L16-24 | 見出し・内容維持 |
| 開発と本番の境界 | L26-37 | 見出し・内容維持 |
| 公開情報と秘密情報 | L39-46 | 見出し・内容維持 |
| 作業時に読む情報 | L48-60 | 見出し・内容維持 |
| Role・Skill・Contextの関係 | L62-71 | 見出し・内容維持 |
| Ansible変更の共通ゲート | L73-78 | 見出し・内容維持 |
| AI間連携と成果物 | L80-86 | 見出し・内容維持 |
| 原則の保守 | L88-92 | 見出し・内容維持 |
| 変更履歴 | 該当なし | 末尾に新設。既存規範を変更しない |

### 2.2 全規範ledger

| ID | 旧行 | 規範 | Phase 2到達先 |
|---|---:|---|---|
| CORE-001 | L3 | 全AI Roleは作業開始時にcoreを読み、製品別入口へ共通原則を複製しない | 冒頭 |
| CORE-002 | L7 | repositoryはAnsible資産と安全運用文書を管理する | 目的と正本 |
| CORE-003 | L9 | Git管理内容をcode /文書の正本とする | 目的と正本 |
| CORE-004 | L10 | coreを全Role共通原則の正本とする | 目的と正本 |
| CORE-005 | L11 | 案件要求と工程記録の正本をagmsg依頼とreviews成果物とする | 目的と正本 |
| CORE-006 | L12 | 現在変更はworktree / diffを正本とし説明だけで判断しない | 目的と正本 |
| CORE-007 | L13 | system固有判断は該当Policyを正本とする | 目的と正本 |
| CORE-008 | L14 | 旧coreはfallbackであり共通原則は新coreを優先する | 目的と正本 |
| CORE-009 | L18 | AIは支援者で、最終判断者はYoshinobuとする | 人間の権限 |
| CORE-010 | L20 | 運用採否、本番適用、危険操作、確定、commitはYoshinobuが判断する | 人間の権限 |
| CORE-011 | L21 | 本番影響操作を暗黙承認や推測で実行しない | 人間の権限 |
| CORE-012 | L22 | 許可不明または安全懸念時は停止して確認する | 人間の権限 |
| CORE-013 | L23 | AIはcommit / pushしない | 人間の権限 |
| CORE-014 | L24 | playbook自身にGit更新をさせない | 人間の権限 |
| CORE-015 | L29 | ansyを開発・review・検証・commit/push準備の場とする | 開発と本番 |
| CORE-016 | L30 | Gitを確定code /文書の正本とする | 開発と本番 |
| CORE-017 | L31 | quoryを確定済みGitの本番実行基盤とする | 開発と本番 |
| CORE-018 | L34 | quoryで原則直接編集・commitしない | 開発と本番 |
| CORE-019 | L35 | 作業開始時にstatusと関連diffを確認する | 開発と本番 |
| CORE-020 | L36 | 既存変更を保護しscope外を上書き・破棄・整形しない | 開発と本番 |
| CORE-021 | L37 | read-only確認と変更処理を分離する | 開発と本番 |
| CORE-022 | L41 | repositoryを公開前提で扱う | 公開情報 |
| CORE-023 | L43 | 秘密情報を保存・表示・生成・複製しない | 公開情報 |
| CORE-024 | L44 | 内部IPを直接記載せずDNS名またはruntime解決を使う | 公開情報 |
| CORE-025 | L45 | runtime report等を意図せずcommit対象にしない | 公開情報 |
| CORE-026 | L46 | SSH port / user / auth / hostを根拠なく固定しない | 公開情報 |
| CORE-027 | L50 | 情報を必要範囲だけ指定順序で選ぶ | 作業時に読む情報 |
| CORE-028 | L52 | 最初にcoreを読む | 作業時に読む情報 |
| CORE-029 | L53 | routing indexでidentity / Role / ownerを解決する | 作業時に読む情報 |
| CORE-030 | L54 | 指定された案件記録を読む | 作業時に読む情報 |
| CORE-031 | L55 | migration mapから必要Context / Policyだけを辿る | 作業時に読む情報 |
| CORE-032 | L56 | taskに一致するSkillを使う | 作業時に読む情報 |
| CORE-033 | L57 | 過去経緯が必要な時だけKnowledgeを読む | 作業時に読む情報 |
| CORE-034 | L58 | 実装・review・testはcode / status / diffで再確認する | 作業時に読む情報 |
| CORE-035 | L60 | 新配置を段階作成し、未移行情報はindex / mapの限定参照から辿り、無差別探索しない | 作業時に読む情報 |
| CORE-036 | L64 | Roleは主体・判断・成果物を定義する | Role等の関係 |
| CORE-037 | L65 | Skillは進め方を定義し環境台帳やRole権限を埋め込まない | Role等の関係 |
| CORE-038 | L66 | Contextは環境 / repository事実を記録し変動事実をcoreへ複製しない | Role等の関係 |
| CORE-039 | L67 | Policyは許可・禁止・停止条件を定義する | Role等の関係 |
| CORE-040 | L68 | Knowledgeは再利用価値のある知識とし一時失敗を恒久ruleへ直ちに昇格しない | Role等の関係 |
| CORE-041 | L69 | IssueとPR/diffの役割をagmsg / reviews / worktreeで暫定的に担う | Role等の関係 |
| CORE-042 | L71 | identity名から責務・権限を推測せずrouting indexを正本とする | Role等の関係 |
| CORE-043 | L75 | 対象playbookのtester-gateとPolicyを確認する | Ansible gate |
| CORE-044 | L76 | tester-gate意味はmigration mapが指す限定節を参照する | Ansible gate |
| CORE-045 | L77 | check-mode-native / dry-run-awareをcheckなしでtester実行しない | Ansible gate |
| CORE-046 | L78 | check shellを観測に限定し危険操作を混ぜない | Ansible gate |
| CORE-047 | L82 | AI間依頼・完了・引継ぎにagmsgを使う | AI間連携 |
| CORE-048 | L83 | 本文 /監査証跡をrepository、agmsgを短い結果に使い分ける | AI間連携 |
| CORE-049 | L84 | 受信側はmessageだけを信頼せずfile / diffを読む | AI間連携 |
| CORE-050 | L85 | routingと成果物形式は正本index / mapから辿る | AI間連携 |
| CORE-051 | L86 | 不一致・競合を独断統合せずowner / techleadへ知らせる | AI間連携 |
| CORE-052 | L90 | core追加前に全Role必読の不変原則か確認し、分類別の置場へ分ける | 原則の保守 |
| CORE-053 | L92 | 旧core項目の移動判断はmigration mapを参照する | 原則の保守 |

CORE-001〜CORE-053の53件をPhase 2で同じ行内容のまま保持する。変更履歴追加はCORE規範を移動、統合、言い換えしない。

## 3. log_observability_policy.md

### 3.1 標準8節への全量配置

| 標準節 | 旧範囲 | 配置内容 |
|---|---|---|
| 1. 目的 | §1 L13-15 | logsの収集・保全・検索。future alertとrecoveryを分離 |
| 2. 対象と実行範囲 | §2-§3 L17-68 | collection plane、source class、現行管理境界。具体構成はContextへ |
| 3. 対応するPlaybook | L70-72、実map | `alloy_setup.yml`と`rsyslog_forward_to_monnie.yml`の2入口 |
| 4. 判断軸 | §4 L74-83、§6 L92-105 | cutover gate、validation、severity / drop境界、人間gate |
| 5. ライフサイクル・処理フロー | §4 L74-83 | install / validate / cutover / rescue、sender rollout |
| 6. 通知方針 | §2 L20、§5 L90、実code | 該当なし（未実装）。Phase 3構想を現行扱いしない |
| 7. 制約・禁止事項 | §6-§7 L92-112 | network / pipeline / exposure / management / apply境界 |
| 8. 変更履歴 | L1-11、§5 L85-90、§8 L114-117 | version history。時点構成 / testは021へ |

| 旧section | 行 | 最終配置 /分離 |
|---|---:|---|
| metadata /変更履歴 | L1-11 | P8 |
| §1 位置づけ | L13-15 | P1 / P2 |
| §2 architecture | L17-34 | P2 / P7、System / Repository Context |
| §3 current configuration | L36-68 | System / Repository Context、Policy核はP2 / P4 / P7 |
| 対応Playbook | L70-72 | P3。mapにあるsender入口も追加 |
| §4 Alloy policy | L74-83 | P4 / P5 / P7、Repository Context |
| §5 roadmap | L85-90 | 完了履歴は021、現行境界はP2、future alertは021 |
| §6 constraints | L92-105 | P7、System / Repository Context |
| §7 rejected alternatives | L107-112 | 021、現行management boundaryはP7 / Context |
| §8 validation status | L114-117 | 021のみ。現行Policyへtest resultを残さない |

### 3.2 範囲超過候補

| # | 旧範囲 | 種類 | 具体的移動先 | Policyへ残す核 |
|---:|---|---|---|---|
| 1 | L1-11 | metadata / history | P8、本021 | 正本のversion変更 |
| 2 | §2.1 L24-30 | System / Repository fact | 既存 `context/system/monitoring.md`、新規 `context/ansible/log-observability.md` | Loki writeをmonnie localに限定、remote credential / port非公開 |
| 3 | §2.2 L32-34 | design decision | Repository Context、本021 | rsyslog集約を維持しAlloy直受信へ置換しない |
| 4 | §3 diagram L36-51 | current topology | System / Repository Context | collection plane一本化 |
| 5 | §3 L53-56 | ownership / implementation fact | System / Repository Context | GUI / manual / Ansible管理境界 |
| 6 | §3 L57-68 | label / config / dashboard contract | Repository Context、code / dashboard | severity誤分類禁止、Loki非公開、self-noise warning/error保持 |
| 7 | L70-72 | repository index | Repository Context / P3 | 人間gateと1入口。sender入口をP3へ追加 |
| 8 | §4 L76-79 | package / path / defaults | Repository Context / code | Git正本、host直編集禁止、major更新review |
| 9 | §4 L80-82 | cross-file lifecycle | Repository Context | validate後だけcutover、rollback維持、実data検証 |
| 10 | §4 L83 | operations link | 既存 `context/operations/autonomous-recovery.md`を参照 | production変更前のmonnie mute |
| 11 | §5 L85-90 | time-dependent roadmap | 本021 | 現行scopeとfuture alertを分離 |
| 12 | §6 L94-105 | risk + environment fact | System / Repository Context | plaintext risk受容、allowlist非認証、Loki非公開、人間gate、秘密禁止 |
| 13 | §7 L107-112 | rejected decision / ownership | 本021、System / Repository Context | rejected方式を現行許可へしない、管理境界 |
| 14 | §8 L114-117 | historical test result | 本021 | 検証合格条件だけP4へ保持 |
| 15 | Phase 3 alert記述 L20/L90とdashboard説明 | future-only | 本021。実装時に別案件でPolicy / Context更新 | P6は該当なし（未実装） |

範囲超過候補は15行である。現状構成は既存System Context、cross-file構成は新Repository Context、検証結果とroadmap時点履歴は本021を移動先とする。

### 3.3 全規範ledger

| ID | 旧行 | 規範 /境界 | 新Policy先 |
|---|---:|---|---|
| LOG-001 | L15 | 本Policyをlogging正本としrecoveryと目的を分離する | P1 |
| LOG-002 | L15 | 現行は収集・保全・検索、alertは将来scopeとする | P1/P6 |
| LOG-003 | L19 | collection pathを一本化し目的別pipelineを建てない | P2/P7 |
| LOG-004 | L20 | future監視はlabels / alert rulesをcollection plane上へ載せる構想に限定する | P8 |
| LOG-005 | L22 | log agentをGrafana Alloyへ統一しEOL Promtailを現行agentにしない | P2 |
| LOG-006 | L26 | syslog-only applianceをmonnie aggregationへ送る | P2 |
| LOG-007 | L27 | monnie local Alloyがjournal / rsyslog filesを読みlocal Lokiへpushする | P2 |
| LOG-008 | L28 | remote Linuxはjournald→rsyslog→monnie funnelを使う | P2 |
| LOG-009 | L30 | Loki writeはmonnie local Alloyだけに限定する | P2/P7 |
| LOG-010 | L30 | remoteへAlloy/Loki credentialやrepositoryを広げずunauthenticated Loki portを公開しない | P7 |
| LOG-011 | L34 | rsyslogをUDP receive / allowlist / routingに維持しAlloy direct receiveへ置換しない | P2/P7 |
| LOG-012 | L53 | CloudKey sender settingはGUI管理としAnsibleが直接編集しない | P2/P7 |
| LOG-013 | L54 | Sophos sender settingはGUI管理としrepositoryはreceive readinessまでを管理する | P2/P7 |
| LOG-014 | L55 | pve sender configをmanual管理としAnsible対象にしない | P2/P7 |
| LOG-015 | L56 | Ubuntu senderをsender role、monnie receiverをAlloy roleで管理する | P2/P5 |
| LOG-016 | L57-58 | CloudKey streamをunifi label contractで扱う | P4 |
| LOG-017 | L59 | network-device streamはdynamic host extractionを行う | P4 |
| LOG-018 | L60 | pve streamはnormalized host extractionを行う | P4 |
| LOG-019 | L61 | Sophos streamはstatic host contractを使う | P4 |
| LOG-020 | L62 | Ubuntu remote streamはnormalized dynamic hostを使う | P4 |
| LOG-021 | L63 | monnie journalをsystem streamとしてunit relabelする | P4 |
| LOG-022 | L64 | levelをerror / warning / info / debugの4値に限定する | P4 |
| LOG-023 | L64 | journal priorityを4 levelへ指定対応させる | P4 |
| LOG-024 | L64 | normalized sourcesはrsyslogがlevelを確定しAlloyが抽出する | P4 |
| LOG-025 | L64 | UniFiは安全に認識できる時だけbest-effort付与しunknownを誤分類しない | P4/P7 |
| LOG-026 | L65 | normalized fileはlabels抽出後message-only本文をLokiへ保存する | P4 |
| LOG-027 | L66 | monnie journalの観測stack exact unitかつinfo/debugだけをdropする | P4 |
| LOG-028 | L66 | warning/errorを保持しremote file sourcesへself-noise dropを適用しない | P4/P7 |
| LOG-029 | L67 | Loki pushをmonnie localhostへ限定する | P2/P7 |
| LOG-030 | L68 | dashboardはline limitとwarning/error defaultを維持しinfo/debugを明示選択可能にする | P4 |
| LOG-031 | L68 | host/searchとline formatを維持する | P4 |
| LOG-032 | L72 | alloy setup入口はcheck-mode-nativeでAPPLYを人間gateとする | P3/P7 |
| LOG-033 | L76 | Alloyをexisting repositoryからrole管理でinstallしstate presentでversion-upしない | P5/P7 |
| LOG-034 | L77 | version-upはmonthly aptへ分離しmajor疑いをhuman reviewへ上げる | P4/P7 |
| LOG-035 | L78 | configをGit / role正本としhost直編集しない | P7 |
| LOG-036 | L79 | existing UniFi configを変更せずnew routeを別configで管理する | P5/P7 |
| LOG-037 | L79 | sender namesをruntime解決しdeployed configはDNSを自動再解決しない | P4/P5 |
| LOG-038 | L79 | address変更後はsetup入口を再実行してallowlistを更新する | P5 |
| LOG-039 | L80 | install時auto-startを抑止しcontract / validate合格後だけPromtail停止→Alloy開始する | P4/P5 |
| LOG-040 | L80 | Alloy start失敗時にPromtailをrestoreしrollback資材を削除しない | P4/P5/P7 |
| LOG-041 | L81 | positionsを移植せずsource種別別tail startを守り小さなgap/overlapを受容する | P4/P7 |
| LOG-042 | L82 | Alloy userへjournal accessを与えactiveだけでなくreal stream dataを検証する | P4/P5 |
| LOG-043 | L83 | production cutover前にmonnieをmuteする | P5/P7 |
| LOG-044 | L87 | Phase 1完了はhistorical resultとして保持し現行通知契約にしない | P8 |
| LOG-045 | L88 | Phase 2の実装済み / validation待ち状態を時点履歴として保持する | P8 |
| LOG-046 | L89 | Phase 2 extensionの稼働 /是正履歴を時点履歴として保持する | P8 |
| LOG-047 | L90 | Slack alertはPhase 3 future-onlyで現行通知としない | P6/P8 |
| LOG-048 | L94-98 | plaintext syslogの盗聴 / spoofing riskとallowlist非認証を受容境界として明示する | P7 |
| LOG-049 | L97-98 | TLSは対応senderだけのfuture optionでappliance plaintext残存を認識する | P7/P8 |
| LOG-050 | L99 | collectionはLoki一本に統一する | P7 |
| LOG-051 | L100 | rsyslog aggregationを維持する | P7 |
| LOG-052 | L101 | Loki / UFWを現scopeで変更せずLoki portをremote公開しない | P7 |
| LOG-053 | L102 | Alloy configのhost直編集を禁止する | P7 |
| LOG-054 | L103 | production APPLYをhuman gateとしtesterは既定でAPPLYしない | P7 |
| LOG-055 | L104 | secrets / IPを記載せずruntime validationをtesterへ分離する | P7 |
| LOG-056 | L105 | log volumeを継続観測しretention / capacity変更を別reviewにする | P7 |
| LOG-057 | L109 | remote pve Alloy案を採らずunit精度 / delivery保証が必須になった場合だけ再検討する | P7/P8 |
| LOG-058 | L110 | systemd-journal-remote案を採らない | P7/P8 |
| LOG-059 | L111 | Alloy direct syslog receive案を採らない | P7/P8 |
| LOG-060 | L112 | Ansible / manual / GUIのmanagement boundaryを維持する | P2/P7 |
| LOG-061 | L114-117 | historical PASS / known non-blocking事象を現行許可条件へ昇格させない | P8 |

LOG-001〜LOG-061の61件をPhase 2でmarker化する。current / future / historicalの状態を相互に昇格させない。

### 3.4 通知方針の実測判定

結論は「現行通知方針なし、未実装」である。

| 根拠 | 実測 |
|---|---|
| Policy | L20とL90はPhase 3 future alertだけ |
| Playbook | `alloy_setup.yml`、`rsyslog_forward_to_monnie.yml`にSlack / notify / alert taskなし |
| Role / template | `roles/alloy`、`roles/rsyslog_forward_to_monnie`にcommon_slack、webhook、contact point、ruler、Alertmanager configなし |
| Dashboard | `infra_syslog_all_nodes.json`のpanel descriptionにPhase 3 alertのbasisとあるだけでalert rule objectなし |
| Map | 2入口はいずれもchange / loggingで、通知roleを列挙しない |

P6の予定文は「該当なし（未実装）。Phase 3のSlack alert構想は現行通知契約ではない」とする。channel、status、failure notificationを新規作文しない。

### 3.5 実装 / map突合

| 入口 | actual role | tester-gate | map | P3計画 |
|---|---|---|---|---|
| `alloy_setup.yml` | `alloy` | check-mode-native | 一致 | 列挙する |
| `rsyslog_forward_to_monnie.yml` | `rsyslog_forward_to_monnie` | check-mode-native | 一致 | 旧P3欠落のため列挙する |

P3列挙は実行許可を増やさず、各入口のtester-gateと人間gateを優先する。

## 4. 軽量4 Policy

### 4.1 cert_renew_cloudkey_policy.md

#### 標準見出し対応 / rename plan

| 標準節 | 旧範囲 | plan |
|---|---|---|
| 1. 目的 | §1-§2 L17-43 | relationをsubsectionに保ち目的見出しへ統合 |
| 2. 対象と実行範囲 | §3-§5 L46-118、§14 L266-275 | target / CA / certificate spec / exclusionsをsubsection保持 |
| 3. 対応するPlaybook | L61-65 | 標準名のまま1入口 |
| 4. 判断軸 | §8-§9 L166-207 | unique name、delete all conditions、delivery verification |
| 5. ライフサイクル・処理フロー | §6-§7 L122-162、§12 L241-249 | upload→activate→verify→delete順序、API contract、schedule |
| 6. 通知方針 | §11 L226-237 | 見出しrenameだけ |
| 7. 制約・禁止事項 | §10 L211-222、§13-§14 L253-275 | secret、unofficial API risk、exclusions |
| 8. 変更履歴 | L1-13 | 末尾へ移動し内容維持 |

#### 軽量安全ledger

| ID | 旧行 | 保持する境界 |
|---|---:|---|
| CCK-001 | L19-22 | cert_renewから独立しfailure domainを分離する |
| CCK-002 | L36-43 | private CA短命certificateによるWeb UI更新目的 |
| CCK-003 | L50-59 | target、controllers、local execution、controller allowlist |
| CCK-004 | L65 | 対応入口をcloudkey deploy 1本とする |
| CCK-005 | L85-99 | 3-level full chain、allowed controllersだけにCA資材、private key非Git |
| CCK-006 | L105-118 | RSA / format / validity / SAN / usage / chain specification |
| CCK-007 | L124-135 | new upload→activate→live verify→old deleteの順序を変えない |
| CCK-008 | L141-162 | API method、TOKEN / CSRF / Origin、hostname接続条件 |
| CCK-009 | L170-175 | unique generation nameでsame-month collisionを防ぐ |
| CCK-010 | L179-189 | delete前にlist再取得しsource / inactive / new-id exclusionをすべて満たす |
| CCK-011 | L186-189 | active / new / non-uploaded certificateをdeleteせずverify failure時はoldを残してfail |
| CCK-012 | L195-207 | live leaf fingerprint AND ordered 3-level chainを合格条件とする |
| CCK-013 | L205-207 | collection shellに判断を置かずAnsibleでAND / failを決める |
| CCK-014 | L213-220 | credentialsをVault、temporary keyをalways cleanup、secret tasksをno_logにする |
| CCK-015 | L221-222 | current shared accountとfuture dedicated accountを混同しない |
| CCK-016 | L228-237 | Slack best-effort、success / failure routing、notify後re-fail |
| CCK-017 | L248-249 | production monthly force issuanceでthresholdを使わない |
| CCK-018 | L255-262 | unofficial API failure riskをUI availability lossへ拡大せずother servicesと分離 |
| CCK-019 | L268-275 | main cert integration / LE delete / unsupported API / future accountをscope外とする |
| CCK-020 | L28/L151-162/L213-217 | actual account / auth storage値を新Policyへ転載せずvariable / Vault / codeを正本とする |

範囲超過はAPI path表、CA file path、実行command、credential storage pathが中心である。今回は指摘のみとし、Phase 2は標準見出し配下のsubsectionとして内容を保持しつつ実値だけ除去する。actual playbook / map / roleは1入口・1roleで一致する。

### 4.2 cert_renew_policy.md

#### 標準見出し対応 / rename plan

| 標準節 | 旧範囲 | plan |
|---|---|---|
| 1. 目的 | §1 L19-22 | 見出しrename |
| 2. 対象と実行範囲 | §2-§4 L26-113、§11 L246-253 | target、split reason、CA scope、exclusions |
| 3. 対応するPlaybook | L49-56 | primary 2入口を維持 |
| 4. 判断軸 | §7-§9 L149-189 | CA expiry、failure、renew threshold / force |
| 5. ライフサイクル・処理フロー | §5-§6 L116-145、§10 L193-243 | staging / cleanup / chain / recovery |
| 6. 通知方針 | §7 L158-162、§8 L169-179 | warning付加、channel条件 |
| 7. 制約・禁止事項 | §4 L60-113、§11 L246-253 | controller restriction、private key、excluded systems |
| 8. 変更履歴 | L1-15 | 末尾へ移動し内容維持 |

#### 軽量安全ledger

| ID | 旧行 | 保持する境界 |
|---|---:|---|
| CERT-001 | L21-22 | management UI certificate自動更新とshort-lived運用 |
| CERT-002 | L28-35 | 対象service / host /入口対応 |
| CERT-003 | L40-47 | quory certificateをself-restart回避の独立入口で更新しansyを含めない |
| CERT-004 | L53-56 | primary入口2本とCloudKey除外 |
| CERT-005 | L72-83 | CA資材をquoryに限定しsource existence / key mode不一致で停止 |
| CERT-006 | L87-93 | root CA private keyをofflineにしintermediateだけでdaily signする |
| CERT-007 | L98-112 | keyをquory only / non-Git / required modeとしownerをhardcodeしない |
| CERT-008 | L116-126 | tmpfs stagingをcleanupしcleanup失敗を最終failにする |
| CERT-009 | L132-145 | leaf + intermediate full chainを生成 /配布する |
| CERT-010 | L151-165 | intermediate expiry thresholdでwarningを設定しperiodic human reviewする |
| CERT-011 | L171-179 | body failure / cleanup / unit exitを検知しwarning / failureをalerts、successをinfoへ |
| CERT-012 | L184-189 | validity / renew threshold OR force / key algorithm / dynamic SAN条件 |
| CERT-013 | L197-219 | initial migrationはforce、production monthlyもforce、thresholdはmanual fallbackだけ |
| CERT-014 | L223-243 | restore / reissue時もintermediate keyをquory onlyに置きall targetsをforce renewする |
| CERT-015 | L246-253 | CloudKeyとEAP-TLS certificateをscope外とする |
| CERT-016 | L73 | both primary playbooksをquory以外から実行しない |
| CERT-017 | L80-83 | persistent CAをruntime stagingへcopyしpost-process deleteする |
| CERT-018 | L107-112 | mode checkを必須としowner checkを追加しない |
| CERT-019 | L126/L173-174 | cleanup failureをnotificationだけでsuccess扱いしない |
| CERT-020 | L187 | renewalはremaining threshold OR explicit forceの関係を維持する |

mapはprimary 2入口に加え `ca_trust_deploy.yml` と `test_ca_env.yml` をPolicy参照として持つ。前者はCA trust support、後者はdiagnosticであり、旧「対応するPlaybook」のrenewal 2入口へ無断追加しない。Phase 2 recordで関連入口として別記する。actual role名は`homelab_cert_renew`であり、旧文書のgeneric `cert_renew role`表現をactual roleへの意味変更なしの参照補正候補とする。

### 4.3 time_sync_check_policy.md

#### 標準見出し対応 / rename plan

| 標準節 | 旧範囲 | plan |
|---|---|---|
| 1. 目的 | §1 L26-37 | 見出しrename、historical rationaleはsubsection |
| 2. 対象と実行範囲 | §2-§3 L41-96、§8 L163-176 | targets、methods、exclusions |
| 3. 対応するPlaybook | L54-59 | 2入口を維持 |
| 4. 判断軸 | §3 L65-81、§4 L100-115 | reference gate、method threshold、collection failure |
| 5. ライフサイクル・処理フロー | §4 L100-115 | 見出しrename |
| 6. 通知方針 | §5 L119-129 | 標準名のまま |
| 7. 制約・禁止事項 | §6-§8 L132-176 | read-only/change分離、no auto correction、scope |
| 8. 変更履歴 | L1-22 | 末尾へ移動し内容維持 |

#### 軽量安全ledger

| ID | 旧行 | 保持する境界 |
|---|---:|---|
| TIME-001 | L28-37 | NTP self-reportを優先しdirect comparisonはunsupported target例外だけ |
| TIME-002 | L45-52 | reference、targets、controllers、read-only / change入口分離、executor self-exclusion |
| TIME-003 | L58-59 | checkとreference-changeの2入口を混同しない |
| TIME-004 | L67-75 | target別client / collection methodを維持する |
| TIME-005 | L76-81 | direct comparisonのmeasurement errorを認識し専用thresholdを使う |
| TIME-006 | L83-84 | quory server追加不要の現状を新しいchange許可へしない |
| TIME-007 | L88-96 | CloudKey NTP configをGUI管理としreference playbook対象外にする |
| TIME-008 | L103-104 | reference hostがuncollected / unsyncedならstopしother hostsへ接続しない |
| TIME-009 | L105-110 | reference pass後にchrony→direct target→CloudKey→aggregate / notifyの順で行う |
| TIME-010 | L113-115 | collectionをcommand / expect、calculation / threshold / failをAnsibleへ分離する |
| TIME-011 | L121-128 | Slack best-effort、OK no-notify、warning / critical / error条件を維持 |
| TIME-012 | L135-137 | check入口をread-onlyとしreference変更を別入口へ限定する |
| TIME-013 | L138-141 | secret tasksをno_log、IP literal禁止、name resolution前提を保持 |
| TIME-014 | L142-144 | auto correction、history/trend、serial consoleをscope外とする |
| TIME-015 | L149-160 | file list / Vault値はcode / mapを正本としPolicy判断へ昇格しない |
| TIME-016 | L167-176 | implemented scopeと4 exclusionsを維持する |
| TIME-017 | actual gates | check=safe-readonly、reference=risk-acceptedをP3で明示する |
| TIME-018 | map / roles | 2 playbook / 2 roleの対応を維持する |

actual path / map / roleは2入口・2roleで一致する。具体host collection command、default threshold、Vault pathはRepository facts / codeであり、Phase 2では意味を変えずsubsectionに保持するかContext候補として指摘する。

### 4.4 unifi_backup_fetch_policy.md

#### 標準見出し対応 / rename plan

| 標準節 | 旧範囲 | plan |
|---|---|---|
| 1. 目的 | §1-§2 L23-49 | relationshipをsubsectionにして目的へ統合 |
| 2. 対象と実行範囲 | §3 L53-64、§9 L154-163 | source / destination / executor / schedule |
| 3. 対応するPlaybook | L66-72 | 1入口を維持 |
| 4. 判断軸 | §4 L76-87、§6-§7 L111-137 | acquire / finalize / cleanup / re-fail、filename / freshness |
| 5. ライフサイクル・処理フロー | §4-§6 L76-125 | auth→download→freshness→rename→rotate→always |
| 6. 通知方針 | §8 L140-150 | 標準名のまま |
| 7. 制約・禁止事項 | §5 L91-107、§10 L167-176 | auth / secret / hostname / no config change |
| 8. 変更履歴 | L1-19、§12 L204-217 | version history。test result / operation memoは021へ |

#### 軽量安全ledger

| ID | 旧行 | 保持する境界 |
|---|---:|---|
| UNIFI-001 | L25-36 | certificate deploymentから取得failure domainを分離しbackup generation / storage deleteだけを変更する |
| UNIFI-002 | L42-49 | system backupをweekly生成 / retainしapp-only backupを取得しない |
| UNIFI-003 | L57-64 | source / storage / executor / root / hostname / Origin条件を維持する |
| UNIFI-004 | L70 | 対応入口を1本とする |
| UNIFI-005 | L79-87 | init→auth→download→freshness→atomic finalize→rotation→rescue→always順序 |
| UNIFI-006 | L85-87 | failureをrecordしalways cleanup / summary / notify後、failure時だけre-failする |
| UNIFI-007 | L93-107 | local API account、CSRF header priority、JWT fallback only条件、auth headers、no_log |
| UNIFI-008 | L113-120 | server filenameを使いallowlist / basename / slash / traversalをfinalize前にassertする |
| UNIFI-009 | L121-122 | same-filesystem atomic renameで毎回overwriteしdownload済みをsuccess扱いしない |
| UNIFI-010 | L123-125 | generation limit超過だけをoldest-first deleteしpermissionを維持する |
| UNIFI-011 | L131-136 | filename timestampとexecutor current timeのabsolute differenceでfreshness failする |
| UNIFI-012 | L135-136 | NTP syncをpreconditionとしtemporary threshold changeをexplicit inputに限定する |
| UNIFI-013 | L142-150 | Slack best-effort、success info / failure alerts、notify failureをbody resultへ反映しない |
| UNIFI-014 | L156-160 | other maintenanceと重複しないweekly確定codeだけをrunしplaybookでGit更新しない |
| UNIFI-015 | L170-176 | IP literal / secret commit禁止、CloudKey config不変、change playbook分離、target identity前提 |
| UNIFI-016 | L184-200 | file / default valuesはcodeを正本としPolicy判断と分離する |
| UNIFI-017 | L206-210 | historical E2E / pending real retention deleteを現行許可へ昇格しない |
| UNIFI-018 | L214-216 | credential change時はVaultを更新しinvalid auth failureをsuccess扱いしない |
| UNIFI-019 | actual gate | risk-acceptedでcheck有無にかかわらずchangeを生じ得る境界をP3へ明記する |
| UNIFI-020 | map / role | 1 playbook / 1 role / common Slackの対応を維持する |
| UNIFI-021 | L100-101 | CSRF headerが有効ならJWTをdecodeせず両header empty時だけfallbackする |
| UNIFI-022 | L121-124 | finalize成功後だけrotationしdelete対象をgeneration超過へ限定する |
| UNIFI-023 | L86 | temporary file cleanupをsuccess / failure双方のalwaysで行う |
| UNIFI-024 | L86 | notification後のre-failをfailure時だけ行う |
| UNIFI-025 | L217 | stray code fenceをPhase 2でformat修正し規範内容を変えない |

actual playbook / map / roleは1入口・1roleで一致する。範囲超過はAPI body / path、default values、実行schedule例、E2E result / operation memoであり、Policy核は残してcode /本021を正本とする。旧L217のunmatched code fenceは構造不良で、Phase 2で削除してよい。

## 5. Phase 2編集path案

Tech Leadの明示許可後だけ編集する。

| path | 操作 | 理由 |
|---|---|---|
| `docs/ai/core.md` | 変更履歴だけ追加 | 個別Policy templateを適用しない |
| `docs/ai/policies/log_observability_policy.md` | 標準8節へ再編 | LOG-001〜061とP6未実装を保持 |
| `docs/ai/context/system/monitoring.md` | log topology / ownershipを最小追記 | codeでは分からないcurrent system facts |
| new `docs/ai/context/ansible/log-observability.md` | 2入口 / 2role / config / cutover契約 | cross-file repository map |
| `docs/ai/policies/cert_renew_cloudkey_policy.md` | 標準8見出しへ統合 | CCK ledger、意味変更なし |
| `docs/ai/policies/cert_renew_policy.md` | 標準8見出しへ統合 | CERT ledger、意味変更なし |
| `docs/ai/policies/time_sync_check_policy.md` | 標準8見出しへ統合 | TIME ledger、意味変更なし |
| `docs/ai/policies/unifi_backup_fetch_policy.md` | 標準8見出しへ統合 | UNIFI ledger、意味変更なし |
| new Phase 2 implement記録 | migration / marker / line index /検査 | audit trail |

新規Operations Contextは不要である。mute / pauseの横断runbookは既存 `context/operations/autonomous-recovery.md`にあり、log-specific duplicateを作らない。

## 6. 重複・矛盾riskとPhase 2検査

| risk | 対策 |
|---|---|
| coreへ8節templateを適用 | 現行9見出し一致と変更履歴1件だけを検査 |
| log future Slackをcurrent化 | P6 exact「該当なし（未実装）」、Slack contract / channel / status新規記述0 |
| log current topologyをPolicyへ残す | 15 migration行でSystem / Repository /021へ移動しPolicy kernelをindex化 |
| rsyslog sender入口欠落 | P3にactual mapの2入口を列挙し、列挙を実行許可にしない |
| 4 Policyの大規模意味変更 | lightweight ledgerと旧HEAD lineを比較し、subsection textを基本維持 |
| cert related map 4本とprimary P3 2本の混同 | primary / supporting / diagnosticを別表にする |
| secret / auth actual転載 | account値 / credential pathを変数名、Vault、code正本へ置換 |
| historical resultをcurrent gate化 | test result / roadmapを021 / implement recordへ分離 |
| existing diff競合 | Phase 2開始前に各許可pathのdiff ownerを再確認し指定外を保持 |

Phase 1検査:

- snapshot commit / blob / line count 6件。
- core ledger CORE-001〜053、log ledger LOG-001〜061の欠落 /重複 /空cell。
- lightweight ledger CCK-001〜020、CERT-001〜020、TIME-001〜018、UNIFI-001〜025。
- log全量配置10行、scope候補15行、standard 8節、current notification実装0。
- lightweight 4本のstandard対応8行ずつ。
- actual playbook / role / tester-gate / map: log 2/2、cloudkey 1/1、cert primary 2/1 + related 2、time 2/2、unifi 1/1。
- Markdown empty cell、IPv4、VLAN ID、VM ID、auth / secret actual、relative path。
- 本021以外の本件変更0、`git diff --check`、untracked 021の`git diff --no-index --check`。

Phase 2検査:

- coreの旧9見出し / CORE-053件を維持し変更履歴だけ1件追加。
- log標準8見出しを順番どおり各1、LOG-061 marker / index、migration 15、P3 2入口、P6未実装。
- lightweight 4本は標準8見出し各1、ledger marker CCK20 / CERT20 / TIME18 / UNIFI25、旧HEAD比較で意味差0。
- 6文書 / Context / implement recordに禁止実値0、空table cell0、link欠落0。
- code / map / requirement /本021 /他PolicyにPhase 2差分0。
- tracked / untracked whitespace、自己diff review、実機・Ansible実行0。

### 6.1 Phase 1検査実績

| 検査 | 結果 |
|---|---|
| snapshot | commit一致1、blob一致6、line count一致6 |
| core | 現行見出し9、変更履歴追加計画1、CORE ledger 53、欠落 /重複 /連番差0 |
| log placement | 標準対応8、旧section全量配置10、scope候補15 |
| log ledger | LOG-001〜LOG-061、61件、欠落 /重複 /連番差0 |
| log notification | current Slack / contact point / alert rule / ruler / Alertmanager実装0、future記述だけ2系統 |
| lightweight mappings | 4文書 × 標準8行 = 32、合計standard対応表40行 |
| lightweight ledgers | CCK 20、CERT 20、TIME 18、UNIFI 25、各欠落 /重複 /連番差0 |
| actual / map | log 2 playbook / 2 role、cloudkey 1 / 1、cert primary 2 / 1 + related 2、time 2 / 2、unifi 1 / 1。実path欠落0 |
| Markdown | empty table cell 0 |
| forbidden values | IPv4、VLAN ID、VM ID、auth / secret actual 0 |
| scope | 本021以外の本件変更0。6 snapshot / Context / code / map / requirementは未変更 |
| whitespace | tracked `git diff --check`、untracked 021 `git diff --no-index --check`ともにPASS |
| runtime | 実機・Ansible実行0 |

自己diffでは、log初稿のroadmap 3行、constraint 2行、不採用案 / management boundary 4行の集約が逐行追跡として粗いことを検出し、LOG-001〜061へ分割した。cert mapの4参照をprimary 2 / supporting 1 / diagnostic 1へ区別し、P3を無断拡張しない計画へ補正した。Unifi旧L217の孤立code fenceは意味を持たないformat不良として追跡した。その他の未解消差異、未決移動先、Phase 2を止めるblockerはない。

## 7. Phase 1結論

coreは現構造を維持して変更履歴だけを追加できる。log_observabilityは標準8節へ再編可能で、現行通知は実装されておらずP6は「該当なし（未実装）」が正しい。current topology / configはSystem / Repository Context、test result / roadmapは本021へ分離する。残り4 Policyは既存規範をsubsection単位で標準8見出しへ包み直す軽量変更で足りる。Phase 2を止める未決移動先、意味矛盾、code変更要求はない。
