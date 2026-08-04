# Review: Context 14本 + Skill 12本 + 索引4本 — 2026-08-02〜08-04変更に対する掃引

作成: Reviewer(subagent) / 2026-08-04

対象: `docs/ai/reviews/norm_docs_post_phase4_sweep/2026-08-04_001_change_baseline.md`(以下「baseline」)に挙がった9項目の事実変化に照らし、`docs/ai/context/`配下14本・`skills/*/SKILL.md`12本・索引/分類4本(`context-classification.md`/`core-migration-map.md`/`policy-migration-map.md`/`memory-classification.md`)、計30本を対象に`skills/document-norm-review/SKILL.md`の観点で掃引した。**全文レビューではなく、baselineの各項目を全体へ当てる掃引に限定**。対象文書は1文字も変更していない。

## Summary

30本すべてを通読した。baselineの9項目のうち、明確な矛盾を1件検出した(`docs/ai/context/system/semaphore.md`)。これは「規範の消失」ではなく「事実の反転」(Semaphoreテンプレートの正本の所在)であり、深夜(2026-08-04 11:47)時点の記述が同日昼(12:29、`bffa6ba`)の適用完了に追随していない。他29本は、baselineの各項目に照らして矛盾・宙ぶらりん参照を検出しなかった。

## 確認済み事項(何を、どう確かめたか)

- 対象30本すべてをRead toolで全文通読した(行番号付き)。
- baseline記載のcommit hash(`65923ae`/`c8bebbf`/`bffa6ba`)を`git show --stat`で確認し、Semaphoreテンプレートの正本化が3段階(Step 0: dispatch追加→Step 1: repo定義→Step 1完了: 本番適用)で進んだことを確認した。
- `git log -1 --format="%H %ai" -- docs/ai/context/system/semaphore.md`で最終更新commitが`c8bebbf`(Step 1、**未適用**時点)であり、その後の`bffa6ba`(Step 1完了・本番適用)に更新が追随していないことを確認した。
- `roles/semaphore_templates/`の実在を`ls`で確認した(`defaults`/`filter_plugins`/`tasks`)。
- baselineの他8項目について、関連語(`incident_sync`、`id_rsa_sophos`、`claude -p`、`commit.*禁止`、`同じ作業ツリー`/`worktree`、`4段`/`毎時複製`、`dispatch`、`ansyから.*到達`、`forced.command`、`正本が無い`等)で対象30本をgrepし、ヒット箇所をすべて現物で個別確認した。
- `scripts/check-deploy-needed.py`・`roles/deployment_drift_check/defaults/main.yml`・`roles/worktree_sync/defaults/main.yml`・`roles/recovery_exec/files/homelab-semaphore-query`(`template-list`サブコマンドの実在)・`docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md`の実在を`ls`/`grep`で確認した(`code-delivery-to-production.md`・`autonomous-recovery.md`(system)が引用する具体パスの裏取り)。

## Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `docs/ai/context/system/semaphore.md` | 17-18 | **Semaphoreテンプレートの正本の所在が反転している。** 「templateはUIで手作りされており、リポジトリに正本が無い」「Semaphoreを構成するroleはこのリポジトリに存在せず」「『本番で押せるボタン』の定義はGitの外にある」と述べるが、`c8bebbf`(Step 1)で`roles/semaphore_templates/`に43件の定義を作り、`bffa6ba`(Step 1完了、2026-08-04 12:29)で本番へ適用済み(baseline項目7)。現在は**リポジトリが正本**であり、定義はGitの外にはない。この段落は`c8bebbf`時点(適用前)で書かれたまま`bffa6ba`に追随しておらず、「読めるようになったことと、正本がここにあることは別である」という結びの一文も、正本が実際にここへ来た今は前提が崩れている。読み手(特にCoordinator/Reviewer)がこの文書を根拠に「Semaphore templateはGit管理外」と判断すると誤る。 | Critical |

## Suggestions

