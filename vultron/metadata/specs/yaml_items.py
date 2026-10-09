"""Line-level slicing of spec YAML into items, shared by the one-shot spec scripts.

The one-shot spec scripts under ``scripts/`` edit ``specs/*.yaml`` as text
rather than through a YAML load/dump round-trip, so every untouched line
survives byte for byte. Each of them needs the same first step: walk a file and
hand back every ``- id: XX-NN-NNN`` item together with the lines that belong to
it. That state machine lives here once (CS-22-001, #4016) instead of once per
script.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

# "  - id: CS-22-001" at any indent (items sit at 0, 2 or 6 spaces).
ITEM_START_RE = re.compile(r"^(\s*)- id: ([A-Z]{2,8}-\d{2}-\d{3}[a-z]?)\s*$")

# The header may carry a trailing comment (``lint_suppress:  # why``).
_LINT_SUPPRESS_BLOCK_RE = re.compile(r"^(\s+)lint_suppress:\s*(?:#.*)?$")
_LINT_SUPPRESS_FLOW_RE = re.compile(
    r"^(\s+)lint_suppress:\s*\[([^\]]*)\](\s+#.*?)?\s*$"
)
# A list entry: a code, optionally quoted, optionally followed by a comment.
_LIST_ITEM_RE = re.compile(r"^\s+-\s+['\"]?(\w+)['\"]?\s*(?:#.*)?$")
_COMMENT_RE = re.compile(r"^\s*#")


@dataclass
class SpecItem:
    """One ``- id:`` item: its ID, the indent of its dash, and its raw lines."""

    spec_id: str
    indent: str
    lines: list[str] = field(default_factory=list)

    @property
    def field_indent(self) -> str:
        """Indent of the item's own fields — two deeper than the dash."""
        return self.indent + "  "


def iter_blocks(lines: Sequence[str]) -> Iterator[str | SpecItem]:
    """Yield each line outside an item as ``str`` and each item as :class:`SpecItem`.

    An item runs from its ``- id:`` line until the next non-blank line that is
    not indented deeper than the dash. Re-emitting every yielded block in order
    reproduces the input exactly.
    """
    i = 0
    while i < len(lines):
        line = lines[i]
        m = ITEM_START_RE.match(line)
        if not m:
            yield line
            i += 1
            continue
        item = SpecItem(spec_id=m.group(2), indent=m.group(1), lines=[line])
        i += 1
        while i < len(lines):
            body = lines[i].rstrip("\n\r")
            if body and not body.startswith(" " * (len(item.indent) + 1)):
                break
            item.lines.append(lines[i])
            i += 1
        yield item


def _eol(lines: Sequence[str]) -> str:
    """The line ending *lines* already use, so an inserted line matches it."""
    return "\r\n" if lines and lines[0].endswith("\r\n") else "\n"


_BlockEntry = tuple[list[str], str, str, int]


def _scan_block(
    header: str, item_lines: Sequence[str], start: int
) -> tuple[list[_BlockEntry], list[str], int]:
    """Parse the block-style ``lint_suppress:`` list whose entries start at *start*.

    Returns ``(entries, trailing_comments, next_index)``. Each entry is
    ``(preceding_comments, line, code, index)``: a comment justifying a
    suppression belongs to the entry after it; comments after the last entry
    are trailing.

    A line that still belongs to the list — it starts with a dash, or sits
    deeper than the header — but is not a list entry raises ``ValueError``:
    stopping there would edit the list as if it ended early, dropping or
    misplacing the entries after it.
    """
    header_indent = len(header) - len(header.lstrip())
    entries: list[_BlockEntry] = []
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
        entries.append((pending_comments, candidate, im.group(1), j))
        pending_comments = []
        j += 1
    return entries, pending_comments, j


def _strip_from_block(
    header: str, item_lines: list[str], start: int, code: str
) -> tuple[list[str], int, bool]:
    """Rewrite one block-style ``lint_suppress:`` list starting at *start*.

    Returns ``(lines_to_emit, next_index, removed)``. Each entry is an item
    line plus the comment lines that precede it, so a comment justifying a
    suppression leaves with the item it justifies; trailing comments with no
    item are kept. The header is dropped only when the list had entries and
    none remain; a header with no parsed entries (a null ``lint_suppress:``)
    is not a target and is left untouched.

    An unparseable entry raises ``ValueError`` (see :func:`_scan_block`):
    silently breaking out would drop the header and orphan the entries after
    it, producing unparseable YAML.
    """
    entries, pending_comments, j = _scan_block(header, item_lines, start)
    remaining = [e for e in entries if e[2] != code]
    out: list[str] = []
    if remaining or not entries:
        out.append(header)
        for comments, item, _code, _at in remaining:
            out.extend(comments)
            out.append(item)
    out.extend(pending_comments)
    return out, j, len(remaining) != len(entries)


