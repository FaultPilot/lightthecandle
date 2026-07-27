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
- The final `LTC_HOME` and ledger path components must not be relative,
  shared, symlinked, or non-private when inspected.
- Ambient Git path and configuration variables cannot redirect discovery.

## Primary threats

- Repository-controlled configuration attempting command execution
- Secrets copied into manifests, logs, memory, or evidence
- Stale memory overriding current source/provider facts
- Unsafe project discovery following paths outside the selected root
- Symlink replacement redirecting manifest or local-ledger writes
- Ambient Git variables redirecting discovery to another repository
- Silent state corruption or incompatible upgrades
- Agents claiming verification or completion without evidence
- Hooks creating an unexpected enforcement or execution surface

## Controls

- Commands remain argument arrays and are never executed by discovery.
- Doctor scans structured keys and values for likely credentials.
- Local paths are stored in the local ledger, not portable manifests.
- Writes use temporary files, `fsync`, and atomic replacement.
- Manifest creation uses verified directory descriptors and no-follow behavior.
- Local state requires a private, current-user-owned directory and regular
  database file on POSIX systems.
- Git discovery removes ambient `GIT_*` variables before read-only inspection.
- SQLite transactions serialize local lifecycle writes.
- Event hashes cover the prior hash and canonical event content.
- Copied manifests require explicit, reasoned local registration.
- Local registration does not authenticate a manifest's origin, owner,
  signatures, prior event history, or approvals.
- Hook and provider-action support remains disabled until separately reviewed.

The local hash chain is not signed or externally anchored. It detects
accidental corruption and unexplained mutation, but a hostile process able to
rewrite the SQLite ledger can recompute internally consistent hashes.

Python's standard SQLite API reopens the ledger by pathname. A hostile process
running as the same OS user can race that open after validation, including
through a parent path replacement. The post-open identity check detects the
change but cannot guarantee that the attacker-selected file was untouched.
Private-directory and no-follow checks protect cooperative local use; they are
not hostile same-user process isolation.

Elevated execution is unsupported. Do not run Light the Candle with `sudo`, as
root, or inside an agent granted unnecessary operating-system authority.

## Later requirements

Remote coordination, signed evidence, provider actions, shared identities,
hostile-repository isolation, and enterprise administration require separate
threat models and must not inherit version 0.1's cooperative trust assumptions.
