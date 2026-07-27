# Technology Strategy

## Three planes

Light the Candle separates authority from execution:

```text
control plane
  policy, lifecycle, approvals, evidence, canonical memory, recovery

worker plane
  Codex, Claude Code, Factory Droid, Copilot, future agents

runtime plane
  native local runner, optional LangGraph, future schedulers
```

Only the Light the Candle control plane may satisfy a gate or transition
authoritative project state. Workers and runtimes return versioned receipts.
Provider memory is advisory context until it is independently validated and
promoted under Light the Candle policy.

## Candidate decisions

| Candidate | Current decision | Reconsider when |
| --- | --- | --- |
| Factory Droid | Optional future worker adapter, not a core dependency | Work items, claims, resource reservations, action requests, and exact-subject evidence receipts exist |
| GitHub Copilot Memory | Design reference for cited, revision-bound, revalidated, expiring memory | Light the Candle owns its memory/evidence schema and GitHub exposes a stable, policy-compatible interface |
| LangGraph | Optional future workflow-runtime implementation, not the control plane | A native deterministic runtime port and restart, idempotency, approval-resume, and cancellation tests exist |

## Integration rules

- Uninstalling any worker or runtime must not prevent local status, evidence
  interpretation, or recovery.
- External agents receive a scoped task specification and cannot write Light
  the Candle state directly.
- Agent output is untrusted until bound to live evidence such as a Git revision,
  test receipt, provider result, or approved artifact digest.
- Runtime checkpoints support resumption; they do not replace canonical events,
  approvals, evidence, or memory.
- Vendor tracing and hosted state remain opt-in.
- Integrations use structured, versioned contracts rather than parsed terminal
  prose.

## Evaluation order

1. Define authority, task, run-receipt, evidence, memory, and runtime contracts.
2. Implement evidence-backed local memory with provenance, subject binding,
   freshness, expiry, supersession, visibility, and redaction.
3. Build a small native deterministic workflow runner.
4. Run a read-only worker conformance comparison across supported agents.
5. Evaluate Factory Droid as a removable worker adapter.
6. Evaluate LangGraph behind the workflow-runtime port with kill/resume and
   equivalence tests.
7. Evaluate Copilot Memory interoperability only after a stable interface is
   available.
