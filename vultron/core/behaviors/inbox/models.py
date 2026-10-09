#!/usr/bin/env python
"""InboxOutcome model and adapter/port protocol interfaces.

Defines the typed return model and Protocol interfaces used by
:func:`~vultron.core.behaviors.inbox.process_payload`.

Per specs/inbox-orchestration.yaml:
- IO-01-001 through IO-01-004: InboxOutcome model
- IO-03-001: IngressPayloadAdapter and DispatchAdapter protocols
- IO-03-002: PendingCaseQueuePort protocol
"""

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

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from vultron.core.models.events import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.primitives import NonEmptyString


class InboxOutcomeStatus(StrEnum):
    """What the inbox pipeline did with one payload (IO-01-002).

    - ``PROCESSED`` — dispatched, and the handler applied or correctly skipped it.
    - ``DEFERRED`` — held for replay: by ``DeferCheckNode`` before dispatch
      (missing case context), or by the handler after it (UCORG-05-011).
    - ``REJECTED`` — refused, unparseable, undispatchable, or the dispatch
      raised.

    This vocabulary belongs to the pipeline. ``DispatchNode`` alone maps a
    handler's ``HandlerDisposition`` onto it (HP-01-004).
    """

    PROCESSED = "processed"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class InboxOutcome(BaseModel):
    """Result returned by every :func:`process_payload` call.

    Per specs/inbox-orchestration.yaml IO-01-001 through IO-01-004.
    """

    status: InboxOutcomeStatus
    context_id: str | None = None
    activity_id: NonEmptyString | None = None
    failure_reason: str | None = None


@runtime_checkable
class IngressPayloadAdapter(Protocol):
    """Adapter: raw input → rehydrated as_Activity.

    Owns parse and rehydrate; isolates wire-format knowledge from the
    orchestration BT.  Per IO-03-001.
    """

    def parse(
        self,
        payload: dict[str, Any] | bytes | str | Any,
    ) -> Any | None:
        """Parse raw payload into a typed Activity.

        Returns ``None`` on parse failure; MUST NOT raise.
        """
        ...  # pragma: no cover

    def rehydrate(self, activity: Any) -> Any:
        """Resolve nested object references to their full representations."""
        ...  # pragma: no cover


@runtime_checkable
class DispatchAdapter(Protocol):
    """Adapter: VultronEvent → use-case execution.

    Wraps the existing ActivityDispatcher port.  Per IO-03-001.
    """

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        """Dispatch a domain event and return the handler's verdict.

        The ``HandlerResult`` is the only channel from the handler to
        ``InboxOutcome`` (UCORG-05-010).
        """
        ...  # pragma: no cover


@runtime_checkable
class PendingCaseQueuePort(Protocol):
    """Port: pending-case inbox queue management.

    Provides defer and replay queue operations to :class:`DeferCheckNode`
    without requiring adapter-layer imports in core.  Per IO-03-002.
    """

    def is_case_known(self, case_id: str) -> bool:
        """Return ``True`` if the case replica is locally available."""
        ...  # pragma: no cover

    def queue(
        self,
        activity_id: str,
        case_id: str,
        case_actor_id: str | None = None,
    ) -> None:
        """Persist *activity_id* in the deferred queue for *case_id*."""
        ...  # pragma: no cover

    def check_and_expire(self, case_id: str) -> bool:
        """Check expiry; drop queue and return ``True`` when expired."""
        ...  # pragma: no cover

    def replay(self, case_id: str) -> None:
        """Move deferred activities for *case_id* back to the live inbox."""
        ...  # pragma: no cover
