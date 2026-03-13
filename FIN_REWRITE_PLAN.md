# fin-over-alph: Rewrite Plan

**Date**: 2026-03-13
**Branch**: `claude/fin-cli-alpheus-rewrite-kk3ef`
**Repo**: `AlpheusCEF/fin-cli` — alph as imported library, fin UX preserved

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
| numeric task ID | alph node ID (12-char) | fin displays first 6 chars; `fin close a1b2c3` does prefix match; no session state |
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

`~/.fin/pools/` is the canonical location. XDG-compliance is a Phase D consideration, not a blocker.

### ID Bridging

fin users reference tasks by short IDs. alph nodes use 12-char SHA hashes. The bridge: **short-hash prefix matching**, the same model git uses.

`fin list` displays the first 6 characters of each node ID in brackets:
```
[ ] Write the quarterly report       [a1b2c3] #work #important
[ ] Fix the login bug                [b2c3d4] #work
```

`fin close a1b2c3` does a prefix match against the pool: find the node whose ID starts with `a1b2c3`. If the prefix is ambiguous (two nodes share the same 6-char prefix — vanishingly rare with SHA-derived IDs), fin reports the collision and asks the user to use more characters. The full 12-char ID always resolves unambiguously.

This is strictly better than the original fin's numeric IDs: numeric IDs renumber when tasks are deleted and are meaningless across contexts. Short hashes are stable — the same task always has the same ID, in any context, forever.

No session-index file. No `~/.fin/.fin-index.json`. No state between invocations. `index.py` is eliminated from the architecture.

---

## Architecture

```
fin-cli/
  fin/
    cli.py            # Thin Click wrapper. No logic — all calls go to core.py
    core.py           # All fin logic. Calls alph_interface.py. Framework-agnostic. Permanent.
    alph_interface.py # Explicit surface fin uses from alph. Versioned contract. See below.
    display.py        # Rendering: priority buckets, date headers, status symbols
    editor.py         # Intermediary edit format: serialize → parse → actions (no editor launch)
    config.py         # fin config: default context, editor, date format, wrap width
  tests/
    test_core.py
    test_display.py
    test_editor.py
    conftest.py       # Shared fixtures: isolated tmp pool dirs, synthetic alph configs
  fin               # CLI entry point (script)
  pyproject.toml
```

`alph` is declared as a library dependency in `pyproject.toml`. **fin never imports `alph.core` directly** — all alph calls go through `fin/alph_interface.py`.

### alph_interface.py — The Compatibility Contract

This is the answer to "how do we handle alph version changes without fin breaking?"

`alph_interface.py` is a thin, fully type-annotated module that declares the exact surface fin uses from alph. It re-exports only the types and calls fin needs, behind stable fin-defined signatures:

```python
# fin/alph_interface.py
from alph.core import load_config, create_node, list_nodes, show_node, validate_node
from alph.core import AlphConfig, NodeResult, NodeSummary  # re-export stable types

def alph_load_config() -> AlphConfig: ...
def alph_create_node(pool_path, source, context, tags, meta, ...) -> NodeResult: ...
def alph_list_nodes(pool_path, statuses) -> list[NodeSummary]: ...
def alph_set_node_status(pool_path, node_id, status) -> NodeResult: ...
```

**Why this approach:**
- `fin/core.py` is insulated from alph API changes — only `alph_interface.py` needs to change when alph upgrades
- `alph_interface.py` is the pinning contract. If alph releases a breaking change, the interface module absorbs it in one place
- Tests can mock `alph_interface` entirely, making `core.py` tests fast and hermetic (no filesystem, no git)
- Version pin in `pyproject.toml`: `alph = ">=0.1.34,<0.2.0"` — allows patch/minor, blocks major breaks

**What fin/core.py does:**
- Calls `alph_interface.py` for all alph operations
- Manages the `tasks` registry and context-as-pool mapping
- Parses fin-specific metadata (`#due:`, `#recur:`, `#depends:`, `#i`, `#t`) from content strings into alph `meta` and `tags` fields

**What fin/core.py does NOT do:**
- Import `alph.*` directly
- Duplicate alph's ID generation, node schema, git operations, config loading, or validation logic
- Maintain its own database

---

## The Editor Format

