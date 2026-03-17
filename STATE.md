# AlpheusCEF: State of the Project

**Date**: 2026-03-16
**Status**: Phase 1, Phase 2 (distribution + MCP), remote registry support, content_type system, update_node, registry-scoped hydration, barrel (hydration cache), search, skill management, and MCP auto-config complete and shipping

---

## What Is This

AlpheusCEF (Alpheus Context Engine Framework) is a system for collecting, linking, and reasoning over scattered context. Context lives everywhere -- Slack threads, Jira tickets, Google Docs, emails, meeting transcripts, even photos of receipts -- and by the time you need it, you've forgotten where it is or that it exists.

AlpheusCEF treats context as a river: you feed things in upstream, they flow through a structured backbone, and they resurface when you need them. The name comes from Alpheus, the Greek river god whose waters traveled underground across the sea and re-emerged transformed on the other side. The working handle is `alph`.

## The Problem

Decisions get made in Slack and forgotten. ADRs exist but nobody links them to the tickets they spawned. A Google Doc captures requirements but the email thread that refined them is lost. Meeting transcripts sit in Zoom archives. When you need the full picture -- why did we choose this approach, who raised that concern, what was the original requirement -- you're reconstructing it from memory and fragments.

This is true for work (security design reviews with 100 artifacts across 20 systems) and personal projects (when did I last change the oil, what was the mileage, did they say the brakes needed checking).

## The Design

### The Context Funnel

AlpheusCEF organizes context as a narrowing funnel. Each level scopes the next:

```
[registry] vehicles              "All vehicle-related context"
  [pool] highlander              "Maintenance, repairs, and mods for the Highlander"
    [node] oil change            "100k checkup at Valvoline, full synthetic"
    [node] brake inspection      "Pads at 40%, replace by 110k"
  [pool] civic                   "Daily driver maintenance"
    [node] tire rotation         "Rotated and balanced, 32 PSI all around"
```

Every entity in the funnel -- registry, pool, node -- carries a `context` field: a human/LLM-readable description that answers "what is this and when is it relevant?" The LLM reads these context fields top-down to efficiently narrow from broad domain to specific artifact without loading everything.

Cross-pool correlation within a registry is implicit -- pools sharing a registry share a domain. "Show me all maintenance across vehicles" is a registry-level query without explicit linking. Explicit `related_to` edges between nodes provide precision when the funnel's implicit grouping isn't enough.

### Three Layers

**Layer 1: Input Adapters** create context nodes from wherever you already are.
- A Slack command (`/ate epic-name`) or emoji reaction to pin a thread
- A CLI tool for manual thoughts and links
- A PWA on your phone to share an image or text
- A gateway function that uses a small LLM to standardize messy input into clean Markdown
- Eventually: email forwarding, Confluence @-mentions, Figma comments

**Layer 2: Context Backend** is a Git repository. Markdown files with YAML frontmatter. Git gives you versioning, diffs, blame, search, and Actions for free. No database to host. LLMs already understand Markdown perfectly.

**Layer 3: Context Frontend** is how you (or an LLM) read and reason over the graph. A Claude Skill that knows the MCP tools. A Gemini Gem. Potentially a web timeline view. Two parallel modes:
- **Sync**: Clone/ingest entire repo into context window. Best for deep reasoning across a timeline. Token-limited.
- **MCP**: Remote query on demand via tools. Best for live node resolution and large archives.

### The Funnel Entities

A **registry** is the top of the funnel. It groups related pools under a namespace, declares where they live, and enables cross-pool discovery. Registries have an `id` (machine reference) and an optional `name` (human-readable). Multiple registries declared in the same alph config file are peers automatically. A "simple" registry type points at a directory, with pools assumed to be subdirectories unless a pool declares otherwise (e.g., its own Git repo).

A **pool** is a scoped collection of context nodes -- all the nodes for one project, one epic, one object (like a car). Pools are the unit of context separation and the primary thing you "load" when working with Alph. Pool type and path/remote are set at creation time:
- **Subdirectory pool**: Lives as a folder within a registry's directory. The default, lowest friction.
- **Repo pool**: Its own Git repo, registered in the same registry. Good for access control, CI, or heavy collaboration.

