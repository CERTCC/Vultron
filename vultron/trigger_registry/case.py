"""Case-management trigger registry rows."""

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

from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    StatusResult,
)
from vultron.core.use_cases.triggers.case import (
    SvcAddObjectToCaseUseCase,
    SvcAddReportToCaseUseCase,
    SvcCreateCaseUseCase,
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
    SvcLeaveCaseUseCase,
    SvcSetStubSummaryUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AddObjectToCaseTriggerRequest,
    AddReportToCaseTriggerRequest,
    CreateCaseTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
    LeaveCaseTriggerRequest,
    SetStubSummaryTriggerRequest,
)
from vultron.trigger_registry._entry import (
    GENERAL_TRIGGER_SPECS,
    TriggerEntry,
    TriggerExposure,
)

_COMMON = (*GENERAL_TRIGGER_SPECS, "TRIG-02-004")
_ACTOR_SCOPED = ("TRIG-06-001", "TRIG-06-002")

ENTRIES: list[TriggerEntry] = [
    TriggerEntry(
        verb="engage-case",
        request_model=EngageCaseTriggerRequest,
        use_case_class=SvcEngageCaseUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON + _ACTOR_SCOPED + ("TRIG-07-001",),
    ),
    TriggerEntry(
        verb="defer-case",
        request_model=DeferCaseTriggerRequest,
        use_case_class=SvcDeferCaseUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON + _ACTOR_SCOPED + ("TRIG-07-001",),
    ),
    TriggerEntry(
        verb="add-object-to-case",
        request_model=AddObjectToCaseTriggerRequest,
        use_case_class=SvcAddObjectToCaseUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON + _ACTOR_SCOPED + ("TRIG-10-001",),
    ),
    TriggerEntry(
        verb="create-case",
        request_model=CreateCaseTriggerRequest,
        use_case_class=SvcCreateCaseUseCase,
        result_type=CaseResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON,
    ),
    TriggerEntry(
        verb="add-report-to-case",
        request_model=AddReportToCaseTriggerRequest,
        use_case_class=SvcAddReportToCaseUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=(*_COMMON, "TRIG-10-002"),
    ),
    # The demo ``close-case`` verb sends ``Leave(VulnerabilityCase)`` — the
    # canonical RM closure path (ADR-0050) — so its use case is the leave one.
    TriggerEntry(
        verb="close-case",
        request_model=LeaveCaseTriggerRequest,
        use_case_class=SvcLeaveCaseUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.DEMO_ONLY,
        bt_backed=True,
        spec_ids=(
            "TRIG-02-006",
            "TRIG-06-001",
            "TRIG-09-001",
            "TRIG-09-004",
            "DEMOMA-07-001",
        ),
    ),
    # The demo ``set-stub-summary`` verb writes stub_summary on the actor's
    # local DataLayer copy of the case so a subsequent invite-actor-to-case
    # trigger can build the stub Invite (CM-17-010, MV-10-001, #4165).
    TriggerEntry(
        verb="set-stub-summary",
        request_model=SetStubSummaryTriggerRequest,
        use_case_class=SvcSetStubSummaryUseCase,
        result_type=StatusResult,
        exposure=TriggerExposure.DEMO_ONLY,
        bt_backed=True,
        spec_ids=(
            "CM-17-010",
            "MV-10-001",
            "TRIG-09-001",
            "TRIG-09-004",
        ),
    ),
]
