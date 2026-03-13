# AlpheusCEF: Completed Work

What was planned, what was built, and the key decisions that shaped each phase.

**Released version**: v0.1.34 (Homebrew)
**Dev status**: content_type, update_node, --tags/--meta/--related-to, and meta display pending next release
**Test count**: 411 passing, mypy strict clean, ruff clean

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
- Closed enum with clear error messages for unknown values
- `task` type has no required meta — flexible for fin-cli integration
- `custom:` prefix for user-defined types — not yet implemented, low priority

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

## Development Principles (All Phases)

These held throughout and remain in effect:

- **TDD non-negotiable**: RED-GREEN-REFACTOR. No production code without a failing test
- **BDD test style**: pytest, behavior-driven naming
- **Type safety**: mypy strict, full type hints, immutable data patterns
- **Pure core**: core.py has no framework dependencies — all logic lives there
- **Thin wrappers**: cli.py and mcp_server.py are translation layers only
- **Schema versioned**: `schema_version` in every node from day one
- **Git-native**: leverage git for versioning, diffs, blame, search, Actions