A **node** is a single piece of context. It can be fixed content (a decision, a thought, any captured text), a set of dynamic resources (all websites in a list, all repos with a certain topic), or a pointer to a living document (which is pulled in its latest state at query time). Nodes carry a `context` field that the LLM reads during scanning to decide relevance before loading full content.

All three entities share a common pattern: an `id` (machine identifier) and a `context` field (human/LLM-readable description). Pools and registries also support `cross_cutting: true` to be automatically included when loading any sibling.

### Two Node Types

**Snapshot nodes** are frozen moments. Someone said something, a decision was reached, a thought was captured. The content is immutable at creation time. They live in `snapshots/`. The shorthand `snap` is accepted by the CLI (`--type snap`).

**Live nodes** reference something that changes -- a Jira ticket, a Confluence page, a Google Doc, or a collection of resources matching a query. The file contains metadata and a context description, but the real content must be fetched at query time. They live in `live/` and include a `provider` hint telling the LLM which tool to use for resolution. Live nodes default to resolving a single resource; collection resolution (e.g., "all repos with topic:security") is indicated via `meta.resolves_to: collection`.

### The Schema

Every node has a common core in its YAML frontmatter:

| Field | Required | Description |
|-------|----------|-------------|
| `schema_version` | Yes | Schema version (starts at `"1"`) |
| `id` | Yes | 12-char SHA-256 hash (of source + context; timestamp excluded for idempotency) |
| `timestamp` | Yes | ISO-8601 creation time |
| `source` | Yes | Originating system — UA-style string (e.g. `alph-cli/v0.1.26`, `alph-mcp/v0.1.26`, `slack`) |
| `node_type` | Yes | `snapshot` or `live` |
| `context` | Yes | Human/LLM-readable description of this node |
| `creator` | Yes | Who created the node (defaults to user's email) |

Optional fields provide graph edges and extensibility:

| Field | Description |
|-------|-------------|
| `status` | Query visibility: `active` (default), `archived`, or `suppressed` (see below) |
| `content_type` | Content format/kind: `text` (default), `gdoc`, `slack`, `jira`, `confluence`, `email`, `image`, `figma`, `task`. Determines expected `meta` fields (see planned.md) |
| `related_to` | List of node/pool references (see cross-referencing below) |
| `tags` | Semantic labels (decision, concern, requirement, open, closed, in-progress) |
| `meta` | Source-specific key-value pairs (url, doc_id, provider, cost, mileage, resolves_to, priority, due, recur) |

### Node Status

`status` is a first-class field because it affects **query behavior** — inclusion/exclusion — not just labeling. That is the line between `status` and `tags`: tags are for categorization, `status` is for system behavior.

| Value | Default (no `-s`) | With `-s <value>` | Meaning |
|-------|-------------------|-------------------|---------|
| `active` (or absent) | included | only if explicitly requested | Normal, in active rotation |
| `archived` | excluded | shown exclusively | No longer relevant — keep for history, rarely surface |
| `suppressed` | excluded | shown exclusively | Still relevant but noisy — like `--verbose` content |

`active` is the implicit default. Omitting `status` from frontmatter is equivalent to `status: active`. Declaring it explicitly is valid and improves clarity in automated or bulk-created nodes.

The `-s` / `--status` flag on `alph list` is an **exclusive filter** — it shows only nodes matching the specified status, not active nodes plus the requested status. Without the flag, only `active` nodes are returned. Multiple values can be combined with commas or by repeating the flag:

```
-s archived              show only archived
-s archived,suppressed   show only archived and suppressed
-s all                   show every node regardless of status
```

**Tags vs. status — the distinction in practice:**

Tags like `open`, `closed`, `in-progress`, `blocked` are domain categorization of work state — they affect how humans and LLMs *interpret* a node, but not whether the system *surfaces* it. A closed repair record is still active context history you want in default queries. `archived` is what you set when the entire node is no longer relevant to any context. A node can be `tags: [closed]` and `status: active` simultaneously — closed work, still relevant history.

Content below the frontmatter `---` separator is free-form Markdown. Snapshot nodes typically have substantial content; live nodes typically have minimal or no content below the frontmatter.

The schema is enforced by a JSON Schema validator. The validator also checks the registry for structural correctness (valid paths, no duplicate pool names, required fields).

### ID Generation and Idempotency

Node IDs are deterministic: `sha256(source + context)[:12]`. Timestamp is intentionally excluded from the hash so that re-submitting the same context from the same source always produces the same ID regardless of when it is submitted. If someone tries to add a node that already exists (same source and context), the system reports who created the existing node and when, rather than creating a duplicate. This provides natural deduplication across input adapters.

### Stateful Context Loading

The system tracks what's been loaded and when. A `.timeline-state.json` in each pool records:
- Last loaded timestamp
- Per-node verification timestamps for live nodes
- Sync history

This lets the LLM say: "4 new artifacts since last Tuesday. The Jira ticket has been updated. Missing: the email thread Alice mentioned."

### Cross-Pool and Cross-Registry Context

Within a registry, cross-pool correlation is implicit -- pools sharing a registry share a domain. The LLM can query at the registry level without explicit linking between pools.

For explicit references, `related_to` uses a namespaced format:
- Within a pool: `"node_id"`
- Across pools in the same registry: `"pool_name::node_id"`
- Across registries: `"registry_id::pool_name::node_id"`

Registries declared in the same alph config are peers and can reference each other. Pools marked `cross_cutting: true` are automatically included when loading any sibling pool in the same registry.

### Interaction Model

`alph` is the universal address. Submission or query, human or AI -- you're always just talking to Alph.

```
alph add -c "Oil change at Valvoline"     (submission)
alph, what do you know about X            (query via LLM)
@alph tag this                            (passive tagging)
```

The tools are symmetric: the same CLI commands a human runs are the same functions Claude calls via MCP. The Skill is a thin orientation layer on top.

## Architecture

### Code Structure

```
alph/
  core.py           # All logic. No framework dependency. Permanent.
  remote.py         # Remote registry providers (GitHub GraphQL) and clone management.
  mcp_server.py     # FastMCP wrapper exposing core as MCP tools. Swappable.
  cli.py            # CLI wrapper exposing core as commands. Swappable.
```

Core logic is importable and framework-agnostic. The MCP server and CLI are thin wrappers that both call `core.py`. If MCP is replaced by something else, only `mcp_server.py` changes. Remote registry access (`remote.py`) provides read-only API providers (GitHub GraphQL) and clone management for read-write operations.

MCP tools use FastMCP 3.x decorators with detailed docstrings (following the Basic Memory pattern), MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`), and dual output format (`text` for human-readable, `json` for structured).

The SKILL.md is installed once at the user level (`~/.claude/skills/context-architect/SKILL.md`), not copied into each pool. It orients Claude to use the MCP tools rather than duplicating their logic.

### Config Hierarchy

Three levels, each overriding the previous:

| Level | Location | Contents |
|-------|----------|----------|
| Global | `~/.config/alph/config.yaml` | Creator email, auto_commit, default registry, default pool, defaults_reminder, registry declarations (including mode, clone_path, auto_push, auto_pull, branch, ssh_command for remote registries) |
| Local walk-up | `config.yaml` files from cwd upward to root | Project or directory-specific overrides; most-specific (nearest to cwd) wins |
| CLI flags | `--pool`, `--creator`, `-c`, etc. | Per-invocation overrides |

Registry metadata (`pool_home` path, context, name, pools) lives entirely in the global config under `registries[id]`. No per-registry config file is written to the pool home directory. The `load_config` function is the single authority on where to look; all other config-related functions operate on the loaded result.

Registries are declared in the alph config file alongside other settings. All registries in the same config file are peers by default.

### CLI Commands

| Command | Short | Description |
|---------|-------|-------------|
| `alph registry init` | | Create a registry, validate, show what was created |
| `alph registry list` | | List known registries with ID, name, mode, context, and pool home path |
| `alph registry` | `alph reg` | No subcommand defaults to `registry list`; `reg` is shorthand for `registry` |
| `alph registry check <id>` | | Verify a remote registry is reachable (runs `git ls-remote`); `check all` iterates all registries |
| `alph registry clone <id>` | | Clone a remote registry locally for RW access |
| `alph registry pull <id>` | | Pull latest changes for a cloned remote registry |
| `alph registry status <id>` | | Show registry mode, clone state, branch, auto_pull, auto_push, and path details |
| `alph pool init --name <name>` | | Create a pool, register it, validate, show defaults |
| `alph pool list` | | List pools in a registry with name, type, context, and path; discovers unconfigured pools on disk |
| `alph add -c "context text"` | `alph a -c "text"` | Create a node (auto-commits if configured; auto-pushes if `auto_push: true`). Supports `--tags`, `--meta key=value`, `--related-to`, `--content-type`/`--ct` |
| `alph update <id> [flags]` | | Update an existing node's frontmatter or body. Flags: `--status`, `--tags-add`, `--tags-remove`, `--meta key=value`, `--content`, `-c`/`--context`, `--content-type`/`--ct`, `--related-add` |
| `alph list [-s ...] [-o ...] [--pull]` | `alph l` | List nodes; default active only; `-s` for status filter; `-o` for output format; `--pull` for fresh data |
| `alph show <id> [--pull]` | `alph s <id>` | Display full node; `--pull` for fresh data from RW clones |
| `alph validate [--pull]` | `alph v` | Check nodes against schema; `--pull` for fresh data |
| `alph config list` | | Show config discovery tree with exists/missing status |
| `alph config show <path>` | | Display a config file with syntax highlighting |
| `alph defaults` | | Show resolved creator, registry, pool, and pool path from current config |
| `alph barrel status` | `alph b status` | Show barrel cache entries with age and freshness |
| `alph barrel check <id>` | `alph b check` | Check if a cached entry is fresh, stale, or missing |
| `alph barrel write <id>` | `alph b write` | Cache hydrated content with standardized frontmatter |
| `alph barrel invalidate <id>` | `alph b invalidate` | Remove a specific cache entry |
| `alph barrel flush` | `alph b flush` | Remove all cache entries in a pool |
| `alph barrel new` | `alph b new` | Show entries cached since last read |
| `alph barrel mark-read` | `alph b mark-read` | Update the timeline read cursor |
| `alph barrel export` | `alph b export` | Export cached content (md/json/yaml) |
| `alph skill install` | | Install SKILL.md symlink + configure MCP server in Claude settings |
| `alph skill status` | | Check skill and MCP configuration state |

`alph barrel` (aliases: `bar`, `b`) defaults to `status` when no subcommand is given.

Global options: `alph --registry <id-or-url>` (also `-r`, `--reg`) scopes pool resolution to a specific registry for one invocation. `alph --branch <name>` overrides the git branch for remote operations. `--pool` accepts `-p`. Global options must appear before the subcommand.

`alph add` creates files locally and optionally auto-commits (`auto_commit: true` in config). For remote RW registries, `auto_push: true` pushes after commit. The commit message follows the convention `alph: add <type> node <id>`.

Both `registry init` and `pool init` validate their output before reporting success and print a clear map of what was created and where (files, paths, defaults).

## Naming

| Level | Name | Usage |
|-------|------|-------|
| Project | **Alpheus** | The vision, the mythology, documentation |
| Product | **AlpheusCEF** | Context Engine Framework |
| Handle | **alph** | CLI, tags, queries, conversation |

From Coleridge's *Kubla Khan* (1797):

> "In Xanadu did Kubla Khan / A stately pleasure-dome decree: / Where Alph, the sacred river, ran / Through caverns measureless to man / Down to a sunless sea."

**Alph** is Coleridge's invention, derived from **Alpheus**, the Greek river god of the Peloponnese. In myth, the river Alpheus traveled underground beneath the Ionian Sea and re-emerged as the fountain of **Arethusa** near Syracuse -- folk proof: a cup thrown into the Alpheus would resurface in Arethusa's spring. Alpheus is also the river Heracles rerouted to clean the Augean Stables.

The myth maps to a context engine: context travels invisibly beneath conversations, preserves its identity through transformation, and re-emerges when relevant. Arethusa remains a candidate name for a future output/emergence layer.

Rejected candidates: ALF (trademarked, Alien Productions 1986), Gulo, Vorr, Olf, Charybdis, Fenrir. Domain candidates noted: alpheus.io, alpheus.dev, alpheus.ai.

## Development Approach

**TDD is non-negotiable.** Every piece of production code is written in response to a failing test. RED-GREEN-REFACTOR in small increments. Behavior-driven tests using pytest. Full type hints with mypy strict mode. Immutable data patterns. Pure functions in core.py.

The project uses the tdd-guardian and py-enforcer agents for enforcement.

Python 3.12+, Poetry for dependency management, FastMCP 3.x for the MCP server layer.

## What Exists

### Decisions Made
- Git repos as the v1 backend (not Airtable, not a database)
- Markdown + YAML frontmatter as the universal node format
- Context funnel: registry -> pool -> node, each with a `context` field
- Snapshot/live node distinction; live nodes support single and collection resolution
- `schema_version` field in frontmatter from day one
- `creator` field (defaults to email) for attribution and idempotency messages
- Deterministic IDs from `sha256(source + context)[:12]` for idempotency (timestamp excluded; version suffix stripped from UA-style source before hashing so `alph-cli/v0.1.24` and `alph-cli/v0.1.99` produce the same ID for the same context)
- Registries have IDs and optional names; declared in alph config as peers
- Pool separation declared at registry level; subdirectory default (`subdir`), repo override per pool
- Config hierarchy: global (`~/.config/alph/config.yaml`) -> local walk-up (config.yaml files from cwd upward, most specific wins) -> CLI flags
- Default registry and default pool in config for daily-use simplicity
- Core logic in `core.py`, exposed via FastMCP server + CLI wrapper
- SKILL.md installed once at user level, references MCP tools
- Auto-commit on add (opt-in via config); `auto_push` and `auto_pull` default to `true` for RW remote registries (explicit `false` overrides), default to `false` for local registries (explicit `true` enables); `git pull --rebase` for all pulls (handles diverged branches from multiple writers)
- Remote registries: two-mode architecture (RO via GitHub GraphQL API, RW via local clone); `mode: ro | rw` config per registry; `auto_push` for RW remotes; SSH host aliases resolved via `~/.ssh/config` for forge detection; `ssh_command` registry key sets `GIT_SSH_COMMAND` for all git ops on that registry
- `defaults_reminder: false` top-level config key suppresses the "not set as default" hint printed by `alph registry init`
- Reserved names: `all` and `alph` are reserved and cannot be used as registry IDs or pool names
- `content_type` field: built-in types (`text`, `gdoc`, `slack`, `jira`, `confluence`, `email`, `image`, `figma`, `task`) with type-specific meta validation; `task` type has no required meta (flexible by design). Registries can define additional content types via `hydration.yaml` at registry root — the built-in set is validated strictly, custom types are valid if declared by the registry
- Hydration is registry-scoped: each registry declares how to resolve its content types (provider, auth, base URLs) in a `hydration.yaml` at registry root. Same content type (e.g. `gdoc`) may resolve differently across registries (different workspaces, auth, MCP servers). Three-layer resolution: SKILL.md (ships with alph, generic patterns) → registry `hydration.yaml` (registry-specific providers and config) → node `meta` (per-resource identifiers like url, doc_id, channel)
- `update_node()` for in-place frontmatter/body modification with validation, no-op detection, and auto-commit
- Validator checks both nodes and registry
- `alph list` and `alph show` for human inspection
- `status` field (`active`/`archived`/`suppressed`) as first-class for query behavior; tags for categorization only; `-s`/`--status` flag to expand beyond active
- BDD/TDD development with pytest, type hints, immutable patterns

### Prior Art Considered
- **Glean**: Enterprise search -- black-box, lacks timeline control
- **LlamaIndex (GraphRAG)**: Phase 4+ candidate for graph indexing
- **MemGPT / LangGraph**: Long-term memory frameworks for LLMs
- **Neo4j**: Graph DB option when volume warrants it
- **Pinecone / Weaviate**: Vector DB with metadata filtering
- **Basic Memory**: Structured Markdown vault -- patterns adopted (one tool per file, dual output, MCP annotations)

### Decisions Deferred
- Airtable as a potential UI/dashboard layer (explored, parked)
- ~~Specific MCP server configurations (Google Docs, Jira)~~ → resolved: registry-scoped hydration config
- Slack bot app name and setup
- Domain registration (alpheus.io/dev/ai)
- PWA design
- Gateway function hosting (Lambda/Vercel)
- GraphRAG / Neo4j when graph complexity warrants it (Phase 4)

### Integration Priority
| Source | Priority | Status |
|--------|----------|--------|
| CLI (manual thoughts, links) | P0 | Built (v0.1.x) |
| Slack threads/messages | P0 | Designed, not built |
| Google Docs | P1 | Designed, not built |
| Email threads | P1 | Concept only |
| Jira issues | P1 | Concept only |
| Figma | P2 | Concept only |
| Confluence pages | P2 | Concept only |
| Zoom/Loom recordings | P2 | Concept only |
| Images (Vision adapter) | P2 | Concept only |
| Basic Memory vault | P2 | Concept only |

## What Has Been Built

Phase 1, Phase 2, remote registry support, content_type system, update_node, registry-scoped hydration, barrel (hydration cache), search, skill management, and MCP auto-config are complete. Released version is v0.1.42 (Homebrew). Latest additions: two-tier search (`alph search` + `alph b search`), search MCP tools (`search_pool_nodes`, `search_pool_barrel`), barrel CLI (`alph barrel`/`bar`/`b`), `alph skill install` (SKILL.md symlink + MCP server config), creator defaults to system username, starter `hydration.yaml` on registry init.

### Core Engine (`alph-cli` repo, `src/alph/`)

- **`core.py`**: All production logic. Framework-agnostic. Fully type-annotated (mypy strict). Functions: `load_config`, `init_registry`, `init_pool`, `create_node`, `update_node`, `generate_id`, `check_idempotency`, `validate_node`, `validate_pool`, `validate_config_keys`, `validate_config_integrity`, `check_git_state`, `list_nodes`, `list_pools`, `show_node`, `resolve_pool_name`, `collect_registries`, `find_registry_config`, `find_registry_for_pool`, `load_hydration_config`, `load_barrel_config`, `barrel_write`, `barrel_check`, `barrel_status`, `barrel_invalidate`, `barrel_flush`, `barrel_new`, `barrel_mark_read`, `barrel_export`, `is_remote_registry`, `parse_remote_registry`, `effective_mode`. Data types: `HydrationTypeConfig`, `HydrationConfig`, `BarrelEntry`, `BarrelStatus`, `BarrelMeta`, `BarrelConfig`, `BarrelTypeConfig` (frozen dataclasses). `update_node()` modifies existing node frontmatter and/or body with full validation, no-op detection, tags add/remove/replace, meta merge, content/context replacement, content_type change, and related_to add/replace. `_find_node_file()` helper shared by `check_idempotency`, `show_node`, and `update_node`. `content_type` field supports: `text`, `gdoc`, `slack`, `jira`, `confluence`, `email`, `image`, `figma`, `task`. `validate_node` accepts `registry_types` parameter for custom types declared in `hydration.yaml`. `show_node` accepts `hydration` parameter and populates `NodeDetail.hydration_instructions` when content_type matches. Slack validation relaxed: `url OR channel` (thread_ts is optional). `init_registry` creates starter `hydration.yaml` with barrel defaults for local registries. `load_config` falls back to `getpass.getuser()` when no creator is configured. Pool dotfiles (`.alph.yaml`) for pool-local metadata; `register_subdir_pools` config key controls whether subdir pools also get config entries (default: false). Config write operations use ruamel.yaml to preserve YAML comments. Reserved names: `all`, `alph`. `resolve_pool_name` falls back to directory existence for bare pool names not explicitly declared in the pools dict. `validate_config_integrity` checks that `default_registry` references a declared registry.
- **`remote.py`**: Remote registry access. `GitHubProvider` (GraphQL batch reads), `RemoteProvider` protocol, `resolve_pool_readonly` (ephemeral tmpdir), clone management (`clone_remote_registry`, `pull_remote_registry`, `push_remote_registry`, `default_clone_dir`). SSH host alias resolution via `~/.ssh/config` — URLs like `git@github-personal:org/repo.git` are correctly identified when the alias maps to `github.com`. All three git ops accept `ssh_command=` to inject `GIT_SSH_COMMAND` into the subprocess env. Pull uses `--rebase` (replaced `--ff-only`) to handle diverged branches from multiple writers. `list_remote_pools` lists pool directories from the remote via the GraphQL API. `fetch_remote_pools_cached` wraps it with a disk cache (`~/.cache/alph/completion/<hash>.json`) using a configurable TTL (default 60 s).
- **`cli.py`**: Typer wrapper. Commands: `registry init`, `registry list`, `registry check` (including `check all`), `registry clone`, `registry pull`, `registry push`, `registry status` (including `status all`), `pool init`, `pool list`, `add` (`a`), `list` (`l`), `show` (`s`), `validate` (`v`), `config list`, `config show`, `config check`, `config show-all`, `defaults`, `examples` (hidden). `reg` is a shorthand for `registry`; `registry`, `pool`, and `config` with no subcommand default to `list`. Registry commands (`check`, `clone`, `pull`, `push`, `status`) default to `default_registry` when no argument given. Global `--registry` (`-r`/`--reg`) and `--branch` options; `--pool` accepts `-p`. Per-command `-v`/`--verbose` flag and `--pull` flag on read commands. Default registry/pool resolution from config with remote URL support. Reserved names (`all`, `alph`) rejected by `registry init` and `pool init`. `config check` validates referential integrity — warns when `default_registry` names a registry not declared in config. Auto-push failures are elevated to errors with a `registry push <id>` recovery hint. `registry status` shows unpushed commit count for cloned RW registries. **Tab completion**: `autocompletion=` wired to registry ID arguments (`_complete_registry_id`) and `--pool/-p` options (`_complete_pool`). Local registries and RW remote clones are scanned from disk; RO remote registries are queried via the forge API only when `completion_remote: true` is set (global or per-registry), with results cached for `completion_cache_ttl` seconds (default 60). `completion_remote` defaults to `false` — no network calls during tab completion unless opted in. `completions show [shell]` prints the completion script to stdout; `completions install [shell]` writes it to the standard location and prints activation instructions. Typer's built-in `--install-completion` is left enabled (`add_completion=True` — disabling it breaks runtime completion) but superseded by these commands. The generated completion script is stripped of Typer's leading newline so zsh `compinit` recognises the `#compdef` directive at byte 0.
- **`mcp_server.py`**: FastMCP 3.x wrapper. One tool per core function. Tools: `add_node` (with `meta`, `related_to`, `content_type` params), `list_pool_nodes`, `show_pool_node` (returns `hydration_instructions`), `validate_pool` (accepts registry-declared custom types), `update_pool_node`. Registry-aware hydration: loads config from alph config cascade, finds owning registry, loads `hydration.yaml`. MCP instructions updated to guide LLMs on following hydration instructions. Detailed docstrings, MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`), dual output (`text` + `json`). Transparent remote pool support via `_resolve_pool` context manager.
- **`man/alph.1`**: Comprehensive man page covering all commands, config keys, node schema, environment variables, and examples. Installed by Homebrew formula.

### Test Suite

511 tests passing. Full TDD — every production function written test-first. mypy strict clean, ruff clean.

### Distribution

- **Homebrew tap**: `AlpheusCEF/homebrew-tap`, formula at v0.1.42. `brew tap AlpheusCEF/tap && brew install alph` installs `alph`, `alph-mcp` binaries, `man alph` man page, SKILL.md to `share/alph/`, and zsh/bash/fish tab completion scripts. After install, `alph skill install` creates the SKILL.md symlink and configures the MCP server. Formula uses `preserve_rpath` to avoid Rust-extension dylib relocation issues. Completion scripts are generated at install time via `_ALPH_COMPLETE=source_<shell>` with leading-newline stripping.
- **GitHub Actions**: CI runs tests, mypy, ruff on every push/PR. Release workflow builds sdist and updates homebrew-tap formula automatically on tag.

### SKILL.md

Symlinked from `~/.claude/skills/context-architect/SKILL.md` to `/opt/homebrew/share/alph/SKILL.md` (auto-updates on brew upgrade). Set up via `alph skill install`. Covers: MCP tools, barrel CLI usage, hydration workflow with cache, context queries synthesis pattern, temporal reasoning, hydration failure handling, content type table with required meta fields. Does not hardcode registry-specific details.

### Demo Data

`multi-pool-repo-example/` in the AlpheusCEF org: three pools (vehicles, appliances, remodeling), 28 nodes total, cross-pool `related_to` references demonstrated. `seed.py --wipe` regenerates cleanly. The `registry/` directory is gitignored on main; a GitHub Action workflow runs `seed.py` and commits the generated data to a `seeded` branch for RO testing. RO config entries use `branch: seeded` to read from that branch.

### Registry-Scoped Hydration

Live nodes point at external resources but don't carry instructions for how to fetch them. **Hydration** is the process of resolving a live node to its current content. This is inherently registry-scoped — the same `gdoc` content type may require different auth, workspace, or MCP server depending on which registry owns the node.

**Design: three-layer resolution**

```
┌──────────────────────────────────────────────┐
│  SKILL.md (ships with alph, user-level)      │
│  Generic patterns + built-in type defaults   │
├──────────────────────────────────────────────┤
│  Registry root: hydration.yaml               │
│  - Override built-in type resolution         │
│  - Define custom types + their resolution    │
│  - All registry-scoped, not org-assumed      │
├──────────────────────────────────────────────┤
│  Node meta                                   │
│  Per-resource identifiers (url, doc_id, etc) │
└──────────────────────────────────────────────┘
```

**`hydration.yaml`** lives at registry root (alongside pool directories). Example:

```yaml
# hydration.yaml — created automatically by alph registry init
types:
  gdoc:
    provider: google-docs-mcp
    instructions: "Use the Google Docs MCP server to fetch document content."
  confluence:
    provider: atlassian-mcp
    base_url: https://life360.atlassian.net
    instructions: "Use the Atlassian MCP server for Confluence pages."
  jira:
    provider: atlassian-mcp
    base_url: https://life360.atlassian.net
    instructions: "Use the Atlassian MCP server for Jira issues."
  slack:
    provider: slack-mcp
    instructions: "Use the Slack MCP server. Channel name is in meta.channel."

barrel:
  default_ttl: 4h
  types:
    snapshot:
      ttl: forever
      fetch_mode: full
    jira:
      ttl: 2h
      fetch_mode: full
    slack:
      ttl: 1h
      fetch_mode: delta

context_queries:
  latest_state:
    matches: latest state, current status, where are we
    instructions: "Synthesize a status update from all hydrated content."
```

**Key properties:**
- A registry without `hydration.yaml` still works — SKILL.md provides generic fallback instructions, and nodes carry URLs in meta for manual resolution
- Registries can define content types beyond the built-in set (e.g. `notion`, `linear`, `internal-wiki`) — the type is valid if the registry declares it
- The `instructions` field is what gets surfaced to the LLM during node resolution — it's the registry-specific "how to hydrate this type"
- `provider` is a hint for which MCP server to use; the SKILL.md maps provider names to tool names
- Pool-level overrides are not planned — if needed later, a pool could carry its own `hydration.yaml` that merges with the registry's

**Implications for content_type validation:**
- Built-in types are validated strictly (meta requirements enforced)
- Custom types declared in `hydration.yaml` pass validation with no meta requirements (the registry author defines what's needed via `instructions`)
- Unknown types not in built-ins AND not declared by the registry fail validation

### What Remains Unbuilt

- Gateway function for standardizing messy input — adapter foundation
- Input adapters (Slack, Google Docs, Jira, email, etc.) — Phase 3
- Unregistered pool notice — informational warning on unregistered pools
- Git fallback provider (shallow sparse clone) — deferred
- PWA, browser extension, mobile — Phase 5
