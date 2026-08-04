# Review: 蒸留内容(I1/S1/R1/R2/T1/T2/A1/C1)の正確性と、Knowledge非読の下での欠落

対象: `docs/ai/reviews/knowledge_delivery_and_core_compression/2026-08-05_001_analysis.md` §2、`2026-08-05_002_implement.md`、および `git diff`(未commit)のうち I1/S1/R1/R2/T1/T2/A1/C1。構造変更(節統合・参照健全性)は別Reviewerの担当のため見ていない。

## Summary

採用8件のうち7件(S1/R1/R2/T1/T2/A1/C1)は原資と照合して条件・限定の脱落なく正確に圧縮されている。**I1は1件、Critical。** `risk-accepted` と `--check` の関係について、core.mdが同じ文書内で正本と指す `docs/ai/policies/ansible_test_safety_policy.md`(TS-030)と矛盾する記述になっている。不採用14件は13件を独立に確認し同意、**1件(`rollback-cli-argument-convention`)は「領分」とした置き場に実体が無く、実質的な孤児化**。Knowledge非読化でImplementerが失うものとして、この1件を除き重大な欠落は見つからなかった。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `docs/ai/core.md` | decoy節(I1追加分) | **`risk-accepted` は `--check` を無効化する分類であるため、decoyと `--check` を重ねても本適用が走る」は、現行Policyと矛盾する。** `docs/ai/policies/ansible_test_safety_policy.md` L22「`risk-accepted`は...`--check`を渡された場合は適用せずに停止する(TS-030)」、L80「実際に変更を行う各playの`pre_tasks`に、`ansible_check_mode`が真なら停止するassertを置く」、L119「`risk-accepted`が停止assertを持つ(TS-030)ことは...lintで保証する」と正面から食い違う。**TS-030はI1の原資インシデント(`2026-07-31_subagent-unintended-deploy-risk-accepted-check.md`)と同日の`check_mode_semantics`案件で新設され、当該インシデントの構造的修正そのものである。** 現在repoに存在する`risk-accepted`3本(`proxmox_backup_restore_verify.yml`・`unifi_backup_fetch.yml`・`cloudkey_cert_deploy.yml`)は全て停止assertを実装済みで確認した。インシデントの対象だった`playbooks/incident_inspect_setup.yml`自体も、現在は`check-mode-native`へ再分類されている。**I1は「修正未実施」時点の状態を、修正後も変わらない分類の性質として書いている。** | Critical |

**残る正当な警告(I1が本来書くべきもの)**: lintは「assertが存在すること」しか検査せず、「変更を行う全playにassertがあること」(play単位の充足)は検査しない(Policy L119)。かつ**pre-commit lintが働くのはcommit時点であり、Implementerが自己検証している未commitの新規playbookには効かない**——これがまさに元インシデントの構造(新規playbook、`--check`を無効化する`check_mode: false`は入っていたが、停止assertがまだ無かった)。I1はこの残存条件を書くべきで、「分類そのものが`--check`を無効化する」という不正確な一般化ではなく、「停止assertの存在は前提にできない(特に自分がまだcommitしていない新規playbook)ので、decoyと`--check`だけで安全と判断しない」という形にすべきである。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `skills/ansible-implementation-style/SKILL.md` | — | 不採用リストの`rollback-cli-argument-convention`は「実装規約。`skills/ansible-implementation-style/SKILL.md`の領分」という理由で不採用にしているが、**実際には同SKILLに`rollback`の記述が1件も無い**(grep 0件)。判断軸2(既に正本があるか)は「正本がある」ことを前提にしており、実際には正本が空である。CLI引数規約(`-e rollback=true`/`-e rollback_to=X.Y.Z`、role内部への`<role>_rollback`マッピング、`-e`のコンマ区切り不可)は今後Implementerが手動適用/rollback系playbookを新規に書くたびに再現しうる具体的な落とし穴で、Knowledgeを読まなくなるとImplementerに渡す経路が無い。次のいずれかを推奨: (a) 本案件のスコープを広げてこの規約をSKILL本文へ実際に転記する、(b) 転記していないことをこの案件の申し送りとして明記し、月次振り返りまたは別案件へ引き継ぐ。**現状は「書いたつもり」の状態のまま放置されている。** | Gap |

