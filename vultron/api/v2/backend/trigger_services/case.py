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

"""
Thin adapter delegates for case-level trigger service functions.

Builds domain request models, instantiates core use-case classes, and
translates domain exceptions to FastAPI ``HTTPException`` responses.
"""

from vultron.api.v2.backend.trigger_services._helpers import (
    domain_error_translation,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.triggers.case import (
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
)


def engage_case_trigger(actor_id: str, case_id: str, dl: DataLayer) -> dict:
    with domain_error_translation():
        request = EngageCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcEngageCaseUseCase(dl, request).execute()


def defer_case_trigger(actor_id: str, case_id: str, dl: DataLayer) -> dict:
    with domain_error_translation():
        request = DeferCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcDeferCaseUseCase(dl, request).execute()
