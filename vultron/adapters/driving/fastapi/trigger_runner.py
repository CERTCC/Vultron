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

"""The one body every trigger route shares (ADR-0110 § Routes).

A trigger route validates its HTTP body, adds the path's ``actor_id`` to make
the core request, and hands it to :func:`run_trigger`, which:

1. calls the :class:`~vultron.core.ports.trigger_dispatcher.TriggerDispatcher`
   under ``domain_error_translation()``, so a domain failure becomes the
   structured 404/409/422 the trigger API promises (TRIG-01-003);
2. schedules the outbox flush as a background task **only after**
   ``trigger()`` has returned (TRIG-07-001), so the 202 does not wait on
   delivery (TRIG-01-004) and nothing is flushed for a trigger that raised;
3. drains the outbox the trigger actually wrote to: the *emitting* actor's
   when the result names one (:class:`EmittingResult` — a delegated emit is
   queued in the CASE_MANAGER's outbox, CM-24-001), otherwise the requesting
   actor's (:func:`emitting_outbox`);
4. returns the verb's typed result — the request binds it, so a route's
   ``response_model`` and its return annotation are the same class
   (UCORG-05-006).

The route keeps its own ``Depends(get_trigger_dl)`` → ``Depends(get_actor_dl)``
chain and passes the resolved store in: a helper that called ``get_actor_dl``
itself would bypass ``app.dependency_overrides`` (TRIG-06-002).

The first consumers are ``add-on-behalf-status`` and the demo
``sync-log-entry``; the remaining routes move here when ``TriggerService`` is
retired.
"""

from fastapi import BackgroundTasks

from vultron.adapters.driving.fastapi.deps import outbox_store
from vultron.adapters.driving.fastapi.errors import domain_error_translation
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.core.behaviors.store_scope import store_for_actor
from vultron.core.models.use_case_result import EmittingResult
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.use_cases.triggers.requests import ResultT_co, TriggerRequest


def emitting_outbox(
    emitting_actor_id: str,
    actor_id: str,
    dl: DataLayer,
    actor_dl: DataLayer,
) -> tuple[str, DataLayer]:
    """Return the ``(actor_id, store)`` whose outbox the trigger just wrote to.

    A delegated emit (CM-24-001, PCR-08-007) is authored as the CaseActor and
    queued in the *CaseActor's* outbox, not the requesting actor's, so the
    drain scheduled after the trigger has to target that queue.  Draining the
    requesting actor's queue instead leaves the row until the CaseActor next
    happens to drain — in CI run 36643399281 an ownership-transfer Offer sat
    unpopped for 111 s while the 90 s gate on its forwarding expired (#3602;
    invite-actor-to-case had the same fault fixed in #2484).

    Unless the CaseActor is on another container, which it is after a handoff
    (CP-08-003).  A node cannot reach a foreign authority's store, so
    ``BTBridge._store_for_actor`` keeps the emit in the requesting actor's own
    store and the activity is queued *there*; resolving the queue any other way
    would drain an empty store minted for a foreign slug and deliver nothing.
    ``store_for_actor`` is the same guard the bridge applies, so the two cannot
    disagree about which queue holds the activity.

    Args:
        emitting_actor_id: ``result.emitting_actor_id`` — who the activity
            was emitted as.
        actor_id: The path's ``actor_id``, the requesting actor.
        dl: The requesting actor's store, used to reach the emitter's.
        actor_dl: The store to drain when the requester is the emitter (the
            same object as *dl* unless a test overrides the two seams apart).
    """
    if emitting_actor_id == actor_id:
        return actor_id, actor_dl
    emitting_dl = store_for_actor(
        dl, emitting_actor_id, require_same_authority=True
    )
    if emitting_dl is None:
        return actor_id, actor_dl
    return emitting_actor_id, emitting_dl


def run_trigger(
    request: TriggerRequest[ResultT_co],
    *,
    dispatcher: TriggerDispatcher,
    dl: DataLayer,
    background_tasks: BackgroundTasks,
) -> ResultT_co:
    """Run *request* through *dispatcher*, then queue the emitter's outbox flush.

    Args:
        request: The core request the route built: its validated body plus
            the path's ``actor_id``.
        dispatcher: The driving port, from ``Depends(get_trigger_dispatcher)``.
        dl: The addressed actor's store, from ``Depends(get_trigger_dl)``;
            the store the use case runs against, and the outbox flushed unless
            the result names another emitting actor this node hosts.
        background_tasks: The route's ``BackgroundTasks``; the flush is added
            to it after ``trigger()`` returns and not at all when it raises.

    Returns:
        The verb's ``TriggerResult`` subtype, as bound by *request*.

    Raises:
        HTTPException: A translated domain error (TRIG-01-003).
        VultronError: A domain error ``domain_error_translation()`` has no
            HTTP mapping for; it propagates for the route to decide.
    """
    with domain_error_translation():
        result = dispatcher.trigger(request, outbox_store(dl))
    flush_id, flush_dl = request.actor_id, dl
    if isinstance(result, EmittingResult):
        flush_id, flush_dl = emitting_outbox(
            result.emitting_actor_id, request.actor_id, dl, dl
        )
    background_tasks.add_task(outbox_handler, flush_id, flush_dl)
    return result


__all__ = ["emitting_outbox", "run_trigger"]
