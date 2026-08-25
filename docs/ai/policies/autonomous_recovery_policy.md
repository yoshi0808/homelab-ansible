# Autonomous Recovery Policy

本書は自律復旧の許可、禁止、停止条件、判断軸の正本である。環境事実と実装・運用詳細は対応Contextを参照し、競合時は本Policyを優先する。

## 1. 目的

<!-- AR-001 -->
対象サービスの業務継続を、人間の承認を待たない限定的な自律復旧試行で支える。

<!-- AR-002 -->
Slackは承認gateにせず、手動依頼の入口と結果通知にだけ使う。

## 2. 対象と実行範囲

自動pull、OnFailure push、人間によるmanual layerは別経路であり、許可範囲を相互に拡張しない。

<!-- AR-003 -->
- `sophos-fw`: service restartを許可しない。ping ladderではVM reboot後、未復旧かつfailover条件を満たす場合だけHA failoverを許可する。
<!-- AR-004 -->
- `authy`: 許可serviceのrestartを許可する。ping ladderではVM reboot後、未復旧かつfailover条件を満たす場合だけHA failoverを許可する。
<!-- AR-005 -->
- `monnie`: 許可serviceのrestartとVM rebootだけを許可し、HA failoverを許可しない。HA管理対象外(`hacritical` tagなし)であるためHA failoverという手段自体が存在しない。非HA guestとしての通常migrationはpatch flowの権限であり、自律復旧の行動集合には含めない。
<!-- AR-006 -->
- `pve1` / `pve2`: 自律復旧actionの対象外とし、限定されたread-only調査だけを許可する。
<!-- AR-007 -->
- `ansy`: 自律復旧actionの対象外とする。

<!-- AR-009 -->
service restartはVM内部のservice crashにだけ用い、対象serviceがない`sophos-fw`にはこの経路を設けない。

<!-- AR-010 -->
ping ladderはVM単位で判定する。`pvesh`で状態を確証し、runningのまま無応答の場合にVM reboot、`hacritical`かつ未復旧の場合だけHA failoverへ進む。

<!-- AR-011 -->
`pve1` / `pve2`へ`action_services`相当の復旧手段を追加してはならない。

<!-- AR-068 -->
Slackからの手動依頼は限定wrapper経由のCodex jobとしてだけ受け、結果を同じthreadへ返す。

<!-- AR-079 -->
自動検知できない機能劣化は人間が判断し、Codexを介さずmanual layerの独立playbookを直接実行できる。

## 3. 対応するPlaybook

setup、action、notificationは安全度と目的が異なる。setup入口の列挙を復旧actionの実行許可として扱ってはならず、各入口のtester-gateは実playbook先頭を正本とする。

| 種別 | Playbook | Policy上の役割 |
|---|---|---|
| setup | `recovery_probe_setup.yml` | pull probeとmute CLIを配備する |
| setup | `recovery_exec_setup.yml` | 限定Codex runner、鍵、wrapper、着地経路を配備する |
| setup | `recovery_io_setup.yml` | Slack I/O bridgeを配備する |
| setup | `recovery_push_setup.yml` | OnFailure push経路を配備する |
| setup | `recovery_push_drill_setup.yml` | push drill unitだけを配備する。drill発火は含まない |
| action | `recovery_ha_failover.yml` | 許可targetのmanualまたはpull最終段HA failoverを行う |
| action | `recovery_service_restart.yml` | 許可targetのmanual service restartを行う |
| action | `recovery_vm_reboot.yml` | 許可targetのmanualまたはpull VM rebootを行う |
| notification | `recovery_probe_notify.yml` | probe通知queueを送信する |

<!-- AR-029 -->
investigate追加後は`recovery_exec_setup.yml`を正規入口としてwrapper、dispatch、Codex向け説明を同時に配備する。

<!-- AR-080 -->
manual service restartは`authy` / `monnie`だけを対象とし、`sophos-fw`を対象外とする。

<!-- AR-081 -->
manual VM rebootは`authy` / `monnie` / `sophos-fw`だけを対象とする。

<!-- AR-082 -->
manual HA failoverは`authy` / `sophos-fw`だけを対象とし、`monnie`を対象外とする。

## 4. 判断軸

### Probeとflapping

<!-- AR-053 -->
`sophos-fw`はicmpとdnsの両probeについて5回連続失敗を発火閾値とする(AR-052の60秒間隔での5回、すなわち約5分)。

<!-- AR-054 -->
`authy`はicmpとtcp probeについて5回連続失敗を発火閾値とする(AR-052の60秒間隔での5回、すなわち約5分)。