## What Looks Good

- **S1**(core.md「安全機構がブロックしたとき」): `blocked-redesign-the-verification-not-the-route.md`の教訓(検証設計を組み替える第3の分岐、必ず報告する義務)を条件を落とさず反映している。「別の手段で同じ結果に到達する」ことと「結果を必要としない設計へ組み替える」ことの区別も保持されている。
- **R1**(reviewer.md、多層エスケープ/rc規約/`--check`非評価分岐): `multilayer-escaping-and-novel-stack-verification.md`項4の文言をほぼそのまま反映。分析が主張する「`code-review`/`ansible-security-review`両SKILLに1件も入っていない」を独立にgrepで再確認し、事実だった。置き場(Reviewer固有)も適切。
- **R2**(reviewer.md、無音化/例外吸収): `distinguish-nothing-found-from-not-run.md`と、根拠として引用されている3 Incident(`precommit-quotepath-bypass`、`incident-capture-spool-root-ownership`、`incident-investigate-callback-did-not-enqueue`)を全文照合した。fail-closedの既定、`rescue`/`failed_when: false`/`|| true`/空の早期returnの列挙は原資と一致し、条件の拡大・縮小は無い。
- **T1**(tester.md、`curl -v`等の禁止): `2026-08-04_ansy-semaphore-api-token-exposed-in-transcript.md`と一致。「露出先は成果物ファイルだけでなく自分のツール出力とtranscriptを含む」「`no_log`は手で叩く経路を守らない」の限定も保持されている。
- **T2**(tester.md、identity昇格禁止): `permission-boundaries-must-be-designed-not-prompted.md`教訓2・教訓3と一致。「正しいidentityを使っただけで迂回ではない、という整理でこれを越えない」という原資の核心(当時Testerが実際にした自己正当化の型そのものを名指しで塞ぐ)が保持されている。
- **A1**(auditor.md、転記先の実在): `2026-08-01_tester-slack-decoy-did-not-contain-request.md`の記述(2026-07-29のIncident2本が「起票した」と書きながら行が存在しなかった)と一致。既存の検査項目(反証の反映/受入条件の充足/未解決の明示/差分の外側の陳腐化)のどれにも重ならない新規の観点であることも確認した。
- **C1**(coordinator.md、無音化の合成判断): `distinguish-nothing-found-from-not-run.md`と`2026-07-27_incident-capture-spool-root-ownership.md`が明示的に「この問いは合成を見る立場(Coordinator、または全体を見る独立レビュー)が持つべき」と持ち主を名指ししている点を正確に引き継いでいる。
- 置き場の判定(全8件): I1/S1をcore.md、R1/R2をreviewer.md、T1/T2をtester.md、A1をauditor.md、C1をcoordinator.mdへ置く判断は、いずれも原資が名指しする主体・適用範囲と一致しており、Role文書とcore.mdの取り違えは無い。
- `docs/ai/memory-classification.md`・`docs/ai/role-context-matrix.md`のKnowledge参照範囲変更(①)は、変更後の文言が実際にsubagent非読・Coordinator限定を明記しており、宣言と内容の不一致は無い。

## 不採用14件の独立確認

