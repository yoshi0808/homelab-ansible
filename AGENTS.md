# Agent entrypoint

AIエージェントは作業開始時に、次の3つを読む。共通原則やRole本文はこの入口へ複製しない。

1. 共通原則の正本 [`docs/ai/core.md`](docs/ai/core.md)
2. **自分のRole本文** — 起動時に指定された役の `docs/ai/roles/<role>.md` を読む。役の指定が無いときの扱いは下の表に従う。Coordinatorなら [`docs/ai/roles/coordinator.md`](docs/ai/roles/coordinator.md)(着手前の報告の型、承認境界、起動できるRoleとモデル配分、`docs/ai/status.md`の維持はここにしか無い)
3. 実行許可・禁止の正本 [`docs/ai/policies/execution_boundary_policy.md`](docs/ai/policies/execution_boundary_policy.md) — **対象作業に関わらず作業開始時に読む**(他のPolicyと扱いが違う)

**このリポジトリは特定のベンダーのAIを前提にしない。** どのRoleをどの製品が担うかは `docs/ai/roles/coordinator.md` が定める。製品によって異なるのは次の2点だけである。

| 製品 | 役の指定が無いとき | 実行境界を機械的に強制している機構 |
|---|---|---|
| Claude Code | Coordinatorとして振る舞う | `.claude/settings.json`(`permissions` と `autoMode`) |
| Codex | Coordinatorとして振る舞わず、どの役かを確認してから着手する | 承認ルール `.codex/rules/default.rules`(`~/.codex/rules/default.rules` からのsymlink)と、sandbox設定 `~/.codex/config.toml` の `[sandbox_workspace_write]` |

会話上の明示承認を実行権限とする境界は `execution_boundary_policy.md` が定める。強制機構は**設定そのものが正本**であり、値を文書へ写さない。

Ansible実行を伴う作業を行うときは、安全分類の正本として [`docs/ai/policies/ansible_test_safety_policy.md`](docs/ai/policies/ansible_test_safety_policy.md) を確認する(他のPolicyと同様、対象作業のときだけでよく、作業開始時の読み込みには含めない)。

**運用の実行エンジンとしてのCodexは、この入口に従わない。** `recovery_exec` とProxmoxパッチ適用で動くCodexは、`recovery_exec_setup` が配布する専用の `AGENTS.md`(`AGENTS.md.j2`)に従う。
