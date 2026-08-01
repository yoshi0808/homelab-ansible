# Playbook catalog (fixture: empty playbooks dir)

`playbooks/` deliberately has no `*.yml` files in this fixture. check1's
input set is then empty, which must be reported as an error (AC4), not as
"0 compared, 0 mismatches, PASS".

| Playbook | 対象 | 用途 | `tester-gate` | 主な role / 実装 |
| --- | --- | --- | --- | --- |
