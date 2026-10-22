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
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
    consent_row_entry,
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
from vultron.core.models.embargo_apply import ConsentRowChange
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronBTInternalError

#: Build the decision activity addressed to *to* (``None``: nobody) and
#: return ``(activity_id, sealed_blob)`` — the shape every embargo factory
#: method returns.
EmbargoActivityBuilder = Callable[[list[str] | None], tuple[str, str]]

#: Ledger ``semantic_type`` of a committed embargo teardown — the value the
#: ``EmbargoTeardown`` announce slot replays.
EMBARGO_TEARDOWN_SEMANTIC_TYPE = (
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
    copying (``commit_and_apply_decision``), all in one transaction: a commit
    that fails leaves no write behind (ADR-0146).  A missing
    decision is a fault in the tree and raises.
    """

    def __init__(
        self,
        case_id: str,
        semantic_type: str,
        builder: EmbargoActivityBuilder,
        notify_participants: bool = False,
        result_out: dict[str, object] | None = None,
        name: str | None = None,
        *,
        decision_from: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            semantic_type=semantic_type,
            notify_participants=notify_participants,
            name=name,
        )
        self._builder = builder
        self._result_out = result_out
        self._decision_from = decision_from

    def update(self) -> Status:
        """Build, queue and commit the act, with its rows, in one transaction.

        The build stores the activity, so it joins the transaction the
        commits run in: an act that fails anywhere leaves nothing it wrote
        behind (ADR-0146).
        """
        if self.datalayer is None:
            return super().update()  # reports the missing store
        with cast(CaseOutboxPersistence, self.datalayer).transaction():
            return super().update()

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
        )


class CommitEmbargoProposalNode(CommitEmbargoDecisionNode):
    """Commit the CASE_MANAGER's own proposal, storing the embargo it names.

    The factory renders the stored ``EmbargoEvent`` (EP-09-003), so the
    record is stored as the proposal is built.  The build runs in the node's
    transaction, so a proposal whose entries do not commit, or whose trial
    apply refuses it, leaves no embargo behind either (CLP-07-013,
    ADR-0146); the failure itself propagates.
    """

    def __init__(
        self,
        case_id: str,
        semantic_type: str,
        builder: EmbargoActivityBuilder,
        embargo: EmbargoEvent,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            semantic_type=semantic_type,
            builder=builder,
            result_out=result_out,
            name=name,
            decision_from=result_out,
        )
        self._embargo = embargo

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.datalayer is not None
        if self.datalayer.read(self._embargo.id_) is None:
            # Inside the node's transaction: a proposal that fails anywhere
            # takes the stored embargo back out with it (ADR-0146).
            self.datalayer.create(self._embargo)
        return super()._build(to)


class CommitOwnConsentDecisionNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Commit the CASE_MANAGER's own consent change as its row's entry alone.

    A CASE_MANAGER with an embargo stake of its own (EP-09-002) that answers
    an embargo by trigger records the row it changes as its own
    ``Update(EmbargoConsent)`` entry, and builds, sends and commits no
    ``Reject(Invite(EmbargoEvent))``: the CASE_MANAGER's ``Reject`` of a
    proposal is its abandonment of it (EMB-16-001, ADR-0152), so a replica
    reads every CASE_MANAGER-sent ``Reject`` as the cancel, and the
    manager's own consent is its row's entry (MSM-07-004).  The deciding
    lifecycle node before this one left an
    :class:`~vultron.core.behaviors.embargo.decided_entries.EmbargoDecision`
    in ``decision_from[EMBARGO_DECISION_KEY]``; the row its act states is
    committed first, then any other row it changes, and only then applied by
    copying (ADR-0124, CLP-07-013), in one transaction (ADR-0146).  The
    snapshot of the first ``Update`` is written to ``captured["activity"]``
    when *captured* is given, so the trigger reports the activity it
    committed (TRIG-04-001).  A missing decision, or one whose act carries a
    register step, is a fault in the tree and raises.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        decision_from: dict[str, object],
        name: str | None = None,
        *,
        captured: dict[str, object] | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._decision_from = decision_from
        self._captured = captured

    def _rows(self) -> tuple[ConsentRowChange, ...]:
        """The rows to commit, the act's own row first."""
        decision = self._decision_from.pop(EMBARGO_DECISION_KEY, None)
        if not isinstance(decision, EmbargoDecision):
            raise VultronBTInternalError(
                f"{self.name}: no embargo decision to record for embargo"
                f" '{self._embargo_id}' on case '{self._case_id}'; a deciding"
                " lifecycle node must run first"
            )
        if isinstance(decision.act, ConsentRowChange):
            return (decision.act, *decision.rows)
        if decision.act is not None:
            raise VultronBTInternalError(
                f"{self.name}: the CASE_MANAGER's own consent on case"
                f" '{self._case_id}' carries a register step"
            )
        return decision.rows

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        dl = cast(CaseOutboxPersistence, self.datalayer)
        rows = self._rows()
        committed: list[dict[str, Any]] = []
        entries = []
        for row in rows:
            planned = consent_row_entry(
                datalayer=dl,
                trigger_activity=self._require_trigger_activity_port(),
                actor_id=cast(str, self.actor_id),
                case_id=self._case_id,
                change=row,
                cause_id=f"own-consent:{self._embargo_id}",
            )
            commit = planned.commit
            assert commit is not None

            def _commit(commit: Callable[[], Any] = commit) -> Any:
                snapshot = commit()
                committed.append(snapshot)
                return snapshot

            entries.append(
                PlannedEmbargoEntry(change=planned.change, commit=_commit)
            )
        commit_and_apply_embargo_entries(dl, self._case_id, entries)
        if self._captured is not None and committed:
            self._captured["activity"] = committed[0]
        self.feedback_message = (
            f"CASE_MANAGER committed its own consent change(s) for embargo"
            f" '{self._embargo_id}' on case '{self._case_id}' as"
            f" {len(rows)} Update(EmbargoConsent) entr(y/ies)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


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
    "EMBARGO_TEARDOWN_SEMANTIC_TYPE",
    "EmbargoActivityBuilder",
    "CommitEmbargoDecisionNode",
    "CommitEmbargoProposalNode",
    "CommitOwnConsentDecisionNode",
    "IndexOwnEmbargoProposalNode",
]
