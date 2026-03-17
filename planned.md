# AlpheusCEF: Completed Work

What was planned, what was built, and the key decisions that shaped each phase.

**Released version**: v0.1.42 (Homebrew)
**Test count**: 511 passing, mypy strict clean, ruff clean

---

## Phase 1: Core Engine

The minimum viable system: create nodes, list them, validate them. Everything runs locally, no services required.

### What shipped

- **Project scaffolding**: Poetry, Python 3.12+, pytest, mypy strict, ruff, pre-commit hooks, TDD/type-safety agents
- **Schema and validation** (`core.py`): Node JSON Schema v1 (`schema_version`, `id`, `timestamp`, `source`, `node_type`, `context`, `creator` + optional `related_to`, `tags`, `meta`). Registry schema. `validate_node()`, `validate_pool()`, `validate_registry()`, `extract_frontmatter()`
- **Node creation** (`core.py`): Deterministic IDs via `sha256(source + context)[:12]`. Idempotency detection. `create_node()` writes to `snapshots/` or `live/`. Auto-commit opt-in
- **Config system** (`core.py`): `load_config()` merges global + local walk-up + CLI overrides. Creator, auto_commit, default_registry, default_pool, registry declarations
- **Registry and pool init** (`core.py`): `init_registry()`, `init_pool()` — both self-validating
- **Query commands** (`core.py`): `list_nodes()` with sort/filter/status, `list_pools()`, `show_node()`, `resolve_pool_name()`
- **CLI wrapper** (`cli.py`): Thin Typer layer — `alph registry init/list`, `alph pool init/list`, `alph add`, `alph list`, `alph show`, `alph validate`, `alph config list/show`, `alph defaults`, per-command `-v` flag

### Deferred from Phase 1

- **Timeline state** (`.timeline-state.json`) — deferred to Phase 3; needs a live adapter to exercise "new since last load"

---

## Phase 2: Distribution and MCP

The system becomes usable by LLMs and installable by others.

### What shipped

