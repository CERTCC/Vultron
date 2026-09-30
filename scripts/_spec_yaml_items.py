"""Line-level slicing of spec YAML into items, shared by the one-shot spec scripts.

The relabel and story-mapping scripts edit ``specs/*.yaml`` as text rather than
through a YAML load/dump round-trip, so every untouched line survives byte for
byte. Each of them needs the same first step: walk a file and hand back every
``- id: XX-NN-NNN`` item together with the lines that belong to it. That state
machine lives here once (CS-22-001) instead of once per script.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

# "  - id: SPEC-01-001" at any indent (items sit at 0, 2 or 6 spaces).
ITEM_START_RE = re.compile(r"^(\s*)- id: ([A-Z]{2,8}-\d{2}-\d{3}[a-z]?)\s*$")


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


def iter_blocks(lines: list[str]) -> Iterator[str | SpecItem]:
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
