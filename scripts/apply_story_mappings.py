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


def apply_file_mappings(
    yaml_path: Path,
    spec_mappings: list[dict],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Apply story mappings to a single spec YAML file.

    Returns (applied_count, skipped_count).
    """
    # Build lookup: spec_id -> story_ids (empty means no_match)
    story_map: dict[str, list[str]] = {}
    for m in spec_mappings:
        if not m.get("no_match") and m.get("story_ids"):
            story_map[m["spec_id"]] = m["story_ids"]

    if not story_map:
        return 0, len(spec_mappings)

    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    result: list[str] = []
    i = 0
    applied = 0
    skipped = 0

    while i < len(lines):
        line = lines[i]
        m = _ITEM_START_RE.match(line)
        if not m:
            result.append(line)
            i += 1
            continue

        item_indent = m.group(1)  # e.g. "  "
        spec_id = m.group(2)
        field_indent = item_indent + "  "  # 2 more spaces for fields

        # Collect all lines for this spec item
        item_lines: list[str] = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            stripped = nxt.rstrip("\n\r")
            if stripped and not stripped.startswith(
                " " * (len(item_indent) + 1)
            ):
                break
            item_lines.append(nxt)
            i += 1

        # Check if this spec needs story mapping
        story_ids = story_map.get(spec_id)
        if story_ids is None:
            result.extend(item_lines)
            continue

        # Check it doesn't already have stories: (shouldn't, but guard)
        if any(re.match(r"^\s+stories:", l) for l in item_lines):
            result.extend(item_lines)
            skipped += 1
            continue

        # Find and rewrite the lint_suppress block
        new_item: list[str] = []
        j = 0
        modified = False
        while j < len(item_lines):
            il = item_lines[j]
            lm = _LINT_SUPPRESS_RE.match(il)
            if not lm:
                new_item.append(il)
                j += 1
                continue

            # Collect the lint_suppress list items
            suppress_items: list[str] = []
            j += 1
            while j < len(item_lines):
                nxt = item_lines[j]
                if _LIST_ITEM_RE.match(nxt):
                    suppress_items.append(nxt)
                    j += 1
                else:
                    break

            # Check if missing_story_reference is in the list
            has_msr = any(_MSR_ITEM_RE.match(si) for si in suppress_items)
            if not has_msr:
                # Put back unchanged
                new_item.append(il)
                new_item.extend(suppress_items)
                continue

            remaining = [
                si for si in suppress_items if not _MSR_ITEM_RE.match(si)
            ]

            # Insert stories: block (before lint_suppress, or in its place)
            stories_lines = [f"{field_indent}stories:\n"]
            for story in story_ids:
                stories_lines.append(f"{field_indent}- {story}\n")
            new_item.extend(stories_lines)

            # Keep the remaining lint_suppress items if any
            if remaining:
                new_item.append(il)  # lint_suppress: header
                new_item.extend(remaining)

            modified = True

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
