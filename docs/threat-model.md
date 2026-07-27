# Threat Model

## Version 0.1 boundary

Light the Candle is a cooperative local controller. It is not a hostile-code
sandbox, identity provider, secret manager, CI system, or substitute for
provider authorization.

## Protected outcomes

- No write occurs during preview, status, or doctor.
- Project manifests contain no secrets or required absolute machine paths.
- Existing manifests are never overwritten implicitly.
- Unknown schema versions fail without mutation.
- Local registrations are transaction-bound and chain-verifiable.
- Registered manifest, canonical root, policy digest, and genesis event agree.
- Provider commands are not executed in version 0.1.

## Primary threats

- Repository-controlled configuration attempting command execution
- Secrets copied into manifests, logs, memory, or evidence
- Stale memory overriding current source/provider facts
- Unsafe project discovery following paths outside the selected root
- Silent state corruption or incompatible upgrades
- Agents claiming verification or completion without evidence
- Hooks creating an unexpected enforcement or execution surface

## Controls

- Commands remain argument arrays and are never executed by discovery.
- Doctor scans structured keys and values for likely credentials.
- Local paths are stored in the local ledger, not portable manifests.
- Writes use temporary files, `fsync`, and atomic replacement.
- SQLite transactions serialize local lifecycle writes.
- Event hashes cover the prior hash and canonical event content.
- Copied manifests require explicit, reasoned local registration.
- Local registration does not authenticate a manifest's origin, owner,
  signatures, prior event history, or approvals.
- Hook and provider-action support remains disabled until separately reviewed.

## Later requirements

Remote coordination, signed evidence, provider actions, shared identities,
hostile-repository isolation, and enterprise administration require separate
threat models and must not inherit version 0.1's cooperative trust assumptions.
