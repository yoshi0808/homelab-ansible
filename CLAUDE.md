# Claude Code entrypoint

Claude Codeは作業開始時に、次の2つを読む。共通原則やRole本文はこの入口へ複製しない。

1. 共通原則の正本 [`docs/ai/core.md`](docs/ai/core.md)
2. **自分のRole本文** — この対話セッションはCoordinatorなので [`docs/ai/roles/coordinator.md`](docs/ai/roles/coordinator.md)(着手前の報告の型、承認境界、起動できるRoleとモデル配分、`docs/ai/status.md`の維持はここにしか無い)

Claude Code固有の実行許可・禁止は、Claude Codeの設定(`.claude/settings.json`)と、`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」を併せて確認する。Ansible実行を伴う作業を行うときは、安全分類の正本として [`docs/ai/policies/ansible_test_safety_policy.md`](docs/ai/policies/ansible_test_safety_policy.md) を確認する(他のPolicyと同様、対象作業のときだけでよく、作業開始時の読み込みには含めない)。
