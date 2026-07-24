# Ubuntu VM Patch Policy 標準構造書換 Phase 1 調査

## 1. 調査範囲と正本

- requirement: `2026-07-24_012_requirement_ubuntu_vm_patch_policy_rewrite.md`
- 旧Policy正本: Git HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79` の `docs/ai/policies/ubuntu_vm_patch_policy.md`
- 旧Policy blob: `bf8cee43f3789dbae1b0a524f84fdb694a5445c7`
- 旧Policy規模: 289行、主section 9件
- Phase 1で編集したファイル: 本013のみ
- 未実施: Policy、Context、playbook、roleの編集、実装不一致の解消、実機・Ansible実行

行番号はすべて上記HEAD snapshotの1始まりである。IP、VLAN ID、VM ID、認証情報、秘密情報の実値は転載しない。時刻、port、閾値、version例は規範または実装契約の照合に必要な非秘密値として区別する。

## 2. 標準8節への旧文書全量配置

### 2.1 新Policyの標準8節

| 新節 | 収容するPolicy核 | 主な旧範囲 |
|---|---|---|
| 1. 目的 | Ubuntu Proを基本とし、Ansibleをreboot制御・healthcheck・通知へ限定する目的 | §1 L10-21 |
| 2. 対象と実行範囲 | 方針1 / 方針2のnode分類、apt /非apt、monthly dry-run / manual applyの範囲 | §2 L25-43、§3 L47-91、§4 L95-129、§5 L133-173 |
| 3. 対応するPlaybook | 旧§5の4入口と、§3.4の既知不一致を持つ候補入口1本 | §3.4 L79-91、§5 L133-173、playbook-map |
| 4. 判断軸 | full-upgrade Status、hold非関与、non-apt判定、reboot要否、healthcheck severity | §3.3-§3.4 L71-91、§4.3 L124-129、§5.1 L148-156 |
| 5. ライフサイクル・処理フロー | unattended更新、月次判定、確認付きapply、reboot、post-check、timer / scheduleへの接続 | §3-§5 L47-173、§7-§8 L239-260 |
| 6. 通知方針 | 状況別通知、channel / status、best-effort | §6 L177-235 |
| 7. 制約・禁止事項 | Ansible定常自動適用禁止、manual apply限定、非apt 3禁止、方針2非管理、apply / reboot gate | §3 L47-91、§4 L95-129、§5 L133-173 |
| 8. 変更履歴 | 旧メタデータと標準化・Context分離を初回記録 | L1-6、新規記録 |

### 2.2 旧section全量配置

| 旧section・行 | 新Policy配置 | 移動先 | 分割方針 |
|---|---|---|---|
| 表題・メタデータ L1-6 | 1、8 | 本013 | 対象と版情報を分ける |
| §1 L10-21 | 1、2 | なし | Ubuntu ProとAnsible責務を保持 |
| §2 L25-43 | 2、7 | System Context | node役割、種別、現行時刻を移し、方針分類と追加時の選択義務を保持 |
| §3 L47-91 | 2、4、5、7 | Repository Context、本013 | apt / nonapt実装・report契約を移し、適用許可、Status、禁止を保持。§3.4不一致は本013で凍結追跡 |
| §4 L95-129 | 2、4、5、7 | System / Repository Context | config値、service / port事実を移し、reboot方針、要否、post-checkを保持 |
| §5 L133-173 | 2、3、5、7 | Repository / Operations Context | 入口・安全度をP3へ、処理詳細をContextへ。対象限定と各gateを保持 |
| §6 L177-235 | 6 | Repository Context | 通知条件を保持し、role / Vault / YAML例を移す |
| §7 L239-249 | 5 | Operations Context | timer名・時刻・移行計画を移し、実行基盤の現行契約を参照する |
| §8 L253-260 | 5 | Operations Context | 全体scheduleの参考表をrunbookへ移す。Policy核はreboot_required時だけ実行する条件 |
| §9 L264-289 | 8の移行根拠 | System Context、本013 | 2026-05-27時点の設定確認を現行Contextへ再確認のうえ移し、時点snapshot自体は本013へ保持 |

表題範囲1行と旧主section 9件の計10行で、L1-289を欠番なく配置する。

## 3. Policy範囲超過候補

Policyは許可・禁止・停止・判断を正本とし、nodeの現状、複数roleの実装契約、runbook、時点履歴を分離する。

| # | 旧section・行 | 種類 | 具体的移動先 | Policyへ残す核 |
|---:|---|---|---|---|
| 1 | L1-6 | metadata | P8と本013 | 対象範囲をP1 / P2へ |
| 2 | §2.2 L34-43 | System Context | 新規 `context/system/ubuntu-vm-patch.md`。node分類、reboot方式、healthcheck有無。時刻はOperations Context | 方針1 / 2の採用と新規node追加時の明示分類 |
| 3 | §3.1 L49-57 | System / Repository Context | System ContextにUbuntu Pro / unattended管理事実、Repository Contextに対象archive contract | security / ESMの定常自動適用とAnsible定常自動適用禁止 |
| 4 | §3.2 L59-69 | Decision / Policy混合 | 自動service restart採用理由は本013。設定実装はRepository Context | apt post-install restart許容、Package-Blacklist不採用 |
| 5 | §3.3 L71-77 | Repository Context | 新規 `context/ansible/ubuntu-vm-patch.md`。report fields、hold / phasing / unpoller表示契約 | monthly dry-run、manual single-node apply、Statusへ使わない情報、候補除外禁止 |
| 6 | §3.4 L79-83 | Repository Context | 同Repository Context。nonapt registry、取得・比較・report I/O | dry-run時だけ確認、両取得成功+数値比較条件 |
| 7 | §3.4 L85-89 | Repository Context + Policy核 | 同Repository Contextへ表示 / JSON schema。判断はP4 | 3表示状態、REVIEW_REQUIRED昇格、上位Status非降格、fail-quiet |
| 8 | §3.4 L91 | 既知不一致 / Issue | 本013とplaybook-mapの既知不一致を参照。実装に合わせて移動・修正しない | 自動download禁止、自動更新禁止、service restart禁止、human manual、apt apply時nonapt check禁止を逐語・意味凍結 |
| 9 | §4.1-§4.2 L97-122 | System / Repository Context | System Contextにnode別reboot管理、Repository Contextにconfig / post-check契約 | 方針1はAnsibleが必要時だけreboot・post-check、方針2は自動rebootでAnsible非管理 |
| 10 | §4.3 L124-129 | Repository Context | reboot flag / needrestartの収集実装 | 2条件のOR判断をP4へ |
| 11 | §5 L133-173 | Repository / Operations Context | 5入口とrole連携はRepository Context、nightly順序は新規 `context/operations/ubuntu-vm-patch.md` | 対象限定、read-only、通知、条件付きreboot、確認順序 |
| 12 | §6.3 L197-219 | Repository Context | common_slack、Vault変数、include契約。秘密値は移さない | Slack経路と秘密管理義務 |
| 13 | §6.3 L221-235 | Repository Context / Policy核 | channel mappingはRepository Context、deprecated mail事実は本013 | 状況別通知強度、best-effort、mail非使用 |
| 14 | §7 L239-249 | Operations Context / roadmap | timer名・schedule・Semaphore移行計画はOperations Contextと本013 | schedulerは実行入口であり適用許可を拡張しない |
| 15 | §8 L253-260 | Operations Context | 新規Operations Contextの参考schedule | reboot_required時だけという実行条件 |
| 16 | §9 L264-289 | System Context / point-in-time evidence | 現行設定はSystem Contextへ再確認後記録。2026-05-27 snapshotは本013 | 方針1 false、方針2 trueというPolicy上の要求 |

範囲超過候補は16行である。§3.4 L91は移動で規範を薄めず、Policyに独立した禁止3件と関連条件を残す。

## 4. 安全境界ledger

### 4.1 記録規則

- 1行を1つの許可・禁止・停止・必須・例外・判断単位とする。
- `P1`〜`P8`は2.1の新標準節、`旧行`はHEAD snapshotとの突合keyである。
- Contextへ移す実装説明に含まれる規範も必ずPolicy到達先を持つ。
- 旧§3.4の既知不一致は実装に合わせて修正せず、Policy原文の許可範囲を拡大も縮小もしない。

### 4.2 全量ledger

| ID | 種別 | 旧行 | 原文の安全境界 | 新Policy先 |
|---|---|---:|---|---|
| UV-001 | 目的 | L12 | homelab Ubuntu nodeのpatch運用方針を定義する | P1 |
| UV-002 | 必須 | L14 | Ubuntu nodeはUbuntu Proによる自動patch適用を基本とする | P1/P5 |
| UV-003 | 制約 | L16-18 | Ansibleはnode特性に応じたreboot timing制御へ限定する | P1/P7 |
| UV-004 | 制約 | L16/L19 | Ansibleはsensitive VMのreboot後service疎通確認へ限定する | P1/P7 |
| UV-005 | 制約 | L16/L20 | Ansibleはsensitive VMの日次healthcheckへ限定する | P1/P7 |
| UV-006 | 制約 | L16/L21 | Ansibleは異常・reboot時の通知へ限定する | P1/P6/P7 |
| UV-007 | 必須 | L29-31 | 停止影響の大きいserviceを持つVMは深夜の計画rebootをAnsible管理する | P2/P5 |
| UV-008 | 必須 | L29/L32 | 開発・backup・検証・infra管理node等は自動rebootとする | P2/P5 |
| UV-009 | 必須 | L38 | authyは方針1としてreboot_required時だけ計画rebootしhealthcheckする | P2/P5 |
| UV-010 | 必須 | L39 | monnieは方針1としてreboot_required時だけ計画rebootしhealthcheckする | P2/P5 |
| UV-011 | 必須/禁止 | L40 | ansyは方針2としてunattended-upgradesに自動rebootを任せ、healthcheckしない | P2/P7 |
| UV-012 | 必須/禁止 | L41 | quoryは方針2として固定時刻の自動rebootとし、ubuntu_nightlyで管理しない | P2/P7 |
| UV-013 | 必須 | L43 | Ubuntu node追加時は表へ追記し、方針1 / 2のどちらかを明示する | P2 |
| UV-014 | 必須 | L51/L53-57 | security / ESM / ESM Appsの定常更新はUbuntu Pro + unattended-upgradesが自動実行する | P2/P5 |
| UV-015 | 禁止/許可 | L51 | Ansibleで定常的に自動適用せず、対象外通常更新だけをmonthly判定と確認付きmanual applyで扱う | P2/P7 |
| UV-016 | 例外 | L61-67 | apt post-installによるservice自動restartを深夜・低需要・低実害を理由に許容する | P2/P5 |
| UV-017 | 禁止 | L69 | serviceをPackage-Blacklistへ追加してmanual管理へ切り替える方式を採用しない | P7 |
| UV-018 | 必須 | L73 | Ubuntu Pro対象外の通常更新をmonthlyにnode単位で判定し`#patches`へ通知する | P4/P6 |
| UV-019 | 禁止/許可 | L73 | monthly実行は`dry_run=true`のread-only判定とし、実適用は確認文字列付きsingle-node manual applyだけを許す | P2/P4/P7 |
| UV-020 | 必須 | L75 | install / remove / phasing保留件数とpackage別versionを通知する | P6 |
| UV-021 | 必須 | L75 | hold packageをread-only収集し、1件以上ある月だけ所定位置へ件数とnameを表示する | P4/P6 |
| UV-022 | 禁止 | L75 | hold一覧をStatus、重要package、件数閾値、apply判断に使用しない | P4/P7 |
| UV-023 | 必須 | L77 | unpollerの同一version文字列候補を既知repository metadata事象として候補表示に残す | P4/P6 |
| UV-024 | 禁止 | L77 | 同一version文字列だけを根拠に専用除外判定を設けない | P4/P7 |
| UV-025 | 許可/制約 | L81 | nonapt productはgeneric registry登録済み対象を`dry_run=true` monthly実行時だけ確認する | P2/P4 |
| UV-026 | 対象 | L81 | 初期対象をmonnieへmanual installされたPrometheusだけとする | P2 |
| UV-027 | 判断 | L81 | current / latestをread-only GETし、両方を数値versionとして取得できた場合だけ比較する | P4 |
| UV-028 | 必須 | L83/L85 | updateあり時はcurrent→latestとmanual update必要を通知 / reportする | P6 |
| UV-029 | 必須 | L83/L86 | latest時はcurrent versionとlatest状態を通知 / reportする | P6 |
| UV-030 | 必須 | L83/L87 | 取得・比較失敗時はcurrent / latest rcを通知 / reportする | P6 |
| UV-031 | 必須 | L83 | reportのnonaptへname / current / latest / state / rc / HTTP status / noteを保存する | P6 |
| UV-032 | 判断 | L89 | 両取得成功かつ数値比較でupdateありが確定した場合だけStatusを最低REVIEW_REQUIREDへ昇格しreasonを追加する | P4 |
| UV-033 | 禁止 | L89 | 既存BLOCKED / MAJOR_UPGRADE_DETECTEDをnonapt結果で降格させない | P4/P7 |
| UV-034 | 例外 | L89 | 取得・parse・比較失敗はfail-quietで通知 / reportだけに残し、Status変更・playbook失敗をしない | P4/P6 |
| UV-035 | 禁止 | L91 | nonapt確認経路はPrometheus artifactの自動downloadを一切行わない | P7 |
| UV-036 | 禁止 | L91 | nonapt確認経路はPrometheusの自動更新を一切行わない | P7 |
| UV-037 | 禁止 | L91 | nonapt確認経路はPrometheus service restartを一切行わない | P7 |
| UV-038 | 必須 | L91 | Prometheus更新は指定手順に従って人間がmanual実行する | P5/P7 |
| UV-039 | 禁止 | L91 | `dry_run=false`のapt apply経路ではnonapt check自体を実行しない | P2/P7 |
| UV-040 | 必須 | L99 | 方針1 VMはunattended-upgradesのAutomatic-Rebootをfalseにする | P2/P7 |
| UV-041 | 必須 | L101 | 方針1 VMのreboot timingはAnsibleが制御する | P5 |
| UV-042 | 判断/許可 | L103 | nightlyがreboot_requiredを確認し、必要な場合だけrebootする | P4/P5 |
| UV-043 | 必須 | L105 | reboot後に対象VMのservice状態と疎通を確認する | P5 |
| UV-044 | 必須 | L108 | authy post-checkはFreeRADIUS状態と規定RADIUS portのlistenを確認する | P4/P5 |
| UV-045 | 必須 | L109 | monnie post-checkはPrometheus / Grafana / Lokiの規定port listenを確認する | P4/P5 |
| UV-046 | 必須 | L113 | 方針2 nodeはunattended-upgradesのAutomatic-Rebootをtrueにする | P2/P7 |
| UV-047 | 判断/許可 | L115 | 方針2はunattended-upgradesがreboot_requiredを検出した場合に自動rebootする | P4/P5 |
| UV-048 | 禁止 | L117 | 方針2をAnsible管理・監視・healthcheckの対象にしない | P2/P7 |
| UV-049 | 例外 | L121 | ansyは再構築・backup前提により自動rebootを許容する | P2 |
| UV-050 | 必須/禁止 | L122 | quoryは自身が実行基盤のためnightly管理せず、Automatic-Reboot-Timeを固定する | P2/P7 |
| UV-051 | 判断 | L126/L128 | 方針1はreboot-required fileが存在すればreboot要と判定する | P4 |
| UV-052 | 判断 | L126/L129 | 方針1はneedrestartがreboot要と判定すればreboot要とする。UV-051との関係はOR | P4 |
| UV-053 | 対象/禁止 | L135 | Policy対応playbookは方針1 VMだけを対象とし、方針2 nodeをAnsible管理対象にしない | P2/P3/P7 |
| UV-054 | 必須 | L144 | serviceに応じた専用healthcheck playbookを用意する | P3 |
| UV-055 | 禁止/必須 | L150 | healthcheckはread-onlyでservice状態を収集・判定・reportする | P3/P7 |
| UV-056 | 必須 | L152 | healthcheckがWARNING / CRITICALなら通知する | P4/P6 |
| UV-057 | 必須 | L154 | 朝healthcheckで前夜reboot後のservice稼働を確認する | P5 |
| UV-058 | 許可 | L156 | healthcheckのmanual standalone実行を許す | P3 |
| UV-059 | 対象 | L146/L160 | ubuntu_nightlyは方針1 groupだけを対象とする共通深夜reboot入口とする | P2/P3 |
| UV-060 | 必須 | L165 | nightlyは最初にreboot_requiredを確認する | P4/P5 |
| UV-061 | 停止 | L166 | reboot_required=falseならrebootせず通知もしない | P4/P5/P6 |
| UV-062 | 必須 | L167-168 | reboot_required=trueならreboot実行前に開始通知する | P5/P6 |
| UV-063 | 許可 | L169 | gate通過後にrebootを1回実行する | P5 |
| UV-064 | 必須 | L170 | reboot後の起動完了を待つ | P5 |
| UV-065 | 必須 | L171 | 起動後に対象VMのservice状態を確認する | P5 |
| UV-066 | 必須 | L172 | post-check結果をOK / CRITICALで通知する | P5/P6 |
| UV-067 | 禁止 | L183 | nightlyでreboot_required=falseなら通知しない | P6 |
| UV-068 | 必須 | L184 | reboot実行後post-check OKならreboot実施とOKを通知する | P6 |
| UV-069 | 必須 | L185 | reboot実行後post-check NGならCRITICAL通知する | P6 |
| UV-070 | 必須 | L186 | full-upgrade monthly dry-run / manual applyはnode単位で通知し、通常`#patches`、BLOCKEDだけ`#alerts`とする | P6 |
| UV-071 | 禁止 | L187 | healthcheck OKは通知しない | P6 |
| UV-072 | 必須 | L188 | healthcheck WARNINGは通知する | P6 |
| UV-073 | 必須 | L189 | healthcheck CRITICALは通知する | P6 |
| UV-074 | 例外 | L193-195 | 深夜通知は翌朝確認する運用を許容する | P6 |
| UV-075 | 必須 | L199-201 | Slack通知はcommon role経由とし、WebhookはVault管理する | P6/P7 |
| UV-076 | 必須 | L223-231 | nightly、full-upgrade、healthcheckを状況別channel / statusへ割り当てる | P6 |
| UV-077 | 例外/禁止 | L233 | 通知失敗はbest-effortとし、caller playを停止しない | P6 |
| UV-078 | 禁止 | L235 | Slack移行taskからmail varsを参照せず、mail moduleを使用しない | P6/P7 |
| UV-079 | 必須 | L241 | systemd timerはquory上で実行する | P5 |
| UV-080 | 必須 | L245 | authy nightlyを規定timerで毎日03:30にscheduleする | P5 |
| UV-081 | 必須 | L246 | authy healthcheckを規定timerで毎日05:30にscheduleする | P5 |
| UV-082 | 必須 | L247 | monitoring healthcheckを規定timerで毎日05:35にscheduleする | P5 |
| UV-083 | roadmap | L249 | Semaphore UI導入後はtimerからSemaphore Scheduleへ移行する | P8から本013 / Operations Context参照 |

