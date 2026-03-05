"""
AlpheusCEF - Remote Node Committer (GitHub API)

STATUS: PRE-DECISION PROTOTYPE (superseded by STATE.md)
Same schema gaps as add_node.py (uses `body`, missing `schema_version`/`creator`,
wrong ID hash). Additionally, remote commit via GitHub Contents API is deferred
to future input adapter work. See FUTURE.md "Remote node creation" open question.

Creates fixed or live context nodes directly in a remote GitHub repo
without needing a local clone. Uses the GitHub Contents API.
"""

import os
import argparse
import datetime
import hashlib
import base64
import json
import yaml
import requests
from pathlib import Path


def load_github_token():
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token

    for path in [Path("secrets.yaml"), Path.home() / ".config" / "alph" / "secrets.yaml"]:
        if path.exists():
            with open(path) as f:
                secrets = yaml.safe_load(f)
                return secrets.get("github_token")

    raise RuntimeError("No GitHub token found. Set GITHUB_TOKEN or add to secrets.yaml.")


def commit_node(owner, repo, source, node_type, body, content="", tags=None, related_to=None, meta=None, branch="main"):
    token = load_github_token()
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
    filename = f"{datetime.date.today()}-{node_id}.md"
    file_path = f"{folder}/{filename}"

    file_content = "---\n" + yaml.dump(frontmatter, sort_keys=False, default_flow_style=False) + "---\n\n" + content

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    get_res = requests.get(url, headers=headers)
    sha = get_res.json().get("sha") if get_res.status_code == 200 else None

    data = {
        "message": f"alph: add {node_type} node {node_id}",
        "content": base64.b64encode(file_content.encode("utf-8")).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        data["sha"] = sha

    response = requests.put(url, headers=headers, json=data)

    if response.status_code in [200, 201]:
        return {"file_path": file_path, "node_id": node_id, "status": "committed"}
    else:
        return {"error": response.json(), "status": "failed"}


def main():
    parser = argparse.ArgumentParser(description="Commit an AlpheusCEF node to a remote GitHub repo")
    parser.add_argument("--owner", required=True, help="GitHub repo owner")
    parser.add_argument("--repo", required=True, help="GitHub repo name")
    parser.add_argument("--source", required=True, help="Originating system")
    parser.add_argument("--type", required=True, choices=["fixed", "live"], dest="node_type")
    parser.add_argument("--body", required=True, help="Summary / description")
    parser.add_argument("--content", default="", help="Full content body")
    parser.add_argument("--tags", nargs="*")
    parser.add_argument("--related-to", nargs="*")
    parser.add_argument("--meta", type=json.loads, default=None, help="JSON metadata")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--json", action="store_true", dest="output_json")

    args = parser.parse_args()

    result = commit_node(
        owner=args.owner,
        repo=args.repo,
        source=args.source,
        node_type=args.node_type,
        body=args.body,
        content=args.content,
        tags=args.tags,
        related_to=args.related_to,
        meta=args.meta,
        branch=args.branch,
    )

    if args.output_json:
        print(json.dumps(result))
    elif result["status"] == "committed":
        print(f"Node committed: {result['file_path']} (id: {result['node_id']})")
    else:
        print(f"Error: {result['error']}")


if __name__ == "__main__":
    main()
