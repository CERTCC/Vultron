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

"""Received-side use cases for the CaseProposal protocol.

Three use cases covering the full CP message flow (ADR-0023):

- ``CreateCaseProposalReceivedUseCase`` — case-actor service receives
  ``Create(CaseProposal)`` from a report receiver; creates a VulnerabilityCase
  and emits ``Accept(CaseProposal)`` + ``Create(VulnerabilityCase)``
  (CP-05-001 through CP-05-004).

- ``AcceptCaseProposalReceivedUseCase`` — report receiver receives
  ``Accept(CaseProposal)`` from the case-actor service; records the
  case-actor URI in the receiver's VultronReportCaseLink (CP-06-001,
  CP-06-003).

- ``RejectCaseProposalReceivedUseCase`` — report receiver receives
  ``Reject(CaseProposal)`` from the case-actor service; logs the
  rejection so the receiver can surface it (CP-06-002, CP-06-004).
"""

from vultron.core.use_cases.received.case_proposal.answer import (
    AcceptCaseProposalReceivedUseCase,
    RejectCaseProposalReceivedUseCase,
)
from vultron.core.use_cases.received.case_proposal.create import (
    CreateCaseProposalReceivedUseCase,
)

__all__ = [
    "AcceptCaseProposalReceivedUseCase",
    "CreateCaseProposalReceivedUseCase",
    "RejectCaseProposalReceivedUseCase",
]
