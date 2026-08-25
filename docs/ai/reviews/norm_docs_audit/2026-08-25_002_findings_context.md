# 規範文書横断監査 findings — Context群(2026-08-25)

対象: CLAUDE.md / AGENTS.md / `docs/ai/core.md` / `docs/ai/context-classification.md` / `docs/ai/role-context-matrix.md` / `docs/ai/memory-classification.md` / `docs/ai/roles/*.md`(6本)/ `docs/ai/context/` 配下18本。文書どうしの整合のみを検査した(技術的な正否は対象外)。参照先の実在確認はリポジトリ全体(`roles/` / `playbooks/` / `scripts/` / `docs/ai/policies/` / git履歴)に対して行った。

---

## 1. 矛盾

### 1-1. Semaphore scheduleの正本が「カタログ」と「Semaphore UI」の2説ある

- `docs/ai/context/system/semaphore.md:18`
  > **template と schedule の正本は `roles/semaphore_templates/defaults/main.yml` のカタログにある**(template=2026-08-04、schedule=2026-08-10 の `semaphore_schedules_as_code` 案件)。
- `docs/ai/context/operations/code-delivery-to-production.md:206`
  > 正本は `roles/semaphore_templates/defaults/main.yml`。**「どの playbook をボタンにするか」(template)と「いつ押されるか」(schedule)の両方**がここにある。
- `docs/ai/context/operations/ubuntu-vm-patch.md:78`
  > 正確な時刻とschedule有効性はSemaphore UIを正本とし、UI設定はリポジトリ外で変化し得るため本書は複製・保証しない。
- `docs/ai/context-classification.md:64`
  > | 実行schedule、時刻、曜日、cadence | scheduler設定(systemd timer定義またはSemaphore UI)。UI設定はリポジトリ外で変化するため、リポジトリ内の記述は現在値を保証しない |

2026-08-10のschedules-as-code化以降、semaphore.mdとcode-delivery-to-production.mdはカタログを正本とする(UIの一時変更は次の適用でカタログ値へ戻る)が、ubuntu-vm-patch.mdとcontext-classification.md §3.2表は依然Semaphore UIを正本と指名しており、同じ値に対する正本の指名が両立しない。なお`semaphore.md`は同一文書内でも割れている — :18でカタログを正本と言いつつ、:22で「UI上で現在有効かどうかと正確な時刻はSemaphore UIで確認する」と述べる(「現在値の観測」と「正本」の区別と読む余地はあるが、:18の宣言とは整合の説明が無い)。

### 1-2. 「現在唯一有効なsystemd timerはcert-renew-quory」は、他の入力文書が記載するtimerと両立しない

- `docs/ai/context/operations/ubuntu-vm-patch.md:78`
  > 現在唯一有効なsystemd timerは`cert-renew-quory`(`quory`上、`cert_renew_quory.yml`、月初00:35)である。
- `docs/ai/context/operations/code-delivery-to-production.md:16`
  > │  git pull --ff-only     ← quoryのtimerが自動で行う(worktree_sync)
  (同:50 も「quoryが作業ツリーをpull(1分間隔)」と、quory上のtimer駆動を記す)
- `docs/ai/memory-classification.md:115`
  > **起動はtimerが行う。** `roles/knowledge_review`が配置する`ansible-knowledge-review.timer`が毎月26日にansyで発火し、`playbooks/knowledge_review.yml`がきっかけの通知を出す。

worktree-sync timerは同じquory上で稼働する設計であり(`roles/worktree_sync/templates/worktree-sync.timer.j2` が実在)、knowledge-review timerもansy上に配置される(`roles/knowledge_review/tasks/install_timer.yml` が実在)。「唯一有効」は`roles/systemd_timers`のカタログ内でのみ真であり(同カタログの現行entryはcert-renew-quoryのみであることは確認した)、無限定に書かれた現在の文はこれら2文書と両立しない。

### 1-3. 「やらないと決めたこと」の置き場が2説ある

- `docs/ai/roles/coordinator.md:80`
  > やらないと決めたことは `docs/ai/status.md`「載せていないもの」が持つ。
- `docs/ai/memory-classification.md:121`
  > 判断はそこへ書かず、行き先を指す — やることは`docs/ai/status.md`、やらないことは`docs/ai/memory/decisions/rejected-proposals.md`、原因の断定は`docs/ai/memory/decisions/`の個別ファイル。

