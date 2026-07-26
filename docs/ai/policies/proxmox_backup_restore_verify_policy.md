# Proxmox Backup Restore Verify Policy

本書はProxmox上のcore VM backupを実restoreして検証する際の許可、禁止、停止条件、判断軸の正本である。環境事実と実装詳細は対応Contextを参照し、競合時は本Policyを優先する。

## 1. 目的

<!-- BRV-001 -->
core VMのbackupを実際にrestoreしてbootできることをmonthlyに検証し、silent corruptionを本番へ影響させず検出する。

<!-- BRV-002 -->
検証は専用固定restore VMIDへ行い、本番VMにはconfig read以外で触れない。

## 2. 対象と実行範囲

<!-- BRV-003 -->
検証対象は`verify` tagを持つVMからmonthly rotationで選ばれた1台とする。

<!-- BRV-004 -->
restore先は`verify_restore_vmid`で定義された専用固定restore VMIDだけとし、検証後に使い捨てる。

<!-- BRV-006 -->
monthly productionは`quory`、development / manual CLIは`ansy`を実行元とする。

<!-- BRV-008 -->
restoreには設定された専用storageを使用する。

<!-- BRV-009 -->
controlled applyとして専用restore VMのcreate / start / deleteを許可する。本番VMのreboot / migrateは許可しない。

<!-- BRV-010 -->
対象決定のためinventory / group vars / host varsを変更せず、Proxmox tagで動的に決定する。

<!-- BRV-016 -->
VMの増減時はtagだけでrotation indexを振り直す。月番号固定方式のため検証履歴を永続化しない。

<!-- BRV-022 -->
backup sourceへのaccess要件を満たすため、検証lifecycleを実行するPlayはroot権限で実行する。この権限を本Policy外の操作許可へ拡張しない。

<!-- BRV-042 -->
monthlyは`quory`から固定時刻のsingle scheduleで実行する。

<!-- BRV-072 -->
現行scopeはmonthly rotation、latest backupの特定、restore、NIC isolation、boot、health判定、destroy、安全装置、minimal lock、Slack通知である。

## 3. 対応するPlaybook

次の1入口を本Policyに関連する索引として列挙する。列挙自体は実行許可を意味せず、本Policyの全規範、playbook先頭のtester-gate、入力gateを満たす場合に限る。

| Playbook | Policy上の役割 |
|---|---|
| `proxmox_backup_restore_verify.yml` | 対象VMを決定し、backupを専用固定restore VMIDへ実restoreしてboot、health、cleanupを検証する |

<!-- BRV-011 -->
本Policyに対応するplaybookは`proxmox_backup_restore_verify.yml`の1本とする。

この入口のtester-gateは`risk-accepted`である(判断基準は`docs/ai/policies/ansible_test_safety_policy.md` TS-009〜TS-011: 対象は専用固定restore VMIDに限定され本番VMへの実害がないこと、かつ実restoreを省略すると検証自体の意味が失われることの2条件を満たす)。`--check`を指定してもrestore / start / stop / destroyを含む本実行になり、挙動は変わらない。`tester_mode`/`tester_gate`は廃止済みの概念であり本Playbookでも参照しない(`tester_mode=true`を指定した場合はassertでfailする)。

この分類自体はYoshinobuが判断済み(2026-07-06)であり、monthly実行のたびに個別の実行判断を必要としない。`quory`からのmonthly schedule実行(BRV-042)、`ansy`からのmanual実行(BRV-006)のいずれも同じ扱いとする。

## 4. 判断軸

### 対象とbackupの選定

<!-- BRV-005 -->
restore nodeは対象VMの`prefer<node>` tagで決定し、決定できなければ停止する。

<!-- BRV-007 -->
backup storageが未指定の場合は、NFS typeかつcontentにbackupを含むstorageを自動検出する。

<!-- BRV-084 -->
rotationの目的は、`verify` tagを持つVM群のbackup restore検証を年間で均等に行うことであり、どの月にどのVMを検証するかを個別には規定しない。`(現在月 - 1) % 候補list長`による決定論的インデックス(BRV-013〜BRV-015)で、対象VMの増減にかかわらずこの均等性を維持する。

<!-- BRV-012 -->
cluster resourcesから対象を決定し、Ansible側に対象VM listを持たずProxmox tagだけで増減に対応する。

<!-- BRV-013 -->
monthly rotationでは`verify` tagを持つQEMU VMだけを列挙する。

<!-- BRV-014 -->
対象候補をVM ID昇順にsortし、deterministicな順序を得る。

<!-- BRV-015 -->
`(現在月 - 1) % 候補list長`のindexによりmonthly対象を確定する。

