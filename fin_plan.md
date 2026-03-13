# fin-over-alph: Rewrite Plan

**Repo**: `AlpheusCEF/fin-cli` — alph as imported library, fin UX preserved

---

## The Idea

`fin` is a battle-tested daily task CLI. Its UX is fast and intuitive — `fin "do the thing"`, `fin`, `fins` — and worth keeping. But its backend is SQLite with no relationship to the AlpheusCEF context model.

The insight: fin's primitives map cleanly onto alph's primitives. Tasks are snapshot nodes. Contexts are pools. Labels are tags. Swapping SQLite for alph core gives:

- **Persistent, portable, human-readable tasks** (Markdown + YAML, not binary DB)
- **Registry-level cross-context visibility** (`alph list --registry` across all contexts)
- **Reuse of alph's tags**, `related_to`, `status`, `meta` fields
- **Git history on every task** — who added, when, what changed
- **MCP access** — Claude manages tasks via existing alph MCP tools
- **Zero new backend** — alph core is already tested and typed

---

## Primitive Mapping

| fin concept | alph concept | Notes |
|---|---|---|
| `context` (e.g. `-c work`) | **pool** | Each context becomes a pool in a `tasks` registry |
| `label` / hashtag | **tag** | `#urgent` → `tags: [urgent]` |
| task (unit of work) | **snapshot node** | `node_type: snapshot`, `content_type: task` |
| open/completed/dismissed | alph `status` + tag | `active` = open, `archived` = completed, `suppressed` = dismissed |
| priority labels `#i`, `#t` | tags `important`, `today` | Rendered as priority buckets in display |
| `due_date` (`#due:2025-08-10`) | `meta.due` | Parsed from content at add time |
| `depends:task_id` | `related_to` | Namespaced node reference |
| `recur:daily\|weekly\|monthly` | `meta.recur` | Handled in fin display logic |
| numeric task ID | alph node ID (12-char) | fin displays first 6 chars; prefix match; no session state |
| SQLite DB | git repo (Markdown + YAML) | Pool = `~/.fin/pools/<context>/` in a `tasks` registry |

### The Registry

A single registry called `tasks` in alph config. `pool_home` defaults to `~/.fin/pools/`. Each fin context is a subdirectory pool.

```yaml
registries:
  tasks:
    pool_home: ~/.fin/pools
    context: "Personal task lists managed by fin"
```

### ID Bridging

Short-hash prefix matching (git model). `fin list` shows first 6 chars in brackets. `fin close a1b2c3` does prefix match. Ambiguous prefix → error asking for more chars. Full 12-char always resolves.

Strictly better than original numeric IDs: stable, survives context moves, same prefix as `alph show`. No session-index file. `index.py` is eliminated.

---

## Architecture

```
fin-cli/
  fin/
    cli.py            # Thin Click wrapper — no logic, calls core.py
    core.py           # All fin logic. Calls alph_interface.py. Framework-agnostic
    alph_interface.py # Explicit surface fin uses from alph. Versioned contract
    display.py        # Rendering: priority buckets, date headers, status symbols
    editor.py         # Intermediary edit format: serialize -> parse -> actions
    config.py         # fin config: default context, editor, date format, wrap width
  tests/
    test_core.py, test_display.py, test_editor.py
    conftest.py       # isolated_pool, synthetic_alph_config, mock_alph_interface
```

### alph_interface.py — The Compatibility Contract

fin never imports `alph.*` directly. All alph calls go through `alph_interface.py`:

```python
from alph.core import load_config, create_node, update_node, list_nodes, show_node, validate_node
from alph.core import AlphConfig, NodeResult, UpdateResult, NodeSummary

def alph_load_config() -> AlphConfig: ...
def alph_create_node(pool_path, source, context, tags, meta, ...) -> NodeResult: ...
def alph_list_nodes(pool_path, statuses) -> list[NodeSummary]: ...
def alph_set_node_status(pool_path, node_id, status) -> UpdateResult: ...
```

Version pin: `alph = ">=0.1.34,<0.2.0"` — allows patch/minor, blocks major breaks. Only `alph_interface.py` absorbs breaking changes.

