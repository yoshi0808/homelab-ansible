# Note (fixture: check3 broken link)

See [role routing](role-routing-index.md) and the [catalog](../../playbooks/README.md).

This one is deliberately broken for `scripts/check-doc-consistency.py`
check3: [nonexistent doc](./this-file-does-not-exist.md) does not resolve
to any tracked file.

This one must NOT be reported (it is a literal code-span example, not a
real link): `[example](...)`.
