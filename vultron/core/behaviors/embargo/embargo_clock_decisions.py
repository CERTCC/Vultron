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

"""The clock decisions every embargo tree takes, received or triggered.

The consent rows are what an embargo act reads (CM-28-007), so the
CASE_MANAGER expires every overdue invitation of the case whenever it handles
an embargo activity: before it commits the case owner's decision on a
proposal, and on every other received embargo activity and embargo trigger
(CM-28-015).  The sweep is a clock decision (CLP-10-025, ADR-0135): a
received embargo tree passes :func:`embargo_clock_decisions` as its
``clock_decisions``, which the factory runs after the door guards and the
case-wide decisions (the end-time check), and ``SvcEmbargoTriggerBase``
adds them to the clock-decision stage ahead of its own tree.  Either way the
stage runs only at the CASE_MANAGER (BT-17-001).

Where the end-time check runs too, the sweep runs after it, so a termination
it commits has already frozen the rows of every embargo it ended (ADR-0122).
Terminate-embargo takes the sweep alone: its own tree answers for the end
time.  The P/X/A refusal of an Invite or of an Accept
(``RefuseEmbargoInviteBT``) takes no clock decision: its handler checks the
sender before it, but runs it as a tree of its own with no sender rule, and
the factory gives such a tree no clock-decision stage (CLP-10-025).  The
next admitted embargo activity sweeps instead; #4642 makes the refusal a
guard of the Invite and Accept trees, which take the sweep.
"""

from datetime import datetime

import py_trees

from vultron.core.behaviors.embargo.nodes.invitation_expiry import (
    ExpireOverdueInvitesNode,
)
from vultron.core.models._helpers import now_utc

__all__ = ["OVERDUE_INVITES_SWEEP_NAME", "embargo_clock_decisions"]

#: Name of the overdue-invitation sweep node in a clock-decision stage.
OVERDUE_INVITES_SWEEP_NAME = "SweepOverdueEmbargoInvites"


def embargo_clock_decisions(
    case_id: str, now: datetime | None = None
) -> list[py_trees.behaviour.Behaviour]:
    """The embargo clock decisions for *case_id*, read against *now*.

    *now* defaults to the CASE_MANAGER's clock: a clock decision decides
    from its own clock, never from the received activity (CLP-10-025).
    Ungated: the caller composes them into the gated stage.
    """
    at = now if now is not None else now_utc()
    return [
        ExpireOverdueInvitesNode(
            case_id=case_id, now=at, name=OVERDUE_INVITES_SWEEP_NAME
        )
    ]
