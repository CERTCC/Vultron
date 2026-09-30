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

from vultron.metadata.specs.lint import sr_11_003_gate_applies
from vultron.metadata.specs.schema import RFC2119Priority, SpecKind

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
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3326
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


def _collect_item_lines(
    lines: list[str], i: int, item_indent: str
) -> tuple[list[str], int]:
    """Collect the spec item starting at lines[i].

    The item ends at the next sibling item at the same indent level or at a
    shallower level.  Returns (item_lines, next_index).
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
            item_lines, i = _collect_item_lines(lines, i, item_indent)

            # Insert stories: if this spec needs it and doesn't already have one
            if spec_id in spec_to_stories:
                has_stories = any(
                    re.match(r"^\s+stories:", line) for line in item_lines
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

_LINT_SUPPRESS_RE = re.compile(r"^(\s+)lint_suppress:\s*$")
_SUPPRESS_ITEM_RE = re.compile(r"^\s+-\s+missing_story_reference\s*$")


def _collect_protocol_must_no_stories(
    yaml_path: Path, backfill_map: dict
) -> set[str]:
    """Return spec IDs in yaml_path that SR-11-003 would fire on and that
    backfill_map does not cover: kind protocol, priority MUST, no stories.

    The gate's scope (MUST-only, the recorded MS-02-003 exception) is read from
    :func:`~vultron.metadata.specs.lint.sr_11_003_gate_applies`, so this script
    and the linter cannot disagree about which specs need the suppression.
    """
    import yaml as _yaml

    try:
        data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  # ruff-baseline #3326
        return set()
    if not isinstance(data, dict):
        return set()

    result = set()
    for group in data.get("groups", []):
        for spec in group.get("specs", []):
            sid = spec.get("id", "")
            if (
                sr_11_003_gate_applies(
                    SpecKind(spec["kind"]), RFC2119Priority(spec["priority"])
                )
                and not spec.get("stories")
                and sid not in backfill_map
            ):
                result.add(sid)
    return result


def _find_last_suppress_item(
    item_lines: list[str], suppress_idx: int, field_indent: str
) -> int:
    """Return the index of the last list item under the lint_suppress: line.

    Returns suppress_idx itself when the list is empty.
    """
    last_item_idx = suppress_idx
    for j in range(suppress_idx + 1, len(item_lines)):
        stripped = item_lines[j].rstrip("\n\r")
        if stripped and stripped.startswith(field_indent + "-"):
            last_item_idx = j
        elif stripped and not stripped.startswith(
            " " * (len(field_indent) + 1)
        ):
            break
    return last_item_idx


def _add_suppress_item(item_lines: list[str], field_indent: str) -> None:
    """Add missing_story_reference to the item's lint_suppress: list in place.

    Appends to an existing lint_suppress: block, or adds a new block at the
    end of the item.
    """
    suppress_idx = next(
        (j for j, il in enumerate(item_lines) if _LINT_SUPPRESS_RE.match(il)),
        None,
    )
    if suppress_idx is None:
        item_lines.append(f"{field_indent}lint_suppress:\n")
        item_lines.append(f"{field_indent}- missing_story_reference\n")
        return

    last_item_idx = _find_last_suppress_item(
        item_lines, suppress_idx, field_indent
    )
    item_lines.insert(
        last_item_idx + 1, f"{field_indent}- missing_story_reference\n"
    )


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
        m = _ITEM_START_RE.match(lines[i])
        if not m:
            result.append(lines[i])
            i += 1
            continue

        item_indent = m.group(1)
        item_lines, i = _collect_item_lines(lines, i, item_indent)

        already_suppressed = any(
            _SUPPRESS_ITEM_RE.match(line) for line in item_lines
        )
        if m.group(2) in to_suppress and not already_suppressed:
            _add_suppress_item(item_lines, item_indent + "  ")
            updated += 1

        result.extend(item_lines)

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

    print("\nBackfill complete.")
    print(f"  {total_stories} spec(s) got stories:")
    print(
        f"  {total_suppressed} spec(s) got lint_suppress: [missing_story_reference]"
    )


if __name__ == "__main__":
    main()
