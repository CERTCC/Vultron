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

"""Registry-backed implementation of the ``TriggerDispatcher`` port.

:class:`RegistryTriggerDispatcher` is to the trigger side what
:class:`~vultron.core.dispatcher.DirectActivityDispatcher` is to the received
side: one ``trigger()`` method that looks the request up in a data table,
injects the driven ports the use case needs, constructs it as
``(dl, request, **ports)``, calls ``execute()`` and returns the typed result
(ADR-0110).  The table is ``vultron.trigger_registry`` (TRIG-12-004); the
adapter passes its rows in, as it passes ``use_case_map()`` to the received
dispatcher, so this module holds no per-verb knowledge.
"""

import logging
from collections.abc import Iterable, Sequence
from typing import Any, cast

from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.dispatcher import CaseUpkeep
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.request_bodies import CaseTriggerRequest
from vultron.core.use_cases.triggers.requests import ResultT_co, TriggerRequest
from vultron.errors import VultronApiHandlerNotFoundError, VultronNotFoundError
from vultron.trigger_registry import TriggerEntry, index_by_request_model

logger = logging.getLogger(__name__)


class RegistryTriggerDispatcher:
    """``TriggerDispatcher`` over a set of registry rows.

    Args:
        entries: The rows to route over — ``vultron.trigger_registry.entries()``
            in deployment; a test may pass a subset.
        trigger_activity: The driven port every trigger use case constructs
            its outbound activity through (ARCH-01-004).
        wire_render_port: The port a BT-backed tree renders ledger payload
            snapshots through (ARCH-20-001); given to every ``bt_backed`` row.
        sync_port: The port a BT-backed commit fans a ledger entry out through
            (SYNC-02-002); given to every ``bt_backed`` row.
        case_upkeep: The
            :class:`~vultron.core.ports.dispatcher.CaseUpkeep` hooks run, in
            order, before a request that names a case, unless its row sets
            ``runs_case_upkeep=False``.  The composition root chooses them.

    Port injection is keyed on the row's ``bt_backed`` flag, never on its
    verb: a BT-backed use case is built with the whole BT port bundle, and the
    one non-BT-backed use case with ``trigger_activity`` alone.
    """

    def __init__(
        self,
        entries: Iterable[TriggerEntry],
        *,
        trigger_activity: TriggerActivityPort,
        wire_render_port: WireRenderPort,
        sync_port: SyncActivityPort,
        case_upkeep: Sequence[CaseUpkeep] = (),
    ) -> None:
        self._by_request = index_by_request_model(entries)
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._case_upkeep = tuple(case_upkeep)

    def _entry_for(self, request: TriggerRequest[Any]) -> TriggerEntry:
        entry = self._by_request.get(type(request))
        if entry is None:
            logger.error(
                "No trigger registry row for request type '%s' (actor_id=%s)",
                type(request).__name__,
                request.actor_id,
            )
            raise VultronApiHandlerNotFoundError(
                f"No trigger registry row for request type"
                f" '{type(request).__name__}'"
            )
        return entry

    def _ports_for(self, entry: TriggerEntry) -> dict[str, object]:
        ports: dict[str, object] = {"trigger_activity": self._trigger_activity}
        if entry.bt_backed:
            ports["wire_render_port"] = self._wire_render_port
            ports["sync_port"] = self._sync_port
        return ports

    def _run_case_upkeep(
        self,
        entry: TriggerEntry,
        request: TriggerRequest[Any],
        dl: CaseOutboxPersistence,
    ) -> None:
        """Run each case-upkeep hook for the request's case, as its actor.

        Skipped with no hooks, for a row that opts out, for a request that
        names no case, and when the actor or case cannot be resolved: the use
        case then reports that itself.
        """
        if not self._case_upkeep or not entry.runs_case_upkeep:
            return
        if not isinstance(request, CaseTriggerRequest):
            return
        try:
            actor_id = resolve_actor(request.actor_id, dl).id_
            case_id = resolve_case(request.case_id, dl).id_
        except VultronNotFoundError:
            return
        for upkeep in self._case_upkeep:
            upkeep(dl, case_id=case_id, actor_id=actor_id, activity_id=None)

    def trigger(
        self,
        request: TriggerRequest[ResultT_co],
        dl: CaseOutboxPersistence,
    ) -> ResultT_co:
        entry = self._entry_for(request)
        self._run_case_upkeep(entry, request, dl)
        use_case = entry.use_case_class(dl, request, **self._ports_for(entry))
        logger.debug(
            "Entering trigger %s for verb '%s' (actor_id=%s)",
            type(use_case).__name__,
            entry.verb,
            request.actor_id,
        )
        result = use_case.execute()
        if not isinstance(result, entry.result_type):
            # A contract breach by the use case, not a domain verdict —
            # ``TypeError`` as ``DispatcherBase._handle`` raises for a
            # received handler that returns something other than a
            # ``HandlerResult``.
            raise TypeError(
                f"use case {entry.use_case_class.__name__} for verb"
                f" '{entry.verb}' returned {type(result).__name__}, not"
                f" {entry.result_type.__name__} (UCORG-05-007)"
            )
        # ``result`` is an instance of the row's ``result_type``, which the
        # row's request model binds as ResultT_co (TRIG-12-004 (c)); the
        # static binding lives on the request, so this is the one place the
        # erasure is closed.
        return cast(ResultT_co, result)
