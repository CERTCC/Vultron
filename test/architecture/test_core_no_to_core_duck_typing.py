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

"""Ratchet: core never duck-types a wire→core projection (ARCH-20-008).

Under ADR-0099 detail 3 the wire class of a domain type *is* the core class,
so no object core holds carries a ``to_core()`` projection.  A
``getattr(obj, "to_core", None)`` in core therefore always answers ``None``
and the branch behind it is dead code that reads as a live fallback (#3840).
The two sites that had it were removed with this test; a new one fails here.

``project_wire_snapshot_to_core`` and ``_project_to_core_participant`` are
identifiers, not attribute accesses, and neither fragment below matches them.
"""

import pytest

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"
_FORBIDDEN = ('"to_core"', "'to_core'", ".to_core(")


@pytest.mark.spec("ARCH-20-008")
def test_core_has_no_to_core_duck_typing() -> None:
    """No line under ``vultron/core/`` names a ``to_core`` attribute."""
    offenders: list[str] = []
    for path, source in _corpus.sources_mentioning("to_core", under=_CORE):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        for lineno, line in enumerate(source.splitlines(), start=1):
            if any(fragment in line for fragment in _FORBIDDEN):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        "core duck-types a wire→core projection (ARCH-20-008); a core-branch "
        "object is already canonical and a snapshot dict goes through "
        "project_wire_snapshot_to_core:\n  " + "\n  ".join(offenders)
    )
