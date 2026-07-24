# Proxmox Backup Restore Verify Policy 標準構造書換 Phase 1 調査

## 1. 調査範囲と正本

- requirement: `2026-07-24_016_requirement_proxmox_backup_restore_verify_policy_rewrite.md`
- 旧Policy正本: Git HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79` の `docs/ai/policies/proxmox_backup_restore_verify_policy.md`
- 旧Policy blob: `9204b94e61d0f3eb652e03406373cbacc5d0af5d`
- 旧Policy規模: 217行、主section 11件
- 実装突合: `playbooks/proxmox_backup_restore_verify.yml`、`roles/proxmox_backup_restore_verify/defaults/main.yml`、`roles/proxmox_backup_restore_verify/tasks/main.yml`、playbook-map、role-map
- Phase 1で編集したファイル: 本017のみ
- 未実施: Policy、Context、playbook、role、map、requirementの編集、実機・Ansible実行

行番号はすべて上記HEAD snapshotの1始まりである。旧Policyとcodeにある専用restore VMの数値VM IDは本書へ転載せず、`verify_restore_vmid`と「専用固定restore VMID」で表す。IP、VLAN ID、その他のVM ID、認証情報、秘密情報も転載しない。

## 2. 標準8節への旧文書全量配置

### 2.1 新Policyの標準8節

| 新節 | 収容するPolicy核 | 主な旧範囲 |
|---|---|---|
| 1. 目的 | backupを実restore / bootしてsilent corruptionを本番無影響で検出する目的 | §1 L14-20 |
| 2. 対象と実行範囲 | `verify` tag、monthly 1台、manual bypass、実行元、controlled apply、除外scope | §2 L24-41、§3 L51-77、§10 L193-204 |
| 3. 対応するPlaybook | 単一入口とrisk-accepted /常時本実行の境界 | L43-47、実playbook |
| 4. 判断軸 | 対象選定、latest backup、agent期待、正常性、lock、residue、ownership、cleanup、終了code | §3 L51-77、§5-§7 L104-163、§11 L208-217 |
| 5. ライフサイクル・処理フロー | lock、residue guard、restore、NIC切断、boot、health、rescue、always cleanup / report / notify / re-fail | §4 L81-100、§7 L157-163 |
| 6. 通知方針 | priority、channel / status、report、best-effort | §8 L167-178 |
| 7. 制約・禁止事項 | 本番VM read-only、同時実行禁止、固定destroy対象、ownership、秘密 / IP禁止、現行除外scope | §6 L120-153、§9 L182-189、§10 L193-204 |
| 8. 変更履歴 | 旧metadata、標準化、Context分離、数値VM ID除去 | L1-12、新規記録 |

### 2.2 旧section全量配置

| 旧section・行 | 新Policy配置 | 移動先 | 分割方針 |
|---|---|---|---|
| 表題・metadata・参照 L1-12 | 1、8 | 本017 | 版 / 対象 /旧参照を履歴化し、目的とscopeをP1 / P2へ |
| §1 L14-20 | 1、2、7 | System / Repository Context | silent corruption検出と本番非変更をPolicyに保持。専用restore値はvars / code正本 |
| §2 L24-41 | 2、3、7 | System / Repository Context | storage / node / controller事実と実装pathを移し、対象 / controlled apply /本番非変更を保持 |
| 対応するPlaybook L43-47 | 3 | Repository Context | 入口はP3へ保持し、2-play / role連携をRepository Contextへ |
| §3 L51-77 | 2、4、5、7 | Repository Context | selection algorithm、tag / config / dynamic groupを移し、対象、manual bypass、fail gateを保持 |
| §4 L81-100 | 5、7 | Repository Context | phase / block構造とcommand配管を移し、順序、rescue / always、本番隔離を保持 |
| §5 L104-116 | 4、5 | Repository Context、本017 | agent別合格基準を保持し、poll / settle値はcode、将来serial案は本017 |
| §6 L120-153 | 4、7 | Repository Context、本017 | lock実装を移し、運用禁止、補助的位置づけ、lock非依存guard、残余riskを保持 |
| §7 L157-163 | 4、5、7 | Repository Context | cleanup条件、live state、ownership、destroy失敗、終了codeを保持 |
| §8 L167-178 | 6 | Repository Context | notification / report配管を移し、priorityと状況別契約を保持 |
| §9 L182-189 | 7 | なし | 全項目を標準P7へ統合する |
| §10 L193-204 | 2、7、8 | Repository Context、本017 | 実装済み一覧はRepository、現行除外はP2 / P7、不要判断 / roadmapはP8 /本017へ分割 |
| §11 L208-217 | 4、7 | 本017、Phase 2 review記録 | 見出し自体は履歴。各bulletの安全判断はP4 / P7へ到達させる |

表題範囲1行と旧主section 11件、独立した「対応するPlaybook」1件の計13行でL1-217を欠番なく配置する。

## 3. Policy範囲超過候補

Policyは許可、禁止、停止、正常性、lock、cleanup、ownership、終了code、通知判断を正本とする。単一taskのcommand、変数既定値、2-play配管はcodeを正本とし、複数fileを横断する契約だけをRepository Contextへまとめる。

| # | 旧section・行 | 種類 | 具体的移動先 | Policyへ残す核 |
|---:|---|---|---|---|
| 1 | L1-12 | metadata /旧参照 | P8と本017 | 対象と目的をP1 / P2へ |
| 2 | §2 L26-34 | System / Repository Context混合 | `context/system/proxmox.md`へbackup / storage / controller事実、Repository Contextへ対象 / destination変数 | monthly対象1台、専用固定restore先、controlled apply、本番VM非変更 |
| 3 | §2 L36-41 | Repository Context | 新規 `context/ansible/proxmox-backup-restore-verify.md`へplaybook / role / dynamic target契約 | 対応入口をP3、inventoryを変更しない境界をP7 |
| 4 | §3 L53-54 | Repository Context | 同Repository Contextへcluster resource / tag source | Ansible側固定対象listを持たずtagを対象正本にする |
| 5 | §3.1 L58-63 | Repository Context | 同Repository Contextへsort / month index /非永続化 | `verify` tag対象、deterministic monthly rotation |
| 6 | §3.2 L67-68 | Repository Context + Policy核 | CLI形式は同Repository Context、許可 /停止条件はP2 / P4 | manual bypassはrotationだけを迂回し、対象が存在しなければ停止 |
| 7 | §3.3 L72-77 | Repository Context | tag / config / `add_host`契約を同Repository Context | prefer tag必須、agent期待分岐 |
| 8 | §4 L83 | Repository / System Context | become / NFS permission事実をRepository / System Context | root実行を他権限の許可へ拡張しない |
| 9 | §4 L85-96 | Repository Context | 2-play / role phase、ctime sourceを同Repository Context | lock→residue→restore→isolate→boot→health→alwaysの順序 |
| 10 | §4 L98-100 | Repository Context | command / shell責務を同Repository Context | 破壊commandの条件と判定 / failをAnsible側で明示制御 |
| 11 | §5 L106-116 | Repository Context / roadmap | poll / settle /分離blockは同Repository Context、serial案は本017 | agent設定別の2合格基準、agent無しを特別扱いしない |
| 12 | §6.2 L132-138 | Repository Context | lock path、atomic mkdir、empty dir / stale回収、release配管を同Repository Context | non-wait fail、lockは補助、取得時だけ解放 |
| 13 | §6.3 L143-147 | Repository Context + Policy核 | assert / token実装を同Repository Context | fixed destroy、residue非接触、own / unstamped / other-tokenの3 ownership分岐 |
| 14 | §6.4 L149-153 | Decision / history | 採択経緯を本017、現行判断をP7 | stale窓の残余riskは一時検証損失に限定し、本番影響なしとして受容 |
| 15 | §7 L157-163 | Repository Context + Policy核 | always / live query / cleanup配管を同Repository Context | cleanup発火AND条件、ownership、destroy失敗、検証失敗OR cleanup失敗の非ゼロ終了 |
| 16 | §8 L167-178 | Repository Context + Policy核 | common Slack / report pathを同Repository Context | best-effort、priority、channel / status 3条件 |
| 17 | §10.1 L195-198 | Repository Context | 同Repository Contextの現行capability一覧 | 一覧を新たな許可へ読み替えない |
| 18 | §10.2 L200-204 | scope / roadmap | 現行除外をP2 / P7、将来案 /不要判断を本017 | serial判定とfreshnessを現行合格基準に混ぜず、履歴永続化を要求しない |
| 19 | §11 L208-217 | review history + Policy核 | 合意時点の重点は本017、Phase 2 review checklist | backup選択、隔離health、fixed destroy、failure cleanup、結果整合、本番非変更をP4 / P7で保持 |
| 20 | 旧数値restore VMIDの全出現 | forbidden value / value source | `verify_restore_vmid`、role defaults / tasksを正本。本017 / 新Policy / Contextへ数値転載しない | 専用固定restore VMID以外をdestroyしない規範を値非依存で保持 |

範囲超過候補は20行である。候補20は複数sectionに現れる同一実値の横断除去であり、各旧範囲の内容追跡を置換しない。

## 4. 安全境界ledger

### 4.1 記録規則

- 1行を1つの許可、禁止、停止、正常性、lock、cleanup、ownership、終了code、通知、scope単位とする。
- `P1`〜`P8`は2.1の標準節、`旧行`はHEAD snapshotとの突合keyである。
- 数値restore VMIDは記載せず、旧原文の固定値条件を`verify_restore_vmid` /専用固定restore VMIDへ置換する。
- lock取得、owner token、未刻印、一時resource存在、cleanup失敗を一つの「安全にcleanup」へ平坦化しない。
- ledger要約は旧原文の代替ではない。Phase 2 Reviewerは旧行と新Policy marker直後を条件、例外、AND / OR、順序、best-effort、非ゼロ終了単位で比較する。

### 4.2 全量ledger

| ID | 種別 | 旧行 | 原文の安全境界 | 新Policy先 |
|---|---|---:|---|---|
| BRV-001 | 目的 /必須 | L16-18 | core VM backupを実restoreしてbootできることをmonthly検証し、silent corruptionを本番無影響で検出する | P1 |
| BRV-002 | 制約 | L20 | 検証は専用固定restore VMIDへ行い、本番VMにはconfig read以外で触れない | P1/P7 |
| BRV-003 | 対象 | L28 | `verify` tagを持つVMからmonthly rotationで選ばれた1台を対象にする | P2/P4 |
| BRV-004 | 制約 | L29 | restore先は専用固定restore VMIDだけとし、使い捨てる | P2/P7 |
| BRV-005 | 必須 /停止 | L30 | restore nodeは対象VMの`prefer<node>` tagで決め、決定できなければ停止する | P2/P4 |
| BRV-006 | 実行範囲 | L31 | monthly productionは`quory`、development / manual CLIは`ansy`を実行元とする | P2 |
| BRV-007 | 判断 | L32 | backup storage未指定時はNFS typeかつcontentにbackupを含むstorageを自動検出する | P4 |
| BRV-008 | 対象 | L33 | restore storageは設定された専用storageを使う | P2 |
| BRV-009 | 許可 /禁止 | L34 | controlled applyとして専用restore VMのcreate / start / deleteを許可するが、本番VMのreboot / migrateを許可しない | P2/P7 |
| BRV-010 | 制約 | L41 | 対象決定のためinventory / group vars / host varsを変更せず、tagで動的決定する | P2/P7 |
| BRV-011 | 対応入口 | L43-47 | 対応playbookを`proxmox_backup_restore_verify.yml`の1本とする | P3 |
| BRV-012 | 必須 | L53-54 | cluster resourcesから対象を決め、Ansible側に対象VM listを持たずProxmox tagだけで増減に対応する | P2/P4 |
| BRV-013 | 対象 | L58 | monthly rotationは`verify` tagを持つQEMU VMだけを列挙する | P2/P4 |
| BRV-014 | 判断 | L59 | 対象候補をVM ID昇順でsortしてdeterministicな順序を得る | P4 |
| BRV-015 | 判断 | L60 | 現在月を候補list長で剰余したindexによりmonthly対象を確定する | P4 |
| BRV-016 | 例外 | L62-63 | VM増減時はtagだけでindexを振り直し、月番号固定方式のため検証履歴を永続化しない | P2/P8 |
| BRV-017 | 許可 /例外 | L67-68 | `target_vmid`指定時はrotationを無視してそのQEMU VMをmanual対象にできる | P2/P4 |
| BRV-018 | 停止 | L68 | manual指定対象が存在しなければ停止する | P4 |
| BRV-019 | 必須 /停止 | L72 | restore nodeは`prefer<node>` tagから決め、tagがなければ停止する | P4 |
| BRV-020 | 判断 | L73-74 | 本番VM configのagentが`1`または`enabled=1`を含む場合だけagent期待とし、それ以外をagent無しとする | P4 |
| BRV-021 | 必須 | L75-77 | 選定結果をdynamic groupへ渡し、Play 2を選定nodeだけで実行する | P5 |
| BRV-022 | 権限 | L83 | NFS access要件のためPlay 2をroot権限で実行する | P2/P7 |
| BRV-023 | 順序 | L85-87 | lifecycleは最初に最小lockを取得し、次に既存restore残骸を確認する | P5 |
| BRV-024 | 停止 /通知 | L87 | 専用固定restore VMIDが既存なら触れず、critical通知して中断する | P4/P6/P7 |
| BRV-025 | 判断 | L88/L96 | storage content APIのctimeが最も新しいbackupを選ぶ | P4/P5 |
| BRV-026 | 許可 | L89 | 選定backupを専用固定restore VMIDへrestoreする | P5 |
| BRV-027 | ownership | L89 | restore後、descriptionへ一意owner tokenを刻印する | P4/P5/P7 |
| BRV-028 | 必須 /禁止 | L90 | boot前に全NIC deviceを削除し、IPを指定しない | P5/P7 |
| BRV-029 | 許可 | L91 | NIC切断後の専用restore VMをstartする | P5 |
| BRV-030 | 必須 | L92 | start後にP4の正常性を判定する | P4/P5 |
| BRV-031 | rescue | L93 | lifecycle失敗はrescueで捕捉する | P5 |
| BRV-032 | always | L94 | 成否にかかわらずalwaysでcleanup、lock解放、report、通知、条件付きre-failを行う | P5 |
| BRV-033 | 責務 | L98-100 | restore / set / start / stop / destroy / guest commandの条件とOK / NG / failはAnsible task側で明示制御する | P5/P7 |
| BRV-034 | 禁止 | L100 | 専用shell scriptへ破壊操作や判断を移さない | P7 |
| BRV-035 | 判断 | L106-107 | 期待levelは本番VMのagent設定、実測はrestore VMのboot結果とし、実測が期待へ到達したかで合否を決める | P4 |
| BRV-036 | 正常性 | L109-112 | agent対応VMはguest agentのosinfo取得成功を合格とする | P4 |
| BRV-037 | 正常性 | L109-112 | agent無しVMはboot後の規定settle期間後もrunningなら合格とする | P4 |
| BRV-038 | 禁止 | L114 | agent無しVMはrunning継続だけで合格とし、特定製品を特別扱いしない | P4/P7 |
| BRV-039 | scope | L115-116 | agent無し判定blockは将来serial console判定へ交換可能な形で分離するが、現行基準へserial判定を追加しない | P2/P7 |
| BRV-040 | 禁止 | L124-125 | 同時実行を運用で禁止する | P7 |
| BRV-041 | lock | L124-125 | lockは同時実行禁止を補助する最小guardであり、完全なdistributed mutexと扱わない | P4/P7 |
| BRV-042 | 必須 | L127 | monthlyは`quory`から固定時刻のsingle scheduleで実行する | P2/P7 |
| BRV-043 | manual gate | L128 | `ansy` manual実行時は人間がmonthlyと重複しないことを確認する | P4/P7 |
| BRV-044 | lock | L132-133 | pmxcfs上のofficial lockをatomic mkdirで取得する | P4/P5 |
| BRV-045 | 停止 /通知 /終了 | L133 | lockが既存なら待機せず即停止し、通知して非ゼロ終了する | P4/P6/P7 |
| BRV-046 | lock | L134-135 | lock directoryをemptyに保ち、pmxcfs標準のstale回収を有効にする | P4/P7 |
| BRV-047 | 禁止 | L136 | lock refresher、期限更新、生存監視、孤児管理を持たない | P7 |
| BRV-048 | lock / ownership | L137 | lockは取得した場合だけempty directoryをrmdirして解放する | P4/P5/P7 |
| BRV-049 | 原則 | L139-141 | production harm防止をlockに依存させない | P4/P7 |
| BRV-050 | hard guard | L143 | destroy対象を専用固定restore VMIDへhard assertし、それ以外を絶対にdestroyしない | P4/P7 |
| BRV-051 | residue | L144 | 開始時に専用restore VMが存在すれば既存物へ触れずcritical通知して停止する | P4/P6/P7 |
| BRV-052 | ownership | L145-147 | cleanupはowner tokenが自runと一致する場合にdestroyする | P4/P7 |
| BRV-053 | ownership /例外 | L145-147 | 未刻印は同時実行禁止前提で自runの途中失敗とみなしdestroyを許可する | P4/P7 |
| BRV-054 | ownership /禁止 | L145-147 | 別runのowner tokenがあればdestroyせず触れない | P4/P7 |
| BRV-055 | residual risk | L151-153 | stale回収窓を超えて低頻度の同時実行が重なる場合、一時検証1 cycleの損失を残余riskとして受容する | P4/P7 |
| BRV-056 | residual boundary | L151-153 | BRV-055の最悪影響を使い捨て検証に限定し、本番影響はない | P4/P7 |
| BRV-057 | cleanup gate | L159 | cleanupはrestoreを試行したAND開始前残骸でない場合だけ実行する | P4/P5/P7 |
| BRV-058 | cleanup | L160 | cleanup時はlive stateを再取得する | P4/P5 |
| BRV-059 | cleanup gate | L160-161 | restore VMが現存しownershipが真の場合だけstopをbest-effortで試し、destroy / purgeする | P4/P5/P7 |
| BRV-060 | cleanup failure | L162 | destroy失敗によりrestore VMが残れば`cleanup_ok=false`とする | P4/P7 |
| BRV-061 | 終了code | L163 | verification失敗OR cleanup失敗のいずれかで非ゼロ終了する | P4/P7 |
| BRV-062 | 通知 | L169-170 | common Slack taskを使い、通知をbest-effortとする | P6 |
| BRV-063 | 通知判断 | L169-170 | 通知priorityをcritical、error、okの順とする | P4/P6 |
| BRV-064 | 通知 | L174 | verification OKはinfo channelへokで通知する | P6 |
| BRV-065 | 通知 | L175 | restore失敗または正常性未達はalerts channelへerrorで通知する | P6 |
| BRV-066 | 通知 | L176 | 既存restore残骸またはdestroy失敗はalerts channelへcriticalで通知する | P6 |
| BRV-067 | report | L178 | JSON reportを設定されたreport directoryへ保存する | P6 |
| BRV-068 | 禁止 | L184 | 本番VMにはconfig read以外で触れない | P7 |
| BRV-069 | 禁止 | L185 | 秘密情報を扱わない | P7 |
| BRV-070 | 禁止 | L186-187 | IP literalをfileへ書かず、NIC切断はdevice削除で行いIPを指定しない | P7 |
| BRV-071 | 変更境界 | L188-189 | 変更系として専用restore VMのcreate / start / stop / deleteだけを行い、本番VMはconfig read-onlyとする | P2/P7 |
| BRV-072 | current scope | L195-198 | 現行scopeはrotation、latest backup、restore、NIC isolation、boot、health、destroy、safety、minimal lock、Slackを含む | P2/P3/P5 |
| BRV-073 | 除外 | L200-203 | agent無しVMのserial console文字列matchを現行scopeへ含めない | P2/P7 |
| BRV-074 | 除外 | L203 | backup freshness checkを現行scopeへ含めず、取得側整備後の別playbookとする | P2/P7 |
| BRV-075 | 除外 /不要 | L204 | 月番号固定方式のためverification history永続化を現行scopeへ含めない | P2/P8 |
| BRV-076 | review方針 | L210 | lock ownershipの深掘りより本質的な危害防止と結果整合へreview重点を置く | P4/P7/P8 |
| BRV-077 | review判断 | L212 | latestかつ正しいtarget VMのbackupを選べることを確認する | P4 |
| BRV-078 | review判断 | L213 | NIC isolation後にbootし有効な正常性判定ができることを確認する | P4/P7 |
| BRV-079 | review判断 | L214 | destroy対象が構造的に専用固定restore VMIDへ限定されることを確認する | P4/P7 |
| BRV-080 | review判断 | L215 | failure時に専用restore VMをownership条件どおり安全に処理できることを確認する | P4/P7 |
| BRV-081 | review判断 | L216 | Slack、report、終了codeが実結果と一致することを確認する | P4/P6/P7 |
| BRV-082 | review判断 | L217 | 本番VMへ変更操作が及ばないことを確認する | P7 |

ledgerはBRV-001〜BRV-082の82件である。

### 4.3 Reviewerの重点逐行照合

Phase 2では次を独立して比較する。

1. `target_vmid` manual bypassはmonthly rotationだけを迂回し、存在確認、restore node tag、agent期待、本番非変更、fixed restore / destroyを迂回しない。
2. lock取得失敗はwaitせず停止 /通知 /非ゼロ終了するが、lock自体をproduction harm防止の根拠にしない。
3. cleanupは`restore_attempted AND not preexisting_residue`、live existence、ownershipの順で判定する。
4. owner tokenはown / empty / otherの3分岐を維持する。emptyは運用上のno-overlap前提に依存する例外で、otherはdestroy禁止である。
5. `rescue`のverification failureとcleanup blockのfailureを分け、最終終了は`verification failure OR cleanup failure`とする。
6. stopはbest-effortだがdestroy失敗はcleanup failureであり、同じbest-effortとして扱わない。
7. notification failureはbest-effortで終了codeを変えない。

## 5. Playbook / role / mapの実装突合

### 5.1 入口と処理境界

| 項目 | map /実装 | Policy計画との一致 |
|---|---|---|
| Playbook | `proxmox_backup_restore_verify.yml` 1本 | P3 1入口と一致 |
| 対象 | Play 1=`proxmox` / run_once、Play 2=`brv_restore_targets` | 旧§3のdynamic selectionと一致 |
| 主role | `proxmox_backup_restore_verify` | role-mapと一致 |
| 種別 | change / restore / start-stop / cleanup | controlled applyと一致 |
| tester-gate | `risk-accepted`、`--check`を含め常に実restore | read-onlyと誤認しないようP3 / P7で明記が必要 |
| Play 1 | resource / tag / manual target / agent期待 / dynamic group | BRV-012〜BRV-021と一致 |
| Play 2 | hard assert後にroleを`check_mode: false`で実行 | BRV-004 / BRV-050と一致 |

`tester_mode=true`はassertで拒否され、`--check`もdry-runにならない。Phase 2で「対応するPlaybook」へ列挙することをread-only検証許可として扱わず、常時本実行の危険度とYoshinobu判断が必要なことを保持する。

### 5.2 safety / cleanup実測

| 論点 | role実測 | 移行時の扱い |
|---|---|---|
| hard guard | restore VMID固定assert、target定義 /正数 / restore先と不同assertが破壊task前にある | P4 / P7へ保持。数値実値は転載しない |
| lock | atomic mkdir、rc非ゼロでfail、取得flag trueの場合だけrmdir、releaseは`failed_when: false` | lock失敗とrelease失敗を同一終了条件にしない |
| residue | cluster resourceに専用restore VMがあれば`preexisting_residue=true`後にfail | cleanupをskipしcritical通知 / re-fail |
| partial restore | `qmrestore`前に`restore_attempted=true` | command途中失敗で残った未刻印restore VMもalways cleanup候補になる |
| owner token | restore成功後にdescriptionへrun tokenを設定 | own / empty / otherの3分岐 |
| other token | debugしてdestroyをskipするが、現行codeはこの分岐だけでは`cleanup_ok=false`にしない | 新Policyでcleanup failureを追加せず、残余risk /禁止分岐としてそのまま記録 |
| cleanup block failure | live query、config判定、destroy等のblock failureをrescueし`cleanup_ok=false` | verification failureと別にnon-zero条件へ入る |
| stop | `failed_when: false` | best-effort。stop failureだけではcleanup falseにしない |
| destroy | failureをcleanup block rescueが捕捉 | `cleanup_ok=false`、critical、non-zero |
| report | localhost copyは`ignore_errors: true` | report保存失敗は現行終了code条件へ入らない。Policyに新たなfail条件を作らない |
| notification | common Slack、best-effort | 通知失敗は本処理結果を変えない |
| re-fail | `_brv_failed OR not _brv_cleanup_ok` | 旧§7と一致 |

lock解放は`failed_when: false`のため、rmdir失敗単独では`cleanup_ok=false`やnon-zeroにならない。旧Policyも解放失敗を終了条件へ含めていない。これはPhase 2で厳格化せず、Repository Contextへ現行事実として記録する。

## 6. §9 / §10統合と§11の扱い

### 6.1 §9「制約」

L184-189はすべて許可範囲と禁止事項であり、標準P7「制約・禁止事項」へ統合するのが妥当である。本番VM read-only、秘密禁止、IP literal禁止、NIC device削除、専用restore VMだけを変更する境界を別bulletとして維持する。

### 6.2 §10「スコープ」

§10全体をP7へ機械的に移すのは不適切である。

- §10.1 L195-198は実装済みcapabilityの一覧であり、Repository Contextへ移す。P2 / P3 / P5の既存許可を超える新規許可にはしない。
- §10.2 L202のserial判定とL203のfreshness checkは、現行の合格基準へ混入させない除外scopeとしてP2 / P7へ残す。
- L204のhistory永続化不要は月番号方式に伴うdesign decisionで、P2 / P8と本017へ置く。永続化そのものを将来も禁止する規範へ厳格化しない。

したがって標準P7は旧§9全量と、旧§10の現行除外境界だけを統合する。

### 6.3 §11「今後のレビュー観点」

「lock所有権の深掘りより本質を重視する」という合意時点のreview方針はPolicyの永続sectionにしない。本017とPhase 2 review記録へ保持する。一方L212-217の各bulletはbackup選択、isolation / health、fixed destroy、failure cleanup、結果整合、本番非変更という現役の判断軸なので、P4 / P7へ個別に到達させる。標準8節外に「今後のレビュー観点」を残さない。

## 7. Phase 2編集path案と移動理由

Phase 1では未編集。Tech Leadの明示承認後に限る。

| path | 予定操作 | 選定理由 |
|---|---|---|
| `docs/ai/policies/proxmox_backup_restore_verify_policy.md` | 標準8節へ全面再編 | 許可、禁止、停止、正常性、lock、cleanup、ownership、終了codeの正本 |
| `docs/ai/context/system/proxmox.md` | 必要最小追記 | backup source / restore storage / controller等、codeだけでは決められないSystem事実。既存他者diffを保護して追記可否を再確認する |
| 新規 `docs/ai/context/ansible/proxmox-backup-restore-verify.md` | 2-play / role横断契約を記録 | selectionからdynamic group、role lifecycle、report / notificationまで複数fileを跨ぐため。単一taskのcommandは複製しない |
| 新規Phase 2 implement記録 | 20候補、BRV index、逐行比較、検査実績 | migration auditとreview用line index |

新規Operations Contextは提案しない。同時実行禁止、manual no-overlap、residue時の停止は単一機能のPolicy規範であり、複数roleに共通する運用patternではない。manual residue cleanupの具体手順も旧Policyにないため、本件で新設しない。

## 8. 重複、矛盾、残存risk

| 論点 | 実測 / risk | Phase 2対策 |
|---|---|---|
| Proxmox System Context | cluster / controller / safety説明が既にある | backup restore固有のstorage / isolation事実だけを最小追記し、patch規範を複製しない |
| playbook-map / role-map | 単一入口とrole概要は既に存在 | 新Repository Contextはcross-file lifecycleだけを記録し、map表を複製しない |
| risk-accepted | `--check`でも実restore / start / destroyを行う | P3列挙を実行許可にせず、P2 / P7で常時本実行を明示する |
| manual bypass | rotationを迂回し、実装上は存在するQEMU VMを対象にできる | tag enrollmentとmanual対象を混同せず、他のsafety gateを迂回しないことを保持 |
| stale lock窓 | full distributed mutexでなく、同時実行は運用禁止 | lock非依存のfixed destroy / residue / ownershipをP4 / P7へ独立保持 |
| empty owner | partial restore救済だがno-overlap前提に依存 | own tokenと同一扱いにせず例外として明記 |
| other owner | destroy禁止だが現行codeは単独でcleanup failureにしない | 禁止を保持しつつ新たなnon-zero条件を作らない |
| report / unlock failure | 現行終了codeへ反映されない | Repository Contextで事実を記録し、PolicyのOR条件を拡張しない |
| freshness | latest available backup選択とbackup age判定は別 | freshnessを現行合格基準へ混ぜず、別playbook scopeを維持 |
| numeric restore VMID | 旧Policy / codeに実値がある | Policy / Context / Phase 2記録へ転載せずvars / codeを正本とする |

Phase 2を止める移動先未決はない。既存System Contextへの追記は他者diffとの競合をTech Leadが許可範囲指定時に再確認する。

## 9. 検査計画

### 9.1 Phase 1

- HEAD commit / blob / 217行、主section 11件を確認する。
- 全量配置13行でL1-217を覆うことを確認する。
- 範囲超過候補20行の種類、具体移動先、Policy核に空欄がないことを確認する。
- BRV ledgerがBRV-001〜BRV-082の連番で、重複 /欠落 /必須cell空欄0であることを確認する。
- playbook 1本、role 1本、map 2件、実path / tester-gate /対象 /副作用を確認する。
- §9 / §10 / §11判断、lock非依存guard、manual bypass、rescue / always、ownership 3分岐、cleanup /終了ORを追跡する。
- Markdown空table cell、IPv4、VLAN ID、VM ID実値、認証 /秘密実値を検査する。
- 本017以外の本件変更0、`git diff --check`、未追跡017の`git diff --no-index --check`を確認する。

Phase 1完了時の実績は次のとおりである。

| 検査 | 結果 |
|---|---|
| snapshot | HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `9204b94e61d0f3eb652e03406373cbacc5d0af5d`、217行 |
| 全量配置 | 13行、旧L1-217の未配置0 |
| 範囲超過候補 | 20行、必須cell空欄0 |
| safety ledger | BRV-001〜BRV-082、82件、連番欠落 /重複0、必須cell空欄0 |
| 実装 / map | playbook 1本、role 1本、playbook-map 1件、role-map 1件を実pathと照合済み |
| 重点条件 | lock非依存guard、manual bypass、rescue / always、ownership 3分岐、cleanup AND、終了ORの追跡欠落0 |
| 実値 /秘密 | IPv4、VLAN ID、数値VM ID、認証 /秘密実値0 |
| scope | 本017以外の本件変更0。既存他者差分は未変更 |
| whitespace | tracked `git diff --check`、untracked 017 `git diff --no-index --check`ともにPASS |
| 実行境界 | 実機・Ansible実行0 |

### 9.2 Phase 2

- 標準8見出しが順番どおり各1回で、P3が単一入口を列挙すること。
- 20候補すべてに実移動先とPolicy核の最終行があること。
- BRV-001〜BRV-082全件に新Policy marker / line indexがあり、旧HEAD逐行比較で欠落、緩和、厳格化、条件 /例外 /順序変更0であること。
- `verify_restore_vmid`の数値実値を新Policy / Context / implement記録へ転載しないこと。
- lock非依存guard、ownership own / empty / other、cleanup AND、終了OR、notification best-effortを個別検査すること。
- Policy対応入口とactual playbook / role / mapsの差分0、Contextの非規範 / Policy優先link、重複、旧path、相対linkを確認すること。
- 承認path外、特にplaybook / role /他Policy / map / requirement /本017へPhase 2差分がないこと。
- tracked / untracked whitespaceを確認し、実機・Ansibleを実行しないこと。

## 10. Phase 1結論

旧Policyの範囲超過候補は20行、安全境界はBRV-001〜BRV-082の82件である。旧§9は全量を標準P7へ統合し、旧§10は実装一覧 /除外scope /design decisionへ分割する。旧§11のreview合意は本017へ保持し、現役の6判断はP4 / P7へ移す。最大の移行riskはlock、owner token、未刻印例外、cleanup、終了codeを「安全装置」として平坦化することである。各条件を独立marker化し、既知のother-token / unlock / report結果を新しい失敗条件へ変更せずPhase 2へ渡す。
