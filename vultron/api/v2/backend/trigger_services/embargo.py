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
Domain service functions for embargo-level trigger behaviors.

Each function accepts domain parameters and a DataLayer instance (injected
from the router via Depends).  No HTTP routing or request parsing belongs
here.
"""

import logging
from datetime import datetime

from fastapi import HTTPException, status

from vultron.api.v2.backend.trigger_services._helpers import (
    add_activity_to_outbox,
    find_embargo_proposal,
    not_found,
    resolve_actor,
    resolve_case,
)
from vultron.api.v2.datalayer.abc import DataLayer
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.wire.as2.vocab.activities.embargo import (
    AnnounceEmbargo,
    EmAcceptEmbargo,
    EmProposeEmbargo,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.bt.embargo_management.states import EM

logger = logging.getLogger(__name__)


def svc_propose_embargo(
    actor_id: str,
    case_id: str,
    note: str | None,
    end_time: datetime | None,
    dl: DataLayer,
) -> dict:
    """
    Propose an embargo on a case.

    Creates a new EmbargoEvent and emits EmProposeEmbargo
    (Invite(EmbargoEvent)).  EM state transitions:
    - EM.N → EM.P (new proposal; emits EP)
    - EM.A → EM.R (revision proposal; emits EV)
    - EM.P or EM.R: counter-proposal; no state change

    Returns HTTP 409 if EM state is EXITED.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001,
        TB-03-002, TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    case = resolve_case(case_id, dl)

    em_state = case.current_status.em_state

    if em_state == EM.EXITED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": 409,
                "error": "Conflict",
                "message": (
                    f"Cannot propose embargo: case '{case.as_id}' EM state "
                    f"is EXITED."
                ),
                "activity_id": None,
            },
        )

    embargo_kwargs: dict = {"context": case.as_id}
    if end_time is not None:
        embargo_kwargs["end_time"] = end_time

    embargo = EmbargoEvent(**embargo_kwargs)

    try:
        dl.create(embargo)
    except ValueError:
        logger.warning("EmbargoEvent '%s' already exists", embargo.as_id)

    proposal = EmProposeEmbargo(
        actor=actor_id,
        object=embargo.as_id,
        context=case.as_id,
    )

    try:
        dl.create(proposal)
    except ValueError:
        logger.warning("EmProposeEmbargo '%s' already exists", proposal.as_id)

    if em_state == EM.NO_EMBARGO:
        case.current_status.em_state = EM.PROPOSED
        logger.info(
            "Actor '%s' proposed embargo '%s' on case '%s' (EM N → P)",
            actor_id,
            embargo.as_id,
            case.as_id,
        )
    elif em_state == EM.ACTIVE:
        case.current_status.em_state = EM.REVISE
        logger.info(
            "Actor '%s' proposed embargo revision '%s' on case '%s' (EM A → R)",
            actor_id,
            embargo.as_id,
            case.as_id,
        )
    else:
        logger.info(
            "Actor '%s' counter-proposed embargo '%s' on case '%s' (EM %s, no state change)",
            actor_id,
            embargo.as_id,
            case.as_id,
            em_state,
        )

    case.proposed_embargoes.append(embargo.as_id)
    dl.update(case.as_id, object_to_record(case))

    add_activity_to_outbox(actor_id, proposal.as_id, dl)

    activity = proposal.model_dump(by_alias=True, exclude_none=True)
    return {"activity": activity}


def svc_evaluate_embargo(
    actor_id: str,
    case_id: str,
    proposal_id: str | None,
    dl: DataLayer,
) -> dict:
    """
    Accept an embargo proposal (evaluate-embargo).

    Emits EmAcceptEmbargo (Accept(EmProposeEmbargo)), activates the embargo
    on the case (EM → ACTIVE), and adds to actor outbox.

    If proposal_id is None, the first pending EmProposeEmbargo for the case
    is used.  Returns 404 if no proposal is found.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001,
        TB-03-002, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    case = resolve_case(case_id, dl)

    if proposal_id:
        proposal_raw = dl.read(proposal_id)
        if proposal_raw is None:
            raise not_found("EmbargoProposal", proposal_id)
        proposal = proposal_raw
    else:
        proposal = find_embargo_proposal(case.as_id, dl)
        if proposal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": 404,
                    "error": "NotFound",
                    "message": (
                        f"No pending embargo proposal found for case "
                        f"'{case.as_id}'."
                    ),
                    "activity_id": None,
                },
            )

    if str(getattr(proposal, "as_type", "")) != "Invite":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "status": 422,
                "error": "ValidationError",
                "message": (
                    f"Expected an Invite (embargo proposal), got "
                    f"{type(proposal).__name__}."
                ),
                "activity_id": None,
            },
        )

    embargo_ref = getattr(proposal, "as_object", None)
    embargo_id = (
        embargo_ref
        if isinstance(embargo_ref, str)
        else getattr(embargo_ref, "as_id", None)
    )
    if not embargo_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "status": 422,
                "error": "ValidationError",
                "message": "Proposal is missing an embargo event reference.",
                "activity_id": None,
            },
        )
    embargo = dl.read(embargo_id)
    if embargo is None or str(getattr(embargo, "as_type", "")) != "Event":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "status": 422,
                "error": "ValidationError",
                "message": f"Could not resolve EmbargoEvent '{embargo_id}'.",
                "activity_id": None,
            },
        )

    accept = EmAcceptEmbargo(
        actor=actor_id,
        object=proposal.as_id,
        context=case.as_id,
    )

    try:
        dl.create(accept)
    except ValueError:
        logger.warning("EmAcceptEmbargo '%s' already exists", accept.as_id)

    case.set_embargo(embargo_id)
    dl.update(case.as_id, object_to_record(case))

    add_activity_to_outbox(actor_id, accept.as_id, dl)

    logger.info(
        "Actor '%s' accepted embargo proposal '%s'; activated embargo '%s' "
        "on case '%s' (EM → ACTIVE)",
        actor_id,
        proposal.as_id,
        embargo_id,
        case.as_id,
    )

    activity = accept.model_dump(by_alias=True, exclude_none=True)
    return {"activity": activity}


def svc_terminate_embargo(actor_id: str, case_id: str, dl: DataLayer) -> dict:
    """
    Terminate the active embargo on a case.

    Emits AnnounceEmbargo (ET message), sets case EM state to EXITED, clears
    the active embargo, and adds to actor outbox.  Returns 409 if the case
    has no active embargo.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001,
        TB-03-002, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    case = resolve_case(case_id, dl)

    if case.active_embargo is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": 409,
                "error": "Conflict",
                "message": (
                    f"Case '{case.as_id}' has no active embargo to terminate."
                ),
                "activity_id": None,
            },
        )

    embargo_id = (
        case.active_embargo
        if isinstance(case.active_embargo, str)
        else case.active_embargo.as_id
    )

    announce = AnnounceEmbargo(
        actor=actor_id,
        object=embargo_id,
        context=case.as_id,
    )

    try:
        dl.create(announce)
    except ValueError:
        logger.warning("AnnounceEmbargo '%s' already exists", announce.as_id)

    case.current_status.em_state = EM.EXITED
    case.active_embargo = None
    dl.update(case.as_id, object_to_record(case))

    add_activity_to_outbox(actor_id, announce.as_id, dl)

    logger.info(
        "Actor '%s' terminated embargo '%s' on case '%s' (EM → EXITED)",
        actor_id,
        embargo_id,
        case.as_id,
    )

    activity = announce.model_dump(by_alias=True, exclude_none=True)
    return {"activity": activity}
