"""The shrink-only baseline of upward level dependencies (DF-11-002).

Read and written by :mod:`vultron.metadata.docs.level_order`. Each entry is
``page | term | reason``: a violation that predates the check, keyed by the
page and the glossary term rather than a line number so an unrelated edit above
the use does not make the entry stale.
"""

from __future__ import annotations

from pathlib import Path

from vultron.metadata.docs.baseline_file import KeyedBaseline

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


#: The level-order baseline, keyed by ``(page, term)``.
LEVEL_BASELINE = KeyedBaseline[tuple[str, str]](
    BASELINE_PATH, _BASELINE_HEADER, ("page", "term")
)

read_baseline = LEVEL_BASELINE.read
write_baseline = LEVEL_BASELINE.write