The bulk editor (`fine` / `fin e`) opens tasks as if they were a text file. The goal: **quick review and editing**, with outcomes including closing tasks, adding tags, modifying content, and adding notes.

### Intermediary Format (`FinEditDoc`)

The editor serializes tasks to an **intermediary YAML structure** — not alph's node format, not the old one-line format. This is the canonical representation for editing. Presentation (how it looks in the editor) is separate from the structure.

Each task block:

```yaml
- summary: Write the quarterly report
  id: a1b2c3d4e5f6
  status: active
  tags: [work, important]
  due: 2026-03-20
  notes: |
    Include Q1 metrics and projections.
    Check with finance on headcount numbers.
```

Tasks without notes are still valid and minimal:

```yaml
- summary: Fix the login bug
  id: b2c3d4e5f6a1
  status: active
  tags: [work]
```

### Editor Presentations

The intermediary format is the parse target. Presentation is what actually gets written to the temp file and shown to the user. Two initial presentations:

**Compact** (default — muscle memory friendly, code-folding-ready):
```
[ ] Write the quarterly report                [a1b2c3] #work #important  due:2026-03-20
[ ] Fix the login bug                         [b2c3d4] #work
```
One line per task. ID shown in brackets. Tags as hashtags. Details hidden. When the editor supports code folding and the file is YAML, each block folds to its summary line — same visual, richer editing.

**YAML** (opt-in via `fin e --format yaml`, or set in fin config):
```yaml
- summary: Write the quarterly report
  id: a1b2c3d4e5f6
  status: active
  tags: [work, important]
  due: 2026-03-20
  notes: |
    Include Q1 metrics and projections.
```
Full detail visible. Add notes inline. Fold blocks in a YAML-aware editor (VSCode, Neovim + treesitter) to get the compact view back.

### Outcomes from the Editor

When the user saves and exits, `editor.py` diffs the original `FinEditDoc` against the parsed result and produces `EditAction` objects:

| Change made in editor | Action |
|---|---|
| Delete a task line / block | `CloseAction` (mark archived) |
| Change `status: active` → `status: archived` | `CloseAction` |
| Add `[d]` / `status: suppressed` | `DismissAction` |
| Add a tag | `AddTagAction` |
| Remove a tag | `RemoveTagAction` |
| Edit summary text | `UpdateContentAction` |
| Add/edit `notes:` | `UpdateNotesAction` |
| Add `due:` | `SetDueAction` |
| Add new line / block (no `id:`) | `AddTaskAction` |

**Key design principle**: the edit format is an **input format**, not a storage format. It is never persisted. Parse errors are surfaced to the user before any actions are applied (all-or-nothing per save).

### Editor Priming

The `notes:` field is the hook for editor-side UX. A well-configured editor (VSCode with YAML extension, Neovim with treesitter folding) will:
- Fold each task block to its `summary:` line by default
- Expand on cursor entry to show tags, due, notes
- Validate YAML structure as you type

`fin` can emit a `.editorconfig` or workspace hint into the temp file header (as a YAML comment) that primes supported editors to fold on open. This is best-effort — compact presentation remains the default for editors that don't support it.

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

### Testing Rules

**Never launch an editor in tests.**

The editor pipeline (`fine` / `fin e`) has two distinct halves: (1) the I/O boundary — serialize to a temp file, invoke `$EDITOR`, read it back; and (2) the logic — `parse_edit_doc()`, `diff_edit_actions()`, `apply_edit_actions()`. Only the second half is tested. The first half is a 3-line OS call in `cli.py` that doesn't need unit testing.

Tests for `editor.py` work by:
1. Serializing a known `FinEditDoc` to a string (as `render_edit_doc()` would write to the temp file)
2. Applying a string transformation that mirrors what a user would do in the editor — delete a line, change a `status:` field, add a tag, add a `notes:` block
3. Passing the transformed string to `parse_edit_doc()` → `diff_edit_actions()`
4. Asserting the correct `EditAction` objects are produced

This tests the full parse-and-diff logic without any process spawning, temp files, or blocking waits.

**Tests never touch real user data.**

No test ever reads from or writes to:
- `~/.fin/` or any subdirectory
- `~/.config/alph/config.yaml` or `~/.config/fin/config.yaml`
- Any path under `~` that a real user installation would use

