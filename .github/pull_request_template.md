## Change

Describe the scoped behavior change and why it is needed.

## Safety

Describe persistence, schema, migration, permission, provider, execution,
privacy, and rollback effects. State `none` where a category does not apply.

## Validation

List the exact commands run and summarize their results.

## Checklist

- [ ] Preview-before-write behavior is preserved.
- [ ] Unknown schemas and unsafe paths fail closed.
- [ ] No credentials, private data, generated artifacts, or local state are included.
- [ ] Focused tests cover the change.
- [ ] Documentation and the threat model are updated when required.
