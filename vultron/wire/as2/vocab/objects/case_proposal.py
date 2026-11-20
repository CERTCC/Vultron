"""Wire name for the CaseProposal object (CP-01-001).

``as_CaseProposal`` is an alias of the core
:class:`~vultron.core.models.case_proposal.CaseProposal` (ARCH-25-003,
ADR-0211): a ``by_alias`` dump of the core class is its AS2 form.

Spec: ``specs/case-proposal.yaml`` CP-01.
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

from typing import TypeAlias

from vultron.core.models.case_proposal import CaseProposal
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

# The wire name of the one class (ARCH-25-003, ADR-0211)
as_CaseProposal = CaseProposal

# Register core class in WIRE_TYPE_MAP so the parser admits it inline
WIRE_TYPE_MAP["CaseProposal"] = CaseProposal

as_CaseProposalRef: TypeAlias = ActivityStreamRef[CaseProposal]