All tests that need a pool directory use pytest's `tmp_path` fixture. All tests that need an alph config construct a synthetic `AlphConfig` object in memory or in `tmp_path`. The `conftest.py` provides:
- `isolated_pool(tmp_path)` — creates a valid pool directory structure under `tmp_path`
- `synthetic_alph_config(tmp_path)` — returns an `AlphConfig` pointing entirely at `tmp_path`
- `mock_alph_interface` — patches `fin.alph_interface` for pure-logic tests that don't need the filesystem at all

The `FIN_POOLS_DIR` environment variable (if set) overrides the default `~/.fin/pools/` path. Tests set this to `tmp_path` for any integration tests that exercise the full stack. CI always runs with `FIN_POOLS_DIR` pointed at a temp directory.

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
- [ ] Add `tests/conftest.py` with `isolated_pool`, `synthetic_alph_config`, and `mock_alph_interface` fixtures
- [ ] Confirm `FIN_POOLS_DIR` env var overrides pool home path (set in all CI runs)

#### A.2 alph Interface Layer (`fin/alph_interface.py`)

Written before `core.py` — this is the dependency boundary. All tests for `core.py` mock this module.

- [ ] `alph_load_config() -> AlphConfig`
- [ ] `alph_ensure_registry(cfg, registry_id, pool_home, context) -> None`
- [ ] `alph_ensure_pool(cfg, registry_id, pool_name, context) -> Path`
- [ ] `alph_create_node(pool_path, source, node_context, tags, meta, content) -> NodeResult`
- [ ] `alph_list_nodes(pool_path, statuses) -> list[NodeSummary]`
- [ ] `alph_set_node_status(pool_path, node_id, status) -> NodeResult`
- [ ] `alph_show_node(pool_path, node_id) -> NodeDetail`
- [ ] Version compatibility note in module docstring: which alph version range this interface was written against
- [ ] Tests: each wrapper calls the correct alph function with correct args (mock `alph.core.*`)

#### A.4 Config Layer (`fin/config.py`)

TDD from here on.

- [ ] `load_fin_config() -> FinConfig` — read `~/.config/fin/config.yaml` (editor, date format, wrap width, default context)
- [ ] `ensure_tasks_registry(alph_cfg) -> None` — idempotently declare `tasks` registry in alph config if absent
- [ ] `ensure_context_pool(context, alph_cfg) -> Path` — idempotently create pool for a context if absent
- [ ] Tests for all three; config is created on first `fin add` call

#### A.5 Content Parser (`fin/core.py`)

- [ ] `parse_fin_content(raw: str) -> ParsedTask` — extract tags (`#label`), meta (`#due:`, `#recur:`, `#depends:`), priority markers (`#i`, `#t`), remaining clean content
- [ ] `build_node_kwargs(parsed: ParsedTask) -> dict` — map ParsedTask fields to alph `create_node()` kwargs (tags, meta, context field)
- [ ] Tests covering: bare text, single label, multiple labels, due date, recur, depends, combined, edge cases (no content, only labels)

#### A.6 Add Task (`fin/core.py`)

- [ ] `add_task(raw_content: str, context: str, alph_cfg) -> NodeResult` — parse content, ensure pool, call `alph_interface.alph_create_node()`
- [ ] Idempotency: alph's SHA ID deduplication is inherited automatically
- [ ] Tests: add task, add duplicate (idempotent), add to named context, labels extracted, meta populated

#### A.7 List Tasks (`fin/core.py`)

- [ ] `list_tasks(context, days, statuses, alph_cfg) -> list[FinTask]` — call `alph_interface.alph_list_nodes()`, filter by date window, return typed list
- [ ] `FinTask` datatype — wraps NodeSummary with fin-specific computed fields (is_important, is_today, due_date, is_overdue)
- [ ] Tests: empty pool, single task, filtering by status, filtering by days window

#### A.8 ID Resolution (`fin/core.py`)

Short-hash prefix matching. No session state, no index file.

- [ ] `resolve_short_id(prefix: str, tasks: list[FinTask]) -> str` — find node ID starting with `prefix`; raise `AmbiguousIDError` if multiple match, `UnknownIDError` if none match
- [ ] `format_short_id(node_id: str) -> str` — return first 6 chars for display
- [ ] Tests: exact 6-char match, longer prefix match, ambiguous prefix raises error, no match raises error, full 12-char passthrough

