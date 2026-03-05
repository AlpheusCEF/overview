"""
AlpheusCEF - Schema Validator

STATUS: PRE-DECISION PROTOTYPE (superseded by STATE.md)
Uses `body` instead of `context`, missing `schema_version`/`creator`/`tags`
in required fields. New validator must also check registry structure.
Will be replaced by validator in core.py.

Validates all context nodes in snapshots/ and pointers/ against the
core JSON Schema. Run locally or as a GitHub Action.
"""

import argparse
import json
import sys
import yaml
import jsonschema
from pathlib import Path

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "id": {"type": "string", "pattern": "^[a-f0-9]{12}$"},
        "timestamp": {"type": "string", "format": "date-time"},
        "source": {"type": "string"},
        "node_type": {"enum": ["fixed", "live"]},
        "body": {"type": "string", "minLength": 10},
        "related_to": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "meta": {"type": "object"},
    },
    "required": ["id", "timestamp", "source", "node_type", "body"],
}

TARGET_DIRS = ["snapshots", "pointers"]


def extract_frontmatter(text):
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1])


def validate(repo_path, output_json=False):
    root = Path(repo_path)
    results = []
    errors = 0

    for folder in TARGET_DIRS:
        target = root / folder
        if not target.exists():
            continue
        for path in sorted(target.glob("*.md")):
            content = path.read_text()
            data = extract_frontmatter(content)

            if data is None:
                results.append({"file": str(path), "valid": False, "error": "Missing or malformed frontmatter"})
                errors += 1
                continue

            try:
                jsonschema.validate(instance=data, schema=SCHEMA)
                results.append({"file": str(path), "valid": True})
            except jsonschema.ValidationError as e:
                results.append({"file": str(path), "valid": False, "error": e.message})
                errors += 1

    if output_json:
        print(json.dumps({"results": results, "errors": errors, "total": len(results)}))
    else:
        for r in results:
            status = "OK" if r["valid"] else "FAIL"
            msg = f"  ({r['error']})" if not r["valid"] else ""
            print(f"{status} {r['file']}{msg}")
        print(f"\n{len(results)} files checked, {errors} errors")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate AlpheusCEF context nodes")
    parser.add_argument("--repo", default=".", help="Path to context repo")
    parser.add_argument("--json", action="store_true", dest="output_json")
    args = parser.parse_args()

    errors = validate(args.repo, args.output_json)
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
