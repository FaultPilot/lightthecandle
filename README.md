# Light the Candle

Light the Candle v0.1 is a local-first project adoption and readiness
foundation. It captures an executive strategy seed, selects delivery rigor,
discovers project capabilities, and binds portable project intent to a local
integrity ledger.

The product direction is a governed virtual executive and software engineering
organisation that keeps delivery connected to evidence, outcomes, changing
assumptions, and the best current use of effort without applying enterprise
ceremony to every project.

The product invariant is:

```text
intent -> governed execution -> verified outcome -> durable recovery
```

## Current milestone

Version 0.1 establishes a project-neutral adoption and readiness foundation:

- Codex plugin packaging and a portable Python CLI
- new-project and existing-project discovery
- prototype, quality, production, and enterprise profiles
- committed, portable project manifests with no machine-specific paths
- local tamper-evident registration events bound to the portable manifest
- read-only status and project doctor commands
- strategy seeds, outcome measures, assumptions, constraints, and review rules
- read-only provider fingerprints and explicit future adapter boundaries
- preview-first reconciliation of a trusted manifest on another workstation

It does not yet claim autonomous delivery, remote coordination, provider
actions, or complete enterprise certification. Those capabilities are gated by
the roadmap and evaluation suite.

## Try locally

```bash
python3 scripts/ltc.py adopt /path/to/existing-project
python3 scripts/ltc.py adopt /path/to/existing-project --profile quality \
  --goal "Serve the intended user" --outcome "Deliver the approved result" --apply
python3 scripts/ltc.py register /path/to/copied-project \
  --reason "Trusted clone on a new workstation" --apply
python3 scripts/ltc.py status /path/to/existing-project
python3 scripts/ltc.py doctor /path/to/existing-project
```

`init`, `adopt`, and `register` preview by default. They write only when
`--apply` is present. `status` and `doctor` are read-only.

`register` is a local trust assertion. It does not transfer or authenticate the
manifest's origin, ownership, signatures, event history, or prior approvals.
Inspect the source and manifest before registering a copy from another person
or machine.

The long-term product is a governed, self-evolving executive strategy and
full-SDLC engineering organisation. Version 0.1 records an immutable strategy
seed. It does not yet implement strategy revision, autonomous learning,
cross-machine history, delivery execution, or release and recovery workflows.

## Product documents

- `docs/product-spec.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/threat-model.md`

## Development

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/ltc.py profiles --json
```