<!-- AR-055 -->
`monnie`はicmpとtcp probeについて5回連続失敗を発火閾値とする(AR-052の60秒間隔での5回、すなわち約5分)。

<!-- AR-057 -->
ladder lockを取得済みなら重複実行をskipする。

<!-- AR-058 -->
直近24時間で3回以上発火していればflappingと判定し、ladderを実行せずescalation通知だけを行う。

### `pvesh`状態分岐と復旧結果

<!-- AR-059 -->
`pvesh`でVM状態を確証し、Proxmox node自体へ到達できなければactionせずcritical通知する。

<!-- AR-060 -->
VMがstoppedならrebootでなくstartを1回だけ行い、復旧を確認する。

<!-- AR-061 -->
VMがnot-foundならactionを進めずcritical通知する。

<!-- AR-062 -->
VMがrunningのままping無応答の場合だけVM reboot段へ進む。

<!-- AR-063 -->
target固定のVM rebootを1回だけ実行し、復旧すればok通知して終了する。

<!-- AR-064 -->
reboot後も未復旧で、かつtargetがfailover許可対象の場合だけHA failoverを1回実行する。それでも未復旧なら人間へescalateする。

### Muteとglobal pause

<!-- AR-075 -->
target別のTTL付きmuteと、明示的なresumeまで継続するTTLなしglobal pauseを、独立したgateとして維持する。

<!-- AR-076 -->
muteまたはglobal pauseが有効ならprobe cycleをskipし、そのtargetの連続失敗counterをresetする。push経路もtarget別muteを確認する。

<!-- AR-077 -->
自動muteは次の契約を維持する。段階単位のplaybookは一律120分とし、待ち時間を個別に最適化しない。`proxmox_evacuate_node.yml`は`authy` / `monnie` / `sophos-fw`へ120分、`proxmox_patch_apply_node.yml`は同3 targetへ120分、`proxmox_restore_vm_placement.yml`は同3 targetへ120分、`ubuntu_nightly.yml`はreboot対象の`authy` / `monnie`へ120分、`ubuntu_vm_full_upgrade.yml`はapply対象の`authy` / `monnie`へ120分。

`proxmox_patch_weekly_full.yml`だけは例外として同3 targetへ360分を設定する。これは両nodeを跨ぐ多時間orchestration全体を先頭で一括して覆う毛布であり、段階単位の120分へ揃えない。段階mute間の待ちが延びた場合(reboot後のhealthcheck retry等)に被覆が切れ、internetに面する`sophos-fw`で誤発火する経路を塞ぐためである。mute設定は`max(既存until, now + minutes)`で既存の窓を短縮しないため、毛布と段階muteは安全に併存する。

<!-- AR-078 -->
証明書deployはglobal pause後に実施し、正常終了した場合だけresumeする。失敗してpauseが残った場合は、人間が明示resumeするまで全targetの監視を再開しない。

<!-- AR-103 -->
**global pauseが継続していること、およびprobeが稼働していないことを、日次で人間へ通知する。** global pauseはTTLを持たない(AR-075)ため、解除忘れは誰かが能動的に状態を問い合わせるまで検出されない。同じく`recovery-probe`のunitは失敗時の自動再起動だけを持ち、明示的に停止された場合を知らせる経路を持たない。両者は「自律復旧が効いていない状態が続く」という同一の失敗classであり、単一の日次確認で扱う。

- 検査は状態の読み取りのみで行い、pause / muteを変更しない。**TTLによる自動resumeは採らない** — 意図的に停止しているhostに対して復旧ladderが誤発火し得るため、解除の判断は人間が行う。
- 正常時は通知しない。通知が到達したこと自体を異常の信号とする。
- 通知にはpauseの開始時刻と経過時間を含める。解除忘れの深刻さ(1日か8日か)を受信者がその場で判断できるようにするためである。
- 状態を`ACTIVE` / `PAUSED`のいずれとも解釈できない場合は、正常扱いにせず非ゼロで停止する。
- target別mute(TTLで自動失効する)は本確認の対象に含めない。解除忘れが構造的に起こらず、かつ定期patch処理が立てるmuteと重なって偽警報を生むためである。

実装は`playbooks/recovery_monitoring_check.yml`、日次起動はSemaphoreのscheduleが担う。案件記録は`docs/ai/reviews/recovery_pause_daily_check/`。

## 5. ライフサイクル・処理フロー

### 共通の経路分離

<!-- AR-008 -->
service restart経路とping ladderは別障害classとして独立させ、相互の発火条件を代用しない。

