"""One-shot migration: stamp effective kind onto every spec item.

Removes file-level and group-level kind: fields; makes item-level kind: explicit
using the current inheritance resolution (item > group > file).

Usage:
    uv run python scripts/migrate_spec_kinds.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "specs"
sys.path.insert(0, str(ROOT))

from vultron.metadata.specs.registry import (
    effective_kind,
    load_registry,
)  # noqa: E402

# Matches file-level kind: (indent 0)
_FILE_KIND_RE = re.compile(r"^kind:\s+\S")
# Matches group-level kind: (indent 2, exactly)
_GROUP_KIND_RE = re.compile(r"^  kind:\s+\S")
# Matches spec item start: 2+ spaces, then "- id: XX-NN-NNN"
_ITEM_START_RE = re.compile(r"^( {2,})-\s+id:\s+([A-Z]{2,8}-\d{2}-\d{3})\s*$")
# Matches priority: at any indent
_PRIORITY_RE = re.compile(r"^ +priority:\s+\S")


def migrate_file(yaml_path: Path, effective_map: dict[str, str]) -> None:
    """Rewrite yaml_path: stamp item kinds, remove file/group-level kinds."""
    lines = yaml_path.read_text().splitlines(keepends=True)
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n")

        # Remove file-level kind: (indent 0)
        if _FILE_KIND_RE.match(stripped):
            i += 1
            continue

        # Remove group-level kind: (indent 2, exactly)
        if _GROUP_KIND_RE.match(stripped):
            i += 1
            continue

        # Detect spec item start: "  - id: XX-NN-NNN"
        m = _ITEM_START_RE.match(stripped)
        if m:
            item_indent = len(m.group(1))  # spaces before '-'
            prop_indent = item_indent + 2  # properties sit 2 deeper
            spec_id = m.group(2)
            out.append(line)
            i += 1

            # Build item_kind_re dynamically for this item's property depth
            item_kind_re = re.compile(
                r"^ {" + str(prop_indent) + r"}kind:\s+\S"
            )

            # Consume lines belonging to this item (until next sibling or dedent)
            item_body: list[str] = []
            while i < len(lines):
                nline = lines[i]
                ns = nline.rstrip("\n")
                n_indent = len(ns) - len(ns.lstrip()) if ns.strip() else 9999
                # Next item at same level or parent content stops this item
                if _ITEM_START_RE.match(ns):
                    break
                if ns.strip() and n_indent <= item_indent:
                    break
                # Drop existing item-level kind: (we'll re-add it)
                if item_kind_re.match(ns):
                    i += 1
                    continue
                item_body.append(nline)
                i += 1

            # Stamp kind: after priority: line
            kind_val = effective_map.get(spec_id)
            if kind_val is None:
                out.extend(item_body)
                continue

            kind_line = " " * prop_indent + f"kind: {kind_val}\n"
            inserted = False
            for body_line in item_body:
                out.append(body_line)
                if not inserted and _PRIORITY_RE.match(body_line.rstrip("\n")):
                    out.append(kind_line)
                    inserted = True
            if not inserted:
                # No priority line found — insert after "- id:" line
                out.append(kind_line)
            continue

        out.append(line)
        i += 1

    yaml_path.write_text("".join(out))


def main() -> None:
    print(f"Loading registry from {SPECS_DIR} ...")
    registry = load_registry(SPECS_DIR)

    # Compute all effective kinds BEFORE touching any file
    effective_map: dict[str, str] = {}
    for spec_file in registry.files:
        for group in spec_file.groups:
            for spec in group.specs:
                effective_map[spec.id] = effective_kind(
                    spec, group, spec_file
                ).value

    print(f"  {len(effective_map)} specs resolved")

    for yp in sorted(SPECS_DIR.glob("*.yaml")):
        migrate_file(yp, effective_map)
        print(f"  {yp.name}")

    print("Done. Run `uv run spec-lint` to verify.")


if __name__ == "__main__":
    main()
