# Contributing

Light the Candle is in public beta. File an issue before starting a material
change so product, security, and compatibility boundaries are agreed first.
Contributions are accepted under the repository's Apache-2.0 license.

## Development environment

- Python 3.10 or newer
- Git
- Codex CLI for Codex packaging validation
- Claude Code for Claude marketplace validation

The runtime has no third-party Python dependencies. Do not add a dependency
without documenting why the standard library and current repository patterns
are insufficient.

## Required checks

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/ltc-pycache python3 -m py_compile scripts/ltc.py src/lightthecandle/*.py
python3 "$CODEX_HOME/skills/.system/plugin-creator/scripts/validate_plugin.py" .
python3 "$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py" skills/lightthecandle
claude plugin validate --strict .
jq -e . .codex-plugin/plugin.json .claude-plugin/*.json .agents/plugins/marketplace.json schemas/*.json src/lightthecandle/policies/*.json
```

Add focused tests for behavior changes. Safety, persistence, schema, migration,
execution, provider, and permission changes require adversarial tests and a
threat-model update.

## Pull requests

- Keep changes scoped and explain the user-visible behavior.
- Preserve preview-before-write behavior and fail closed on unknown schemas.
- Do not commit generated artifacts, local ledgers, credentials, private data,
  or machine-specific paths.
- Do not silently weaken policy or broaden agent authority.
- Record exact validation commands and results.

Security reports follow `SECURITY.md`, not the public issue tracker.