<!-- AR-052 -->
pull probeは全対象を60秒間隔で継続監視する。

<!-- AR-056 -->
各targetは短縮名でなく明示FQDNで解決する。

### Pull ladder

pullはlock、flapping、`pvesh`の各分岐を順に評価し、条件を満たす段だけを実行する。

<!-- AR-032 -->
service restartを行う場合はrestart前にreset-failedを行い、start-limit raceを回避する。

### Push

<!-- AR-065 -->
push経路は許可serviceのOnFailure、target固有key、forced commandに限定する。

<!-- AR-066 -->
pushはtarget別muteを確認し、実行中lockを取得できない場合は重複起動しない。

<!-- AR-067 -->
pushで起動されたCodexはinvestigate→判断→recover→再investigate→escalationの順に従い、VM reboot / HA failover手段を持たない。

<!-- AR-071 -->
VM rebootとHA failoverはpush経路にwrapperを置かないことで到達不能にし、pull経路のtarget固定・決定論的playbook呼出しにだけ許可する。

### Manual layerと終了

<!-- AR-083 -->
manual layerはprobeの現在状態を発火条件にせず、人間の判断責任で直接起動できる。ただしtarget allowlist、tag再検証、VM存在確認、HA登録確認を迂回してはならない。

<!-- AR-094 -->
pushでservice restartが効かなければ、CodexからVM reboot / HA failoverへ進まず人間へescalateする。後段はping無応答条件を独立して満たしたpullか、人間判断のmanual layerだけが実行できる。

## 6. 通知方針

<!-- AR-084 -->
各経路はreport保存とSlack通知を行う。Slack通知はbest-effortとし、送信失敗を本処理の成否へ影響させない。

<!-- AR-085 -->
trigger受理時、各ladder段の試行結果、最終escalation時にJSTで通知する。

## 7. 制約・禁止事項

### Account、token、keyの分離

<!-- AR-012 -->
`ann`は定常自動化専用とし、自律復旧の権限・keyと混用しない。

<!-- AR-013 -->
`recovery-io`はSlack認可だけを担当し、Slack token以外の復旧権限を持たせない。

<!-- AR-014 -->
`recovery-exec`は調査・復旧keyを持てるがSlack tokenを持たず、呼び出された時だけCodexを起動する。

<!-- AR-015 -->
target側`recovery-exec`はforced-command着地専用accountとする。

<!-- AR-016 -->
probe実行accountにはglobal pauseを読むために必要な権限だけを与える。

<!-- AR-017 -->
`recovery-exec`に常駐processを持たせてはならない。

<!-- AR-018 -->
investigate keyが受け取るparameterはdispatch allowlistで検証してから実行する。

<!-- AR-019 -->
action keyのforced commandはparameterを受け取らず、固定された許可serviceのrestart一式だけを実行する。

<!-- AR-020 -->
push keyはtarget固有のforced commandへ固定し、target側から引数を渡せないようにする。

<!-- AR-021 -->
`ann`の既存keyを`recovery-exec`へ流用してはならない。

<!-- AR-022 -->
`authy` / `monnie`の`authorized_keys`はinvestigate / actionの2 entryだけをtemplateで排他的に管理する。

### Investigate / actionのallowlist

<!-- AR-023 -->
investigateはservice、journal、extra、common checkのallowlistだけを許可し、一致しない値を拒否する。

<!-- AR-024 -->
新規investigateにはread-only確認だけを追加でき、復旧commandを追加してはならない。

<!-- AR-025 -->
service調査の追加はtargetごとの`investigate_services`へ限定して反映する。

<!-- AR-026 -->
extra調査は固定name / commandとして追加し、sudoが必要なら対応sudoersを個別に同期する。検証済みparameterを取る調査を追加する場合はこの限りでなく、「Loki横断ログ調査」の条項に従う。

<!-- AR-027 -->
`recovery_exec_targets`をwrapperとdispatchの共通allowlist正本とする。

<!-- AR-028 -->
調査追加時はCodexがそのcheckを認識できる説明も同期する。

<!-- AR-104 -->
Codex向けAGENTS.mdは2つある。`recovery_exec`が配るもの(自律復旧のCodex)と、`incident_inspect`が配るもの(一次調査のLLM)で、能力が異なるため同一にしない。統合もしない。一次調査のLLMはSSH鍵を持たずdispatchへ到達できないため、そのAGENTS.mdへdispatchのcommandを書かない。

<!-- AR-030 -->
common check categoryを追加する場合だけ両templateへ直接追加し、両側の検証を同期する。

