# Playbook catalog (fixture: check1 tester-gate mismatch)

This fixture is deliberately broken for
`scripts/check-doc-consistency.py` check1: the header below says
`risk-accepted`, but `playbooks/sample.yml` actually declares
`safe-readonly`.

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
| [`sample.yml`](sample.yml) | `localhost` | fixture用ダミー | `risk-accepted` | none |