- **Homebrew distribution**: `AlpheusCEF/homebrew-tap`, `brew install alph`, man page, release workflow auto-builds sdist
- **MCP server** (`mcp_server.py`): FastMCP 3.x wrapper. One tool per core function. MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`). Dual output (text + JSON). Overwrite guard
- **Claude Skill** (`SKILL.md`): Installed at user level, references MCP tools for pool discovery, node search, live node resolution, timeline synthesis
- **Cross-pool references**: Within pool (`"node_id"`), across pools (`"pool_name::node_id"`), across registries (`"registry_id::pool_name::node_id"`), cross-cutting pools (`cross_cutting: true`)
- **Repo separation**: `overview/` (docs), `alph-cli` (code), `agents/` (shared)
- **CI/CD**: GitHub Actions — test suite, mypy, ruff on push/PR; release workflow for Homebrew

---

## Phase 2.5: Remote Git Registries

Remote registries allow `pool_home` to be a git URL instead of a local path.

### What shipped

- **Core types** (`core.py`): `RemoteRegistryRef`, `is_remote_registry()`, `parse_remote_registry()`, `effective_mode()`, `RegistryEntry` with mode/clone_path/auto_push/auto_pull/branch
- **Remote providers** (`remote.py`): `RemoteProvider` protocol, `GitHubProvider` (GraphQL batch reads — 2 API calls for 50 nodes), `detect_forge()`, `provider_for_url()`, SSH host alias resolution via `~/.ssh/config`
- **Pool resolution** (`remote.py`): `resolve_pool_readonly()` (ephemeral tmpdir via API), `clone_remote_registry()`, `pull_remote_registry()` (--rebase), `push_remote_registry()`
- **CLI integration**: `_pool_context` handles local/RO/RW transparently, `registry check/clone/pull/push/status`, `--pull` flag, `--registry` global option, `--branch` global option, auto_push after writes, clear RO error messages
- **MCP integration**: `_resolve_pool` context manager for transparent remote support, write rejection on RO
- **Auth**: `GITHUB_TOKEN` → `GH_TOKEN` → `gh auth token`
- **URL format**: `<git-url>:/<subpath>` split on `.git:/`

### Deferred

- GitLab, Bitbucket, git fallback providers — waiting for a real user need

---

## content_type System

The missing third leg: `source` = WHO made the node, `node_type` = HOW stored, `content_type` = WHAT the content is.

### What shipped

- **Field**: Optional `content_type` in frontmatter, defaults to `text`
- **Type catalog**: `text`, `gdoc`, `slack`, `jira`, `confluence`, `email`, `image`, `figma`, `task`
- **Validation**: Type-specific required meta enforcement (`gdoc` requires `url`, `jira` requires `url` + `issue_key`, etc.)
- **CLI**: `--content-type`/`--ct` flag on `alph add` and `alph update`, `--tags` (repeatable), `--meta key=value` (repeatable), `--related-to` (repeatable)
- **MCP**: `meta` and `related_to` params on `tool_add_node`, `content_type` on both add and update
- **Display**: `alph show` renders meta fields, marks required fields with `*` (e.g. `meta.url*:`)
- **List output**: `content_type` column in table, JSON, YAML, CSV formats

### Design decisions

- `content_type` excluded from ID hash — preserves idempotency
- Closed enum with clear error messages for unknown values; registries can declare custom types via `hydration.yaml`
- `task` type has no required meta — flexible for fin-cli integration
- Slack validation relaxed: `url OR channel` (thread_ts optional — channel-only reference is valid)

---

## update_node()

In-place modification of existing nodes — prerequisite for fin-cli Phase B and any mutation workflow.

### What shipped

- **Core function** (`core.py`): `update_node()` with status, tags (add/remove/replace), meta (merge), content (body replacement), context, content_type, related_to (add/replace)
- **UpdateResult** dataclass: `node_id`, `path`, `valid`, `errors`, `noop`
- **Validation**: Re-validates modified frontmatter before writing
- **No-op detection**: Compares old vs new, returns early if identical
- **Mutual exclusion**: `tags` vs `tags_add`/`tags_remove`, `related_to` vs `related_add`
- **Auto-commit**: Opt-in, same pattern as `create_node`
- **Helper**: `_find_node_file()` extracted from `show_node()`/`check_idempotency()` for shared lookup
- **CLI**: `alph update <id> [--status] [--tags-add] [--tags-remove] [--meta] [--content] [--context] [--ct] [--related-add]`
- **MCP**: `tool_update_node` / `update_pool_node` with all update fields

---

## Registry-Scoped Hydration

Resolving live nodes to their current content — registry-scoped because the same content type may require different auth, workspace, or MCP server depending on which registry owns the node.

### What shipped

- **Data types** (`core.py`): `HydrationTypeConfig` and `HydrationConfig` frozen dataclasses. `HydrationConfig.declared_types` property for the set of registry-declared types
- **Config loading** (`core.py`): `load_hydration_config()` reads `hydration.yaml` from registry root; `find_registry_for_pool()` finds the owning registry by longest-prefix match (local paths and remote RW clone paths)
- **Validation** (`core.py`): `validate_node(registry_types=)` accepts custom content types declared in hydration.yaml; built-in types still validated strictly
- **Show** (`core.py`): `show_node(hydration=)` populates `NodeDetail.hydration_instructions` when content_type matches a declared type
- **CLI**: `alph show` displays `hydration:` line when instructions are available; `alph validate` loads registry types automatically from hydration.yaml
- **MCP**: `show_pool_node` returns `hydration_instructions` field; `validate_pool` accepts registry-declared custom types; MCP instructions updated to guide LLMs on following hydration instructions
- **SKILL.md**: Rewritten with hydration workflow, generic fallback patterns per content type, installed at `~/.claude/skills/context-architect/SKILL.md`
- **SPP registry**: First real registry with hydration.yaml (gdoc, confluence, jira, slack). All 6 socialauth nodes pass validation
- **human_test.sh**: Section 19 covers hydration config end-to-end

### Design decisions

- Three-layer resolution: SKILL.md (generic) -> hydration.yaml (registry-specific) -> node meta (per-resource)
- Registry-declared custom types skip meta validation — the registry author defines requirements via instructions
- No pool-level overrides planned; registry scope is sufficient for now

---

## Barrel — Hydration Cache (v0.1.37+)

Per-pool cache of hydrated live node content. Deterministic CLI for cache operations so Claude doesn't need to manage files or do TTL math.

### What shipped

- **Data types** (`core.py`): `BarrelEntry`, `BarrelStatus`, `BarrelMeta`, `BarrelConfig`, `BarrelTypeConfig` frozen dataclasses
- **Core functions** (`core.py`): `barrel_write`, `barrel_check` (TTL comparison), `barrel_status`, `barrel_invalidate`, `barrel_flush`, `barrel_new` (timeline — what's changed since last read), `barrel_mark_read`, `barrel_export` (md/json/yaml), `load_barrel_config`
- **TTL parsing**: `_parse_ttl()` handles `4h`, `30m`, `1d`, `forever`
- **CLI** (`cli.py`): `alph barrel` subcommand (aliases: `bar`, `b`) with: status, check, write, invalidate, flush, new, mark-read, export
- **Registry init**: `init_registry()` creates starter `hydration.yaml` with barrel defaults for local registries
- **SKILL.md**: Updated with barrel CLI usage, defaults (always on, 4h TTL), hydration workflow with cache, context queries, temporal reasoning, hydration failure handling
- **Skill management** (`cli.py`): `alph skill install` creates symlink from `~/.claude/skills/context-architect/SKILL.md` to `share/alph/SKILL.md` (auto-updates on brew upgrade). `alph skill status` checks install state.
- **Homebrew**: Formula installs SKILL.md to `share/alph/`, caveats mention `alph skill install`

### Design decisions

- Barrel is always on — no enable/disable toggle. Every hydration caches, every read checks cache first.
- Cache per pool (`<pool>/barrel/`), config per registry (`hydration.yaml → barrel`)
- TTL defaults to 4h when no barrel config exists; registries override per content type
- Symlink install for SKILL.md — brew share path is version-independent, survives upgrades
- `alph skill install` is one-time; `alph skill status` warns on stale copies

---

## Search — Finding Content (v0.1.42)

Two-tier keyword search across node content and cached hydrated content.

### What shipped

- **Core functions** (`core.py`): `SearchResult` frozen dataclass, `search_nodes()` (frontmatter + body), `search_barrel()` (cached hydrated content), shared `_search_file()` helper
- **CLI**: `alph search "query"` (shallow, node-level), `alph b search "query"` (deep, barrel cache)
- **MCP tools**: `search_pool_nodes`, `search_pool_barrel` — both read-only, idempotent, return node IDs with context and matching excerpts
- **SKILL.md**: Search section with usage examples, tool table updated

### Design decisions

- Case-insensitive matching across all searchable fields (context, tags, meta values, body, cached content)
- No indexing or embeddings — structured grep over markdown files. Simple, deterministic, no dependencies.
- Two tiers by design: shallow (always available, node files) vs. deep (requires barrel cache to exist)
- Excerpts capped at 5 per result in MCP responses to avoid token bloat

---

## fin-cli: Task Management over alph

`fin` reimplements the battle-tested fin task CLI on top of alph as a library. Tasks are snapshot nodes with `content_type: task`. Published to Homebrew as v0.1.0.

### What shipped

- **Phase A** (complete): Repo scaffolding, alph interface layer (`alph_interface.py`), config, content parser, add/list/close/dismiss/open tasks, short-hash ID resolution, priority bucket display, CLI entry points (`fin`, `fins`, `fine`)
- **Phase B** (complete): Bulk editor with intermediary YAML format, completed view, status/label filtering, recurring tasks, dependencies, context management, fin config
- **Phase C** (partial): Cross-pool `fin list --all`, `fin link <id> <id>`, `fin log <id>`, `fin diff <id>`
- **Phase D** (partial): Homebrew formula published (v0.1.0), CI/CD working

### Remaining

- **C.2**: MCP access verification + SKILL fragment ✅
- ~~C.5~~: Folded into barrel CLI (`barrel export`)
- ~~D.1~~: Dropped (legacy fin-cli deprecated, not worth bridging)

### Key design decisions

- `alph_interface.py` as versioned contract — fin never imports `alph.*` directly
- Tasks registry at `~/.fin/pools/`, each fin context = one pool
- Short-hash prefix matching (6-char display, full 12-char always resolves)
- Editor operates on staged strings, never launches editor in tests
- Legacy chasemp/fin-cli deprecated in favor of AlpheusCEF/fin-cli

---

## Development Principles (All Phases)

These held throughout and remain in effect:

- **TDD non-negotiable**: RED-GREEN-REFACTOR. No production code without a failing test
- **BDD test style**: pytest, behavior-driven naming
- **Type safety**: mypy strict, full type hints, immutable data patterns
- **Pure core**: core.py has no framework dependencies — all logic lives there
- **Thin wrappers**: cli.py and mcp_server.py are translation layers only
- **Schema versioned**: `schema_version` in every node from day one
- **Git-native**: leverage git for versioning, diffs, blame, search, Actions
