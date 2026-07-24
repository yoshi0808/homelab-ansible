# Autonomous Recovery Policy 標準構造書換 Phase 1 調査

## 1. 調査範囲と正本

- requirement: `2026-07-24_008_requirement_autonomous_recovery_policy_rewrite.md`
- 旧Policy正本: Git HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79` の `docs/ai/policies/autonomous_recovery_policy.md`
- 旧Policy blob: `e141d3eae0be403cc30fd6f905e08d6c2ddc51d7`
- 旧Policy規模: 288行、主section 11件
- 分類基準: `docs/ai/context-classification.md` L31-48
- Phase 1で編集したファイル: 本009のみ
- 未実施: Policy、Context、playbook、roleの編集、実機・Ansible実行、安全境界の意味変更

行番号はすべて上記HEAD snapshotの1始まりである。旧表にあるVM IDの数値実値は転載せず、Phase 2でもinventory / vars / codeを正本としてPolicyとContextから除く。内部IP、VLAN ID、認証情報、秘密情報の実値も転載しない。

## 2. A: 標準8節への旧section全量配置計画

### 2.1 新Policyの標準8節

| 新節 | 収容するPolicy核 | 主な旧範囲 |
|---|---|---|
| 1. 目的 | 人間承認なしの限定的な復旧試行、Slackの位置づけ | §1 L14-16 |
| 2. 対象と実行範囲 | 対象別の許可されたrestart / reboot / failover、調査専用対象、経路分離 | §2 L20-35、§8 L251-263 |
| 3. 対応するPlaybook | recovery系9入口、その目的、安全度、対象範囲 | §5 L163-205、§8 L251-263、実playbook / playbook-map |
| 4. 判断軸 | probe失敗回数、flapping、pvesh状態、復旧確認、failover可否、mute / pause gate | §5.1 L165-187、§7 L227-247 |
| 5. ライフサイクル・処理フロー | pull / push / manualの開始、ロック、復旧ラダー、再確認、停止・エスカレーション | §5 L163-205、§8 L251-263、§11 L286-288 |
| 6. 通知方針 | Slackのbest-effort、通知失敗と本処理の分離、通知時点 | §1 L16、§9 L267-269 |
| 7. 制約・禁止事項 | read-only / allowlist / forced command / no escalation、鍵・account分離、禁止事項、既知制約 | §2 L27-35、§3-§4 L39-159、§6 L208-223、§10-§11 L273-288 |
| 8. 変更履歴 | 旧版snapshotと標準化・Context分離を初回記録 | L1-10、新規記録 |

### 2.2 旧section全量配置

| 旧section・行 | 新Policy配置 | 移動先 | 分割方針 |
|---|---|---|---|
| 表題・参照・位置づけ L1-10 | 1、8 | 本009 | 現行目的を残し、旧pathと時点依存説明は履歴へ |
| §1 L14-16 | 1、6 | なし | 自律試行とSlack非承認gateを保持 |
| §2 L20-35 | 2、4、7 | `context/system/autonomous-recovery.md` | 対象・配置・サービスの現状を移し、許可手段、経路分離、除外を保持。VM ID実値は移さない |
| §3 L39-49 | 7 | System Context、Repository Context | 配置事実と複数account連携を移し、権限・token・鍵・常駐性の分離をPolicy核として保持 |
| §4 L53-159 | 7 | Repository Context、System Context、Operations Context、本009 | 鍵・wrapper・dispatch・ACL・sudoersの実装を移す。read-only、allowlist、forced command、no escalation、二段検証、書込み禁止を保持 |
| §5 L163-205 | 2、3、4、5 | Repository Context、System Context | daemon / unit / wrapperの現状を移し、probe・flapping・pvesh分岐・reboot / failover条件・ロックを保持 |
| §6 L208-223 | 7 | Repository Context、System Context | execpolicy / wrapper / sandboxの実装契約を移し、deny-by-default、限定入口、OS権限、昇格禁止を保持 |
| §7 L227-247 | 4、5、7 | Operations Context、Repository Context | CLI・state path・TTL一覧を移し、skip、counter reset、resume gateを保持 |
| §8 L251-263 | 2、3、5、7 | Operations Context、Repository Context | Semaphore実行手順を移し、人間判断での直接実行許可と実装safety gateを保持 |
| §9 L267-269 | 6 | Repository Context | notification role / Vault配置の実装を移し、best-effortと通知時点を保持 |
| §10 L273-282 | 7 | なし | 8禁止事項を全件保持 |
| §11 L286-288 | 5、7 | Operations Context | push経路の到達限界とmanual layerへの遷移を保持 |

全旧主section 11件と表題範囲を欠番なく配置する。標準節への統合で、旧sectionの削除を意味しない。

## 3. B: Policy範囲超過候補の行単位追跡

Policy核は「何をしてよいか」を答える規範であり、配置・実装契約・手順・時点履歴は指定Contextまたは本009へ移す。混合範囲は移動内容と保持する核を分ける。

| # | 旧section・行 | 種類 | 移動内容と受け皿 | Policyへ残す核 |
|---:|---|---|---|---|
| 1 | L1-10 | 旧参照 / 時点説明 | 2026-07-05以前の参照関係と旧版位置づけは本009 | 現行Policyの目的だけをP1へ |
| 2 | §2 L22-29 | System Context / 実値 | 対象、tag、service、配置事実はSystem Context。VM ID数値は移さずinventory / vars / codeを正本とする | 対象別に許可された復旧手段と対象外 |
| 3 | §3 L41-49 | System / Repository Context | account配置、daemon有無、保持物、連携はSystem / Repository Context | account・token・鍵・職務の分離、不要な常駐禁止 |
| 4 | §4 L55-62 | Repository Context | 鍵名、保持者、配布、template、authorized_keys構成 | 調査/action/push/定常鍵の目的分離、forced command、引数制限、排他管理 |
| 5 | §4.1 L64-66 | Repository Context | defaults、dispatch、named checkの現行一覧 | read-only allowlistと非一致拒否 |
| 6 | §4.1.1 L68-82 | Operations / Repository Context | 調査追加の編集・配備手順、生成元、template実装 | 調査だけを追加可、復旧追加不可、allowlistとsudoersの同期必須 |
| 7 | §4.2 L84-86 | Repository Context | script名、reset-failedからrestartまでのtask実装 | actionは無引数かつ許可service一式だけ、個別指定不可 |
| 8 | §4.3 L88-95 | Repository Context | report path、command grammar、二層helper、ACL配置 | 定型commandのみ、path traversal拒否、no escalation、二段検証 |
| 9 | §4.4 L97-103 | Repository / System Context | DB配置・mode、query実装、ACL、argv構成 | read-only定型queryのみ、自由SQL禁止、shell再解釈禁止、no escalation |
| 10 | §4.5 L105-115 | Issue / Knowledge | 2026-07-05の失敗経緯、tester教訓、実機確認結果は本009。再利用する教訓は将来Knowledge候補 | sandbox防御を弱めず、Codex経路で昇格を前提にせずACLを使う。remote SSH内sudoだけを別経路として許す |
| 11 | §4.6 L117-134 | System / Repository Context | pve調査対象、専用鍵・account、named check一覧とparameter | pveは調査だけ、action不可、鍵/account分離、固定allowlist |
| 12 | §4.6 L135-158 | Repository Context | wrapper / dispatch / sudoersのparser、regex、argv、command対応 | dispatchを本gateとし、二段再検証、read-only動詞固定、書込み・eval・過剰token禁止 |
| 13 | §4.6 L159 | System Context / Issue | sudo経路差、実機確認済みpath / unit、配備前検査履歴 | Codex sandboxを通らないremote sudoだけ許し、追加checkは配備前に検証必須 |
| 14 | §5.1 L165-175 | System / Repository Context | daemon間隔、config path、probe方式、FQDN事実 | 連続失敗閾値と明示target解決を判断軸に残す |
| 15 | §5.1 L177-187 | Repository / Operations Context | function・lock path・playbook呼出し実装 | lock、flapping、pvesh分岐、各段1回、対象限定failover、停止・通知 |
| 16 | §5.2 L189-200 | Repository Context | unit / script / key / wrapper / AGENTS連携 | mute、lock、許可されたinvestigate→recover順序、Codexへreboot / failoverを渡さない |
| 17 | §5.3 L202-204 | System / Repository Context | Slack Socket Mode、service、sudo invocation、home設定 | Slackは手動依頼入口であり、限定wrapper経由で実行する |
| 18 | §6 L210-223 | Repository / System Context | execpolicy一覧、wrapper引数、sandbox設定、file mode / owner | deny-by-default、列挙wrapperのみ、pve read-only、reboot / failover非公開、no escalation、OS権限分離 |
| 19 | §7 L231-247 | Operations / Repository Context | mute / pause CLI、state path、各playbook TTL、cert deploy手順 | 独立gate、skip時counter reset、push mute確認、失敗時pause残留、人間の明示resume |
| 20 | §8 L251-263 | Operations / Repository Context | Semaphore入口、extra-var、report / notify共通実装 | 人間判断で3 layerを直接起動可。target allowlist・tag・存在・HA gateは迂回不可 |
| 21 | §9 L267-269 | Repository Context | Vault変数、role / task名、timezone実装 | 通知はbest-effortで本処理成否に影響させず、所定時点で通知 |
| 22 | §10-§11 L273-288 | Policy核 / Operations Context | manual escalationの操作入口だけOperations Context | 禁止8件、pushの自動到達限界、人間へエスカレーション |

範囲超過候補は22行である。移動のみの項目はなく、いずれもPolicy核を含む混合範囲か、旧履歴と現行規範を分割する範囲である。

## 4. C: 安全境界ledger

### 4.1 記録規則

- 1行は1つの許可・禁止・停止・必須・例外・判断単位とする。
- `旧行`はHEAD snapshotとの突合キー、`新Policy先`の`P1`〜`P8`は2.1の標準節を表す。
- Contextへ移す説明に規範が混在する場合も、規範には必ず新Policy到達先を割り当てる。
- 表行や箇条書きに複数条件がある場合、Reviewerは旧HEADの各文・各条件を個別に照合し、ledger要約を原文の代替にしない。

### 4.2 全量ledger

| ID | 種別 | 旧行 | 原文の安全境界 | 新Policy先 |
|---|---|---:|---|---|
| AR-001 | 目的/許可 | L16 | 対象の業務継続を、人間承認を待たない自律的な復旧試行で支える | P1 |
| AR-002 | 禁止/必須 | L16 | Slackを承認gateにせず、手動依頼の入口と結果通知にだけ使う | P1/P6 |
| AR-003 | 許可 | L24 | sophos-fwはservice restartをせず、ping ladderのVM reboot後に条件付きfailoverだけを許す | P2/P4 |
| AR-004 | 許可 | L25 | authyは許可serviceのrestartと、ping ladderのVM reboot後に条件付きfailoverを許す | P2/P4 |
| AR-005 | 許可/禁止 | L26 | monnieは許可serviceのrestartとVM rebootだけを許し、failoverを許さない | P2/P7 |
| AR-006 | 禁止/例外 | L27/L35 | pve1 / pve2を自律復旧action対象にせず、read-only調査だけを許す | P2/P7 |
| AR-007 | 禁止 | L28/L35 | ansyを自律復旧action対象にしない | P2/P7 |
| AR-008 | 必須 | L30-33 | service restart経路とping ladderは別障害classとして独立させ、混同しない | P2/P5 |
| AR-009 | 判断 | L32 | service restartはVM内service crashにだけ用い、対象serviceがないsophos-fwへ設けない | P2/P4 |
| AR-010 | 判断/必須 | L33 | ping ladderはVM単位で判定し、pveshで状態を確証後、running無応答ならreboot、hacriticalかつ未復旧ならfailoverへ進む | P4/P5 |
| AR-011 | 禁止 | L35 | pve1 / pve2へaction_services相当を追加しない | P7 |
| AR-012 | 禁止 | L43 | annは定常自動化専用とし、自律復旧の権限・鍵と混用しない | P7 |
| AR-013 | 必須/禁止 | L44 | recovery-ioはSlack認可だけを担当し、Slack token以外の復旧権限を持たせない | P7 |
| AR-014 | 必須/禁止 | L45 | recovery-execは調査・復旧鍵を持つがSlack tokenを持たず、呼出時だけCodexを起動する | P7 |
| AR-015 | 必須 | L46 | target側recovery-execはforced-command着地専用accountとする | P7 |
| AR-016 | 必須 | L47 | probe実行accountはglobal pauseを読める権限だけを必要範囲で持つ | P7 |
| AR-017 | 禁止 | L49 | recovery-io以外のrecovery-execに常駐processを持たせない | P7 |
| AR-018 | 必須 | L57 | investigate keyはparameterをdispatch allowlistで検証してから実行する | P7 |
| AR-019 | 必須/禁止 | L58 | action keyのforced commandはparameterを受けず、固定service restart一式だけを実行する | P7 |
| AR-020 | 必須/禁止 | L59 | push keyはtarget固有forced commandへ固定し、target側から引数を渡せないようにする | P7 |
| AR-021 | 禁止 | L60 | annの既存鍵をrecovery-execへ流用しない | P7 |
| AR-022 | 必須 | L62 | target authorized_keysはinvestigate / actionの限定entryだけをtemplateで排他的に管理する | P7 |
| AR-023 | 許可/禁止 | L66 | investigateはservice / journal / extra / common checkのallowlistだけを許し、非一致値を拒否する | P7 |
| AR-024 | 許可/禁止 | L70 | 新規investigateはread-only確認だけを追加でき、復旧command追加には使わない | P7 |
| AR-025 | 必須 | L72 | service調査追加はtargetごとのinvestigate_servicesに限定して反映する | P7 |
| AR-026 | 必須 | L73 | extra調査は固定name / commandで追加し、sudoが必要なら対応sudoersを個別に同期する | P7 |
| AR-027 | 必須 | L75 | recovery_exec_targetsをwrapperとdispatchの共通allowlist正本とする | P7 |
| AR-028 | 必須 | L79 | 調査追加時はCodexが認識できる説明も同期する | P7 |
| AR-029 | 必須 | L80 | 調査追加後は正規setup入口でwrapper / dispatch /説明を同時配備する | P3/P7 |
| AR-030 | 必須 | L82 | 共通check category追加時だけ両templateへ直接追加し、両側の検証を同期する | P7 |
| AR-031 | 必須/禁止 | L86 | actionは無引数でallowlist全serviceを一括restartし、個別service指定を許さない | P7 |
| AR-032 | 必須 | L86 | restart前にreset-failedを行い、start-limit raceを回避する | P5 |
| AR-033 | 許可/禁止 | L90-93 | report調査は定型3 commandだけを許す。optional targetは最大1 path segment、各componentは英数字・underscore・hyphenだけ、filenameは固定`.json` suffixを必須のdot例外として許可し、それ以外のslash / dotを拒否する。list / show対象はJSONだけに限定する | P7 |
| AR-034 | 必須/禁止 | L94 | report読取りは直接ACLで許可し、sudo / setuid昇格を使わない | P7 |
| AR-035 | 必須 | L95 | report調査はwrapperとhelperの二層で引数を再検証する | P7 |
| AR-036 | 許可/禁止 | L99-101 | Semaphore調査は定型4 queryと範囲検証済み整数parameterだけを許し、自由SQLを受け付けない | P7 |
| AR-037 | 必須/禁止 | L102 | DBは必要なACLとread-only engine flagで読み、sudoを使わない | P7 |
| AR-038 | 禁止 | L103 | SQLをargv配列で渡し、shell文字列連結・再解釈を行わない | P7 |
| AR-039 | 禁止 | L109 | no_new_privilegesを解除してsandbox防御を弱めない | P7 |
| AR-040 | 必須 | L111 | Codex側の不足読取り権限は権限昇格でなく対象accountへの直接ACLで与える | P7 |
| AR-041 | 例外 | L115/L159 | pve上SSH session内のsudoはCodex sandbox経路外に限って許し、quory上Codexからの昇格とは区別する | P7 |
| AR-042 | 禁止 | L119-122 | pve調査をread-onlyに限定し、自律復旧actionを追加しない | P2/P7 |
| AR-043 | 必須 | L124 | pve調査鍵を他targetのinvestigate鍵から目的別に分離し、両node調査にだけ用いる | P7 |
| AR-044 | 必須/禁止 | L125 | pve着地accountをannから分離し、forced command専用にする | P7 |
| AR-045 | 許可/禁止 | L126-134 | pve named checkを固定checkと検証済みparameter付きcheckの列挙範囲だけに限定する | P7 |
| AR-046 | 必須 | L135-140 | wrapperを一次filter、dispatchを権限本gateとして独立再parseし、不正token等をsudo前に拒否する | P7 |
| AR-047 | 必須 | L141-145 | parameter検証はdispatchを正本、wrapperをmirrorとし、形式・範囲・allowlist・出力量を固定する | P7 |
| AR-048 | 必須/禁止 | L146-149 | sudo argvは絶対path・固定read-only動詞・検証済みoperandの順に固定し、eval / shell再解釈 / 書込み動詞を許可しない | P7 |
| AR-049 | 必須/禁止 | L150-155 | sudoersは固定checkを1:1列挙し、parameter位置だけの限定wildcard以外を禁じ、dispatch検証を必須とする | P7 |
| AR-050 | 禁止 | L156-158 | pvesh書込み動詞を構造的に実行不能とし、node状態はread-only代替checkで取得する | P7 |
| AR-051 | 必須 | L159 | 追加checkの絶対path、unit実在、sudoers grammar、forced-command経路を配備前 / tester工程で確認する | P7 |
| AR-052 | 必須 | L167 | probeは全対象を一定間隔で継続監視する | P4/P5 |
| AR-053 | 判断 | L171 | sophos-fwはicmpとdnsの両probeについて5回連続失敗を発火閾値とする | P4 |
| AR-054 | 判断 | L172 | authyはicmpとtcp probeについて同じ5回連続失敗を発火閾値とする | P4 |
| AR-055 | 判断 | L173 | monnieはicmpとtcp probeについて同じ5回連続失敗を発火閾値とする | P4 |
| AR-056 | 必須 | L175 | 各targetは短縮名でなく明示FQDNで解決する | P2/P7 |
| AR-057 | 停止 | L179 | ladder lock取得済みなら重複実行をskipする | P4/P5 |
| AR-058 | 停止/判断 | L180 | 直近24時間で3回以上発火ならflappingとし、ladderを実行せずescalation通知だけを行う | P4/P5 |
| AR-059 | 停止 | L181-182 | pveshで状態を確証し、pve到達不能ならactionせずcritical通知する | P4/P5 |
| AR-060 | 判断/許可 | L183 | VM stoppedならrebootでなくstartを1回行い、復旧確認する | P4/P5 |
| AR-061 | 停止 | L184 | VM not-foundならactionを進めずcritical通知する | P4/P5 |
| AR-062 | 判断 | L185 | runningのままping無応答の場合だけreboot段へ進む | P4/P5 |
| AR-063 | 許可/停止 | L186 | target固定のVM rebootを1回実行し、復旧すればok通知して終了する | P4/P5 |
| AR-064 | 許可/停止 | L187 | reboot後未復旧かつfailover許可targetだけfailoverを1回実行し、未復旧なら人間へescalateする | P4/P5 |
| AR-065 | 必須 | L191-196 | push経路を許可serviceのOnFailure、target固有key、forced commandに限定する | P2/P7 |
| AR-066 | 停止 | L197 | pushは対象muteを確認し、実行中lockを取得できない場合は重複起動しない | P4/P5 |
| AR-067 | 必須/禁止 | L198-200 | Codexはinvestigate→判断→recover→再investigate→escalationの順に従い、VM reboot / failover手段を持たない | P5/P7 |
| AR-068 | 許可 | L204 | Slack手動依頼は限定wrapper経由のCodex jobとして受け、結果を同threadへ返す | P2/P6/P7 |
| AR-069 | 必須/禁止 | L210-216 | execpolicyはdefault denyとし、列挙されたinvestigate / report / query / recover / monitoring wrapperだけを許す | P7 |
| AR-070 | 禁止 | L217-219 | pveへrecover wrapperを用意せず、二段検証済みread-only named check以外を実行不能にする | P7 |
| AR-071 | 禁止/許可 | L220 | VM reboot / HA failoverをCodex execpolicyへ含めず、pull経路のtarget固定・決定論的呼出しだけに許す | P5/P7 |
| AR-072 | 必須/禁止 | L221 | Codex wrapperは引数個数・位置・値を厳密固定し、sandbox / approval / execpolicy optionを呼出元から受け取らない | P7 |
| AR-073 | 必須 | L222 | sandboxとexecpolicyを別層とし、token・SSH keyはOS file権限と専用ownerで保護する | P7 |
| AR-074 | 禁止/必須 | L223 | Codex wrapperはsudo / setuid / capability昇格を前提にせず、不足権限には直接ACLを使う | P7 |
| AR-075 | 必須 | L229-234 | target別TTL付きmuteと、明示resumeまで継続するTTLなしglobal pauseを独立gateとして維持する | P4/P5 |
| AR-076 | 停止/必須 | L236 | mute / pause中はprobe cycleをskipして連続失敗counterをresetし、pushもtarget muteを確認する | P4/P5 |
| AR-077 | 必須 | L238-245 | 自動muteする各playbookは対象とTTLを実装契約どおり設定する | P4/P5 |
| AR-078 | 停止/必須 | L247 | cert deployはglobal pause後、正常終了時だけresumeし、失敗でpauseが残れば人間の明示resumeまで全targetを再開しない | P4/P5/P7 |
| AR-079 | 例外/許可 | L253-255 | 自動検知不能な機能劣化は人間が判断し、Codexを介さず独立playbookを直接実行できる | P2/P5 |
| AR-080 | 許可/禁止 | L257-259 | manual service restartはauthy / monnieだけを対象とし、sophos-fwを対象外とする | P2/P3 |
| AR-081 | 許可 | L257/L260 | manual VM rebootは列挙された3 targetだけを対象とする | P2/P3 |
| AR-082 | 許可/禁止 | L257/L261 | manual HA failoverはauthy / sophos-fwだけを対象とし、monnieを対象外とする | P2/P3 |
| AR-083 | 例外/必須 | L263 | manual layerはprobe状態を発火条件にせず人間責任で起動できるが、target allowlist・tag・VM存在・HA登録gateを維持する | P4/P5/P7 |
| AR-084 | 必須/例外 | L263/L269 | report保存とSlack通知を各経路で行うが、通知失敗は本処理成否に影響させない | P6 |
| AR-085 | 必須 | L269 | trigger受理、各ladder段の結果、最終escalation時にJSTで通知する | P6 |
| AR-086 | 禁止 | L275 | Codexに汎用toolを許可しない | P7 |
| AR-087 | 禁止 | L276 | action key forced commandにparameterを許さない | P7 |
| AR-088 | 禁止 | L277 | investigate forced commandが未検証値をeval・展開して実行することを許さない | P7 |
| AR-089 | 禁止 | L278 | action_services allowlist外の変更操作を自動実行しない | P7 |
| AR-090 | 禁止 | L279 | ladder各段を2回以上自動反復しない | P4/P7 |
| AR-091 | 禁止 | L280 | sophos-fw上でOS level調査を自動実行しない | P7 |
| AR-092 | 禁止 | L281 | pve1 / pve2 / ansyを復旧action対象にしない | P7 |
| AR-093 | 禁止 | L282 | recovery-execにann鍵またはSlack tokenを持たせない | P7 |
| AR-094 | 制約/停止 | L288 | pushでservice restartが効かなければCodexからreboot / failoverへ進まず、人間へescalateする。ping条件を満たす独立pullまたはmanual layerだけが後段を実行できる | P5/P7 |

### 4.3 Reviewerの逐行照合規則

AR-001〜AR-094は移行先索引であり、原文の代替ではない。Phase 2 Reviewerは各`旧行`について、新Policy到達行と `保持` / `欠落` / `緩和` / `厳格化` / `条件・例外・順序変更` を記録する。特にAR-003〜AR-011、AR-018〜AR-023、AR-033〜AR-051、AR-053〜AR-078、AR-079〜AR-094は、対象allowlist、論理積・論理和、`のみ`、`一切`、`1回`、`skip`、`明示resume`、`人間判断`を旧HEADの表行・箇条書き・文単位で展開して照合する。

## 5. D: 対応Playbookと変更履歴の計画

### 5.1 対応するPlaybook 9本

「対応するPlaybook」はPolicy ownerが本Policyであるrecovery系入口を列挙する。muteを利用するpatch / certificate playbookは横断参照であり、この9本へ追加しない。

| playbook | 実role / task入口 | 新Policyで示す役割 |
|---|---|---|
| `recovery_probe_setup.yml` | `recovery_probe`、`recovery_mute` | pull probeとmute CLIの配備入口 |
| `recovery_exec_setup.yml` | `recovery_exec` | 限定Codex runner、鍵、wrapper、着地経路の配備入口 |
| `recovery_io_setup.yml` | `recovery_io` | Slack I/O bridgeの配備入口 |
| `recovery_push_setup.yml` | `recovery_push` | OnFailure push経路の配備入口 |
| `recovery_push_drill_setup.yml` | `recovery_push/tasks/drill_setup.yml` | push drill unitの配備入口。drill発火自体とは分ける |
| `recovery_ha_failover.yml` | `recovery_ha_failover` | 許可targetのmanual / pull最終段HA failover |
| `recovery_service_restart.yml` | `recovery_service_restart` | 許可targetのmanual service restart |
| `recovery_vm_reboot.yml` | `recovery_vm_reboot` | 許可targetのmanual / pull VM reboot |
| `recovery_probe_notify.yml` | `common_slack/tasks/notify.yml` | probe通知queueの送信入口 |

setup 5本とaction / notification 4本は実行安全度が異なる。新Policyでは入口を列挙するだけでなく、各playbookのtester-gateと実playbook先頭を参照し、setup配備と復旧actionを同じ許可として扱わない。

### 5.2 変更履歴

P8を新設し、少なくとも次を記録する。

| 日付 | 変更 | 記録方針 |
|---|---|---|
| 旧HEAD時点 | 288行版を移行元snapshotとして確定 | commit / blob /本009へ到達可能にする |
| Phase 2実施日 | 標準8節化、Policy核保持、3 Contextへの非規範情報分離、VM ID実値除去 | 安全境界の意味変更なしとReviewer結果を記録する |

## 6. E: 移動先、編集対象、選定理由

### 6.1 受け皿の選定理由

| 受け皿 | 選定理由 | 書かないもの |
|---|---|---|
| `docs/ai/context/system/autonomous-recovery.md` | target、account配置、daemon、依存先などコードだけで完結しない環境事実を収容する | VM ID / IP / VLAN /認証実値、許可・禁止、時点履歴 |
| `docs/ai/context/ansible/autonomous-recovery.md` | 9 playbook、複数role、鍵、forced command、wrapper、execpolicy、ACL、入出力の横断契約を収容する | 単一taskの逐語複製、最終安全判断、秘密、実値 |
| `docs/ai/context/operations/autonomous-recovery.md` | mute / pause、manual layer、調査追加、障害後の復旧・再開を順序として読む運用手順を収容する | Policyの判断条件、実装source、環境実値 |
| 本009 | 2026-07-05経緯、tester教訓、時点依存test /導入履歴、旧snapshot追跡を保持する | 現行運用の規範正本 |

ホームラボ固有のCLI / wrapper / forced-command契約はRepository Contextに置く。汎用化できず、Tech Lead指定どおり新Skillは作らない。

### 6.2 Phase 2で想定する編集対象

Phase 1では本009以外を編集しない。Phase 2はTech Leadの明示承認後に限る。

| path | 予定操作 |
|---|---|
| `docs/ai/policies/autonomous_recovery_policy.md` | 標準8節へ全面再編し、AR-001〜AR-094を意味変更なく収容 |
| `docs/ai/context/system/autonomous-recovery.md` | 新規。対象・account・依存の非規範事実を収容 |
| `docs/ai/context/ansible/autonomous-recovery.md` | 新規。9 playbookと横断実装契約を収容 |
| `docs/ai/context/operations/autonomous-recovery.md` | 新規。mute / manual /調査追加 /復旧運用を収容 |
| Phase 2 implement記録 | 新規。移動実績、AR到達行index、検査実績を記録 |

playbooks、roles、他Policy、既存Context、map、requirement、他者変更は対象外である。

## 7. 重複・矛盾リスク

| リスク | 実測 | Phase 2対策 |
|---|---|---|
| PolicyとRepository Contextの二重正本 | allowlist、鍵、wrapperが旧§4と§6で重複する | Policyはdeny / allow /分離原則だけ、Repository Contextは横断契約だけとし、具体一覧の正本をvars / template / codeへlinkする |
| §2、§5、§8のtarget範囲のずれ | 自動pull、push、manualで許可targetが異なる | P2に経路別matrixを一つ置き、P4/P5から参照する。全経路を一つのallowlistへ平坦化しない |
| §4.5のno_new_privilegesと§4.6 sudo | 前者はquory上Codex、後者はpve上SSH sessionで経路が異なる | System / Repository Contextで実行境界を図示し、P7にremote経路だけの例外条件を残す |
| muteとglobal pauseの混同 | 粒度、TTL、解除条件が異なる | P4で独立gateとして定義し、Operations Contextも別手順にする |
| cert_renew / patch Policyとの重複 | 他Policyがmute設定を参照する | 自律復旧Policyはmonitoring側skip / resume gateだけを正本とし、各呼出元の適用条件は各Policyに残す |
| notification重複 | §1、§5、§8、§9に通知記述が散在する | P6にbest-effortと通知時点を一度だけ定義し、各lifecycleはP6参照にする |
| playbook-map / role-mapとの重複 | 既存mapに9入口の概要がある | Repository Contextは横断する鍵・wrapper・ACL契約だけを追加し、mapの一行説明を複製しない |
| VM ID実値の再混入 | 旧§2に数値実値がある | 新Policy / 3 Context /記録へ転載せず、inventory / vars / codeを正本と明記する |
| 安全境界の強弱変化 | 要約でonly、all、1回、skip、resume条件が落ち得る | AR ledgerと4.3の逐行照合をPhase 2 Reviewerの必須gateにする |

## 8. 未解決点とPhase 2確認事項

Phase 2を止める受け皿未決はない。Reviewerが重点確認すべき点は次のとおりである。

1. 旧L24-26の対象別許可を、数値VM IDなしで同じtarget名・tag・許可actionにより一意に保てるか。
2. 旧L159の実機確認済み事実はSystem Contextへ固定せず、本009の時点履歴へ置く。現行remote sudo例外の条件だけをP7へ残す。
3. 旧L238-247の具体TTLとcert resume実装はOperations / Repository Contextへ移すが、skip時counter resetと失敗時の明示resume gateはP4/P5から落とさない。
4. setup playbookのrisk-acceptedとaction playbookのcheck-mode-native等は実playbook先頭が正本であり、新Policyの列挙表へ古いgate説明を複製しない。
5. 旧L288のpush制約を「push失敗後に自動pullを即発火する」と誤読しない。pullはping無応答条件で独立し、その他はmanual layerへescalateする。

## 9. 検査計画とPhase 1実績

### 9.1 Phase 1検査

- HEAD commit / blob / 288行を記録し、作業ツリー版でなくHEAD snapshotを参照する。
- 旧section配置表が表題1行 + 主section 11行で、§1〜§11を欠番なく覆うことを確認する。
- 範囲超過追跡表の件数、各行の種類・受け皿・Policy核が空でないことを確認する。
- ledger IDがAR-001から連番で重複せず、全行に種別・旧行・新Policy先があることを確認する。
- 対応Playbookが指定9本と完全一致し、全pathが実在することを確認する。
- Markdown表空欄、IPv4 literal、VLAN ID / VM ID数値実値、認証・秘密らしい実値を検査する。
- 本009以外のPhase 1差分が増えていないことを確認する。
- `git diff --check`と未追跡009への`git diff --no-index --check`を実施する。

Phase 1実測結果:

| 検査 | 結果 |
|---|---|
| HEAD snapshot | commit `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `e141d3eae0be403cc30fd6f905e08d6c2ddc51d7`、288行で一致 |
| 全量配置 | 表題範囲1行 + 主section 11行 = 12行、§1〜§11の欠番なし |
| 範囲超過追跡 | 22行、種類・受け皿・Policy核の空欄0 |
| safety ledger | AR-001〜AR-094の94件、連番欠落0、重複0、必須cell空欄0 |
| 対応Playbook | 指定9本、重複0、実path欠落0 |
| Markdown表 | 空cell 0 |
| 禁止実値 | IPv4 literal 0、VLAN ID / VM ID /認証情報 /秘密の実値0 |
| scope | Phase 1で本009だけを新規作成。Policy / Context / playbook / roleに本件の変更なし |
| whitespace | `git diff --check` PASS、`git diff --no-index --check /dev/null <本009>` PASS |

