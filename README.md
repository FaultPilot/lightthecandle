# Light the Candle

Light the Candle v0.1.3 is a local-first project adoption and readiness
foundation. It captures an executive strategy seed, selects delivery rigor,
discovers project capabilities, and binds portable project intent to a local
integrity ledger.

> **Release status:** public beta. Every published tag must pass the hosted CI,
> release-state, artifact, and clean-install gates in
> `docs/release-checklist.md`.

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
- local hash-chained registration events for accidental-corruption and
  unexplained-mutation detection
- read-only status and project doctor commands
- strategy seeds, outcome measures, assumptions, constraints, and review rules
- read-only provider fingerprints and explicit future adapter boundaries
- preview-first reconciliation of a trusted manifest on another workstation

It does not yet claim autonomous delivery, remote coordination, provider
actions, or complete enterprise certification. Those capabilities are gated by
the roadmap and evaluation suite.

Rigor profiles define readiness expectations. They do not execute checks,
certify a project, or independently prove compliance.

## Prerequisites

- macOS or Linux; Windows is not yet in the supported beta boundary
- Python 3.9 or newer
- Git for marketplace installation and Git-aware discovery
- Codex or Claude Code with plugin marketplace support

The Python runtime has no third-party dependencies. Version 0.1.3 was tested
with Codex CLI 0.145.0 and Claude Code 2.1.207.

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

After the repository is hosted, install a reviewed, tag-pinned release rather
than an unpinned default branch. Exact Codex and Claude commands, verification,
updates, uninstall behavior, data retention, and limitations are in
`docs/public-beta.md`. A ChatGPT desktop share link for a local plugin remains
workspace-scoped; it is not public Git distribution.

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

The manifest is intended to be reviewable and may be committed. The local
ledger contains canonical machine paths and registration metadata. Neither
location is suitable for credentials, personal information, client-confidential
material, or raw production data. Read `PRIVACY.md` before adoption.

The long-term product is a governed, self-evolving executive strategy and
full-SDLC engineering organisation. Version 0.1 records a locally governed
strategy seed. It does not yet implement strategy revision, autonomous learning,
cross-machine history, delivery execution, or release and recovery workflows.

## Product documents

- `docs/product-spec.md`
- `docs/architecture.md`
- `docs/agent-adapters.md`
- `docs/distribution.md`
- `docs/public-beta.md`
- `docs/release-checklist.md`
- `docs/technology-strategy.md`
- `docs/roadmap.md`
- `docs/threat-model.md`
- `SECURITY.md`
- `PRIVACY.md`
- `SUPPORT.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`

## Development

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/ltc.py profiles --json
python3 scripts/release_guard.py
```

The publication gate is:

```bash
python3 scripts/release_guard.py --require-license --scan-history
```

The exact tagged checkout additionally runs with `--require-release-state`.
See `CONTRIBUTING.md` for the complete local validation set.

## License

Copyright 2026 Aaron Robbins.

Licensed under the Apache License, Version 2.0. See `LICENSE`.