| Lesson | 分析の理由 | 確認結果 | 根拠 |
|---|---|---|---|
| `acceptance-criteria-need-observable-success` | `skills/requirements-analysis/SKILL.md`へ昇格済み | **同意** | 同SKILL「『成功』の観測方法まで書く」節に、終了コード・通知・成果物・部分成功の4観点と根拠incidentが実在 |
| `verify-through-the-consuming-filter` | `docs/ai/roles/implementer.md` L12へ昇格済み | **同意** | implementer.md L12に`repr`相当の型確認、`| length`等の下流フィルタまで通す旨がほぼ逐語で存在 |
| `sweep-all-documents-stating-a-changed-boundary` | `skills/document-norm-review/SKILL.md`へ昇格済み | **同意** | 同SKILL「前提: 掃引は目視でなく機械的に行う」節が該当箇所を明示的に引用し、内容も一致 |
| `verification-referent-and-path-mismatch` | 同上(「参照先を誤らないための作法」に全文) | **同意** | 同SKILL該当節の4項目が、Lesson本文の適用条件1〜4と1対1で対応することを確認した |
| `destructive-operation-classification-criteria` | Policyが分類の正本 | **同意** | `ansible_test_safety_policy.md` L54「実行コスト...を分類理由にしない」がLessonの規約とほぼ逐語で一致 |
| `rollback-cli-argument-convention` | 実装規約。`skills/ansible-implementation-style/SKILL.md`の領分 | **不同意(要対応)** | 同SKILLに`rollback`の記述が0件(grep)。「領分」と判断した置き場が空で、規約は実質どこにも渡らない。上記Suggestions #1参照 |
| `claude-code-unattended-session-confinement` | 対象が存在しない(無人`claude -p`廃止) | **同意** | `roles/knowledge_review`配下に残る`claude -p`言及はすべて「2026-08-03に廃止した」旨の説明コメントのみで、実行コードとしては現存しない |
| `agmsg-bootstrap-live-test-identity-collision` | 対象が存在しない(agmsg/tmux多ペイン廃止) | **同意** | `roles/`・`scripts/`・`playbooks/`配下に`agmsg`言及が0件 |
| `verify-the-outside-of-a-claimed-boundary` / `enumerate-credentials-that-reach-you-not-those-you-placed` | 境界設計側の教訓、発火機会が稀。境界設計時はCoordinatorが読む(①) | **条件付き同意** | 判断軸1の適用自体は妥当。ただし境界設計を伴う実装(依頼文の権限境界を書く場面)はCoordinatorだけでなくsubagent-briefing経由でImplementer/Testerにも及ぶため、依頼文側で境界を明示する運びが崩れていないかは今後も確認が要る(本件のスコープ外、既存の`skills/subagent-briefing/SKILL.md`「実行identityと権限境界」がその代わりを担っている) |
| `dynamic-include-escapes-static-and-rescue` | 発火機会が稀。`scripts/check-staged-yaml.py`が予防層 | **同意** | 同スクリプトが実在し、コメントで「動的include先の構文検査の唯一のpre-commit防御」と明記している |
| `multilayer-escaping-and-novel-stack-verification` 項1・項3 | 発火機会が稀(項4のみR1として採用) | **同意** | 初物スタック導入は稀という判断軸1の適用は妥当。項4のみが独立して再利用可能な観点であることも内容から支持できる |
| `always-loaded-summaries-are-the-least-current` | `coordinator.md` L58・`status.md` L15でcovered | **同意(範囲限定)** | 本Lessonの主題(索引/要約/本文の3層で最も古い層が最も読まれる)はCoordinator自身の読み方の教訓であり、Coordinatorは今後もKnowledgeを読み続けるため、Role文書化しなくても消失しない。L58は「確認手段があるなら先に確認する」という一般原則で完全一致ではないが、実害は無い |
| `reasoning-heavy-models-trade-depth-for-breadth` | `coordinator.md` L102が既に述べている | **同意(範囲限定)** | L102「委任するときの独立性」がReviewer/Auditorの独立性を実質的防御として扱う姿勢を捕捉している。「差し戻しの多さを失敗と見なさない」の一文だけは未記載だが、分析の言う通りこれは工程設計の姿勢でありRole文書の留意事項ではない |
| `permission-boundaries-must-be-designed-not-prompted` 教訓1 / `2026-08-02_auditor-reverted-coordinator-uncommitted-edits` | `skills/subagent-briefing/SKILL.md` L14・`core.md` L129へ昇格済み | **同意** | 両方とも実在を確認。core.md「自分が作った変更以外を元に戻さない」、subagent-briefing「結果で書く方式の死角」がそれぞれ該当Incidentの是正内容と一致 |