<!-- BRV-017 -->
`target_vmid`を指定した場合はrotationだけを無視し、指定されたQEMU VMをmanual対象にできる。

<!-- BRV-018 -->
manual指定対象が存在しなければ停止する。

<!-- BRV-019 -->
restore nodeを対象VMの`prefer<node>` tagから決定できなければ停止する。

<!-- BRV-020 -->
本番VM configのagentが`1`または`enabled=1`を含む場合だけagent期待とし、それ以外をagent無しとする。

<!-- BRV-025 -->
対象VMのbackupから、storage content APIのctimeが最も新しいものを選ぶ。

manual bypassはrotationだけを迂回する。存在確認、restore node tag、agent期待、本番非変更、専用固定restore先、destroy guardは迂回しない。

### 正常性

<!-- BRV-035 -->
期待levelは本番VMのagent設定、実測はrestore VMのboot結果とし、実測が期待へ到達したかで合否を決める。

<!-- BRV-036 -->
agent対応VMはguest agentのosinfo取得成功を合格とする。

<!-- BRV-037 -->
agent無しVMはboot後の規定settle期間を経過してもrunningであることを合格とする。

### lockと開始前残骸

<!-- BRV-041 -->
同時実行禁止を補助するminimal lockを使用するが、完全なdistributed mutexとは扱わない。

<!-- BRV-043 -->
`ansy`からmanual実行する場合は、人間がmonthly実行と重複しないことを確認する。

<!-- BRV-044 -->
pmxcfs上のofficial lockをatomic mkdirで取得する。

<!-- BRV-045 -->
lockが既存なら待機せず即時停止し、通知して非ゼロ終了する。

<!-- BRV-046 -->
lock directoryはemptyに保ち、pmxcfs標準の120秒stale回収を有効にする。crashした実行のlockはmanual削除なしで自動回収される。

<!-- BRV-024 -->
専用固定restore VMIDに既存VMがあれば、そのVMへ触れずcritical通知して中断する。

<!-- BRV-051 -->
開始時に専用固定restore VMが存在すれば既存物へ触れず、critical通知して停止する。

### ownership、cleanup、終了

<!-- BRV-052 -->
cleanupではowner tokenが自runと一致する場合にdestroyする。

<!-- BRV-053 -->
owner tokenが未刻印の場合は、同時実行禁止の前提下で自runの途中失敗とみなしdestroyを許可する。

<!-- BRV-054 -->
別runのowner tokenがある場合はdestroyせず、対象へ触れない。この分岐だけを新たなcleanup failureまたは非ゼロ終了条件にはしない。

<!-- BRV-057 -->
cleanupは「restoreを試行した」AND「開始前残骸でない」の両方を満たす場合だけ開始する。

<!-- BRV-058 -->
cleanup開始後はrestore VMのlive stateを再取得する。

<!-- BRV-059 -->
restore VMが現存しownershipが真の場合だけ、stopをbest-effortで試みてからdestroy / purgeする。stop失敗だけをcleanup failureにしない。

<!-- BRV-060 -->
destroy失敗によりrestore VMが残る場合は`cleanup_ok=false`とする。

<!-- BRV-061 -->
verification失敗OR cleanup失敗のいずれかで非ゼロ終了する。other-owner分岐、lock解放失敗、report保存失敗を新しい失敗条件へ追加しない。

### reviewで保持する判断

<!-- BRV-076 -->
lock ownershipの深掘りより、本質的な危害防止と結果整合をreviewの重点とする。

<!-- BRV-077 -->
latestかつ正しいtarget VMのbackupを選べることを確認する。

<!-- BRV-078 -->
NIC isolation後にbootし、有効な正常性判定ができることを確認する。

<!-- BRV-080 -->
failure時に専用restore VMをownership条件どおり安全に処理できることを確認する。

<!-- BRV-081 -->
Slack通知、report、終了codeが実結果と一致することを確認する。

## 5. ライフサイクル・処理フロー

<!-- BRV-021 -->
選定結果をdynamic groupへ渡し、検証Playは選定されたnodeだけでroleを実行する。

処理順序は次のとおりとする。

<!-- BRV-023 -->
1. minimal lockを取得し、その後に開始前restore残骸を確認する。
<!-- BRV-026 -->
2. 選定したbackupを専用固定restore VMIDへrestoreする。
<!-- BRV-027 -->
3. restore後、descriptionへ一意のowner tokenを刻印する。
<!-- BRV-028 -->
4. boot前に全NIC deviceを削除し、IPを指定しない。
<!-- BRV-029 -->
5. NIC切断後の専用restore VMをstartする。
<!-- BRV-030 -->
6. start後に本Policyの正常性を判定する。

