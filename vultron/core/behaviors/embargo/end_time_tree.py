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
  (:func:`end_time_clock_decision`), a clock decision composed into the one
  tree that handles the activity or trigger (CLP-10-025, ADR-0135) — no
  scheduler is needed; and
- an **outside request**, such as a Sentinel monitoring embargo timers,
  through the terminate-embargo trigger with ``reason=END_TIME_REACHED``.

Both commit the CASE_MANAGER's ``Remove(EmbargoEvent)`` with ``content``
``END_TIME_REACHED`` and run the full cascade of ``terminate_embargo_bt``.
Whichever arrives second finds the embargo ended, commits nothing and is
answered as already done, so it never reaches the register, which accepts
no change once an entry is ``TERMINATED``::

    EndEmbargoAtEndTimeBT (Selector)
    ├─ EmbargoAlreadyEndedNode          # EM EXITED: already done
    └─ TerminateEmbargoBT               # END_TIME_REACHED, claimed at *now*

    EmbargoEndTimeDecision (Selector; a clock decision, gated by its stage)
    ├─ EndTimeNotPassed (Inverter(EmbargoEndTimePassedNode))
    └─ EndEmbargoOnAFreshLedger (Sequence)
       ├─ EndTimeLedgerFresh (CheckLedgerFreshnessNode)
       └─ EndEmbargoAtEndTimeBT

The decision commits one CASE_MANAGER entry for each AS2 activity the
termination needs: the ``Remove``, whose register step also cancels every
open proposal, so no prefix of the entries shows the embargo ``TERMINATED``
beside a ``PROPOSED`` one (EP-08-004), then the ``Add(CaseStatus)`` and each
re-issued stub ``Invite`` (CLP-10-025).
"""

from datetime import datetime
from typing import cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    EmbargoActivityBuilder,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.sync.nodes import CheckLedgerFreshnessNode
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    has_reached_end_time,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import embargo_in_force
from vultron.core.states.em import EM
from vultron.errors import BtNodePreconditionError, VultronError

#: ``result_out`` key :class:`EmbargoAlreadyEndedNode` sets when the embargo
#: had already ended, so the request is answered as already done.
EMBARGO_ALREADY_ENDED_KEY = "embargo_already_ended"

#: Name of the ledger-freshness check that leads the end-time termination
#: in :func:`end_time_clock_decision`.
END_TIME_LEDGER_FRESH_NODE_NAME = "EndTimeLedgerFresh"


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


def end_time_clock_decision(
    *, case_id: str, now: datetime
) -> py_trees.behaviour.Behaviour:
    """The CASE_MANAGER's lazy end-time check for *case_id* (ADR-0122).

    A clock decision (CLP-10-025): runs :func:`end_embargo_at_end_time_bt`
    only when the embargo in force has reached its end time at *now*, and is
    otherwise SUCCESS with nothing done.  A gapped local ledger, the one way
    the ledger refuses a CASE_MANAGER commit, is FAILURE before anything is
    committed, so the stage logs it and the tree continues (CLP-10-025); a
    commit that then fails is an internal error and ends the tree.  It holds
    no gate of its own: every caller composes it into its one tree behind
    the CASE_MANAGER gate of the clock-decision stage, a received tree through
    :func:`~vultron.core.behaviors.case.case_clock_decisions.case_clock_decisions`
    and a case-scoped trigger through ``SvcBTTriggerBase``.  The
    termination's own output goes to a dict of its own, so it never mixes
    with the output of the tree it runs in.
    """
    result_out: dict[str, object] = {}
    return py_trees.composites.Selector(
        name="EmbargoEndTimeDecision",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="EndTimeNotPassed",
                child=EmbargoEndTimePassedNode(case_id=case_id, now=now),
            ),
            py_trees.composites.Sequence(
                name="EndEmbargoOnAFreshLedger",
                memory=False,
                children=[
                    # The ledger's one refusal of a CASE_MANAGER commit, a
                    # gapped local prefix (SYNC-10-001), is judged before
                    # the termination commits anything: its commit nodes
                    # raise on a failed commit, which would end the tree the
                    # decision runs in as an internal error (CLP-10-025).
                    CheckLedgerFreshnessNode(
                        case_id=case_id, name=END_TIME_LEDGER_FRESH_NODE_NAME
                    ),
                    end_embargo_at_end_time_bt(
                        case_id=case_id, result_out=result_out, now=now
                    ),
                ],
            ),
        ],
    )


__all__ = [
    "EMBARGO_ALREADY_ENDED_KEY",
    "END_TIME_LEDGER_FRESH_NODE_NAME",
    "EmbargoAlreadyEndedNode",
    "EmbargoEndTimePassedNode",
    "end_embargo_at_end_time_bt",
    "end_time_clock_decision",
]
