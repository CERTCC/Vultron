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
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Callable

from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.errors import (
    VultronApiHandlerNotFoundError,
    VultronValidationError,
)

if TYPE_CHECKING:
    from vultron.core.models.events import VultronEvent
    from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)

_JOIN_BACKFILL_GATED_SEMANTICS = frozenset(
    {
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.ADD_NOTE_TO_CASE,
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        MessageSemantics.DEFER_CASE,
        MessageSemantics.ENGAGE_CASE,
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
    }
)


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
            Mapping[
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
        self._enforce_join_backfill_gate(event, dl)
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

    def _enforce_join_backfill_gate(
        self, event: "VultronEvent", dl: "DataLayer"
    ) -> None:
        if event.semantic_type not in _JOIN_BACKFILL_GATED_SEMANTICS:
            return
        sender_id = event.actor_id
        if not sender_id:
            return
        case_id = self._extract_case_id(event, dl)
        if not case_id:
            return
        state_id = VultronReplicationState(
            case_id=case_id,
            peer_id=sender_id,
        ).id_
        state = dl.read(state_id)
        if not isinstance(state, VultronReplicationState):
            return
        if state.join_backfill_target_index == -1:
            return
        if state.join_backfill_complete:
            return
        raise VultronValidationError(
            f"Actor '{sender_id}' is not caught up for case '{case_id}' "
            "(join-time backfill incomplete)."
        )

    def _extract_case_id(
        self, event: "VultronEvent", dl: "DataLayer"
    ) -> str | None:
        if (
            event.semantic_type
            == MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
        ):
            status_obj = getattr(event, "object_", None)
            status_context = getattr(status_obj, "context", None)
            if isinstance(status_context, str) and status_context:
                return status_context
        if (
            event.semantic_type
            == MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE
        ):
            invite_id = getattr(event, "invite_id", None)
            if isinstance(invite_id, str) and invite_id:
                invite = dl.read(invite_id)
                invite_context = getattr(invite, "context", None)
                if isinstance(invite_context, str) and invite_context:
                    return invite_context
                invite_context_id = getattr(invite, "context_id", None)
                if isinstance(invite_context_id, str) and invite_context_id:
                    return invite_context_id
        for attr in (
            "case_id",
            "inner_context_id",
            "context_id",
            "origin_id",
            "inner_target_id",
            "target_id",
        ):
            value = getattr(event, attr, None)
            if isinstance(value, str) and value:
                return value
        return None

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
