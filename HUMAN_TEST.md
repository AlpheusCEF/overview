# AlpheusCEF Human Test Script

Walk through this top to bottom. Each section is a checkpoint — verify the
expected output before moving on. Commands assume a clean macOS environment.

---

## Prerequisites

```bash
# Verify Homebrew is installed
brew --version

# Verify Python 3.12+ is available (for pip fallback)
python3 --version

# Verify gh CLI is installed and authed (for GitHub checks)
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
# Verify both entry points installed
which alph
which alph-mcp
alph --help
alph -h
```

Expected: help shows top-level commands: `add`, `list`, `show`, `validate`, `registry`, `pool`, `config`.
Both `--help` and `-h` should work.

---

## 2. CLI — Registry and Pool Init

### 2a. Create a scratch workspace

```bash
mkdir -p /tmp/alph-test
```

### 2b. Create a registry

```bash
# --home: the directory where pool subdirectories will be created.
#         A config.yaml with registry metadata is written here.
#         The registry is also registered in ~/.config/alph/config.yaml
#         so all alph commands can find it by ID without explicit paths.
# --id:   machine-readable identifier used everywhere.
# --name: optional human-readable label.
alph registry init \
  --home /tmp/alph-test/registry \
  --id test-household \
  --context "Scratch registry for human test run." \
  --name "Test Household"
```

Expected output (first registry — no default exists yet):
```
registry created: test-household
  home:   /tmp/alph-test/registry
  config: ~/.config/alph/config.yaml
  set as default registry
```

Note: no `config.yaml` is written inside `/tmp/alph-test/registry`. The registry
definition (id, home path, context, name) lives entirely in `~/.config/alph/config.yaml`.

```bash
# Inspect the global config — this is the single source of truth
cat ~/.config/alph/config.yaml
```

The global config now has:
```yaml
default_registry: test-household
registries:
  test-household:
    home: /tmp/alph-test/registry
    context: Scratch registry for human test run.
    name: Test Household
```

### 2b. Inspect what registries alph knows about

```bash
alph registry list
```

Expected: a table with `test-household`, `Test Household`, the context text,
and the home directory path.

### 2c. Create a pool inside the registry

```bash
# pool init takes a registry ID (or name), not a path.
# alph resolves the registry from the global config by ID.
# The pool will be created as a subdirectory of the registry home:
#   /tmp/alph-test/registry/vehicles/
alph pool init \
  --registry test-household \
  --name vehicles \
  --context "Vehicle maintenance and purchase records."
```

Expected output:
```
pool created: vehicles
  registry: test-household
  path:     /tmp/alph-test/registry/vehicles
  config:   ~/.config/alph/config.yaml
```

```bash
# Verify the structure
ls /tmp/alph-test/registry/vehicles/
# Expected: snapshots/  pointers/  .alph/
```

### 2d. Error behavior — unknown registry

```bash
# Try to create a pool in a registry that doesn't exist.
# alph should error and show you what registries ARE known.
alph pool init \
  --registry ghost-registry \
  --name demo \
  --context "Demo pool."
```

Expected: exit non-zero with `ghost-registry not found`, followed by a list
of known registries (test-household should appear).

---

## 3. CLI — Add Nodes

The `--pool` flag is always explicit here to make the target clear. After
section 5 (config defaults), you will see how to omit it.

```bash
POOL=/tmp/alph-test/registry/vehicles

# Add a fixed node (snapshot — immutable record)
alph add \
  --pool $POOL \
  --context "Purchased 2022 Subaru Outback Wilderness, $38,200. VIN: 4S4BTGND7N3123456." \
  --creator test@example.com
```

Expected: `node created: <12-char-id>` + `path: .../snapshots/<id>.md`

```bash
# Add it again — should deduplicate
alph add \
  --pool $POOL \
  --context "Purchased 2022 Subaru Outback Wilderness, $38,200. VIN: 4S4BTGND7N3123456." \
  --creator test@example.com
```

