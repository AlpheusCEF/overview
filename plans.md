# AlpheusCEF: Plans

What we're planning to build next, organized by priority and horizon.

**Prerequisite reading**: [planned.md](planned.md) for completed work, [STATE.md](STATE.md) for design

---

## Suggested Sequence

```
1. Barrel CLI              <- cache, timeline, export (next up)
2. Search (alph + barrel)  <- shallow node search + deep cached content search
3. Gateway function        <- adapter foundation, then pause
```

Barrel is next — it subsumes hydration caching, timeline state ("what's new"), and fin-cli export (C.5). Search builds on barrel for the deep tier. Gateway is the last item before we pause active development.

---

## Near Term: Known Needs

### Barrel CLI — hydration cache + timeline + export

**Priority: Next up.** The barrel is a per-pool cache of hydrated live node content. It subsumes three previously separate items:

1. **Hydration caching** — deterministic cache with TTL, delta fetch, consistent frontmatter
2. **Timeline state** — "what's new since I last looked" (barrel already tracks `cached_at` per node; adding `last_read` gives the delta)
3. **Export** — cached content is already markdown; `barrel export` gives fin-cli C.5 for free

Currently Claude manages the barrel via prose instructions in CLAUDE.md, but LLM-directed file I/O is not reliable enough for cache management. A thin CLI moves the mechanical parts into deterministic code while leaving synthesis intelligence with Claude.

**Why Claude can't reliably do this alone:**

- **TTL math**: Comparing ISO timestamps and deciding "is this more than 4h old" is error-prone for an LLM. Sometimes it gets the math wrong, sometimes it misjudges timezone offsets.
- **Frontmatter fidelity**: Writing YAML frontmatter with exact fields, exact format, every time is inconsistent across sessions. Fields get renamed, formats drift.
- **Delta append**: For append-only types like Slack, correctly reading a cursor timestamp, fetching only newer content, appending without duplication, and updating the cursor requires mechanical precision.
- **Cross-session consistency**: Different Claude sessions may write barrel files in slightly different formats, breaking assumptions of the next session.

**What the barrel CLI handles (mechanical bookkeeping):**

```bash
# Check if a node's cache is fresh
barrel check <pool> <node_id>
# Returns: fresh | stale | missing  (+ age, TTL, content_type)

# Write/update a cache entry with correct frontmatter
barrel write <pool> <node_id> --content-type <type> < content.md
# Writes <pool>/barrel/<node_id>.md with standardized frontmatter

# Append to a delta-mode cache entry (e.g., Slack)
barrel append <pool> <node_id> --cursor <timestamp> < new_content.md
# Appends content, updates cached_through in frontmatter

# Show cache status for a pool
barrel status <pool>
# Table: node_id, content_type, cached_at, age, TTL, fresh/stale, read status

# What's changed since last read
barrel new <pool>
# Shows nodes with content newer than last_read timestamp

# Mark pool as read (update last_read cursor)
barrel mark-read <pool>

# Force refresh (delete cache entry so next hydration re-fetches)
barrel invalidate <pool> [<node_id>]
# Without node_id: invalidate entire pool cache

# Flush (delete all barrel files)
barrel flush <pool>

# Export cached content
barrel export <pool> [--format md|json|yaml]
# Dumps all cached hydrated content (subsumes fin-cli C.5)
```

**What stays with Claude (intelligence):**

- Deciding which nodes to hydrate
- Fetching content via MCP servers or CLI tools (mdsync, etc.)
- Piping fetched content into `barrel write`
- Interpreting `barrel check` output to decide fetch vs. use-cache
- Synthesizing cached content into answers
- Reporting cache status to the user

**Config (in hydration.yaml, registry-scoped):**

```yaml
barrel:
  default_ttl: 4h
  types:
    snapshot:
      ttl: forever
      fetch_mode: full
    gdoc:
      ttl: 4h
      fetch_mode: full
    confluence:
      ttl: 4h
      fetch_mode: full
    jira:
      ttl: 2h
      fetch_mode: full
    slack:
      ttl: 1h
      fetch_mode: delta
```

**Cache file format (standardized by CLI, not Claude):**

```yaml
---
node_id: 48a537fb104f
content_type: slack
cached_at: 2026-03-16T14:30:00+00:00
cached_through: 2026-03-16T14:30:00+00:00
fetch_mode: delta
---
<hydrated content as markdown>
```

**Pool-level metadata (`<pool>/barrel/.barrel-meta.yaml`):**

```yaml
last_read: 2026-03-16T14:30:00+00:00
```

**Implementation:** `alph barrel` subcommand in alph-cli. Ships with alph, no separate install. Shorthand aliases: `alph bar` and `alph b`. Reads hydration.yaml for TTL config, writes to `<pool>/barrel/`, gitignored.

**Claude hooks / commands:** After barrel CLI exists, Claude instructions can call `barrel check` before hydrating and `barrel new` to answer "what's changed." A Claude Code hook could auto-run `barrel status` at session start when cwd is inside a registry, giving Claude immediate cache awareness.

**Interim state (current):** Claude uses a simplified model — if a barrel file exists, use it; user says "barrel refresh" to force re-fetch. No TTL math, no delta append. This works but puts all freshness decisions on the user.

**Exit criteria:**

- `barrel check` reliably compares timestamps against TTL
- `barrel write` produces consistent frontmatter every time
- `barrel append` handles delta cursor correctly for Slack
- `barrel status` gives clear view of cache state
- `barrel new` shows what's changed since last read
- `barrel export` dumps cached content in multiple formats
- Claude instructions updated to call barrel CLI instead of managing files directly

---

### Search — two tiers

Two complementary search commands at different depths:

**`alph search "keyword"`** — shallow, node-level
- Grep across node frontmatter (context, tags, meta) and body text
- Works on the node files themselves — no barrel needed
- Fast, always available, answers "do I have a node about X?"

**`barrel search "keyword"`** — deep, hydrated content
- Grep across cached barrel content (the actual resolved live content)
- Only searches what's been hydrated — barrel must exist
- Answers "does any of my source material mention X?"
- Useful for finding things buried in a 50-page design doc or a week of Slack messages

Both return node IDs, context summaries, and matching excerpts. Claude can use either depending on whether it needs node-level or content-level results.

**Implementation:** Both are structured grep — walk files, parse frontmatter, match against query. No indexing, no embeddings. Simple and deterministic.

---

### Lightweight task views in alph

Rather than building task awareness only in fin-cli, a lightweight `alph task` subcommand:

- `alph task add "do the thing"` — creates snapshot node with `content_type: task`
- `alph task list` — filters for task-typed nodes
- fin-cli remains the power-user experience (editor, recurrence, dependencies)
- Keeps alph useful for task tracking even without fin installed

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

### Human-readable filenames

`2026-03-05-a1b2c3d4e5f6-token-rotation-decision.md` vs `a1b2c3d4e5f6.md`. Opt-in via config (`readable_filenames: true`). Requires slugification, truncation (~500 char cap), unicode handling.

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

---

## Phase 4: Scale and Intelligence

When volume makes simple scanning insufficient.

### Live node resolution at scale

- ~~Cached resolution with TTL~~ → **Barrel CLI** (moved to Near Term)
- Background refresh (pre-resolve live nodes on schedule — builds on barrel)
- Freshness checks (verify live nodes still exist — builds on barrel)
- Fetch-current-all mode → barrel refresh

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

- **Input adapters** — foundation not ready (no gateway function). Build foundation first
- **GraphRAG** — premature until hundreds of nodes with rich `related_to` edges
- **Multi-LLM frontends** — Claude MCP works; others can wait until schema stabilizes
