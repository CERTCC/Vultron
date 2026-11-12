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

"""The shared outbox-enqueue seam for BT emit nodes (OX-14-001, ASK-04-008).

Every BT node that queues an outbound activity goes through
``_EmitSingleActivityBase._emit_through_seam()``; ``UpdateActorOutbox`` is the
legacy direct queue for a case-creation notification.
"""

import json
from contextlib import AbstractContextManager
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.helpers.ports_base import DataLayerActionWithPorts
from vultron.core.ports.case_outbox import CaseOutboxPersistence


class _EmitSingleActivityBase(DataLayerActionWithPorts, EmitCapable):
    """Base class for emit nodes that create one activity and queue it in the actor's outbox.

    Subclasses override ``_call_factory()`` (required) to invoke the
    appropriate ``TriggerActivityPort`` method and return
    ``(activity_id, activity_dict)``.  A node whose activity is recorded in
    the case ledger overrides ``_record_sent()`` to commit it: ``update()``
    calls it after the outbox write, because a ledger entry records a
    completed act and a send is complete once the activity is in this
    actor's outbox (ADR-0119, SYNC-09-002).  The build, the outbox write
    and the commit run in one act (:meth:`_one_act`), so the outbox entry
    is not delivered before the commit, and a failed commit leaves nothing
    queued (OX-03-002, ADR-0146).  The optional ``_on_success()`` hook is
    called after the act commits and is useful for domain-specific log
    messages.

    When *captured* is provided, ``captured["activity"]`` is set to the
    serialised activity dict on success, avoiding a follow-up ``dl.read()``
    (AC-1, AC-2, DL-06-001).

    Implements BTND-07-005, BTND-07-009, BTND-07-010.
    """

    def __init__(
        self,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._captured = captured

    def _call_factory(self) -> tuple[str, str]:
        """Invoke the trigger-activity factory.  Subclasses must implement this.

        Returns:
            ``(activity_id, activity_json)``

        Raises:
            NotImplementedError: Subclasses must implement this method.
        """
        raise NotImplementedError

    def _record_sent(self, activity_id: str, activity_blob: str) -> None:
        """Commit the ledger entry of the activity just queued; default: none.

        Called after the outbox write, in the same act (:meth:`_one_act`),
        whether or not that write queued the activity: an id already pending
        is not queued again (OX-06-002) and is still recorded (ADR-0119).
        Raises when the commit fails;
        ``update()`` does not catch it, so the act rolls back, taking the
        outbox write with it, and the exception reaches ``BTBridge``.
        """

    def _one_act(self) -> AbstractContextManager[None]:
        """The transaction a send and the commit recording it share.

        The outbox write is not visible to a drain until the act commits,
        and is rolled back with it, so a drain the write wakes (OX-09-001)
        cannot deliver an activity whose act then fails (OX-03-002,
        ADR-0146).  Inside an enclosing act (an ``ActTransaction``) this is
        part of that act.
        """
        return cast(CaseOutboxPersistence, self.datalayer).transaction()

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        """Optional hook called after a successful outbox write.

        Override in concrete nodes to emit domain-specific log messages or
        post-emit side-effects.  The default implementation is a no-op.
        """

    def _emit_through_seam(self, activity_id: str, activity_blob: str) -> bool:
        """Route activity emission through the shared outbox-enqueue seam.

        Appends *activity_id* to the actor's outbox and populates
        ``_captured["activity"]`` when a capture dict is present.  An id
        already pending is not queued again (OX-06-002): a retry that rebuilt
        the activity under its first attempt's id sends it once.  Returns
        ``True`` when this call queued it, ``False`` when it was pending.

        Cross-cutting hooks for outstanding-ask registration (ASK-04-008)
        and undelivered-activity correlation (OX-14-001) belong here.

        Note: ``_on_success()`` is intentionally NOT called here — callers
        invoke it *outside* the enclosing try/except so that a hook bug is
        not silently swallowed as a retryable FAILURE after the write has
        already committed.
        """
        # `outbox_append`, not the retired `record_outbox_item(actor_id, …)`:
        # this store is already the executing actor's own, so naming the
        # actor again is both redundant and a way to get it wrong (ADR-0073,
        # see `CaseOutboxPersistence`).
        # Parsed before the queue write, so nothing after the write can fail
        # and leave the activity queued by an act that reports FAILURE.
        captured = (
            json.loads(activity_blob) if self._captured is not None else None
        )
        queued = cast(CaseOutboxPersistence, self.datalayer).outbox_append(
            activity_id
        )
        if not queued:
            self.logger.info(
                "%s: activity '%s' is already pending in the outbox — not"
                " queued again (OX-06-002)",
                self.name,
                activity_id,
            )
        if self._captured is not None:
            self._captured["activity"] = captured
        return queued

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error("%s", self.feedback_message)
            return f
        failure: Exception | None = None
        with self._one_act():
            try:
                activity_id, activity_blob = self._call_factory()
                self._emit_through_seam(activity_id, activity_blob)
            except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
                # Nothing was queued, so no answer is out.  The act keeps
                # what the build stored, for a redelivery to queue
                # (CBT-01-001).
                failure = e
            else:
                # Not caught: the activity is queued in this act, so a
                # FAILURE here would let an enclosing Selector fall through to
                # another arm and send a second, contradictory answer after
                # it.  A failed commit rolls the act back, taking the queued
                # activity with it, and escapes to ``BTBridge`` as an internal
                # error instead (BT-14-001, ARCH-15-001), as in the relay node
                # and ``_CommitCaseManagerActivityBase``.
                self._record_sent(activity_id, activity_blob)
        if failure is not None:
            self.feedback_message = (
                f"{self.__class__.__name__} failed: {failure}"
            )
            self.logger.error("%s", self.feedback_message)
            return Status.FAILURE
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS


class UpdateActorOutbox(DataLayerActionWithPorts, EmitCapable):
    """
    Update actor's outbox with a new activity.

    Reads ``activity_id`` and ``case_id`` from the blackboard (set by the
    preceding activity-creation node) and appends the activity ID to the
    actor's outbox.  Also queues the activity for delivery via
    ``outbox_append``.

    Per BTND-04-005: defined here as shared logic used by both
    ``vultron/core/behaviors/report/nodes.py`` and
    ``vultron/core/behaviors/case/nodes.py``.
    """

    def __init__(self, name: str | None = None):
        """
        Initialize UpdateActorOutbox node.

        Args:
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity_id": PortInformation(data_type=str, required=True),
        "case_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity_id": "/activity_id", "case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self.activity_id = self.get_input("activity_id")
        except NoDataAvailable, NotImplementedError:
            self.activity_id = None
        try:
            self.case_id = self.get_input("case_id")
        except NoDataAvailable, NotImplementedError:
            self.case_id = None

    def update(self) -> Status:
        """
        Update actor's outbox with activity ID.

        Returns:
            SUCCESS if outbox updated, FAILURE on error
        """
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        try:
            activity_id = self.activity_id
            if activity_id is None:
                self.logger.error(
                    "%s: activity_id not found in blackboard", self.name
                )
                return Status.FAILURE

            case_id = self.case_id

            queued = cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
            self.logger.info(
                "%s Create(VulnerabilityCase '%s') activity '%s' in actor '%s'"
                " outbox (case creation notification)",
                "Queued" if queued else "Left already-pending (OX-06-002)",
                case_id,
                activity_id,
                self.actor_id,
            )

            return Status.SUCCESS

        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: Error updating actor outbox: %s", self.name, e
            )
            return Status.FAILURE
