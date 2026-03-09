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
Domain service functions for case-level trigger behaviors.

Each function accepts domain parameters and a DataLayer instance (injected
from the router via Depends).  No HTTP routing or request parsing belongs
here.
"""

import logging

from vultron.api.v2.backend.trigger_services._helpers import (
    add_activity_to_outbox,
    resolve_actor,
    resolve_case,
    update_participant_rm_state,
)
from vultron.api.v2.datalayer.abc import DataLayer
from vultron.as_vocab.activities.case import RmDeferCase, RmEngageCase
from vultron.bt.report_management.states import RM

logger = logging.getLogger(__name__)


def svc_engage_case(actor_id: str, case_id: str, dl: DataLayer) -> dict:
    """
    Engage a case (RM → ACCEPTED).

    Emits RmEngageCase (Join(VulnerabilityCase)), updates the actor's own
    CaseParticipant RM state, adds to actor outbox, and returns
    {"activity": {...}}.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001,
        TB-03-002, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    case = resolve_case(case_id, dl)

    engage_activity = RmEngageCase(
        actor=actor_id,
        object=case.as_id,
    )

    try:
        dl.create(engage_activity)
    except ValueError:
        logger.warning(
            "EngageCase activity '%s' already exists", engage_activity.as_id
        )

    update_participant_rm_state(case.as_id, actor_id, RM.ACCEPTED, dl)

    add_activity_to_outbox(actor_id, engage_activity.as_id, dl)

    logger.info(
        "Actor '%s' engaged case '%s' (RM → ACCEPTED)",
        actor_id,
        case.as_id,
    )

    activity = engage_activity.model_dump(by_alias=True, exclude_none=True)
    return {"activity": activity}


def svc_defer_case(actor_id: str, case_id: str, dl: DataLayer) -> dict:
    """
    Defer a case (RM → DEFERRED).

    Emits RmDeferCase (Ignore(VulnerabilityCase)), updates the actor's own
    CaseParticipant RM state, adds to actor outbox, and returns
    {"activity": {...}}.

    Implements: TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001,
        TB-03-002, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    actor = resolve_actor(actor_id, dl)
    actor_id = actor.as_id

    case = resolve_case(case_id, dl)

    defer_activity = RmDeferCase(
        actor=actor_id,
        object=case.as_id,
    )

    try:
        dl.create(defer_activity)
    except ValueError:
        logger.warning(
            "DeferCase activity '%s' already exists", defer_activity.as_id
        )

    update_participant_rm_state(case.as_id, actor_id, RM.DEFERRED, dl)

    add_activity_to_outbox(actor_id, defer_activity.as_id, dl)

    logger.info(
        "Actor '%s' deferred case '%s' (RM → DEFERRED)",
        actor_id,
        case.as_id,
    )

    activity = defer_activity.model_dump(by_alias=True, exclude_none=True)
    return {"activity": activity}
