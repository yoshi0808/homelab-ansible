# Codex entrypoint

Codexは作業開始時に、共通原則の正本 [`docs/ai/core.md`](docs/ai/core.md) を読む。共通原則やRole本文はこの入口へ複製しない。

Ansible実行の安全分類は [`docs/ai/policies/ansible_test_safety_policy.md`](docs/ai/policies/ansible_test_safety_policy.md) が正本。

Codexは、`recovery_exec`とProxmoxパッチ適用の実行エンジンに加え、開発工程ではCoordinatorが指定したRoleとして起動される。開発工程でRoleを指定されたCodexは、共通原則に続けて`docs/ai/roles/<role>.md`の該当する正本を読む。運用実行エンジンは引き続き`recovery_exec_setup`が配布する専用のAGENTS.md(`AGENTS.md.j2`)に従う。
