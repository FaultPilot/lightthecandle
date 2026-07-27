# Agent Adapters

## Contract

Light the Candle is an agent-neutral kernel with thin presentation adapters.
Every supported agent must call the bundled `scripts/ltc.py` entry point and
use the same project and machine-local state:

- `.lightthecandle/project.json`: portable project intent
- `$LTC_HOME/state.sqlite`: local registration and integrity ledger
- `src/lightthecandle/policies/`: versioned profile policy

An adapter may translate invocation syntax and resolve its installation root.
It must not duplicate policy, reinterpret structured output as authority, or
create its own project memory.

## Supported surfaces

| Surface | Manifest | Invocation | Plugin root |
| --- | --- | --- | --- |
| Codex | `.codex-plugin/plugin.json` | `$lightthecandle` | Root containing the loaded skill |
| Claude Code | `.claude-plugin/plugin.json` | `/lightthecandle:lightthecandle` | `${CLAUDE_PLUGIN_ROOT}` |

The shared skill is `skills/lightthecandle/SKILL.md`. The two manifests contain
only identity and presentation metadata. Version 0.1.3 intentionally ships no
hooks, MCP servers, background monitors, provider credentials, or automatic
execution.

## Installation

Validate a clone without installing it:

```bash
python3 scripts/ltc.py profiles --json
claude plugin validate --strict .
claude --plugin-dir .
```

Install the clone as a local Codex marketplace:

```bash
codex plugin marketplace add /path/to/lightthecandle
codex plugin add lightthecandle@lightthecandle
```

Install the clone as a local Claude Code marketplace:

```bash
claude plugin marketplace add /path/to/lightthecandle
claude plugin install lightthecandle@lightthecandle
```

After the repository is hosted, use the tag-pinned commands in
`public-beta.md`. Claude Code copies installed plugins into its cache, so every
plugin-supplied runtime asset must remain inside this repository. Python and
optional Git are host prerequisites documented in `public-beta.md`.

See `distribution.md` for the distinction between Git distribution, ChatGPT
workspace sharing, and public-directory publication.

## Current limitation

Cross-agent compatibility does not mean cross-agent concurrency or shared
remote memory. Version 0.1.3 lets Codex and Claude Code operate the same local
project contract. Claims, leases, remote history, conflict handling, handoff
bundles, and coordinated agent execution remain roadmap work and require
separate threat modelling and tests.
