# Group B 実装記録(2026-08-25)

対象: `2026-08-25_004_fix_scope.md`「Group B: context + skills + agents + 分類3本 + coordinator.md」表の22項目。coordinator.md自体はGroup Aが担当するため、C1-3/C2-1のうちsandbox-vm.mdとcode-delivery-to-production.mdの2箇所のみ本記録で扱う。

## 変更ファイル一覧

- `docs/ai/context-classification.md`
- `docs/ai/context/operations/ubuntu-vm-patch.md`
- `docs/ai/context/operations/code-delivery-to-production.md`
- `docs/ai/context/operations/sandbox-vm.md`
- `docs/ai/context/operations/autonomous-recovery.md`
- `docs/ai/context/operations/semaphore-db-restore.md`
- `docs/ai/context/operations/grafana-alerting-tuning.md`
- `docs/ai/context/operations/healthcheck.md`
- `docs/ai/context/system/semaphore.md`
- `docs/ai/role-context-matrix.md`
- `docs/ai/memory-classification.md`
- `skills/subagent-briefing/SKILL.md`
- `skills/architecture-decision-record/SKILL.md`
- `skills/incident-recording/SKILL.md`
- `skills/goal-tracking/SKILL.md`
- `skills/test-strategy/SKILL.md`
- `.claude/agents/auditor.md`
- `.claude/agents/implementer.md`
- `.claude/agents/reviewer.md`
- `.claude/agents/tester.md`

frontmatter(`model:`/`effort:`/description)はいずれも未変更。skillsのdescriptionも未変更。

## 項目ごとの充足

| 項目 | 対応 | 参照先の実在確認 |
|---|---|---|
| C1-1 | ubuntu-vm-patch.md:78・context-classification.md:64の「Semaphore UI」正本宣言を`roles/systemd_timers`(timer)・`roles/semaphore_templates/defaults/main.yml`(カタログ)へ差し替え | 両ファイルとも実在確認済み |
| C1-2 | ubuntu-vm-patch.md:78の「現在唯一有効なsystemd timer」を`roles/systemd_timers`カタログ上の限定に書き換え、月初00:35の時刻実値を除去 | 同上 |
| C1-3/C2-1 | sandbox-vm.md:7、code-delivery-to-production.md:141の「`docs/ai/status.md`「載せていないもの」」参照を`docs/ai/memory/decisions/rejected-proposals.md`へ差し替え | `ls`で実在確認済み。相対リンクパス(`../../memory/decisions/rejected-proposals.md`)も確認 |
| C1-4 | code-delivery-to-production.md:50(1分間隔)、:119(日次00:40)、:179(1分間隔)の実値を`roles/worktree_sync/defaults/main.yml`・`roles/semaphore_templates/defaults/main.yml`の`semaphore_schedules_catalog`へのポインタへ差し替え | grepで`worktree_sync_schedule`(:52)、`semaphore_schedules_catalog`内の`deployment_drift_check`エントリ(cron `"40 0 * * *"`)を確認済み |
| C1-5 | system/semaphore.md:29(project id 3/1)、:49(バージョン2.19.8)の実値を除去し、「idは両インスタンスで異なり変わったことがある。固定値として扱わず都度実測する」「バージョンとサービス実行ユーザーは両インスタンスで一致させる」という不変の意味論を残した | 同ファイル内:48/:71/:73に残る「2.19.8」は過去の移行理由・出力形式例・実施済み検証の記録であり、現在値の主張ではないため対象外と判断(下記「scope外」参照) |
| C2-2 | grafana-alerting-tuning.md:52の決定所在を`docs/ai/roles/coordinator.md`→`docs/ai/policies/execution_boundary_policy.md`(EXEC-010)へ | EXEC-010の表(:53、「それ以外」= `monnie`/`ansy`/`sandbox`、確認不要側)を確認済み |
| C2-3 | role-context-matrix.md:42の「(docs/ai/roles/coordinator.md)」典拠を除去 | coordinator.mdに`progress`の語が無いことを確認済み(finding記載どおり) |
| C3-1 | autonomous-recovery.md(operations):30-39のTTL表を削除し、`autonomous_recovery_policy.md`AR-077(横断契約)へのポインタへ置換。表中の個別分数値は本文へ再掲しない | AR-077のコメント行が現在:118にあることを確認(fix_scope記載の:119-121とほぼ一致、行ずれは監査後の別編集による) |
| C3-2 | semaphore-db-restore.md:39の「project id=2」例示を除去し、system/semaphore.mdへのポインタへ | 同上C1-5の修正後の記述と整合 |
| C4-1 | autonomous-recovery.md(operations):79の「009 investigation」に実パスを付与 | `docs/ai/reviews/policy_standardization/2026-07-24_009_investigation_autonomous_recovery_policy_rewrite.md`の実在を`ls`で確認 |
| C4-2 | healthcheck.md:49,:57の「TODO 7-2」「pilot2」に実パスを付与 | `docs/ai/reviews/agent_skills_reorganization_todo7-2_result.md`、`docs/ai/reviews/agent_skills_reorganization_phase7_pilot2_setup.md`の実在を`ls`で確認。「pilot1」自体へのパス付与はfix_scopeの指定に含まれないため据え置いた |
| S1-1 | subagent-briefing:26から未追跡ファイル・git操作の複製2項目を除去し、「各subagentが触れてよいパス」だけを「書くもの」に残した | — |
| S1-2 | architecture-decision-record:40「新設予定の`docs/ai/adr/`」→「`docs/ai/adr/`」 | `docs/ai/adr/`に001〜010が実在することを確認済み |
| S1-3/S3-2 | incident-recording「運用ルール」節(:54-59)の規則本文複製を、memory-classification「3. 昇格・廃止ルール」「月次振り返りの対象と手順」へのポインタ1行へ置換 | 両見出しの実在を確認済み。descriptionの「型のみ定める」と本文が整合する状態になった |
| S1-4 | role-context-matrix.md:38「次の4つに限る」→「次に限る」 | 直後の表が3行であることを確認済み(数の宣言を落としたため不一致は解消) |
| S2-1 | subagent-briefing:8「下記「参照」」を、存在しない節を指さない文言(「各章が個別に指す正本」)へ置換 | — |
| S2-2 | goal-tracking:18の旧core.md「on the horizon」参照を除去 | `grep -n "on the horizon" docs/ai/core.md`が0件であることを確認済み(除去後、参照先不在の言及自体が無い) |
| S3-1 | subagent-briefing:73のcore.md逐語再掲(「実効的な境界は文章ではなく…」)をポインタへ置換 | core.md:39/:143の文言を複製せず、正本の節名参照に差し替えたことを確認 |
| S4-1 | subagent-briefing:75見出し「AC1対応表」→「過去の逸脱3クラスとの対応」。表ヘッダ列も「AC1のクラス」→「逸脱のクラス」に合わせた | 表本文の①②③行はAC1識別子を使っていないため変更不要と確認 |
| S5-1 | test-strategy:26-27の実行ユーザー名(`ann`/`yoshi`)・sandbox構成を「ホームラボ固有の補足」節へ分離し、汎用部分(temp path分離の一般原則)から切り離した | context-classification.md §4の例外条件文言(:73-78)を確認し、節見出しをその表現に合わせた |
| S5-3 | `.claude/agents/`4定義から「会話の過程は永続しない」「最終メッセージは記録として残らない」の複製文を除去し、正本ポインタ+成果物ファイル名対応のみへ縮約 | coordinator.md:39「bodyに置いてよいのは正本へのポインタと成果物ファイル名対応だけ」との整合を確認。frontmatterは未変更 |
| memory-classification | :5「## 1. 4層モデル」→「## 1. 層モデル」 | `grep -n "4層" docs/ai/memory-classification.md`が0件になったことを確認(自文書内の被参照が消えたことの確認) |

