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
alph --version
alph --help
```

Expected: `alph --help` shows top-level commands: `add`, `list`, `show`, `validate`, `registry`, `pool`.

---

## 2. CLI — Registry and Pool Init

```bash
# Create a scratch workspace
mkdir -p /tmp/alph-test
cd /tmp/alph-test

# Init a registry
alph registry init \
  --path /tmp/alph-test/registry \
  --id test-household \
  --context "Scratch registry for human test run." \
  --name "Test Household"
```

Expected: `registry created: /tmp/alph-test/registry/config.yaml`

```bash
# Inspect the config
cat /tmp/alph-test/registry/config.yaml
```

Expected: YAML with `id: test-household`, `context`, `name`.

```bash
# Init a pool
alph pool init \
  --registry /tmp/alph-test/registry \
  --name vehicles \
  --context "Vehicle maintenance and purchase records."
```

Expected:
```
pool created: /tmp/alph-test/registry/vehicles
  snapshots/  /tmp/alph-test/registry/vehicles/snapshots
  pointers/   /tmp/alph-test/registry/vehicles/pointers
  .alph/      /tmp/alph-test/registry/vehicles/.alph
```

---

## 3. CLI — Add Nodes

```bash
# Add a fixed node
alph add \
  --pool /tmp/alph-test/registry/vehicles \
  --context "Purchased 2022 Subaru Outback Wilderness, $38,200. VIN: 4S4BTGND7N3123456." \
  --creator test@example.com
```

Expected: `node created: <12-char-id>` + `path: .../snapshots/<id>.md`

```bash
# Add it again — should deduplicate
alph add \
  --pool /tmp/alph-test/registry/vehicles \
  --context "Purchased 2022 Subaru Outback Wilderness, $38,200. VIN: 4S4BTGND7N3123456." \
  --creator test@example.com
```

Expected: `duplicate: node already exists (created by test@example.com)`

```bash
# Add a live node
alph add \
  --pool /tmp/alph-test/registry/vehicles \
  --context "Outback due for 10k service — oil change, tire rotation, multi-point inspection." \
  --creator test@example.com \
  --type live
```

Expected: `node created: <different-id>` + path ends in `pointers/`

```bash
# Add a node with tags and status
alph add \
  --pool /tmp/alph-test/registry/vehicles \
  --context "Replaced wiper blades, passenger side was streaking badly. $22 at AutoZone." \
  --creator test@example.com \
  --status archived
```

Expected: `node created: <id>`

---

## 4. CLI — List and Show

```bash
# Default: active only
alph list --pool /tmp/alph-test/registry/vehicles
```

Expected: table with 3 rows (the fixed node, live node, and the active archived-status one).
Wait — the archived node should NOT appear by default.

Expected: 2 rows (fixed + live, both active by default).

```bash
# Include archived
alph list --pool /tmp/alph-test/registry/vehicles -s archived
```

Expected: 3 rows (adds the archived wiper blade node).

```bash
# Show a specific node (copy an ID from the list output)
POOL=/tmp/alph-test/registry/vehicles
NODE_ID=<paste-id-from-list>
alph show $NODE_ID --pool $POOL
```

Expected: full node display with `id`, `context`, `type`, `source`, `creator`, `timestamp`.

---

## 5. CLI — Validate

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

Expected: `invalid: <filename>: 'schema_version' is a required property`

```bash
# Restore by reinserting the line (or just re-add the node)
# Quick fix: re-seed the whole thing
rm -rf /tmp/alph-test && mkdir /tmp/alph-test
# (re-run the init and add steps above if you want a clean pool)
```

---

## 6. Demo Registry — Household Seed Data

```bash
cd /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example

# Wipe and recreate
/Users/cpettet/Library/Caches/pypoetry/virtualenvs/alph-cli--e5mY6pC-py3.12/bin/python \
  seed.py --wipe
```

Expected: `28 total`, 3 pools created, 9+9+10 nodes.

```bash
VENV=/Users/cpettet/Library/Caches/pypoetry/virtualenvs/alph-cli--e5mY6pC-py3.12/bin
POOL=/Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry

# List all pools
$VENV/alph list --pool $POOL/vehicles
$VENV/alph list --pool $POOL/appliances
$VENV/alph list --pool $POOL/remodeling
```

Expected: tables showing nodes. Remodeling has 10 (includes the 2025 capital plan node).

```bash
# Show the cross-pool reference node
$VENV/alph show 9eb6b033c1de --pool $POOL/remodeling
```

Expected: node with `related: appliances::a76746c51d46, 3f9a51c99832`
This demonstrates the cross-pool `pool_name::node_id` format.

```bash
# Show a within-pool reference (CV axle -> 60k service)
$VENV/alph show 5d4e71fbe603 --pool $POOL/vehicles
```

Expected: `related: 2079032c3079`

```bash
# Validate the whole demo
$VENV/alph validate --pool $POOL/vehicles
$VENV/alph validate --pool $POOL/appliances
$VENV/alph validate --pool $POOL/remodeling
```

Expected: `all nodes valid.` for all three.

---

## 7. MCP Server — Smoke Test

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

## 8. CI Check

Verify GitHub Actions are green:

```bash
# CI run on the latest push to main
cd /Users/cpettet/git/chasemp/AlpheusCEF/alph-cli
gh run list --limit 5
gh run view --log  # most recent run
```

Expected: tests, mypy, ruff all passing.

---

## 9. Homebrew Formula (one-time, after brew install)

```bash
# Confirm formula is auditable (run from tap repo)
cd /Users/cpettet/git/chasemp/AlpheusCEF/homebrew-tap
brew audit --strict Formula/alph.rb
```

Expected: no errors. Warnings about non-`homebrew/core` tap are normal.

```bash
# Reinstall from source to verify formula installs cleanly
brew reinstall alph
alph --help
alph-mcp --help
```

---

## 10. Setup: HOMEBREW_TAP_TOKEN (for future releases)

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
- [ ] `alph registry init` / `alph pool init` work
- [ ] `alph add` deduplicates correctly
- [ ] `alph list` default shows active only; `-s archived` expands
- [ ] `alph show` displays all fields including `related:`
- [ ] `alph validate` catches schema violations
- [ ] Demo registry seeds 28 nodes cleanly
- [ ] Cross-pool `related:` field renders correctly on show
- [ ] `alph-mcp` starts without error
- [ ] MCP tools callable from Claude Code session
- [ ] CI green on GitHub Actions
