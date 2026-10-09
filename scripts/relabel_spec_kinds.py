"""Relabel spec items' ``kind:`` and drop their ``missing_story_reference`` suppression.

Applies the MS-12 decision tree's outcome to the spec YAML (issues #3600 and
#4312). The input is a JSON object mapping each spec ID to one of:

- a kind string, or ``null`` for "keep the kind" (the inert-suppression
  cleanup of #3600 AC-6). The item's ``kind:`` line is rewritten when a kind is
  given, and ``missing_story_reference`` is removed from its ``lint_suppress:``
  list, in block or flow style, dropping the list when that empties it;
- an object ``{"kind": <kind or null>, "stories": [...], "suppress": bool}``
  for a relabel *to* ``protocol``, where the suppression comes back with the
  kind rather than leaving with it (#4312). ``stories`` appends a ``stories:``
  list (the item must not already have one) and strips the suppression as the
  plain form does; ``"suppress": true`` adds ``missing_story_reference``
  instead. Giving both is an error: a story is what makes the suppression
  unnecessary (SR-11-003).

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
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.specs.yaml_items import (
    SpecItem,
    add_lint_suppression,
    append_list_field,
    iter_blocks,
    remove_lint_suppression,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPECS_DIR = _REPO_ROOT / "specs"

_SUPPRESSION = "missing_story_reference"

# A trailing ``# comment`` on a scalar line is kept and re-emitted verbatim.
_KIND_RE = re.compile(r"^(\s+)kind:\s*(\S+)(\s+#.*)?\s*$")


@dataclass(frozen=True)
class _Instruction:
    """One mapping entry, normalised from either JSON form."""

    kind: str | None
    stories: tuple[str, ...] = ()
    suppress: bool = False


def _parse_instruction(spec_id: str, value: object) -> _Instruction:
    """Normalise a mapping value.

    Raises ``TypeError`` for a value of the wrong type and ``ValueError`` for
    a well-typed but inconsistent one.
    """
    if value is None or isinstance(value, str):
        return _Instruction(kind=value)
    if not isinstance(value, dict):
        raise TypeError(f"{spec_id}: expected a kind, null or an object")
    unknown = set(value) - {"kind", "stories", "suppress"}
    if unknown:
        raise ValueError(f"{spec_id}: unknown key(s) {sorted(unknown)}")
    kind = value.get("kind")
    stories = value.get("stories", [])
    suppress = value.get("suppress", False)
    if kind is not None and not isinstance(kind, str):
        raise TypeError(f"{spec_id}: kind must be a string or null")
    if not isinstance(stories, list) or not all(
        isinstance(story, str) and story for story in stories
    ):
        raise ValueError(f"{spec_id}: stories must be a list of story IDs")
    if len(set(stories)) != len(stories):
        raise ValueError(f"{spec_id}: stories repeats a story ID")
    if not isinstance(suppress, bool):
        raise TypeError(f"{spec_id}: suppress must be true or false")
    if stories and suppress:
        raise ValueError(
            f"{spec_id}: give stories or suppress, not both — a story is "
            f"what makes the suppression unnecessary"
        )
    return _Instruction(kind=kind, stories=tuple(stories), suppress=suppress)


class _RunTally:
    """Per-run tallies and the mapping entries the corpus never presented."""

    def __init__(self, mapping: dict[str, _Instruction]) -> None:
        self.pending = dict(mapping)
        self.relabeled = 0
        self.stripped = 0
        self.added = 0
        self.storied = 0
        self.unchanged_kind: list[str] = []
        self.no_suppression: list[str] = []
        self.already_suppressed: list[str] = []
        self.kind_not_found: list[str] = []


def _apply_suppression(
    item: SpecItem, instruction: _Instruction, tally: _RunTally
) -> list[str]:
    """Add or strip the suppression as *instruction* asks, and tally it."""
    if instruction.suppress:
        lines, added = add_lint_suppression(item, _SUPPRESSION)
        if added:
            tally.added += 1
        else:
            tally.already_suppressed.append(item.spec_id)
        return lines
    lines, stripped = remove_lint_suppression(item, _SUPPRESSION)
    if stripped:
        tally.stripped += 1
    else:
        tally.no_suppression.append(item.spec_id)
    return lines


def _rewrite_item(
    item: SpecItem, instruction: _Instruction, tally: _RunTally
) -> list[str]:
    """Return the item's lines with its kind, suppression and stories rewritten."""
    lines = _apply_suppression(item, instruction, tally)
    if instruction.stories:
        lines = append_list_field(
            SpecItem(item.spec_id, item.indent, lines),
            "stories",
            instruction.stories,
        )
        tally.storied += 1
    new_kind = instruction.kind
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

    if new_kind is not None and not kind_seen:
        tally.kind_not_found.append(item.spec_id)
    return out


