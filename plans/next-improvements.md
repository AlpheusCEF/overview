# Next Improvements: Prioritized Recommendations

_Date: 2026-03-13_
_Based on review of: STATE.md, PLAN.md, FUTURE.md, FIN_REWRITE_PLAN.md, plans/content-type-node-system.md_

---

## Tier 1: High Value, High Fit — Do Next

### 1. `update_node()` in alph-cli core

The single most important blocker. Prerequisite for:
- fin-cli Phase B (all mutation operations)
- The `content_type` system (migrating existing nodes)
- Any future workflow where nodes evolve over time

The spec is already written in `FIN_REWRITE_PLAN.md` (Outstanding Items section). Well-scoped, interface defined, fits naturally into `core.py`. Implement TDD-first in alph-cli, release as a patch, unblocks two entire workstreams.

### 2. fin-cli Phase A (Primitive Mapping & Scaffolding)

Phase A is pure creation-time writes and reads — no `update_node()` needed. Proves the concept: tasks as alph nodes, contexts as pools, short-hash IDs. The `alph_interface.py` boundary is well-designed. Gives alph a second real consumer, stress-testing the API surface.

### 3. `content_type` node system

The design in `plans/content-type-node-system.md` is clean and ready for implementation. The missing third leg (source = who, node_type = how, content_type = what). Enables type-specific meta validation. Critical before building any input adapters — `content_type: slack` and `content_type: jira` should exist before those adapters land.

---

## Tier 2: Medium-Term, High Utility — Queue After Tier 1

### 4. Lightweight task views in alph itself

Rather than building task awareness only in fin-cli, consider a lightweight `alph task` subcommand directly in alph:
- `alph task add "do the thing"` creates a snapshot node with `tags: [task, open]`
- `alph task list` filters for task-tagged nodes
- fin-cli remains the power-user experience (editor, recurrence, dependencies)
- Aligns with content_type system: `content_type: task` as a first-class type
- Keeps alph useful for task tracking even without fin installed

### 5. Timeline state (`.timeline-state.json`)

Deferred from Phase 1, becomes useful the moment you have two consumers (alph + fin) or any live nodes. Enables the killer daily query: "what's new since I last looked." Minimum scope: `last_loaded` timestamp per pool, `last_verified` per live node.

### 6. Gateway function pattern (adapter foundation)

Before building specific adapters (Slack, Jira, etc.), nail the universal pattern: raw input -> small LLM -> clean Markdown + YAML. Build as a `core.py` function all adapters call. Could ship in the next alph-cli release and be exercised first by the CLI itself (`alph add --raw` that runs content through the gateway).

---

## Tier 3: Valuable Extensions — When Opportunity Arises

### 7. Unregistered pool notice

Small, self-contained, useful for UX hygiene. Design already in FUTURE.md. Quick win between larger features.

### 8. Human-readable filenames

`2026-03-05-a1b2c3d4e5f6-token-rotation-decision.md` vs `a1b2c3d4e5f6.md`. Matters as pool size grows. Opt-in via config (`readable_filenames: true`). Low risk, real QoL improvement when browsing repos.

### 9. Pool-local `.alph/` directory

Wait until timeline state or live node caching gives it a concrete first resident. Don't create the directory spec until something needs to live there.

### 10. `alph search` command

Not in any current plan, but as node count grows, `alph list` with tag/status filters won't suffice. `alph search "keyword"` that greps across node content and frontmatter fields. Simple implementation: walk pool, parse frontmatter + body, match against query. No GraphRAG needed yet — just structured grep.

---

## Deprioritize

- **Input adapters (Slack, Jira, email)** — Foundation isn't ready: no `content_type`, no gateway function, no timeline state. Build the foundation first.
- **GraphRAG** — Premature until hundreds of nodes with rich `related_to` edges. File-based approach scales far enough.
- **Additional remote providers (GitLab, Bitbucket)** — Wait for a real user to need them.
- **Multi-LLM frontends** — Claude MCP works. Gemini Gem can wait until the schema stabilizes post-content_type.

---

## Suggested Sequence

```
1. update_node()          <- unblocks everything mutable
2. fin-cli Phase A        <- proves alph-as-library, second consumer
3. content_type system    <- structural foundation for adapters
4. fin-cli Phase B        <- needs update_node(), full UX parity
5. timeline state         <- "what's new" queries
6. gateway function       <- adapter foundation
7. alph search            <- utility as node count grows
```

Steps 1-3 can partially overlap since they touch different repos (alph-cli vs fin-cli vs overview). The `update_node()` work is the critical path.
