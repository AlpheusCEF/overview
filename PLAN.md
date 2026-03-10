# AlpheusCEF: Phased Execution Plan

**Date**: 2026-03-10
**Source of truth**: STATE.md (design), FUTURE.md (horizons)

---

## Phase 1: Core Engine (Complete)

The minimum viable system: create nodes, list them, validate them. Everything runs locally, no services required.

### 1.1 Project Scaffolding

- [x] Create `alph` repo (separate from `overview`)
- [x] Poetry init with Python 3.12+, pytest, mypy (strict), jsonschema, PyYAML
- [x] Configure mypy strict mode, pytest with BDD-style conventions
- [x] Set up pre-commit hooks (mypy, ruff)
- [x] Add `.claude/CLAUDE.md` with TDD/type-safety rules
- [x] Add tdd-guardian and py-enforcer agents

### 1.2 Schema and Validation (core.py)

TDD from here on. RED-GREEN-REFACTOR for every function.

- [x] Define node JSON Schema (v1): `schema_version`, `id`, `timestamp`, `source`, `node_type`, `context`, `creator` (required) + `related_to`, `tags`, `meta` (optional)
- [x] Define registry schema: `id`, `name` (optional), `context`, pools map
- [x] `validate_node(frontmatter: dict) -> ValidationResult` -- validates a single node against schema
- [x] `validate_pool(pool_path: Path) -> ValidationResult` -- validates all nodes in snapshots/ and live/
- [x] `validate_registry(config: dict) -> ValidationResult` -- validates registry structure (valid paths, no duplicate pool names, required fields)
- [x] `extract_frontmatter(text: str) -> dict | None` -- parse YAML frontmatter from Markdown

### 1.3 Node Creation (core.py)

- [x] `generate_id(source: str, context: str) -> str` -- deterministic sha256[:12] (timestamp excluded so identical content always produces the same ID)
- [x] `check_idempotency(pool_path: Path, node_id: str) -> ExistingNode | None` -- detect duplicate by ID, return creator and timestamp if exists
- [x] `create_node(pool_path, source, node_type, context, creator, content, tags, related_to, meta) -> NodeResult` -- write Markdown file to `snapshots/` (snapshot nodes) or `live/` (live nodes), return path and ID
- [x] Auto-commit logic: if `auto_commit: true` in config, `git add` + `git commit` with message `alph: add <type> node <id>`
- [x] No auto-pull, no auto-push

### 1.4 Config System (core.py)

- [x] `load_config() -> AlphConfig` -- merge global (`~/.config/alph/config.yaml`) + local walk-up (config.yaml files from cwd upward, most specific wins) + CLI overrides
- [x] Config fields: `creator` (email), `auto_commit`, `default_registry`, `default_pool`, registry declarations
- [x] Secrets loading from `~/.config/alph/secrets.yaml` (separate, gitignored)

### 1.5 Registry and Pool Init (core.py)

- [x] `init_registry(pool_home, id, name, context) -> RegistryResult` -- write registry declaration to global config, validate, print what was created
- [x] `init_pool(registry_id, name, context, pool_type) -> PoolResult` -- create pool directory (snapshots/, live/), register in config, validate, print defaults
- [x] Both commands validate their own output before reporting success

### 1.6 Query Commands (core.py)

- [x] `list_nodes(pool_path, sort_by, filter_tags, status) -> list[NodeSummary]` -- list nodes with frontmatter fields; default active only, `-s` expands
- [x] `list_pools(registry_id_or_name, cfg) -> list[PoolSummary] | None` -- list pools registered under a registry
- [x] `show_node(pool_path, node_id) -> NodeDetail` -- full node display, formatted for terminal
- [x] `resolve_pool_name(name, cfg) -> Path | None` -- resolve pool name to path via registry config (default registry checked first)

### 1.7 CLI Wrapper (cli.py)

Thin Typer wrapper calling core.py functions:

- [x] `alph registry init` -- create registry
- [x] `alph registry list` -- list known registries
- [x] `alph pool init --name <name>` -- create pool
- [x] `alph pool list` -- list pools in a registry
- [x] `alph add` / `alph a` -- create node
- [x] `alph list` / `alph l` -- list nodes (registry/pool header; `-s` status filter; `-o` output format)
- [x] `alph show <id>` / `alph s <id>` -- show node
- [x] `alph validate` / `alph v` -- run validator
- [x] `alph config list` -- show config discovery tree
- [x] `alph config show <path>` -- display config file with syntax highlighting
- [x] `alph defaults` -- show resolved creator, registry, pool, and pool path
- [x] Per-command `-v`/`--verbose` flag (works as both `alph -v cmd` and `alph cmd -v`)