<!-- BRV-031 -->
lifecycle失敗はrescueで捕捉する。

<!-- BRV-032 -->
成否にかかわらずalwaysでcleanup、lock解放、report、通知、条件付きre-failをこの順に行う。

<!-- BRV-033 -->
restore / set / start / stop / destroy / guest commandの実行条件、OK / NG判定、fail制御はAnsible task側で明示する。

<!-- BRV-048 -->
lockは取得した場合だけ、empty directoryをrmdirして解放する。解放失敗だけを新しいcleanup failureまたは非ゼロ終了条件にしない。

## 6. 通知方針

<!-- BRV-062 -->
通知はcommon Slack taskを使用し、best-effortとする。通知失敗は検証結果または終了codeを変更しない。

<!-- BRV-063 -->
通知priorityはcritical、error、okの順とする。

| 状況 | channel | status |
|---|---|---|
| verification OK | info | ok |
| restore失敗または正常性未達 | alerts | error |
| 開始前restore残骸またはdestroy失敗 | alerts | critical |

<!-- BRV-064 -->
verification OKはinfo channelへokで通知する。

<!-- BRV-065 -->
restore失敗または正常性未達はalerts channelへerrorで通知する。

<!-- BRV-066 -->
開始前restore残骸またはdestroy失敗はalerts channelへcriticalで通知する。

<!-- BRV-067 -->
JSON reportを設定されたreport directoryへ保存する。保存失敗だけを新しい非ゼロ終了条件にしない。

## 7. 制約・禁止事項

<!-- BRV-034 -->
破壊操作またはOK / NG / fail判断を専用shell scriptへ移さない。

<!-- BRV-038 -->
agent無しVMはrunning継続だけで合格とし、特定製品を特別扱いしない。

<!-- BRV-039 -->
agent無し判定blockは将来serial console判定へ交換可能な形で分離するが、現行基準へserial判定を追加しない。

<!-- BRV-040 -->
同時実行を運用で禁止する。

<!-- BRV-047 -->
lock refresher、期限更新、生存監視、孤児管理を持たない。

<!-- BRV-049 -->
本番への危害防止をlockに依存させない。

<!-- BRV-083 -->
危害防止は次の3つが独立に成立することで担保する。lockはこの3つの代替にならず、lockが機能しない場合でも各々が単独で破壊対象を制限する。

1. 専用固定restore VMIDへのhard assert(BRV-050)。
2. 開始前の残骸確認による停止(BRV-051、BRV-024)。
3. owner tokenによるcleanup対象の限定(BRV-052、BRV-053、BRV-054のown / 未刻印 / other分岐)。

<!-- BRV-050 -->
destroy対象を専用固定restore VMIDへhard assertし、それ以外を絶対にdestroyしない。

<!-- BRV-055 -->
stale回収窓を超えて低頻度の同時実行が重なる場合、一時検証1 cycleの損失を残余riskとして受容する。

<!-- BRV-056 -->
BRV-055の場合も最悪影響は使い捨て検証に限定され、本番影響はない。

<!-- BRV-068 -->
本番VMにはconfig read以外で触れない。

<!-- BRV-069 -->
秘密情報を扱わない。

<!-- BRV-071 -->
変更系として許可するのは専用restore VMのcreate / start / stop / deleteだけであり、本番VMはconfig read-onlyとする。

<!-- BRV-073 -->
agent無しVMのserial console文字列matchを現行scopeへ含めない。

<!-- BRV-074 -->
backup freshness checkを現行scopeへ含めず、取得側整備後の別playbookとする。

<!-- BRV-079 -->
destroy対象が構造的に専用固定restore VMIDへ限定されることを確認する。

<!-- BRV-082 -->
本番VMへ変更操作が及ばないことを確認する。

## 8. 変更履歴

<!-- BRV-075 -->
月番号固定方式のため、verification historyの永続化を現行scopeへ含めない。この判断を将来の永続化まで禁止する規範へ拡張しない。

| 日付 | 変更 |
|---|---|
| 2026-06-14 | v1.0。monthly restore verification、minimal lock、ownership、cleanup、通知を定義 |
| 2026-07-24 | 標準8節へ再編。環境事実とcross-file実装契約をContextへ分離し、専用restore VMIDの数値実値をPolicyから除去 |
| 2026-07-26 | Yoshinobuの再点検を反映。BRV-011を`tester_mode`廃止後の実態(risk-accepted分類はYoshinobu判断済み・monthly実行に個別の実行判断は不要)に合わせて改訂。rotationの目的(年間均等化)をBRV-084として明記。core.mdと重複するBRV-070(IP literal禁止)を削除 |