現物は後者を支持する: `docs/ai/status.md`に「載せていないもの」節は存在せず(見出しは「このファイルの規律」「Now」「Next」×2のみ)、commit `a830672`「status: 退けた提案22件をdecisions/へ移し、statusを現在地だけにする」で`docs/ai/memory/decisions/rejected-proposals.md`(実在)へ移設済みである。coordinator.mdの指示は移設に追随していない(参照切れとしては2-1に再掲)。

### 1-4. code-delivery-to-production.md が「値を写さない」と宣言した同じ文書内に、timer間隔とschedule時刻の実値を写している

- `docs/ai/context/operations/code-delivery-to-production.md:7`
  > 値(timer間隔、閾値、パス)はここに写さない。正本は `roles/worktree_sync/defaults/main.yml` と各roleのdefaults。
- 同 `:50`
  > | 4 | quoryが作業ツリーをpull(1分間隔)。…
- 同 `:119`
  > `playbooks/deployment_drift_check.yml`(`safe-readonly`、日次 00:40)が**自動で突合する**。
- 同 `:179`
  > **この抑止は1分間隔のtimerに対する設計である。**

自文書の冒頭宣言と本文が両立しない。値そのものは現在の実装と一致している(`roles/worktree_sync/defaults/main.yml` の `worktree_sync_schedule: "*:*:00"`、`roles/semaphore_templates/defaults/main.yml:701` の `cron: "40 0 * * *"`)ため、現時点の食い違いではなく、片方だけが直る経路の問題である(3-3参照)。

### 1-5. system/semaphore.md が、context-classification.md §3.2 が「実値を書かない」と定める種類の値(バージョン・インスタンスid)を記載している

- `docs/ai/context-classification.md:60`
  > 秘密情報でなくても、次の値の**実値**をContext・Policy・Skillへ書かない。値そのものではなく正本へのポインタを書く。
  (同:65 の表に「ソフトウェアのバージョン、リリース番号 | 対象host上の実測値、またはrole defaults / vars」)
- `docs/ai/context/system/semaphore.md:29`
  > **id は異なる**(2026-08-18時点で ansy=3 / quory=1。ansy は 2026-08-04 の実測では 2 で、**その後変わっている**)。**id を固定値として扱わない。この行の値も、読んだ時点で古い可能性がある。**
- 同 `:49`
  > ansy / quory ともSemaphoreのバージョンとサービス実行ユーザーは一致している(**2026-08-18に両方を 2.19.8 へ上げた**。…)

semaphore.md自身が「古い可能性がある」と自己申告しつつ実値を保持しており、分類規則の側(書かない)と実践の側(書いて注記する)が両立していない。実際にこの形の値が古びた実例が3-2にある。

## 2. 宙ぶらりん参照

### 2-1. `docs/ai/status.md`「載せていないもの」節への参照3箇所 — 節が存在しない

参照元3箇所:

- `docs/ai/roles/coordinator.md:80`
  > やらないと決めたことは `docs/ai/status.md`「載せていないもの」が持つ。
- `docs/ai/context/operations/sandbox-vm.md:7`
  > 採らないと決めた案の一覧は [`docs/ai/status.md`](../../status.md)「載せていないもの」が持つ。
- `docs/ai/context/operations/code-delivery-to-production.md:141`
  > **この排他を外さないことは2026-08-05に決定済みである**(現状維持。`docs/ai/status.md`「載せていないもの」)。

現在の`docs/ai/status.md`(94行)の見出しは「このファイルの規律」「Now(進行中)」「Next(着手候補)— 工程・体制」「Next(着手候補)— システム・運用」のみで、「載せていないもの」節は無い。内容はcommit `a830672` で `docs/ai/memory/decisions/rejected-proposals.md` へ移設されており、3箇所とも移設先へ追随していない。

### 2-2. grafana-alerting-tuning.md が「monnieは非冪等操作でも確認不要」の決定の所在としてcoordinator.mdを指すが、coordinator.mdに該当記述が無い

- `docs/ai/context/operations/grafana-alerting-tuning.md:52`
  > 対象ホストは `monnie`(Prometheus)。**read-onlyの参照であり、Yoshinobuの確認を要さない**(2026-07-30、`monnie`は非冪等操作でも確認不要と決定済み。`docs/ai/roles/coordinator.md`)。
- `docs/ai/roles/coordinator.md:76`
  > **正本は [`docs/ai/policies/execution_boundary_policy.md`](../policies/execution_boundary_policy.md) である。** 承認区分、ホストの区分、状態を変えない確認の扱い、Roleごとの実行可否は、すべてそちらが定める。**値も表も、ここへ写さない。**

