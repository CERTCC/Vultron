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

"""Named exemptions for an emit that runs outside the CASE_MANAGER gate (BT-17-008).

``create_receive_activity_tree`` refuses an
:class:`~vultron.core.behaviors.emit_capable.EmitCapable` node that sits among
a received tree's ``replica_effects`` outside every CASE_MANAGER gate.
A tree whose ungated emit is correct by design passes one of the exemptions
declared here as ``replica_emit_exemption``.
The factory refuses an exemption not in :data:`REPLICA_EMIT_EXEMPTIONS`, an
ungated emitter the exemption does not name in ``covers``, and an exemption
that covers none of the tree's ungated emitters, so this module is the whole
list and each entry stays true.

Each exemption records the decision for one tree: why its emit speaks for the
executing actor, or is addressed only to an actor other than itself.
A sender check added to a tree without an exemption is not enough on its own,
because it says nothing about whether this replica owns the case (#2667).

``test/architecture/test_received_tree_case_manager_gate.py`` pins which tree
uses each exemption, in both directions (ARCH-18-001, ARCH-18-005).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, ConfigDict

from vultron.primitives import NonEmptyString

__all__ = [
    "ACK_ECHO",
    "OFFER_ROLE",
    "REPLICA_EMIT_EXEMPTIONS",
    "RSH_STATUS",
    "ReplicaEmitExemption",
]


class ReplicaEmitExemption(BaseModel):
    """One recorded decision that a received tree's emit runs ungated.

    Attributes:
        name: Short stable name of the decision.
        reason: Why the emit is correct on every replica.
        covers: Class names of the emit-capable nodes the decision covers;
            any other ungated emitter in the tree is still refused.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonEmptyString
    reason: NonEmptyString
    covers: frozenset[NonEmptyString]


ACK_ECHO: Final = ReplicaEmitExemption(
    name="ack-echo",
    reason=(
        "AckReport forwards the executing actor's own Read(Offer) to the"
        " CASE_MANAGER. The tree skips another actor's ack and skips at the"
        " CASE_MANAGER itself, so the emit speaks only for its author and is"
        " never addressed to itself (BT-17-008, #2667)."
    ),
    covers=frozenset({"EmitAckReportActivity"}),
)

OFFER_ROLE: Final = ReplicaEmitExemption(
    name="offer-role",
    reason=(
        "Offer(CaseParticipantRole) is answered by the actor offered the"
        " role: its Accept or Reject is the executing actor's own answer,"
        " addressed to the offering vendor, not a CASE_MANAGER act"
        " (ADR-0039)."
    ),
    covers=frozenset(
        {
            "AutoAcceptCaseParticipantRoleNode",
            "EmitRejectCaseParticipantRoleNode",
        }
    ),
)

RSH_STATUS: Final = ReplicaEmitExemption(
    name="rsh-status",
    reason=(
        "Add(ParticipantStatus) emits only as the executing actor: the RM gap"
        " note is its own note to the sender (RSH-06-004), and the threat"
        " teardown's terminate request runs in the participant-replica arm"
        " and asks the CASE_MANAGER (RSH-03-004, EP-09-008)."
    ),
    covers=frozenset(
        {"EmitRMGapNoteNode", "SendTerminateEmbargoActivityNode"}
    ),
)

#: Every exemption ``create_receive_activity_tree`` accepts, by name.
REPLICA_EMIT_EXEMPTIONS: Final[Mapping[str, ReplicaEmitExemption]] = (
    MappingProxyType(
        {
            exemption.name: exemption
            for exemption in (ACK_ECHO, OFFER_ROLE, RSH_STATUS)
        }
    )
)
