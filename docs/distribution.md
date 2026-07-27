# Distribution

Light the Candle supports three distinct distribution paths. They are not
interchangeable.

## Git marketplace

Use this for friends, private beta testers, teams using different ChatGPT
workspaces, and command-line installation. The repository contains both:

- `.agents/plugins/marketplace.json` for Codex and ChatGPT plugin hosts
- `.claude-plugin/marketplace.json` for Claude Code

After the repository has a Git URL, a Codex user can install it with:

```bash
codex plugin marketplace add owner/repository
codex plugin add lightthecandle@lightthecandle
```

A Claude Code user can install the same repository with:

```bash
claude plugin marketplace add owner/repository
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
