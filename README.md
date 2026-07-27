# Light the Candle

Light the Candle v0.1.2 is a local-first project adoption and readiness
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

- Codex and Claude Code plugin packaging around one portable Python CLI
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

## Agent surfaces

Codex and Claude Code load the same `skills/lightthecandle/SKILL.md` and call
the same deterministic kernel. They do not maintain separate project state.

- Codex invocation: `$lightthecandle`
- Claude Code invocation: `/lightthecandle:lightthecandle`

Test the Claude Code adapter directly from a clone:

```bash
claude plugin validate --strict .
claude --plugin-dir .
```

This repository is a self-contained marketplace for both Codex and Claude
Code. Test a local Codex marketplace installation with:

```bash
codex plugin marketplace add /path/to/lightthecandle
codex plugin add lightthecandle@lightthecandle
```

For a persistent local Claude Code installation:

```bash
claude plugin marketplace add /path/to/lightthecandle
claude plugin install lightthecandle@lightthecandle
```

After the repository is hosted, replace the local path with its GitHub
`owner/repository` or Git URL. A ChatGPT desktop share link for a local plugin
is workspace-scoped; it is not public Git distribution. See
`docs/distribution.md` and `docs/agent-adapters.md`.

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
- `docs/agent-adapters.md`
- `docs/distribution.md`
- `docs/technology-strategy.md`
- `docs/roadmap.md`
- `docs/threat-model.md`

## Development

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/ltc.py profiles --json
```
