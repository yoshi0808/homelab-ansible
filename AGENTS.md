# Codex entrypoint

Codexは作業開始時に、共通原則の正本 [`docs/ai/core.md`](docs/ai/core.md) と、identity・Role・routingの正本 [`docs/ai/role-routing-index.md`](docs/ai/role-routing-index.md) を読む。共通原則やRole本文はこの入口へ複製しない。

Ansible実行の安全分類は [`docs/ai/policies/ansible_test_safety_policy.md`](docs/ai/policies/ansible_test_safety_policy.md) が正本。

注記(2026-07-26): Codexは開発工程から外れ、`recovery_exec`とProxmoxパッチ適用の実行エンジンとしてのみ稼働している。それらは`recovery_exec_setup`が配布する専用のAGENTS.md(`AGENTS.md.j2`)を読むため、このリポジトリ直下のAGENTS.mdを参照する主体は現状存在しない。
