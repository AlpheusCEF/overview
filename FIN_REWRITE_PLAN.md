# fin-over-alph: Rewrite Plan

**Date**: 2026-03-13
**Branch**: `claude/fin-cli-alpheus-rewrite-kk3ef`
**Repo**: `fin-cli` (new) — alph as imported library, fin UX preserved

---

## The Idea

`fin` is a battle-tested daily task CLI. Its UX is fast and intuitive — `fin "do the thing"`, `fin`, `fins` — and worth keeping. But its backend is a SQLite database that has no relationship to the context model we've built in AlpheusCEF.

The insight: `fin`'s primitives map cleanly onto alph's primitives. Tasks are snapshot nodes. Contexts are pools. Labels are tags. If we swap the SQLite backend for alph's core, we get:

- **Persistent, portable, human-readable tasks** (Markdown + YAML, not a binary DB)
- **Registry-level cross-context visibility** (`alph list --registry` across all contexts)
- **Reuse of alph's tags**, `related_to`, `status`, `meta` fields
- **Git history on every task** — who added it, when, what changed
- **MCP access** — Claude can read and manage your tasks via existing MCP tools
- **Zero new backend to maintain** — alph core is already tested and typed

The user sees `fin`. The backend is `alph`.

---

## Primitive Mapping

| fin concept | alph concept | Notes |
|---|---|---|
| `context` (e.g. `-c work`) | **pool** | Each context becomes its own pool in a `tasks` registry |
| `label` / hashtag | **tag** | `#urgent` → `tags: [urgent]` |
| task (unit of work) | **snapshot node** | `node_type: snapshot` |
| task open/completed/dismissed | alph `status` + tag | `active` = open, `archived` = completed, `suppressed` = dismissed |
| priority labels `#i`, `#t` | tags `important`, `today` | Rendered as priority buckets in display |
| `due_date` (`#due:2025-08-10`) | `meta.due` | Parsed from content at add time |
| `depends:task_id` | `related_to` | Namespaced node reference |
| `recur:daily\|weekly\|monthly` | `meta.recur` | Handled in fin display logic |
| numeric task ID | alph node ID (12-char) | fin maps short IDs from list display; see ID bridging below |
| SQLite DB | git repo (Markdown + YAML) | Pool = `~/.fin/pools/<context>/` in a `tasks` registry |

### The Registry

A single registry called `tasks` is declared in the alph config. Its `pool_home` defaults to `~/.fin/pools/`. Each fin context becomes a subdirectory pool. The `default` context maps to the `default` pool.

```yaml
# ~/.config/alph/config.yaml
registries:
  tasks:
    pool_home: ~/.fin/pools
    context: "Personal task lists managed by fin"
```

### ID Bridging

fin users reference tasks by short numeric IDs shown in `fin list` output (e.g., `fin close 3`). alph nodes use 12-char SHA hashes. The bridge: fin generates a **session-local ordered index** mapping display integers to node IDs. This index is written to `~/.fin/.fin-index.json` after every `fin list` call. Commands like `fin close 3` resolve `3` → node ID via this index. The index is ephemeral (session-scoped) — never relied on across reboots for correctness, only for convenience.

---

## Architecture

```
fin-cli/
  fin/
    cli.py          # Thin Click wrapper. No logic — all calls go to core.py
    core.py         # All fin logic. Imports alph.core. Framework-agnostic. Permanent.
    display.py      # Rendering: priority buckets, date headers, status symbols
    index.py        # Session-local int→node_id mapping (~/.fin/.fin-index.json)
    config.py       # fin config: default context, editor, date format, wrap width
  tests/
    test_core.py
    test_display.py
    test_index.py
  fin             # CLI entry point (script)
  pyproject.toml
```

`alph` is declared as a library dependency in `pyproject.toml`. `fin/core.py` imports `alph.core` directly. The alph CLI is not invoked — only its Python API is used.

**What fin/core.py does:**
- Calls `alph.core.load_config()` to get registry/pool config
- Calls `alph.core.create_node()` to add tasks
- Calls `alph.core.list_nodes()` to list tasks, then passes results to `display.py`
- Calls `alph.core.validate_node()` for integrity checks
- Manages the `tasks` registry and context-as-pool mapping
- Parses fin-specific metadata (`#due:`, `#recur:`, `#depends:`, `#i`, `#t`) from content strings into alph `meta` and `tags` fields

**What fin/core.py does NOT do:**
- Duplicate alph's ID generation, node schema, git operations, config loading, or validation logic
- Maintain its own database

---

## Development Principles

Inherit from AlpheusCEF project standards (`agents/CLAUDE.md`):

