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

from vultron.core.models.events.base import MessageSemantics, VultronEvent


class CreateCaseProposalReceivedEvent(VultronEvent):
    """Case-actor received a Create(CaseProposal) from a vendor actor.

    ``object_`` contains a minimal ``VultronObject`` wrapping the
    ``as_CaseProposal`` wire object; the full proposal is accessible via the
    ``activity.object_`` field when ``include_activity=True``.
    """

    semantic_type: Literal[MessageSemantics.CREATE_CASE_PROPOSAL] = (
        MessageSemantics.CREATE_CASE_PROPOSAL
    )

    @property
    def proposal_id(self) -> str | None:
        """URI of the CaseProposal object."""
        return self.object_id


class AcceptCaseProposalReceivedEvent(VultronEvent):
    """Vendor received an Accept(CaseProposal) from the case-actor service.

    The case-actor accepted the vendor's proposal; a
    Create(VulnerabilityCase) will follow separately (CP-05-003).
    ``object_`` contains a minimal ``VultronObject`` wrapping the
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
    """Vendor received a Reject(CaseProposal) from the case-actor service.

    The case-actor declined the vendor's proposal (CP-05-004).
    ``object_`` contains a minimal ``VultronObject`` wrapping the
    ``as_CaseProposal`` that was rejected.
    """

    semantic_type: Literal[MessageSemantics.REJECT_CASE_PROPOSAL] = (
        MessageSemantics.REJECT_CASE_PROPOSAL
    )

    @property
    def proposal_id(self) -> str | None:
        """URI of the rejected CaseProposal object."""
        return self.object_id
