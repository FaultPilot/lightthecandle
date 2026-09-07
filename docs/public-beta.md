# Public Beta

## Status

Version 0.1.3 is a project-adoption and readiness foundation. It is not an
autonomous engineering organisation, certification product, hostile-code
sandbox, or production control plane.

## Compatibility

| Surface | Beta support |
| --- | --- |
| Operating system | macOS and Linux |
| Python | 3.10 or newer |
| Codex | Tested with Codex CLI 0.145.0; older plugin hosts are unsupported |
| Claude Code | Tested with Claude Code 2.1.207; older plugin hosts are unsupported |
| Git | Optional for plain folders; required for Git marketplace installation and Git discovery |
| Windows | Not yet in the supported beta boundary |

The runtime has no third-party Python dependencies.

## Install a tag-pinned beta

Codex:

```bash
codex plugin marketplace add FaultPilot/lightthecandle --ref lightthecandle--v0.1.3
codex plugin add lightthecandle@lightthecandle
codex plugin list --json
```

Claude Code:

```bash
claude plugin marketplace add \
  https://github.com/FaultPilot/lightthecandle.git#lightthecandle--v0.1.3
claude plugin install lightthecandle@lightthecandle
claude plugin details lightthecandle@lightthecandle
```

Start a new Codex thread or restart Claude Code after installation.

These commands select a release tag, not a cryptographic identity. Before
publication, maintainers record the tag's resolved commit SHA and protect the
tag against changes. Testers who need stronger provenance should verify the
resolved commit with the release notes.

## First safe use

Run a preview against a disposable or already-backed-up project:

```bash
python3 <plugin-root>/scripts/ltc.py adopt /path/to/project \
  --profile quality \
  --goal "State the intended purpose" \
  --outcome "State one observable outcome" \
  --json
```

Review the proposed manifest and issues. Add `--apply` only after the target,
strategy, profile, and data are acceptable.

## Move to a newer beta

A marketplace configured at one release tag remains pinned to that tag. Replace
the installed plugin and marketplace to select the next published tag. Set
`VERSION` to that release first, for example `0.1.4`.

Codex:

```bash
VERSION=0.1.4
codex plugin remove lightthecandle@lightthecandle
codex plugin marketplace remove lightthecandle
codex plugin marketplace add FaultPilot/lightthecandle \
  --ref "lightthecandle--v${VERSION}"
codex plugin add lightthecandle@lightthecandle
```

Claude Code:

```bash
VERSION=0.1.4
claude plugin uninstall lightthecandle@lightthecandle --scope user
claude plugin marketplace remove lightthecandle
claude plugin marketplace add \
  "https://github.com/FaultPilot/lightthecandle.git#lightthecandle--v${VERSION}"
claude plugin install lightthecandle@lightthecandle --scope user
```

## Uninstall

Remove the plugin and marketplace:

```bash
codex plugin remove lightthecandle@lightthecandle
codex plugin marketplace remove lightthecandle
claude plugin uninstall lightthecandle@lightthecandle --scope user
claude plugin marketplace remove lightthecandle
```

Uninstalling does not delete `.lightthecandle/project.json` or `$LTC_HOME`.
Read `PRIVACY.md` before deleting shared local state.

## Known limitations

- No remote or cross-machine authoritative history
- No lifecycle transition engine, recovery engine, worker orchestration, or
  autonomous execution
- No provider writes, deployments, database actions, or command execution
- No signed or externally anchored evidence
- No compatibility promise for prerelease schemas without an explicit
  migration
- Rigor profiles define readiness expectations; they are not assurance,
  compliance, certification, or proof that checks ran
- A hostile process running as the same OS user may race pathname-based SQLite
  access; the private-directory checks are a cooperative-local control, not
  hostile-process isolation

Use synthetic data in reports and follow `SUPPORT.md` and `SECURITY.md`.
