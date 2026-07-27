# Light the Candle Engineering Guidance

## Product boundary

Light the Candle is a project-neutral virtual executive and software
engineering organisation. It must not depend on FaultPilot, gimmebackmyson,
Aaron-specific paths, private vaults, or provider credentials.

## Architecture

- Keep deterministic mechanics in the portable CLI and kernel.
- Keep agent skills thin and free of authoritative state.
- Keep project manifests portable, non-secret, and machine-path independent.
- Put provider behavior behind capability-scoped adapters.
- Treat memory as advisory and evidence as subject-bound.
- Version every persisted schema and preserve replay compatibility.

## Safety

- Preview before mutation.
- Status and doctor remain read-only.
- Do not add arbitrary shell, provider writes, hooks, deployments, database
  writes, or automatic updates without a threat-model update and adversarial
  tests.
- Do not store secrets, credentials, or raw production data.
- Unknown schema versions fail closed without mutation.
- Self-evolution produces reviewed proposals; it never silently changes goals,
  lowers policy, grants capabilities, spends, publishes, or modifies
  production.

## Validation

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/ltc-pycache python3 -m py_compile scripts/ltc.py src/lightthecandle/*.py
python3 "$CODEX_HOME/skills/.system/plugin-creator/scripts/validate_plugin.py" .
python3 "$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py" skills/lightthecandle
claude plugin validate --strict .
jq -e . .codex-plugin/plugin.json .claude-plugin/*.json .agents/plugins/marketplace.json schemas/*.json src/lightthecandle/policies/*.json
```

Start narrow, then run the entire suite before release.