Expected: `duplicate: node already exists (created by test@example.com)`

```bash
# Add a live node (pointer — references something that changes)
alph add \
  --pool $POOL \
  --context "Outback due for 10k service — oil change, tire rotation, multi-point inspection." \
  --creator test@example.com \
  --type live
```

Expected: `node created: <different-id>` + path ends in `pointers/`

```bash
# Add a node with archived status (historical, excluded from default list)
alph add \
  --pool $POOL \
  --context "Replaced wiper blades, passenger side was streaking badly. $22 at AutoZone." \
  --creator test@example.com \
  --status archived
```

Expected: `node created: <id>`

---

## 4. CLI — List and Show

```bash
POOL=/tmp/alph-test/registry/vehicles

# Default: active nodes only (archived is excluded)
alph list --pool $POOL
```

Expected: 2 rows — the fixed purchase node and the live 10k-service node.
The wiper blade node (status: archived) is NOT shown.

```bash
# Expand to include archived nodes
alph list --pool $POOL -s archived
```

Expected: 3 rows — adds the archived wiper blade node with status column showing `archived`.

```bash
# Show a specific node — copy an ID from the list output
NODE_ID=<paste-id-from-list>
alph show $NODE_ID --pool $POOL
```

Expected: full node display with `id`, `context`, `type`, `source`, `creator`, `timestamp`.

---

## 5. CLI — Config Defaults (optional but recommended for daily use)

Setting defaults means you can omit `--pool` and `--creator` on every command.
This is what `default_registry` (already written to the registry config) enables
— but you also need `default_pool` and a registered path for the pool resolution
to work end-to-end.

```bash
# Write a global alph config
mkdir -p ~/.config/alph
cat > ~/.config/alph/config.yaml << 'EOF'
creator: test@example.com
default_registry: test-household
default_pool: vehicles
registries:
  test-household:
    home: /tmp/alph-test/registry
    context: Scratch registry for human test run.
    name: Test Household
EOF
```

```bash
# Now add without --pool or --creator
alph add -c "Oil change at Valvoline, 10,200 miles, full synthetic 0W-20."
```

Expected: `node created: <id>`. No --pool needed — resolved via
`registries[default_registry].home / default_pool`.

What alph is doing: `~/.config/alph/config.yaml` → `default_registry=test-household`
→ `registries[test-household].home=/tmp/alph-test/registry` → `default_pool=vehicles`
→ pool = `/tmp/alph-test/registry/vehicles`. Everything is in one config file.

```bash
# List without --pool
alph list
```

Expected: table including the Valvoline oil change node.

---

## 6. CLI — Config Discovery

```bash
# List all config files alph checks when loading config (global + walk up from cwd)
alph config list
```

Expected: a table with at least two rows — the global `~/.config/alph/config.yaml` (marked
`global`, `exists`) and any local `config.yaml` files found walking up from the current
directory. The footer explains merge order (global first, most specific wins).

```bash
# Show a config file with syntax highlighting
alph config show ~/.config/alph/config.yaml
```

Expected: YAML content printed with syntax highlighting (monokai theme).

```bash
# Show a path that doesn't exist — should print bootstrap instructions + template
alph config show /tmp/alph-test/does-not-exist/config.yaml
```

Expected: `not found: ...` message, followed by `alph registry init` instructions and
a commented YAML template with all standard keys and descriptions.

---

## 7. CLI — Validate

```bash
alph validate --pool /tmp/alph-test/registry/vehicles
```

Expected: `all nodes valid.`

```bash
# Corrupt a node manually to test failure detection
SNAP=$(ls /tmp/alph-test/registry/vehicles/snapshots/*.md | head -1)
# Remove the schema_version line from frontmatter
sed -i '' '/schema_version/d' "$SNAP"
alph validate --pool /tmp/alph-test/registry/vehicles
```

Expected: `invalid: <filename>: missing required field: 'schema_version'`

