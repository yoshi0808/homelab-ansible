# ADR-002: Proxmox Patch Dry-run 単一ノード対応の実装方式

**Status:** Accepted

## Context

homelabでは夏季の室温対策として`pve1`を平日日中シャットダウンする運用にしている(`pve2`は常時稼働)。この結果、毎日実行される`playbooks/proxmox_patch_dryrun.yml`(パッチのdry-run検出、実適用はしない)が、pve1停止中は構造的に機能しなくなっている。原因は3層ある。

1. `playbooks/proxmox_patch_dryrun.yml:13`の`any_errors_fatal: true`により、pve1がUNREACHABLEになるとpve2側の処理まで中断される。
2. `roles/proxmox_patch_dryrun/tasks/main.yml`が複数箇所(`:58-64`のmerge入力生成、`:89-107`のpre-status判定、`:216-230`の最終レポート生成)で`hostvars['pve1']`/`hostvars['pve2']`を固定参照しており、`--limit pve2`のような単独指定でも未定義変数エラーになる。通知文面(`:291`, `:296`, `:298`, `:311`)も`groups['proxmox']`固定参照で「pve1/pve2 ともに」という事実と異なる表示をする。
3. `docs/ai/policies/proxmox_patch_policy.md:99`のSB-023が単一ノードdry-run実行を明示的に禁止しており、実装だけ直してもPolicy違反状態になる。

2026-07-26、Yoshinobuから「SB-023の制約対象が誤っていた。本来の目的はpve1/pve2間の版数差分(drift)を作らないことであり、これはapply(実パッチ適用、SB-027/SB-028)側の懸念。dry-runはpackage metadata更新+simulationのみでpackage状態を変更しない情報収集であり、drift発生源ではない。パッチ情報は可能な限り入手したい」という方針確定があった(詳細は`docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_001_single_node_dryrun_investigation.md`§4)。

対照実装として`roles/proxmox_healthcheck`は、ホスト間相互参照をせず、集約が必要な箇所(Semaphoreサマリ生成、`roles/proxmox_healthcheck/tasks/main.yml:142,165`)で`ansible_play_hosts`(到達・成功したホストの動的リスト)をループする設計で、かつ`playbooks/proxmox_healthcheck.yml`は`any_errors_fatal`を持たない。この組み合わせにより`--limit`単体実行に既に対応済みである。

`roles/proxmox_patch_dryrun/files/proxmox-dryrun-merge.py`は`node_summaries`辞書(`:71-81`)を含め既にノード数非依存の実装であり(2026-07-26に全文再確認)、`reboot_required`は各ノードのsummary内に既に含まれている(`:77`)。Ansible側の固定参照を直せば無改修で流用できる。

## Options Considered

### (a) `any_errors_fatal`の扱い

| Option | Pros | Cons |
|---|---|---|
| a-1: `any_errors_fatal`を除去し、Phase 2以降を`ansible_play_hosts`ベースの動的処理に変更、到達ノード0件のみ明示fail | `proxmox_healthcheck.yml`実証済みパターンをそのまま踏襲。実装コストが最小 | pve2単体の本物のapt/healthcheck異常も即abortでなく単なる除外になり、fixed-pair時の「どちらかがダメなら両方止める」という従来の安全側挙動と意味が変わる |
| a-2: `any_errors_fatal_when`でUNREACHABLE/failed種別ごとに挙動を分岐 | 到達性エラーとロジックエラーを機構レベルで区別できる | タスク単位の細かい制御が必要になり複雑化。既存healthcheckゲート(`roles/proxmox_patch_dryrun/tasks/main.yml:6-9`)との役割分担が二重管理になる |
| a-3: `any_errors_fatal`をPhase 1収集blockだけに局所適用(block/rescue) | 全体構成を変えず影響範囲を局所化できる | Phase 2以降を「揃ったノードだけで処理する」設計にする必要は結局a-1と同じで、a-3単独では解決しない |

### (b) `reboot_required_pve1`/`_pve2`レポートschema

