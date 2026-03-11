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

Expected: help shows top-level commands: `add`, `list`, `show`, `validate`, `registry`, `pool`, `config`, `defaults`, and global options `--registry` (`-r`/`--reg`), `--branch`, and `--pool` (`-p`).
Both `--help` and `-h` should work.

Note: `--registry` and `--branch` are **global options** — they must appear
before the subcommand (e.g., `alph --branch seeded list`, not `alph list --branch seeded`).
`-r` and `-p` work on both global and per-command options.

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

Expected: a table with `test-household`, `Test Household`, mode `rw`, the context text,
and the pool home directory path. Local registries always show `rw`.

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

### 2g. Default subcommands

```bash
alph registry
```

Expected: same output as `alph registry list` — table with `test-household`.

```bash
alph pool
```

Expected: same output as `alph pool list` — table with `vehicles`.

### 2h. `reg` shorthand

```bash
alph reg list
```

Expected: same output as `alph registry list`.

```bash
alph reg
```

Expected: same as `alph registry` (defaults to list).

### 2i. Reserved names

```bash
alph registry init \
  --pool-home /tmp/alph-test/all-reg \
  --id all \
  --context "Should fail."
```

Expected: error — `'all' is a reserved name and cannot be used as a registry ID`.

```bash
alph pool init \
  --registry test-household \
  --name all \
  --context "Should fail."
```

Expected: error — `'all' is a reserved name and cannot be used as a pool name`.

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
Rows use alternating styles (normal / dim) for readability.

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

### Short flag aliases

```bash
alph pool list -r test-household
```

Expected: same output as `alph pool list --registry test-household`.

```bash
alph list -p /tmp/alph-test/registry/vehicles
```

Expected: same output as `alph list --pool /tmp/alph-test/registry/vehicles`.

---

## 5. CLI — Config Defaults (optional but recommended for daily use)

`alph registry init` already wrote `default_registry` and `alph pool init` already
wrote `default_pool`. The missing piece for daily use is `creator`. This step
adds `creator` to the config, preserving the existing registry and pool entries.

Open `~/.config/alph/config.yaml` and add `creator`, `default_pool`, and (if not
already present from `registry init`) `default_registry` at the top level:

```yaml
creator: test@example.com
default_registry: test-household
default_pool: vehicles
```

The `registries` block written by `alph registry init` and `alph pool init`
should already be present. The full file should now look like:

```yaml
creator: test@example.com
default_registry: test-household
default_pool: vehicles
registries:
  test-household:
    pool_home: /tmp/alph-test/registry
    context: Scratch registry for human test run.
    name: Test Household
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
alph config
```

Expected: same output as `alph config list` (defaults to list when no subcommand given).

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
alph show d133ae8da4be --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/remodeling
```

Expected: node with `related: appliances::b2d4bc365387, 9fd88fff72f8`
This demonstrates the cross-pool `pool_name::node_id` format.

```bash
alph show 396a97378477 --pool /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/vehicles
```

Expected: `related: b4344a31f5ef`

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

## 9. Remote Registry — RO Mode

This section tests reading from a remote GitHub repository without a local clone.
Requires a GitHub token (`GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth login`).

### 9a. Add a remote registry to config

Add the following entry under the `registries:` block in `~/.config/alph/config.yaml`:

```yaml
  remote-example:
    pool_home: git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry
    context: Remote demo registry (read-only).
    mode: ro
    branch: seeded
```

These fields can also be set at `alph registry init` time:

```bash
alph reg init \
  --id remote-example \
  --pool-home git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry \
  --context "Remote demo registry (read-only)." \
  --mode ro \
  --branch seeded
```

Note: `branch: seeded` points RO reads at the `seeded` branch, which contains
generated node data. The `main` branch has only `seed.py` and `seed.yaml`
(the `registry/` directory is gitignored there).

If your SSH config uses a host alias (e.g., `Host github-personal` with
`HostName github.com`), you can use that alias in the URL:
`git@github-personal:AlpheusCEF/multi-pool-repo-example.git:/registry`.
Alph resolves SSH aliases via `~/.ssh/config` to detect the forge correctly.

```bash
alph registry list
```

Expected: two registries — `test-household` (mode `rw`) and `remote-example` (mode `ro`).

### 9b. Check remote reachability

```bash
alph registry check remote-example
```

Expected: `ok: remote-example remote is reachable (git@github.com:AlpheusCEF/multi-pool-repo-example.git)`

```bash
alph registry check all
```

Expected: checks every configured registry. Shows `ok` or `error` for each one.
`test-household` (local) should show ok if the path exists; `remote-example` should show ok.

### 9c. List nodes from remote pool

Uses `--registry` to go through the config entry (which has `branch: seeded`):

```bash
alph --registry remote-example list --pool vehicles
```

Expected: table of nodes fetched via GitHub GraphQL API from the `seeded` branch. No local clone created.

### 9d. Show a node from remote pool

Copy a node ID from the list output above.

```bash
alph --registry remote-example show <paste-id-here> --pool vehicles
```

Expected: full node display with all fields.

### 9e. Validate remote pool

```bash
alph --registry remote-example validate --pool vehicles
```

Expected: `N nodes in pool ... valid.`

### 9f. Write to RO pool errors correctly

```bash
alph add -c "Should fail." \
  --pool git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry/vehicles \
  --creator test@example.com