## 自己検証の結果

- 22項目すべてについて、修正後の文が指す参照先(ファイル・節・パス)の実在を上表のとおり個別に確認した。
- `python3 scripts/check-doc-consistency.py` は3チェックとも `OK`(check1: 114件比較、check2: 8件比較、check3: 102件比較)。
- `.claude/skills/` 配下の相対symlinkについて `test -e` で全件到達可能を確認し、壊れているものは無かった(本タスクではskillsの中身のみ変更しファイル移動は行っていないため symlink自体には影響しない設計だが、明示的に確認した)。
- `git diff -U0` で今回の差分に追加されたIPv4リテラルが無いことを確認した(ループバック/ワイルドカード/ブロードキャスト以外はゼロ件)。
- 落とした実値・除去した参照が同一文書内の他箇所に残っていないか、各対象ファイルをgrepで確認した。system/semaphore.mdの「2.19.8」「project id」の残存(:48,:71,:73)は、C1-5が対象とした「現在値の主張」ではなく過去の移行理由・出力形式例・実施済み検証の記録であるため、意図的に残置した(下記「scope外と判断したもの」参照)。

## scope外と判断して触れなかったもの

- `docs/ai/context/system/semaphore.md:48`(「2.19.8 で `semaphore.db` の直読みが壊れた」)、`:71`(バージョン出力形式の例`2.19.8-3449a04-...`)、`:73`(「両ホスト・両版(2.18.4 / 2.19.8)で…照合して確定した」)——finding 1-5/3-2が指摘したのは:29(project id)と:49(現在バージョンの宣言)であり、これらは過去の事象・出力例・実施済み検証の記録であって「現在値」の主張ではないため、C1-5のscopeに含めず変更しなかった。
- `docs/ai/context/operations/code-delivery-to-production.md:53`(「翌00:40の日次ドリフト検査」)——fix_scope C1-4が明示した対象は:50,:119,:179の3箇所のみで、:53はfindings文書でも実値違反として引用されていない。同一事実を指す重複箇所だが、scope表に無い修正として据え置いた。
- 同ファイル:183(「5分間隔前提の「3回」を1分間隔へ移すと3分で発火し」)——過去の実装時に発見された具体的事象の記録であり、現在値の主張ではないため対象外。
- healthcheck.md:49の「(pilot1)」自体へのパス付与——fix_scopeが指定したのは「TODO 7-2」と「pilot2」の2語のみで、「pilot1」への直接のパス付与は含まれていない。TODO 7-2のパスと併記される形で文脈上は解決している。

## 未解決事項

- なし。scope表22項目はすべて対応済みで、実行ホストへの到達・git add/commit/pushは行っていない。
