"""Apply story mappings produced by the SR-11 map-spec-stories workflow.

Reads a JSON mappings file (list of {file, spec_mappings: [{spec_id, story_ids, no_match}]})
and for each non-no_match spec:
  - Adds a ``stories:`` block with the mapped story IDs
  - Removes the ``- missing_story_reference`` line from ``lint_suppress:``
  - If ``lint_suppress:`` only had that one item, removes the whole block

Text-manipulation approach: items are sliced, and their suppressions and
stories edited, by the shared ``vultron.metadata.specs.yaml_items`` helpers.
No YAML load/dump round-trip — preserves all formatting.

Usage:
    uv run python scripts/apply_story_mappings.py mappings.json [--dry-run]
"""

import json
import re
import sys
from pathlib import Path

from vultron.metadata.specs.yaml_items import (
    SpecItem,
    append_list_field,
    iter_blocks,
    remove_lint_suppression,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent

_SUPPRESSION = "missing_story_reference"


def _build_story_map(spec_mappings: list[dict]) -> dict[str, list[str]]:
    """Return spec_id -> story_ids for mappings that have a story match."""
    story_map: dict[str, list[str]] = {}
    for m in spec_mappings:
        if not m.get("no_match") and m.get("story_ids"):
            story_map[m["spec_id"]] = m["story_ids"]
    return story_map


def _rewrite_item(
    item: SpecItem, story_ids: list[str]
) -> tuple[list[str], bool]:
    """Swap one item's missing_story_reference suppression for a stories list.

    The edit goes through the shared ``yaml_items`` helpers, which keep each
    justification comment with its entry and raise ``ValueError`` on a block
    they cannot parse rather than corrupt it. An item without the
    suppression is returned unchanged.

    Returns (new_item_lines, modified).
    """
    lines, removed = remove_lint_suppression(item, _SUPPRESSION)
    if not removed:
        return list(item.lines), False
    return (
        append_list_field(
            SpecItem(item.spec_id, item.indent, lines), "stories", story_ids
        ),
        True,
    )


def apply_file_mappings(
    yaml_path: Path,
    spec_mappings: list[dict],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Apply story mappings to a single spec YAML file.

    Returns (applied_count, skipped_count).
    """
    story_map = _build_story_map(spec_mappings)
    if not story_map:
        return 0, len(spec_mappings)

    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    result: list[str] = []
    applied = 0
    skipped = 0

    for block in iter_blocks(lines):
        if isinstance(block, str):
            result.append(block)
            continue

        item_lines = block.lines

        # Check if this spec needs story mapping
        story_ids = story_map.get(block.spec_id)
        if story_ids is None:
            result.extend(item_lines)
            continue

        # Check it doesn't already have stories: (shouldn't, but guard)
        if any(re.match(r"^\s+stories:", line) for line in item_lines):
            result.extend(item_lines)
            skipped += 1
            continue

        new_item, modified = _rewrite_item(block, story_ids)
        if modified:
            result.extend(new_item)
            applied += 1
        else:
            result.extend(item_lines)
            skipped += 1

    if applied > 0 and not dry_run:
        yaml_path.write_text("".join(result), encoding="utf-8")

    return applied, skipped


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/apply_story_mappings.py <mappings.json> [--dry-run]"
        )
        sys.exit(1)

    mappings_path = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv

    data = json.loads(mappings_path.read_text())
    # Support both {"mappings": [...]} wrapper and bare list
    if isinstance(data, dict) and "mappings" in data:
        file_mappings = data["mappings"]
    else:
        file_mappings = data

    total_applied = 0
    total_skipped = 0
    no_match_ids: list[str] = []

    for fm in file_mappings:
        file_path = _REPO_ROOT / fm["file"]
        spec_mappings = fm.get("spec_mappings", [])

        # Collect no_match IDs for reporting
        for m in spec_mappings:
            if m.get("no_match") or not m.get("story_ids"):
                no_match_ids.append(m["spec_id"])

        if not file_path.exists():
            print(f"  [SKIP] {fm['file']}: file not found", file=sys.stderr)
            continue

        applied, skipped = apply_file_mappings(
            file_path, spec_mappings, dry_run=dry_run
        )
        total_applied += applied
        total_skipped += skipped
        if applied > 0 or skipped > 0:
            mode = "(dry-run) " if dry_run else ""
            print(
                f"  {mode}{fm['file']}: {applied} mapped, {skipped} skipped/no-match"
            )

    print(f"\nTotal: {total_applied} specs mapped to stories")
    print(
        f"Total: {len(no_match_ids)} specs with no story match (suppression retained)"
    )
    if no_match_ids:
        print("\nSpecs with no plausible story match (gap list):")
        for sid in sorted(no_match_ids):
            print(f"  - {sid}")


if __name__ == "__main__":
    main()
