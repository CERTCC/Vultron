#!/usr/bin/env python
"""BT pipeline leaf nodes for inbox orchestration.

Each node is responsible for exactly one pipeline step.  Intermediate
state is communicated via the py_trees blackboard using the
``inbox_*`` key namespace.

Blackboard keys (all prefixed ``inbox_``):

Input keys (written by :func:`~...process_payload` before BT execution):
    inbox_payload       — raw payload passed to process_payload
    inbox_ingress       — IngressPayloadAdapter instance
    inbox_dispatch      — DispatchAdapter instance
    inbox_queue         — PendingCaseQueuePort instance or None

Intermediate keys (written by pipeline nodes during execution):
    inbox_activity      — parsed as_Activity
    inbox_event         — VultronEvent with extracted semantics
    inbox_context_id    — case context ID string or None

Output keys (written by pipeline nodes on completion or failure):
    inbox_outcome_status   — an ``InboxOutcomeStatus`` member
    inbox_failure_reason   — human-readable reason when not processed

Steps 5 and 6 (dispatch and the processed outcome) live in
:mod:`~vultron.core.behaviors.inbox.nodes.dispatch`, which also owns the
handler-verdict-to-outcome mapping (HP-01-004).

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

import logging
from typing import Any

from py_trees.common import Status
from py_trees.ports import BehaviourWithPorts, NoDataAvailable, PortInformation

from vultron.core.behaviors.inbox.models import InboxOutcomeStatus
from vultron.core.models.events import (
    is_case_bootstrap,
    resolve_case_context_id,
)
from vultron.semantic_registry import extract_event

# Blackboard key constants — single source of truth used by both nodes
# and process_payload setup/cleanup.
KEY_PAYLOAD = "inbox_payload"
KEY_INGRESS = "inbox_ingress"
KEY_DISPATCH = "inbox_dispatch"
KEY_QUEUE = "inbox_queue"
KEY_ACTIVITY = "inbox_activity"
KEY_EVENT = "inbox_event"
KEY_CONTEXT_ID = "inbox_context_id"
KEY_OUTCOME_STATUS = "inbox_outcome_status"
KEY_FAILURE_REASON = "inbox_failure_reason"

# All keys managed by the inbox pipeline (for setup and cleanup).
ALL_INBOX_KEYS = (
    KEY_PAYLOAD,
    KEY_INGRESS,
    KEY_DISPATCH,
    KEY_QUEUE,
    KEY_ACTIVITY,
    KEY_EVENT,
    KEY_CONTEXT_ID,
    KEY_OUTCOME_STATUS,
    KEY_FAILURE_REASON,
)


class _InboxNodeWithPorts(BehaviourWithPorts):
    """Base class for typed-Ports inbox pipeline nodes.

    Declares the shared outcome output ports (inbox_outcome_status,
    inbox_failure_reason) and wires them to the flat blackboard keys
    used by process_payload for cleanup.  Subclasses override
    _domain_port_remappings() to add their domain-specific port-to-key
    mappings, and declare their own INPUT_PORTS / OUTPUT_PORTS.

    Per specs/inbox-orchestration.yaml IO-02-002.
    Per specs/behavior-tree-node-design.yaml BTND-03-012.
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        """Domain-specific port-to-absolute-key remappings for this subclass."""
        return {}

    INPUT_PORTS: dict[str, PortInformation] = {}

    OUTPUT_PORTS: dict[str, PortInformation] = {
        KEY_OUTCOME_STATUS: PortInformation(data_type=str, required=False),
        KEY_FAILURE_REASON: PortInformation(data_type=str, required=False),
    }

    def setup(self, **kwargs: Any) -> None:
        self.setup_ports(
            port_remappings={
                KEY_OUTCOME_STATUS: f"/{KEY_OUTCOME_STATUS}",
                KEY_FAILURE_REASON: f"/{KEY_FAILURE_REASON}",
                **self._domain_port_remappings(),
            }
        )

    def _record_outcome(
        self, status: InboxOutcomeStatus, reason: str
    ) -> Status:
        """Write a non-processed outcome via typed output ports; return FAILURE.

        Logged at INFO, not WARNING: the driving adapter logs every rejected
        ``InboxOutcome`` at WARNING with the actor and activity ids
        (UCORG-05-013), so a node-level warning would report it twice.
        """
        self.feedback_message = reason
        self._set_output(KEY_OUTCOME_STATUS, status)
        self._set_output(KEY_FAILURE_REASON, reason)
        self.logger.info("%s: %s — %s", self.name, status, reason)
        return Status.FAILURE

    def _reject(self, reason: str) -> Status:
        return self._record_outcome(InboxOutcomeStatus.REJECTED, reason)

    def _defer(self, reason: str) -> Status:
        return self._record_outcome(InboxOutcomeStatus.DEFERRED, reason)

    def update(self) -> Status:
        raise NotImplementedError


