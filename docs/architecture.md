# Architecture

## Layers

### Kernel

Version 0.1 implements project identity, an executive strategy seed, profile
policy evaluation, local registration events, and integrity checks. The
lifecycle graph, state reduction, evidence references, resource ownership,
approvals, controlled evolution, and recovery are planned kernel capabilities.

### Profiles

Project-neutral rigor requirements for prototype, quality, production, and
enterprise delivery.

### Adapters

Version 0.1 records read-only or disabled capability fingerprints discovered
from project files and Git metadata. Future replaceable adapters cover source
control, trackers, documentation, CI, deployment, databases, distribution,
secrets, observability, and communication.

### Agent surfaces

The portable CLI is authoritative for deterministic mechanics. Codex skills,
plugins, other agent integrations, and future interfaces call the same kernel.

### Human projections

Readable plans, build logs, reports, and memories are projections from
structured facts. A projection never silently overrides live evidence.

### Executive strategy and learning

Strategy records connect intent, outcomes, measures, assumptions, decisions,
risks, initiatives, and delivered evidence. Learning records remain candidates
until an approved evolution event versions the affected strategy or policy.
Future versions retain the artifacts required to reproduce historic decisions
and policy evaluation.

Only the initial strategy seed and its policy digest binding exist in version
0.1. The digest detects drift; it does not retain the original policy artifact.

## Persistence

- `.lightthecandle/project.json`: portable, non-secret, project configuration
- `$LTC_HOME/state.sqlite`: machine-local projects and tamper-evident events
- project documentation: reviewable requirements, decisions, plans, and memory
- provider systems: authoritative remote facts when configured

The local event ledger forms a hash chain. It provides accidental-corruption
and unexplained-mutation detection, not hostile-user cryptographic security.

## Authority model

Models and agents may observe, analyse, challenge, simulate, and propose.
Deterministic policy decides the minimum rigor. Only the human owner or a
separately configured external authority may approve material goal changes,
policy reductions, external writes, releases, spending, or production actions.

## Dependency rule

The kernel must not import provider implementations. Adapters depend on kernel
interfaces. Agent surfaces depend on both. Project policies contain no
machine-specific paths or secrets.

## Compatibility

Schemas use stable identifiers such as `lightthecandle.project/v1`. Migrations
must be explicit, idempotent, backed up, and covered by fixture tests. Unknown
newer schemas fail closed without modifying state.
