# AlpheusCEF: Phased Execution Plan

**Date**: 2026-03-05
**Source of truth**: STATE.md (design), FUTURE.md (horizons)

---

## Phase 1: Core Engine

The minimum viable system: create nodes, list them, validate them. Everything runs locally, no services required.

### 1.1 Project Scaffolding

- [ ] Create `alph` repo (separate from `overview`)
- [ ] Poetry init with Python 3.12+, pytest, mypy (strict), jsonschema, PyYAML
- [ ] Configure mypy strict mode, pytest with BDD-style conventions
- [ ] Set up pre-commit hooks (mypy, ruff)
- [ ] Add `.claude/CLAUDE.md` with TDD/type-safety rules
- [ ] Add tdd-guardian and py-enforcer agents

### 1.2 Schema and Validation (core.py)

TDD from here on. RED-GREEN-REFACTOR for every function.

- [ ] Define node JSON Schema (v1): `schema_version`, `id`, `timestamp`, `source`, `node_type`, `context`, `creator` (required) + `related_to`, `tags`, `meta` (optional)
- [ ] Define registry schema: `id`, `name` (optional), `context`, pools map
- [ ] `validate_node(frontmatter: dict) -> ValidationResult` -- validates a single node against schema
- [ ] `validate_pool(pool_path: Path) -> ValidationResult` -- validates all nodes in snapshots/ and pointers/
- [ ] `validate_registry(config: dict) -> ValidationResult` -- validates registry structure (valid paths, no duplicate pool names, required fields)
- [ ] `extract_frontmatter(text: str) -> dict | None` -- parse YAML frontmatter from Markdown

### 1.3 Node Creation (core.py)

- [ ] `generate_id(timestamp: str, source: str, context: str) -> str` -- deterministic sha256[:12]
- [ ] `check_idempotency(pool_path: Path, node_id: str) -> ExistingNode | None` -- detect duplicate by ID, return creator and timestamp if exists
- [ ] `create_node(pool_path, source, node_type, context, creator, content, tags, related_to, meta) -> NodeResult` -- write Markdown file to snapshots/ or pointers/, return path and ID
- [ ] Auto-commit logic: if `auto_commit: true` in config, `git add` + `git commit` with message `alph: add <type> node <id>`
- [ ] No auto-pull, no auto-push

### 1.4 Config System (core.py)

- [ ] `load_config() -> AlphConfig` -- merge global (~/.config/alph/config.yaml) + pool (.alph/config.yaml) + CLI overrides
- [ ] Config fields: `creator` (email), `auto_commit`, `default_registry`, `default_pool`, registry declarations
- [ ] Secrets loading from `~/.config/alph/secrets.yaml` (separate, gitignored)

### 1.5 Registry and Pool Init (core.py)

- [ ] `init_registry(path, id, name, context) -> RegistryResult` -- create config with registry declaration, validate, print what was created
- [ ] `init_pool(registry_path, name, context, layout, path_or_remote) -> PoolResult` -- create pool directory (snapshots/, pointers/, .alph/), register in config, validate, print defaults
- [ ] Both commands validate their own output before reporting success

### 1.6 Query Commands (core.py)

- [ ] `list_nodes(pool_path, sort_by, filter_tags) -> list[NodeSummary]` -- list nodes with frontmatter fields
- [ ] `show_node(pool_path, id_or_context) -> NodeDetail` -- full node display, formatted for terminal

### 1.7 CLI Wrapper (cli.py)

Thin Click/Typer wrapper calling core.py functions:

- [ ] `alph registry init` -- create registry
- [ ] `alph pool init --name <name>` -- create pool
- [ ] `alph add -c "context text"` / `alph a -c "text"` -- create node
- [ ] `alph list` / `alph l` -- list nodes
- [ ] `alph show <id-or-context>` / `alph s <id>` -- show node
- [ ] `alph validate` -- run validator

### 1.8 Timeline State

- [ ] `.timeline-state.json` in each pool: last_loaded, per-node last_verified, sync history
- [ ] `load_state(pool_path) -> TimelineState`
- [ ] `update_state(pool_path, state) -> None`

### Phase 1 Exit Criteria

- All core.py functions have passing tests (100% of production code written test-first)
- mypy strict passes with zero errors
- `alph registry init` + `alph pool init` + `alph add` + `alph list` + `alph show` + `alph validate` all work end-to-end
- A user can create a registry, create a pool, add fixed and live nodes, list them, show them, and validate the structure

---

## Phase 2: Distribution and MCP

The system becomes usable by LLMs and installable by others.

### 2.1 Homebrew Distribution

- [ ] Create GitHub org tap repo
- [ ] Write Homebrew formula for `brew install alph`
- [ ] CI pipeline to publish on release

### 2.2 MCP Server (mcp_server.py)

FastMCP 3.x wrapper exposing core.py as MCP tools:

