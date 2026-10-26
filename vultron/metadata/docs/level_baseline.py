"""The shrink-only baseline of upward level dependencies (DF-11-002).

Read and written by :mod:`vultron.metadata.docs.level_order`, which re-exports
these names. Each entry is ``page | term | reason``: a violation that predates
the check, keyed by the page and the glossary term rather than a line number so
an unrelated edit above the use does not make the entry stale.
"""

from __future__ import annotations

from pathlib import Path

from vultron.metadata.docs.baseline_file import (
    BaselineEntry,
    read_keyed_entries,
    write_keyed_entries,
)

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


def read_baseline_entries(
    path: Path | None = None,
) -> dict[tuple[str, str], BaselineEntry]:
    """Return ``{(page, term): entry}`` for every baselined violation.

    Raises:
        MetadataLoadErrors: Naming ``path:line`` for every entry that is not
            three ``|``-separated fields with a non-empty reason, or repeats
            an earlier entry.
    """
    entries = read_keyed_entries(path or BASELINE_PATH, ("page", "term"))
    return {(page, term): entry for (page, term), entry in entries.items()}


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
    write_keyed_entries(path or BASELINE_PATH, _BASELINE_HEADER, entries)
