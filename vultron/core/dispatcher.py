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
from typing import TYPE_CHECKING, Any, Callable

from vultron.core.models.events import MessageSemantics
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.errors import VultronApiHandlerNotFoundError

if TYPE_CHECKING:
    from vultron.core.models.events import VultronEvent
    from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


class DispatcherBase:
    """Base dispatcher implementation.

    Looks up the use case class for the event's ``semantic_type`` from the
    supplied routing table, instantiates it with ``dl``, and calls
    ``execute(event)``.

    Optional *port_factories* allow driven ports to be injected for specific
    semantic types.  Each factory receives the ``DataLayer`` and returns a
    dict of keyword arguments to pass to the use-case constructor.  Use cases
    whose constructors do not accept these kwargs are unaffected.
    """

    def __init__(
        self,
        use_case_map: dict[MessageSemantics, type],
        port_factories: (
            dict[
                MessageSemantics,
                Callable[["DataLayer"], dict[str, Any]],
            ]
            | None
        ) = None,
    ):
        self._use_case_map = use_case_map
        self._port_factories = port_factories or {}

    def dispatch(self, event: "VultronEvent", dl: "DataLayer") -> None:
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
        self._handle(event, dl)

    def _handle(self, event: "VultronEvent", dl: "DataLayer") -> None:
        use_case_class = self._get_use_case(event.semantic_type)
        extra_kwargs: dict[str, Any] = {}
        port_factory = self._port_factories.get(event.semantic_type)
        if port_factory is not None:
            extra_kwargs = port_factory(dl)
        try:
            use_case_class(dl, event, **extra_kwargs).execute()
        except Exception:
            logger.error(
                "Unexpected error dispatching activity_id=%s actor_id=%s semantics=%s",
                event.activity_id,
                event.actor_id,
                event.semantic_type,
                exc_info=True,
            )
            raise

    def _get_use_case(self, semantics: MessageSemantics) -> type:
        use_case_class = self._use_case_map.get(semantics)
        if use_case_class is None:
            logger.error("No use case found for semantics '%s'", semantics)
            raise VultronApiHandlerNotFoundError(
                f"No use case found for semantics '{semantics}'"
            )
        return use_case_class


class DirectActivityDispatcher(DispatcherBase):
    """Local in-process dispatcher implementation."""


def get_dispatcher(
    use_case_map: dict[MessageSemantics, type],
    port_factories: (
        dict[
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