### 4.3 §3.4凍結gate

UV-035、UV-036、UV-037を一つの「自動変更なし」へ畳み込まない。Reviewerは旧L91と新Policyを文言・意味単位で比較し、次の3禁止がそれぞれ独立して存在することを確認する。

1. 自動downloadを一切行わない。
2. 自動更新を一切行わない。
3. service restartを一切行わない。

さらにUV-038のhuman manualとUV-039の`dry_run=false`時nonapt check禁止を別条件として保持する。`prometheus_update_check.yml` / roleが確認入力に基づくupdate、rollback、service restartを実装する事実はplaybook-mapに記録済みだが、Phase 2でPolicyを実装へ合わせない。実装を禁止へ合わせる判断も行わない。不一致の大きさを変えず、別Issueへ残す。

### 4.4 Reviewerの逐行照合規則

ledger要約は旧原文の代替ではない。各`旧行`の表行、箇条書き、規範文を個別に展開し、新Policy到達行へ `保持` / `欠落` / `緩和` / `厳格化` / `条件・例外・順序変更` を記録する。特に`だけ`、`のみ`、`一切`、`場合`、OR条件、Status非降格、fail-quiet、single-node、manual confirmation、通知なしを落とさない。

## 5. 対応Playbook全件の実装突合

### 5.1 新Policy P3へ列挙する5入口