def relabel_text(yaml_path: Path, tally: _RunTally) -> str | None:
    """Return one spec file's rewritten text, or ``None`` when it is unchanged.

    Writes nothing, so :func:`main` can compute every file before touching
    any: a ``ValueError`` from one item leaves the whole corpus as it was.
    """
    lines = yaml_path.read_text(encoding="utf-8").splitlines(keepends=True)
    result: list[str] = []
    for block in iter_blocks(lines):
        if isinstance(block, str):
            result.append(block)
            continue
        if block.spec_id not in tally.pending:
            result.extend(block.lines)
            continue
        instruction = tally.pending.pop(block.spec_id)
        result.extend(_rewrite_item(block, instruction, tally))

    new_text = "".join(result)
    return None if new_text == "".join(lines) else new_text


def _report(tally: _RunTally) -> bool:
    """Print the run's tallies; return True when the run failed."""
    print(
        f"\n{tally.relabeled} kind(s) relabeled; {tally.stripped} "
        f"{_SUPPRESSION} suppression(s) removed"
    )
    if tally.added or tally.storied:
        print(
            f"{tally.added} {_SUPPRESSION} suppression(s) added; "
            f"{tally.storied} stories: list(s) added"
        )
    if tally.already_suppressed:
        print(
            f"already carried {_SUPPRESSION} "
            f"({len(tally.already_suppressed)}): "
            f"{sorted(tally.already_suppressed)}"
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
    return failed


def _load_mapping(path: Path) -> dict[str, _Instruction] | None:
    """Parse the JSON mapping; print why and return ``None`` when it is invalid."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        print(
            "invalid mapping: expected a JSON object of spec IDs",
            file=sys.stderr,
        )
        return None
    try:
        return {
            spec_id: _parse_instruction(spec_id, value)
            for spec_id, value in raw.items()
        }
    except (TypeError, ValueError) as exc:
        print(f"invalid mapping: {exc}", file=sys.stderr)
        return None


def _compute_rewrites(specs_dir: Path, tally: _RunTally) -> dict[Path, str]:
    """Return every changed file's new text, writing nothing.

    A ``ValueError`` from any item propagates before a single file is written.
    """
    rewrites: dict[Path, str] = {}
    for yaml_path in sorted(specs_dir.glob("*.yaml")):
        new_text = relabel_text(yaml_path, tally)
        if new_text is not None:
            rewrites[yaml_path] = new_text
    return rewrites


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
    mapping = _load_mapping(Path(args[0]))
    if mapping is None:
        return 2
    tally = _RunTally(mapping)
    try:
        rewrites = _compute_rewrites(specs_dir, tally)
    except ValueError as exc:
        print(f"no file changed: {exc}", file=sys.stderr)
        return 2

    for yaml_path, new_text in rewrites.items():
        if not dry_run:
            yaml_path.write_text(new_text, encoding="utf-8")
        shown = (
            yaml_path.relative_to(_REPO_ROOT)
            if yaml_path.is_relative_to(_REPO_ROOT)
            else yaml_path
        )
        print(f"{'(dry-run) ' if dry_run else ''}{shown}")

    return 1 if _report(tally) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