### 9.1.1 011 reviewによるAR-033補正（2026-07-24）

上記Phase 1実測結果は当時の実績として変更していない。011の旧HEAD逐行レビューで、AR-033要約に旧L92-93の`.json` suffix例外、optional target最大1 segment、JSON限定条件が不足していると判明した。AR番号を増減せず、§4.2のAR-033だけを全条件へ補正した。これはPhase 1実績の遡及改竄ではなく、Reviewerが検出した索引欠落をPhase 2修正契約へ反映する追記である。

### 9.2 Phase 2検査

- 新Policyの標準8見出しが順番どおり各1回で、変更履歴を含むこと。
- 範囲超過22行すべてに実移動先と新Policy核到達行があること。
- AR-001〜AR-094の全件に新Policy到達行があり、4.3に従う旧HEAD逐行照合で欠落・緩和・厳格化・条件変更が0であること。
- 対応Playbook 9本がP3に過不足なく列挙され、実path / playbook-mapと一致すること。
- 3 Contextが非規範であることとPolicy正本へのlinkを明示し、単一taskを過剰複製しないこと。
- Context間の重複、旧path、VM ID / IP / VLAN /認証 /秘密実値、Markdown表空欄を検査すること。
- 承認path以外、特にplaybooks / roles /他Policy /他者変更に新規diffがないこと。
- `git diff --check`を実施し、実機・Ansibleは実行しないこと。

## 10. Phase 1結論

旧Policyは、復旧判断のPolicy核と、環境配置、複数role実装、運用手順、時点履歴が混在している。22件の範囲超過候補を指定3 Contextと本009へ分けつつ、94件の安全境界を標準8節へ1:1追跡すれば、権限・禁止・復旧ラダーを弱めず再編できる。Phase 2を止める未解決点はなく、Tech Leadの承認まではPolicy / Context / codeを編集しない。
