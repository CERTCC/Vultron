"""Participant-status trigger registry rows."""

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

from vultron.core.models.use_case_result import StatusResult
from vultron.core.use_cases.triggers.case import (
    SvcAddOnBehalfStatusUseCase,
    SvcAddParticipantStatusUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AddOnBehalfStatusTriggerRequest,
    AddParticipantStatusTriggerRequest,
)
from vultron.trigger_registry._entry import (
    GENERAL_TRIGGER_SPECS,
    TriggerEntry,
    TriggerExposure,
)

#: The three demo ``notify-*`` verbs puppeteer a self-report the actor's own
#: BT would make (TRIG-08-002); each builds an
#: ``AddParticipantStatusTriggerRequest`` with the state its verb names.
_NOTIFY_SPECS = (
    "TRIG-02-003",
    "TRIG-06-001",
    "TRIG-09-001",
    "TRIG-09-004",
    "DEMOMA-07-001",
)

ENTRIES: list[TriggerEntry] = [
    TriggerEntry(
        verb="notify-fix-ready",
        request_model=AddParticipantStatusTriggerRequest,
        use_case_class=SvcAddParticipantStatusUseCase,
        result_type=StatusResult,
        exposure=TriggerExposure.DEMO_ONLY,
        bt_backed=True,
        spec_ids=_NOTIFY_SPECS,
    ),
    TriggerEntry(
        verb="notify-fix-deployed",
        request_model=AddParticipantStatusTriggerRequest,
        use_case_class=SvcAddParticipantStatusUseCase,
        result_type=StatusResult,
        exposure=TriggerExposure.DEMO_ONLY,
        bt_backed=True,
        spec_ids=_NOTIFY_SPECS,
    ),
    TriggerEntry(
        verb="notify-published",
        request_model=AddParticipantStatusTriggerRequest,
        use_case_class=SvcAddParticipantStatusUseCase,
        result_type=StatusResult,
        exposure=TriggerExposure.DEMO_ONLY,
        bt_backed=True,
        spec_ids=_NOTIFY_SPECS,
    ),
    # A coordinator recording a vendor's evidenced awareness is an intentional
    # actor decision (TRIG-08-002), so the on-behalf verb is general-purpose.
    TriggerEntry(
        verb="add-on-behalf-status",
        request_model=AddOnBehalfStatusTriggerRequest,
        use_case_class=SvcAddOnBehalfStatusUseCase,
        result_type=StatusResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        # Its body carries ids, not an activity, so TRIG-04-001 is not its.
        spec_ids=(
            *tuple(s for s in GENERAL_TRIGGER_SPECS if s != "TRIG-04-001"),
            "TRIG-06-001",
            "TRIG-06-002",
            "TRIG-07-001",
            "PRM-06-003",
            "PRM-06-004",
            "PRM-06-005",
        ),
    ),
]
