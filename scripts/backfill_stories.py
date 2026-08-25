"""Backfill stories: entries into kind:protocol spec YAML files.

Reads docs/reference/user_stories/traceability.md to build a forward
story→spec_id mapping, inverts it to spec_id→stories, loads the spec
registry to discover which specs are kind:protocol, then inserts a
``stories:`` block into the YAML text of each affected file.

Text-insertion approach: preserves ALL existing formatting.  No load/dump
round-trip is performed — only lines for the new ``stories:`` field are
injected.

Usage (from repo root):
    uv run python scripts/backfill_stories.py
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRACEABILITY_PATH = _REPO_ROOT / "docs/reference/user_stories/traceability.md"
_SPECS_DIR = _REPO_ROOT / "specs"


# ---------------------------------------------------------------------------
# Parse traceability.md
# ---------------------------------------------------------------------------

_STORY_RE = re.compile(r"^\s*-\s+\*\*story_(\d{4}_\d{3})\*\*")
_SPEC_REF_RE = re.compile(r"^\s+-\s+\*\*([A-Z]{2,8}-\d{2}-\d{3}[a-z]?)\*\*")


def parse_traceability(path: Path) -> dict[str, list[str]]:
    """Return {story_id: [spec_id, ...]} from traceability.md."""
    story_to_specs: dict[str, list[str]] = defaultdict(list)
    current_story = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _STORY_RE.match(line)
        if m:
            current_story = f"story_{m.group(1)}"
            continue
        if current_story:
            m2 = _SPEC_REF_RE.match(line)
            if m2:
                spec_id = m2.group(1)
                if spec_id not in story_to_specs[current_story]:
                    story_to_specs[current_story].append(spec_id)
    return dict(story_to_specs)


def invert_mapping(
    story_to_specs: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Return {spec_id: [story_id, ...]} sorted by story_id."""
    spec_to_stories: dict[str, list[str]] = defaultdict(list)
    for story_id, spec_ids in story_to_specs.items():
        for spec_id in spec_ids:
            spec_to_stories[spec_id].append(story_id)
    return {sid: sorted(stories) for sid, stories in spec_to_stories.items()}


# ---------------------------------------------------------------------------
# Discover protocol-kind specs via registry
# ---------------------------------------------------------------------------