| Playbook | 実path | 主role / task | 旧Policyとの関係 | P3での扱い |
|---|---|---|---|---|
| `radius_healthcheck.yml` | 実在 | `radius_healthcheck` | 旧§5 L139/L148-156 | read-only healthcheck |
| `monitoring_healthcheck.yml` | 実在 | `monitoring_healthcheck` | 旧§5 L140/L148-156 | read-only healthcheck |
| `ubuntu_nightly.yml` | 実在 | playbook tasks、`recovery_mute`、`monitoring_healthcheck`、`common_slack` | 旧§4.1、§5 L141/L158-173 | reboot lifecycle従属、条件付き変更 |
| `ubuntu_vm_full_upgrade.yml` | 実在 | `ubuntu_vm_full_upgrade`、`recovery_mute`、healthcheck roles | 旧§3.3-§3.4、§5 L142 | monthly read-only判定と確認付きmanual apply |
| `prometheus_update_check.yml` | 実在 | `prometheus_update_check`、`common_slack` | playbook-mapが旧§3.4のPolicy候補として記録 | **既知不一致入口**。P3へ存在と不一致を列挙するが、Policy上のupdate許可を作らない |

旧§5の明示表は4本だが、playbook-mapは`prometheus_update_check.yml`を§3.4候補としてPolicy owner欄に持つ。標準P3では入口を隠さず5本を列挙し、5本目は「PolicyのUV-035〜UV-039と実装が不一致で未解決」と明示する。列挙自体を許可へ読み替えない。

