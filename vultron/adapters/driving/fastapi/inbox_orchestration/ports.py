"""Inbox dispatch, queue and outcome adapters.

- :class:`FastAPIDispatchAdapter` — wraps the dispatcher port
- :class:`FastAPIQueuePort` — wraps pending-case queue helpers
- :class:`FastAPIReceivedOutcomePort` — wraps the received-outcome service
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

from datetime import datetime
from typing import cast

from vultron.adapters.driving.fastapi.inbox_handler import (
    dispatch,
    emit_processing_fault,
)
from vultron.adapters.driving.fastapi.inbox_pending_queue import (
    _case_window_is_open,
    _expire_pending_case_activities,
    _queue_pending_case_activity,
    _replay_pending_case_activities,
)
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.core.services.received_outcome import (
    archive_applied,
    write_receipt_stub,
)


class FastAPIDispatchAdapter:
    """Dispatch adapter wrapping the inbox dispatcher port.

    Args:
        dl: Shared DataLayer for use-case dispatch.
        actor_id: Canonical URI of the receiving actor; injected into
            the domain event before dispatch.
        dispatcher: Optional per-app dispatcher.  Falls back to the
            module-level dispatcher when ``None``.
    """

    def __init__(
        self,
        dl: DataLayer,
        actor_id: str,
        dispatcher: ActivityDispatcher | None = None,
    ) -> None:
        self._dl = dl
        self._actor_id = actor_id
        self._dispatcher = dispatcher

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        """Inject receiving actor ID, dispatch, and return the verdict."""
        scoped_event = event.model_copy(
            update={"receiving_actor_id": self._actor_id}
        )
        return dispatch(
            event=scoped_event,
            dl=self._dl,
            dispatcher=self._dispatcher,
        )

    def emit_processing_fault(
        self, event: VultronEvent, failure_class: str, *, at: datetime
    ) -> None:
        """Queue the receiving actor's fault to *event*'s sender (ASK-07-010)."""
        emit_processing_fault(
            self._dl,
            self._actor_id,
            event.activity_id,
            event.actor_id,
            failure_class,
            at=at,
        )


class FastAPIQueuePort:
    """Pending-case queue port wrapping the adapter-layer helpers.

    Args:
        dl: Shared DataLayer, for case reads.
        actor_dl: Actor-scoped DataLayer for queue management.
        staging: The inbox run's inline-object staging; a deferred activity's
            staged inline objects are held through it for the replay.
    """

    def __init__(
        self,
        dl: DataLayer,
        actor_dl: DataLayer,
        staging: InlineObjectStaging | None = None,
    ) -> None:
        self._dl = dl
        self._actor_dl = cast(DataLayer, actor_dl)
        self._staging = staging or InlineObjectStaging(actor_dl)

    def is_case_known(self, case_id: str) -> bool:
        """Return ``True`` if the case replica is locally available."""
        return isinstance(self._dl.read(case_id), VulnerabilityCase)

    def queue(
        self,
        activity_id: str,
        case_id: str,
        case_actor_id: str | None = None,
        *,
        at: datetime,
    ) -> None:
        """Persist *activity_id* in the deferred queue for *case_id*.

        The activity is held whole with its staged inline objects, because
        the replay rebuilds it after this delivery's staging is gone, and the
        receiver keeps no copy under its id (DL-06-006).  It is held before
        it is queued, so a failed hold queues nothing.  The hold is what
        records the wait: the held record names *case_id* it waits on, and
        the per-case record only opens the expiry window (ADR-0154).  Both
        take *at*, the activity's arrival stamp (ADR-0176).
        """
        # Read before the hold: the hold is what makes this activity one of
        # the waiting, so only a reading taken first tells a first arrival
        # from a redelivery of the only waiter (CBT-03-003).
        window_already_open = _case_window_is_open(self._actor_dl, case_id)
        self._staging.hold_for_replay(
            activity_id, received_at=at, awaiting_case_id=case_id
        )
        _queue_pending_case_activity(
            queue_dl=self._actor_dl,
            case_id=case_id,
            case_actor_id=case_actor_id,
            window_already_open=window_already_open,
            at=at,
        )

    def check_and_expire(self, case_id: str, *, at: datetime) -> bool:
        """Drop *case_id*'s queue and return ``True`` if it expired by *at*."""
        return _expire_pending_case_activities(
            case_id=case_id, queue_dl=self._actor_dl, at=at
        )

    def replay(self, case_id: str, *, at: datetime) -> None:
        """Move deferred activities for *case_id* back to the live inbox."""
        _replay_pending_case_activities(
            case_id=case_id,
            dl=self._dl,
            queue_dl=self._actor_dl,
            at=at,
        )


class FastAPIReceivedOutcomePort:
    """Received-outcome port over the receiving actor's own store.

    The two writes a final outcome makes: an applied or skipped delivery's
    record is archived (:func:`~vultron.core.services.received_outcome
    .archive_applied`, CLP-10-073), and a refused delivery's body is given up
    for a receipt stub (:func:`~vultron.core.services.received_outcome
    .write_receipt_stub`, CLP-10-018).  A deferred delivery keeps what its
    record holds, so the port is never called for one.

    Args:
        actor_dl: The receiving actor's DataLayer — the store that holds its
            received records (DL-06-006).
    """

    def __init__(self, actor_dl: DataLayer) -> None:
        self._dl = cast(CasePersistence, actor_dl)

    def apply(self, activity_id: str) -> None:
        """Archive the record holding *activity_id*'s applied body."""
        archive_applied(self._dl, activity_id)

    def refuse(
        self,
        activity_id: str,
        *,
        sender_id: str,
        reason: str,
        received_body: str | None,
        received_at: datetime,
    ) -> None:
        """Replace what is held for *activity_id* with a receipt stub."""
        write_receipt_stub(
            self._dl,
            activity_id,
            sender_id=sender_id,
            reason=reason,
            received_body=received_body,
            received_at=received_at,
        )
