"""File I/O shared by the shrink-only baselines of the ``docs/`` checks.

A baseline is a text file under an explanatory ``#`` header, one entry per
line. Each check owns what an entry means and how it parses: the
``docs-frontmatter`` baseline lists page paths, and the ``docs-level-order``
baseline lists ``page | term | reason``. This module owns only the file shape,
so both read and rewrite it the same way.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path


def entry_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, line)`` for every entry in the baseline at *path*.

    Blank lines and lines starting with ``#`` are skipped. A missing file has
    no entries.
    """
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if line.strip() and not line.lstrip().startswith("#"):
            yield number, line


def write_entries(path: Path, header: str, entries: Iterable[str]) -> None:
    """Write *entries* sorted, one per line, under *header*."""
    body = "".join(f"{entry}\n" for entry in sorted(entries))
    path.write_text(header + "\n" + body, encoding="utf-8")
