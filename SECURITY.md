# Security Policy

## Supported versions

Light the Candle is in public beta. Until 1.0, only the latest
tagged `0.1.x` release receives security fixes. Older prerelease versions may
require upgrading rather than a backport.

## Report a vulnerability

Use the repository's **Security > Report a vulnerability** flow. Do not include
exploit details, credentials, private source, customer information, or
production data in a public issue.

If private vulnerability reporting is unavailable, open a minimal public issue
requesting a private maintainer contact channel without describing the
vulnerability. Public distribution requires private reporting to remain
enabled on the canonical repository.

Reports are handled on a best-effort basis during beta; there is no response
SLA or bug bounty. A useful report includes the affected version, operating
system, host agent, reproduction steps using synthetic data, impact, and any
suggested mitigation.

## Security boundary

Version 0.1 is a cooperative local controller. It is not a hostile-code
sandbox, identity provider, secret manager, CI system, or provider
authorization layer.

- Do not run Light the Candle with `sudo`, as root, or in an elevated agent.
- Do not place credentials, personal data, client-confidential information, or
  raw production data in prompts, manifests, events, or registration reasons.
- Treat repository files and discovered commands as untrusted. Version 0.1
  records discovered commands but does not execute them.
- The local hash chain detects accidental corruption and unexplained mutation.
  A hostile process able to rewrite the SQLite ledger can recompute it; it is
  not a signed or externally anchored audit log.
- Python SQLite opens the ledger by pathname. Private-directory, ownership,
  permission, no-follow, and identity checks reduce accidental redirection but
  do not isolate the ledger from a hostile process running as the same OS user.
- The plugin performs no provider writes or network requests in version 0.1.
  Codex, Claude Code, Git, and the surrounding operating environment retain
  their own security and data-handling boundaries.

The detailed technical boundary is in `docs/threat-model.md`.

## Release security

Before publishing a release, maintainers must run the repository release
checklist, review and enforce the source and wheel artifact allowlist, run the
automated reachable-history credential scan, verify clean installs, and publish
from an exact reviewed commit. Hosted actions are pinned to reviewed commits;
Dependabot proposes grouped monthly updates for explicit review.
