"""Relabel spec items' ``kind:`` and drop their ``missing_story_reference`` suppression.

Applies the MS-12 decision tree's outcome to the spec YAML (issue #3600). The
input is a JSON object ``{spec_id: new_kind}``; a ``null`` kind means "keep
the kind, only strip the suppression" (the inert-suppression cleanup of AC-6).
For every listed item this script:

- rewrites the item's ``kind:`` line when a new kind is given;
- removes ``missing_story_reference`` from the item's ``lint_suppress:`` list,
  in block or flow style;
- drops the ``lint_suppress:`` block entirely when that leaves it empty.

Text-manipulation approach: items are sliced, and the suppression removed,
by the shared helpers in ``vultron.metadata.specs.yaml_items``. No YAML load/dump
round-trip, so every other line of every file is preserved byte for byte.

Usage:
    uv run python scripts/relabel_spec_kinds.py mapping.json [--dry-run] [--specs-dir DIR]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from vultron.metadata.specs.yaml_items import (
    SpecItem,
    iter_blocks,
    remove_lint_suppression,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPECS_DIR = _REPO_ROOT / "specs"

_SUPPRESSION = "missing_story_reference"

# A trailing ``# comment`` on a scalar line is kept and re-emitted verbatim.
_KIND_RE = re.compile(r"^(\s+)kind:\s*(\S+)(\s+#.*)?\s*$")


class _RunTally:
    """Per-run tallies and the mapping entries the corpus never presented."""

    def __init__(self, mapping: dict[str, str | None]) -> None:
        self.pending = dict(mapping)
        self.relabeled = 0
        self.stripped = 0
        self.unchanged_kind: list[str] = []
        self.no_suppression: list[str] = []
        self.kind_not_found: list[str] = []


def _rewrite_item(
    item: SpecItem, new_kind: str | None, tally: _RunTally
) -> list[str]:
    """Return the item's lines with the kind relabeled and the suppression removed."""
    lines, stripped = remove_lint_suppression(item, _SUPPRESSION)
    out: list[str] = []
    kind_seen = False
    for line in lines:
        km = _KIND_RE.match(line)
        if km and km.group(1) == item.field_indent and new_kind is not None:
            kind_seen = True
            if km.group(2) == new_kind:
                tally.unchanged_kind.append(item.spec_id)
            else:
                tally.relabeled += 1
            out.append(
                f"{item.field_indent}kind: {new_kind}{km.group(3) or ''}\n"
            )
            continue
        out.append(line)

    if stripped:
        tally.stripped += 1
    else:
        tally.no_suppression.append(item.spec_id)
    if new_kind is not None and not kind_seen:
        tally.kind_not_found.append(item.spec_id)
    return out


def relabel_file(yaml_path: Path, tally: _RunTally, dry_run: bool) -> bool:
    """Rewrite one spec file. Returns True when the file changed."""
    lines = yaml_path.read_text(encoding="utf-8").splitlines(keepends=True)
    result: list[str] = []
    for block in iter_blocks(lines):
        if isinstance(block, str):
            result.append(block)
            continue
        if block.spec_id not in tally.pending:
            result.extend(block.lines)
            continue
        new_kind = tally.pending.pop(block.spec_id)
        result.extend(_rewrite_item(block, new_kind, tally))

    new_text = "".join(result)
    changed = new_text != "".join(lines)
    if changed and not dry_run:
        yaml_path.write_text(new_text, encoding="utf-8")
    return changed


def main(argv: list[str]) -> int:
    specs_dir = _SPECS_DIR
    if "--specs-dir" in argv:
        at = argv.index("--specs-dir")
        if at + 1 >= len(argv):
            print("--specs-dir requires a directory", file=sys.stderr)
            print(__doc__, file=sys.stderr)
            return 2
        specs_dir = Path(argv[at + 1])
        argv = argv[:at] + argv[at + 2 :]
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    dry_run = "--dry-run" in argv
    mapping = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    tally = _RunTally(mapping)

    for yaml_path in sorted(specs_dir.glob("*.yaml")):
        if relabel_file(yaml_path, tally, dry_run):
            shown = (
                yaml_path.relative_to(_REPO_ROOT)
                if yaml_path.is_relative_to(_REPO_ROOT)
                else yaml_path
            )
            print(f"{'(dry-run) ' if dry_run else ''}{shown}")

    print(
        f"\n{tally.relabeled} kind(s) relabeled; {tally.stripped} "
        f"{_SUPPRESSION} suppression(s) removed"
    )
    if tally.unchanged_kind:
        print(
            f"already carried the requested kind: {sorted(tally.unchanged_kind)}"
        )
    if tally.no_suppression:
        print(
            f"no {_SUPPRESSION} suppression to remove "
            f"({len(tally.no_suppression)}): {sorted(tally.no_suppression)}"
        )
    failed = False
    if tally.kind_not_found:
        print(
            f"kind: line not found (relabel not applied): "
            f"{sorted(tally.kind_not_found)}",
            file=sys.stderr,
        )
        failed = True
    if tally.pending:
        print(f"NOT FOUND in specs/: {sorted(tally.pending)}", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
