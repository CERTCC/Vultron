#!/usr/bin/env bash
# spec-amendments.sh — list spec requirements whose `statement:` or `priority:`
# the branch changed or removed, relative to a base ref.
#
# Usage: spec-amendments.sh [<base-ref>] [<head-ref>]   (defaults: origin/main, HEAD)
#
# Compares the parsed YAML of every changed specs/*.yaml, so a reflowed or
# mid-sentence edit of a folded `statement: >-` is caught (a line grep on
# `statement:` is not). Newly added requirements are not amendments: nothing
# built on the old text can be wrong.
#
# Output: one line per amended requirement, `<ID>\t<changed|removed>\t<fields>`.
# Exit:   0  no requirement amended
#         1  at least one amended (the PR body needs a `## Spec amended` section)
#         2  usage or load error
set -euo pipefail

project="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
base="${1:-origin/main}"
head="${2:-HEAD}"

files="$(git diff --name-only --diff-filter=MD "${base}...${head}" -- 'specs/*.yaml')" || exit 2
[ -z "${files}" ] && exit 0

FILES="${files}" BASE="${base}" HEAD_REF="${head}" PYTHONPATH= uv run --project "${project}" python - <<'PY'
import os
import subprocess
import sys

import yaml

base, head = os.environ["BASE"], os.environ["HEAD_REF"]


def load(ref: str, path: str) -> dict[str, dict[str, str]]:
    shown = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True
    )
    if shown.returncode != 0:
        return {}
    doc = yaml.safe_load(shown.stdout) or {}
    found: dict[str, dict[str, str]] = {}
    for group in doc.get("groups", []):
        for spec in group.get("specs", []):
            found[spec["id"]] = {
                "statement": " ".join(str(spec.get("statement", "")).split()),
                "priority": str(spec.get("priority", "")),
            }
    return found


amended = []
for path in os.environ["FILES"].split():
    old, new = load(base, path), load(head, path)
    for spec_id, before in old.items():
        after = new.get(spec_id)
        if after is None:
            amended.append((spec_id, "removed", "statement,priority"))
            continue
        fields = [k for k in ("statement", "priority") if before[k] != after[k]]
        if fields:
            amended.append((spec_id, "changed", ",".join(fields)))

for row in sorted(amended):
    print("\t".join(row))
sys.exit(1 if amended else 0)
PY