- **TDD non-negotiable.** RED-GREEN-REFACTOR. Every production function in `core.py` and `display.py` is written in response to a failing test. No production code without a failing test first.
- **BDD test style.** pytest, behavior-driven naming (`test_add_task_with_due_date_extracts_meta_field`).
- **Type safety.** mypy strict, full type hints. `display.py` functions are pure (input → string, no side effects).
- **Pure core.** `fin/core.py` has no Click dependency. `cli.py` is a thin translation layer only.
- **Immutable data patterns.** Use dataclasses or TypedDicts for intermediate representations.
- **Schema versioned.** All fin nodes write `schema_version: "1"` and `source: fin-cli/v<version>`.

Agents active during development (via `.claude/agents/` symlinks from `agents` repo):
- `tdd-guardian.md` — enforces RED-GREEN-REFACTOR discipline
- `py-enforcer.md` — enforces mypy strict, ruff, type hint coverage

---

## Phases

---

### Phase A: Primitive Mapping and Scaffolding

**Milestone**: A new `fin-cli` repo exists. `fin add` writes a valid alph snapshot node into a `tasks` registry pool. `fin list` reads them back and renders output matching current fin display.

#### A.1 Repo Scaffolding

- [ ] Create new `fin-cli` repo (separate from the original)
- [ ] Poetry init: Python 3.12+, `alph` as dependency, pytest, mypy strict, ruff
- [ ] Configure mypy strict, pytest BDD conventions
- [ ] Pre-commit hooks (mypy, ruff)
- [ ] Wire `.claude/CLAUDE.md` → agents repo CLAUDE.md (same 5-line block as other AlpheusCEF repos)
- [ ] Symlink `tdd-guardian.md` and `py-enforcer.md` agents
- [ ] Add `fin` entry point script

#### A.2 Config Layer (`fin/config.py`)

TDD from here on.

- [ ] `load_fin_config() -> FinConfig` — read `~/.config/fin/config.yaml` (editor, date format, wrap width, default context)
- [ ] `ensure_tasks_registry(alph_cfg) -> None` — idempotently declare `tasks` registry in alph config if absent
- [ ] `ensure_context_pool(context, alph_cfg) -> Path` — idempotently create pool for a context if absent
- [ ] Tests for all three; config is created on first `fin add` call

#### A.3 Content Parser (`fin/core.py`)

- [ ] `parse_fin_content(raw: str) -> ParsedTask` — extract tags (`#label`), meta (`#due:`, `#recur:`, `#depends:`), priority markers (`#i`, `#t`), remaining clean content
- [ ] `build_node_kwargs(parsed: ParsedTask) -> dict` — map ParsedTask fields to alph `create_node()` kwargs (tags, meta, context field)
- [ ] Tests covering: bare text, single label, multiple labels, due date, recur, depends, combined, edge cases (no content, only labels)

#### A.4 Add Task (`fin/core.py`)

- [ ] `add_task(raw_content: str, context: str, alph_cfg) -> NodeResult` — parse content, ensure pool, call `alph.core.create_node()`
- [ ] Idempotency: alph's SHA ID deduplication is inherited automatically
- [ ] Tests: add task, add duplicate (idempotent), add to named context, labels extracted, meta populated

#### A.5 List Tasks (`fin/core.py`)

- [ ] `list_tasks(context, days, statuses, alph_cfg) -> list[FinTask]` — call `alph.core.list_nodes()`, filter by date window, return typed list
- [ ] `FinTask` datatype — wraps NodeSummary with fin-specific computed fields (is_important, is_today, due_date, is_overdue)
- [ ] Tests: empty pool, single task, filtering by status, filtering by days window

#### A.6 Index Management (`fin/index.py`)

- [ ] `build_index(tasks: list[FinTask]) -> Index` — map 1-based ints to node IDs, in display order
- [ ] `save_index(index: Index) -> None` — write to `~/.fin/.fin-index.json`
- [ ] `load_index() -> Index` — read back; return empty dict if missing
- [ ] `resolve_id(user_input: str, index: Index) -> str` — int → node ID; pass-through if already looks like node ID
- [ ] Tests: round-trip build/save/load, resolve int, resolve hash passthrough, missing index fallback

#### A.7 Display (`fin/display.py`)

- [ ] `render_task_list(tasks: list[FinTask], index: Index) -> str` — priority buckets (important, today, regular), date headers, `[ ]` / `[x]` / `[d]` symbols, ID column
- [ ] `render_task_detail(task: FinTask) -> str` — single task full view
- [ ] All pure functions (str → str); no I/O
- [ ] Tests: empty list, single task, priority ordering, completed task symbol, dismissed task symbol, overdue indicator

