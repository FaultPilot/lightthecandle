# Changelog

All notable changes are recorded here. Light the Candle follows Semantic
Versioning for tagged releases; pre-1.0 compatibility remains explicitly
limited.

## [0.1.3] - 2026-07-27

### Added

- Public-beta security, privacy, support, contribution, compatibility, and
  release documentation
- GitHub Actions validation and source-distribution smoke coverage
- Reachable Git-history credential scanning for release CI
- Commit-pinned GitHub Actions, Dependabot maintenance, and enforced release
  artifact inventories
- Apache-2.0 licensing and canonical public repository metadata
- Clean JSON argument-error output for agent consumers
- Security tests for local state, Git environment, manifest paths, and
  credential-like values

### Changed

- Local state now rejects relative, shared, non-owned, symlinked, and
  non-private paths
- Project manifest creation uses directory descriptors and no-follow behavior
- Git discovery ignores ambient `GIT_*` path and configuration injection
- Plain-folder discovery now works when Git is not installed
- Strategy, lifecycle, command, and public schemas match runtime validation
- Python source distributions include the plugin contracts, documentation,
  schemas, tests, and packaged policy JSON
- Public claims now distinguish readiness expectations and accidental
  corruption detection from certification or adversarial audit integrity

## [0.1.2] - 2026-07-27

- Added self-contained Codex and Claude Code marketplace distribution
- Documented the vendor-neutral worker and runtime strategy

## [0.1.1] - 2026-07-27

- Added the Claude Code adapter around the shared skill and kernel

## [0.1.0] - 2026-07-27

- Established project adoption, profiles, portable manifests, local
  registration events, status, doctor, and initial tests