- `docs/ai/context/system/semaphore.md`の該当段落は、`roles/semaphore_templates/`が正本であること・同定はdescriptionマーカーで行うこと・`semaphore-query template-list`は「一覧の読み取り」であり正本の所在とは別物であることを明記する形に更新するとよい(ただし本掃引の対象外であり、書き換えは行っていない)。
- 同段落の「Semaphoreを構成するroleはこのリポジトリに存在せず(`homelab_cert_renew`が証明書を配る箇所のみ)」という一文も、`roles/semaphore_templates/`(reconcile role)の存在と矛盾するため、上記修正と合わせて見直すのが妥当。

## What Looks Good

baselineの9項目のうち、#1の1件を除く8項目について、対象30本に矛盾・宙ぶらりん参照・撤回済み根拠の残存を検出しなかった。

- **項目1(ansyの本番到達手段喪失)**: `docs/ai/context/system/overview.md`・`system/semaphore.md`・`system/autonomous-recovery.md`・`operations/autonomous-recovery.md`・`operations/code-delivery-to-production.md`のいずれも、ansyが本番ホストへ認証情報で到達できることを前提にした記述を持たない。`system/autonomous-recovery.md`は「開発環境 | ansy | 自律復旧action対象外」と明記済みで、baselineと整合する。`system/semaphore.md`の「ansy の Semaphore」節(2026-08-04追記)はSSH鍵削除の事実を正確に反映している。
- **項目2(incident_sync退役)**: `incident_sync`/`incident-sync`という語は`code-delivery-to-production.md`の1箇所(退役した機構の実例として言及)にのみ出現し、他の文書に「稼働中」であるかのような記述は無い。
- **項目3(月次Knowledge振り返りの無人化廃止)**: `claude -p`という語は対象30本のどこにも出現しない。`memory-classification.md`の月次振り返り節は「振り返り自体は人がCoordinatorとの対話セッションで行う」「起動はtimerが行う」と記述しており、baselineの「無人セッションは1つも残っていない」と整合する。
- **項目4(commit/push全面禁止→都度承認)**: 対象30本に「commit禁止」「push禁止」「全面禁止」に相当する記述は無い(該当する規範はcore.md側にあり対象外)。
- **項目5(quory作業ツリー自動追随・Semaphoreは別clone)**: `code-delivery-to-production.md`は2026-08-04付けの訂正として「Semaphoreは`/home/yoshi/homelab-ansible`を使っていない」を明記し、旧記述を「訂正前の記述である。判断の根拠に使わないこと」と明示的に無効化した形で残している(意図的な保持であり宙ぶらりんではない)。他の文書はこの点に触れていない。
- **項目6(配備経路のContext明文化)**: `code-delivery-to-production.md`自体がこの期間の新設物であり内容は現行事実と一致することを確認した。`repository-overview.md`からの参照も整合している。
- **項目8(core.md等の規範文書変更)**: 対象30本のうち、core.mdの当該変更点(判断者/実行者の分離、打鍵入口を増やさない、開発運用分離の書き直し)を誤って複製・矛盾させている箇所は見つからなかった(対象30本はcore.mdの当該節を引用・複製していない)。
- **索引4本**: `context-classification.md`・`core-migration-map.md`・`policy-migration-map.md`・`memory-classification.md`が指す分類先・参照先(`inventory-map.md`/`playbook-map.md`廃止、`agmsg`廃止、Tech Lead廃止等)はいずれも過去の既決事項であり、baseline期間の変更と矛盾しない。`policy-migration-map.md`は自身を「凍結(歴史的記録)」と明示しており、現在値を保証しないことを自己申告している。

## 未確認事項・未解決事項

- **baseline項目9(その他確定事実: ACPI shutdown、journal-ssh配備後確認、Lesson昇格2件、時刻表記規約の移設、日次ドリフト検査の実例)**は、対象30本中で個別の技術的正否を検証する性質のものではなく、grep範囲では矛盾を検出しなかった。ただしこの項目は「その他」であり網羅的な当て込みは行っていない。
- 本掃引は**baselineに挙がった変更点への掃引に限定**しており、baseline以外の理由で対象30本が古くなっている可能性(baseline作成者が見落とした事実変化)までは検査していない。
- Critical #1の段落を除き、30本全文を読んだ上での判断であり、見ていない範囲は無い(索引4本・Context14本・Skill12本すべて通読済み)。

## Verdict

Request Changes(Critical #1のみ。他29本はWhat Looks Goodの記載どおり問題なし)。
