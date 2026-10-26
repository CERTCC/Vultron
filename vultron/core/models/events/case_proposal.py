"""Per-semantic inbound domain event types for CaseProposal activities.

Covers the three CaseProposal message flows:
  Create(CaseProposal)  → CREATE_CASE_PROPOSAL
  Accept(CaseProposal)  → ACCEPT_CASE_PROPOSAL
  Reject(CaseProposal)  → REJECT_CASE_PROPOSAL
"""

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

from typing import Literal

from pydantic import Field, field_validator

from vultron.core.models.actor import CoreActor
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.enums.roles import CVDRole
from vultron.primitives import NormalisedActorId


class CreateCaseProposalReceivedEvent(VultronEvent):
    """Case-actor received a Create(CaseProposal) from a report receiver.

    ``object_`` contains a minimal ``CoreObject`` wrapping the
    ``as_CaseProposal`` wire object; the full proposal is accessible via the
    ``activity.object_`` field when ``include_activity=True``.
    """

    semantic_type: Literal[MessageSemantics.CREATE_CASE_PROPOSAL] = (
        MessageSemantics.CREATE_CASE_PROPOSAL
    )
    # The Reporter's proposed terms, read from the Offer the proposal carries
    # inline (CP-01-008, EP-04-004); ``context`` is still the report until the
    # CASE_MANAGER rewrites it at case creation (EP-04-009).
    proposed_embargo: EmbargoEvent | None = None
    # The proposer's actor profile: sent inline as the Create's ``actor``, or
    # named by its id, which the inbox dereferences from the proposer before
    # dispatch and swaps for the fetched profile (CP-01-009, AKM-05-007).  Its
    # ``embargo_policy`` is the CASE_OWNER's actor default for this case and
    # no other (CP-01-010, EP-04-003).  An id still here at dispatch is a
    # fetch that failed, and the tree refuses the proposal for it.
    proposer_profile: CoreActor | NormalisedActorId
    # The CVD roles the proposer states for itself on the proposal (CP-01-011,
    # ADR-0133), from its own ``default_case_roles`` (CP-01-013).  The parse
    # edge has already refused a claim to ``CASE_MANAGER`` (CP-01-012).  Empty
    # seats the proposer as ``CASE_OWNER`` only.
    proposer_case_roles: list[CVDRole] = Field(default_factory=list)

    @field_validator("proposer_case_roles")
    @classmethod
    def _proposer_claims_no_case_manager(
        cls, value: list[CVDRole]
    ) -> list[CVDRole]:
        """Refuse ``CASE_MANAGER`` here too, so core is fail-fast (CP-01-012).

        The parse edge already refuses it; this keeps any core caller that
        builds the event directly from seating a second CASE_MANAGER.
        """
        if CVDRole.CASE_MANAGER in value:
            raise ValueError(
                "proposer_case_roles claims CASE_MANAGER, which only the"
                " CaseActor holds (CP-01-012)"
            )
        return value

    @property
    def proposal_id(self) -> str | None:
        """URI of the CaseProposal object."""
        return self.object_id


class AcceptCaseProposalReceivedEvent(VultronEvent):
    """Report receiver received an Accept(CaseProposal) from the case-actor service.

    The case-actor accepted the report receiver's proposal; a
    Create(VulnerabilityCase) will follow separately (CP-05-003).
    ``object_`` contains a minimal ``CoreObject`` wrapping the
    ``as_CaseProposal`` that was accepted.
    """

    semantic_type: Literal[MessageSemantics.ACCEPT_CASE_PROPOSAL] = (
        MessageSemantics.ACCEPT_CASE_PROPOSAL
    )

    @property
    def proposal_id(self) -> str | None:
        """URI of the accepted CaseProposal object."""
        return self.object_id


class RejectCaseProposalReceivedEvent(VultronEvent):
    """Report receiver received a Reject(CaseProposal) from the case-actor service.

    The case-actor declined the report receiver's proposal (CP-05-004).
    ``object_`` contains a minimal ``CoreObject`` wrapping the
    ``as_CaseProposal`` that was rejected.
    """

    semantic_type: Literal[MessageSemantics.REJECT_CASE_PROPOSAL] = (
        MessageSemantics.REJECT_CASE_PROPOSAL
    )

    @property
    def proposal_id(self) -> str | None:
        """URI of the rejected CaseProposal object."""
        return self.object_id
