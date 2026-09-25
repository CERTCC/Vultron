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

from vultron.core.behaviors.inbox.models import InboxOutcomeStatus
from vultron.core.behaviors.inbox.nodes.pipeline import (
    KEY_CONTEXT_ID,
    KEY_DISPATCH,
    KEY_EVENT,
    KEY_OUTCOME_STATUS,
    KEY_QUEUE,
    _InboxNodeWithPorts,
)
from vultron.core.models.events import VultronEvent, is_case_bootstrap
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


class DispatchNode(_InboxNodeWithPorts):
    """Step 5: dispatch the domain event and map the handler's verdict.

    The returned ``HandlerResult`` decides the outcome (UCORG-05-011), not the
    absence of an exception: ``APPLIED``/``SKIPPED`` return SUCCESS so
    :class:`BuildOutcomeNode` records ``processed``; ``DEFERRED`` records
    ``deferred`` and ``REFUSED`` records ``rejected`` with the handler's
    ``reason``, both returning FAILURE. A dispatch that returns anything but a
    ``HandlerResult`` is rejected — no verdict is not a success.

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
        or deferred has not made the case locally available. A replay failure
        is logged and swallowed rather than escaping ``update()`` (MV-01-007):
        the bootstrap itself was applied, so it must not be reported as
        rejected.
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
            try:
                queue.replay(context_id)
            except Exception:
                self.logger.error(
                    "%s: replay failed for case '%s' after bootstrap"
                    " activity_id=%s",
                    self.name,
                    context_id,
                    event.activity_id,
                    exc_info=True,
                )
                return
            self.logger.info(
                "%s: triggered replay for case '%s'", self.name, context_id
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
            # A raise is not a verdict: keep the traceback so a programming
            # error stays distinguishable from a handler's REFUSED.
            self.logger.warning(
                "%s: dispatch raised for activity_id=%s",
                self.name,
                getattr(event, "activity_id", None),
                exc_info=True,
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

        self._replay_after_bootstrap(event)
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
