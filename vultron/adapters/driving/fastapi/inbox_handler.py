#!/usr/bin/env python
"""Vultron Actor Inbox Handler.

Dispatcher management, dispatch-prep helpers, and the processing-fault
emitter.  The production inbox loop, with its bounded retry and dead letter
(IE-06-004), is
:func:`~vultron.adapters.driving.fastapi.inbox_orchestration.run_inbox_pipeline`.
Port-factory wiring and pending-queue management are provided by the
focused submodules:

- :mod:`~vultron.adapters.driving.fastapi.inbox_port_factories` —
  port factory functions and semantics-set constants
- :mod:`~vultron.adapters.driving.fastapi.inbox_pending_queue` —
  pre-bootstrap pending case queue helpers
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can
#    Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol
#  Prototype is licensed under a MIT (SEI)-style license, please see
#  LICENSE.md distributed with this Software or contact
#  permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States
#  Government (see Acknowledgments file). This program may include
#  and/or can make use of certain third party source code, object code,
#  documentation and other files ("Third Party Software"). See
#  LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered
#  in the U.S. Patent and Trademark Office by Carnegie Mellon University

import logging
from typing import cast

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)

# Re-export port factories and semantics sets so existing callers that
# import them from this module continue to work (backward compat).
from vultron.adapters.driving.fastapi import inbox_port_factories
from vultron.adapters.driving.fastapi.inbox_port_factories import (
    _CASE_PROPOSAL_SEMANTICS,
    _CLOSE_CASE_SEMANTICS,
    _EMBARGO_INVITE_SEMANTICS,
    _LEDGER_REPLAY_SEMANTICS,
    _STATUS_AUTH_TRIGGER_SEMANTICS,
    _SUBMIT_REPORT_SEMANTICS,
    _case_proposal_port_factory,
    _inbox_replay_port_factory,
    _status_auth_trigger_port_factory,
    _trigger_activity_with_actor_config_port_factory,
)
from vultron.adapters.driving.fastapi.startup_slot import StartupSlot
from vultron.core.dispatcher import get_dispatcher
from vultron.core.models.events import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.semantic_registry import (
    extract_event,
    use_case_map as _use_case_map,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def prepare_for_dispatch(activity: as_Activity) -> VultronEvent:
    """Extract domain event from an AS2 activity, ready for dispatch.

    The local actor's configured RSVP windows govern an inbound embargo
    invite (EP-07-001, EP-07-002); when no ``ActorConfig`` loads, the
    protocol defaults apply.
    """
    logger.debug(
        "Preparing activity '%s' of type '%s' for dispatch.",
        activity.id_,
        activity.type_,
    )
    actor_config = inbox_port_factories._resolve_actor_config()
    event = extract_event(
        activity,
        min_rsvp_window=(
            actor_config.min_rsvp_window if actor_config else None
        ),
        default_rsvp_window=(
            actor_config.default_rsvp_window if actor_config else None
        ),
    )
    logger.debug(
        "Prepared event with semantics '%s' for activity '%s'",
        event.semantic_type,
        event.activity_id,
    )
    return event


#: The module-level dispatcher, installed by :func:`init_dispatcher`.
_DISPATCHER_SLOT: StartupSlot[ActivityDispatcher] = StartupSlot()


def make_dispatcher() -> ActivityDispatcher:
    """Create and return a new inbox dispatcher without mutating any global.

    Use this in :func:`create_app` lifespans to build a per-app dispatcher
    that is stored on ``app.state.dispatcher`` instead of the module-level
    ``_DISPATCHER_SLOT``.  Production code (``app_v2``) continues to call
    :func:`init_dispatcher` so the global is set for backward-compatible
    callers such as the CLI.
    """
    # Guard: all semantics sets must be mutually disjoint.  An overlap
    # would cause a silent dict.update() overwrite — exactly the class of bug
    # that #628 introduced — so fail fast with an actionable message.
    _all_sets = (
        _SUBMIT_REPORT_SEMANTICS,
        _CASE_PROPOSAL_SEMANTICS,
        _EMBARGO_INVITE_SEMANTICS,
        _CLOSE_CASE_SEMANTICS,
        _STATUS_AUTH_TRIGGER_SEMANTICS,
        _LEDGER_REPLAY_SEMANTICS,
    )
    for i, left in enumerate(_all_sets):
        for right in _all_sets[i + 1 :]:
            overlap = left & right
            if overlap:
                raise AssertionError(
                    f"Port-semantics sets overlap: {overlap!r}. "
                    "Each semantic must appear in exactly one set. "
                    "For semantics that need extra ports (e.g. actor_config) "
                    "create a dedicated set+factory pair like _SUBMIT_REPORT_SEMANTICS."
                )

    port_factories: dict = {
        sem: _trigger_activity_with_actor_config_port_factory
        for sem in _SUBMIT_REPORT_SEMANTICS
        | _EMBARGO_INVITE_SEMANTICS
        | _CLOSE_CASE_SEMANTICS
    }
    port_factories.update(
        {sem: _case_proposal_port_factory for sem in _CASE_PROPOSAL_SEMANTICS}
    )
    port_factories.update(
        {
            sem: _status_auth_trigger_port_factory
            for sem in _STATUS_AUTH_TRIGGER_SEMANTICS
        }
    )
    port_factories.update(
        {sem: _inbox_replay_port_factory for sem in _LEDGER_REPLAY_SEMANTICS}
    )
    # Every received use case gets a TriggerActivityPort, a WireRenderPort and
    # a SyncActivityPort, on top of whatever else its semantics needs: a
    # received tree's guarded ledger commit snapshots the activity as an AS2
    # rendering core cannot produce itself (ARCH-20-001, CLP-07-009), the
    # CASE_MANAGER fans the entry out to the participants (SYNC-02-003), and
    # its case-wide clock decisions build their activities (EMB-13-003).  See
    # with_received_baseline_ports for why this is not a hand-kept list
    # (#3930, #4113); a use case that runs no tree accepts all three ports
    # and has nothing to pass them to.
    use_cases = _use_case_map()
    port_factories = {
        sem: inbox_port_factories.with_received_baseline_ports(
            port_factories.get(sem, lambda dl: {})
        )
        for sem in use_cases
    }
    d = get_dispatcher(
        use_case_map=use_cases,
        port_factories=port_factories,
    )
    logger.debug("Created inbox dispatcher: %s", type(d).__name__)
    return d


def init_dispatcher() -> None:
    """Initialise the module-level dispatcher.

    Must be called once during application startup (e.g. from the FastAPI
    lifespan event) before any inbox items are processed.  Calling it more
    than once (e.g. in tests) is allowed — the dispatcher is simply replaced.

    The vestigial ``dl`` parameter is gone.  It had already been unused for
    some time (the DataLayer is passed at dispatch time via :func:`dispatch`),
    and its one remaining caller reached for the unscoped ``get_datalayer()``
    to satisfy it — which ADR-0073 removes.
    """
    dispatcher = make_dispatcher()
    _DISPATCHER_SLOT.install(dispatcher)
    logger.info("Initialised inbox dispatcher: %s", type(dispatcher).__name__)


def dispatch(
    event: VultronEvent,
    dl: DataLayer,
    dispatcher: ActivityDispatcher | None = None,
) -> HandlerResult:
    """Dispatch the given domain event and return the handler's verdict.

    Uses *dispatcher* when provided; otherwise falls back to the module-level
    ``_DISPATCHER_SLOT`` (set by :func:`init_dispatcher`).  Passing an explicit
    dispatcher enables per-app isolation when multiple :func:`create_app`
    instances coexist in the same process (issue #534).

    Args:
        event: The domain event to dispatch.
        dl: The DataLayer instance scoped to the current actor.
        dispatcher: Optional per-app dispatcher.  When ``None`` the
            module-level ``_DISPATCHER_SLOT`` is used (backward-compatible).

    Returns:
        The ``HandlerResult`` of the routed use case (UCORG-05-010).

    Raises:
        RuntimeError: If no dispatcher is available (neither *dispatcher*
            nor the module-level ``_DISPATCHER_SLOT`` has been initialised).
    """
    _d = dispatcher or _DISPATCHER_SLOT.value
    if _d is None:
        raise RuntimeError(
            "Inbox dispatcher not initialised. "
            "Call init_dispatcher() during application startup."
        )
    logger.debug(
        "Dispatching activity '%s' with semantics '%s'",
        event.activity_id,
        event.semantic_type,
    )
    return _d.dispatch(event, dl)


def handle_inbox_item(
    actor_id: str,
    obj: as_Activity,
    dl: DataLayer,
    dispatcher: ActivityDispatcher | None = None,
) -> None:
    """Handle a single item in the Actor's inbox.

    Args:
        actor_id: The canonical URI of the Actor whose inbox is being processed.
        obj: The Activity item to process.
        dl: The DataLayer instance used for reads and dispatch.
        dispatcher: Optional per-app dispatcher.  When ``None`` the
            module-level ``_DISPATCHER_SLOT`` is used (backward-compatible).
    """
    logger.info("Processing item '%s' for actor '%s'", obj.name, actor_id)
    logger.debug(
        "Validated object:\n%s",
        obj.model_dump_json(indent=2, exclude_none=True),
    )
    event = prepare_for_dispatch(activity=obj)
    event = event.model_copy(update={"receiving_actor_id": actor_id})
    dispatch(event=event, dl=dl, dispatcher=dispatcher)


def emit_processing_fault(
    dl: DataLayer,
    receiver_id: str,
    failed_activity_id: str,
    sender_id: str,
    failure_class: str,
) -> str:
    """Queue ``Create(ProcessingFault)`` from *receiver_id* to *sender_id*.

    The fault names *failed_activity_id* and *failure_class* and nothing
    else (ASK-07-006).  Its id is derived from the failed activity and the
    class, so a second failure of the same activity builds no second fault
    (ASK-07-010, ID-04-004).  *dl* is the receiver's own store, whose outbox
    delivers it.

    Returns:
        The fault activity's id.
    """
    return TriggerActivityAdapter(
        cast(CaseOutboxPersistence, dl)
    ).emit_processing_fault(
        actor=receiver_id,
        failed_activity_id=failed_activity_id,
        failure_class=failure_class,
        to=[sender_id],
    )