```

Expected: `error: registry is read-only. Set mode: rw in config to enable writes.`

### 9g. Ad-hoc --registry flag with raw URL

Ad-hoc URLs bypass config (no `branch: seeded`), so reads hit the main branch
which has no node data. This verifies the ad-hoc path works without error:

```bash
alph --registry git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry list --pool vehicles
```

Expected: empty table (main branch has no node data — `registry/` is gitignored there).
This confirms the ad-hoc `--registry` URL path works; use a config entry with
`branch: seeded` for actual data (as in 9c).

### 9h. Ad-hoc --branch flag with raw URL

Combine `--branch` with `--registry` to hit a specific branch without config:

```bash
alph --branch seeded --registry git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry list --pool vehicles
```

Expected: table of nodes from the `seeded` branch — same data as 9c.
This verifies `--branch` works as a global option for ad-hoc remote operations.

Note: `--branch` and `--registry` are global options and must appear **before**
the subcommand. `alph list --branch seeded` will fail with `No such option`.

---

## 10. Remote Registry — RW Mode (Clone-Based)

### 10a. Clone a remote registry

Create via CLI or add manually to config:

```bash
alph reg init \
  --id remote-rw \
  --pool-home git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry \
  --context "Remote demo registry (read-write clone)." \
  --mode rw \
  --branch seeded \
  --clone-path /tmp/alph-test-clone
```

Note: `branch: seeded` is respected by both RO reads and RW clones. The clone
will check out the `seeded` branch (which has the generated `registry/` data).

```bash
alph registry clone remote-rw
```

Expected: `cloned: remote-rw -> /tmp/alph-test-clone (branch: seeded)`

```bash
alph registry clone remote-rw
```

Expected: `ok: remote-rw already cloned at /tmp/alph-test-clone`
(Second clone is a no-op with a distinct message.)

```bash
ls /tmp/alph-test-clone/registry/
```

Expected: pool directories (vehicles, appliances, remodeling) — present because
the `seeded` branch has committed `registry/` data.

### 10b. Registry status

```bash
alph registry status remote-rw
```

Expected:
```
registry:    remote-rw
mode:        rw
remote:      git@github.com:AlpheusCEF/multi-pool-repo-example.git
subpath:     registry
branch:      seeded
clone_path:  /tmp/alph-test-clone
clone_state: cloned (clean)
auto_pull:   true
auto_push:   true
```

```bash
alph registry status test-household
```

Expected:
```
registry:    test-household
mode:        rw
path:        /tmp/alph-test/registry
exists:      false
```

Note: `exists: false` because section 7 ran `rm -rf /tmp/alph-test`.
To see `exists: true`, run this before section 7's cleanup.

### 10c. Pull latest changes

```bash
alph registry pull remote-rw
```

Expected: `pulled: remote-rw (/tmp/alph-test-clone)`

### 10d. List with --pull flag

```bash
alph list --pool git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry/vehicles --pull
```

Expected: pulls latest changes, then lists nodes from the local clone.

### 10e. Write to RW remote pool

```bash
alph add -c "Test node from RW clone." \
  --pool git@github.com:AlpheusCEF/multi-pool-repo-example.git:/registry/vehicles \
  --creator test@example.com
```

Expected: `node created: <id>`. Node file written to `/tmp/alph-test-clone/registry/vehicles/snapshots/`.

### 10f. Clean up

```bash
rm -rf /tmp/alph-test-clone
```

Remove the `remote-example` and `remote-rw` entries from `~/.config/alph/config.yaml`.

---

## 11. MCP Server — Smoke Test

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

For a proper MCP test, register the server with Claude Code:

```bash
claude mcp add --scope user alph -- alph-mcp
```

Expected: confirms the MCP server was added. This writes to `~/.claude.json`.

Then open a Claude Code session and ask:
> "Using alph MCP tools, list all nodes in the pool at /Users/cpettet/git/chasemp/AlpheusCEF/multi-pool-repo-example/registry/remodeling"

Expected: Claude calls `list_pool_nodes` and returns the 10 remodeling nodes.

---

## 12. CI Check

```bash
cd /Users/cpettet/git/chasemp/AlpheusCEF/alph-cli
gh run list --limit 5
```

```bash
gh run view --log
```

Expected: tests, mypy, ruff all passing.

---

## 13. Homebrew Formula

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

## 14. Setup: HOMEBREW_TAP_TOKEN (for future releases)

For automatic formula updates on every release, add a PAT to the alph-cli repo:

1. Go to GitHub → Settings → Developer settings → Personal access tokens (classic)
2. Create token with `repo` scope (for pushing to homebrew-tap)
3. Go to `https://github.com/AlpheusCEF/alph-cli/settings/secrets/actions`
4. Add secret named `HOMEBREW_TAP_TOKEN` with the token value