| Option | Pros | Cons |
|---|---|---|
| b-1: 固定キーを維持し、値だけconditionalにする | 変更範囲最小 | 単一ノード時に存在しない側のキーの値をどう埋めるか(null/false)が意味的に曖昧になり、「未検証」と「reboot不要」を混同しかねない |
| b-2: `unified_dryrun.node_summaries[node].reboot_required`から動的な形式(ノード名key)で構築する | node数に依存しないschemaになり、`node_summaries`と情報源が一致し重複がなくなる。存在しないノードのキー自体が生成されないため「未検証」が自然に表現される | repo外の未確認消費者(Semaphore dashboard等)がいた場合に影響する可能性 |

### (c) 既存playbook改修 vs 専用playbook新設

| Option | Pros | Cons |
|---|---|---|
| c-1: 既存`playbooks/proxmox_patch_dryrun.yml`と`roles/proxmox_patch_dryrun`を直接改修 | ロジック重複がなく保守対象が1つ。fixed-pair運用時の回帰確認を1本のテストでカバーできる | 既存の安定動作(fixed-pair時)に対するリグレッションリスクがある |
| c-2: 専用playbook(例: `proxmox_patch_dryrun_single.yml`)を新設 | 既存版に一切触れないためfixed-pair側のリグレッションリスクがゼロ | ロジック重複(healthcheckゲート、merge呼び出し、通知文面組み立て等)が二重管理になり、Policy改訂も両方に効かせる必要が生じる。`proxmox_healthcheck`が単一playbookで両方カバーしている実例と矛盾する |

### (d) 通信断と`--limit`による意図的単一ノードの区別

| Option | Pros | Cons |
|---|---|---|
| d-1: 新規実行時変数(例: `proxmox_patch_dryrun_expected_nodes`)を導入し、実行者が明示的に対象を宣言する | 意図を明示的に受け取れる | 新規変数の運用(誰がいつ設定するか、scheduler側の対応)が増え、指定を忘れると区別できない。Policyにも新しい運用手順を追加する必要がある |
| d-2: Ansible標準の`ansible_play_hosts_all`(play開始時点で`--limit`適用済みの対象集合、失敗で縮小しない)と`ansible_play_hosts`(実行中に到達・処理失敗したノードを除いた集合)の差分で区別する | 新規変数が不要。`--limit`で明示的に除外されたノードは最初から`ansible_play_hosts_all`に現れず、in-play障害で脱落したノードは`_all`に居るが`ansible_play_hosts`から消える、という標準機構の違いだけで判定できる | 未実装のため実機検証で挙動を裏付ける必要がある。導入済み`ansible-core`バージョンでの実地確認が前提 |

## Decision

