"""Apply story mappings produced by the SR-11 map-spec-stories workflow.

Reads a JSON mappings file (list of {file, spec_mappings: [{spec_id, story_ids, no_match}]})
and for each non-no_match spec:
  - Adds a ``stories:`` block with the mapped story IDs
  - Removes the ``- missing_story_reference`` line from ``lint_suppress:``
  - If ``lint_suppress:`` only had that one item, removes the whole block

Text-manipulation approach: same line-by-line state machine as backfill_stories.py.
No YAML load/dump round-trip — preserves all formatting.

Usage:
    uv run python scripts/apply_story_mappings.py mappings.json [--dry-run]
"""

import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Matches the start of a spec item: "  - id: SPEC-01-001"
_ITEM_START_RE = re.compile(r"^(\s+)- id: ([A-Z]{2,8}-\d{2}-\d{3}[a-z]?)\s*$")
# Matches lint_suppress: line
_LINT_SUPPRESS_RE = re.compile(r"^(\s+)lint_suppress:\s*$")
# Matches "- missing_story_reference"
_MSR_ITEM_RE = re.compile(r"^\s+-\s+missing_story_reference\s*$")
# Matches any list item under lint_suppress
_LIST_ITEM_RE = re.compile(r"^\s+-\s+\S")


def _build_story_map(spec_mappings: list[dict]) -> dict[str, list[str]]:
    """Return spec_id -> story_ids for mappings that have a story match."""
    story_map: dict[str, list[str]] = {}
    for m in spec_mappings:
        if not m.get("no_match") and m.get("story_ids"):
            story_map[m["spec_id"]] = m["story_ids"]
    return story_map


def _collect_item_lines(
    lines: list[str], i: int, item_indent: str
) -> tuple[list[str], int]:
    """Collect the spec item starting at lines[i].

    Returns (item_lines, next_index).
    """
    item_lines: list[str] = [lines[i]]
    i += 1
    while i < len(lines):
        nxt = lines[i]
        stripped = nxt.rstrip("\n\r")
        if stripped and not stripped.startswith(" " * (len(item_indent) + 1)):
            break
        item_lines.append(nxt)
        i += 1
    return item_lines, i


def _collect_suppress_items(
    item_lines: list[str], j: int
) -> tuple[list[str], int]:
    """Collect the lint_suppress list items starting at item_lines[j].

    Returns (suppress_items, next_index).
    """
    suppress_items: list[str] = []
    while j < len(item_lines) and _LIST_ITEM_RE.match(item_lines[j]):
        suppress_items.append(item_lines[j])
        j += 1
    return suppress_items, j


def _rewrite_suppress_block(
    header: str,
    suppress_items: list[str],
    field_indent: str,
    story_ids: list[str],
) -> list[str] | None:
    """Replace missing_story_reference in a lint_suppress block with stories.

    Returns the replacement lines, or None if the block has no
    missing_story_reference item.
    """
    if not any(_MSR_ITEM_RE.match(si) for si in suppress_items):
        return None

    remaining = [si for si in suppress_items if not _MSR_ITEM_RE.match(si)]

    # Insert stories: block (before lint_suppress, or in its place)
    new_lines = [f"{field_indent}stories:\n"]
    for story in story_ids:
        new_lines.append(f"{field_indent}- {story}\n")

    # Keep the remaining lint_suppress items if any
    if remaining:
        new_lines.append(header)  # lint_suppress: header
        new_lines.extend(remaining)
    return new_lines


def _rewrite_item(
    item_lines: list[str], field_indent: str, story_ids: list[str]
) -> tuple[list[str], bool]:
    """Rewrite every lint_suppress block in one spec item.

    Returns (new_item_lines, modified).
    """
    new_item: list[str] = []
    j = 0
    modified = False
    while j < len(item_lines):
        il = item_lines[j]
        j += 1
        if not _LINT_SUPPRESS_RE.match(il):
            new_item.append(il)
            continue

        suppress_items, j = _collect_suppress_items(item_lines, j)
        replacement = _rewrite_suppress_block(
            il, suppress_items, field_indent, story_ids
        )
        if replacement is None:
            # Put back unchanged
            new_item.append(il)
            new_item.extend(suppress_items)
            continue

        new_item.extend(replacement)
        modified = True
    return new_item, modified


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
    i = 0
    applied = 0
    skipped = 0

    while i < len(lines):
        m = _ITEM_START_RE.match(lines[i])
        if not m:
            result.append(lines[i])
            i += 1
            continue

        item_indent = m.group(1)  # e.g. "  "
        field_indent = item_indent + "  "  # 2 more spaces for fields
        item_lines, i = _collect_item_lines(lines, i, item_indent)

        # Check if this spec needs story mapping
        story_ids = story_map.get(m.group(2))
        if story_ids is None:
            result.extend(item_lines)
            continue

        # Check it doesn't already have stories: (shouldn't, but guard)
        if any(re.match(r"^\s+stories:", line) for line in item_lines):
            result.extend(item_lines)
            skipped += 1
            continue

        new_item, modified = _rewrite_item(item_lines, field_indent, story_ids)
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
