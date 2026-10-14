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
"""Ending an embargo when its end time passes (ADR-0122, EMB-13).

An embargo reaches its end time through either of two requests, which share
one idempotent termination path, :func:`end_embargo_at_end_time_bt`:

- the CASE_MANAGER's **lazy check** when it next handles the case
  (:func:`end_embargo_if_end_time_passed`, installed as a dispatcher
  :class:`~vultron.core.ports.dispatcher.CaseUpkeep` hook by
  :func:`end_time_case_upkeep`, so it runs before each activity or trigger
  the actor handles for a case) — no scheduler is needed; and
- an **outside request**, such as a Sentinel monitoring embargo timers,
  through the terminate-embargo trigger with ``reason=END_TIME_REACHED``.

Both commit the CASE_MANAGER's ``Remove(EmbargoEvent)`` with ``content``
``END_TIME_REACHED`` and run the full cascade of ``terminate_embargo_bt``.
Whichever arrives second finds the embargo ended, commits nothing and is
answered as already done, so it never reaches the register (invariant 4)::

    EndEmbargoAtEndTimeBT (Selector)
    ├─ EmbargoAlreadyEndedNode          # EM EXITED: already done
    └─ TerminateEmbargoBT               # END_TIME_REACHED, claimed at *now*

    EndEmbargoIfEndTimePassedBT (CASE_MANAGER-gated)
    └─ EndTimeDue (Selector)
       ├─ EndTimeNotPassed (Inverter(EmbargoEndTimePassedNode))
       └─ EndEmbargoAtEndTimeBT
"""

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    EmbargoActivityBuilder,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models._helpers import now_utc
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    has_reached_end_time,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import CaseUpkeep
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.services.embargo_lifecycle import embargo_in_force
from vultron.core.states.em import EM
from vultron.errors import BtNodePreconditionError, VultronError

logger = logging.getLogger(__name__)

#: ``result_out`` key :class:`EmbargoAlreadyEndedNode` sets when the embargo
#: had already ended, so the request is answered as already done.
EMBARGO_ALREADY_ENDED_KEY = "embargo_already_ended"