### 5.2 group2境界

| group2入口 | 本Policyとの境界 |
|---|---|
| `ubuntu_vm_full_upgrade.yml` | 本Policyのapt / registry nonapt monthly判定とmanual applyの主入口 |
| `prometheus_update_check.yml` | 論理group2のnonapt入口だが、本Policyとの既知不一致を解消するまで実装の変更機能を本Policyが許可したと扱わない |
| `ubuntu_nightly.yml` | package更新入口ではなく、更新後に必要となるreboot lifecycleの従属入口 |
| `codex_update_check.yml` | group2横断indexには含まれるが、本PolicyのUbuntu node patch / reboot owner外。P3へ追加しない |
| `radius_healthcheck.yml` / `monitoring_healthcheck.yml` | group1の横断health indexからも参照されるが、Policy ownerは本Policyのまま。group2の更新入口へ分類しない |

group2はPolicy統合案でなく論理indexである。`alloy_setup.yml`等の構成配備をapt利用だけで本Policyへ含めず、`codex_update_check.yml`の更新規範も本Policyへ取り込まない。

## 6. 変更履歴・制約見出しの計画

- P7「制約・禁止事項」を新設し、UV-015、UV-017、UV-019、UV-022、UV-024、UV-033、UV-035〜UV-037、UV-039、UV-040、UV-046、UV-048、UV-050、UV-053、UV-055、UV-061、UV-067、UV-071、UV-077、UV-078を判断節・flowから参照できる形で集約する。
- P8「変更履歴」を新設し、旧v1.5 metadataと今回の標準8節化、Context分離、§3.4不一致の非解消を記録する。
- P7へ移動しても、P4 / P5に必要な判断・順序を消さず、相互参照で一つの規範を二重定義しない。

