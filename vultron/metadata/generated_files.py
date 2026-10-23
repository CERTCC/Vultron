#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Compare and write whole generated files (CS-22-001).

Every generate-and-``--check`` subpackage (``vultron/metadata/AGENTS.md``
§ Generate vs. Check) asks one question of a committed artifact: does it
equal a fresh generation byte for byte?  The comparison lives here once, so
the modes cannot disagree about "stale".

Files are read and written without newline translation.  ``Path.read_text``
turns ``\\r\\n`` into ``\\n``, so a CRLF copy of an artifact would compare
equal and pass ``--check``; ``Path.write_text`` would write ``\\r\\n`` on
Windows.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path


def read_committed(target: Path) -> str | None:
    """Return *target*'s exact UTF-8 text, or ``None`` when it does not exist."""
    if not target.is_file():
        return None
    return target.read_bytes().decode("utf-8")


def write_generated(target: Path, text: str) -> None:
    """Write *text* to *target* with ``\\n`` line endings, creating parents."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def stale_paths(base: Path, desired: Mapping[str, str]) -> Iterator[str]:
    """Yield each repo-relative path in *desired* whose file differs or is missing."""
    for path, text in desired.items():
        if read_committed(base / path) != text:
            yield path


__all__ = ["read_committed", "stale_paths", "write_generated"]
