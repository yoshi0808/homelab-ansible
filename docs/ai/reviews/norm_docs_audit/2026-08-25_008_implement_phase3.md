# 第2束フェーズ3(分類の越境5件)実装記録(2026-08-25)

対象: `2026-08-25_004_fix_scope.md`「第2束」「3. 越境5件」節(前提A案 + C5-1〜C5-5)。観測事実は`2026-08-25_002_findings_context.md`「5. 群固有: 分類の越境」。移設先は同fix_scope文書でYoshinobuと合意済みであり、本記録は決定の変更・拡大を行わない。

## 変更ファイル一覧

- `docs/ai/context-classification.md`
- `docs/ai/context/operations/agent-messaging.md`
- `docs/ai/context/operations/sandbox-vm.md`
- `docs/ai/context/operations/healthcheck.md`
- `docs/ai/context/system/semaphore.md`
- `docs/ai/context/system/overview.md`
- `skills/ansible-implementation-style/SKILL.md`
- `docs/ai/core.md`
- `docs/ai/roles/operator.md`
- `roles/semaphore_templates/defaults/main.yml`(コメント行のみ)

`docs/ai/context/operations/operator-request-channel.md`は調査の結果、変更不要と判断し触れていない(下記「作業単位2」参照)。

## 作業単位ごとの充足

### 1. 前提(A案)

`context-classification.md`「Operations Context」の「作成条件」直後に「Policyとの境界」を新設し、「Operations Contextのrunbookは、その手順に閉じた禁止・義務を持ってよい。ただし安全境界・承認・ホスト区分に触れる規範は対象がOperations Contextであっても正本にせず、Policyへ置く」の線を既存の分類定義(「対象」「例」「書かないもの」「作成条件」の書きぶり)に合わせて追加した。

### 2. C5-2/C5-4(agent-messaging.md / operator-request-channel.md / sandbox-vm.md)

- `agent-messaging.md:7`と`sandbox-vm.md:7`の「非規範runbook」自己宣言を、1で新設した分類の境界へのポインタ付き文言(「runbookである。禁止・義務はこの経路/このVMの手順に閉じる」)へ置き換えた。両文書の禁止・義務(team local-only、送信前の同意取得、鍵を消してはならない、恒久環境を作らない等)はいずれも当該runbookの手順に閉じており、1の新しい線の下で正当な内容と判断した。安全境界・承認・ホスト区分そのものを新設・変更している箇所は無く、Policyへの移設対象は見つからなかった。
- `operator-request-channel.md`は「非規範」を自己宣言しておらず(grep 0件)、finding 5-4が指摘したのは「Operations Contextであるにもかかわらず禁止・義務を持つこと」自体であって自己宣言との矛盾ではない。1の新設により、同文書の禁止・義務(チャンネル停止時に既存鍵を消してはならない、ruleset変更時の①〜⑤手順等)はすべて経路の手順に閉じた内容として分類上正当になったため、本文書は変更していない。

### 3. C5-1(healthcheck.md §1 → SKILL.md)

- `healthcheck.md` §1の本文(shell/Ansible責務分離の禁止列挙、責務分離図、補足3点、`proxmox_snapshot_check`の実装例)を`skills/ansible-implementation-style/SKILL.md`「Shell」節の下に「check系shellの責務分離」小節として新設し、そのまま移設した。移設に伴い「旧core.md §7・§17から移設した詳細である(2026-07-26、移行表C07-01/C07-02)」という経緯注記は落とした(規範文書には指示だけを書く)。
- `healthcheck.md`側は「作成日/更新」欄に2026-08-25の再移設を1行で記録し、「§1はリポジトリ全体に適用される正本」の自認を除去した。§1本体は「規範の正本は`skills/ansible-implementation-style/SKILL.md`「check系shellの責務分離」である」という1文のポインタへ縮約した。
- `core.md:109`の「check系shellは観測に留め…」行のポインタを`docs/ai/context/operations/healthcheck.md`から`skills/ansible-implementation-style/SKILL.md`「check系shellの責務分離」へ付け替えた。
- `context-classification.md:27`の「例」記述から、healthcheck.mdの内容説明として残っていた「shell/Ansible責務分離」を落とした(healthcheck.md自身がもう正本でないため)。
- 他の規範文書からhealthcheck.mdを同規範の正本として指す箇所を`docs/ai/core.md` `docs/ai/roles` `docs/ai/policies` `docs/ai/context` `docs/ai/context-classification.md` `docs/ai/role-context-matrix.md` `docs/ai/memory-classification.md` `skills` `.claude`全体でgrepした。`docs/ai/policies/time_sync_check_policy.md:147`(TIME-010)が同規範をhealthcheck.mdへの参照で指しており未対応(下記「未解決事項」)。同ファイル:159(TIME-020、severity/fail別軸の慣習)はhealthcheck.md §2を指しており、§2は移設対象外のため対応不要と判断した。

### 4. C5-3(system/semaphore.mdの禁止・義務)

