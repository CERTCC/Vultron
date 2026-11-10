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


"""The template-method base of every BT-backed trigger use case.

:class:`SvcBTTriggerBase` owns the ``__init__``, the TriggerActivityPort
guard, BTBridge construction, BT execution, and the failure guard.  It is
generic in the :class:`TriggerResult` subtype its verb returns
(UCORG-05-007).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar

import py_trees
from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.bridge.act_instant import open_act
from vultron.core.behaviors.case.case_clock_decisions import (
    case_clock_decisions,
)
from vultron.core.behaviors.case.nodes.clock_decision_stage import (
    create_clock_decision_gate,
)
from vultron.core.models.pending_assertion import (
    ASSERTED_ACTIVITY_KEY,
    record_pending_assertion,
)
from vultron.core.models.use_case_result import TriggerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.clock import ClockPort
from vultron.core.ports.received_activity_loader import ReceivedActivityLoader
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases.triggers._helpers import resolve_case
from vultron.core.use_cases.triggers.request_bodies import CaseTriggerRequest
from vultron.errors import (
    VultronBTInternalError,
    VultronNotFoundError,
    VultronValidationError,
    VultronWiringError,
)


class SvcBTTriggerBase[TriggerResultT: TriggerResult](ABC):
    """Abstract base for all BT-backed trigger use cases.

    The :meth:`execute` template method orchestrates the common workflow,
    all of it one act (ADR-0176): it takes the tree lock, then reads the act
    clock once into :attr:`_at`, and holds the lock until it returns, so the
    checks before the tree judge against the same instant as the tree.

    1. Initialise transient state (``_captured``, ``_result_out``,
       ``_actor_id``).
    2. Call :meth:`_prepare` (abstract) — subclass resolves domain objects and
       sets ``self._actor_id``.
    3. Validate that a ``TriggerActivityPort`` was supplied and store it as
       ``self._factory``.
    4. Construct a :class:`~vultron.core.behaviors.bridge.BTBridge`.
    5. Call :meth:`_build_tree` (abstract) — subclass returns the BT; a
       case-scoped trigger's tree is preceded by the case-wide clock
       decisions (:meth:`_with_case_clock_decisions`).
    6. Execute the BT via ``bridge.execute_with_setup``.
    7. Raise on failure.
    8. Call :meth:`_handle_result` (abstract) — subclass logs/extracts output.
    9. Return :meth:`_build_result` (abstract) — the verb's typed
       :class:`TriggerResult` subtype, ``TriggerResultT``.
    """

    _requires_trigger_activity: bool = True

    #: Whether a case-scoped request's tree takes the case-wide clock
    #: decisions first (the embargo end-time check, EMB-13-003).  ``False``
    #: only for a trigger whose own tree takes that decision's path and must
    #: answer for it: terminate-embargo ends the embargo with
    #: ``END_TIME_REACHED`` itself once the end time has passed (ADR-0122).
    _takes_case_clock_decisions: ClassVar[bool] = True

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: object,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        sync_port: SyncActivityPort | None = None,
        *,
        clock: ClockPort,
    ) -> None:
        self._dl = dl
        self._request = request
        # The act clock, supplied by the composition root and read once, by
        # execute(), after it takes the tree lock (ADR-0176).
        self._clock = clock
        self._trigger_activity = trigger_activity
        # A tree that captures a core object in a ledger snapshot renders it
        # through this port; core cannot produce the AS2 shape itself
        # (ARCH-20-001, CLP-07-009).
        self._wire_render_port = wire_render_port
        # A tree that commits a ledger entry fans it out through this port
        # (SYNC-02-003): the ``sync-log-entry`` verb's tree, and every
        # embargo trigger the CASE_MANAGER runs (EP-09-008, #4085).
        self._sync_port = sync_port

    @property
    def _received_activities(self) -> ReceivedActivityLoader:
        """The port a trigger loads a received activity it answers through.

        The trigger port is also the loader (ADR-0149), so a trigger that
        reads what it received before its tree runs needs it in
        :meth:`_prepare` too.

        Raises:
            VultronWiringError: When no trigger port was supplied.
        """
        if self._trigger_activity is None:
            raise VultronWiringError(
                f"{type(self).__name__} reads a received activity but has no"
                " TriggerActivityPort to load it through (ADR-0149)"
            )
        return self._trigger_activity

    #: This act's instant, read once by :meth:`execute` after it takes the
    #: tree lock — before anything decides anything, and whatever the run
    #: then decides.  Every clock decision this run takes judges against it,
    #: and so does the pending-assertion check in
    #: :meth:`_suppressed_duplicate`, which therefore reads no clock of its
    #: own: the check's verdict cannot move the clock, and thread
    #: interleaving cannot move the verdict (#5591, ADR-0176).  Unset before
    #: :meth:`execute`.
    _at: datetime

    def execute(self) -> TriggerResultT:
        """Run the trigger as one act: lock, read the clock once, then run.

        The tree lock covers the whole invocation, so :meth:`_prepare` and
        :meth:`_suppressed_duplicate` run inside it against the act's
        instant; the lock is re-entrant, so the bridge taking it again is
        safe (ADR-0176).
        """
        with open_act(self._clock) as at:
            self._at = at
            return self._execute_act()

    def _execute_act(self) -> TriggerResultT:
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
        tree = self._with_case_clock_decisions(self._build_tree())
        result = bridge.execute_with_setup(
            tree,
            actor_id=self._actor_id,
            at=self._at,
            **self._extra_execute_kwargs(),
        )

        if result.status != Status.SUCCESS:
            error = self._result_out.get("error")
            if isinstance(error, Exception):
                raise error
            if result.internal_error:
                # A bug or a composition fault (a missing port), not a refused
                # request: never reported as the client's error (ARCH-20-001).
                # The received side classifies it the same way (_bt_verdict).
                raise VultronBTInternalError(
                    f"{type(self).__name__} failed on an internal error:"
                    f" {result.feedback_message}"
                )
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
        response body carries (UCORG-05-015).
        """

    def _record_asserted_activity(
        self,
        case_id: str,
        semantic_type: str,
        subject_id: str | None = None,
    ) -> bool:
        """Record the activity the tree asserted to the CASE_MANAGER, if any.

        Reads the id the tree's builder wrote under ``ASSERTED_ACTIVITY_KEY``
        and records it in the actor's pending-assertion store under
        *semantic_type*, the key the CASE_MANAGER's commit carries, so the
        announced commit clears it (SYNC-11-002, SYNC-11-003).  Returns
        whether anything was recorded.
        """
        asserted_id = self._output_id(ASSERTED_ACTIVITY_KEY)
        if asserted_id is None:
            return False
        record_pending_assertion(
            self._actor_id,
            case_id,
            semantic_type,
            asserted_id,
            subject_id=subject_id,
        )
        return True

    def _with_case_clock_decisions(
        self, tree: py_trees.behaviour.Behaviour
    ) -> py_trees.behaviour.Behaviour:
        """*tree*, preceded by the case-wide clock decisions for its case.

        An overdue embargo is a fact about the case, whatever the entry
        point: without the end-time check, a trigger such as accepting a
        pending revision would extend an embargo whose end time has passed
        (EMB-13-003, ADR-0135).  So a request that names a case runs the
        same CASE_MANAGER-gated clock-decision stage the received trees run
        after their door guards, as the first step of its one tree
        (BT-15-001, CLP-10-005).  A decision whose commit is refused is
        logged and the trigger's own tree still runs, and judges the case
        as it stands (CLP-10-025).  What :meth:`_prepare` read before the
        decision may be stale by then, so a trigger's tree re-reads the case
        state it acts on in its nodes: the register and the lifecycle refuse
        a change the decision forbade, such as activating a revision the
        termination cancelled.  Unchanged when the trigger takes no clock
        decision (:meth:`_clock_decisions`), names no case, or names one
        this store does not hold, which the trigger reports itself.
        """
        request = self._request
        if not isinstance(request, CaseTriggerRequest):
            return tree
        try:
            case_id = resolve_case(request.case_id, self._dl).id_
        except VultronNotFoundError:
            return tree
        decisions = self._clock_decisions(case_id)
        if not decisions:
            return tree
        return py_trees.composites.Sequence(
            name=f"CaseClockDecisionsThen{tree.name}",
            memory=True,
            children=[
                create_clock_decision_gate(case_id, decisions),
                tree,
            ],
        )

    def _clock_decisions(
        self, case_id: str
    ) -> list[py_trees.behaviour.Behaviour]:
        """The clock decisions this trigger's tree takes first for *case_id*.

        The case-wide decisions (the end-time check, EMB-13-003), unless the
        trigger opts out of them (:attr:`_takes_case_clock_decisions`); a
        trigger family whose acts read more of the case's clock extends the
        list, as the embargo triggers add the overdue-invitation sweep
        (CM-28-029).  An empty list runs the trigger's own tree alone.
        """
        if not self._takes_case_clock_decisions:
            return []
        return case_clock_decisions(case_id)

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
