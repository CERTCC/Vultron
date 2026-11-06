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
"""The per-host lock that caps concurrent heavy local checks (#5947).

Every slot container on a host shares one Docker VM, and each
``pytest -n auto``, pyright run or site build sizes itself to its own container
without seeing the others. ``.agents/skills/shared/run-heavy.py`` runs such a
command in one of a few slots shared by every container on the host. This
module names that script for the Python tools that print or run a heavy
command: ``targeted-tests --pytest`` and the ``prepush-ci-mirror`` checks.
"""

from __future__ import annotations

from collections.abc import Sequence

#: The lock wrapper, relative to the repository root each command runs in.
HEAVY_LOCK_SCRIPT = ".agents/skills/shared/run-heavy.py"

#: The wrapper as a command prefix.
HEAVY_LOCK = ("uv", "run", "python", HEAVY_LOCK_SCRIPT)

#: The wrapper's exit status when ``--wait`` ran out before a slot came free;
#: the command did not run.
WAIT_EXPIRED = 75


def under_heavy_lock(
    argv: Sequence[str], *, wait: int | None = None
) -> tuple[str, ...]:
    """*argv* run in a heavy-check slot, giving up after *wait* seconds.

    Without *wait* the wrapper's own default limit applies.
    """
    limit = () if wait is None else ("--wait", str(wait))
    return (*HEAVY_LOCK, *limit, "--", *argv)
