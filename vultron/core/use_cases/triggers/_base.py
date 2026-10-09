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

"""Abstract base classes for BT-backed trigger use cases.

Three-level hierarchy:

- :class:`SvcBTTriggerBase` — top-level template method that owns the
  ``__init__``, the TriggerActivityPort guard, BTBridge construction, BT
  execution, and the failure guard.  Generic in the :class:`TriggerResult`
  subtype its verb returns (UCORG-05-007).  Subclasses implement
  ``_prepare()``, ``_build_tree()``, ``_handle_result()`` and
  ``_build_result()``.

- :class:`SvcActivityTriggerBase` — binds the result to
  :class:`ActivityResult` and builds it from the captured activity and the
  emitting actor; the base of every verb whose body is
  ``{"activity", "emitting_actor_id"}``.

- :class:`SvcEmbargoTriggerBase` — extends ``SvcActivityTriggerBase`` with a
  concrete ``_handle_result()`` for the two role arms of an embargo trigger
  tree (EP-09-008): a non-manager's pending assertion is recorded, and a
  CASE_MANAGER's ``lifecycle_result`` is validated and handed to the
  per-operation ``_log_lifecycle_result()`` hook.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import py_trees.behaviour
from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.pending_assertion import (
    ASSERTED_ACTIVITY_KEY,
    record_pending_assertion,
    suppressed_repeat_reason,
)
from vultron.core.models.use_case_result import ActivityResult, TriggerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.services.embargo_lifecycle import EmbargoLifecycleResult
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class SvcBTTriggerBase[TriggerResultT: TriggerResult](ABC):
    """Abstract base for all BT-backed trigger use cases.

    The :meth:`execute` template method orchestrates the common workflow:

    1. Initialise transient state (``_captured``, ``_result_out``,
       ``_actor_id``).
    2. Call :meth:`_prepare` (abstract) — subclass resolves domain objects and
       sets ``self._actor_id``.
    3. Validate that a ``TriggerActivityPort`` was supplied and store it as
       ``self._factory``.
    4. Construct a :class:`~vultron.core.behaviors.bridge.BTBridge`.
    5. Call :meth:`_build_tree` (abstract) — subclass returns the BT.
    6. Execute the BT via ``bridge.execute_with_setup``.
    7. Raise on failure.
    8. Call :meth:`_handle_result` (abstract) — subclass logs/extracts output.
    9. Return :meth:`_build_result` (abstract) — the verb's typed
       :class:`TriggerResult` subtype, ``TriggerResultT``.
    """

    _requires_trigger_activity: bool = True

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: object,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        sync_port: SyncActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity
        # Every tree that commits a ledger entry renders its payload snapshot
        # through this port; core cannot produce the AS2 shape itself
        # (ARCH-20-001, CLP-07-009).
        self._wire_render_port = wire_render_port
        # A tree that commits a ledger entry fans it out through this port
        # (SYNC-02-002): the ``sync-log-entry`` verb's tree, and every
        # embargo trigger the CASE_MANAGER runs (EP-09-008, #4085).
        self._sync_port = sync_port

    def execute(self) -> TriggerResultT:
        """Template method: prepare → gate → run BT → handle result."""
        self._captured: dict = {}
        self._result_out: dict[str, object] = {}
        self._actor_id: str = ""

        self._prepare()

        if self._requires_trigger_activity and self._trigger_activity is None:
            raise RuntimeError(
                f"{type(self).__name__} requires a TriggerActivityPort"
            )
        if self._trigger_activity is not None:
            self._factory: TriggerActivityPort = self._trigger_activity

        if (suppressed := self._suppressed_duplicate()) is not None:
            return suppressed

        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
        tree = self._build_tree()
        result = bridge.execute_with_setup(
            tree,
            actor_id=self._actor_id,
            **self._extra_execute_kwargs(),
        )

        if result.status != Status.SUCCESS:
            error = self._result_out.get("error")
            if isinstance(error, Exception):
                raise error
            raise VultronValidationError(
                f"{type(self).__name__} failed:"
                f" {BTBridge.get_failure_reason(tree)}"
            )

        self._handle_result()

        try:
            return self._build_result()
        except ValidationError as exc:
            # A result the subtype refuses is a bug in the use case or a node
            # (a non-string id, an unexpected key), not a client fault: the
            # routers translate pydantic ``ValidationError`` to 422, so it is
            # re-raised as the internal error it is.
            raise RuntimeError(
                f"{type(self).__name__} built an invalid result: {exc}"
            ) from exc

    @abstractmethod
    def _prepare(self) -> None:
        """Pre-BT validation and setup.

        Implementations MUST set ``self._actor_id`` to the resolved full actor
        URI and may set additional operation-specific attributes (e.g.
        ``self._case``, ``self._embargo``).  Raise domain exceptions on invalid
        input.
        """

    @abstractmethod
    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        """Construct and return the operation-specific BT.

        Called after ``_prepare()`` and after ``self._factory`` is set.
        Implementations may close over ``self._captured`` and
        ``self._result_out`` for BT I/O.
        """

    @abstractmethod
    def _handle_result(self) -> None:
        """Post-BT logging or result extraction.

        Called only when the BT succeeded.
        """

    @abstractmethod
    def _build_result(self) -> TriggerResultT:
        """Assemble the verb's typed result from the captured BT output.

        Called last, after :meth:`_handle_result`, and only when the BT
        succeeded.  The returned subtype declares exactly the keys the verb's
        response body carries (UCORG-05-005).
        """

    def _activity_fields(self) -> dict[str, Any]:
        """The two keys every :class:`ActivityResult` body carries.

        ``activity`` is what the tree captured (``None`` when it captured
        nothing) and ``emitting_actor_id`` the actor ``_prepare()`` resolved.
        Subtypes that extend the activity body splat this into their result.
        """
        return {
            "activity": self._captured.get("activity"),
            "emitting_actor_id": self._actor_id,
        }

    def _output_id(self, key: str) -> str | None:
        """Return the id the BT wrote to ``_result_out[key]``, or ``None``.

        BT output is ``dict[str, object]``; a result field is typed, so a
        value that is neither a string nor absent is a node bug and raises
        rather than being coerced into the body.
        """
        value = self._result_out.get(key)
        if value is not None and not isinstance(value, str):
            raise RuntimeError(
                f"{type(self).__name__}: BT output {key!r} is"
                f" {type(value).__name__}, expected str"
            )
        return value

    def _suppressed_duplicate(self) -> TriggerResultT | None:
        """Return a result in place of running the tree, or ``None`` to run it.

        Called after :meth:`_prepare`.  A trigger that records a pending
        assertion overrides this to answer a duplicate inside the window
        without re-emitting it (SYNC-11-002).  The default runs the tree.
        """
        return None

    def _extra_execute_kwargs(self) -> dict[str, Any]:
        """Additional kwargs passed to ``bridge.execute_with_setup``.

        Override to inject extra blackboard context required by specific BT
        trees (e.g. ``{"case_id": self._case_id}`` for trees whose nodes
        read ``case_id`` from the blackboard).
        """
        return {}


class SvcActivityTriggerBase(SvcBTTriggerBase[ActivityResult]):
    """BT-backed trigger whose body is the emitted activity and its emitter.

    Binds :class:`SvcBTTriggerBase` to :class:`ActivityResult` and builds it
    from the activity the tree captured (``None`` when it captured nothing)
    and the actor ``_prepare()`` resolved.  Verbs whose body differs bind the
    generic base to their own subtype instead.
    """

    def _build_result(self) -> ActivityResult:
        return ActivityResult(**self._activity_fields())


class SvcEmbargoTriggerBase(SvcActivityTriggerBase):
    """Abstract base for embargo trigger use cases.

    A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008), so
    the tree runs one of two arms and :meth:`_handle_result` handles both:

    - **Asked the CASE_MANAGER** (the tree wrote
      ``result_out[ASSERTED_ACTIVITY_KEY]``): records the queued activity in
      the pending-assertion store through the helper the note trigger also
      uses (SYNC-11-002, ASK-04-008).  No EM state was written, so there is
      no lifecycle result.
    - **Decided as the CASE_MANAGER**: extracts and validates
      ``lifecycle_result``, raising ``RuntimeError`` if it is absent or the
      wrong type, stores it as ``self._lifecycle_result`` and delegates to the
      per-operation :meth:`_log_lifecycle_result` hook.

    A repeat of an assertion still pending — the same :meth:`_assertion_subject`
    asked again inside the window — is suppressed before the tree runs and
    reported with no activity (:meth:`_suppressed_duplicate`).
    """

    #: Ledger ``event_type`` of the activity this trigger emits; the key the
    #: pending assertion and the manager's commit share (SYNC-11-003).
    _assertion_event_type: ClassVar[str]

    _case: VulnerabilityCase

    def _asserted_event_type(self) -> str:
        """The ledger ``event_type`` this run asserts.

        :attr:`_assertion_event_type` by default; a trigger whose activity
        depends on who runs it overrides this (the case owner's answer is its
        decision for the case, ADR-0122).
        """
        return self._assertion_event_type

    @abstractmethod
    def _assertion_subject(self) -> str | None:
        """What a repeat of this trigger would be about, or ``None``.

        The proposal an answer names, the embargo a teardown ends, the terms a
        proposal offers.  ``None`` when there is nothing to compare (the
        tree's own guard then refuses the request).
        """

    def _suppressed_duplicate(self) -> ActivityResult | None:
        subject = self._assertion_subject()
        if subject is None:
            return None
        reason = suppressed_repeat_reason(
            self._actor_id,
            self._case.id_,
            self._asserted_event_type(),
            subject,
        )
        if reason is None:
            return None
        logger.info("%s: %s", type(self).__name__, reason)
        return ActivityResult(activity=None, emitting_actor_id=self._actor_id)

    def _handle_result(self) -> None:
        asserted_id = self._output_id(ASSERTED_ACTIVITY_KEY)
        if asserted_id is not None:
            record_pending_assertion(
                self._actor_id,
                self._case.id_,
                self._asserted_event_type(),
                asserted_id,
                subject_id=self._assertion_subject(),
            )
            return
        lifecycle_result = self._result_out.get("lifecycle_result")
        if not isinstance(lifecycle_result, EmbargoLifecycleResult):
            raise RuntimeError(  # noqa: TRY004  # ruff-baseline #3353
                f"{type(self).__name__} did not capture lifecycle result"
                " in BT output"
            )
        self._lifecycle_result: EmbargoLifecycleResult = lifecycle_result
        self._log_lifecycle_result()

    @abstractmethod
    def _log_lifecycle_result(self) -> None:
        """Log the per-operation lifecycle result after BT execution."""
