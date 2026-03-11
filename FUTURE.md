# AlpheusCEF: Future Looking

Where the problem goes as it evolves, and where AlpheusCEF might need to follow.

---

## The Near Horizon (Things we know we need)

### Remote Git Registries

> **Status**: Core implementation complete (Phase 2.5). GitHub provider, RO/RW modes, clone management, CLI commands, `--pull` flag, and `--registry` global option all shipped. Remaining work: additional forge providers.

A registry's `pool_home` can be a remote git URL instead of a local path. Two access modes:

**RO (read-only, default for remote registries):** No local clone. Reads pool/node data via forge API (GitHub GraphQL). Zero local state — files fetched to ephemeral tmpdir for core functions that expect `Path` objects. This is the path a future timeline UI would share. **Implemented.**

**RW (read-write, opt-in):** Persistent local clone with `.git`. Required for `add`, `pool init`, and other write operations. Clone location: user-specified `clone_path` or default `~/.cache/alph/clones/<sha256(url)[:12]>/`. Supports `auto_push` after commit. **Implemented.**

Config:
```yaml
registries:
  household:
    pool_home: git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry
    mode: ro              # ro (default for remote) | rw
    branch: seeded        # git branch for RO reads and RW clone checkout (default: HEAD)
    clone_path: ~/regs/h  # only used when mode: rw
    auto_pull: false      # pull --ff-only before read (default: true for rw remote, false for local)
    auto_push: false      # push after commit (default: true for rw remote, false for local)
```

Local registries (`pool_home` is a filesystem path) ignore `mode` — always RW.

URL format: `<git-remote-url>:/<subpath>`. The `:/subpath` suffix scopes the registry to a subdirectory within the repo. Detection: URL starts with `git@`, `ssh://`, `git://`, `http://`, or `https://`.

Provider abstraction for RO reads:
- `GitHubProvider` — GraphQL batch reads (2 API calls for a full pool of 50 nodes) **Implemented.**
- `GitLabProvider` / `BitbucketProvider` — REST APIs (~51 calls for 50 nodes) **Deferred.**
- `GitFallbackProvider` — shallow sparse clone to tmpdir for unknown hosts **Deferred.**

Auth: `GITHUB_TOKEN` / `GH_TOKEN` env vars → `gh auth token`. **Implemented.**

SSH host alias resolution: URLs like `git@github-personal:org/repo.git` are resolved via `~/.ssh/config` to detect the actual forge (e.g., `HostName github.com`). This avoids requiring users to duplicate SSH config knowledge in alph config. **Implemented.**

Ad-hoc CLI usage: `alph --registry git@github.com:Org/repo.git:/path list --pool vehicles` (ephemeral, not persisted to config). **Implemented.**

Commands: `alph registry clone <id>`, `alph registry pull <id>`, `alph registry check <id>`. **Implemented.**

`--pull` flag on `list`, `show`, `validate` pulls latest changes before reading (RW clones only). **Implemented.**

When a user runs a write operation against an RO remote registry, alph errors with: `error: registry is read-only. Set mode: rw in config to enable writes.` **Implemented.**

### Unregistered Pool Notice

When a user runs `alph add --pool /some/path` or `alph list --pool /some/path` against a pool that is not tracked in any registry, alph should print a notice: `notice: pool at /some/path is not registered in any registry`. The notice is informational, not an error — the command still runs. Default behavior: notice enabled (`true`). Suppressible via config key `unregistered_pool_notice: false`.

### Pool-Local State Directory (`.alph/`)

A reserved `.alph/` directory inside each pool is a natural place for pool-local state that should not be committed as nodes — e.g. a last-loaded timestamp, a local resolution cache for live nodes, or a per-machine config override. Nothing is written there yet. Before adding it back, nail down at least one concrete use case so the directory has a reason to exist on day one.

### Pool Interconnection

Right now pools are mostly independent with `related_to` as loose coupling. As pool count grows, the connections between them become the most valuable part. A decision in the `standards` pool ripples into every work pool. A technique discovered in a personal project turns out to apply at work.

The registry handles discovery and the namespaced `related_to` format (`pool_name::node_id`, `registry_id::pool_name::node_id`) provides explicit cross-references. What's still needed:
- A registry-level index that maps which pools reference which other pools
- A "ripple" mechanism: when a cross-cutting node changes, downstream pools are flagged as potentially stale

### Temporal Views