```bash
# Restore by reinserting the line (or just re-add the node)
# Quick fix: re-seed the whole thing
rm -rf /tmp/alph-test && mkdir /tmp/alph-test
# (re-run the init and add steps above if you want a clean pool)
```

---

## 8. Demo Registry — Household Seed Data

```bash
cd /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example

# seed.py uses the alph library directly; run it with the poetry venv python
VENV_PYTHON=$(poetry -C /Users/cpettet/git/chasemp/AlpheusCEF/alph-cli env info --path)/bin/python

# Wipe and recreate
$VENV_PYTHON seed.py --wipe
```

Expected: `28 total`, 3 pools created, 9+9+10 nodes.

```bash
POOL=/Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry

# List all pools
alph list --pool $POOL/vehicles
alph list --pool $POOL/appliances
alph list --pool $POOL/remodeling
```

Expected: tables showing nodes. Remodeling has 10 (includes the 2025 capital plan node).

```bash
# Show the cross-pool reference node
alph show 9eb6b033c1de --pool $POOL/remodeling
```

Expected: node with `related: appliances::a76746c51d46, 3f9a51c99832`
This demonstrates the cross-pool `pool_name::node_id` format.

```bash
# Show a within-pool reference (CV axle -> 60k service)
alph show 5d4e71fbe603 --pool $POOL/vehicles
```

Expected: `related: 2079032c3079`

```bash
# Validate the whole demo
alph validate --pool $POOL/vehicles
alph validate --pool $POOL/appliances
alph validate --pool $POOL/remodeling
```

Expected: `all nodes valid.` for all three.

---

## 9. MCP Server — Smoke Test

```bash
# Start the server in one terminal (keep it running)
alph-mcp &
MCP_PID=$!
sleep 2
echo "MCP server PID: $MCP_PID"
```

Expected: server starts without error (FastMCP logs to stderr).

```bash
# Confirm process is running
ps aux | grep alph-mcp | grep -v grep
```

```bash
# Stop it
kill $MCP_PID
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

Verify GitHub Actions are green:

```bash
# CI run on the latest push to main
cd /Users/cpettet/git/chasemp/AlpheusCEF/alph-cli
gh run list --limit 5
gh run view --log  # most recent run
```

Expected: tests, mypy, ruff all passing.

---

## 11. Homebrew Formula

```bash
# Confirm formula is auditable (run from tap repo)
cd /Users/cpettet/git/chasemp/AlpheusCEF/homebrew-tap
brew audit --strict Formula/alph.rb
```

Expected: no errors. Warnings about non-`homebrew/core` tap are normal.

```bash
# Reinstall from tap to verify latest formula installs cleanly
brew reinstall alph
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
- [ ] `alph --help` shows: `add`, `list`, `show`, `validate`, `registry`, `pool`, `config`
- [ ] `alph registry init` sets default when no default exists; reports it clearly
- [ ] `alph registry list` shows registry ID, name, context, config path
- [ ] `alph pool init --registry <id>` finds registry by walking up from `--cwd`
- [ ] `alph pool init --registry ghost` errors and shows known registries
- [ ] `alph add` deduplicates correctly
- [ ] `alph list` default shows active only; `-s archived` expands
- [ ] `alph show` displays all fields including `related:`
- [ ] `alph validate` catches schema violations
- [ ] Config defaults (`default_registry`, `default_pool`, `creator`) resolve correctly
- [ ] `alph add` / `alph list` work without `--pool` / `--creator` when config set
- [ ] `alph config list` shows config discovery tree with exists/missing status
- [ ] `alph config show <path>` displays YAML with syntax highlighting
- [ ] `alph config show <missing-path>` shows bootstrap instructions + template
- [ ] Demo registry seeds 28 nodes cleanly
- [ ] Cross-pool `related:` field renders correctly on show
- [ ] `alph-mcp` starts without error
- [ ] MCP tools callable from Claude Code session
- [ ] CI green on GitHub Actions
