# Release Checklist

## Human decisions

- [x] Repository owner, name, visibility, and canonical URL approved
- [x] License and copyright terms approved and `LICENSE` added
- [x] Public maintainer identity, commit email, and support identity approved
- [ ] GitHub private vulnerability reporting enabled
- [x] Publication explicitly approved by the owner

## Source gate

- [ ] Worktree clean and release commit reviewed
- [ ] Version matches Python, Codex, Claude, changelog, and tag
- [ ] Unit tests and Python compilation pass
- [ ] Codex plugin and skill validation pass
- [ ] Claude strict marketplace validation passes
- [ ] Every tracked JSON file parses
- [ ] `python3 scripts/release_guard.py --scan-history` passes
- [ ] Tagged checkout passes `python3 scripts/release_guard.py --require-license --scan-history --require-release-state`
- [ ] Reviewed artifact allowlist and automated sdist/wheel inventory check pass
- [ ] Wheel built from the source distribution installs in a fresh environment
- [ ] Installed console command loads all policy profiles

## Distribution gate

- [ ] Canonical remote configured
- [ ] Branch protection and required CI checks configured
- [ ] CI passes on the exact release commit
- [ ] Codex install from the canonical tagged Git source passes in isolation
- [ ] Claude Code install from the canonical tagged Git source passes in isolation
- [ ] Cached plugin scripts run from outside the source checkout
- [ ] Install, update, uninstall, state-retention, and limitation docs verified

## Publish and verify

- [ ] Create tag `lightthecandle--v<version>` from the reviewed commit
- [ ] Publish release notes with commit and artifact checksums
- [ ] Reinstall from the published tag on a clean beta account or machine
- [ ] Confirm the public issue and private security-reporting paths
- [ ] Record rollback owner and decision trigger

Git releases use the same base Semantic Version across Python, Codex, and
Claude. A temporary `+codex.<timestamp>` suffix may be used only to refresh a
personal local Codex cache; it must not be tagged or published.