def get_protocol_spec_ids(specs_dir: Path) -> set[str]:
    """Return spec IDs with kind:protocol from the loaded registry."""
    import yaml

    protocol_ids: set[str] = set()
    for yaml_path in sorted(specs_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  [SKIP] {yaml_path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        for group in data.get("groups", []):
            for spec in group.get("specs", []):
                if spec.get("kind") == "protocol":
                    protocol_ids.add(spec["id"])
    return protocol_ids


# ---------------------------------------------------------------------------
# Text-based insertion of stories: into a YAML file
# ---------------------------------------------------------------------------

# Matches the start of a spec item: "  - id: SPEC-01-001" (2-space indent)
_ITEM_START_RE = re.compile(r"^(\s+)- id: ([A-Z]{2,8}-\d{2}-\d{3}[a-z]?)\s*$")


def insert_stories_in_yaml(
    yaml_path: Path, spec_to_stories: dict[str, list[str]]
) -> int:
    """Insert stories: field into spec items that need it.

    Returns the number of specs updated.
    """
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    result: list[str] = []
    i = 0
    updated = 0

    while i < len(lines):
        line = lines[i]
        m = _ITEM_START_RE.match(line)
        if m:
            item_indent = m.group(1)  # e.g. "  "
            spec_id = m.group(2)
            field_indent = item_indent + "  "  # 2 more spaces

            # Collect all lines belonging to this spec item
            item_lines: list[str] = [line]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                stripped = nxt.rstrip("\n\r")
                # Next sibling item at same indent level OR a shallower level
                if stripped and not stripped.startswith(
                    " " * (len(item_indent) + 1)
                ):
                    break
                item_lines.append(nxt)
                i += 1

            # Insert stories: if this spec needs it and doesn't already have one
            if spec_id in spec_to_stories:
                has_stories = any(
                    re.match(r"^\s+stories:", l) for l in item_lines
                )
                if not has_stories:
                    stories = spec_to_stories[spec_id]
                    stories_lines: list[str] = [f"{field_indent}stories:\n"]
                    for story in stories:
                        stories_lines.append(f"{field_indent}- {story}\n")
                    item_lines.extend(stories_lines)
                    updated += 1

            result.extend(item_lines)
            continue

        result.append(line)
        i += 1

    if updated > 0:
        yaml_path.write_text("".join(result), encoding="utf-8")

    return updated


# ---------------------------------------------------------------------------
# Suppression insertion for protocol MUST specs not in traceability
# ---------------------------------------------------------------------------

_MUST_RE = re.compile(r"^\s+priority:\s+MUST\s*$")
_LINT_SUPPRESS_RE = re.compile(r"^(\s+)lint_suppress:\s*$")
_SUPPRESS_ITEM_RE = re.compile(r"^\s+-\s+missing_story_reference\s*$")


def _collect_protocol_must_no_stories(
    yaml_path: Path, backfill_map: dict
) -> set[str]:
    """Return spec IDs in yaml_path that are kind:protocol, MUST, no stories, not in backfill_map."""
    import yaml as _yaml

    try:
        data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if not isinstance(data, dict):
        return set()

    result = set()
    for group in data.get("groups", []):
        for spec in group.get("specs", []):
            sid = spec.get("id", "")
            if (
                spec.get("kind") == "protocol"
                and spec.get("priority") == "MUST"
                and not spec.get("stories")
                and sid not in backfill_map
            ):
                result.add(sid)
    return result


def insert_suppress_in_yaml(yaml_path: Path, to_suppress: set[str]) -> int:
    """Add lint_suppress: [missing_story_reference] to specs in to_suppress.

    Handles:
    - No lint_suppress: → adds new lint_suppress: block
    - Existing lint_suppress: → appends the item to the list

    Returns count of specs updated.
    """
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    result: list[str] = []
    i = 0
    updated = 0

    while i < len(lines):
        line = lines[i]
        m = _ITEM_START_RE.match(line)
        if m:
            item_indent = m.group(1)
            spec_id = m.group(2)
            field_indent = item_indent + "  "

            # Collect the item's lines
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

            if spec_id in to_suppress:
                # Check if already suppressed
                already_suppressed = any(
                    _SUPPRESS_ITEM_RE.match(l) for l in item_lines
                )
                if not already_suppressed:
                    # Find existing lint_suppress: block
                    suppress_idx = None
                    for j, il in enumerate(item_lines):
                        if _LINT_SUPPRESS_RE.match(il):
                            suppress_idx = j
                            break

                    if suppress_idx is not None:
                        # Append after the last existing item in the lint_suppress list
                        # Find the last item under lint_suppress
                        last_item_idx = suppress_idx
                        for j in range(suppress_idx + 1, len(item_lines)):
                            stripped = item_lines[j].rstrip("\n\r")
                            if stripped and stripped.startswith(
                                field_indent + "-"
                            ):
                                last_item_idx = j
                            elif stripped and not stripped.startswith(
                                " " * (len(field_indent) + 1)
                            ):
                                break
                        insert_pos = last_item_idx + 1
                        item_lines.insert(
                            insert_pos,
                            f"{field_indent}- missing_story_reference\n",
                        )
                    else:
                        # Add a new lint_suppress: block at the end of the item
                        item_lines.append(f"{field_indent}lint_suppress:\n")
                        item_lines.append(
                            f"{field_indent}- missing_story_reference\n"
                        )

                    updated += 1

            result.extend(item_lines)
            continue

        result.append(line)
        i += 1

    if updated > 0:
        yaml_path.write_text("".join(result), encoding="utf-8")

    return updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Parsing traceability.md …")
    story_to_specs = parse_traceability(_TRACEABILITY_PATH)
    spec_to_stories = invert_mapping(story_to_specs)
    print(
        f"  {len(story_to_specs)} stories → {len(spec_to_stories)} unique spec IDs"
    )

    print("Loading protocol spec IDs …")
    protocol_ids = get_protocol_spec_ids(_SPECS_DIR)
    print(f"  {len(protocol_ids)} kind:protocol specs in registry")

    # Filter to only protocol-kind specs that appear in traceability
    backfill_map = {
        sid: stories
        for sid, stories in spec_to_stories.items()
        if sid in protocol_ids
    }
    print(
        f"  {len(backfill_map)} protocol specs have story references to backfill"
    )

    total_stories = 0
    total_suppressed = 0

    for yaml_path in sorted(_SPECS_DIR.glob("*.yaml")):
        n = insert_stories_in_yaml(yaml_path, backfill_map)
        if n:
            print(f"  {yaml_path.name}: added stories to {n} spec(s)")
            total_stories += n

    print(f"  Stories backfill complete. {total_stories} spec(s) updated.")

    # Add lint_suppress to protocol MUST specs without story coverage
    print(
        "\nSuppressing SR-11-003 on protocol MUST specs not in traceability …"
    )
    for yaml_path in sorted(_SPECS_DIR.glob("*.yaml")):
        to_suppress = _collect_protocol_must_no_stories(
            yaml_path, backfill_map
        )
        if to_suppress:
            n = insert_suppress_in_yaml(yaml_path, to_suppress)
            if n:
                print(f"  {yaml_path.name}: suppressed {n} spec(s)")
                total_suppressed += n

    print(f"\nBackfill complete.")
    print(f"  {total_stories} spec(s) got stories:")
    print(
        f"  {total_suppressed} spec(s) got lint_suppress: [missing_story_reference]"
    )


if __name__ == "__main__":
    main()
