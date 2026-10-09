"""Sync every spec item's ``verification_debt:`` marker with its ``verification:``.

The migration for MS-10-006's per-requirement rule (issue #4199), safe to
re-run at any time. For every item in ``specs/*.yaml`` this script:

- adds ``verification_debt: '#N'`` after the ``kind:`` line of a MUST-tier item
  that has no ``verification:`` and no marker, naming its kind's owner;
- deletes the marker from an item that now has a ``verification:`` field, or
  sits below the MUST tier (a sibling PR verified it after the last run);
- removes the retired ``must_without_verification`` suppression.

A marker naming the wrong kind's owner (a relabel that kept its old marker,
MS-10-008) is reported, not rewritten: the fix is a ``verification:`` clause.

Owners follow the backfill Tasks: one per kind, and for ``kind: project`` one
per file group (#2573 demo files, #2574 BT and spec tooling, #2575 the rest).

Text-manipulation approach: items are sliced by the shared helpers in
``vultron.metadata.specs.yaml_items``. No YAML dump, so every other line of
every file is preserved byte for byte; the file is parsed only to read each
item's fields.

Usage:
    uv run python scripts/mark_verification_debt.py [--dry-run] [--specs-dir DIR]
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vultron.metadata.file_loading import load_yaml
from vultron.metadata.specs.schema import RFC2119Priority, SpecKind
from vultron.metadata.specs.verification import (
    VERIFICATION_DEBT_OWNERS,
    owes_verification,
    owns_kind,
)
from vultron.metadata.specs.yaml_items import (
    SpecItem,
    iter_blocks,
    remove_lint_suppression,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPECS_DIR = _REPO_ROOT / "specs"

_RETIRED_SUPPRESSION = "must_without_verification"

#: ``kind: project`` owners by spec file stem; any other file goes to #2575.
_PROJECT_FILE_OWNERS: dict[str, str] = {
    **dict.fromkeys(
        ("multi-actor-demo", "demo-ci", "demo-report", "demo-cli"), "#2573"
    ),
    **dict.fromkeys(
        (
            "spec-registry",
            "behavior-tree-integration",
            "testability",
            "behavior-tree-node-design",
            "sync-behavior-trees",
            "docs-build-workflow",
            "bt-composability",
            "notes-frontmatter",
        ),
        "#2574",
    ),
}
_PROJECT_DEFAULT_OWNER = "#2575"

_KIND_RE = re.compile(r"^(\s+)kind:\s*\S+")
_DEBT_RE = re.compile(r"^(\s+)verification_debt:")


def owner_for(kind: SpecKind, file_stem: str) -> str:
    """The issue a new marker on an item of *kind* in *file_stem* names."""
    if kind is SpecKind.PROJECT:
        return _PROJECT_FILE_OWNERS.get(file_stem, _PROJECT_DEFAULT_OWNER)
    (owner,) = VERIFICATION_DEBT_OWNERS[kind]
    return owner


@dataclass
class Tally:
    """What one run changed, and what it refused to change."""

    added: dict[str, int] = field(default_factory=dict)
    removed_stale: list[str] = field(default_factory=list)
    suppressions_removed: int = 0
    wrong_owner: list[str] = field(default_factory=list)
    kind_not_found: list[str] = field(default_factory=list)


# Raw parsed YAML is untyped by nature; ``Any`` here is the YAML boundary. The
# items are not validated as ``StatementSpec`` because a retired suppression
# code — one of the things this script removes — fails that validation.
def _items_by_id(yaml_path: Path) -> dict[str, dict[str, Any]]:
    """Every spec item's raw fields, keyed by ID."""
    data = load_yaml(yaml_path, root=_REPO_ROOT)
    if not isinstance(data, dict):
        return {}
    return {
        spec["id"]: spec
        for group in data.get("groups", [])
        for spec in group.get("specs", [])
    }


def _sync_item(
    item: SpecItem, fields: dict[str, Any], file_stem: str, tally: Tally
) -> list[str]:
    """Return *item*'s lines with its marker and suppression brought in line."""
    lines, stripped = remove_lint_suppression(item, _RETIRED_SUPPRESSION)
    if stripped:
        tally.suppressions_removed += 1

    owes = owes_verification(
        RFC2119Priority(fields["priority"]), fields.get("verification")
    )
    marker = fields.get("verification_debt")
    kind = SpecKind(fields["kind"])

    if marker and not owes:
        tally.removed_stale.append(item.spec_id)
        return [
            ln
            for ln in lines
            if not (
                (m := _DEBT_RE.match(ln)) and m.group(1) == item.field_indent
            )
        ]
    if marker:
        if not owns_kind(VERIFICATION_DEBT_OWNERS, kind, marker):
            tally.wrong_owner.append(item.spec_id)
        return lines
    if not owes:
        return lines

    owner = owner_for(kind, file_stem)
    for at, ln in enumerate(lines):
        m = _KIND_RE.match(ln)
        if m and m.group(1) == item.field_indent:
            tally.added[owner] = tally.added.get(owner, 0) + 1
            return [
                *lines[: at + 1],
                f"{item.field_indent}verification_debt: '{owner}'\n",
                *lines[at + 1 :],
            ]
    tally.kind_not_found.append(item.spec_id)
    return lines


def sync_file(yaml_path: Path, tally: Tally, dry_run: bool) -> bool:
    """Rewrite one spec file. Returns True when the file changed."""
    text = yaml_path.read_text(encoding="utf-8")
    fields_by_id = _items_by_id(yaml_path)
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    for block in iter_blocks(lines):
        if isinstance(block, str):
            result.append(block)
        elif block.spec_id in fields_by_id:
            result.extend(
                _sync_item(
                    block, fields_by_id[block.spec_id], yaml_path.stem, tally
                )
            )
        else:
            result.extend(block.lines)
    new_text = "".join(result)
    changed = new_text != text
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
    unknown = [a for a in argv if a != "--dry-run"]
    if unknown:
        print(__doc__, file=sys.stderr)
        return 2
    dry_run = "--dry-run" in argv

    tally = Tally()
    for yaml_path in sorted(specs_dir.glob("*.yaml")):
        if sync_file(yaml_path, tally, dry_run):
            print(f"{'(dry-run) ' if dry_run else ''}{yaml_path.name}")

    added = ", ".join(f"{o}: {n}" for o, n in sorted(tally.added.items()))
    print(
        f"\n{sum(tally.added.values())} marker(s) added ({added or 'none'}); "
        f"{len(tally.removed_stale)} stale marker(s) removed; "
        f"{tally.suppressions_removed} {_RETIRED_SUPPRESSION} "
        f"suppression(s) removed"
    )
    if tally.removed_stale:
        print(f"stale markers removed: {sorted(tally.removed_stale)}")
    failed = False
    if tally.wrong_owner:
        print(
            "marker names another kind's owner (MS-10-008 — add a "
            f"verification: clause): {sorted(tally.wrong_owner)}",
            file=sys.stderr,
        )
        failed = True
    if tally.kind_not_found:
        print(
            f"kind: line not found (marker not added): "
            f"{sorted(tally.kind_not_found)}",
            file=sys.stderr,
        )
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