#### A.9 Display (`fin/display.py`)

- [ ] `render_task_list(tasks: list[FinTask]) -> str` — priority buckets (important, today, regular), date headers, `[ ]` / `[x]` / `[d]` symbols, 6-char short ID column
- [ ] `render_task_detail(task: FinTask) -> str` — single task full view
- [ ] All pure functions (str → str); no I/O
- [ ] Tests: empty list, single task, priority ordering, completed task symbol, dismissed task symbol, overdue indicator

#### A.10 CLI (`fin/cli.py`)

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
- [ ] `fin close a1b2c3` marks it archived via prefix resolution
- [ ] `alph_interface.py` is the only point of contact with `alph.*`; core.py has no direct alph imports
- [ ] All `alph_interface.py`, `core.py`, `display.py` functions have passing tests written test-first
- [ ] `core.py` tests mock `alph_interface` — no filesystem or git required to run unit tests
- [ ] No test writes to `~/.fin/` or `~/.config/`; all filesystem tests use `tmp_path`
- [ ] mypy strict clean, ruff clean

---

### Phase B: User Experience Parity

**Milestone**: Every `fin` command from the original CLI works identically from the user's perspective. Data lives in alph pools.

#### B.1 Bulk Editor (`fin/editor.py` + `fin/cli.py`)

The editor pipeline: `list_tasks()` → `serialize_to_edit_doc()` → temp file → user's `$EDITOR` → `parse_edit_doc()` → `diff_edit_actions()` → `apply_edit_actions()`.

- [ ] `FinEditDoc` — typed intermediary dataclass; list of `FinEditTask` entries (summary, id, status, tags, due, notes)
- [ ] `serialize_to_edit_doc(tasks: list[FinTask]) -> FinEditDoc` — convert FinTask list to intermediary structure
- [ ] `render_edit_doc(doc: FinEditDoc, fmt: Literal['yaml', 'compact']) -> str` — produce the string written to temp file; compact is display-only, yaml is the editable target
- [ ] `parse_edit_doc(text: str, fmt: Literal['yaml', 'compact']) -> FinEditDoc` — parse temp file back to intermediary; compact format is read-only (no edit actions produced from compact diffs — users must use YAML mode to edit)
- [ ] `diff_edit_actions(original: FinEditDoc, edited: FinEditDoc) -> list[EditAction]` — produce `CloseAction`, `DismissAction`, `AddTagAction`, `RemoveTagAction`, `UpdateContentAction`, `UpdateNotesAction`, `SetDueAction`, `AddTaskAction`
- [ ] `apply_edit_actions(actions: list[EditAction], alph_cfg) -> EditResult` — execute via `alph_interface.py`; all-or-nothing (validate all before applying any)
- [ ] `fin e` / `fine` — open editor (default YAML format), parse result, apply actions; the editor invocation itself is a single `subprocess.call([editor, tmpfile])` in `cli.py` — not tested
- [ ] `fin e --compact` — open in compact (read-only) mode for quick review without editing
- [ ] Tests: **never launch an editor**. All `editor.py` tests operate on staged strings:
  - Serialize a known `FinEditDoc` → string via `render_edit_doc()`
  - Apply a string mutation mirroring a user action (delete block, change field, add block)
  - Pass to `parse_edit_doc()` → `diff_edit_actions()` → assert correct `EditAction` list
  - Cases: no changes, add task block, delete block → CloseAction, `status: archived` → CloseAction, `status: suppressed` → DismissAction, add tag, remove tag, edit summary, add notes, add due, new block (no id) → AddTaskAction
  - Parse error cases: malformed YAML → error before any actions applied; missing required field → error with message identifying the block

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

Same pattern as `alph` — same tap, same release workflow shape.

- [ ] Add `fin` formula to `AlpheusCEF/homebrew-tap` alongside the existing `alph` formula
- [ ] `brew tap AlpheusCEF/tap && brew install fin` installs `fin`, `fine`, and `fins` binaries
- [ ] `alph` declared as a Homebrew dependency in the `fin` formula — installs both tools together
- [ ] Release workflow (GitHub Actions on tag): build sdist, update formula SHA in homebrew-tap automatically
- [ ] `brew install alph` and `brew install fin` remain independent — users who want only alph still can

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

