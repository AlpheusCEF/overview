# AlpheusCEF Human Test Script

Walk through this top to bottom. Each section is a checkpoint — verify the
expected output before moving on. Commands assume a clean macOS environment.
Every code block is written to be copy-pasted independently.

---

## Prerequisites

```bash
brew --version
```

```bash
python3 --version
```

```bash
gh auth status
```

---

## 1. Install via Homebrew

```bash
brew tap AlpheusCEF/tap
brew install alph
```

Expected: no errors, formula installs into a virtualenv under Cellar.

```bash
which alph
which alph-mcp
```

```bash
alph --version
```

Expected: `alph 0.1.x`

```bash
alph --help
```

```bash
alph -h
```

Expected: help shows top-level commands: `add`, `list`, `show`, `validate`, `registry`, `pool`, `config`, `defaults`.
Both `--help` and `-h` should work.

---

## 2. CLI — Registry and Pool Init

### 2a. Create a scratch workspace

```bash
mkdir -p /tmp/alph-test
```

### 2b. Create a registry

```bash
alph registry init \
  --pool-home /tmp/alph-test/registry \
  --id test-household \
  --context "Scratch registry for human test run." \
  --name "Test Household"
```

Expected (first registry — no default exists yet):
```
registry created: test-household
  pool home: /tmp/alph-test/registry
  config: /Users/<you>/.config/alph/config.yaml
  set as default registry
```

Notes:
- `config:` shows the full expanded path, not `~`
- No `config.yaml` is written inside `/tmp/alph-test/registry` — the registry
  definition (id, pool home path, context, name) lives entirely in `~/.config/alph/config.yaml`

```bash
cat ~/.config/alph/config.yaml
```

Expected:
```yaml
default_registry: test-household
registries:
  test-household:
    pool_home: /tmp/alph-test/registry
    context: Scratch registry for human test run.
    name: Test Household
```

### 2c. Inspect what registries alph knows about

```bash
alph registry list
```

Expected: a table with `test-household`, `Test Household`, the context text,
and the pool home directory path.

### 2d. Create a pool inside the registry

```bash
alph pool init \
  --registry test-household \
  --name vehicles \
  --context "Vehicle maintenance and purchase records."
```

Expected:
```
pool created: vehicles
  registry: test-household
  path:     /tmp/alph-test/registry/vehicles
  config:   /Users/<you>/.config/alph/config.yaml
```

```bash
ls /tmp/alph-test/registry/vehicles/
```

Expected: `snapshots/  live/`

### 2e. List pools in the registry

```bash
alph pool list
```

Expected: a table with `test-household`, `vehicles`, type `subdir`, the context text, and the full path.
The registry column appears first. (Uses default registry from config.)

### 2f. Error behavior — unknown registry

```bash
alph pool init \
  --registry ghost-registry \
  --name demo \
  --context "Demo pool."
```

Expected: exit non-zero with `ghost-registry not found`, followed by a list
of known registries (test-household should appear).

---

## 3. CLI — Add Nodes

The `--pool` flag is explicit throughout this section. After section 5
(config defaults), you will see how to omit it.

```bash
alph add \
  --pool /tmp/alph-test/registry/vehicles \
  --context 'Purchased 2022 Subaru Outback Wilderness, $38,200. VIN: 4S4BTGND7N3123456.' \
  --creator test@example.com
```

Expected: `node created: <12-char-id>` + `path: .../snapshots/<id>.md`

Note: use single quotes around the context string when it contains `$` amounts —
double quotes cause bash to expand `$38` as a variable (to empty).

```bash
alph add \
  --pool /tmp/alph-test/registry/vehicles \
  --context 'Purchased 2022 Subaru Outback Wilderness, $38,200. VIN: 4S4BTGND7N3123456.' \
  --creator test@example.com
```

Expected: `duplicate: node already exists (created by test@example.com)`

```bash
alph add \
  --pool /tmp/alph-test/registry/vehicles \
  --context "Outback due for 10k service — oil change, tire rotation, multi-point inspection." \
  --creator test@example.com \
  --type live
```

Expected: `node created: <different-id>` + path ends in `live/`

```bash
alph add \
  --pool /tmp/alph-test/registry/vehicles \
  --context 'Replaced wiper blades, passenger side was streaking badly. $22 at AutoZone.' \
  --creator test@example.com \
  --status archived
```

Expected: `node created: <id>`

---

## 4. CLI — List and Show

```bash
alph list --pool /tmp/alph-test/registry/vehicles
```

Expected: 2 rows — the snapshot purchase node and the live 10k-service node.
The wiper blade node (status: archived) is NOT shown.

```bash
alph list --pool /tmp/alph-test/registry/vehicles -s archived
```

Expected: 1 row — only the archived wiper blade node. Active nodes are NOT shown.

```bash
alph list --pool /tmp/alph-test/registry/vehicles -s archived,suppressed
```