<!-- AR-031 -->
actionは無引数でallowlist内の全serviceを一括restartし、個別service指定を許可しない。

### Loki横断ログ調査

<!-- AR-095 -->
Loki横断ログ調査は、`recovery_exec` roleのdispatch templateが列挙する検証済みparameter付きcheckの範囲だけを許可する。

<!-- AR-096 -->
parameterは固定arityとし、時刻は分精度の固定書式、それ以外は列挙allowlistに限定する。自由文字列によるlog本文filterを許可しない。

<!-- AR-097 -->
quory側wrapperを一次filter、対象host側dispatchを権限の本gateとし、dispatchが独立に再parseして不正tokenをLoki問い合わせ到達前に拒否する。

<!-- AR-098 -->
出力量はLokiへのquery limit、返す行数、1行の長さの3点で固定し、対象host側で強制する。quory側wrapperへ出力量制限を置かない — logが認可境界を越えた後の切り詰めは防御にならず、二層あるという誤解だけを生む。二層で検証するのはparameterであり、出力量ではない。

<!-- AR-099 -->
level labelでの絞り込みを既定にしない。label自体が付かないlogが存在するため、絞り込みを既定にすると該当logが無言で欠落する。

<!-- AR-100 -->
時刻parameterはJST固定解釈とし、実行hostのTZ設定に依存させない。

<!-- AR-101 -->
このcheckが返すlog本文はhomelab全体の集約であり、対象hostのlogに限られない。Alloyが収集済みのlogがCodexへ渡ることを許容するが、`docs/ai/core.md`が定義する秘密情報は対象外とする。

### Report / Semaphore調査

<!-- AR-033 -->
report調査は定型3 commandだけを許可する。optional `target`は最大1 path segmentとし、`playbook` / `target` / filename basenameは英数字・underscore・hyphenだけを許可する。component内のslashとdotは拒否するが、filename末尾の固定`.json` suffixだけはdotの例外として必須で許可する。`list-reports`の列挙と`show-report`の表示対象はJSONだけに限定する。

<!-- AR-034 -->
report読取りは対象accountへの直接ACLで許可し、sudo / setuidによる昇格を使わない。

<!-- AR-035 -->
report調査はwrapperとhelperの二層で引数を再検証する。

<!-- AR-036 -->
Semaphore調査は定型4 queryと範囲検証済み整数parameterだけを許可し、自由SQLを受け付けない。

<!-- AR-037 -->
DBは必要なACLとread-only engine flagで読み、sudoを使わない。

<!-- AR-038 -->
SQLはargv配列として渡し、shell文字列連結・再解釈を行わない。

### Privilege境界とProxmox調査

<!-- AR-039 -->
`no_new_privileges`を解除してsandbox防御を弱めてはならない。

<!-- AR-040 -->
Codex側の不足読取り権限は権限昇格でなく、対象accountへの直接ACLで与える。

<!-- AR-041 -->
Proxmox node上のSSH session内sudoはCodex sandboxを通らない場合にだけ許可し、quory上Codexからの権限昇格と区別する。

<!-- AR-042 -->
Proxmox調査はread-onlyに限定し、自律復旧actionを追加してはならない。

<!-- AR-043 -->
Proxmox調査keyは他targetのinvestigate keyから目的別に1本分離し、両Proxmox nodeの調査にだけ用いる。

<!-- AR-044 -->
Proxmox着地accountは`ann`から分離し、forced command専用にする。

<!-- AR-045 -->
Proxmox named checkは、`recovery_exec` roleのdispatch templateが列挙する固定checkと検証済みparameter付きcheckの範囲だけを許可する。

<!-- AR-046 -->
quory側wrapperを一次filter、Proxmox側dispatchを権限の本gateとし、dispatchが独立に再parseして不正token等をsudo到達前に拒否する。

<!-- AR-047 -->
parameter検証はdispatchを正本、wrapperをmirrorとし、形式、範囲、allowlist、出力量を固定する。

<!-- AR-048 -->
sudo argvは絶対path、固定read-only動詞、検証済みoperandの順に固定し、`eval`、shell再解釈、書込み動詞を許可しない。

<!-- AR-049 -->
sudoersは固定checkを1:1列挙し、検証済みparameter位置だけの限定wildcard以外を禁止する。wildcard単独を権限境界にせずdispatch検証を必須とする。

<!-- AR-050 -->
`pvesh`の書込み動詞を構造的に実行不能とし、node状態はread-only代替checkで取得する。

<!-- AR-051 -->
追加checkの絶対path、unit実在、sudoers grammar、forced-command経路を配備前とtester工程で確認する。