After this, tagging a new release (`git tag v0.X.0 && git push origin v0.X.0`)
will automatically update the formula in homebrew-tap via the release workflow.

---

## Checklist

### Install and Help
- [ ] `brew install alph` works cleanly
- [ ] Both `alph` and `alph-mcp` binaries in PATH
- [ ] `alph --version` prints `alph 0.1.x`
- [ ] `alph --help` shows: `add`, `list`, `show`, `validate`, `registry`, `pool`, `config`, `defaults`, global options `--registry` (`-r`/`--reg`), `--branch`, `--pool` (`-p`)

### Registry and Pool Setup
- [ ] `alph registry init` sets default when no default exists; reports full expanded pool home and config path
- [ ] `alph registry list` shows registry ID, name, mode (rw/ro), context, pool home path
- [ ] `alph registry` (no subcommand) defaults to `registry list`
- [ ] `alph pool` (no subcommand) defaults to `pool list`
- [ ] `alph reg list` works as shorthand for `alph registry list`
- [ ] `alph reg` defaults to list (same as `alph registry`)
- [ ] `alph config` (no subcommand) defaults to `config list`
- [ ] `-r` and `--reg` work as aliases for `--registry` (global and per-command)
- [ ] `-p` works as alias for `--pool`
- [ ] `alph pool init --registry <id>` finds registry from global config by ID
- [ ] `alph pool init --registry ghost` errors and shows known registries
- [ ] `alph pool list` lists pools in the default registry with registry, name, type, context, path
- [ ] `alph pool list --registry <id>` lists pools in the specified registry
- [ ] `alph pool list -v` shows `source` column (configured vs discovered) for pools found on disk but not in config
- [ ] Reserved names: `alph registry init --id all` and `alph pool init --name all` both error
- [ ] `alph pool init` on duplicate pool name errors: "already exists"
- [ ] `alph pool init` on RO remote registry errors: "read-only"
- [ ] `alph pool init` on RW remote without clone errors: "run registry clone first"
- [ ] `alph pool init` on RW remote with clone creates pool at clone_path + subpath
- [ ] Config key order preserved after pool init (no reordering of registries)

### Node Operations
- [ ] `alph add` deduplicates correctly (same context -> "duplicate: node already exists")
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
- [ ] Tables use alternating row styles (normal / dim) for readability

### Config Defaults
- [ ] Config defaults (`default_registry`, `default_pool`, `creator`) resolve correctly
- [ ] `alph add` / `alph list` work without `--pool` / `--creator` when config set
- [ ] `alph config list` shows config discovery tree with exists/missing status
- [ ] `alph config show <path>` displays YAML with syntax highlighting
- [ ] `alph config show <missing-path>` shows "not found" + hints to `registry init` and `alph defaults` (no template dump)
- [ ] `alph defaults` shows resolved creator, registry, pool, auto_commit, and resolved pool path; unset values show as `not set`

### Demo Registry
- [ ] Demo registry seeds 28 nodes cleanly
- [ ] Cross-pool `related:` field renders correctly on show

### Remote Registry — RO Mode
- [ ] `alph registry list` shows `ro` for remote and `rw` for local registries
- [ ] `alph registry check <id>` verifies remote reachability
- [ ] `alph registry check all` checks every configured registry
- [ ] `branch: seeded` in config directs RO reads to the seeded branch
- [ ] `alph list --pool <remote-url>` fetches nodes via GitHub API (no local clone)
- [ ] `alph show <id> --pool <remote-url>` displays remote node content
- [ ] `alph validate --pool <remote-url>` validates remote pool
- [ ] `alph add` against RO remote pool errors: "registry is read-only"
- [ ] `alph --registry <remote-url> list --pool <name>` works (ad-hoc global option)
- [ ] `alph --branch seeded --registry <remote-url> list --pool <name>` works (ad-hoc branch override)
- [ ] SSH host aliases in URLs (e.g., `git@github-personal:...`) resolve correctly via `~/.ssh/config`

### Remote Registry — RW Mode
- [ ] `alph registry clone <id>` creates local clone and checks out configured branch
- [ ] Second `alph registry clone <id>` prints "already cloned" (not "cloned")
- [ ] `alph registry status <id>` shows mode, remote, clone state, auto_pull, auto_push for remote registries
- [ ] `alph registry status <id>` shows path and exists for local registries
- [ ] `auto_pull` and `auto_push` default to `true` for RW remote registries, `false` for local
- [ ] `alph registry pull <id>` pulls latest changes in clone
- [ ] `alph list --pool <remote-url> --pull` pulls before listing (RW clones)
- [ ] `alph add` against RW remote pool creates node in local clone
- [ ] `alph validate` on local registries with auto_pull/auto_push checks git health (remote, clean tree)

### MCP Server
- [ ] `alph-mcp` starts without error
- [ ] `claude mcp add --scope user alph -- alph-mcp` registers the server
- [ ] MCP tools callable from Claude Code session

### CI and Distribution
- [ ] CI green on GitHub Actions
