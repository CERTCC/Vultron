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
    "CASE_PROPOSAL",
    "CASE_STATUS",
    "CLOSE_REPORT_RM_DECLARATION",
    "DEFER_RM_DECLARATION",
    "EMBARGO_INVITE_ANSWER",
    "EMBARGO_INVITE_REFUSAL",
    "EMBARGO_TEARDOWN_ANNOUNCE",
    "ENGAGE_RM_DECLARATION",
    "GENESIS_REJECT_ANNOUNCE",
    "INVALIDATE_REPORT_RM_DECLARATION",
    "OFFER_ROLE",
    "REPLICA_EMIT_EXEMPTIONS",
    "REPORT_CASE_PROPOSAL",
    "RSH_STATUS",
    "VALIDATE_REPORT_RM_DECLARATION",
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

CASE_PROPOSAL: Final = ReplicaEmitExemption(
    name="case-proposal",
    reason=(
        "Create(CaseProposal) is answered by its addressee, which builds the"
        " case it was offered: no case and no CASE_MANAGER exist yet to gate"
        " on (the tree has no commit stage), and the Accept or Reject, the"
        " bootstrap Create(VulnerabilityCase) and the creation-time revision"
        " relay are the executing actor's own acts as the new case's creator"
        " (CP-05-002, ADR-0041, EP-04-011)."
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

CASE_STATUS: Final = ReplicaEmitExemption(
    name="case-status",
    reason=(
        "Add(CaseStatus) emits only as the executing actor: the CSB-18"
        " diagnostic Note is its own note to the sender, skipped on a replica"
        " that awaits the CASE_MANAGER's teardown entry (CSB-18-002,"
        " RSH-03-004), and the threat teardown's terminate request runs in"
        " the participant-replica arm of terminate_embargo_bt and asks the"
        " CASE_MANAGER (RSH-03-001, RSH-03-004, EP-09-008)."
    ),
    covers=frozenset(
        {"PxaEmInvariantDiagnosticNode", "SendTerminateEmbargoActivityNode"}
    ),
)

EMBARGO_INVITE_ANSWER: Final = ReplicaEmitExemption(
    name="embargo-invite-answer",
    reason=(
        "Invite(EmbargoEvent) is answered by its addressee: the Accept or"
        " Reject runs in the participant-replica arm, only when the executing"
        " actor is the Invite's sole addressee, and is that actor's own"
        " answer addressed to the CASE_MANAGER (EP-09-003, EP-09-010,"
        " PCR-08)."
    ),
    covers=frozenset({"SendEmbargoInviteAnswerNode"}),
)

EMBARGO_INVITE_REFUSAL: Final = ReplicaEmitExemption(
    name="embargo-invite-refusal",
    reason=(
        "Once P/X/A is set, a received Invite(EmbargoEvent) or Accept of one"
        " is refused with ER, the executing actor's own Reject of that"
        " Invite: a participant answers only an Invite addressed to it and"
        " sends the ER to the CASE_MANAGER, and the CASE_MANAGER answers the"
        " actor that sent it the Invite or the Accept (EMB-01-002,"
        " EMB-02-002, EP-09-003, EP-09-010, PCR-08-001)."
    ),
    covers=frozenset({"SendEmbargoInviteAnswerNode"}),
)

REPORT_CASE_PROPOSAL: Final = ReplicaEmitExemption(
    name="report-case-proposal",
    reason=(
        "Offer(VulnerabilityReport) makes its receiver the prospective"
        " CASE_OWNER, which proposes a case to the CaseActor service: no"
        " case and no CASE_MANAGER exist yet to gate on (the tree has no"
        " commit stage), and the Create(CaseProposal) is the executing"
        " actor's own act, addressed to the CaseActor (CP-04-001, CP-04-002,"
        " ADR-0041)."
    ),
    covers=frozenset({"ProposeReportCaseToActorNode"}),
)

EMBARGO_TEARDOWN_ANNOUNCE: Final = ReplicaEmitExemption(
    name="embargo-teardown-announce",
    reason=(
        "Not a design decision: kept to preserve behaviour while the received"
        " trees move onto the factory gate. Remove(EmbargoEvent)'s"
        " Announce(EmbargoEvent) is correct at the CASE_MANAGER, but a"
        " participant replica that tears down also re-announces the"
        " CASE_MANAGER's act as its own, which BT-17-008 forbids; #4323"
        " gates it and deletes this exemption."
    ),
    covers=frozenset({"SendAnnounceEmbargoEventNode"}),
)

GENESIS_REJECT_ANNOUNCE: Final = ReplicaEmitExemption(
    name="genesis-reject-announce",
    reason=(
        "The genesis pre-seed Announce(VulnerabilityCase) is the ledger"
        " holder's answer to the rejecting peer, addressed to that peer, and"
        " runs only behind the tree's in-place CheckIsCaseManagerNode,"
        " ahead of the entry replay so the peer can anchor its chain"
        " (SYNC-15-002, ADR-0073). The in-place check masks a failure at the"
        " CASE_MANAGER as a skip (BTND-07-005); #4324 moves it onto a real"
        " gate and deletes this exemption."
    ),
    covers=frozenset({"AnnounceCaseOnGenesisRejectNode"}),
)


def _rm_declaration_exemption(
    name: str, activity: str
) -> ReplicaEmitExemption:
    """The RSH-06-004 gap-note decision for one activity-typed RM tree."""
    return ReplicaEmitExemption(
        name=name,
        reason=(
            f"{activity} declares an RM state for its sender; the RM gap note"
            " is the executing actor's own clarification to that sender,"
            " posted only when the declaration guard flagged an anomaly"
            " (RSH-06-004, RSH-06-006), as in the RSH status tree."
        ),
        covers=frozenset({"EmitRMGapNoteNode"}),
    )


ENGAGE_RM_DECLARATION: Final = _rm_declaration_exemption(
    "engage-rm-declaration", "Join(VulnerabilityCase)"
)

DEFER_RM_DECLARATION: Final = _rm_declaration_exemption(
    "defer-rm-declaration", "Ignore(VulnerabilityCase)"
)

VALIDATE_REPORT_RM_DECLARATION: Final = _rm_declaration_exemption(
    "validate-report-rm-declaration", "Accept(Offer(VulnerabilityReport))"
)

CLOSE_REPORT_RM_DECLARATION: Final = _rm_declaration_exemption(
    "close-report-rm-declaration", "Reject(Offer(VulnerabilityReport))"
)

INVALIDATE_REPORT_RM_DECLARATION: Final = _rm_declaration_exemption(
    "invalidate-report-rm-declaration",
    "TentativeReject(Offer(VulnerabilityReport))",
)

#: Every exemption ``create_receive_activity_tree`` accepts, by name.
REPLICA_EMIT_EXEMPTIONS: Final[Mapping[str, ReplicaEmitExemption]] = (
    MappingProxyType(
        {
            exemption.name: exemption
            for exemption in (
                ACK_ECHO,
                OFFER_ROLE,
                CASE_PROPOSAL,
                RSH_STATUS,
                CASE_STATUS,
                EMBARGO_INVITE_ANSWER,
                EMBARGO_INVITE_REFUSAL,
                REPORT_CASE_PROPOSAL,
                EMBARGO_TEARDOWN_ANNOUNCE,
                GENESIS_REJECT_ANNOUNCE,
                ENGAGE_RM_DECLARATION,
                DEFER_RM_DECLARATION,
                VALIDATE_REPORT_RM_DECLARATION,
                CLOSE_REPORT_RM_DECLARATION,
                INVALIDATE_REPORT_RM_DECLARATION,
            )
        }
    )
)
