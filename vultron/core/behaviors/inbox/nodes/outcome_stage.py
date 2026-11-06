#!/usr/bin/env python
"""Step 6a: the handler's verdict becomes the record's final stage (ADR-0154).

:class:`SettleReceivedOutcome` wraps :class:`.DispatchNode` so it runs on
every path the dispatch can take — applied, skipped, deferred, refused, and a
dispatch that raised — and maps that one verdict onto what the receiver keeps:

- **applied** or **skipped** -- the ``HELD`` record intake wrote is archived
  with the sealed body it holds (CLP-10-017, CLP-10-073).
- **refused** -- the body is given up for a receipt stub: the sender, the
  activity id, the time of receipt, the reason and the body's digest
  (CLP-10-018).  That includes a semantic type no use case handles: nothing
  applies it, so the receiver keeps no copy of it (CLP-10-074).  A delivery
  a door refused before intake ran has no record, so its stub is written
  from the delivery's own sealed body.
- **deferred** -- the message is still waiting, so the holding record stands
  as it is (IO-03-009).
- **no verdict** (the dispatch raised, or returned something that is not a
  ``HandlerResult``) -- not an outcome.  The record is left untouched,
  ``HELD`` with its sealed body, so a resend or a re-run runs the act again
  from it (ADR-0151, CLP-10-074).

It is a decorator, not a sibling, because the inbox pipeline is a ``Sequence``
whose later children do not run once a step fails, and a refusal fails the
dispatch.  A decorator runs its ``update()`` after the child whatever the
child returned, and returns the child's status unchanged, so the verdict the
sender is answered with is still the dispatch's (as in
``LedgerPositionAnswer`` and ``RefusalEffectsBestEffort``).

The verdict reaches it on the blackboard, from ``DispatchNode``, which is the
only node that reads the ``HandlerResult`` (UCORG-05-010): no stage reads
in-memory state an earlier stage left behind (ADR-0154).
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

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.inbox.models import ReceivedOutcomePort
from vultron.core.behaviors.inbox.nodes.pipeline import (
    KEY_DISPOSITION,
    KEY_EVENT,
    KEY_FAILURE_REASON,
    KEY_OUTCOME,
)
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.models.events import VultronEvent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.errors import VultronWiringError

#: The dispositions whose record is archived with the body it holds.
_ARCHIVES = frozenset({HandlerDisposition.APPLIED, HandlerDisposition.SKIPPED})


class SettleReceivedOutcome(py_trees.decorators.Decorator):
    """Map the handler's verdict onto the received record's final stage.

    Returns the decorated node's status unchanged, always: this stage records
    an outcome, it never decides one.  A failure to record it is logged at
    ERROR and does not change the verdict the sender is answered with —
    over-retaining a refused body is a bookkeeping fault, while rewriting the
    verdict would answer the sender for the wrong reason (MV-01-007).
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(
        self,
        child: py_trees.behaviour.Behaviour,
        name: str = "SettleReceivedOutcome",
    ) -> None:
        super().__init__(name=name, child=child)
        self.logger = node_logger(self)  # type: ignore[assignment]
        self._blackboard = py_trees.blackboard.Client(name=name)
        for key in (
            KEY_DISPOSITION,
            KEY_EVENT,
            KEY_FAILURE_REASON,
            KEY_OUTCOME,
        ):
            self._blackboard.register_key(
                key, access=py_trees.common.Access.READ
            )

    def _read(self, key: str) -> Any | None:
        """*key*'s value, or ``None`` when no node has written it."""
        try:
            return self._blackboard.get(key)
        except KeyError:
            return None

    def update(self) -> Status:
        # BT-HELPER-01: this is the node's only try/except.  Everything the
        # stage can raise is a bookkeeping fault, never the sender's.
        try:
            self._settle()
        except Exception:
            self.logger.exception(
                "%s: the received record's final stage was not recorded; the"
                " delivery's verdict stands",
                self.name,
            )
        return self.decorated.status

    def _settle(self) -> None:
        """Record the final stage for this delivery's verdict."""
        disposition = self._read(KEY_DISPOSITION)
        if disposition is None:
            # The dispatch raised, or returned no verdict: nothing judged
            # the message, so the record keeps its body for the re-run
            # (ADR-0151, ADR-0154).
            self.logger.debug(
                "%s: no handler verdict, so the received record is left as"
                " it is, with its body",
                self.name,
            )
            return
        if disposition is HandlerDisposition.DEFERRED:
            self.logger.debug(
                "%s: deferred — the received record stays in holding",
                self.name,
            )
            return
        event = self._read(KEY_EVENT)
        if not isinstance(event, VultronEvent):
            self.logger.error(
                "%s: a %s delivery with no received event on the blackboard,"
                " so no received record names it (ARCH-15-001)",
                self.name,
                disposition,
            )
            return
        port = self._port(event)
        if port is None:
            return
        if disposition in _ARCHIVES:
            port.apply(event.activity_id)
            return
        # Refused, an unhandled semantic type included: nothing applies the
        # message, so the receiver keeps a receipt and not the body
        # (CLP-10-018, CLP-10-074).
        port.refuse(
            event.activity_id,
            sender_id=event.actor_id,
            reason=self._read(KEY_FAILURE_REASON) or "refused",
            received_body=event.received_evidence,
        )

    def _port(self, event: VultronEvent) -> ReceivedOutcomePort | None:
        """The wired received-outcome port, or ``None`` when none is."""
        port = self._read(KEY_OUTCOME)
        if port is None:
            # The two production pipelines both wire the port
            # (``_InboxRun``, the queue drain); a run without it leaves the
            # record as it is, which over-retains rather than losing anything.
            self.logger.debug(
                "%s: no received-outcome port is wired, so activity_id=%s"
                " keeps its record as it is",
                self.name,
                event.activity_id,
            )
            return None
        if not isinstance(port, ReceivedOutcomePort):
            raise VultronWiringError(
                f"{self.name}: {type(port).__name__} on"
                f" '{KEY_OUTCOME}' is no ReceivedOutcomePort, so the received"
                " record's final stage cannot be written (ARCH-15-001)"
            )
        return port


__all__ = ["SettleReceivedOutcome"]