- **(a) a-1を採用**: `any_errors_fatal: true`(`playbooks/proxmox_patch_dryrun.yml:13`)を除去し、Phase 2以降を`ansible_play_hosts`ベースの動的処理へ変更する。a-1の懸念(本物の異常が静かに握りつぶされる)への対策として、Phase 2冒頭に「到達・処理できたノードが0件なら明示fail」するガードタスクの追加を必須とする。既存healthcheckゲート(`roles/proxmox_patch_dryrun/tasks/main.yml:6-9`)は各ホストごとに独立して機能する設計のまま維持し、healthcheckがWARNING/CRITICALのノードはそのノード単体が除外される。これはfixed-pair時の「片方がダメなら両方止める」という従来の全体abort挙動からの意図的な変更であり、Yoshinobuの確定方針(「パッチ情報は可能な限り入手したい」)と整合する。
- **(b) b-2を採用**: `reboot_required`を`unified_dryrun.node_summaries[node].reboot_required`から動的に構築する。この情報はmerge script(`proxmox-dryrun-merge.py:77`)に既に存在し、`main.yml:226-227`の`hostvars['pve1']`/`hostvars['pve2']`再参照は重複した情報源だったため、統合により行数も減る。repo内消費者は0件(grep確認済み、投稿された投資記録`2026-07-26_001_...md`§5参照)。repo外消費者の有無はrequirement.mdのオープンクエスチョンとし、実装着手前にYoshinobuへ確認する。**2026-07-26追記(review 2026-07-26_004 Suggestions #4を受けて)**: requirement.md P0スコープの実装(`2026-07-26_003_implement.md`)では、repo外消費者の有無が未確認のままP0を先行実装するため、`reboot_required_pve1`/`_pve2`という固定キー自体は維持し(b-1の機構)、`none`明示によりb-1の却下理由(「未検証」と「reboot不要」の混同)を解消したうえで、値の算出だけを`unified_dryrun.node_summaries`ベースのnode非依存な形にする最小修正にとどめた。b-2が指す完全な動的schema化(固定キー自体の廃止、node名keyへの置換)はrequirement.md P1へ再委任し、repo外消費者の有無確認後に改めて実施する。
- **(c) c-1を採用**: 既存playbook/roleを直接改修する。`proxmox_healthcheck`が単一playbookでfixed-pair運用と単一ノード運用の両方を実証済みでカバーしている実例に倣う。ロジック二重管理とPolicy二重適用のコストが、c-2のリグレッション回避メリットを上回ると判断する。リグレッションリスクはTesterによるfixed-pair側の回帰確認(requirement.md AC2)で相殺する。
- **(d) d-2を採用**: 新規変数を導入せず、`ansible_play_hosts_all`と`ansible_play_hosts`の差分でintentional excludeとin-play failureを区別する。Phase 2冒頭のガードタスクで両者を比較し、通知文面の生成にこの区別を反映する。Testerが実機で本機構の実挙動を裏付ける。

## Trade-off Analysis

4つの決定はいずれも「新しい独自機構を増やさず、`proxmox_healthcheck`が既に実証済みのAnsible標準機構(`ansible_play_hosts`系変数、`any_errors_fatal`の不使用)を再利用する」という一貫した方針を取る。これは本リポジトリの既存パターン踏襲であり、保守対象を増やさない。

`any_errors_fatal`除去(a-1)は、fixed-pair運用時に持っていた「片方の本物の異常で全体停止する」という安全側の挙動を弱める副作用があるが、これはYoshinobuが明示的に受け入れた方針転換(dry-runはdrift源ではないため片肺でも情報収集を優先する)の直接の帰結であり、独立した設計判断ミスではない。この副作用の実害(異常の見逃し)は、a-1単体ではなく「到達ノード0件の明示fail」ガードと組み合わせることで、最悪ケース(両ノード喪失)だけは確実に検知できるようにして限定する。片方のノードだけの異常(もう片方は健全)を見逃さないという要求は今回のスコープでは追わない(healthcheckゲートがそのノード単体を除外するのみで全体停止はしない、というのが新しい仕様として明示される)。

(d)のAnsible標準変数差分方式は、新規変数(d-1)よりも「運用者が指定を忘れる」余地がなく、`--limit`の有無という既存の実行方法そのものから区別できる点で優れるが、実装前に静的コードレビューだけでは正しさを保証できないため、Testerによる実機検証を明示的に要求する。

## Consequences

- `roles/proxmox_patch_dryrun/tasks/main.yml`の`hostvars['pve1']`/`hostvars['pve2']`直接参照(`:58-64`, `:92-97`, `:226-227`)をすべて`ansible_play_hosts`または`unified_dryrun.node_summaries`のキー集合ベースのループに置き換える。
- `playbooks/proxmox_patch_dryrun.yml`の`any_errors_fatal: true`(`:13`)を削除し、Phase 2冒頭に到達ノード0件の明示failガードタスクを追加する。
- 通知文面(`roles/proxmox_patch_dryrun/tasks/main.yml:291,296,298,311`付近)の`groups['proxmox']`固定参照を、実際に処理したノード集合ベースの動的表現に置き換え、`--limit`明示ケースと通信断ケースを区別する文言を追加する。
- `docs/ai/policies/proxmox_patch_policy.md`のSB-023(`:99`)を、apply側のdrift回避要求とdry-run側の許可を分離する条件文へ改訂する。新規SB番号を採番し、廃止番号非再利用の既存慣行(§8変更履歴)に倣う。
- apply/weekly full側(SB-027/SB-028/SB-032)は本ADRの対象外であり変更しない。単一ノードdry-runの`PATCH_READY`がfixed-pair gate条件を満たさないことをPolicy本文(§7制約、`:354`以降)に明記する。
- `docs/ai/context/operations/proxmox-patch.md:30`の「dry-runまたはre-dry-run」という一文は、Policy改訂後の反映としてContext側も後追いで更新が必要(Policyが正本、Contextは非規範であるためPolicy改訂が先)。
- 既存fixed-pair運用時の出力(Status/Urgency/report/通知文言)が変更前と一致することをTesterが回帰確認する(requirement.md AC2)。
