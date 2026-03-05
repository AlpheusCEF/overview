# AlpheusCEF: State of the Project

**Date**: 2026-03-05
**Status**: Design complete, pre-implementation

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

All three entities share a common pattern: a `name` (machine identifier) and a `context` field (human/LLM-readable description). Pools and registries also support `cross_cutting: true` to be automatically included when loading any sibling.

### Two Node Types

**Fixed nodes** are snapshots. Someone said something, a decision was reached, a thought was captured. The content is frozen at creation time. It lives in `snapshots/`.

**Live nodes** are pointers. They reference something that changes -- a Jira ticket, a Confluence page, a Google Doc, or a collection of resources matching a query. The file contains metadata and a context description, but the real content must be fetched at query time. They live in `pointers/` and include a `provider` hint telling the LLM which tool to use for resolution. Live nodes default to resolving a single resource; collection resolution (e.g., "all repos with topic:security") is indicated via `meta.resolves_to: collection`.

### The Schema

Every node has a common core in its YAML frontmatter:

| Field | Required | Description |
|-------|----------|-------------|
| `schema_version` | Yes | Schema version (starts at `"1"`) |
| `id` | Yes | 12-char SHA-256 hash (of timestamp + source + context) |
| `timestamp` | Yes | ISO-8601 creation time |
| `source` | Yes | Originating system (cli, slack, google_docs) |
| `node_type` | Yes | `fixed` or `live` |
| `context` | Yes | Human/LLM-readable description of this node |
| `creator` | Yes | Who created the node (defaults to user's email) |

Optional fields provide graph edges and extensibility:

| Field | Description |
|-------|-------------|
| `related_to` | List of node/pool references (see cross-referencing below) |
| `tags` | Semantic labels (decision, concern, requirement) |
| `meta` | Source-specific key-value pairs (url, doc_id, provider, cost, mileage, resolves_to) |

Content below the frontmatter `---` separator is free-form Markdown. Fixed nodes typically have substantial content; live nodes typically have minimal or no content below the frontmatter.

The schema is enforced by a JSON Schema validator. The validator also checks the registry for structural correctness (valid paths, no duplicate pool names, required fields).

### ID Generation and Idempotency

Node IDs are deterministic: `sha256(timestamp + source + context)[:12]`. If someone tries to add a node that already exists (same timestamp, source, and context), the system reports who created the existing node and when, rather than creating a duplicate. This provides natural deduplication across input adapters.

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
  mcp_server.py     # FastMCP wrapper exposing core as MCP tools. Swappable.
  cli.py            # CLI wrapper exposing core as commands. Swappable.
```

Core logic is importable and framework-agnostic. The MCP server and CLI are thin wrappers that both call `core.py`. If MCP is replaced by something else, only `mcp_server.py` changes.

MCP tools use FastMCP 3.x decorators with detailed docstrings (following the Basic Memory pattern), MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`), and dual output format (`text` for human-readable, `json` for structured).

The SKILL.md is installed once at the user level (`~/.claude/skills/context-architect/SKILL.md`), not copied into each pool. It orients Claude to use the MCP tools rather than duplicating their logic.

### Config Hierarchy

Three levels, each overriding the previous:

| Level | Location | Contents |
|-------|----------|----------|
| Global | `~/.config/alph/config.yaml` | Creator email, auto_commit, default registry, default pool, registry declarations |
| Pool | `.alph/config.yaml` in pool root | Pool-specific overrides |
| CLI flags | `--commit`, `--creator`, `-c`, etc. | Per-invocation overrides |

Secrets live separately in `~/.config/alph/secrets.yaml` (never in a pool repo, always in .gitignore).

Registries are declared in the alph config file alongside other settings at the desired scope. All registries in the same config file are peers by default.

### CLI Commands

| Command | Short | Description |
|---------|-------|-------------|
| `alph registry init` | | Create a registry, validate, show what was created |
| `alph pool init --name <name>` | | Create a pool, register it, validate, show defaults |
| `alph add -c "context text"` | `alph a -c "text"` | Create a node (auto-commits if configured) |
| `alph list` | `alph l` | List nodes in a pool with frontmatter |
| `alph show <id-or-context>` | `alph s <id>` | Display full node formatted for terminal |
| `alph validate` | | Check nodes against schema + registry against registry schema |

`alph add` creates files locally and optionally auto-commits (`auto_commit: true` in config). No auto-pull, no auto-push -- those are separate git operations. The commit message follows the convention `alph: add <type> node <id>`.

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
- Fixed/live node distinction; live nodes support single and collection resolution
- `schema_version` field in frontmatter from day one
- `creator` field (defaults to email) for attribution and idempotency messages
- Deterministic IDs from `sha256(timestamp + source + context)` for idempotency
- Registries have IDs and optional names; declared in alph config as peers
- Pool separation declared at registry level; subdirectory default, repo override per pool
- Config hierarchy: global (~/.config/alph/) -> pool (.alph/) -> CLI flags
- Default registry and default pool in config for daily-use simplicity
- Core logic in `core.py`, exposed via FastMCP server + CLI wrapper
- SKILL.md installed once at user level, references MCP tools
- Auto-commit on add (opt-in via config, no auto-pull/push)
- Validator checks both nodes and registry
- `alph list` and `alph show` for human inspection
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
- GraphRAG / Neo4j when graph complexity warrants it
- Specific MCP server configurations (Google Docs, Jira)
- Slack bot app name and setup
- Domain registration (alpheus.io/dev/ai)
- PWA design
- Gateway function hosting (Lambda/Vercel)
- Homebrew formula for distribution (Phase 2, via GitHub org tap repo)

### Integration Priority
| Source | Priority | Status |
|--------|----------|--------|
| CLI (manual thoughts, links) | P0 | Designed, not built |
| Slack threads/messages | P0 | Designed, not built |
| Google Docs | P1 | Designed, not built |
| Email threads | P1 | Concept only |
| Jira issues | P1 | Concept only |
| Figma | P2 | Concept only |
| Confluence pages | P2 | Concept only |
| Zoom/Loom recordings | P2 | Concept only |
| Images (Vision adapter) | P2 | Concept only |
| Basic Memory vault | P2 | Concept only |

## What Has NOT Been Built

Nothing has been built yet. Prototype scripts from design sessions remain in `scripts/` (annotated as pre-decision, will be replaced by proper implementation). Design session transcripts have been folded into STATE.md and FUTURE.md and removed. The project is at the "detailed design complete, ready to implement" stage.