## 7. Phase 2編集path案と移動理由

Phase 1では未編集。Tech Leadの明示承認後に限る。

| path | 予定操作 | 選定理由 |
|---|---|---|
| `docs/ai/policies/ubuntu_vm_patch_policy.md` | 標準8節へ全面再編 | 許可・禁止・停止・判断の正本 |
| 新規 `docs/ai/context/system/ubuntu-vm-patch.md` | node分類、Ubuntu Pro / reboot管理の現状 | 既存overview / radius / monitoringへlinkし、node役割を複製せずpatch固有の現状だけを収容 |
| 新規 `docs/ai/context/ansible/ubuntu-vm-patch.md` | 5入口、role連携、apt / nonapt、report、notification contract | 複数playbook / role横断のRepository Context |
| 新規 `docs/ai/context/operations/ubuntu-vm-patch.md` | monthly判定 / manual apply、nightly、timer / schedule runbook | 複数入口を順序で読む運用情報 |
| 新規Phase 2 implement記録 | 16候補、UV index、検査実績 | migration auditと§3.4凍結証跡 |

既存System Contextは参照先として使い、同じhost役割を新Contextへ複製しない。playbooks、roles、他Policy、map、requirement、本013、既存他者変更はPhase 2でもTech Leadが明示しない限り編集しない。