The timeline is implicit right now (sort by timestamp). As pools accumulate hundreds of nodes, raw chronological order stops being useful. We'll need:
- Milestone markers (git tags or explicit milestone nodes) that chunk the timeline into phases
- "What changed between milestone A and milestone B" queries
- Decay/relevance weighting -- a decision from 2 years ago matters less than one from last week unless explicitly marked as foundational

### Input Adapter Ecosystem

The CLI is first. But the real value comes when adding context is zero-friction from wherever you already are:
- Slack bot with slash command (`/ate pool-name`) preferred over reaction-based (faster, more intentional); reaction as fallback for unexpected sources
- Email forwarding address per pool (or a single address with pool routing via subject tags)
- iOS/Android share sheet target (PWA or native) for photos, links, text
- Browser extension for "save this page/selection to pool X"
- Meeting bot that auto-creates a node when a Zoom/Google Meet recording lands

Each adapter is independent, but they all need to produce the same schema. The gateway function pattern (raw input -> small LLM -> clean Markdown + YAML) is probably the universal adapter backbone.

For OAuth-based adapters (Google Docs, etc.), credential lookup follows: cwd -> `~/.config/alph/` -> `~/.<app>/` (mdsync pattern). Google Docs MCP package reference: `@a-bonus/google-docs-mcp`.

### Live Node Resolution at Scale

With a handful of live nodes, MCP calls on demand are fine. With 50 live nodes in a pool, resolving all of them on every load is slow and expensive. This evolves toward:
- Cached resolution with TTL (fetch Jira ticket once, cache for N hours)
- Local caching of resolved content for immediate analysis with staleness indicators
- Background refresh (a cron or Action that pre-resolves live nodes and commits a `last_resolved_content` field)
- Freshness checks that verify live nodes still exist in their external systems
- Fetch-current-all mode that resolves every live node fresh on demand

### Collection Resolution

Live nodes with `meta.resolves_to: collection` need their own resolution logic:
- A collection query returns a set of results, not one document
- Freshness checks need to detect new/removed members, not just content changes
- The transition from a single live pointer to a collection query should be a natural refactoring step as context evolves

---

## The Middle Horizon (Things we can see coming)

### GraphRAG

The YAML frontmatter is already a graph in disguise. `related_to` fields are edges. Tags are implicit groupings. When the volume of nodes makes grep-and-sort insufficient, we index the pool into a proper graph:
- LlamaIndex or similar ingests the Markdown files
- `related_to` becomes explicit edges in a graph DB (Neo4j, or even SQLite with a graph extension)
- Vector embeddings of node content enable semantic search ("find nodes similar to this concern")
- The LLM traverses the graph rather than scanning files

The key insight from the Gemini session: this transition should be seamless. The data doesn't change format. The graph is derived from the same Markdown files. You can always fall back to raw file search.

Reference material for when we get here:
- LlamaIndex GraphRAG v2 cookbook: https://developers.llamaindex.ai/python/examples/cookbooks/graphrag_v2/
- LlamaIndex Knowledge Graph RAG query engine: https://developers.llamaindex.ai/python/examples/query_engine/knowledge_graph_rag_query_engine/
- Microsoft Research GraphRAG (narrative private data): https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/
- Building a GraphRAG pipeline with LlamaIndex (tutorial): https://medium.com/@tuhinsharma121/beyond-rag-building-a-graphrag-pipeline-with-llamaindex-for-smarter-structured-retrieval-3e5489b0062c

### Homebrew Distribution

> **Status**: Complete. `AlpheusCEF/homebrew-tap` ships `brew install alph` (v0.1.24). Includes man page (`man alph`). Release workflow auto-builds sdist; formula updated manually until `HOMEBREW_TAP_TOKEN` is configured.

### Multi-LLM Frontend

Claude gets a Skill. Gemini gets a Gem. But the context is the same underneath. As LLM capabilities diverge, different frontends may be better for different tasks:
- Claude for deep reasoning across a timeline ("why did we make this decision")
- Gemini for rapid search and summarization across many pools
- A local model for private/sensitive pools that can't leave the machine

The pool registry and node schema are LLM-agnostic by design. The core.py logic has no LLM dependency. The Skill/Gem layer is a thin translation on top.

### Context-Aware Automation

Once pools are rich enough, automation starts writing its own nodes:
- A GitHub Action detects a PR merged and creates a fixed node linking to the ADR it implements
- A Jira webhook fires when a ticket transitions and updates the live node's context
- A Slack bot notices a thread got 10+ replies and suggests pinning it as a decision node
- A scheduled job compares live nodes against their sources and flags drift

