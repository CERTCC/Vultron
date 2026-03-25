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
Trigger router for embargo-management behaviors.

Thin wrapper: validates request → calls adapter → returns response.
All domain logic lives in vultron.core.use_cases.triggers.embargo.
"""

from fastapi import APIRouter, Depends, Path, status

from vultron.adapters.driving.fastapi._trigger_adapter import (
    evaluate_embargo_trigger,
    propose_embargo_trigger,
    terminate_embargo_trigger,
)
from vultron.adapters.driving.fastapi.trigger_models import (
    EvaluateEmbargoRequest,
    ProposeEmbargoRequest,
    TerminateEmbargoRequest,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.adapters.driven.datalayer_tinydb import get_datalayer

router = APIRouter(prefix="/actors", tags=["Triggers"])


def _actor_dl(actor_id: str = Path(...)) -> DataLayer:  # noqa: ARG001
    """FastAPI dependency: return the shared DataLayer for trigger use cases.

    Operational data (actors, offers, reports, cases) is stored in the shared
    DataLayer.  The ``actor_id`` path parameter is accepted but unused so that
    ``app.dependency_overrides[_actor_dl]`` works in tests (ADR-0012).
    """
    return get_datalayer()


@router.post(
    "/{actor_id}/trigger/propose-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an embargo proposal.",
    description=(
        "Triggers the propose-embargo behavior for the given actor. "
        "Creates a new EmbargoEvent and emits an EmProposeEmbargoActivity "
        "(Invite(EmbargoEvent)) activity. "
        "EM state transitions: N → P (new proposal) or A → R (revision). "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
    operation_id="actors_trigger_propose_embargo",
)
def trigger_propose_embargo(
    actor_id: str,
    body: ProposeEmbargoRequest,
    dl: DataLayer = Depends(_actor_dl),
) -> dict:
    """
    Trigger the propose-embargo behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return propose_embargo_trigger(
        actor_id, body.case_id, body.note, body.end_time, dl
    )


@router.post(
    "/{actor_id}/trigger/evaluate-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo evaluation (accept a proposal).",
    description=(
        "Triggers the evaluate-embargo behavior for the given actor. "
        "Accepts the current (or specified) embargo proposal by emitting "
        "an EmAcceptEmbargoActivity activity. Activates the embargo on the case "
        "(EM state → ACTIVE). "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
    operation_id="actors_trigger_evaluate_embargo",
)
def trigger_evaluate_embargo(
    actor_id: str,
    body: EvaluateEmbargoRequest,
    dl: DataLayer = Depends(_actor_dl),
) -> dict:
    """
    Trigger the evaluate-embargo (accept) behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return evaluate_embargo_trigger(
        actor_id, body.case_id, body.proposal_id, dl
    )


@router.post(
    "/{actor_id}/trigger/terminate-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo termination.",
    description=(
        "Triggers the terminate-embargo behavior for the given actor. "
        "Announces the end of the active embargo by emitting an "
        "AnnounceEmbargoActivity activity. Updates the case EM state to EXITED "
        "and clears the active embargo. "
        "Returns HTTP 409 if no active embargo exists. "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
    operation_id="actors_trigger_terminate_embargo",
)
def trigger_terminate_embargo(
    actor_id: str,
    body: TerminateEmbargoRequest,
    dl: DataLayer = Depends(_actor_dl),
) -> dict:
    """
    Trigger the terminate-embargo behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return terminate_embargo_trigger(actor_id, body.case_id, dl)
