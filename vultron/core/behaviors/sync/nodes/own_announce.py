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

"""The anomaly in an ``Announce(CaseLedgerEntry)`` a store sent to itself.

Split from the announce tree's factory so the factory holds composition only
(BTND-07-004).
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._event_condition_base import (
    _ActivityEventNode,
)

__all__ = ["AnnouncedEntryIsNotOwnEchoNode"]


class AnnouncedEntryIsNotOwnEchoNode(_ActivityEventNode):
    """Guard: this ``Announce`` was not sent by the actor receiving it.

    An actor that announces a ledger entry holds the case's canonical ledger,
    so it is that case's CASE_MANAGER (SYNC-13-006).  On the manager path its
    own echoed ``Announce`` only confirms delivery, and this guard is not
    there.  Off that path the echo cannot happen: a replica receiver that
    sent the ``Announce`` is not the manager of the case it holds, and the
    sender guard has already refused it.  What is left is the receiver that
    holds no replica of the case it announced — a Regime 1 anomaly
    (ADR-0087), because the manager always holds the case it manages.

    So this guard refuses it, at ERROR: the pre-genesis window the no-case
    path otherwise takes is self-healing for a *peer's* ``Announce``, which
    the genesis ``Reject`` repairs (SYNC-15-001), and that reading does not
    hold here — the store would buffer its own entry and ask itself for the
    case it is the authority for.  Reads only the blackboard.
    """

    def update(self) -> Status:
        sender_id = getattr(self.activity, "actor_id", None)
        if sender_id != self.actor_id:
            return Status.SUCCESS
        self.feedback_message = (
            f"'{self.actor_id}' announced this ledger entry and holds no"
            " replica of the case it names: the actor that announces an"
            " entry is the case's CASE_MANAGER, so this store is missing a"
            " case it is the authority for (ADR-0087, SYNC-13-006)"
        )
        self.logger.error("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
