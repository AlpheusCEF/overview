# AlpheusCEF Overview

Design documentation for the Alpheus Context Engine Framework.

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
