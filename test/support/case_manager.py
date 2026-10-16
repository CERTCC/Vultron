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

"""A case with a CASE_MANAGER participant, for sender-side trigger tests.

Triggers routed through ``sender_side_bt`` address the CASE_MANAGER alone
(PCR-08-005) and fail fast when the case has none, so their tests need a case
that names one.
"""

from vultron.core.ports.datalayer import DataLayer
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_MANAGER_ID = "https://example.org/actors/case-manager"


def make_case_with_case_manager(
    dl: DataLayer,
    case_manager_id: str = CASE_MANAGER_ID,
) -> as_VulnerabilityCase:
    """Store and return a case whose only participant is its CASE_MANAGER."""
    case = as_VulnerabilityCase(name="Test Case")
    participant = as_CaseParticipant(
        attributed_to=case_manager_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[case_manager_id] = participant.id_
    case.case_participants.append(participant.id_)
    dl.create(case)
    dl.create(participant)
    return case
