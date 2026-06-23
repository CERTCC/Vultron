"""Stub received-side use cases for the CaseProposal protocol.

These stubs satisfy the ``SemanticEntry.use_case_class`` requirement in
``vultron/semantic_registry/case.py`` while full implementations are
tracked in follow-up issues.  Each ``execute()`` raises
``NotImplementedError`` to signal that the logic is not yet in place.
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

from vultron.core.models.events.case_proposal import (
    AcceptCaseProposalReceivedEvent,
    CreateCaseProposalReceivedEvent,
    RejectCaseProposalReceivedEvent,
)
from vultron.core.ports.datalayer import DataLayer


class CreateCaseProposalReceivedUseCase:
    """Handle an inbound Create(CaseProposal) on the case-actor service.

    Full implementation tracked in a follow-up issue (CP-05-001, CP-05-002).
    """

    def __init__(
        self,
        dl: DataLayer,
        request: CreateCaseProposalReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        raise NotImplementedError(
            "CreateCaseProposalReceivedUseCase is not yet implemented."
        )


class AcceptCaseProposalReceivedUseCase:
    """Handle an inbound Accept(CaseProposal) on the vendor actor.

    Full implementation tracked in a follow-up issue (CP-06-001).
    """

    def __init__(
        self,
        dl: DataLayer,
        request: AcceptCaseProposalReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        raise NotImplementedError(
            "AcceptCaseProposalReceivedUseCase is not yet implemented."
        )


class RejectCaseProposalReceivedUseCase:
    """Handle an inbound Reject(CaseProposal) on the vendor actor.

    Full implementation tracked in a follow-up issue (CP-06-002).
    """

    def __init__(
        self,
        dl: DataLayer,
        request: RejectCaseProposalReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        raise NotImplementedError(
            "RejectCaseProposalReceivedUseCase is not yet implemented."
        )