Expected: same 1 row (no suppressed nodes exist yet). Demonstrates comma-separated filter.

```bash
alph list --pool /tmp/alph-test/registry/vehicles -s all
```

Expected: 3 rows — all nodes regardless of status.

```bash
alph list --pool /tmp/alph-test/registry/vehicles -v
```

Expected: same table output preceded by DEBUG log lines showing config load and pool resolution.

```bash
alph list --pool /tmp/alph-test/registry/vehicles -o json
```

Expected: a JSON array of node objects. No rich table, no header.

```bash
alph list --pool /tmp/alph-test/registry/vehicles -o csv
```

Expected: a CSV with a header row followed by one row per active node.

For the next two commands, copy an ID from the list output above and substitute it:

```bash
alph show <paste-id-here> --pool /tmp/alph-test/registry/vehicles
```

Expected: full node display with `id`, `context`, `type`, `source`, `creator`, `timestamp`.

```bash
alph l --pool /tmp/alph-test/registry/vehicles
```

Expected: same output as `alph list` (short alias).

```bash
alph s <paste-id-here> --pool /tmp/alph-test/registry/vehicles
```

Expected: same output as `alph show` (short alias).

---

## 5. CLI — Config Defaults (optional but recommended for daily use)

`alph registry init` already wrote `default_registry` and `alph pool init` already
wrote `default_pool`. The missing piece for daily use is `creator`. This step
adds `creator` to the config, preserving the existing registry and pool entries.

```bash
mkdir -p ~/.config/alph
cat > ~/.config/alph/config.yaml << 'EOF'
creator: test@example.com
default_registry: test-household
default_pool: vehicles
registries:
  test-household:
    pool_home: /tmp/alph-test/registry
    context: Scratch registry for human test run.
    name: Test Household
EOF
```

```bash
alph add -c "Oil change at Valvoline, 10,200 miles, full synthetic 0W-20."
```

Expected: `node created: <id>`. No `--pool` or `--creator` needed.

What alph resolved: `default_registry=test-household` →
`registries[test-household].pool_home=/tmp/alph-test/registry` →
`default_pool=vehicles` → pool = `/tmp/alph-test/registry/vehicles`.

```bash
alph list
```

Expected: table including the Valvoline oil change node.

---

## 6. CLI — Config Discovery

```bash
alph config list
```

Expected: a table with at least two rows — the global `~/.config/alph/config.yaml`
(marked `global`, `exists`) and any local `config.yaml` files found walking up from
the current directory. Footer explains merge order (global first, most specific wins).

```bash
alph config show ~/.config/alph/config.yaml
```

Expected: YAML content printed with syntax highlighting (monokai theme).

```bash
alph config show /tmp/alph-test/does-not-exist/config.yaml
```

Expected: `not found: ...` message followed by two hint lines — one pointing to
`alph registry init`, one pointing to `alph defaults`. No template dump.

```bash
alph defaults
```

Expected: a summary of the currently resolved defaults — `creator`, `default_registry`,
`default_pool`, `auto_commit`, and the resolved pool path. Values not yet configured
show as `not set`.

---

## 7. CLI — Validate

```bash
alph validate --pool /tmp/alph-test/registry/vehicles
```

Expected: `N nodes in pool vehicles valid.`

```bash
alph validate --pool /tmp/alph-test/registry/vehicles -v
```

Expected: same `N nodes in pool vehicles valid.` result, preceded by DEBUG log lines.

```bash
sed -i '' '/schema_version/d' /tmp/alph-test/registry/vehicles/snapshots/*.md
```

```bash
alph validate --pool /tmp/alph-test/registry/vehicles
```

Expected: `invalid: <filename>: missing required field: 'schema_version'`

```bash
mkdir -p /tmp/alph-test/registry/empty-pool/snapshots
```

```bash
mkdir -p /tmp/alph-test/registry/empty-pool/live
```

```bash
alph validate --pool /tmp/alph-test/registry/empty-pool
```

Expected: `no nodes found in pool empty-pool.`
Not `N nodes in pool ... valid.` — an empty pool is reported distinctly.

```bash
rm -rf /tmp/alph-test
```

```bash
alph validate --pool /tmp/alph-test/registry/vehicles
```

Expected: `error: pool not found: /tmp/alph-test/registry/vehicles`
Not `N nodes ... valid.` — a missing pool is an error, not a valid result.

---

## 8. Demo Registry — Household Seed Data

```bash
cd /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example
```

```bash
poetry -C /Users/cpettet/git/chasemp/AlpheusCEF/alph-cli run python "$(pwd)/seed.py" --wipe
```

Expected: `28 total`, 3 pools created, 9+9+10 nodes.

```bash
alph list --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/vehicles
```

```bash
alph list --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/appliances
```

```bash
alph list --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/remodeling
```

Expected: tables showing nodes. Remodeling has 10 (includes the 2025 capital plan node).

```bash
alph show 9eb6b033c1de --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/remodeling
```