### 1.8 Timeline State

- [ ] `.timeline-state.json` in each pool: last_loaded, per-node last_verified, sync history
- [ ] `load_state(pool_path) -> TimelineState`
- [ ] `update_state(pool_path, state) -> None`

> Deferred to Phase 3 — first meaningful use requires a live adapter to exercise the "new since last load" pattern.

### Phase 1 Exit Criteria

- [x] All core.py functions have passing tests (100% of production code written test-first)
- [x] mypy strict passes with zero errors
- [x] `alph registry init` + `alph pool init` + `alph add` + `alph list` + `alph show` + `alph validate` all work end-to-end
- [x] A user can create a registry, create a pool, add snapshot and live nodes, list them, show them, and validate the structure

---

## Phase 2: Distribution and MCP (Complete)

The system becomes usable by LLMs and installable by others.

### 2.1 Homebrew Distribution

- [x] Create GitHub org tap repo (`AlpheusCEF/homebrew-tap`)
- [x] Write Homebrew formula for `brew install alph`
- [x] CI pipeline to publish on release (release workflow updates formula SHA on tag)

### 2.2 MCP Server (mcp_server.py)

FastMCP 3.x wrapper exposing core.py as MCP tools:

- [x] One tool per core function (following Basic Memory pattern)
- [x] Detailed docstrings on every tool
- [x] MCP annotations: `readOnlyHint`, `destructiveHint`, `idempotentHint`
- [x] Dual output: `text` (human-readable) + `json` (structured)
- [x] Overwrite guard on write operations

### 2.3 Claude Skill (SKILL.md)

- [x] Write thin SKILL.md that orients Claude to use MCP tools
- [x] Install at user level: `~/.claude/skills/context-architect/SKILL.md`
- [x] Covers: pool discovery, node search, live node resolution, timeline synthesis, state awareness, cross-pool context

### 2.4 Cross-Pool References

- [x] Within pool: `"node_id"`
- [x] Across pools: `"pool_name::node_id"`
- [x] Across registries: `"registry_id::pool_name::node_id"`
- [x] Cross-cutting pools: `cross_cutting: true` auto-included when loading any sibling

### 2.5 Repo Separation

- [x] `overview/` is a standalone documentation repo for the framework ecosystem
- [x] `alph-cli` is its own repo (CLI + core + MCP server)

### 2.6 CI/CD

- [x] GitHub Actions: run test suite, mypy, ruff on alph-cli repo
- [x] GitHub Actions: release workflow builds sdist and updates homebrew-tap formula on tag

### Phase 2 Exit Criteria

- [x] `brew install alph` works
- [x] Claude can use alph via MCP tools (add, list, show, validate)
- [x] Cross-pool references resolve correctly
- [x] Repos are separated: overview (docs), alph-cli (code)

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

### 3.6 Timeline State (deferred from Phase 1)

- [ ] `.timeline-state.json` in each pool: last_loaded, per-node last_verified, sync history
- [ ] `load_state(pool_path) -> TimelineState`
- [ ] `update_state(pool_path, state) -> None`

### Phase 3 Exit Criteria

- [ ] At least Slack + one other adapter working
- [ ] All adapters produce schema-compliant nodes
- [ ] Gateway function pattern proven and reusable
- [ ] Timeline state updated on every sync

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

- [ ] Live nodes resolve efficiently at 50+ nodes per pool
- [ ] Temporal queries work across milestones
- [ ] Cross-pool references tracked at registry level

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

| Artifact | Repo | Phase | Status |
|----------|------|-------|--------|
| STATE.md, FUTURE.md, PLAN.md | overview | Now | Done |
| core.py, cli.py, tests/ | alph-cli | Phase 1 | Done |
| mcp_server.py | alph-cli | Phase 2 | Done |
| SKILL.md | alph-cli (installed to ~/.claude/) | Phase 2 | Done |
| Homebrew formula | AlpheusCEF/homebrew-tap | Phase 2 | Done |
| Input adapters | alph-cli or separate repos | Phase 3 | Not started |
| Timeline state | alph-cli | Phase 3 | Not started |
| GraphRAG integration | alph-cli | Phase 4 | Not started |
