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
list and no entry goes wholly stale.
The factory does not refuse a single ``covers`` class the tree no longer
emits while another covered class remains, so drop a class from ``covers`` in
the change that removes it from its tree.

Each exemption records the decision for one tree: why its emit speaks for the
executing actor, or is addressed only to an actor other than itself.
A sender check added to a tree without an exemption is not enough on its own,
because it says nothing about whether this replica owns the case (#2667).

**An exemption is a waiver of BT-17-008, never a satisfaction of it.**  The
requirement gives an emit two guards and no third: the CASE_MANAGER gate, or a
check that the executing actor is the actor the emit speaks for.  So this
registry holds only the emits that can carry neither, and every entry says
which of the two it lacks and why.  An emit a tree *can* put behind either one
loses its entry in the same change: a manager-only path declaration bounds it
(HP-01-038), and a
:class:`~vultron.core.behaviors.speaks_for_executing_actor.SpeaksForExecutingActor`
leaf ahead of it is the second arm, which
:func:`~vultron.core.behaviors.case.receive_stages.effects.ungated_emitters`
reads.  That is how the role-offer answer, the embargo Invite answer and its
P/X/A refusal stopped needing entries: each already had the leaf guard, and
the walk could not see it.

The registry itself is kept, not retired with them.  Its refusal of an
unregistered or uncovered exemption is what makes a bare emit fail at
construction rather than run on every replica, so deleting the registry would
delete that enforcement.  ``AddresseeExemption`` / ``ADDRESSEE_EXEMPTIONS`` is
the same shape, kept for the same reason (HP-01-005).

``test/architecture/test_received_tree_case_manager_gate.py`` pins which tree
uses each exemption, in both directions (ARCH-18-001, ARCH-18-005).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, ConfigDict

from vultron.primitives import NonEmptyString

__all__ = [
    "CASE_PROPOSAL",
    "EMBARGO_INVITE_FAULT",
    "REPLICA_EMIT_EXEMPTIONS",
    "REPORT_CASE_PROPOSAL",
    "REPORTER_INTRODUCTION",
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


CASE_PROPOSAL: Final = ReplicaEmitExemption(
    name="case-proposal",
    reason=(
        "Create(CaseProposal) is answered by its addressee, which builds the"
        " case it was offered: no case and no CASE_MANAGER exist yet to gate"
        " on (the tree has no commit stage), and the Accept or Reject, the"
        " bootstrap Create(VulnerabilityCase) and the creation-time revision"
        " relay are the executing actor's own acts as the new case's creator"
        " (CP-05-002, ADR-0041, EP-04-011).  Neither arm of BT-17-008 is"
        " open: there is no CASE_MANAGER to gate on, and a no-case path"
        " declaration says only that this receiver holds no replica, which"
        " pins no identity, so declaring one would weaken the requirement"
        " rather than meet it (HP-01-038, HP-01-041)."
    ),
    covers=frozenset(
        {
            "EmitAcceptCaseProposalNode",
            "EmitCreateVulnerabilityCaseNode",
            "EmitRejectCaseProposalNode",
            "RelayCreationTimeRevisionNode",
        }
    ),
)

EMBARGO_INVITE_FAULT: Final = ReplicaEmitExemption(
    name="embargo-invite-fault",
    reason=(
        "A received Invite(EmbargoEvent) that names no embargo, or not"
        " exactly one to recipient, is received but not understood: the"
        " receiver answers the Invite's sender with Create(ProcessingFault),"
        " its own act, whose id derives from the Invite and the failure"
        " class (MSM-05-001, EP-09-010, ID-04-004).  An Invite to nobody"
        " names no addressee and may reach a store that is not the case's"
        " CASE_MANAGER, so there is no gate to put it under, and the tree"
        " declares no paths to bound it with (HP-01-038).  The second arm is"
        " vacuous here: the fault unconditionally speaks for whichever actor"
        " is executing, and a tautology is not a guard."
    ),
    covers=frozenset({"EmitEmbargoInviteFaultNode"}),
)

REPORT_CASE_PROPOSAL: Final = ReplicaEmitExemption(
    name="report-case-proposal",
    reason=(
        "Offer(VulnerabilityReport) makes its receiver the prospective"
        " CASE_OWNER, which proposes a case to the CaseActor service: no"
        " case and no CASE_MANAGER exist yet to gate on (the tree has no"
        " commit stage), and the Create(CaseProposal) is the executing"
        " actor's own act, addressed to the CaseActor (CP-04-001, CP-04-002,"
        " ADR-0041).  As for Create(CaseProposal), there is no CASE_MANAGER"
        " to gate on and a no-case declaration would pin no identity"
        " (HP-01-038)."
    ),
    covers=frozenset({"ProposeReportCaseToActorNode"}),
)


REPORTER_INTRODUCTION: Final = ReplicaEmitExemption(
    name="reporter-introduction",
    reason=(
        "A trusted Create(VulnerabilityCase) seeds a replica, and the case"
        " owner that receives it is the report receiver, which introduces the"
        " CASE_MANAGER to the reporter with its own Create(VulnerabilityCase)"
        " (CBT-01-001, CM-12-003, ADR-0132).  The introduction is the"
        " executing actor's own act, addressed to the actor that sent it the"
        " report: it answers that report outside any case traffic the"
        " CASE_MANAGER routes (PCR-08-001), and the reporter has no anchor"
        " for the CASE_MANAGER until it arrives (CBT-01-005).  The receiving"
        " replica is never the case's CASE_MANAGER on this path, so there is"
        " no gate to put it under, and the path declaration that admits it"
        " names a receiver rather than the reporter the introduction speaks"
        " for (HP-01-038)."
    ),
    covers=frozenset({"IntroduceCaseManagerToReporterNode"}),
)


#: Every exemption ``create_receive_activity_tree`` accepts, by name.
#:
#: The RM-declaration gap-note exemptions (engage, defer, and the three report
#: verdicts) and ``rsh-status`` were retired by #3814: once each tree's state
#: write moved under the CASE_MANAGER gate (RSH-08-003), the whole ordered
#: effect pipeline — gap note and, for add_participant_status, the adoption
#: emit and threat teardown — moved with it, so nothing in those trees emits
#: outside the gate.  ``case-status`` was retired by #4851: add_case_status
#: now runs only at a participant replica, from the CASE_MANAGER (RSH-04-005),
#: and has no effects to exempt, so its threat-ask went with its teardown.
#: ``offer-role``, ``embargo-invite-answer`` and ``embargo-invite-refusal``
#: were retired by #5044: each of those emits already sat behind a leaf that
#: admits the executing actor alone, so each is BT-17-008's second arm and
#: the waiver recorded nothing the tree did not already state.
REPLICA_EMIT_EXEMPTIONS: Final[Mapping[str, ReplicaEmitExemption]] = (
    MappingProxyType(
        {
            exemption.name: exemption
            for exemption in (
                CASE_PROPOSAL,
                EMBARGO_INVITE_FAULT,
                REPORT_CASE_PROPOSAL,
                REPORTER_INTRODUCTION,
            )
        }
    )
)
