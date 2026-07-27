# Data Handling

## Version 0.1 behavior

The Light the Candle Python kernel has no telemetry, analytics, advertising,
hosted service, provider API client, or automatic network request. It invokes
local Git commands for read-only discovery when Git is available.

The surrounding Codex or Claude Code host may send conversation and repository
context to its provider under that provider's settings and terms. Installing
Light the Candle does not change that host-level behavior.

## Data written

`.lightthecandle/project.json` is portable project state intended to be
reviewable and, when appropriate, committed to version control. It can contain:

- project name, type, description, and strategy text
- outcomes, measures, assumptions, and constraints
- discovered command argument arrays and technology labels
- read-only provider and Git capability fingerprints

`$LTC_HOME/state.sqlite`, defaulting to `~/.lightthecandle/state.sqlite`, is
machine-local. It contains canonical local project paths, manifest hashes,
actor identifiers, registration reasons, timestamps, and hash-chained events.
On POSIX systems, Light the Candle requires the state directory and database
to be private to the current user.

## User responsibility

The credential detector is a safety heuristic, not a data-loss-prevention
system. Do not enter secrets, tokens, passwords, private keys, personal data,
client-confidential information, regulated data, or raw production data.

Review every preview before `--apply`. Treat the portable manifest as shareable
with anyone who can read the repository.

## Retention and deletion

Uninstalling the Codex or Claude Code plugin does not delete project manifests
or `$LTC_HOME`. Version 0.1 has no selective forget or export command.

To remove data, first identify every project that depends on the local ledger,
back up anything that must be retained, and then remove the relevant project
manifest or local state using normal operating-system tools. Deleting the
shared SQLite ledger removes the local registration history for every adopted
project on that machine.
