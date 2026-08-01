# Playbook catalog (fixture: clean baseline)

Everything below is consistent on purpose — this fixture is the "should
stay green" control for `scripts/check-doc-consistency.py`, exercised by
`scripts/tests/fixtures/README.md`'s test procedure.

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`sample.yml`](sample.yml) | `localhost` | fixture用ダミー | `safe-readonly` | none |