- `semaphore.md`の「鍵を再登録しない」を`docs/ai/policies/execution_boundary_policy.md`(EXEC-052、Testerが使ってよい検証環境の表に同文言が既にある)へのポインタへ、「quory側の鍵を、ansyと同じ判断で消してはならない」をEXEC-005へのポインタへそれぞれ置換した(規範本文の複製を解消)。
- 「時刻を提案・変更するときは表に照らす」「scheduleを変えたら表へ反映する」の2つの義務を`roles/semaphore_templates/defaults/main.yml`の`semaphore_schedules_catalog`直前へ、既存ヘッダコメントの書式(見出し行・太字強調・日付付き実例)に合わせて移設した。`semaphore.md`側は該当箇所を「義務の正本は`semaphore_schedules_catalog`ヘッダコメントを正本とする」という1文へ置換し、定期実行の窓が他システムにも広がっているという事実(UniFi/Proxmox/systemd timer/unattended-upgrades)と「バッチ処理工程管理表」の所在の事実は System Context の記述としてそのまま残した。

### 5. C5-5(roles/operator.md「現在の状態」節)

見出しを「現在の状態」から「権限の範囲」へ変え、OPREQ/OPRES/DEVREQ実装済み・agmsg開通済み・それ以外は設計中、という個別の実装状況の列挙を削除した。代わりに「本Roleの権限は実装済みの能力に限る。実装状況の正本はrepoの現物(対象Role・Policy・実効権限)と`docs/ai/status.md`である」という規則と、「経路が開通していることは、その経路が運ぶ内容についての権限を認めることの根拠にならない」という一般規則を書いた。agmsgが権限を運ばないことは例として1文だけ残し、詳細規定への複製はしていない(正本は引き続き`agent-messaging.md` §7〜§9)。

### 6. 巻き取り(overview.mdの未確認1件)

`overview.md`のノード役割表、`semaphore_servers`行の説明を「開発側・本番側のSemaphore実行環境」から「`quory`は本番実行基盤。`ansy`は鍵を持たずどのホストへも到達できない検証用インスタンス。詳細は`docs/ai/context/system/semaphore.md`」へ書き換えた。`semaphore.md`が定める性格(鍵なし、どのホストへも到達不能、cloneも不可)と矛盾しない記述にし、詳細はsemaphore.mdへ委譲した。

## 自己検証の結果

- 移設した規範本文(healthcheck.md §1、semaphore.mdの鍵2文・schedule義務2文)は、移設先(SKILL.md、EXEC-052/EXEC-005、`semaphore_schedules_catalog`ヘッダ)に1箇所だけ存在することを、移設元の該当箇所をポインタへ置換した差分と、移設先への新規追加差分を突き合わせて確認した。二重化は残っていない。
- ポインタ・参照先の実在確認: `skills/ansible-implementation-style/SKILL.md`「check系shellの責務分離」(本作業で新設)、`execution_boundary_policy.md`のEXEC-052(:111)・EXEC-005(:35、いずれも`<!-- EXEC-XXX -->`マーカーで実在確認)、`roles/semaphore_templates/defaults/main.yml`の`semaphore_schedules_catalog`(:684、本作業でヘッダ追加)、`docs/ai/status.md`(実在確認)、`docs/ai/context/system/semaphore.md`(overview.mdの参照先、実在確認)。
- 旧参照の掃引: healthcheck.md §1を規範として指す箇所を`docs/ai/core.md` `docs/ai/roles` `docs/ai/policies` `docs/ai/context` `docs/ai/context-classification.md` `docs/ai/role-context-matrix.md` `docs/ai/memory-classification.md` `skills` `.claude`でgrepし、`docs/ai/policies/time_sync_check_policy.md:147`(TIME-010)の1件を検出した。変更してよいファイルにPolicyが含まれないため未対応。他はすべて掃引済み(0件)。
- `python3 scripts/check-doc-consistency.py` は3チェックとも `OK`(check1: 114件比較、check2: 8件比較、check3: 104件比較)。
- `roles/semaphore_templates/defaults/main.yml`は`yaml.safe_load`でパースし、`semaphore_schedules_catalog`が21件のまま(変更前と同数)であることを確認した。`git diff --unified=0`で今回の差分行がすべて`#`始まりのコメント追加であることを確認し、データ構造・値への変更が無いことを確認した。
- `.claude/skills/`配下の全symlinkについて`test -e`相当の到達確認を行い、壊れているものは無かった(`ansible-implementation-style`を含む)。
- `git diff --name-only`が変更してよいファイル一覧と一致することを確認した。`git diff`差分にIPv4リテラルが含まれないことを確認した(ループバック/ワイルドカード/ブロードキャスト以外はゼロ件)。
- 実ホストへのansible・ssh実行、git add/commit/pushは行っていない。

## 未解決事項

- `docs/ai/policies/time_sync_check_policy.md:147`(TIME-010)が、healthcheck.md §1が保持していた「shell/Ansible責務分離」規範への参照を`docs/ai/context/operations/healthcheck.md`のまま持っている。healthcheck.md §1は今回`skills/ansible-implementation-style/SKILL.md`「check系shellの責務分離」へのポインタに変わったため、TIME-010の参照は依然として正しい規範へ到達できる(healthcheck.md §1経由の1段階の間接参照)が、直接指してはいない。`docs/ai/policies/`は本依頼の「変更してよいファイル」に含まれないため修正していない。Coordinatorの判断でTIME-010の参照先を`skills/ansible-implementation-style/SKILL.md`「check系shellの責務分離」へ直接付け替えることを推奨する。