### wrapper、sandbox、file権限

<!-- AR-069 -->
Codexが呼べるwrapper群 — target investigate、Proxmox investigate、report、Semaphore query、target recover、monitoring control — は`AGENTS.md`が列挙する**指示**であり、実行を阻む境界ではない。wrapper名と引数grammarは`recovery_exec` roleのfiles / templatesを正本とする。

<!-- AR-070 -->
Proxmox nodeへrecover wrapperを用意せず、二段検証済みread-only named check以外を実行不能にする。

<!-- AR-072 -->
Codex wrapperは引数の個数・位置・値を厳密に固定し、sandbox、approval、execpolicy optionを呼出元から受け取らない。

<!-- AR-073 -->
この経路の防御層はCodex sandbox、`no_new_privileges`、target側forced command、sudoersの4つとし、tokenとSSH keyはOS file権限と専用ownerで保護する。設定層のコマンド制限を層として数えない。

<!-- AR-074 -->
Codex wrapperはsudo、setuid、file capabilityによる権限昇格を前提にせず、不足権限には直接ACLを使う。

### 明示的な禁止事項

<!-- AR-086 -->
- CodexにBash / Write / Edit / Read / Glob / Grep等の汎用toolを許可してはならない。
<!-- AR-087 -->
- action keyのforced commandにparameterを許可してはならない。
<!-- AR-088 -->
- investigate forced commandが未検証値を`eval`または展開して実行してはならない。
<!-- AR-089 -->
- `action_services` allowlist外の変更操作を自動実行してはならない。
<!-- AR-090 -->
- ladderの各段を2回以上自動反復してはならない。
<!-- AR-091 -->
- `sophos-fw`上でOS level調査を自動実行してはならない。
<!-- AR-092 -->
- `pve1` / `pve2` / `ansy`を復旧action対象にしてはならない。
<!-- AR-093 -->
- `recovery-exec`に`ann`のkeyまたはSlack tokenを持たせてはならない。
<!-- AR-102 -->
- Codexの設定ファイルに書くコマンド制限(execpolicy等)を安全境界として設計してはならない。境界は能力の不在 — 鍵・wrapper・到達先が存在しないこと — で作る。

## 8. 変更履歴

| 日付 | 変更 |
|---|---|
| 2026-07-24 | Git HEADの旧288行版を標準8節へ再編。Policy核を維持し、非規範の環境・Repository・Operations情報をContextへ分離。旧表の数値VM IDは転載せず、inventory / vars / codeを正本とした |
| 2026-07-29 | Loki横断ログ調査(AR-095〜AR-101)を新設し、AR-026に検証済みparameter付き調査の例外を追加。案件記録: `docs/ai/reviews/slack_loki_investigation/` |
| 2026-07-31 | execpolicyが安全境界として成立しないことが実測で確定したため、AR-069 / AR-071 / AR-073を実態(能力の不在で境界を作る)へ改訂し、AR-102を新設。§7の節名も`Execpolicy、wrapper、file権限`から改めた。根拠: `docs/ai/memory/incidents/2026-07-31_codex-execpolicy-allowlist-not-enforcing.md` |
| 2026-08-01 | global pauseの解除忘れとprobe停止を日次で検知する規定としてAR-103を新設。TTLによる自動resumeは採らず、通知で人間の判断を挟む形とした(Yoshinobu選択)。根拠: `docs/ai/memory/incidents/2026-07-29_global-monitoring-pause-left-on-8-days.md`、案件記録: `docs/ai/reviews/recovery_pause_daily_check/` |
| 2026-08-02 | AR-103本文にあった根拠引用(`docs/ai/memory/incidents/2026-07-29_global-monitoring-pause-left-on-8-days.md`。上記2026-08-01行に同一引用が既存)を除去し、実装・案件記録のポインタだけを残した(`docs/ai/reviews/norm_docs_rationale_removal_round3/`)。許可・禁止・停止条件、AR番号はいずれも変更していない。AR番号の新設・退番はない |
| 2026-08-25 | Codex向けAGENTS.mdが2つあり能力が異なることを規定としてAR-104を新設。同一化・統合を禁じ、一次調査のLLMのAGENTS.mdへdispatchのcommandを書かないことを明記した。既存AR番号の改訂・退番はない |
| 2026-08-25 | Pull ladderの説明文にあった未定義識別子「P4」(本文書のどこにも定義が無い)と、列挙と一致しない数の宣言「4分岐」を削除した。許可・禁止・停止条件は変更していない。 |