---

## The Editor Format

Bulk editor (`fine` / `fin e`) opens tasks for quick review and editing.

### Intermediary format (`FinEditDoc`)

Each task block as YAML:

```yaml
- summary: Write the quarterly report
  id: a1b2c3d4e5f6
  status: active
  tags: [work, important]
  due: 2026-03-20
  notes: |
    Include Q1 metrics and projections.
```

### Presentations

**Compact** (default): One line per task, muscle-memory friendly.
```
[ ] Write the quarterly report       [a1b2c3] #work #important  due:2026-03-20
```

**YAML** (opt-in via `fin e --format yaml`): Full detail, editable. Compact is display-only.

### Editor outcomes

Diff original vs parsed result → `EditAction` objects: `CloseAction`, `DismissAction`, `AddTagAction`, `RemoveTagAction`, `UpdateContentAction`, `UpdateNotesAction`, `SetDueAction`, `AddTaskAction`.

All-or-nothing: parse errors surfaced before any actions apply.

---

## Phases

### Phase A: Primitive Mapping and Scaffolding

**Milestone**: `fin add` writes a valid alph snapshot node. `fin list` reads them back with fin display format.

- **A.1 Repo scaffolding**: New repo, Poetry, Python 3.12+, mypy strict, ruff, agents, conftest fixtures, `FIN_POOLS_DIR` env var
- **A.2 alph interface layer**: `alph_load_config()`, `alph_ensure_registry()`, `alph_ensure_pool()`, `alph_create_node()`, `alph_list_nodes()`, `alph_set_node_status()`, `alph_show_node()`. Tests mock `alph.core.*`
- **A.3 Config layer**: `load_fin_config()`, `ensure_tasks_registry()`, `ensure_context_pool()`. Config created on first `fin add`
- **A.4 Content parser**: `parse_fin_content()` — extract tags, meta (`#due:`, `#recur:`, `#depends:`), priority markers. `build_node_kwargs()` maps to alph params
- **A.5 Add task**: `add_task()` — parse, ensure pool, create node. Inherits alph SHA dedup
- **A.6 List tasks**: `list_tasks()` — call alph, filter by date window. `FinTask` wraps `NodeSummary` with computed fields (is_important, is_today, due_date, is_overdue)
- **A.7 ID resolution**: `resolve_short_id()` — prefix match, `AmbiguousIDError` / `UnknownIDError`. `format_short_id()` — first 6 chars
- **A.8 Display**: `render_task_list()` — priority buckets, date headers, status symbols, short ID. `render_task_detail()`. All pure functions
- **A.9 CLI**: `fin "content"` / `fin add`, `fin` / `fin list`, `fin list -d 7`, `fin list -c work`, `fin close <id>`, `fin dismiss <id>`, `fin open <id>`

**Exit criteria**: `fin "write the plan"` creates valid node, `fin` lists it, `fin close a1b2c3` archives via prefix match. All tests written first. core.py tests mock alph_interface. No test touches `~/.fin/` or `~/.config/`. mypy strict clean.

---

### Phase B: User Experience Parity

**Milestone**: Every original `fin` command works identically. Data lives in alph pools.

- **B.1 Bulk editor**: `FinEditDoc` intermediary, `serialize_to_edit_doc()`, `render_edit_doc()` (compact/YAML), `parse_edit_doc()`, `diff_edit_actions()`, `apply_edit_actions()`. Tests never launch an editor — operate on staged strings
- **B.2 Completed view**: `fins` / `fin done` lists archived. `fins "content"` adds and immediately completes (log mode)
- **B.3 Status filtering**: `list_tasks(statuses=[...])`, `fin list -s open,done`
- **B.4 Label filtering**: `filter_by_labels()` with AND/OR/NOT, `fin list -l "work and urgent"`, `fin list-labels`
- **B.5 Recurring tasks**: `get_recur_meta()`, `spawn_recurrence()` — on close, create next instance
- **B.6 Dependencies**: `resolve_depends()` via `related_to`, blocked indicator when dep is open
- **B.7 Context management**: `fin context`, `fin context set <name>`, `fin context clear`
- **B.8 Config**: `fin config set/show` for editor, date_format, wrap_width, default_context