#### A.8 CLI (`fin/cli.py`)

Thin Click wrapper calling core functions:

- [ ] `fin "content"` / `fin add "content"` — add task
- [ ] `fin` / `fin list` — list tasks (default context, last day)
- [ ] `fin list -d 7` — last N days
- [ ] `fin list -c work` — named context
- [ ] `fin close <id>` — mark archived
- [ ] `fin dismiss <id>` — mark suppressed
- [ ] `fin open <id>` — reopen (mark active)

#### Phase A Exit Criteria

- [ ] `fin "write the plan"` creates a valid alph snapshot node in `~/.fin/pools/default/`
- [ ] `fin` lists it with display matching current fin output format
- [ ] `fin close 1` marks it archived
- [ ] All core.py and display.py functions have passing tests written test-first
- [ ] mypy strict clean, ruff clean

---

### Phase B: User Experience Parity

**Milestone**: Every `fin` command from the original CLI works identically from the user's perspective. Data lives in alph pools.

#### B.1 Bulk Editor (`fin/core.py` + `fin/cli.py`)

- [ ] `get_editable_text(tasks: list[FinTask], index: Index) -> str` — serialize tasks to editor format
- [ ] `parse_edited_text(text: str, original: list[FinTask]) -> list[EditAction]` — diff original vs edited, produce add/update/close/delete actions
- [ ] `apply_edit_actions(actions: list[EditAction], alph_cfg) -> EditResult` — execute actions via alph core
- [ ] `fin e` / `fine` — open editor, parse result, apply actions
- [ ] Tests: no changes, add line, delete line, modify content, close (remove checkbox), round-trip

#### B.2 Completed Task View (`fin/cli.py`)

- [ ] `fins` / `fin done` — list archived (completed) tasks with same display format
- [ ] `fins "content"` — add a task and immediately mark it complete (log mode)
- [ ] Tests: list completed, log entry, empty completed pool

#### B.3 Status Filtering (`fin/core.py`)

- [ ] `list_tasks(statuses=['open','done','dismissed'])` — multi-status queries via alph `-s` flag
- [ ] `fin list -s open,done` — pass status list to list_tasks
- [ ] Tests: each status, combined statuses, all statuses

#### B.4 Label Filtering (`fin/core.py` + `fin/cli.py`)

- [ ] `filter_by_labels(tasks, label_expr: str) -> list[FinTask]` — simple AND/OR matching on tags (no reserved word conflicts since alph tags are already normalized)
- [ ] `fin list -l "work and urgent"` — label expression filter
- [ ] `fin list-labels` — count open/completed per label
- [ ] Tests: single label, AND, OR, NOT, combined, no match

#### B.5 Recurring Tasks (`fin/core.py`)

- [ ] `get_recur_meta(task: FinTask) -> RecurMeta | None` — extract recur pattern from node meta
- [ ] `spawn_recurrence(task: FinTask, alph_cfg) -> NodeResult | None` — when a recurring task is closed, create next instance
- [ ] Call from close action: if task has `meta.recur`, spawn next before archiving
- [ ] Tests: daily, weekly, monthly, close without recur (no spawn), spawn produces correct due date

#### B.6 Task Dependencies

- [ ] `resolve_depends(task: FinTask, index: Index) -> list[FinTask]` — follow `related_to` references tagged with `depends`
- [ ] Display: show blocked indicator when dependency is open
- [ ] Tests: no deps, single dep (open → blocked), single dep (closed → unblocked), missing ref (graceful)

#### B.7 Context Management (`fin/cli.py`)

- [ ] `fin context` — list contexts (= list pools in tasks registry)
- [ ] `fin context set <name>` — set default context (writes to fin config)
- [ ] `fin context clear` — reset to default
- [ ] Tests: list contexts, set/get, clear

#### B.8 Config Command (`fin/cli.py`)

- [ ] `fin config set <key> <value>` — write to `~/.config/fin/config.yaml`
- [ ] `fin config show` — display current fin config
- [ ] Keys: `editor`, `date_format`, `wrap_width`, `default_context`
- [ ] Tests: set/get round-trip, invalid key rejected

#### Phase B Exit Criteria

- [ ] All original fin commands have working equivalents
- [ ] `fine` bulk editor round-trip works
- [ ] `fins` shows completed tasks
- [ ] Recurring task spawning works
- [ ] Dependency blocking indicator renders
- [ ] 100% TDD on new core.py functions; mypy strict clean

---

### Phase C: alph-Native Enhancements

**Milestone**: fin gains capabilities that weren't possible with SQLite, powered by alph's cross-pool and registry features.

#### C.1 Cross-Context View

