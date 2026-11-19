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

"""Received ``Announce(<an admitted act>)``: the participant records it.

The CASE_MANAGER announces an act it admitted to an actor the act concerns
that the entry's fan-out does not reach, such as a removed or reinstated
participant (ADR-0199, CM-31-044).  The receiver reads it here::

    AnnounceAdmittedActReceivedBT (Sequence)
    ├─ ActivityAddressedToReceiverNode / ActivityNotSeenBeforeNode
    ├─ ReceivedPathNode                # the participant replica alone
    ├─ CaseOpenToExternalWrites
    ├─ <sender guard: the case's CASE_MANAGER only>
    └─ IntakeReceivedActivityNode      # records the notice (CLP-10-017)

The ``Announce`` informs and asks nothing, so nothing answers it, and the
participant writes no case state from it: a replica takes the change from the
ledger entry that carries the act (CM-31-029, CM-31-045, RSH-08-003).
Nothing is committed: the notice is the CASE_MANAGER's delivery of an entry's
act, not a case event (CLP-02-013).  A redelivery is answered by the
seen-before door (HP-01-014).  The type declares the participant-replica path
alone, so an ``Announce`` reaching the case's CASE_MANAGER, or a store that
holds no replica of the case, is refused at the path stage (HP-01-038,
HP-01-039), and one from any sender but the CASE_MANAGER by the sender guard
(HP-01-006).
"""

from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule

ANNOUNCE_ADMITTED_ACT_TREE = "AnnounceAdmittedActReceivedBT"


def announce_admitted_act_received_tree(
    *,
    sender_rule: SenderRule,
    sender_context: SenderCheckContext,
) -> ReceivedActivityTree:
    """Build the received ``Announce(<an admitted act>)`` tree.

    Args:
        sender_rule: The use case's declared sender rule (HP-01-008).
        sender_context: The ``Announce``'s sender and the case its
            ``context`` names; a case naming no CASE_MANAGER refuses the
            sender (Regime 1, ADR-0087).
    """
    return create_receive_activity_tree(
        name=ANNOUNCE_ADMITTED_ACT_TREE,
        # Only an actor the CASE_MANAGER announces to receives it; the
        # CASE_MANAGER never receives its own (HP-01-038).
        paths={ReceivedPath.PARTICIPANT_REPLICA},
        case_id=None,
        sender_rule=sender_rule,
        sender_context=sender_context,
        precondition_guards=[],
        replica_effects=[],
    )


__all__ = [
    "ANNOUNCE_ADMITTED_ACT_TREE",
    "announce_admitted_act_received_tree",
]