coordinator.mdに`monnie`への言及は無い(grepで0件)。ホスト区分の現行正本は`docs/ai/policies/execution_boundary_policy.md`(EXEC-010の表:53に`monnie`が「それ以外」= 確認不要側で載る)であり、参照先の指し直しが行われていない。

### 2-3. role-context-matrix.md が progress.md 撤廃の典拠としてcoordinator.mdを指すが、coordinator.mdに該当記述が無い

- `docs/ai/role-context-matrix.md:42`
  > `progress.md` は必須成果物から撤廃した(`docs/ai/roles/coordinator.md`)。
- `docs/ai/roles/coordinator.md` — `progress` の語は全文に存在しない(grepで0件)。

撤廃の事実そのものは他の記録と整合するが、典拠として指された文書が該当内容を持たず、読者は撤廃の根拠へ辿り着けない。

## 3. 正本の二重化

### 3-1. 自動muteのTTL表が実装と食い違っている(6行中4行)

`docs/ai/context/operations/autonomous-recovery.md:28` は
> 自動mute対象とTTLの具体値は各呼出playbook / role varsを正本とする。

と宣言した直後の:30〜39で「現行の横断契約」としてTTL実値の表を持つ。表と実装の突合:

| 表の行(doc:line) | 表のTTL | 実装 | 実装のTTL |
|---|---:|---|---:|
| `proxmox_evacuate_node.yml`(:34) | 120分 | `playbooks/proxmox_evacuate_node.yml:40,48,56` | 120 ✓ |
| `proxmox_patch_apply_node.yml`(:35) | **60分** | `playbooks/proxmox_patch_apply_node.yml:44,52,60`(`recovery_mute_minutes: 120`) | **120** ✗ |
| `proxmox_restore_vm_placement.yml`(:36) | **90分** | `playbooks/proxmox_restore_vm_placement.yml:43,51,59`(同120) | **120** ✗ |
| `ubuntu_nightly.yml`(:37) | **30分** | `playbooks/ubuntu_nightly.yml:122,408`(同120) | **120** ✗ |
| `proxmox_patch_weekly_full.yml`(:38) | 360分 | `playbooks/proxmox_patch_weekly_full.yml:515,523,531` | 360 ✓ |
| `ubuntu_vm_full_upgrade.yml`(:39) | **45分** | `roles/ubuntu_vm_full_upgrade/tasks/apply.yml:64`(`recovery_mute_minutes: 120`) | **120** ✗ |

正本を別に指した上で実値の表を複製した結果、playbook側だけが直り表が取り残されている。

### 3-2. ansyのSemaphore project idが2文書で食い違っている

- `docs/ai/context/operations/semaphore-db-restore.md:39`(2026-08-17作成)
  > 対象ホストに既に別の Semaphore project(例: ansy 自身の project id=2)が存在する場合、
- `docs/ai/context/system/semaphore.md:29`(2026-08-18更新)
  > **id は異なる**(2026-08-18時点で ansy=3 / quory=1。ansy は 2026-08-04 の実測では 2 で、**その後変わっている**)。

同じ値が2箇所に書かれ、semaphore.md側だけが更新された。semaphore.md自身が「idを固定値として扱わない」と警告する値を、semaphore-db-restore.mdは例示として保持し続けている。

### 3-3. 実装側に正本がある値・一覧の複製(現在は一致しているが、片方だけが直る経路がある)

いずれも現物と突き合わせて現時点の一致は確認済み。将来は実装側だけが直り得る。

- **dispatchの調査コマンド本数**: `docs/ai/context/operations/operator-request-channel.md:137`「止まるのは追加したchannel操作だけで、**既存の25本の read-only 調査は動き続ける**」/ 同:53「dispatcherへ足したchannel操作4本」。実物 `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh` のcase labelはread-only系25本+`operator-*`4本(一致)。本数は列挙の追加(例: 2026-08-25の`acl-status`エントリ拡張のような改修)で変わる。
- **deployed-hash対応表の9件列挙**: `docs/ai/context/operations/code-delivery-to-production.md:102`「対応表にあるのは `recovery-probe` / … / `investigate-dispatch-quory` の9件」。実物は同dispatch script `deployed-hash)` caseの9エントリ(一致)。
- **retry既定値**: `docs/ai/context/operations/proxmox-operations.md:65`「role defaultsはそれぞれ`2`と`60`である。現在値の正本はrole defaultsとする」。実物 `roles/proxmox_patch_apply_node/defaults/main.yml:59-60`(一致)。「正本はrole defaults」と指しながら実値も併記している。
- **cert-renew-quoryの時刻**: `docs/ai/context/operations/ubuntu-vm-patch.md:78`「月初00:35」。実物 `roles/systemd_timers/defaults/main.yml` の `schedule: "*-*-01 00:35:00"`(一致)。context-classification.md:64はschedule実値の記載自体を禁じている。
- **timer間隔・ドリフト検査時刻**: 1-4に記載(1分間隔・日次00:40。いずれも実装と一致)。