- [ ] `fin list --all-contexts` — query all pools in the `tasks` registry and merge results
- [ ] Registry-level list via `alph.core.list_nodes()` called per-pool, merged and sorted
- [ ] Display: context/pool header per group
- [ ] Tests: single context, multiple contexts, empty contexts hidden

#### C.2 MCP Access

- [ ] Verify existing alph MCP tools (`tool_list_nodes`, `tool_add_node`, `tool_show_node`) work against fin's `tasks` registry pools without modification
- [ ] Write SKILL fragment: orient Claude on fin's tag conventions (`important`, `today`, `archived` = done, `suppressed` = dismissed), the `tasks` registry, and fin's `meta` fields
- [ ] Tests: not applicable (MCP is alph's responsibility); manual verification documented

#### C.3 Related Tasks

- [ ] `fin link <id> <id>` — add a `related_to` reference between two tasks (across contexts supported via pool::node namespacing)
- [ ] Display: show related task IDs in `fin show <id>` output
- [ ] Tests: same-pool link, cross-pool link, self-link rejected

#### C.4 Git History Commands

- [ ] `fin log <id>` — shell out to `git log --follow <node_file>` and display changelog
- [ ] `fin diff <id>` — show `git diff` for a node file
- [ ] No tests needed (thin shell delegation); manual verification documented

#### C.5 Export / Import Compatibility

- [ ] `fin export --format json|csv|txt` — serialize FinTask list to formats matching original fin export
- [ ] `fin import <file>` — read original fin export formats, call `add_task()` for each row
- [ ] Tests: round-trip export/import for JSON, CSV, TXT; duplicate import is idempotent (alph SHA dedup)

#### Phase C Exit Criteria

- [ ] `fin list --all-contexts` returns merged results
- [ ] Claude can query fin tasks via MCP tools
- [ ] `fin link` creates `related_to` edges
- [ ] `fin export` / `fin import` produce correct output and survive round-trips

---

### Phase D: Distribution

**Milestone**: `brew install fin` (via AlpheusCEF tap) installs fin with alph as a bundled dependency. Existing fin users can migrate.

#### D.1 Migration Tool

- [ ] `fin migrate --from <sqlite_db_path>` — read original SQLite DB, create nodes for each task preserving created_at, labels, context, status
- [ ] Idempotent: re-running migration doesn't duplicate nodes (alph SHA dedup by content)
- [ ] Tests: empty DB, single task, task with labels, completed task, dismissed task, all statuses, duplicate run

#### D.2 Homebrew Formula

- [ ] Add `fin` formula to `AlpheusCEF/homebrew-tap`
- [ ] `brew install fin` installs `fin` and `fine` and `fins` binaries
- [ ] `alph` is a dependency in the formula (pulls in the tap's existing alph formula)
- [ ] Release workflow updates formula SHA on tag

#### D.3 CI/CD

- [ ] GitHub Actions: run tests, mypy, ruff on push/PR
- [ ] Release workflow: build sdist, update homebrew-tap formula on tag

#### Phase D Exit Criteria

- [ ] `brew install fin` works
- [ ] `fin migrate` successfully imports an existing SQLite DB
- [ ] CI green

---

## Quick Reference: What Goes Where

| Artifact | Repo | Phase | Status |
|---|---|---|---|
| This plan | overview | Now | Draft |
| `fin/core.py`, `fin/display.py`, `fin/index.py`, `tests/` | fin-cli (new) | A | Not started |
| `fin/cli.py` | fin-cli (new) | A | Not started |
| Bulk editor, fins, label filter, recur, depends | fin-cli (new) | B | Not started |
| Cross-context, MCP skill fragment, link, git log | fin-cli (new) | C | Not started |
| Migration tool, Homebrew formula, CI | fin-cli (new) | D | Not started |

---

## Open Questions (to resolve before or during Phase A)

1. **New repo vs. fork**: Create a fresh `AlpheusCEF/fin-cli` repo, or fork `chasemp/fin-cli` into the org? Fresh repo preferred to avoid carrying SQLite history and `requirements.txt` patterns.
2. **alph version pinning**: Pin to a specific alph release or track latest? Recommend pinning to current stable (`^0.1.34`) and testing upgrades explicitly.
3. **`tasks` registry pool_home path**: `~/.fin/pools/` is proposed. Should it be `~/.local/share/fin/` (XDG)? Decide before Phase A.2 config tests are written.
4. **Bulk editor format**: Current fin editor format is one task per line with checkbox prefix. Keep identical for muscle memory, or take the opportunity to use alph's Markdown format natively in the editor? Recommend keeping existing format for UX continuity.
5. **fin package name**: `fin-cli` (PyPI) to avoid collision with existing `fin` packages.
