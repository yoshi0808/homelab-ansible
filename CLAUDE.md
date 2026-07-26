# Claude Code entrypoint

Claude Codeは作業開始時に、共通原則の正本 [`docs/ai/core.md`](docs/ai/core.md) と、identity・Role・routingの正本 [`docs/ai/role-routing-index.md`](docs/ai/role-routing-index.md) を読む。共通原則やRole本文はこの入口へ複製しない。

Claude Code固有の実行許可・禁止は、Claude Codeの設定(`.claude/settings.json`)と、`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」を併せて確認する。Ansible実行の安全分類は [`docs/ai/policies/ansible_test_safety_policy.md`](docs/ai/policies/ansible_test_safety_policy.md) が正本。
