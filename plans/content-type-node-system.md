# Node `content_type` System

_Status: Design proposal — not yet implemented_

---

## Problem

Nodes currently have two structural fields that partially describe "what kind of thing is this":

- **`source`** — the originating adapter (`alph-cli/0.1.25`, `slack`, `alph-mcp/0.1.25`). Identifies **who/what created the node**, not the content format.
- **`node_type`** — `snapshot` vs `live`. Describes **mutability/storage**, not content format.

The missing leg: there's no formal, validated field for the **kind of content** (plain text, Google Doc, Slack thread, Jira ticket, etc.). Without it:

- `meta` is a free-form bag — no validator can enforce that a gdoc node has a `url`
- Processing code has to guess the content shape from `source` or convention
- Health checks can't assert structural completeness

---

## Proposal: Add `content_type` (optional, defaults to `text`)

### Field Definition

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `content_type` | No | `text` | Content format/kind — determines expected `meta` fields |

### Where it lives in the frontmatter

```yaml
---
schema_version: "1"
id: a3f9b2c11e04
timestamp: 2026-03-13T14:00:00Z
source: alph-cli/0.1.25        # adapter that created this — unchanged
node_type: snapshot             # mutability — unchanged
content_type: gdoc              # NEW: what kind of content this is
context: "Architecture review doc for the auth rewrite"
creator: user@example.com
meta:
  url: https://docs.google.com/document/d/abc123
  doc_id: abc123
  title: "Auth Rewrite Architecture Review"
  summary: "Covers the proposed OAuth2 flow and session management changes"
---
```

### Relationship to existing fields

```
source      = WHO made the node (adapter identity)
node_type   = HOW content is stored/fetched (snapshot vs live)
content_type = WHAT the content is (text, gdoc, slack, jira...)
```

These are orthogonal. A gdoc node can be snapshot (captured state) or live (real-time fetch). A slack thread can be either too.

---

## Type Catalog

### `text` (default)

Plain text, typically from direct CLI input. No meta fields required.

```yaml
content_type: text   # can be omitted — this is the default
```

- Required meta: _(none)_
- Applies to: `alph add -c "some thought"`, raw text paste

---

### `gdoc`

Google Doc reference. Previously discussed: context is the doc title + brief summary, link is in meta.

```yaml
content_type: gdoc
meta:
  url: https://docs.google.com/document/d/...
  doc_id: <google-doc-id>          # optional but useful
  title: "Doc Title"               # optional
  summary: "One-line description"  # optional
  provider: gdocs-mcp              # for live nodes: which tool resolves this
```

- Required meta: `url`
- Works as: `snapshot` (content captured) or `live` (fetched at query time via `provider`)

---

### `slack`

Slack message or thread.

```yaml
content_type: slack
meta:
  url: https://yourworkspace.slack.com/archives/C.../p...
  channel: "#eng-architecture"
  thread_ts: "1741872000.123456"
```

- Required meta: `url` OR (`channel` + `thread_ts`) — at least one anchor
- Works as: `snapshot` (captured state) or `live` (re-fetched via Slack API)

---

### `jira`

Jira issue.

```yaml
content_type: jira
meta:
  url: https://yourorg.atlassian.net/browse/ENG-1234
  issue_key: ENG-1234
  provider: jira-mcp
```

- Required meta: `url`, `issue_key`
- Typically `live` (tickets change)

---

### `confluence`

Confluence page.

```yaml
content_type: confluence
meta:
  url: https://yourorg.atlassian.net/wiki/spaces/ENG/pages/...
  page_id: "12345678"
  space_key: ENG
  provider: confluence-mcp
```

- Required meta: `url`
- Optional: `page_id`, `space_key`, `provider`

---

### `email`

Email thread or message.

```yaml
content_type: email
meta:
  from: alice@example.com
  subject: "Re: Auth rewrite timeline"
  message_id: "<abc123@mail.example.com>"
  url: https://mail.google.com/mail/u/0/#inbox/...
```

- Required meta: `from`, `subject`

---

### `image`

Photo, screenshot, diagram.

```yaml
content_type: image
meta:
  url: https://...
  caption: "ERD for the new auth tables"
```

- Required meta: `url`

---

### `figma`

Figma file, frame, or component.

```yaml
content_type: figma
meta:
  url: https://www.figma.com/file/...
  file_id: abc123
  frame_id: 456
```

- Required meta: `url`

---

## Validation Rules

When `content_type` is present and not `text`, the validator enforces required meta fields:

```
validate_node():
  if content_type == "gdoc":
    assert meta.url exists
  if content_type == "slack":
    assert meta.url exists OR (meta.channel AND meta.thread_ts)
  if content_type == "jira":
    assert meta.url exists AND meta.issue_key exists
  ...
```

If `content_type` is an unrecognized value (e.g., `cli`, `google_doc`), the validator rejects with a clear message:

```
Error: unknown content_type 'cli'.
  - 'cli' is a source identifier, not a content type. Use source: alph-cli/...
  - Did you mean 'text'?
  - Valid values: text, gdoc, slack, jira, confluence, email, image, figma
```

---

## ID Generation — Unchanged

`content_type` does **not** affect ID generation. The formula stays:

```
id = sha256(source + context)[:12]
```

Same context from same source = same node, regardless of content_type. This preserves idempotency.

---

## CLI Behavior

### Default (no `--content-type` flag)

`alph add -c "some thought"` produces a node with `content_type` omitted from frontmatter (implicitly `text`).

### Explicit type

```bash
alph add -c "Auth rewrite architecture review" \
  --content-type gdoc \
  --meta url=https://docs.google.com/... \
  --meta title="Auth Rewrite Architecture Review"
```

### Alias / flag shorthand

`--ct` as shorthand for `--content-type`.

### Error case

```bash
alph add -c "some text" --ct cli
# Error: unknown content_type 'cli'. Did you mean 'text'?
```

---

## Schema Changes

### `STATE.md`

1. Add `content_type` row to optional fields table
2. Add "Content Types" section (this catalog) after the schema section
3. Update validation subsection to describe type-specific meta enforcement

### `scripts/context-schema.json`

Already marked superseded. Add `content_type` property for completeness:

```json
"content_type": {
  "type": "string",
  "description": "Content format/kind (text, gdoc, slack, jira, confluence, email, image, figma). Defaults to text.",
  "default": "text"
}
```

### `alph-cli` (separate repo)

- `validate_node()` in `core.py`: add content_type-aware meta field checks
- `add_node()` in `core.py`: accept and write `content_type` field
- `cli.py`: add `--content-type` / `--ct` flag to `alph add`
- JSON Schema for validator: add `content_type` enum + conditional `meta` requirements via `if/then`

---

## Open Questions

1. **Should `content_type` be part of the ID hash?** Currently excluded to preserve idempotency. Could be included if we want `gdoc` and `text` nodes with same context to be different IDs — but that seems wrong.

2. **Extensibility**: Should the type catalog be open (any string allowed, validated only for known types) or closed (enum, unknown values always rejected)? Leaning **closed with clear error messages** to enforce hygiene, but could open it for power users with a `custom:` prefix.

3. **`content_type` in `alph list` output?** Probably yes as a column alongside `node_type` and `source`.

4. **Does `content_type` affect how LLMs process nodes?** Yes — the system prompt or MCP tool could hint to the LLM "this is a gdoc, use the gdocs-mcp tool to fetch it" even without an explicit `provider` field. `content_type` becomes a first-class routing signal.
