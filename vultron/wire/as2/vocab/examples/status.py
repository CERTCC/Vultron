#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.wire.as2.vocab.activities.case import (
    AddStatusToCaseActivity,
    CreateCaseStatusActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddStatusToParticipantActivity,
    CreateStatusForParticipantActivity,
)
from vultron.wire.as2.vocab.examples._base import case, vendor
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_pxa, CS_vfd


def case_status() -> CaseStatus:
    status = CaseStatus(
        as_id="https://vultron.example/cases/1/status/1",
        context="https://vultron.example/cases/1",
        em_state=EM.EMBARGO_MANAGEMENT_NONE,
        pxa_state=CS_pxa.pxa,
    )
    return status


def create_case_status():
    actor = vendor()
    status = case_status()
    _case = case()

    activity = CreateCaseStatusActivity(
        actor=actor.as_id,
        as_object=status,
        context=_case.as_id,
    )
    return activity


def add_status_to_case() -> AddStatusToCaseActivity:
    _vendor = vendor()
    _case = case()
    _status = case_status()
    activity = AddStatusToCaseActivity(
        actor=_vendor.as_id,
        as_object=_status,
        target=_case.as_id,
    )
    return activity


def participant_status() -> ParticipantStatus:
    status = ParticipantStatus(
        as_id="https://vultron.example/cases/1/participants/vendor/status/1",
        context="https://vultron.example/cases/1/participants/vendor",
        attributed_to="https://vultron.example/organizations/vendor",
        rm_state=RM.RECEIVED,
        vfd_state=CS_vfd.Vfd,
        case_status=case_status(),
    )
    return status


def create_participant_status() -> CreateStatusForParticipantActivity:
    pstatus = participant_status()
    _vendor = vendor()

    activity = CreateStatusForParticipantActivity(
        actor=_vendor.as_id,
        as_object=pstatus,
    )
    return activity


def add_status_to_participant() -> AddStatusToParticipantActivity:
    _vendor = vendor()
    pstatus = participant_status()

    activity = AddStatusToParticipantActivity(
        actor=_vendor.as_id,
        as_object=pstatus,
        target="https://vultron.example/cases/1/participants/vendor",
    )
    return activity