## Open Questions

### Resolved

1. **New repo vs. fork**: `AlpheusCEF/fin-cli` — fresh repo, blank slate. ✓
2. **alph version pinning**: `alph_interface.py` is the contract. Pin `alph = ">=0.1.34,<0.2.0"` in pyproject.toml; only `alph_interface.py` absorbs breaking changes. ✓
3. **`tasks` registry pool_home path**: `~/.fin/pools/` — confirmed. ✓
4. **Bulk editor format**: Intermediary `FinEditDoc` YAML structure with two presentations (compact default, YAML opt-in). Editor priming for fold-to-summary-line UX. ✓
5. **Distribution**: Same AlpheusCEF Homebrew tap pattern as `alph`. `brew install fin` via `AlpheusCEF/homebrew-tap`. `alph` declared as a formula dependency. ✓

6. ~~**fin package name (PyPI)**~~ — no PyPI release planned. Homebrew only. ✓
7. **Compact editor parse tolerance**: Compact is display-only; YAML is the edit target. ✓
8. **`notes:` field in alph node**: maps to node body (Markdown below `---` separator). `create_node(content=notes_text)`. ✓
9. **ID model**: short-hash prefix matching (git model). Session-index eliminated. ✓

### Still Open

10. **`update_node()` in alph core** — see Outstanding Items below. Must be resolved before Phase B work begins.

---

## Assessment: Semantic and Conceptual Matchup

### Strong Fits

**context → pool** is near-perfect. Each fin context becomes its own pool in the `tasks` registry. Cross-context queries (`fin list --all-contexts`) fall out from registry-level enumeration at no extra cost. The mental model is identical: a context is a scoped bucket of tasks.

**label → tag** is clean. alph tags are already normalized lowercase strings. `#urgent` becomes `tags: [urgent]` at parse time. No semantic gap.

**priority markers** (`#i`, `#t`) become tags `important` and `today` — fin's display logic reads them back for bucket rendering. No information loss.

**meta fields** (`#due:`, `#recur:`) map to alph's `meta` dict which is an open key-value store by design. The mapping is mechanical.

**open/completed/dismissed → active/archived/suppressed** is the closest behavioral match available. The semantics align well enough: active tasks surface by default, archived tasks are done, suppressed tasks are declined. The only nuance: alph describes `archived` as "no longer relevant — rarely surface." fin queries archived tasks frequently via `fins`. In practice this is fine — archived is still fully queryable; alph's language is descriptive guidance, not a hard filter.

**Short hash IDs** are strictly better than fin's original numeric IDs. Numeric IDs in fin renumber as tasks are deleted and are meaningless across contexts. A short hash is stable — the same task has the same ID forever, survives context moves, and is the same prefix a user would use in `alph show`. This is a genuine UX improvement over the original, not a compromise.

**Git history** as a first-class feature is a real improvement. `fin log a1b2c3` showing when a task was created, tagged, completed — this was impossible with SQLite.

**MCP access** lands for free. Claude can see and manage fin tasks via the existing alph MCP tools the moment the `tasks` registry is declared. No new server code.

### Real Tension: Task Mutability vs Node Immutability

This is the most important thing to be clear-eyed about. alph's design language describes snapshot nodes as frozen moments — "content is immutable at creation time." fin tasks are inherently mutable: you complete them, tag them, add notes, reopen them, change their due dates. The plan's `UpdateContentAction`, `UpdateNotesAction`, `SetDueAction`, and `CloseAction` all require in-place frontmatter or body edits on existing node files.

alph's current `core.py` does not have an `update_node()` function. See Outstanding Items for the full specification.

This is a real gap but not a fatal one. The `alph_interface.py` boundary contains it: the interface declares stable update signatures regardless of the underlying implementation. The gap is a prerequisite for Phase B, not Phase A.

### The Philosophical Gap

alph nodes are designed for *context capture* — decisions, observations, references that increase in value over time. fin tasks are operational — they exist to be completed and discarded. These are genuinely different:

- An alph node ("we chose Postgres because...") is indefinitely relevant and gets richer as more context references it.
- A fin task ("renew registration") has zero long-term value once done.

