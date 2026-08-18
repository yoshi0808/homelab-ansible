# Harness層(Claude Code / codex設定・機械検査)定期見直し

日付: 2026-08-18
対象: `.claude/settings.json` / `.claude/agents/*.md` / `.claude/skills/` / `scripts/git-pre-commit-check.sh` / `scripts/git-pre-push-check.sh` / `scripts/check-doc-consistency.py` / `scripts/check-deploy-needed.py` / `scripts/check-staged-yaml.py` / `scripts/check-tester-gate.sh` / `scripts/session-context.sh` / `.gitignore`(AI実行環境まわりの行)
レビュアー: subagent(document-norm-review Skill併用)

## Code Review: Harness config/checks vs 現行規範

### Summary

承認境界(`.claude/settings.json` `autoMode` ↔ `docs/ai/roles/coordinator.md`)は行単位で突き合わせ、host分類・soft_deny/hard_deny・quory到達不能の記述とも食い違いを検出しなかった。`.claude/agents/*.md`もbodyがポインタのみで規範の複製は無い。一方、**Reviewer役が必須と定めるSkillのうち2本がClaude Code側で発見不能になっている**接続断(Critical #1)と、**.gitignoreに載るがgit管理下に残ったまま退役パスを参照するスクリプト**(Suggestions #1)を検出した。機械検査本体(pre-commit/pre-push/check-doc-consistency/check-tester-gate)は空集合PASSを設計上防いでおり、退役参照は見当たらなかった。

### Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `docs/ai/roles/reviewer.md` L43 / `.claude/skills/`(欠落) | reviewer.md:43 | `docs/ai/roles/reviewer.md`「必須ContextとSkill」は「Ansibleの計画または実装差分をレビューするときは、Ansible correctness review(`skills/ansible-correctness-review/SKILL.md`)とtest gap review(`skills/test-gap-review/SKILL.md`)を併用する」と**義務**として定めるが、`skills/ansible-correctness-review/`・`skills/test-gap-review/`には`.claude/skills/`配下のsymlinkが無い(他12本にはある)。Claude Code subagentとして起動されたReviewer(coordinator.md「Reviewerはagmsg経由のcodexを主、Claude Code subagentを代替とする」の代替経路)からは、`Skill`ツールの一覧にこの2本が現れず、名指しで併用できない。commit `860f635`(2026-08-10、この2本のSKILL.mdとreviewer.mdの併用規定を同時導入)以降、symlink追加が行われていない。**意図的な保留か追随漏れかは、この記録からは判定できない。** | Critical |

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `.gitignore`(AI実行環境の行)/ `scripts/ai-next.sh` | - | `.gitignore`は`scripts/ai-next.sh`をローカル専用ヘルパーとして除外指定しているが、`git ls-tree HEAD -- scripts/ai-next.sh`はこのファイルがcommit済み(100755 blob)であることを示す — 除外行は実効を持たない(既に追跡済みのパスに`.gitignore`は効かない)。加えてファイル内部は`PROMPTS_DIR="$REPO_ROOT/docs/ai/prompts"` / `CORE_MD="$PROMPTS_DIR/core.md"`を参照するが、`docs/ai/prompts/core.md`は2026-07-26のcore.md退役で存在しない(現行正本は`docs/ai/core.md`)。現行のRole文書・core.md・status.mdのいずれからも呼び出し参照が無い(grep実測)ため実害は無いが、退役した機構への参照を持つ死んだ成果物がリポジトリに残っている。 | 退役参照の残存 |
| 2 | `skills/ansible-correctness-review/` `skills/test-gap-review/`(ディレクトリ権限) | - | 上記2本のディレクトリ・SKILL.md・`agents/openai.yaml`はいずれも`0700`/`0600`(所有者のみ)。同階層の他Skillディレクトリは`0755`。git上のblob modeは通常の`100644`なので権限差は作業ツリー側のローカル事象であり、リポジトリの内容には影響しない。同一ユーザ(yoshi)配下で動く限り実害は無いはずだが、Critical #1の欠落symlinkと合わせて「commit `860f635`以降この2本だけ扱いが違う」という同一の兆候であるため参考として記録する。 | 参考(実害未確認) |

### What Looks Good

- `.claude/settings.json` `autoMode.allow`(monnie/ansy/sandbox確認不要、`operator_request_channel_client_setup.yml`個別許可)と`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」表の対応する行(`monnie`/`ansy`/`sandbox`行)は一致。追加された個別playbook許可の理由記述(2026-08-08の事情)もRole文書側の記述と矛盾しない。
- `autoMode.soft_deny`の保護対象ホスト列挙(pve1/pve2/authy/sophos-fw/UniFi)、quory含む「到達不能」列挙、git commit/push行、working tree破壊操作の行、いずれもcoordinator.md該当行(保護対象ホスト行/到達手段が無いホスト行/git commit・push行)と一致。**片方にしかない項目は無かった**(quoryが両ファイルとも「soft_denyは無効化されたが行は残す」という同じ扱いで揃っている)。
- `autoMode.hard_deny`は`$defaults`のみで、この2ファイル間の対応を崩すリポジトリ固有の追加は無い。
- `.claude/agents/{auditor,implementer,reviewer,tester}.md`のbodyは、coordinator.md「Agent定義との関係」が定める「正本へのポインタと成果物ファイル名の対応だけ」の範囲に収まっている。規範本文の複製は見当たらない。参照先(`docs/ai/core.md`、`docs/ai/roles/<role>.md`、`docs/ai/policies/ansible_test_safety_policy.md`、`skills/*/SKILL.md`)は全て実在を確認した。frontmatterの`model:`/`effort:`はcheck2の管轄のため対象外とした。
- `.claude/skills/`の12本のsymlinkは、対応する`skills/*`ディレクトリを正しく指しており、リンク切れは無い(Critical #1で挙げた2本を除く)。
- `scripts/git-pre-commit-check.sh`・`scripts/check-doc-consistency.py`・`scripts/check-tester-gate.sh`は、いずれも「入力集合が空のとき暗黙にPASSする」形を設計上排除している — `check-doc-consistency.py`はdocstringで明言し`AnalysisError`を投げる実装、`check-tester-gate.sh`はplaybook無しでも`grep`失敗でfail-closedになる形、`git-pre-commit-check.sh`はstaged files空なら`no staged files`として早期exit(commitできる実データが無い場合の話であり空PASSの穴ではない)。
- `check-doc-consistency.py`の実行結果(本日実行: check1 112件/check2 8件/check3 99件、全OK)・`check-tester-gate.sh`(56 playbooks OK)は観測事実どおりで、対象パス・件数の食い違いは無い。
- `scripts/check-deploy-needed.py`が前提とする`roles/deployment_drift_check/defaults/main.yml`は実在する。docstringが挙げる`docs/ai/context/operations/code-delivery-to-production.md`、`docs/ai/reviews/deploy_awareness/2026-08-04_002_implement.md`も実在を確認した。
- `scripts/session-context.sh`はSessionStart hookとして`.claude/settings.json`のhooks定義と一致し、`docs/ai/status.md`を要約せず現物として渡す設計(hooks本体のコメントが根拠を明示)。退役した状態管理機構への参照は無い。
- `.gitignore`の`.codex`・`.claude/settings.local.json`の2行は、対象タスクの前提どおり「このrepoは持たない」ものとして扱い、内容の照合対象から除外した。

### Verdict

Needs Discussion

Critical #1(`skills/ansible-correctness-review`・`skills/test-gap-review`のsymlink欠落)は、Reviewer役の必須Skill規定とClaude Code側の発見可能性が食い違っている状態であり、意図的な保留か追随漏れかをこの記録だけでは判定できない。Coordinatorが経緯(commit `860f635`前後の意図)を確認し、症状(symlink追加/reviewer.mdの記述後退のいずれか)を決める必要がある。

## 未解決事項

- Critical #1の欠落が「意図的(codex側のみで運用する設計)」か「追随漏れ」かは未確認。judgment可能な追加情報は本レビューの範囲では見つからなかった。
- Suggestions #2のディレクトリ権限差(0700/0600)がなぜ他Skillと異なるのかは未確認(誰が・どの経路でこの2本だけ作成したかは、このレビューの手段では特定できない)。