## Knowledge非読化で残る欠落(§3の検討)

- **Implementer**: 本差分でImplementer向けの新規追加は0件(方針通り、I1はcore.mdのdecoy節でImplementerも含む全Roleに掛かる)。既存の`implementer.md` L12(消費側フィルタ)と`skills/ansible-implementation-style/SKILL.md`の既存内容で、`proxmox_patch_dryrun`系インシデント(None化クラッシュ、rc=4の観測不足)が生んだ教訓は概ね拾えている。**例外は上記Suggestions #1のrollback CLI規約。**
- **Reviewer/Tester/Auditor**: 追加4件(R1/R2/T1/T2/A1)はいずれも実績のある反復欠陥から来ており、置き場・内容とも欠落は見当たらない。
- **Coordinator**: Knowledgeを読み続けるため、そもそも本設計変更の影響を受けない。

## Verdict

**Request Changes**(I1の技術的正確性)。S1/R1/R2/T1/T2/A1/C1と①③④(構造)は問題なし。

是正が要る点:
1. `docs/ai/core.md` decoy節のI1を、`ansible_test_safety_policy.md`(TS-030)の停止assert機構と矛盾しない表現へ書き直す。焦点は「分類そのものが`--check`を無効化する」ではなく、「停止assertの存在(特に未commitの新規playbook・play単位の充足)を確認せずにdecoy+`--check`を安全策として扱わない」こと。
2. `rollback-cli-argument-convention`の置き場(`skills/ansible-implementation-style/SKILL.md`)へ実際に規約を転記するか、転記していないことを明示的な申し送りとして残す。

## 確認範囲

- 読んだ: `docs/ai/core.md`(全文diff)、`docs/ai/roles/reviewer.md`・`tester.md`・`auditor.md`・`coordinator.md`(全文diff+周辺)、`docs/ai/memory-classification.md`・`role-context-matrix.md`(diff)、`skills/code-review/SKILL.md`、`skills/document-norm-review/SKILL.md`、`skills/requirements-analysis/SKILL.md`(該当節)、`skills/ansible-implementation-style/SKILL.md`(grep)、`skills/subagent-briefing/SKILL.md`(該当節)、`skills/ansible-security-review/SKILL.md`(grep)、`docs/ai/policies/ansible_test_safety_policy.md`(risk-accepted関連全節)。
- `docs/ai/memory/lessons/`17本、`incidents/`16本、`decisions/`2本の全件を読んだ(本依頼の例外規定に基づく)。
- `git log -S"TS-030"`でPolicy改訂の導入時期を確認し、I1原資のインシデントと同日・同案件(`check_mode_semantics`)であることを確認した。
- 現在repoに存在する`risk-accepted`playbook 3本すべてで停止assertの実装を`grep`で確認した。
- `scripts/check-staged-yaml.py`・`roles/knowledge_review/`配下の`claude -p`残存・`agmsg`残存を`grep`で確認した。

## 未確認事項

- 構造変更(節統合、宙ぶらりん参照の有無)は別Reviewerの担当のため確認していない。
- `docs/ai/memory/decisions/`2本(`ansy-must-not-trigger-production-changes.md`・`approval-authority-for-real-host-operations.md`)は読んだが、今回の8件の採否には関与しておらず、本レビューでの指摘対象にはならなかった。
- 実ホストへは一切触れていない(禁止事項の通り)。ansible実行もしていない。