This matters less than it sounds. The alph schema is flexible enough to hold tasks — nothing in the schema prevents it. The `tasks` registry will simply have a different character than other registries when queried by Claude: mostly short-lived operational items rather than durable decisions. That's fine and expected. Claude reading the `tasks` registry context field ("Personal task lists managed by fin") will understand what it's looking at.

The philosophical difference becomes interesting in Phase C: once fin tasks live in the same system as alph context nodes, a task like "write security design review" can carry a `related_to` reference to the alph pool for that project. That cross-linking was the whole point.

### Feasibility Summary

**Phase A — High confidence.** All operations are creation-time writes and reads. alph's `create_node` and `list_nodes` are the only alph functions needed, both well-tested. The `alph_interface.py` boundary makes this solid.

**Phase B — Conditional on one prerequisite.** `update_node()` in alph must exist before Phase B begins. Everything else (recurrence, dependencies, label filtering, context commands) is pure fin logic with no alph changes needed.

**Phase C — Straightforward.** `fin list --all-contexts` is a loop over pools. MCP access is already working. `fin link` requires `update_node()` (same prerequisite as Phase B). Git history commands are thin shell calls.

**Phase D — Standard.** Migration from SQLite is mechanical. Homebrew formula follows the established pattern.

---

## Outstanding Items

### `update_node()` in alph core — Required Before Phase B

**The gap**: alph has `create_node()` but no function to update an existing node's frontmatter or body. fin needs this for every mutation operation: completing a task, adding tags via the editor, changing a due date, adding notes.

**What's needed** in `alph.core`:

```python
def update_node(
    pool_path: Path,
    node_id: str,
    *,
    status: str | None = None,          # active | archived | suppressed
    tags: list[str] | None = None,       # replaces existing tags if provided
    tags_add: list[str] | None = None,   # merge into existing tags
    tags_remove: list[str] | None = None,# remove from existing tags
    meta: dict[str, str] | None = None,  # merge into existing meta
    content: str | None = None,          # replaces node body if provided
    summary: str | None = None,          # replaces the `context` frontmatter field
    related_to: list[str] | None = None, # replaces related_to list if provided
    related_add: list[str] | None = None,# append to related_to
) -> NodeResult:
    ...
```

**Behavior**:
- Reads the existing node file
- Parses frontmatter
- Applies only the fields passed (None = leave untouched)
- Re-validates the modified frontmatter against the node schema before writing
- Writes the file back in-place (ruamel.yaml to preserve comment formatting)
- If `auto_commit` is configured, commits with message `alph: update node <id>`
- Returns `NodeResult` with the updated node ID and path

**Tags semantics**: `tags=` is a full replacement (sets the list to exactly this). `tags_add=` merges without duplicates. `tags_remove=` removes named tags. Only one of `tags` or `tags_add`/`tags_remove` should be passed in a single call; passing `tags=` together with `tags_add=` is an error.

**Idempotency**: calling `update_node()` with the same values as the current state is a no-op (no file write, no commit). Detect by comparing computed values before writing.

**What fin's `alph_interface.py` exposes**:

```python
def alph_update_node(
    pool_path: Path,
    node_id: str,
    *,
    status: str | None = None,
    tags_add: list[str] | None = None,
    tags_remove: list[str] | None = None,
    meta: dict[str, str] | None = None,
    content: str | None = None,
    summary: str | None = None,
    related_add: list[str] | None = None,
) -> NodeResult: ...
```

fin does not use `tags=` (full replacement) — always uses `tags_add`/`tags_remove` to avoid clobbering tags set by other tools (e.g. alph CLI or MCP).

**Where this needs to be implemented**: `alph.core` in the `alph-cli` repo. This should be raised as a GitHub issue on `AlpheusCEF/alph-cli` before Phase B begins, implemented TDD-first in that repo, released in a patch version, and referenced in `alph_interface.py`'s version compatibility note.

**Interim option if alph update lands late**: `alph_interface.py` can implement a temporary in-process version that directly edits the YAML file using ruamel.yaml, bypassing `alph.core`. This keeps fin unblocked and gets replaced once the real alph function ships. The fin interface signature stays identical — the implementation swaps under it.
