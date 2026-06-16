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
    inbox_outcome_status   — one of "processed", "deferred", "rejected"
    inbox_failure_reason   — human-readable reason when not processed

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

import py_trees
from py_trees.common import Access, Status

from vultron.core.models.events import MessageSemantics
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


class _InboxNode(py_trees.behaviour.Behaviour):
    """Base class for inbox pipeline nodes.

    Provides a properly-wired logger and helper methods for writing
    failure outcomes to the blackboard.
    """

    logger: logging.Logger  # type: ignore[assignment]
    blackboard: py_trees.blackboard.Client

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        # Replace py_trees' parentless logger with a hierarchy-wired one.
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def _reject(self, reason: str) -> Status:
        """Write rejected outcome to blackboard and return FAILURE."""
        self.feedback_message = reason
        try:
            self.blackboard.inbox_outcome_status = "rejected"
            self.blackboard.inbox_failure_reason = reason
        except Exception:
            pass
        self.logger.warning("%s: rejected — %s", self.name, reason)
        return Status.FAILURE


class ParsePayloadNode(_InboxNode):
    """Step 1: parse raw payload into a typed Activity.

    Reads ``inbox_payload`` and ``inbox_ingress``; writes
    ``inbox_activity``.  Returns FAILURE with status ``rejected`` when
    parsing fails.
    """

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(KEY_PAYLOAD, access=Access.READ)
        self.blackboard.register_key(KEY_INGRESS, access=Access.READ)
        self.blackboard.register_key(KEY_ACTIVITY, access=Access.WRITE)
        self.blackboard.register_key(KEY_OUTCOME_STATUS, access=Access.WRITE)
        self.blackboard.register_key(KEY_FAILURE_REASON, access=Access.WRITE)

    def update(self) -> Status:
        try:
            payload = self.blackboard.inbox_payload
            ingress = self.blackboard.inbox_ingress
        except KeyError as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            activity = ingress.parse(payload)
        except Exception as exc:
            return self._reject(f"Parse raised exception: {exc}")

        if activity is None:
            return self._reject("Ingress adapter returned None from parse()")

        self.blackboard.inbox_activity = activity
        self.logger.debug(
            "%s: parsed activity type=%s id=%s",
            self.name,
            getattr(activity, "type_", "?"),
            getattr(activity, "id_", "?"),
        )
        return Status.SUCCESS


class RehydrateActivityNode(_InboxNode):
    """Step 2: resolve nested object references in the parsed Activity.

    Reads ``inbox_activity`` and ``inbox_ingress``; overwrites
    ``inbox_activity`` with the rehydrated result.
    """

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(KEY_ACTIVITY, access=Access.WRITE)
        self.blackboard.register_key(KEY_INGRESS, access=Access.READ)
        self.blackboard.register_key(KEY_OUTCOME_STATUS, access=Access.WRITE)
        self.blackboard.register_key(KEY_FAILURE_REASON, access=Access.WRITE)

    def update(self) -> Status:
        try:
            activity = self.blackboard.inbox_activity
            ingress = self.blackboard.inbox_ingress
        except KeyError as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            rehydrated = ingress.rehydrate(activity)
        except Exception as exc:
            return self._reject(f"Rehydrate raised exception: {exc}")

        self.blackboard.inbox_activity = rehydrated
        self.logger.debug(
            "%s: rehydrated activity id=%s",
            self.name,
            getattr(rehydrated, "id_", "?"),
        )
        return Status.SUCCESS


class ExtractSemanticsNode(_InboxNode):
    """Step 3: extract MessageSemantics from the rehydrated Activity.

    Reads ``inbox_activity``; writes ``inbox_event`` and
    ``inbox_context_id``.
    """

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(KEY_ACTIVITY, access=Access.READ)
        self.blackboard.register_key(KEY_EVENT, access=Access.WRITE)
        self.blackboard.register_key(KEY_CONTEXT_ID, access=Access.WRITE)
        self.blackboard.register_key(KEY_OUTCOME_STATUS, access=Access.WRITE)
        self.blackboard.register_key(KEY_FAILURE_REASON, access=Access.WRITE)

    def update(self) -> Status:
        try:
            activity: Any = self.blackboard.inbox_activity
        except KeyError as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            event = extract_event(activity)
        except Exception as exc:
            return self._reject(f"extract_event raised exception: {exc}")

        self.blackboard.inbox_event = event

        # Resolve context_id: prefer event.context_id, fall back to
        # activity.context_ (the AS2 context field — but only when it is
        # a non-default, case-scoped URI), and finally to event.object_.id_
        # for bootstrap (ANNOUNCE_VULNERABILITY_CASE) activities where the
        # case ID is carried in the announce object rather than the context.
        context_id: str | None = event.context_id
        if context_id is None:
            context = getattr(activity, "context_", None)
            # Skip the default AS2 namespace URI — it is not a case ID.
            if (
                isinstance(context, str)
                and context
                and not context.startswith("https://www.w3.org/ns/")
            ):
                context_id = context
            elif context is not None and not isinstance(context, str):
                context_id = getattr(context, "id_", None)
        if (
            context_id is None
            and event.semantic_type
            == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
            and event.object_ is not None
        ):
            # Bootstrap case: case ID is in the announced VulnerabilityCase.
            candidate = getattr(event.object_, "id_", None)
            if isinstance(candidate, str) and candidate:
                context_id = candidate
        self.blackboard.inbox_context_id = context_id

        self.logger.debug(
            "%s: extracted semantics=%s context_id=%s",
            self.name,
            event.semantic_type,
            context_id,
        )
        return Status.SUCCESS


