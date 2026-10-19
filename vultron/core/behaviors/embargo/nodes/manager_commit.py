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

"""The CASE_MANAGER's own embargo decision, committed as a canonical entry.

A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008).  When
the role holder is the actor deciding — proposing terms, accepting or
rejecting them, or ending the embargo — its EM write is canonical, and a
replica can only learn it from a ledger entry the announce slots replay
(EP-09-007, RSH-08-004).  The ``Add(CaseStatus)`` the trigger tree also
emits is not replayed for EM, so without this commit every replica kept the
state it had before the manager decided (#4085).

The nodes here build the decision activity through the trigger-activity
factory as the executing actor, queue it when it has an audience, and then
commit the sealed blob as the canonical entry (VM-08-003): the entry records
a completed act (ADR-0119).  The activity is addressed to the participants it has to *reach*,
never to the manager itself (CLP-10-001, ADR-0109): an embargo teardown goes
to every other participant (EMB-19-001), and an empty audience commits the
entry and queues nothing (EMB-19-002).  A decision every replica learns from
the entry alone (an Accept or Reject the manager makes) is addressed to
nobody and only committed.

Like the relay node, these catch nothing: a failed factory call or commit
after the manager's EM write is not a protocol refusal, so the exception
escapes to ``BTBridge`` and the trigger raises (BT-14-001).
"""

from collections.abc import Callable
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.embargo.decided_entries import (
    EMBARGO_DECISION_KEY,
    EmbargoDecision,
    commit_and_apply_decision,
)
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronBTInternalError

#: Build the decision activity addressed to *to* (``None``: nobody) and
#: return ``(activity_id, sealed_blob)`` — the shape every embargo factory
#: method returns.
EmbargoActivityBuilder = Callable[[list[str] | None], tuple[str, str]]

#: Ledger ``event_type`` of a committed embargo teardown — the value the
#: ``EmbargoTeardown`` announce slot replays.
EMBARGO_TEARDOWN_EVENT_TYPE = (
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE.value
)

#: ``result_out`` key :class:`CommitEmbargoDecisionNode` writes the id of the
#: activity it committed to, for :class:`IndexOwnEmbargoProposalNode`.
COMMITTED_ACTIVITY_KEY = "committed_activity_id"


class CommitEmbargoDecisionNode(
    _CommitCaseManagerActivityBase, StateWriteCapable
):
    """Commit the decision a trigger use case builds (EP-09-008, #4085).

    *builder* is the use case's factory closure, so the use case captures the
    activity it reports in its result.  With *result_out* the built
    activity's id is also written to ``result_out[COMMITTED_ACTIVITY_KEY]``.

    With *decision_from*, the act is recorded under the copy model
    (ADR-0124, CLP-07-013): the deciding lifecycle node before this one left
    an :class:`~vultron.core.behaviors.embargo.decided_entries.EmbargoDecision`
    in ``decision_from[EMBARGO_DECISION_KEY]``, and this node commits the act's
    entry first, carrying the decision's register step, then one CASE_MANAGER
    entry per consent row the decision changes, and only then applies them by
    copying (``commit_and_apply_decision``).  A commit that fails leaves no
    write behind but those of the entries committed before it.  A missing
    decision is a fault in the tree and raises.
    """

    def __init__(
        self,
        case_id: str,
        event_type: str,
        builder: EmbargoActivityBuilder,
        notify_participants: bool = False,
        result_out: dict[str, object] | None = None,
        name: str | None = None,
        *,
        decision_from: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            event_type=event_type,
            notify_participants=notify_participants,
            name=name,
        )
        self._builder = builder
        self._result_out = result_out
        self._decision_from = decision_from

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        activity_id, blob = self._builder(to)
        if self._result_out is not None:
            self._result_out[COMMITTED_ACTIVITY_KEY] = activity_id
        return activity_id, blob

    def _record(
        self, activity_id: str, send_and_commit: Callable[[], None]
    ) -> None:
        if self._decision_from is None:
            send_and_commit()
            return
        decision = self._decision_from.pop(EMBARGO_DECISION_KEY, None)
        if not isinstance(decision, EmbargoDecision):
            raise VultronBTInternalError(
                f"{self.name}: no embargo decision to record for"
                f" '{activity_id}' on case '{self._case_id}'; a deciding"
                " lifecycle node must run first"
            )
        commit_and_apply_decision(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            decision=decision,
            trigger_activity=self._require_trigger_activity_port(),
            actor_id=cast(str, self.actor_id),
            cause_id=activity_id,
            act_commit=send_and_commit,
            act_entry_id=self._ledger_object_id(activity_id),
        )


