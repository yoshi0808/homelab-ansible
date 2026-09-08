# Claude Code entrypoint

Claude Codeは作業開始時に、次の3つを読む。共通原則やRole本文はこの入口へ複製しない。

1. 共通原則の正本 [`docs/ai/core.md`](docs/ai/core.md)
2. **自分のRole本文** — **起動時に役を指定されていればその役、指定が無ければCoordinatorである。** 該当する `docs/ai/roles/<role>.md` を読む。Coordinatorなら [`docs/ai/roles/coordinator.md`](docs/ai/roles/coordinator.md)(着手前の報告の型、承認境界、起動できるRoleとモデル配分、`docs/ai/status.md`の維持はここにしか無い)
3. 実行許可・禁止の正本 [`docs/ai/policies/execution_boundary_policy.md`](docs/ai/policies/execution_boundary_policy.md) — **対象作業に関わらず作業開始時に読む**(他のPolicyと扱いが違う)

**このリポジトリは特定のベンダーのAIを前提にしない。** この入口と同じ内容をCodex向けに [`AGENTS.md`](AGENTS.md) が持つ。どのRoleをどちらが担うかは `docs/ai/roles/coordinator.md` が定める。

機械的な実行境界を強制している機構は、Claude Codeの設定 `.claude/settings.json`(`permissions` と `autoMode`)である。会話上の明示承認を実行権限とする境界は `execution_boundary_policy.md` が定める。**設定そのものが正本**であり、値を文書へ写さない。

Ansible実行を伴う作業を行うときは、安全分類の正本として [`docs/ai/policies/ansible_test_safety_policy.md`](docs/ai/policies/ansible_test_safety_policy.md) を確認する(他のPolicyと同様、対象作業のときだけでよく、作業開始時の読み込みには含めない)。