## 4. 読み取れない箇所

### 4-1. 「009 investigationを参照する」— どのファイルか本文から特定できない

- `docs/ai/context/operations/autonomous-recovery.md:79`
  > 実装・導入の時点履歴と2026-07-05のtester教訓は009 investigationを参照する。

パスも案件フォルダ名も無い。`docs/ai/context/system/autonomous-recovery.md:66` が同じ対象をフルパス(`docs/ai/reviews/policy_standardization/2026-07-24_009_investigation_autonomous_recovery_policy_rewrite.md`、実在)で参照しており、そこを経由しないと解決できない。

### 4-2. 「TODO 7-2(pilot1)・pilot2」— 識別子の所在が示されていない

- `docs/ai/context/operations/healthcheck.md:49`
  > TODO 7-2(pilot1)・pilot2で、コメントの理由文と実guardが乖離する“marker drift”が実際に見つかった。
  (同:57 にも「TODO 7-2で見つかり、pilot2(`monitoring_healthcheck`)でも再発しないか確認済み」)

「TODO 7-2」「pilot1」「pilot2」がどの案件記録のどの項目かを指す情報が文書内に無く、何の事実の記録かを本文から再構成できない(リポジトリ全文検索では`docs/ai/reviews/agent_skills_reorganization_phase7_*`に関連記述があるが、読者にその導線は与えられていない)。

## 5. 群固有: 分類の越境

### 5-1. healthcheck.md(Operations Context)が「リポジトリ全体に適用される規範の正本」を自認している

- `docs/ai/context/operations/healthcheck.md:4`
  > 更新: 2026-07-26。旧`docs/ai/prompts/core.md` §7・§17のshell責務規範を移設し、**§1はリポジトリ全体に適用される正本**となった。
  (同:6「§1「shell / Ansible責務分離」は、healthcheck系に限らず**shellを使う全roleに適用される規範**である」、同:16「**変更操作**(check系shellへ変更を伴う操作を一切入れない)」ほか禁止列挙)
- `docs/ai/context-classification.md:33`
  > **対象**: 「何をしてよいか・してはいけないかの判断基準」— Context(事実)と違い、Policyは規範(ルール)。

「してはいけない」の列挙を正本として持つ文書がContext分類に置かれており、分類定義と両立しない。`docs/ai/core.md:109` もこの節を規範の根拠として参照している(「check系shellは観測に留め、判定・分類・通知・保存をshellへ持たせない(`docs/ai/context/operations/healthcheck.md`)」)ため、事実上のPolicyがContextの住所に住んでいる形になっている。

### 5-2. agent-messaging.md — 「非規範runbook」を名乗る文書が、禁止・承認条件・「要件の正本」を持つ

- `docs/ai/context/operations/agent-messaging.md:7`
  > 本書は、Coordinator(Claude Code)を起点とする agmsg の連絡経路を扱う**非規範runbook**である。
- 同 `:13`「**この team は local-only であり、remote 化しない**」(禁止)
- 同 `:101`「**送るものは Yoshinobu が選ぶ。** cross-team(`homelab-ops`)への送信は、**送る文面を提示して同意を得てから**行う。」(承認条件)
- 同 `:188`「**したがって、この節が要件の正本である。** スクリプトを書き直すときはここへ突き合わせる。」(要件の正本宣言)

自己宣言(非規範)と内容(禁止・承認・要件正本)が両立しない。さらに `docs/ai/roles/operator.md:11` は「経路の性質は `docs/ai/context/operations/agent-messaging.md` §7〜§9 が正本」と、背骨側からこのContextを正本として指しており、越境が参照によって固定されている。

### 5-3. system/semaphore.md(System Context)に禁止・義務が書かれている