class CommitEmbargoProposalNode(CommitEmbargoDecisionNode):
    """Commit the CASE_MANAGER's own proposal, storing the embargo it names.

    The factory renders the stored ``EmbargoEvent`` (EP-09-003), so the
    record is stored as the proposal is built.  A proposal whose entry does
    not commit, or whose trial apply refuses it, takes a record it stored
    back out, so a failed proposal leaves no orphan behind (CLP-07-013); the
    failure itself propagates.
    """

    def __init__(
        self,
        case_id: str,
        event_type: str,
        builder: EmbargoActivityBuilder,
        embargo: EmbargoEvent,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            event_type=event_type,
            builder=builder,
            result_out=result_out,
            name=name,
            decision_from=result_out,
        )
        self._embargo = embargo
        self._stored_here = False

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.datalayer is not None
        self._stored_here = self.datalayer.read(self._embargo.id_) is None
        if self._stored_here:
            self.datalayer.create(self._embargo)
        built = False
        try:
            result = super()._build(to)
            built = True
        finally:
            if not built:
                self._discard_stored()
        return result

    def _record(
        self, activity_id: str, send_and_commit: Callable[[], None]
    ) -> None:
        committed = False

        def _commit_act() -> None:
            nonlocal committed
            send_and_commit()
            committed = True

        try:
            super()._record(activity_id, _commit_act)
        finally:
            # Once the proposal's own entry is committed, the embargo it
            # names is case data: a later row commit that fails leaves it
            # stored, and the next embargo run commits the rows owed
            # (CLP-07-015).
            if not committed:
                self._discard_stored()

    def _discard_stored(self) -> None:
        """Take the embargo this node stored back out of the store."""
        if not self._stored_here:
            return
        assert self.datalayer is not None
        self.datalayer.delete(str(self._embargo.type_), self._embargo.id_)
        self._stored_here = False
        self.logger.warning(
            "%s: proposal of embargo '%s' on case '%s' was not recorded;"
            " its stored record is removed",
            self.name,
            self._embargo.id_,
            self._case_id,
        )


class IndexOwnEmbargoProposalNode(DataLayerActionWithPorts):
    """Index the CASE_MANAGER's own proposal (EP-09-001, EP-08-002).

    The manager answers its own terms through
    ``pending_embargo_proposal_index``, as it answers a proposal it received.
    It runs last in the manager's propose arm, so the correlation is written
    only once every other half of the proposal — EM write, commit, relay —
    has succeeded (ID-04-005).  Reads the proposal id
    :class:`CommitEmbargoDecisionNode` wrote to ``result_out``; a missing id
    is a fault in the tree, not a refusal, so it raises (BT-14-001).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._result_out = result_out

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        proposal_id = self._result_out.get(COMMITTED_ACTIVITY_KEY)
        if not isinstance(proposal_id, str) or not proposal_id:
            raise RuntimeError(
                f"{self.name}: no committed proposal id for embargo"
                f" '{self._embargo_id}' on case '{self._case_id}'"
            )
        record_embargo_proposal_index(
            self.datalayer, self._case_id, self._embargo_id, proposal_id
        )
        self.feedback_message = (
            f"Indexed own proposal '{proposal_id}' for embargo"
            f" '{self._embargo_id}' on case '{self._case_id}'"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = [
    "COMMITTED_ACTIVITY_KEY",
    "EMBARGO_TEARDOWN_EVENT_TYPE",
    "EmbargoActivityBuilder",
    "CommitEmbargoDecisionNode",
    "CommitEmbargoProposalNode",
    "IndexOwnEmbargoProposalNode",
]
