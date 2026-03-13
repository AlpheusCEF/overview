# AlpheusCEF: Plans

What we're planning to build next, organized by priority and horizon.

**Prerequisite reading**: [planned.md](planned.md) for completed work, [STATE.md](STATE.md) for design

---

## Suggested Sequence

```
1. fin-cli Phase A        <- proves alph-as-library, second consumer (see fin_plan.md)
2. fin-cli Phase B        <- full UX parity, exercises update_node()
3. Timeline state          <- "what's new" queries
4. Gateway function        <- adapter foundation
5. alph search             <- utility as node count grows
```

Steps 1-2 are the critical path and live in [fin_plan.md](fin_plan.md).

---

## Near Term: Known Needs

### Lightweight task views in alph

Rather than building task awareness only in fin-cli, a lightweight `alph task` subcommand:

- `alph task add "do the thing"` — creates snapshot node with `content_type: task`
- `alph task list` — filters for task-typed nodes
- fin-cli remains the power-user experience (editor, recurrence, dependencies)
- Keeps alph useful for task tracking even without fin installed

### Timeline state (`.timeline-state.json`)

Deferred from Phase 1. Becomes useful with two consumers (alph + fin) or any live nodes. Enables: "what's new since I last looked."

- `last_loaded` timestamp per pool
- `last_verified` per live node
- Sync history
- `load_state(pool_path) -> TimelineState`
- `update_state(pool_path, state) -> None`

### Gateway function pattern (adapter foundation)

Before building specific adapters (Slack, Jira, etc.), nail the universal pattern:

- Raw input -> small LLM -> clean Markdown + YAML
- Build as a `core.py` function all adapters call
- Could be exercised first by `alph add --raw` that runs content through the gateway

### Unregistered pool notice

When `alph add --pool /some/path` targets a pool not in any registry:

- Print notice: `notice: pool at /some/path is not registered in any registry`
- Informational, not an error — command still runs
- Suppressible via config: `unregistered_pool_notice: false`

### `alph search` command

As node count grows, `alph list` with tag/status filters won't suffice:

- `alph search "keyword"` — grep across node content and frontmatter
- Walk pool, parse frontmatter + body, match against query
- No GraphRAG needed — just structured grep

### Human-readable filenames

`2026-03-05-a1b2c3d4e5f6-token-rotation-decision.md` vs `a1b2c3d4e5f6.md`. Opt-in via config (`readable_filenames: true`). Requires slugification, truncation (~500 char cap), unicode handling.

### Pool-local `.alph/` directory

Reserved directory inside each pool for pool-local state (last-loaded, resolution cache, per-machine overrides). Wait until timeline state or live node caching gives it a concrete first resident.

---

## Phase 3: Input Adapters

Zero-friction context capture from wherever you already are.

### Gateway function pattern

See Near Term section above. Must land before adapters.

### Slack adapter (P0)

- Slash command or emoji reaction to pin a thread as a node
- Route to correct pool via thread context or explicit pool tag
- Uses gateway function to standardize content

### Google Docs adapter (P1)

- Live node creation from Google Doc URL
- Provider hint for resolution via Google Docs MCP

### Jira adapter (P1)

- Live node creation from Jira ticket URL/key
- Provider hint for resolution via Jira MCP

### Email adapter (P1)

- Forwarding address per pool (or single address with subject-tag routing)
- Gateway function parses email into node

### Phase 3 exit criteria

- At least Slack + one other adapter working
- All adapters produce schema-compliant nodes
- Gateway function pattern proven and reusable
- Timeline state updated on every sync

---

## Phase 4: Scale and Intelligence

When volume makes simple scanning insufficient.

### Live node resolution at scale

- Cached resolution with TTL
- Background refresh (pre-resolve live nodes on schedule)
- Freshness checks (verify live nodes still exist)
- Fetch-current-all mode for on-demand full resolution

### Collection resolution

- `resolves_to: collection` returns a set of results
- Freshness checks detect new/removed members
- Natural refactoring from single live pointer to collection query

### Temporal views

- Milestone markers (git tags or explicit milestone nodes)
- "What changed between A and B" queries
- Decay/relevance weighting (configurable, foundational nodes exempt)

### Pool interconnection

- Registry-level index mapping cross-pool references
- Ripple mechanism: flag downstream pools when cross-cutting nodes change

### GraphRAG (when volume demands it)

- Index pool into graph (LlamaIndex or similar)
- `related_to` becomes explicit graph edges
- Vector embeddings for semantic search
- Seamless transition: same Markdown files, graph is derived

### Phase 4 exit criteria

- Live nodes resolve efficiently at 50+ nodes per pool
- Temporal queries work across milestones
- Cross-pool references tracked at registry level

---

## Phase 5: Ecosystem

The longer horizon. Not committed, but the design supports it.

- Multi-LLM frontends (Claude Skill, Gemini Gem, local models for private pools)
- Context-aware automation (GitHub Actions, Jira webhooks, Slack bots creating nodes autonomously)
- Federation (controlled sharing across registries/teams)
- Browser extension, mobile PWA, meeting bot adapters
- Emergent graph analysis (cluster detection, orphan detection, coupling analysis)

---

## Deferred Provider Work

- **GitLab provider** — REST API (~51 calls for 50 nodes). Wait for a user to need it
- **Bitbucket provider** — same
- **Git fallback provider** — shallow sparse clone for unknown hosts

---

## Open Questions

These don't have answers yet, just tension:

- **Archival**: When does a pool become "done"? Do old pools get archived, compressed, or just left?
- **Conflict resolution**: What when two nodes contradict each other? "Most recent wins" is naive for complex decisions
- **Privacy boundaries**: If global config spans personal and work registries, how to prevent work LLM from surfacing personal context? Registry-level ACLs? Separate configs?
- **Node granularity**: When is something too small/large for a node? Should a 50-page Google Doc be one live node or section-level nodes?
- **Versioning nodes**: Snapshot nodes are immutable, but what if you got the context wrong? New superseding node, or edit in place? Git tracks either way, but schema should have an opinion
- **"So what" layer**: Nodes capture what happened. Should derived insights be first-class nodes?
- **Pool field in frontmatter**: Currently pool membership = file location. Explicit `pool` field helps cross-pool search but creates second source of truth
- **Node `name` field**: Reserved for future. Short slug for human-friendly references
- **Basic Memory as adapter**: A live pointer to a Basic Memory vault with `provider: basic-memory-mcp`
- **Remote node creation**: For serverless/Slack bots — commit via GitHub Contents API without local clone
- **Repomix for live code repos**: `provider: repomix` hint on live nodes for token-optimized repo snapshots
- **`custom:` prefix for content types**: Allow `custom:meeting-notes` without modifying enum. Low priority until real use case

---

## Deprioritized

- **Input adapters** — foundation not ready (no gateway function, no timeline state). Build foundation first
- **GraphRAG** — premature until hundreds of nodes with rich `related_to` edges
- **Additional remote providers** — wait for real user need
- **Multi-LLM frontends** — Claude MCP works; others can wait until schema stabilizes
