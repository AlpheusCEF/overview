"""
AlpheusCEF - Local Node Creator

STATUS: PRE-DECISION PROTOTYPE (superseded by STATE.md)
This script was created during the Gemini design session before final schema
decisions were made. Key differences from current spec:
  - Uses `body` instead of `context`
  - Missing `schema_version` and `creator` fields
  - ID hash uses (timestamp + body) instead of (timestamp + source + context)
  - No idempotency check
Will be replaced by core.py + cli.py in implementation.

Creates fixed or live context nodes as Markdown files with YAML frontmatter
in a local Git repository.
"""

import argparse
import hashlib
import datetime
import json
import yaml
from pathlib import Path


def create_node(repo_path, source, node_type, body, content="", tags=None, related_to=None, meta=None):
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    node_id = hashlib.sha256(f"{ts}{body}".encode()).hexdigest()[:12]

    frontmatter = {
        "id": node_id,
        "timestamp": ts,
        "source": source,
        "node_type": node_type,
        "body": body,
    }

    if tags:
        frontmatter["tags"] = tags
    if related_to:
        frontmatter["related_to"] = related_to
    if meta:
        frontmatter["meta"] = meta

    folder = "snapshots" if node_type == "fixed" else "pointers"
    file_path = Path(repo_path) / folder / f"{datetime.date.today()}-{node_id}.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, sort_keys=False, default_flow_style=False)
        f.write("---\n\n")
        f.write(content)

    return str(file_path), node_id


def main():
    parser = argparse.ArgumentParser(description="Create an AlpheusCEF context node")
    parser.add_argument("--repo", required=True, help="Path to the context repo")
    parser.add_argument("--source", required=True, help="Originating system (cli, slack, google_docs, etc)")
    parser.add_argument("--type", required=True, choices=["fixed", "live"], dest="node_type", help="Node type")
    parser.add_argument("--body", required=True, help="Summary / description of the node")
    parser.add_argument("--content", default="", help="Full content body (for fixed nodes)")
    parser.add_argument("--tags", nargs="*", help="Semantic tags (decision, concern, requirement)")
    parser.add_argument("--related-to", nargs="*", help="Related node IDs or file paths")
    parser.add_argument("--meta", type=json.loads, default=None, help="JSON string of source-specific metadata")
    parser.add_argument("--json", action="store_true", dest="output_json", help="Output result as JSON")

    args = parser.parse_args()

    file_path, node_id = create_node(
        repo_path=args.repo,
        source=args.source,
        node_type=args.node_type,
        body=args.body,
        content=args.content,
        tags=args.tags,
        related_to=args.related_to,
        meta=args.meta,
    )

    if args.output_json:
        print(json.dumps({"file_path": file_path, "node_id": node_id}))
    else:
        print(f"Node created: {file_path} (id: {node_id})")


if __name__ == "__main__":
    main()