The system moves from "human feeds Alph" to "Alph notices things and asks if they should be recorded."

---

## The Far Horizon (Things we suspect but can't be sure about)

### The Context Operating System

If AlpheusCEF works, the funnel pattern (registry -> pool -> node) becomes a general-purpose way to give any LLM structured, versioned, queryable memory. Not just for project tracking -- for anything where context accumulates over time and needs to be recalled:
- A "life context" pool that an AI assistant draws from across every conversation
- Organizational knowledge that new team members can "load" on day one
- Research contexts that persist across paper readings, experiments, and discussions

At this point AlpheusCEF is less a tool and more an infrastructure layer -- the way Git is infrastructure for code, AlpheusCEF could be infrastructure for context.

### Federation

Multiple people or teams each maintaining their own registries and pools, with a federation layer that allows controlled sharing:
- "Share this pool read-only with the platform team"
- "Subscribe to the standards pool from the security team's registry"
- "Merge insights from two pools into a third"

This is where the Git foundation pays off -- forking, merging, and access control are already solved problems.

### Emergent Graph Structure

With enough nodes and enough `related_to` edges, patterns emerge that nobody explicitly designed:
- Clusters of highly connected nodes reveal the actual centers of gravity in a project (not what the project plan says matters, but what actually generated the most context)
- Orphan nodes with no edges reveal forgotten or disconnected work
- Cross-pool edge density reveals which projects are actually coupled (regardless of org chart)

The graph becomes a diagnostic tool for how knowledge actually flows in an organization or a life.

---

## Open Questions

These don't have answers yet, just tension:

- **Archival**: When does a pool become "done"? Do old pools get archived, compressed, or just left? Does a closed pool's standards content get promoted to a cross-cutting pool?
- **Conflict resolution**: What happens when two nodes in the same pool contradict each other? Right now "most recent wins" but that's naive for complex decisions with multiple dimensions.
- **Privacy boundaries**: If a global config spans personal and work registries, how do you prevent a work LLM session from accidentally surfacing personal context? Registry-level ACLs? Separate configs? Both?
- **Node granularity**: When is something too small to be a node? Too large? Should a 50-page Google Doc be one live node, or should it be broken into section-level nodes?
- **Versioning nodes**: A fixed node is immutable, but what if you got the context wrong? Do you create a new node that supersedes it, or edit in place? Git tracks the edit either way, but the schema should have an opinion.
- **The "so what" layer**: Nodes capture what happened. But the real value is "so what does this mean for the decision we're making right now." That's the LLM's job today, but should the system itself track derived insights as first-class nodes?
- **Pool field in frontmatter**: Currently pool membership is determined by file location. An explicit `pool` or `origin_pool` field in frontmatter would help with cross-pool search results, promoted/copied nodes, and human readability -- but creates a second source of truth that can conflict with file location. Consider adding when cross-pool operations become common.
- **Node `name` field**: Reserved for future use. Nodes currently use `id` as machine identifier and `context` as human-readable text. A `name` field (short slug) may be useful if nodes need to be referenced by human-friendly handles.
- **Basic Memory as input adapter**: A Basic Memory vault is a directory of structured Markdown. A live pointer to a specific memory bank (with `provider: basic-memory-mcp`) is a natural adapter.
- **Remote node creation (no local clone)**: The core CLI assumes a local checkout. For scenarios where no clone exists (serverless functions, Slack bots, PWA gateways), input adapters can commit directly via the GitHub Contents API. This was prototyped in the design phase (`commit_node_remote.py`) and should be revisited when building adapters that run outside a local environment.
- **Human-readable filenames**: Include a slugified context in the filename (e.g., `2026-03-05-a1b2c3d4e5f6-token-rotation-decision.md`). Requires slugification logic, truncation (~500 char cap), unicode handling. Add as opt-in config when browsing repos feels painful in practice.
- **Repomix for live code repository nodes**: [Repomix](https://github.com/yamadashy/repomix) packs an entire repository into a single LLM-friendly file. A live node pointing at a code repo could use repomix as a resolution strategy — instead of resolving to raw git content, resolve via `repomix` to produce a consolidated, token-optimized snapshot of the repo (or a scoped subset). Useful for "give the LLM this whole codebase as context" workflows. Could be a `provider: repomix` hint on live nodes with `resolves_to: single` (whole-repo pack) or `collection` (multi-path pack).