Expected: node with `related: appliances::a76746c51d46, 3f9a51c99832`
This demonstrates the cross-pool `pool_name::node_id` format.

```bash
alph show 5d4e71fbe603 --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/vehicles
```

Expected: `related: 2079032c3079`

```bash
alph validate --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/vehicles
```

```bash
alph validate --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/appliances
```

```bash
alph validate --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/remodeling
```

Expected: `N nodes in pool <name> valid.` for all three.

---

## 9. MCP Server — Smoke Test

```bash
alph-mcp &
```

Expected: server starts without error (FastMCP logs to stderr).

```bash
ps aux | grep alph-mcp | grep -v grep
```

Expected: process appears in the list.

```bash
pkill -f alph-mcp
```

For a proper MCP test, configure Claude Code to use the server:

**`~/.claude.json`** (or Claude Desktop config):
```json
{
  "mcpServers": {
    "alph": {
      "command": "alph-mcp"
    }
  }
}
```

Then open a Claude Code session and ask:
> "Using alph MCP tools, list all nodes in the pool at /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/remodeling"

Expected: Claude calls `list_pool_nodes` and returns the 10 remodeling nodes.

---

## 10. CI Check

```bash
cd /Users/cpettet/git/chasemp/AlpheusCEF/alph-cli
gh run list --limit 5
```

```bash
gh run view --log
```

Expected: tests, mypy, ruff all passing.

---

## 11. Homebrew Formula

```bash
cd /Users/cpettet/git/chasemp/AlpheusCEF/homebrew-tap
brew audit --strict Formula/alph.rb
```

Expected: no errors. Warnings about non-`homebrew/core` tap are normal.

```bash
brew reinstall alph
```

```bash
alph --help
alph-mcp --help
```

---

## 12. Setup: HOMEBREW_TAP_TOKEN (for future releases)

For automatic formula updates on every release, add a PAT to the alph-cli repo:

1. Go to GitHub → Settings → Developer settings → Personal access tokens (classic)
2. Create token with `repo` scope (for pushing to homebrew-tap)
3. Go to `https://github.com/AlpheusCEF/alph-cli/settings/secrets/actions`
4. Add secret named `HOMEBREW_TAP_TOKEN` with the token value

After this, tagging a new release (`git tag v0.X.0 && git push origin v0.X.0`)
will automatically update the formula in homebrew-tap via the release workflow.

---

## Checklist

- [ ] `brew install alph` works cleanly
- [ ] Both `alph` and `alph-mcp` binaries in PATH
- [ ] `alph --version` prints `alph 0.1.x`
- [ ] `alph --help` shows: `add`, `list`, `show`, `validate`, `registry`, `pool`, `config`, `defaults`
- [ ] `alph registry init` sets default when no default exists; reports full expanded pool home and config path
- [ ] `alph registry list` shows registry ID, name, context, pool home path
- [ ] `alph pool init --registry <id>` finds registry from global config by ID
- [ ] `alph pool init --registry ghost` errors and shows known registries
- [ ] `alph pool list` lists pools in the default registry with registry, name, type, context, path
- [ ] `alph pool list --registry <id>` lists pools in the specified registry
- [ ] `alph add` deduplicates correctly (same context → "duplicate: node already exists")
- [ ] `alph add` with `$` in context: use single quotes to prevent bash expansion
- [ ] `alph list` default shows active only; `-s archived` shows only archived (exclusive); `-s all` shows everything; `-s foo,bar` comma-separation works
- [ ] `alph list -o json` outputs JSON array; `-o csv` outputs CSV with header row
- [ ] `alph list --pool vehicles` resolves pool by name from registry config
- [ ] `alph show` displays all fields including `related:`
- [ ] `alph validate` catches schema violations
- [ ] `alph validate` success prints `N nodes in pool <name> valid.`
- [ ] `alph validate` on missing pool directory errors (not a valid result)
- [ ] `alph validate` on empty pool prints `no nodes found in pool <name>.`
- [ ] Short aliases work: `alph l`, `alph a`, `alph s`, `alph v`
- [ ] Per-command `-v`/`--verbose` flag works: `alph list -v`, `alph validate -v`
- [ ] Config defaults (`default_registry`, `default_pool`, `creator`) resolve correctly
- [ ] `alph add` / `alph list` work without `--pool` / `--creator` when config set
- [ ] `alph config list` shows config discovery tree with exists/missing status
- [ ] `alph config show <path>` displays YAML with syntax highlighting
- [ ] `alph config show <missing-path>` shows "not found" + hints to `registry init` and `alph defaults` (no template dump)
- [ ] `alph defaults` shows resolved creator, registry, pool, auto_commit, and resolved pool path; unset values show as `not set`
- [ ] Demo registry seeds 28 nodes cleanly
- [ ] Cross-pool `related:` field renders correctly on show
- [ ] `alph-mcp` starts without error
- [ ] MCP tools callable from Claude Code session
- [ ] CI green on GitHub Actions