- `docs/ai/context/system/semaphore.md:34`「**鍵を再登録しない。**」
- 同 `:36`「**quory 側の鍵を、ansy と同じ判断で消してはならない。**」
- 同 `:20`「**時刻を提案・変更するときは、その表に照らしてもらうこと。**」
- 同 `:21`「**scheduleを追加・変更したら、同じ表へも反映する。**」

`docs/ai/context-classification.md:9` はSystem Contextの対象を「「このシステムが何であるか」…実環境についての知識」と定める。上記は許可・禁止・手順義務であり、分類定義上はPolicy側の内容である。

### 5-4. Operations Contextの禁止・義務(その他の明確な箇所)

- `docs/ai/context/operations/operator-request-channel.md:135`「**channelを止める目的で、既存の鍵やauthorized_keysを消してはならない。**」
- 同 `:95`「**したがって、rulesetを変える者は毎回こうする。** ①…⑤…。**①〜③を飛ばすと、読まれないまま取得不能になるmessageが出る。**」(手順義務)
- `docs/ai/context/operations/sandbox-vm.md:18`「**恒久的な開発環境をここへ作らない。**」
- 同 `:80`「**黙って直そうとせず、壊したと報告する。**」

いずれも位置づけ節で「非規範」を宣言した文書(operator-request-channel.mdは宣言なしだがOperations Context)内の禁止・義務であり、context-classification.md:37「「これをしてよいか」を答える文書はPolicy」との整合が取れていない。

### 5-5. roles/operator.md(背骨)に環境の変化する状態が記録されている

- `docs/ai/roles/operator.md:7-13`(「## 現在の状態」節)
  > Operator Request Channelを介したOPREQの受領、OPRESの返却およびDEVREQの作成は実装済みである。…**済んでいるのは上の2つ(Request Channel と agmsg)だけである。** 本番調査、Semaphore操作、サービス操作、リカバリを含むそれ以外の責務・権限・安全制約は設計中であり、
- `docs/ai/core.md:11`
  > `docs/ai/status.md` は**現在地**(進行中の作業、観測待ち、着手候補)の正本とする。規範は書かない。

「実装済み/設計中」はrepoの現物で真偽が変わる現在地であり、Role文書(責任・権限・成果物・禁止事項の正本、core.md:12)に置くと実装が進むたびにRole文書側だけが古びる。権限を能力の実装状況で縛る意図は読み取れるが、状態の正本(status.md)との棲み分けは書かれていない。

## 未確認(解釈に確信が持てない・repoから確かめきれない)

- **overview.mdとsemaphore.mdのansy側Semaphoreの性格づけ**: `docs/ai/context/system/overview.md:15` は `semaphore_servers` の `ansy` を「開発側・本番側のSemaphore実行環境」とするが、`docs/ai/context/system/semaphore.md:32` は「このインスタンスは、どのホストへも到達できず、リポジトリを clone することもできない」(鍵なしの検証用)とする。「実行環境」と「実行能力なしの検証用インスタンス」は矛盾とも、粒度の違いとも読める。断定しない。
- **CLAUDE.md:6 の「承認境界…はここにしか無い」**: coordinator.md:76 は承認境界の正本を `execution_boundary_policy.md` と定め「値も表も、ここへ写さない」と述べる。CLAUDE.mdの括弧書き(「着手前の報告の型、承認境界、起動できるRoleとモデル配分、`docs/ai/status.md`の維持はここにしか無い」)が「Coordinator固有の承認作法」を指す意図なら矛盾ではない。文面上は両立しないが、意図の解釈が割れるため本文へ入れない。
- **grafana-alerting-tuning.md:48-52 の手順1(AIがmonnieのPrometheusをrange queryで引く)の実行経路**: `execution_boundary_policy.md` v1.1(2026-08-19)で ansy→monnie の鍵(`id_ann`)は削除済みであり、repo内のdispatch(`roles/dev_investigate`、25本)にPrometheus queryの語彙は無い。同Policy:21の「読み取り専用の名前付きチェックは `monnie-investigate` で今も通る」の実体はホスト側設定でrepoから語彙を確認できず、この手順が現在も記載どおり実行可能かは確認できなかった。

---

集計: 矛盾5件 / 宙ぶらりん参照3件(うち1件は3箇所同根)/ 正本の二重化3件(うち1件は実値4箇所の食い違いを含む)/ 読み取れない箇所2件 / 分類の越境5件 / 未確認3件。