class ParsePayloadNode(_InboxNodeWithPorts):
    """Step 1: parse raw payload into a typed Activity.

    Reads ``inbox_payload`` and ``inbox_ingress``; writes
    ``inbox_activity``.  Returns FAILURE with status ``rejected`` when
    parsing fails.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        KEY_PAYLOAD: PortInformation(data_type=object, required=True),
        KEY_INGRESS: PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        **_InboxNodeWithPorts.OUTPUT_PORTS,
        KEY_ACTIVITY: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            KEY_PAYLOAD: f"/{KEY_PAYLOAD}",
            KEY_INGRESS: f"/{KEY_INGRESS}",
            KEY_ACTIVITY: f"/{KEY_ACTIVITY}",
        }

    def update(self) -> Status:
        try:
            payload = self.get_input(KEY_PAYLOAD)
            ingress = self.get_input(KEY_INGRESS)
        except (KeyError, NoDataAvailable) as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            activity = ingress.parse(payload)
        except Exception as exc:
            return self._reject(f"Parse raised exception: {exc}")

        if activity is None:
            return self._reject("Ingress adapter returned None from parse()")

        self._set_output(KEY_ACTIVITY, activity)
        self.logger.debug(
            "%s: parsed activity type=%s id=%s",
            self.name,
            getattr(activity, "type_", "?"),
            getattr(activity, "id_", "?"),
        )
        return Status.SUCCESS


class RehydrateActivityNode(_InboxNodeWithPorts):
    """Step 2: resolve nested object references in the parsed Activity.

    Reads ``inbox_activity`` and ``inbox_ingress``; overwrites
    ``inbox_activity`` with the rehydrated result.

    The read and write of ``inbox_activity`` use separate port names:
    ``inbox_activity_in`` (READ) and ``inbox_activity`` (WRITE), both
    remapped to ``/inbox_activity`` so the same blackboard slot is
    used — this makes the read-modify-write data flow explicit in the
    typed-Ports contract.
    """

    # Port alias for reading the pre-rehydration activity value.
    _PORT_ACTIVITY_IN = "inbox_activity_in"

    INPUT_PORTS: dict[str, PortInformation] = {
        _PORT_ACTIVITY_IN: PortInformation(data_type=object, required=True),
        KEY_INGRESS: PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        **_InboxNodeWithPorts.OUTPUT_PORTS,
        KEY_ACTIVITY: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            # Both read alias and write port remap to the same physical key.
            cls._PORT_ACTIVITY_IN: f"/{KEY_ACTIVITY}",
            KEY_INGRESS: f"/{KEY_INGRESS}",
            KEY_ACTIVITY: f"/{KEY_ACTIVITY}",
        }

    def update(self) -> Status:
        try:
            activity = self.get_input(self._PORT_ACTIVITY_IN)
            ingress = self.get_input(KEY_INGRESS)
        except (KeyError, NoDataAvailable) as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            rehydrated = ingress.rehydrate(activity)
        except Exception as exc:
            return self._reject(f"Rehydrate raised exception: {exc}")

        self._set_output(KEY_ACTIVITY, rehydrated)
        self.logger.debug(
            "%s: rehydrated activity id=%s",
            self.name,
            getattr(rehydrated, "id_", "?"),
        )
        return Status.SUCCESS


class ExtractSemanticsNode(_InboxNodeWithPorts):
    """Step 3: extract MessageSemantics from the rehydrated Activity.

    Reads ``inbox_activity``; writes ``inbox_event`` and
    ``inbox_context_id``.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        KEY_ACTIVITY: PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        **_InboxNodeWithPorts.OUTPUT_PORTS,
        KEY_EVENT: PortInformation(data_type=object, required=False),
        KEY_CONTEXT_ID: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            KEY_ACTIVITY: f"/{KEY_ACTIVITY}",
            KEY_EVENT: f"/{KEY_EVENT}",
            KEY_CONTEXT_ID: f"/{KEY_CONTEXT_ID}",
        }

    def update(self) -> Status:
        try:
            activity: Any = self.get_input(KEY_ACTIVITY)
        except (KeyError, NoDataAvailable) as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            event = extract_event(activity)
        except Exception as exc:
            return self._reject(f"extract_event raised exception: {exc}")

        self._set_output(KEY_EVENT, event)

        # Resolve the case this activity is scoped to.  See
        # ``vultron.core.models.events.case_context`` for the precedence rules
        # and why bootstrap activities resolve from their inline case object
        # rather than the AS2 ``context`` field.
        # NB: ``context`` is the AS2 case-scoping field; ``context_`` is the
        # JSON-LD ``@context`` namespace declaration.  Only the former can
        # carry a case reference.
        context_id = resolve_case_context_id(
            event, wire_context=getattr(activity, "context", None)
        )
        self._set_output(KEY_CONTEXT_ID, context_id)

        self.logger.debug(
            "%s: extracted semantics=%s context_id=%s",
            self.name,
            event.semantic_type,
            context_id,
        )
        return Status.SUCCESS


