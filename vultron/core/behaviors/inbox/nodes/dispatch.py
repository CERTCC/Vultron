#!/usr/bin/env python
"""Inbox pipeline dispatch-stage nodes: dispatch and the processed outcome.

:class:`DispatchNode` is the one place a handler's ``HandlerResult`` becomes
an inbox outcome (HP-01-004, UCORG-05-011); :class:`BuildOutcomeNode` records
``processed`` when every preceding step succeeded. The shared blackboard keys
and node base class live in :mod:`~vultron.core.behaviors.inbox.nodes.pipeline`.

Per specs/inbox-orchestration.yaml IO-02-002.
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

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.inbox.models import (
    DispatchAdapter,
    InboxOutcomeStatus,
)
from vultron.core.behaviors.inbox.nodes.pipeline import (
    KEY_CONTEXT_ID,
    KEY_DISPATCH,
    KEY_EVENT,
    KEY_OUTCOME_STATUS,
    KEY_QUEUE,
    _InboxNodeWithPorts,
)
from vultron.core.models.events import (
    MessageSemantics,
    VultronEvent,
    is_case_bootstrap,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)

# The only place a handler's verdict becomes an inbox outcome (HP-01-004,
# UCORG-05-011). Many-to-one: a correct no-op is still ``processed``.
_OUTCOME_FOR_DISPOSITION: dict[HandlerDisposition, InboxOutcomeStatus] = {
    HandlerDisposition.APPLIED: InboxOutcomeStatus.PROCESSED,
    HandlerDisposition.SKIPPED: InboxOutcomeStatus.PROCESSED,
    HandlerDisposition.DEFERRED: InboxOutcomeStatus.DEFERRED,
    HandlerDisposition.REFUSED: InboxOutcomeStatus.REJECTED,
}


def answers_with_internal_error_fault(event: VultronEvent) -> bool:
    """Whether a raise while processing *event* is answered with a fault.

    Every received activity is, except a ``Create(ProcessingFault)``: a
    fault answered with a fault would let two peers that fail alike answer
    each other without end, each fault's derived id naming the one before
    (ASK-07-010).
    """
    return event.semantic_type is not MessageSemantics.CREATE_PROCESSING_FAULT


class DispatchNode(_InboxNodeWithPorts):
    """Step 5: dispatch the domain event and map the handler's verdict.

    The returned ``HandlerResult`` decides the outcome (UCORG-05-011), not the
    absence of an exception: ``APPLIED``/``SKIPPED`` return SUCCESS so
    :class:`BuildOutcomeNode` records ``processed``; ``DEFERRED`` records
    ``deferred`` and ``REFUSED`` records ``rejected`` with the handler's
    ``reason``, both returning FAILURE. A dispatch that returns anything but a
    ``HandlerResult`` is rejected — no verdict is not a success.  A dispatch
    that raises is rejected too, and its sender is answered with an
    internal-error ``Create(ProcessingFault)`` (ASK-07-010).

    After a bootstrap the handler accepted (``processed``), triggers replay
    of any activities that were deferred pending this case's local replica.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        KEY_EVENT: PortInformation(data_type=object, required=True),
        KEY_DISPATCH: PortInformation(data_type=object, required=True),
        KEY_CONTEXT_ID: PortInformation(data_type=object, required=False),
        KEY_QUEUE: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            KEY_EVENT: f"/{KEY_EVENT}",
            KEY_DISPATCH: f"/{KEY_DISPATCH}",
            KEY_CONTEXT_ID: f"/{KEY_CONTEXT_ID}",
            KEY_QUEUE: f"/{KEY_QUEUE}",
        }

    def _replay_after_bootstrap(self, event: VultronEvent) -> None:
        """Replay activities held pending this case's local replica.

        Runs only for a ``processed`` verdict: a bootstrap the handler refused
        or deferred has not made the case locally available.

        Raises whatever the queue port raises; ``update()`` catches it.
        """
        try:
            context_id: str | None = self.get_input(KEY_CONTEXT_ID)
        except (NotImplementedError, NoDataAvailable):
            context_id = None

        try:
            queue = self.get_input(KEY_QUEUE)
        except (NotImplementedError, NoDataAvailable, KeyError):
            queue = None

        if (
            is_case_bootstrap(event)
            and context_id is not None
            and queue is not None
        ):
            queue.replay(context_id)
            self.logger.info(
                "%s: triggered replay for case '%s'", self.name, context_id
            )

    def _answer_with_internal_error_fault(
        self, dispatch: DispatchAdapter, event: VultronEvent
    ) -> None:
        """Answer the sender of a raised dispatch with a fault (ASK-07-010).

        The dispatch has returned by raising, so any transaction the act
        opened has closed: an act that runs as one act has rolled back, and
        the fault is not undone with it.  A live delivery is never retried,
        so only the sender's own resend, which the fault invites, can later
        succeed (ADR-0151).  A replay of a queued item the inbox may retry
        gets a dispatch adapter that holds the fault until the item is
        dead-lettered, so a retry that succeeds follows no false fault
        (IE-06-004, ASK-07-007).  The sender is the event's
        ``actor_id``: an activity that names none is refused at extraction
        and never reaches dispatch.  The inbox does not yet authenticate that
        sender (#509), so the fault goes to the actor the activity claims.
        A raised ``Create(ProcessingFault)`` is not answered
        (:func:`answers_with_internal_error_fault`).  The fault is a notice,
        not a recovery; it carries the internal-error class and no
        diagnostics (ASK-07-006).

        Raises whatever the dispatch adapter raises; ``update()`` catches
        it, so the outcome stays the dispatch's rejection (MV-01-007).
        """
        if not answers_with_internal_error_fault(event):
            self.logger.info(
                "%s: activity_id=%s is a ProcessingFault; it is not answered"
                " with another",
                self.name,
                event.activity_id,
            )
            return
        dispatch.emit_processing_fault(
            event, VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR
        )
        self.logger.info(
            "%s: queued ProcessingFault/InternalProcessingError to actor_id=%s"
            " for activity_id=%s",
            self.name,
            event.actor_id,
            event.activity_id,
        )

    def update(self) -> Status:
        try:
            event = self.get_input(KEY_EVENT)
            dispatch = self.get_input(KEY_DISPATCH)
        except (KeyError, NoDataAvailable) as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            result = dispatch.dispatch(event)
        except Exception as exc:
            # A raise is not a verdict but an internal error (HP-06-003): this
            # is the one ERROR record naming the failed act and its sender,
            # with the traceback, so a programming error stays
            # distinguishable from a handler's REFUSED.  The driving adapter
            # names the receiver when it logs the rejected outcome.  An act
            # that kept nothing runs again on a redelivery (ADR-0151).
            self.logger.exception(
                "%s: dispatch raised for activity_id=%s actor_id=%s",
                self.name,
                getattr(event, "activity_id", None),
                getattr(event, "actor_id", None),
            )
            try:
                self._answer_with_internal_error_fault(dispatch, event)
            except Exception:
                # A fault that cannot be queued is logged, never raised.
                self.logger.exception(
                    "%s: ProcessingFault not queued for activity_id=%s"
                    " actor_id=%s",
                    self.name,
                    event.activity_id,
                    event.actor_id,
                )
            return self._reject(f"Dispatch raised exception: {exc}")

        if not isinstance(result, HandlerResult):
            return self._reject(
                f"Dispatch returned {type(result).__name__}, not a"
                " HandlerResult"
            )

        self.logger.info(
            "%s: dispatched %s activity_id=%s disposition=%s",
            self.name,
            event.semantic_type,
            event.activity_id,
            result.disposition,
        )

        status = _OUTCOME_FOR_DISPOSITION[result.disposition]
        if status is InboxOutcomeStatus.REJECTED:
            # HandlerResult rejects a REFUSED verdict without a reason.
            assert result.reason is not None
            return self._reject(result.reason)
        if status is InboxOutcomeStatus.DEFERRED:
            return self._defer(
                result.reason or "Deferred by handler (no reason given)"
            )

        try:
            self._replay_after_bootstrap(event)
        except Exception:
            # The bootstrap itself was applied, so a replay fault is logged
            # rather than escaping update() or rejecting it (MV-01-007).
            self.logger.exception(
                "%s: replay failed after bootstrap activity_id=%s",
                self.name,
                event.activity_id,
            )
        return Status.SUCCESS


class BuildOutcomeNode(_InboxNodeWithPorts):
    """Step 6: record the processed outcome on the blackboard.

    Runs only when all preceding Sequence nodes succeeded — including
    :class:`DispatchNode`, which succeeds only for an ``APPLIED`` or
    ``SKIPPED`` verdict.  Writes ``InboxOutcomeStatus.PROCESSED`` so that
    :func:`process_payload` can assemble the final :class:`InboxOutcome`.
    """

    def update(self) -> Status:
        self._set_output(KEY_OUTCOME_STATUS, InboxOutcomeStatus.PROCESSED)
        self.logger.debug("%s: outcome = processed", self.name)
        return Status.SUCCESS
