# AlpheusCEF Overview

Design documentation for the Alpheus Context Engine Framework.

## Quickstart

```bash
brew tap AlpheusCEF/tap
brew install alph
alph skill install         # Claude Code skill + MCP server config
alph registry init --pool-home ~/my-context --id my-reg --context "My stuff"
alph add -c "First node"   # creator auto-detected from system username
```

After `alph skill install`, Claude Code can use alph via MCP tools and
knows how to hydrate live nodes, manage the barrel cache, and synthesize
answers from pool content.

## Docs

- [STATE.md](STATE.md) — full design and current status
- [planned.md](planned.md) — completed work with details
- [plans.md](plans.md) — future alph plans and open questions
- [fin_plan.md](fin_plan.md) — fin-cli rewrite plan (separate track)

## Repos

| Repo | Purpose |
|------|---------|
| `overview` | This repo — design docs, no code |
| `alph-cli` | CLI and core engine (Phase 1+) |
| `agents` | Shared Claude Code agents and instructions |

## Agents and Claude config

All repos share agents via symlinks into the `agents` repo. See [agents.md](agents.md) for how it's wired.

Adding a future repo (e.g. an MCP server): copy the 5-line shell block from [agents/agents.md](../agents/agents.md) and run it.
