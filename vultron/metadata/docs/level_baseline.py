"""The shrink-only baseline of upward level dependencies (DF-11-002).

Read and written by :mod:`vultron.metadata.docs.level_order`, which re-exports
these names. Each entry is ``page | term | reason``: a violation that predates
the check, keyed by the page and the glossary term rather than a line number so
an unrelated edit above the use does not make the entry stale.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from vultron.metadata.docs.baseline_file import entry_lines, write_entries
from vultron.metadata.file_loading import FailureCollector, MetadataLoadError

#: Upward dependencies that predate the check, one per line as
#: ``page | term | reason``. Kept outside ``docs/`` so it is never published.
BASELINE_PATH = Path(__file__).with_name("level_order_baseline.txt")

_BASELINE_HEADER = """\
# Upward level dependencies in docs/ that predate the DF-11-002 check.
#
# Maintained by vultron.metadata.docs.level_order. One entry per line:
#   <docs/-relative page> | <glossary term> | <reason it is still unfixed>
# This list may only shrink. Fix an entry by linking the term's first use to
# the page that introduces it (SG-11) or by moving the page, then run
# `uv run docs-level-order --prune-baseline`. Do not add entries by hand;
# test_level_baseline.py pins the exact set of entries.
"""


class BaselineEntry(NamedTuple):
    """One tolerated violation: why it is unfixed, and where it is listed."""

    reason: str
    line: int


def read_baseline_entries(
    path: Path | None = None,
) -> dict[tuple[str, str], BaselineEntry]:
    """Return ``{(page, term): entry}`` for every baselined violation.

    Raises:
        MetadataLoadErrors: Naming ``path:line`` for every entry that is not
            three ``|``-separated fields with a non-empty reason, or repeats
            an earlier entry.
    """
    path = path or BASELINE_PATH
    entries: dict[tuple[str, str], BaselineEntry] = {}
    collector = FailureCollector()
    for number, line in entry_lines(path):
        with collector.attempt():
            fields = [f.strip() for f in line.split("|")]
            if len(fields) != 3 or not all(fields):
                raise MetadataLoadError(
                    "an entry is `page | term | reason`, each non-empty; "
                    "every baselined violation names why it is unfixed",
                    path=path.name,
                    line=number,
                )
            page, term, reason = fields
            if (page, term) in entries:
                raise MetadataLoadError(
                    f"repeats the entry for {page} | {term}",
                    path=path.name,
                    line=number,
                )
            entries[(page, term)] = BaselineEntry(reason, number)
    collector.raise_if_any(
        summary=f"{len(collector.failures)} malformed baseline entry(ies):"
    )
    return entries


def read_baseline(path: Path | None = None) -> dict[tuple[str, str], str]:
    """Return ``{(page, term): reason}`` for every baselined violation.

    Raises:
        MetadataLoadErrors: As :func:`read_baseline_entries`.
    """
    return {
        key: entry.reason for key, entry in read_baseline_entries(path).items()
    }


def write_baseline(
    entries: dict[tuple[str, str], str], path: Path | None = None
) -> None:
    """Write *entries* sorted, under the explanatory header."""
    write_entries(
        path or BASELINE_PATH,
        _BASELINE_HEADER,
        (
            f"{page} | {term} | {reason}"
            for (page, term), reason in entries.items()
        ),
    )
