"""Report-domain trigger registry rows."""

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

from vultron.core.models.use_case_result import ActivityResult, OfferResult
from vultron.core.use_cases.triggers.report import (
    SvcCloseCaseUseCase,
    SvcInvalidateReportUseCase,
    SvcRejectReportUseCase,
    SvcSubmitReportUseCase,
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    CloseReportTriggerRequest,
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.trigger_registry._entry import (
    GENERAL_TRIGGER_SPECS,
    TriggerEntry,
    TriggerExposure,
)

_COMMON = GENERAL_TRIGGER_SPECS + (
    "TRIG-02-001",
    "TRIG-06-001",
    "TRIG-06-002",
    "TRIG-07-001",
)

ENTRIES: list[TriggerEntry] = [
    TriggerEntry(
        verb="validate-report",
        request_model=ValidateReportTriggerRequest,
        use_case_class=SvcValidateReportUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON + ("TRIG-03-003", "TRIG-05-001", "TRIG-05-002"),
    ),
    TriggerEntry(
        verb="invalidate-report",
        request_model=InvalidateReportTriggerRequest,
        use_case_class=SvcInvalidateReportUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON + ("TRIG-03-003",),
    ),
    TriggerEntry(
        verb="reject-report",
        request_model=RejectReportTriggerRequest,
        use_case_class=SvcRejectReportUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON + ("TRIG-03-004",),
    ),
    # ``close-report`` closes the *report* behind an offer; the use case kept
    # its historical name (ADR-0110 § Named exceptions and cleanups).
    TriggerEntry(
        verb="close-report",
        request_model=CloseReportTriggerRequest,
        use_case_class=SvcCloseCaseUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_COMMON + ("TRIG-03-003",),
    ),
    TriggerEntry(
        verb="submit-report",
        request_model=SubmitReportTriggerRequest,
        use_case_class=SvcSubmitReportUseCase,
        result_type=OfferResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        # No ``case_id``/``offer_id`` in its body, so TRIG-03-001 is not its.
        spec_ids=tuple(s for s in _COMMON if s != "TRIG-03-001"),
    ),
]