def remove_lint_suppression(
    item: SpecItem, code: str
) -> tuple[list[str], bool]:
    """Return *item*'s lines with *code* removed from its ``lint_suppress:``.

    Handles block and flow lists, quoted or commented entries; drops the
    ``lint_suppress:`` key entirely when *code* was its last entry. Every
    other line is returned unchanged. The flag says whether *code* was found.
    """
    out: list[str] = []
    removed = False
    j = 0
    lines = item.lines
    while j < len(lines):
        line = lines[j]
        fm = _LINT_SUPPRESS_FLOW_RE.match(line)
        if fm and fm.group(1) == item.field_indent:
            # Entries keep their spelling (quotes included); the match unquotes.
            codes = [c.strip() for c in fm.group(2).split(",") if c.strip()]
            remaining = [c for c in codes if c.strip("'\"") != code]
            if len(remaining) != len(codes):
                removed = True
                # The trailing comment stays with a surviving list and leaves
                # with an emptied one, as a block-style entry's comment does.
                if remaining:
                    out.append(
                        f"{item.field_indent}lint_suppress: "
                        f"[{', '.join(remaining)}]{fm.group(3) or ''}"
                        f"{_eol(lines)}"
                    )
            else:
                out.append(line)
            j += 1
            continue
        bm = _LINT_SUPPRESS_BLOCK_RE.match(line)
        if bm and bm.group(1) == item.field_indent:
            block, j, found = _strip_from_block(line, lines, j + 1, code)
            removed = removed or found
            out.extend(block)
            continue
        out.append(line)
        j += 1
    return out, removed


def _field_re(item: SpecItem, key: str) -> re.Pattern[str]:
    """Match *key* as one of *item*'s own fields, not a nested mapping key."""
    return re.compile(rf"^{re.escape(item.field_indent)}{re.escape(key)}:")


def _end_of_fields(item: SpecItem) -> int:
    """Index just past the item's last content line.

    Trailing blank lines, and comment lines no deeper than the item's fields,
    stay after a field appended here, so a comment that introduces the next
    item keeps its place. A ``#`` line indented deeper than the fields may be
    the last line of a block scalar (``rationale: >-`` ending ``#3377.``), so
    it is content and the scan stops there.
    """
    lines = item.lines
    depth = len(item.field_indent)
    end = len(lines)
    while end > 1:
        line = lines[end - 1].rstrip("\n\r")
        body = line.strip()
        if body:
            indent = len(line) - len(line.lstrip())
            if not body.startswith("#") or indent > depth:
                break
        end -= 1
    return end


def append_list_field(
    item: SpecItem, key: str, values: Sequence[str]
) -> list[str]:
    """Return *item*'s lines with a block-style ``key:`` list appended.

    The list goes after the item's last field, at the item's field indent.
    Raises ``ValueError`` when *item* already has *key* (merging two lists is
    a judgment this helper does not make), or when *values* is empty or
    repeats a value. The new lines copy the item's line ending.
    """
    if not values:
        raise ValueError(f"{item.spec_id}: no values to write under {key}:")
    pattern = _field_re(item, key)
    if any(pattern.match(line) for line in item.lines):
        raise ValueError(f"{item.spec_id} already has a {key}: field")
    if len(set(values)) != len(values):
        raise ValueError(f"{item.spec_id}: duplicate values under {key}:")
    end = _end_of_fields(item)
    eol = _eol(item.lines)
    added = [f"{item.field_indent}{key}:{eol}"] + [
        f"{item.field_indent}- {value}{eol}" for value in values
    ]
    return list(item.lines[:end]) + added + list(item.lines[end:])


def add_lint_suppression(item: SpecItem, code: str) -> tuple[list[str], bool]:
    """Return *item*'s lines with *code* added to its ``lint_suppress:``.

    The inverse of :func:`remove_lint_suppression`: appends to an existing
    block or flow list, or adds a block list after the item's last field when
    the item has none. The flag is ``False`` when *code* was already present,
    in which case the lines come back unchanged. An unparseable block entry
    raises ``ValueError``, as it does for :func:`remove_lint_suppression`.
    """
    lines = list(item.lines)
    eol = _eol(lines)
    for j, line in enumerate(lines):
        fm = _LINT_SUPPRESS_FLOW_RE.match(line)
        if fm and fm.group(1) == item.field_indent:
            codes = [c.strip() for c in fm.group(2).split(",") if c.strip()]
            if code in (c.strip("'\"") for c in codes):
                return lines, False
            lines[j] = (
                f"{item.field_indent}lint_suppress: "
                f"[{', '.join([*codes, code])}]{fm.group(3) or ''}{eol}"
            )
            return lines, True
        bm = _LINT_SUPPRESS_BLOCK_RE.match(line)
        if bm and bm.group(1) == item.field_indent:
            entries, _trailing, _next = _scan_block(line, lines, j + 1)
            if any(entry[2] == code for entry in entries):
                return lines, False
            if entries:
                # A new entry copies the indent of the entries already there.
                _comments, last, _code, last_at = entries[-1]
                at = last_at + 1
                indent = last[: len(last) - len(last.lstrip())]
            else:
                at, indent = j + 1, item.field_indent
            lines.insert(at, f"{indent}- {code}{eol}")
            return lines, True
    return append_list_field(item, "lint_suppress", [code]), True
