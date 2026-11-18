#!/usr/bin/env python

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

"""Following a case: a reading per new ledger entry, inside the shadow tool.

A case reader reads a case once (``CaseReader.read_case``).  A reader whose
source pushes each new entry can also follow the case, as the live Vultron
case reader does over a node's event stream (#6531).  :class:`CaseFollower`
names that operation.  It belongs to the case shadow tool, not to the core:
only one reader can follow and only the dashboard calls it, so the core
``CaseReader`` port is unchanged (CRD-01-002).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Protocol, runtime_checkable

from vultron.core.models.case_reading import CaseReading
from vultron.errors import VultronError

#: What a follow yields: the case's whole reading after a new entry, or
#: the refusal of that reading.
FollowedReading = CaseReading | VultronError


@runtime_checkable
class CaseFollower(Protocol):
    """A case reader that can also follow a case as its ledger grows."""

    def follow_case(
        self,
        case_id: str,
        *,
        heartbeat: Callable[[], None] | None = None,
    ) -> Iterator[FollowedReading]:
        """Yield the case's whole reading after each new entry arrives.

        Each reading holds every entry received so far, in log-index order
        (SHD-04-003).  A reading that cannot be accepted is yielded as the
        error refusing it, never as a reading without the bad entry
        (SHD-04-004).  The iterator ends when the source ends the follow
        or can no longer be reached; an error that ends it is the last
        item.

        Args:
            case_id: The case to follow, as the reader's ``read_case``
                takes it.
            heartbeat: Called from time to time while no new entry
                arrives, such as at each keepalive the source sends, so a
                caller that is waiting on the follow can stop it.
        """
        ...


__all__ = ["CaseFollower", "FollowedReading"]
