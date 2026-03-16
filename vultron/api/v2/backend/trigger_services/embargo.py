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
Thin adapter delegates for embargo-level trigger service functions.

Builds domain request models, instantiates core use-case classes, and
translates domain exceptions to FastAPI ``HTTPException`` responses.
"""

from datetime import datetime

from vultron.api.v2.backend.trigger_services._helpers import (
    translate_domain_errors,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.triggers.embargo import (
    SvcEvaluateEmbargoUseCase,
    SvcProposeEmbargoUseCase,
    SvcTerminateEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    EvaluateEmbargoTriggerRequest,
    ProposeEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import VultronError


def svc_propose_embargo(
    actor_id: str,
    case_id: str,
    note: str | None,
    end_time: datetime | None,
    dl: DataLayer,
) -> dict:
    try:
        request = ProposeEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id, note=note, end_time=end_time
        )
        return SvcProposeEmbargoUseCase(dl).execute(request)
    except VultronError as e:
        raise translate_domain_errors(e)


def svc_evaluate_embargo(
    actor_id: str,
    case_id: str,
    proposal_id: str | None,
    dl: DataLayer,
) -> dict:
    try:
        request = EvaluateEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id, proposal_id=proposal_id
        )
        return SvcEvaluateEmbargoUseCase(dl).execute(request)
    except VultronError as e:
        raise translate_domain_errors(e)


def svc_terminate_embargo(actor_id: str, case_id: str, dl: DataLayer) -> dict:
    try:
        request = TerminateEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id
        )
        return SvcTerminateEmbargoUseCase(dl).execute(request)
    except VultronError as e:
        raise translate_domain_errors(e)