- [ ] One tool per core function (following Basic Memory pattern)
- [ ] Detailed docstrings on every tool
- [ ] MCP annotations: `readOnlyHint`, `destructiveHint`, `idempotentHint`
- [ ] Dual output: `text` (human-readable) + `json` (structured)
- [ ] Overwrite guard on write operations

### 2.3 Claude Skill (SKILL.md)

- [ ] Write thin SKILL.md that orients Claude to use MCP tools
- [ ] Install at user level: `~/.claude/skills/context-architect/SKILL.md`
- [ ] Covers: pool discovery, node search, live node resolution, timeline synthesis, state awareness, cross-pool context

### 2.4 Cross-Pool References

- [ ] Within pool: `"node_id"`
- [ ] Across pools: `"pool_name::node_id"`
- [ ] Across registries: `"registry_id::pool_name::node_id"`
- [ ] Cross-cutting pools: `cross_cutting: true` auto-included when loading any sibling

### 2.5 Repo Separation

- [ ] Move `overview/` to standalone documentation repo for the framework ecosystem
- [ ] `alph` CLI/core in its own repo
- [ ] MCP server package (or bundled with CLI)

### 2.6 CI/CD

- [ ] GitHub Actions: validate nodes on push/PR (updated workflow, Python 3.12+)
- [ ] GitHub Actions: run test suite, mypy, ruff on alph repo

### Phase 2 Exit Criteria

- `brew install alph` works
- Claude can use alph via MCP tools (add, list, show, validate)
- Cross-pool references resolve correctly
- Repos are separated: overview (docs), alph (code)

---

## Phase 3: Input Adapters

Zero-friction context capture from wherever you already are.

### 3.1 Gateway Function Pattern

- [ ] Define the universal adapter interface: raw input -> small LLM -> clean Markdown + YAML
- [ ] Implement as a reusable function that all adapters call

### 3.2 Slack Adapter (P0)

- [ ] Slash command or emoji reaction to pin a thread as a node
- [ ] Route to correct pool via thread context or explicit pool tag
- [ ] Uses gateway function to standardize content

### 3.3 Google Docs Adapter (P1)

- [ ] Live node creation from Google Doc URL
- [ ] Provider hint for resolution via Google Docs MCP

### 3.4 Jira Adapter (P1)

- [ ] Live node creation from Jira ticket URL/key
- [ ] Provider hint for resolution via Jira MCP

### 3.5 Email Adapter (P1)

- [ ] Forwarding address per pool (or single address with subject-tag routing)
- [ ] Gateway function parses email into node

### Phase 3 Exit Criteria

- At least Slack + one other adapter working
- All adapters produce schema-compliant nodes
- Gateway function pattern proven and reusable

---

## Phase 4: Scale and Intelligence

When the volume of nodes makes simple scanning insufficient.

### 4.1 Live Node Resolution at Scale

- [ ] Cached resolution with TTL
- [ ] Background refresh (pre-resolve live nodes on schedule)
- [ ] Freshness checks (verify live nodes still exist in external systems)
- [ ] Fetch-current-all mode for on-demand full resolution

### 4.2 Collection Resolution

- [ ] `resolves_to: collection` query returns a set of results
- [ ] Freshness checks detect new/removed collection members
- [ ] Natural refactoring path from single live pointer to collection query

### 4.3 Temporal Views

- [ ] Milestone markers (explicit milestone nodes or git tags)
- [ ] "What changed between A and B" queries
- [ ] Decay/relevance weighting (configurable, foundational nodes exempt)

### 4.4 Pool Interconnection

- [ ] Registry-level index mapping cross-pool references
- [ ] Ripple mechanism: flag downstream pools when cross-cutting nodes change

### 4.5 GraphRAG (when volume demands it)

- [ ] Index pool into graph (LlamaIndex or similar)
- [ ] `related_to` becomes explicit graph edges
- [ ] Vector embeddings for semantic search
- [ ] Seamless transition: same Markdown files, graph is derived

### Phase 4 Exit Criteria

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

## Development Principles (All Phases)

- **TDD non-negotiable**: RED-GREEN-REFACTOR. No production code without a failing test first.
- **BDD test style**: pytest, behavior-driven naming
- **Type safety**: mypy strict, full type hints, immutable data patterns
- **Pure core**: core.py has no framework dependencies. All logic lives there.
- **Thin wrappers**: cli.py and mcp_server.py are translation layers only
- **Schema versioned**: `schema_version` in every node from day one
- **Git-native**: leverage git for versioning, diffs, blame, search, Actions

---

## Quick Reference: What Goes Where

| Artifact | Repo | Phase |
|----------|------|-------|
| STATE.md, FUTURE.md, PLAN.md, transcripts | overview | Now |
| core.py, cli.py, tests/ | alph | Phase 1 |
| mcp_server.py | alph | Phase 2 |
| SKILL.md | alph (installed to ~/.claude/) | Phase 2 |
| Homebrew formula | tap repo (GitHub org) | Phase 2 |
| Input adapters | alph or separate repos | Phase 3 |
| GraphRAG integration | alph | Phase 4 |
