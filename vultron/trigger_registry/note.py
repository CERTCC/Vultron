"""Note-domain trigger registry rows."""

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

from vultron.core.models.use_case_result import NoteResult
from vultron.core.use_cases.triggers.note import SvcAddNoteToCaseUseCase
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
)
from vultron.trigger_registry._entry import TriggerEntry, TriggerExposure

ENTRIES: list[TriggerEntry] = [
    TriggerEntry(
        verb="add-note-to-case",
        request_model=AddNoteToCaseTriggerRequest,
        use_case_class=SvcAddNoteToCaseUseCase,
        result_type=NoteResult,
        exposure=TriggerExposure.DEMO_ONLY,
        bt_backed=True,
        spec_ids=(
            "TRIG-01-002",
            "TRIG-02-006",
            "TRIG-03-001",
            "TRIG-03-002",
            "TRIG-04-001",
            "TRIG-06-001",
            "TRIG-06-002",
            "TRIG-09-001",
            "TRIG-09-004",
            "TRIG-10-003",
            "HTTP-03-005",
        ),
    ),
]
