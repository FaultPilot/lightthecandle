# Distribution

Light the Candle supports three distinct distribution paths. They are not
interchangeable.

## Git marketplace

Use this for friends, private beta testers, teams using different ChatGPT
workspaces, and command-line installation. The repository contains both:

- `.agents/plugins/marketplace.json` for Codex and ChatGPT plugin hosts
- `.claude-plugin/marketplace.json` for Claude Code

After the repository has a Git URL and release tag, a Codex user can install
the tag-pinned beta with:

```bash
codex plugin marketplace add FaultPilot/lightthecandle --ref lightthecandle--v0.1.3
codex plugin add lightthecandle@lightthecandle
```

A Claude Code user can install the same repository with:

```bash
claude plugin marketplace add \
  https://github.com/FaultPilot/lightthecandle.git#lightthecandle--v0.1.3
claude plugin install lightthecandle@lightthecandle
```

Use a private repository only when every tester has repository access and their
Git credentials can clone it.

## ChatGPT workspace sharing

The ChatGPT desktop app can share a locally created plugin only with members or
groups in the same ChatGPT workspace. The generated link remains inside that
workspace and does not publish the plugin publicly. Workspace policy can
disable this feature.

Do not send a `codex://` local-plugin link to a friend as an installation link.
It identifies a marketplace file on the originating computer and is useful
only for opening that computer's local plugin detail or share flow.

## Public Plugins Directory

A public ChatGPT installation link requires publication through OpenAI's
plugin submission and review process. A skills-only plugin is eligible, but a
submission needs a verified publisher identity, production listing assets and
legal/support URLs, starter prompts, and reproducible positive and negative
test cases.

Keep Git distribution as the private-beta channel. Submit to the public
directory only after the product claims, security model, documentation,
fixtures, support path, and release process are ready for unknown users.

## Release version policy

Tagged releases use one base Semantic Version in Python, Codex, Claude Code,
the changelog, and tag. The tag format is
`lightthecandle--v<version>`.

A `+codex.<timestamp>` suffix is a local-development cachebuster only. It may be
used temporarily to refresh a personal Codex installation but must not appear
in a public tag.

A Git tag is only as stable as the repository controls around it. Each public
release records the resolved commit SHA and uses a protected tag; the install
syntax alone does not provide cryptographic immutability.

Use `public-beta.md` for tested install, update, verification, and uninstall
commands. Use `release-checklist.md` before any external publication.