class DeferCheckNode(_InboxNodeWithPorts):
    """Step 4: defer activity when its case context is not yet known.

    If a case context ID is present, the activity semantic is not one of
    the case-bootstrap semantics (see
    :data:`~vultron.core.models.events.case_context.CASE_BOOTSTRAP_SEMANTICS`),
    and the case is not yet locally available, the activity is either
    queued for later replay (``deferred`` outcome) or dropped when the
    queue has expired (``rejected`` outcome).

    Passes through to SUCCESS when no deferral is needed.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        KEY_EVENT: PortInformation(data_type=object, required=True),
        KEY_CONTEXT_ID: PortInformation(data_type=object, required=False),
        KEY_QUEUE: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            KEY_EVENT: f"/{KEY_EVENT}",
            KEY_CONTEXT_ID: f"/{KEY_CONTEXT_ID}",
            KEY_QUEUE: f"/{KEY_QUEUE}",
        }

    def update(self) -> Status:  # noqa: C901
        try:
            event = self.get_input(KEY_EVENT)
        except (KeyError, NoDataAvailable) as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        # context_id can legitimately be None (no case scope on the activity).
        try:
            context_id: str | None = self.get_input(KEY_CONTEXT_ID)
        except (NotImplementedError, NoDataAvailable):
            context_id = None

        try:
            queue = self.get_input(KEY_QUEUE)
        except (NotImplementedError, NoDataAvailable, KeyError):
            queue = None

        # No deferral needed when there is no case context, when
        # processing a bootstrap itself, or when no queue port is
        # available.  Deferring a bootstrap would deadlock: nothing else
        # can make its case known locally.
        if context_id is None or is_case_bootstrap(event) or queue is None:
            return Status.SUCCESS

        # Non-URI context_id (e.g. a genesis hash from Reject(CaseLedgerEntry))
        # is not a deferrable case reference — skip deferral.
        if ":" not in context_id:
            return Status.SUCCESS

        if queue.is_case_known(context_id):
            return Status.SUCCESS

        # Case is not yet known — check if the pending queue has expired.
        if queue.check_and_expire(context_id):
            reason = (
                f"Pre-bootstrap queue for case '{context_id}' expired; "
                "resend required after new bootstrap"
            )
            return self._reject(reason)

        # Queue for replay when bootstrap arrives.
        queue.queue(
            activity_id=event.activity_id,
            case_id=context_id,
            case_actor_id=event.actor_id,
        )
        reason = f"Deferred: case '{context_id}' not yet known locally"
        return self._defer(reason)