## 8. 重複・矛盾リスクと未解決点

| リスク | 実測 | Phase 2対策 |
|---|---|---|
| §3.4 Policy /実装不一致 | playbook-map L49が明示。roleはupdate / rollback / restart機能を持つ | UV-035〜UV-039を凍結し、P3で不一致を見える化するだけ。解消しない |
| P3列挙と実行許可の混同 | `prometheus_update_check.yml`を追加すると許可に見え得る | 「存在 / owner候補」と「Policy上の許可」を別columnにし、P7禁止を優先する |
| group1 / group2重複 | 2 healthcheckはgroup1、nightlyはgroup2従属 | Policy ownerを変えず、論理indexの多重参照として説明する |
| node tableと既存System Context | overview / radius / monitoringにrole事実が既にある | 新System Contextはpatch / reboot管理の差分だけを記載して既存へlinkする |
| §3.3と§5 full-upgrade重複 | 判定・apply説明が分散 | P4に判断、P5にflow、P7に禁止を一度ずつ置く |
| §4と§5 nightly重複 | reboot条件と手順が重複 | P4にOR条件、P5に一つのflow、Operationsにrunbookを置く |
| §6 notification code複製 | Vault / YAML例がPolicyに同居 | P6は通知契約、Repository Contextは共通role I/O。秘密値は移さない |
| scheduleの時点依存 | timerと将来Semaphore計画が同居 | 現行runbookとroadmap履歴を分け、schedulerを許可gateにしない |

