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

"""Core dispatcher implementation.

``DispatcherBase`` and ``DirectActivityDispatcher`` implement the
``ActivityDispatcher`` driving port defined in ``vultron/core/ports/dispatcher.py``.
The concrete dispatcher is injected into adapters (inbox handler, CLI, etc.)
rather than being instantiated by them directly.

The ``get_dispatcher`` factory function is provided for adapter convenience.
"""

import logging
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from vultron.core.models.events import MessageSemantics
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.dispatcher import ActivityDispatcher

if TYPE_CHECKING:
    from vultron.core.models.events import VultronEvent
    from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


class DispatcherBase:
    """Base dispatcher implementation.

    Looks up the use case class for the event's ``semantic_type`` from the
    supplied routing table, instantiates it with ``dl``, calls ``execute()``,
    and returns the handler's ``HandlerResult`` (UCORG-05-010).

    Optional *port_factories* allow driven ports to be injected for specific
    semantic types.  Each factory receives the ``DataLayer`` and returns a
    dict of keyword arguments to pass to the use-case constructor.  Use cases
    whose constructors do not accept these kwargs are unaffected.
    """

    def __init__(
        self,
        use_case_map: Mapping[MessageSemantics, type],
        port_factories: (
            Mapping[
                MessageSemantics,
                Callable[["DataLayer"], dict[str, Any]],
            ]
            | None
        ) = None,
    ):
        self._use_case_map = use_case_map
        self._port_factories = port_factories or {}

    def dispatch(
        self, event: "VultronEvent", dl: "DataLayer"
    ) -> HandlerResult:
        logger.info(
            "Dispatching activity of type '%s' with semantics '%s'",
            event.object_type,
            event.semantic_type,
        )
        logger.debug(
            "Activity payload: activity_id=%s actor_id=%s object_type=%s",
            event.activity_id,
            event.actor_id,
            event.object_type,
        )
        return self._handle(event, dl)

    def _handle(self, event: "VultronEvent", dl: "DataLayer") -> HandlerResult:
        """Run the routed use case and return its verdict.

        This is the link that calls ``execute()``, so it is the first hop that
        must keep the ``HandlerResult`` (UCORG-05-010). A semantic type with
        no use case in the routing table runs no handler: the dispatcher
        reports it as "no use case found" (:meth:`_no_use_case_found`), a
        rejection, never ``processed`` (UCORG-05-012).

        Raises:
            TypeError: The use case returned something other than a
                ``HandlerResult`` — a contract breach, not a verdict.
        """
        use_case_class = self._use_case_map.get(event.semantic_type)
        if use_case_class is None:
            return self._no_use_case_found(event)
        extra_kwargs: dict[str, Any] = {}
        port_factory = self._port_factories.get(event.semantic_type)
        if port_factory is not None:
            extra_kwargs = port_factory(dl)
        use_case = use_case_class(dl, event, **extra_kwargs)
        # HP-06-001: handler entry is logged once, here, with the handler's
        # class name, so no handler carries its own entry line.
        logger.debug(
            "Entering handler %s (activity_id=%s semantics=%s actor_id=%s)",
            type(use_case).__name__,
            event.activity_id,
            event.semantic_type,
            event.actor_id,
        )
        result = use_case.execute()
        if not isinstance(result, HandlerResult):
            raise TypeError(
                f"use case {use_case_class!r} for {event.semantic_type} "
                f"returned {type(result).__name__}, not HandlerResult"
                " (UCORG-05-001)"
            )
        return result

    @staticmethod
    def _no_use_case_found(event: "VultronEvent") -> HandlerResult:
        """Report an activity whose semantic type no use case handles.

        The registry recognizes the type, but this receiver does not handle
        it: the message is not invalid, so this is a normal outcome logged
        at INFO, never a raise that would answer the sender with a fault
        (ADR-0140 item 5, SE-05-002).  No handler ran, so the verdict is
        ``REFUSED`` and the activity is not ``processed`` (UCORG-05-012); it
        is marked ``unhandled`` so the inbox reports it at INFO (IO-01-005).
        An unrecognized activity never reaches here: it routes to the
        ``UNKNOWN`` fallback's use case (SE-04).
        """
        logger.info(
            "No use case found for semantics '%s' (activity_id=%s"
            " actor_id=%s); the activity is not processed",
            event.semantic_type,
            event.activity_id,
            event.actor_id,
        )
        return HandlerResult.no_use_case_found(event.semantic_type)


class DirectActivityDispatcher(DispatcherBase):
    """Local in-process dispatcher implementation."""


def get_dispatcher(
    use_case_map: Mapping[MessageSemantics, type],
    port_factories: (
        Mapping[
            MessageSemantics,
            Callable[["DataLayer"], dict[str, Any]],
        ]
        | None
    ) = None,
) -> ActivityDispatcher:
    """Factory: return a ``DirectActivityDispatcher`` for the given routing table."""
    return DirectActivityDispatcher(
        use_case_map=use_case_map,
        port_factories=port_factories,
    )