class DeferCheckNode(_InboxNode):
    """Step 4: defer activity when its case context is not yet known.

    If a case context ID is present, the activity semantic is not the
    bootstrap ``ANNOUNCE_VULNERABILITY_CASE``, and the case is not yet
    locally available, the activity is either queued for later replay
    (``deferred`` outcome) or dropped when the queue has expired
    (``rejected`` outcome).

    Passes through to SUCCESS when no deferral is needed.
    """

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(KEY_EVENT, access=Access.READ)
        self.blackboard.register_key(KEY_CONTEXT_ID, access=Access.READ)
        self.blackboard.register_key(KEY_QUEUE, access=Access.READ)
        self.blackboard.register_key(KEY_OUTCOME_STATUS, access=Access.WRITE)
        self.blackboard.register_key(KEY_FAILURE_REASON, access=Access.WRITE)

    def update(self) -> Status:
        try:
            event = self.blackboard.inbox_event
            context_id: str | None = self.blackboard.inbox_context_id
        except KeyError as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            queue = self.blackboard.inbox_queue
        except KeyError:
            queue = None

        # No deferral needed when there is no case context, when
        # processing the bootstrap itself, or when no queue port is
        # available.
        is_bootstrap = (
            event.semantic_type == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
        )
        if context_id is None or is_bootstrap or queue is None:
            return Status.SUCCESS

        if queue.is_case_known(context_id):
            return Status.SUCCESS

        # Case is not yet known — check if the pending queue has expired.
        if queue.check_and_expire(context_id):
            reason = (
                f"Pre-bootstrap queue for case '{context_id}' expired; "
                "resend required after new bootstrap"
            )
            self.feedback_message = reason
            self.blackboard.inbox_outcome_status = "rejected"
            self.blackboard.inbox_failure_reason = reason
            self.logger.warning("%s: %s", self.name, reason)
            return Status.FAILURE

        # Queue for replay when bootstrap arrives.
        queue.queue(
            activity_id=event.activity_id,
            case_id=context_id,
            case_actor_id=event.actor_id,
        )
        reason = f"Deferred: case '{context_id}' not yet known locally"
        self.feedback_message = reason
        self.blackboard.inbox_outcome_status = "deferred"
        self.blackboard.inbox_failure_reason = reason
        self.logger.info("%s: %s", self.name, reason)
        return Status.FAILURE


class DispatchNode(_InboxNode):
    """Step 5: dispatch the domain event to the appropriate use case.

    After a successful bootstrap dispatch, triggers replay of any
    activities that were deferred pending this case's local replica.
    """

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(KEY_EVENT, access=Access.READ)
        self.blackboard.register_key(KEY_DISPATCH, access=Access.READ)
        self.blackboard.register_key(KEY_CONTEXT_ID, access=Access.READ)
        self.blackboard.register_key(KEY_QUEUE, access=Access.READ)
        self.blackboard.register_key(KEY_OUTCOME_STATUS, access=Access.WRITE)
        self.blackboard.register_key(KEY_FAILURE_REASON, access=Access.WRITE)

    def update(self) -> Status:
        try:
            event = self.blackboard.inbox_event
            dispatch = self.blackboard.inbox_dispatch
        except KeyError as exc:
            return self._reject(f"Missing blackboard key: {exc}")

        try:
            dispatch.dispatch(event)
        except Exception as exc:
            return self._reject(f"Dispatch raised exception: {exc}")

        self.logger.info(
            "%s: dispatched %s activity_id=%s",
            self.name,
            event.semantic_type,
            event.activity_id,
        )

        # After bootstrap, replay any activities that were held pending
        # this case's local replica becoming available.
        is_bootstrap = (
            event.semantic_type == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
        )
        try:
            context_id: str | None = self.blackboard.inbox_context_id
            queue = self.blackboard.inbox_queue
        except KeyError:
            context_id = None
            queue = None

        if is_bootstrap and context_id is not None and queue is not None:
            queue.replay(context_id)
            self.logger.info(
                "%s: triggered replay for case '%s'", self.name, context_id
            )

        return Status.SUCCESS


class BuildOutcomeNode(_InboxNode):
    """Step 6: record the processed outcome on the blackboard.

    Runs only when all preceding Sequence nodes succeeded.  Writes
    ``inbox_outcome_status = "processed"`` so that :func:`process_payload`
    can assemble the final :class:`InboxOutcome`.
    """

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(KEY_OUTCOME_STATUS, access=Access.WRITE)

    def update(self) -> Status:
        self.blackboard.inbox_outcome_status = "processed"
        self.logger.debug("%s: outcome = processed", self.name)
        return Status.SUCCESS