**Exit criteria**: All original commands have equivalents. Editor round-trip works. Recurring spawning works. Dependency blocking renders. 100% TDD, mypy strict.

---

### Phase C: alph-Native Enhancements

**Milestone**: fin gains capabilities impossible with SQLite.

- **C.1 Cross-context view**: `fin list --all-contexts` — query all pools in `tasks` registry, merge results
- **C.2 MCP access**: Verify alph MCP tools work against fin's `tasks` registry pools. Write SKILL fragment for fin tag conventions
- **C.3 Related tasks**: `fin link <id> <id>` — add `related_to` reference, cross-pool supported
- **C.4 Git history**: `fin log <id>`, `fin diff <id>` — thin shell delegation to git
- **C.5 Export/import**: `fin export --format json|csv|txt`, `fin import <file>` — round-trip, idempotent via SHA dedup

---

### Phase D: Distribution

**Milestone**: `brew install fin` works. Existing users can migrate.

- **D.1 Migration tool**: `fin migrate --from <sqlite_db_path>` — read SQLite, create nodes preserving timestamps/labels/status. Idempotent
- **D.2 Homebrew formula**: Same tap (`AlpheusCEF/homebrew-tap`), `alph` as formula dependency
- **D.3 CI/CD**: GitHub Actions on push/PR and release

---

## Testing Rules

- **Never launch an editor in tests.** Test the logic (parse, diff, apply), not the I/O boundary
- **Tests never touch real user data.** All use `tmp_path`. `conftest.py` provides `isolated_pool`, `synthetic_alph_config`, `mock_alph_interface`
- **`FIN_POOLS_DIR` env var** overrides `~/.fin/pools/` — set in all CI runs

---

## Assessment: Semantic Fit

### Strong fits

- **context -> pool**: Near-perfect. Cross-context queries fall out from registry enumeration
- **label -> tag**: Clean. Normalized lowercase strings
- **priority markers** (`#i`, `#t`): Become tags `important`/`today` for bucket rendering
- **meta fields** (`#due:`, `#recur:`): Map to alph's open `meta` dict
- **Short hash IDs**: Strictly better than original numeric IDs (stable, survives moves)
- **Git history**: Real improvement. `fin log a1b2c3` was impossible with SQLite
- **MCP access**: Free — existing alph MCP tools work the moment `tasks` registry exists

### Real tension: mutability

alph snapshot nodes are conceptually frozen moments. fin tasks are inherently mutable. `update_node()` resolves this mechanically — status, tags, meta, content, and context can all be modified. The tension is philosophical, not technical.

### The philosophical gap

alph nodes are for context capture (indefinitely relevant). fin tasks are operational (complete and discard). This matters less than it sounds — the `tasks` registry will simply have a different character than other registries. Claude reading the context field ("Personal task lists managed by fin") understands what it's looking at. The gap becomes interesting in Phase C: a task like "write security review" can `related_to` the project's alph pool.

### Feasibility

- **Phase A** — High confidence. Creation-time writes and reads only
- **Phase B** — Ready to start. `update_node()` prerequisite resolved
- **Phase C** — Straightforward. Registry-level queries, thin shell calls
- **Phase D** — Standard. Migration is mechanical, Homebrew follows established pattern

---

## Resolved Questions

1. **New repo vs. fork**: `AlpheusCEF/fin-cli` — fresh repo
2. **alph version pinning**: `alph_interface.py` is the contract
3. **`tasks` registry path**: `~/.fin/pools/`
4. **Editor format**: Intermediary YAML with compact/YAML presentations
5. **Distribution**: Same Homebrew tap pattern
6. **PyPI**: No release planned — Homebrew only
7. **Compact editor parse**: Display-only; YAML is the edit target
8. **Notes field**: Maps to node body (Markdown below `---`)
9. **ID model**: Short-hash prefix matching, session-index eliminated
10. **`update_node()`**: Implemented in alph-cli. `UpdateResult` return type. `context` parameter (not `summary`)