class EmbargoAlreadyEndedNode(DataLayerConditionWithPorts):
    """SUCCESS when the case's embargo has already ended (EM ``EXITED``).

    The idempotency guard of :func:`end_embargo_at_end_time_bt`: a second
    end-time request finds the ``TERMINATED`` entry and commits nothing
    (ADR-0122).  Sets ``result_out[EMBARGO_ALREADY_ENDED_KEY]``.  FAILURE
    otherwise, a case that cannot be read included, so the termination
    branch runs and reports it.
    """

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._result_out = result_out

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            em_state = read_case_em_state(self.datalayer, self.case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE
        if em_state != EM.EXITED:
            return Status.FAILURE
        self._result_out[EMBARGO_ALREADY_ENDED_KEY] = True
        self.feedback_message = (
            f"Case '{self.case_id}' embargo already ended — nothing to commit"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class EmbargoEndTimePassedNode(DataLayerConditionWithPorts):
    """SUCCESS when the case's embargo in force has reached its end time.

    Compares the ``ACTIVE`` entry's ``end_time`` with *now*; FAILURE when
    there is no embargo in force or its end time is still ahead.  The
    embargo is read inline from the register when carried there, else from
    the store; one that cannot be read is FAILURE with a WARNING, so the
    lazy check never ends an embargo whose terms it cannot see.
    """

    def __init__(
        self, case_id: str, now: datetime, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._now = now

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        try:
            embargo = embargo_in_force(
                cast(CasePersistence, self.datalayer), case
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if embargo is None:
            self.feedback_message = (
                f"No embargo in force on case '{self.case_id}'"
            )
            return Status.FAILURE
        embargo_id = embargo.id_
        if not has_reached_end_time(embargo.end_time, self._now):
            self.feedback_message = (
                f"Embargo '{embargo_id}' on case '{self.case_id}' ends at"
                f" {embargo.end_time.isoformat()}"
            )
            return Status.FAILURE
        self.feedback_message = (
            f"Embargo '{embargo_id}' on case '{self.case_id}' reached its"
            f" end time {embargo.end_time.isoformat()}"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


def end_embargo_at_end_time_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
    now: datetime,
    activity_builder: EmbargoActivityBuilder | None = None,
) -> py_trees.behaviour.Behaviour:
    """The one idempotent end-time termination path (ADR-0122).

    An embargo already ended answers as already done and commits nothing;
    otherwise ``terminate_embargo_bt`` ends it with ``END_TIME_REACHED``
    claimed at *now* — refused before the embargo's end time — and runs the
    full cascade.  *activity_builder* is the trigger's own builder; ``None``
    lets the commit node build the ``Remove`` (the lazy check).
    """
    return py_trees.composites.Selector(
        name="EndEmbargoAtEndTimeBT",
        memory=False,
        children=[
            EmbargoAlreadyEndedNode(case_id=case_id, result_out=result_out),
            terminate_embargo_bt(
                case_id=case_id,
                result_out=result_out,
                termination=EmbargoTermination.end_time_reached(),
                terminated_at=now,
                activity_builder=activity_builder,
            ),
        ],
    )


def end_embargo_if_end_time_passed_tree(
    *, case_id: str, now: datetime, result_out: dict[str, object]
) -> py_trees.behaviour.Behaviour:
    """The CASE_MANAGER's lazy end-time check for *case_id* (ADR-0122).

    Gated on the CASE_MANAGER role, with a case the actor does not hold read
    as "not the manager"; runs :func:`end_embargo_at_end_time_bt` only when
    the embargo in force has reached its end time, and is otherwise
    SUCCESS with nothing done.
    """
    return create_case_manager_gated_tree(
        name="EndEmbargoIfEndTimePassedBT",
        case_id=case_id,
        case_may_be_absent=True,
        children=[
            py_trees.composites.Selector(
                name="EndTimeDue",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="EndTimeNotPassed",
                        child=EmbargoEndTimePassedNode(
                            case_id=case_id, now=now
                        ),
                    ),
                    end_embargo_at_end_time_bt(
                        case_id=case_id, result_out=result_out, now=now
                    ),
                ],
            )
        ],
        body_name="EndEmbargoIfEndTimePassed",
    )


def end_embargo_if_end_time_passed(
    *,
    datalayer: CaseOutboxPersistence,
    case_id: str,
    actor_id: str,
    now: datetime,
    trigger_activity: TriggerActivityPort | None,
    sync_port: SyncActivityPort | None,
    wire_render_port: WireRenderPort | None,
    activity_id: str | None = None,
) -> BTExecutionResult:
    """Run the CASE_MANAGER's lazy end-time check for *case_id* as *actor_id*.

    Called before the CASE_MANAGER handles an activity for the case, so the
    activity is handled against an embargo that has ended when its end time
    passed (ADR-0122).  A non-manager, or a case the actor does not hold,
    does nothing.  Returns the bridge's result; a failed termination leaves
    the case as it was and is retried the next time the case is handled.
    *activity_id* names the inbound activity being handled, for the log.
    """
    result_out: dict[str, object] = {}
    bridge = BTBridge(
        datalayer=datalayer,
        trigger_activity=trigger_activity,
        sync_port=sync_port,
        wire_render_port=wire_render_port,
    )
    tree = end_embargo_if_end_time_passed_tree(
        case_id=case_id, now=now, result_out=result_out
    )
    result = bridge.execute_with_setup(tree, actor_id=actor_id)
    if result.status != Status.SUCCESS:
        logger.warning(
            "Lazy end-time check for case '%s' by actor '%s' failed"
            " (activity_id=%s): %s",
            case_id,
            actor_id,
            activity_id,
            result.feedback_message,
        )
    return result


def end_time_case_upkeep(
    port_factory: Callable[[DataLayer], Mapping[str, Any]],
) -> CaseUpkeep:
    """The lazy end-time check as a dispatcher :class:`CaseUpkeep` hook.

    *port_factory* supplies, for the store being handled, the ports the
    termination's commit and announcement need (``trigger_activity``,
    ``sync_port``, ``wire_render_port``).  The composition root installs the
    hook on the inbox and trigger dispatchers, so the CASE_MANAGER ends an
    embargo whose end time has passed the next time it handles the case
    (ADR-0122, EMB-13-003).
    """

    def _upkeep(
        dl: CaseOutboxPersistence,
        *,
        case_id: str,
        actor_id: str,
        activity_id: str | None,
    ) -> None:
        # The inbox's port factories are typed on the whole DataLayer; the
        # store a dispatcher hands a hook is that DataLayer.
        ports = port_factory(cast(DataLayer, dl))
        end_embargo_if_end_time_passed(
            datalayer=dl,
            case_id=case_id,
            actor_id=actor_id,
            now=now_utc(),
            trigger_activity=ports.get("trigger_activity"),
            sync_port=ports.get("sync_port"),
            wire_render_port=ports.get("wire_render_port"),
            activity_id=activity_id,
        )

    return _upkeep


__all__ = [
    "EMBARGO_ALREADY_ENDED_KEY",
    "EmbargoAlreadyEndedNode",
    "EmbargoEndTimePassedNode",
    "end_embargo_at_end_time_bt",
    "end_time_case_upkeep",
    "end_embargo_if_end_time_passed",
    "end_embargo_if_end_time_passed_tree",
]
