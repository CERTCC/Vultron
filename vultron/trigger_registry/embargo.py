"""Embargo-domain trigger registry rows."""

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

from vultron.core.models.use_case_result import ActivityResult
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcProposeEmbargoUseCase,
    SvcRejectEmbargoUseCase,
    SvcTerminateEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
)
from vultron.trigger_registry._entry import (
    GENERAL_TRIGGER_SPECS,
    TriggerEntry,
    TriggerExposure,
)

_COMMON = (
    *GENERAL_TRIGGER_SPECS,
    "TRIG-02-002",
    "TRIG-06-001",
    "TRIG-06-002",
    "TRIG-07-001",
)

ENTRIES: list[TriggerEntry] = [
    TriggerEntry(
        verb="propose-embargo",
        request_model=ProposeEmbargoTriggerRequest,
        use_case_class=SvcProposeEmbargoUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=(*_COMMON, "TRIG-03-003"),
    ),
    TriggerEntry(
        verb="accept-embargo",
        request_model=AcceptEmbargoTriggerRequest,
        use_case_class=SvcAcceptEmbargoUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON,
    ),
    TriggerEntry(
        verb="reject-embargo",
        request_model=RejectEmbargoTriggerRequest,
        use_case_class=SvcRejectEmbargoUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON,
    ),
    TriggerEntry(
        verb="propose-embargo-revision",
        request_model=ProposeEmbargoRevisionTriggerRequest,
        use_case_class=SvcProposeEmbargoRevisionUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=(*_COMMON, "TRIG-03-003"),
    ),
    TriggerEntry(
        verb="terminate-embargo",
        request_model=TerminateEmbargoTriggerRequest,
        use_case_class=SvcTerminateEmbargoUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON,
    ),
]
