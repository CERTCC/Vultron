"""Relabel spec items' ``kind:`` and drop their ``missing_story_reference`` suppression.

Applies the MS-12 decision tree's outcome to the spec YAML (issue #3600). The
input is a JSON object ``{spec_id: new_kind}``; a ``null`` kind means "keep
the kind, only strip the suppression" (the inert-suppression cleanup of AC-6).
For every listed item this script:

- rewrites the item's ``kind:`` line when a new kind is given;
- removes ``missing_story_reference`` from the item's ``lint_suppress:`` list,
  in block or flow style;
- drops the ``lint_suppress:`` block entirely when that leaves it empty.

Text-manipulation approach: the same line-by-line state machine as
``apply_story_mappings.py``. No YAML load/dump round-trip, so every other line
of every file is preserved byte for byte.

Usage:
    uv run python scripts/relabel_spec_kinds.py mapping.json [--dry-run] [--specs-dir DIR]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from vultron.metadata.specs.yaml_items import SpecItem, iter_blocks

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPECS_DIR = _REPO_ROOT / "specs"

_SUPPRESSION = "missing_story_reference"

# A trailing ``# comment`` on a scalar line is kept and re-emitted verbatim.
_KIND_RE = re.compile(r"^(\s+)kind:\s*(\S+)(\s+#.*)?\s*$")
_LINT_SUPPRESS_BLOCK_RE = re.compile(r"^(\s+)lint_suppress:\s*$")
_LINT_SUPPRESS_FLOW_RE = re.compile(
    r"^(\s+)lint_suppress:\s*\[([^\]]*)\](\s+#.*?)?\s*$"
)
# A list entry: a code, optionally quoted, optionally followed by a comment.
_LIST_ITEM_RE = re.compile(r"^\s+-\s+['\"]?(\w+)['\"]?\s*(?:#.*)?$")
_COMMENT_RE = re.compile(r"^\s*#")


class _RunTally:
    """Per-run tallies and the mapping entries the corpus never presented."""

    def __init__(self, mapping: dict[str, str | None]) -> None:
        self.pending = dict(mapping)
        self.relabeled = 0
        self.stripped = 0
        self.unchanged_kind: list[str] = []
        self.no_suppression: list[str] = []
        self.kind_not_found: list[str] = []


def _strip_from_block(
    header: str, item_lines: list[str], start: int
) -> tuple[list[str], int, bool]:
    """Rewrite one block-style ``lint_suppress:`` list starting at *start*.

    Returns ``(lines_to_emit, next_index, removed)``. Each entry is an item
    line plus the comment lines that precede it, so a comment justifying a
    suppression leaves with the item it justifies; trailing comments with no
    item are kept. The header is dropped only when the list had entries and
    none remain; a header with no parsed entries (a null ``lint_suppress:``)
    is not a target and is left untouched.

    A line that still belongs to the list — it starts with a dash, or sits
    deeper than the header — but is not a list entry raises ``ValueError``:
    silently breaking out would drop the header and orphan the entries after
    it, producing unparseable YAML.
    """
    header_indent = len(header) - len(header.lstrip())
    entries: list[tuple[list[str], str, str]] = []
    pending_comments: list[str] = []
    j = start
    while j < len(item_lines):
        candidate = item_lines[j]
        if _COMMENT_RE.match(candidate):
            pending_comments.append(candidate)
            j += 1
            continue
        im = _LIST_ITEM_RE.match(candidate)
        if im is None:
            body = candidate.rstrip("\n\r")
            in_list = body.lstrip().startswith("-") or (
                body and len(body) - len(body.lstrip()) > header_indent
            )
            if in_list:
                raise ValueError(
                    f"unparseable lint_suppress entry under "
                    f"{header.strip()!r}: {body!r}"
                )
            break
        entries.append((pending_comments, candidate, im.group(1)))
        pending_comments = []
        j += 1

    remaining = [e for e in entries if e[2] != _SUPPRESSION]
    out: list[str] = []
    if remaining or not entries:
        out.append(header)
        for comments, item, _code in remaining:
            out.extend(comments)
            out.append(item)
    out.extend(pending_comments)
    return out, j, len(remaining) != len(entries)


def _rewrite_item(
    item: SpecItem, new_kind: str | None, tally: _RunTally
) -> list[str]:
    """Return the item's lines with the kind relabeled and the suppression removed."""
    spec_id, item_lines, field_indent = (
        item.spec_id,
        item.lines,
        item.field_indent,
    )
    out: list[str] = []
    stripped_here = False
    kind_seen = False
    j = 0
    while j < len(item_lines):
        line = item_lines[j]

        km = _KIND_RE.match(line)
        if km and km.group(1) == field_indent and new_kind is not None:
            kind_seen = True
            if km.group(2) == new_kind:
                tally.unchanged_kind.append(spec_id)
            else:
                tally.relabeled += 1
            out.append(f"{field_indent}kind: {new_kind}{km.group(3) or ''}\n")
            j += 1
            continue

        fm = _LINT_SUPPRESS_FLOW_RE.match(line)
        if fm and fm.group(1) == field_indent:
            # Entries keep their spelling (quotes included); the match unquotes.
            codes = [c.strip() for c in fm.group(2).split(",") if c.strip()]
            remaining = [c for c in codes if c.strip("'\"") != _SUPPRESSION]
            if len(remaining) != len(codes):
                stripped_here = True
                # The trailing comment stays with a surviving list and leaves
                # with an emptied one, as a block-style entry's comment does.
                if remaining:
                    out.append(
                        f"{field_indent}lint_suppress: [{', '.join(remaining)}]"
                        f"{fm.group(3) or ''}\n"
                    )
            else:
                out.append(line)
            j += 1
            continue

        bm = _LINT_SUPPRESS_BLOCK_RE.match(line)
        if bm and bm.group(1) == field_indent:
            block, j, removed = _strip_from_block(line, item_lines, j + 1)
            stripped_here = stripped_here or removed
            out.extend(block)
            continue

        out.append(line)
        j += 1

    if stripped_here:
        tally.stripped += 1
    else:
        tally.no_suppression.append(spec_id)
    if new_kind is not None and not kind_seen:
        tally.kind_not_found.append(spec_id)
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