Phase 2を止める受け皿未決はない。§3.4不一致は意図的な未解決事項であり、Phase 2完了条件は「不一致解消」ではなく「Policy文言・意味と不一致範囲が変化していないこと」である。

## 9. 検査計画

### 9.1 Phase 1

- HEAD commit / blob / 289行、主section 9件を記録する。
- 全量配置が表題1 + §1〜§9の10行で欠番なくL1-289を覆うことを確認する。
- 範囲超過候補16行の種類、移動先、Policy核に空欄がないことを確認する。
- UV ledgerが連番・重複なしで、各行に種別、旧行、Policy先を持つことを確認する。
- P3候補5 playbookの実path、playbook-map owner、role / task入口を確認する。
- group2の4入口とhealthcheck 2入口の境界を記録する。
- Markdown空table cell、IPv4、VLAN / VM ID /認証 /秘密実値、末尾空白を検査する。
- `git diff --check`と未追跡013の`git diff --no-index --check`を実施する。

Phase 1実測結果:

| 検査 | 結果 |
|---|---|
| HEAD snapshot | commit `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `bf8cee43f3789dbae1b0a524f84fdb694a5445c7`、289行で一致 |
| 全量配置 | 表題範囲1行 + 主section 9行 = 10行、§1〜§9の欠番なし |
| 範囲超過候補 | 16行、種類・移動先・Policy核の空欄0 |
| safety ledger | UV-001〜UV-083の83件、連番欠落0、重複0、必須cell空欄0 |
| 対応Playbook | 5本、実path欠落0、playbook-map参照5、role / task入口欠落0 |
| group2境界 | group2 4入口とhealthcheck 2入口を分類し、Policy owner変更0 |
| §3.4凍結 | 自動download /自動更新 / service restartの独立禁止3件、human manual、apt apply時nonapt check禁止を独立追跡 |
| Markdown | 空table cell 0 |
| 禁止実値 | IPv4 0、VLAN ID / VM ID /認証情報 /秘密の実値0 |
| scope | 本013だけを新規作成。Policy / Context / playbook / role / map / requirementに本件変更なし |
| whitespace | `git diff --check` PASS、`git diff --no-index --check /dev/null <本013>` PASS |

### 9.2 Phase 2

- 標準8見出しが順番どおり各1回で、P3が5入口を過不足なく列挙すること。
- 16候補すべてに実移動先とPolicy核の最終行があること。
- UV ledger全件に新Policy marker /行indexがあり、旧HEAD逐行比較で欠落・緩和・厳格化・条件変更0であること。
- UV-035、UV-036、UV-037が独立し、`一切行わない`を維持すること。
- UV-038のhuman manual、UV-039の`dry_run=false` nonapt check禁止を維持すること。
- `prometheus_update_check.yml`の現行実装を根拠にPolicyを緩和せず、逆にコード変更で不一致を縮小しないこと。
- 3 Contextの非規範 / Policy優先link、重複、旧path、実値、秘密、空表、linkを検査すること。
- 承認path外、特にplaybooks / roles /他Policy / map / requirement /本013にdiffがないこと。
- tracked / untracked whitespaceを確認し、実機・Ansibleを実行しないこと。

## 10. Phase 1結論

旧Policyは16の範囲超過候補を持ち、Policy核は標準8節へ配置できる。安全境界はUV-001〜UV-083として追跡し、明示4入口に既知不一致候補1入口を加えた5 playbookをP3計画とする。最大リスクは§3.4を現行実装へ合わせて緩和すること、または実装を禁止へ合わせて本件scopeを拡張することである。どちらも行わず、UV-035〜UV-039と4.3のgateをPhase 2の凍結契約とする。
