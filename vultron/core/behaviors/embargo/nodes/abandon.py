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

"""The P/X/A abandonment of open embargo proposals (EMB-16-001, #4131).

Once the case is public, an exploit is public or attacks are observed while
EM is ``PROPOSED``, no proposal can be accepted any more (EMB-02-002), so
every open proposal is abandoned and EM returns to ``NONE``.  Abandoning
writes shared EM state, so only the CASE_MANAGER makes it (EP-09-008,
BT-17-001):

- As the CASE_MANAGER, :class:`ReadOpenEmbargoProposalsNode` maps each open
  proposal to the Invite that proposed it before anything moves.  A proposal
  with no indexed Invite cannot be answered, so the tree fails closed.
  :class:`AbandonEmbargoProposalsLifecycleNode` then abandons them one at a
  time, each with the activities its AS2 shape names (ADR-0152): an actor
  declines an Invite it received with ``Reject`` and withdraws one it sent
  with ``Undo``.  The CASE_MANAGER's ``Reject(Invite(EmbargoEvent))`` of the
  proposal it received, committed as ``reject_invite_to_embargo_on_case``,
  carries the proposal's ``CANCEL`` step; when the CASE_MANAGER sent the
  proposal itself, its ``Undo(Invite(EmbargoEvent))`` of that proposal
  carries it instead.  Its ``Undo`` of each Invite it relayed for the
  proposal follows, as ``undo_invite_to_embargo_on_case``, and changes
  nothing more.  The abandonment is a decision the CASE_MANAGER takes from
  local policy, so its entries come before the change they record
  (CLP-07-013).  Each activity is addressed to nobody: the manager never
  mails itself (CLP-10-001, ADR-0109), and every replica learns the
  decision from the entries (EP-09-009).
- Any other participant sends nothing (EMB-16-002, #4148):
  :class:`LeaveAbandonmentToCaseManagerNode` succeeds without a write or an
  ask.  Only the case owner, or the CASE_MANAGER it delegates to, decides
  the abandonment.  The participant's P/X/A signal already reached the
  manager as its status declaration, and the manager abandons on its own
  detection.  A ``Reject`` sent as the abandonment would be read as that
  participant declining the proposal (MSM-07-004).  This covers only the
  proposals already open on the case: a proposal, Invite or revision the
  participant *receives* at P/X/A is still answered with its own ``Reject``
  of the Invite on the received path (EMB-01-002).
- On a replica, :class:`ApplyEmbargoAbandonmentFromLedgerNode` copies the
  ``CANCEL`` step of the embargo the entry's Invite names through the same
  function (EP-09-007, RSH-08-004, CM-23-016).  The CASE_MANAGER's
  ``Reject`` is told from a participant's by the payload's ``actor``, after
  routing (SE-03-004).  The first entry of an abandonment cancels the
  proposal, and each ``Undo`` after it finds the proposal cancelled, in
  place.
"""

from functools import partial
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
)
from vultron.core.behaviors.embargo.nodes.abandon_effect import (
    ApplyEmbargoAbandonmentFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    _EmbargoLifecycleNode,
)
from vultron.core.behaviors.helpers import (
    TRIGGER_FACTORY_UNAVAILABLE,
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_apply import (
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import snapshot_actor_id
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
)
from vultron.core.services.received_activity import (
    holds_activity,
    holds_received_activity,
)
from vultron.core.states.em import EM
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronNotFoundError, VultronWiringError

#: Ledger ``semantic_type`` of the CASE_MANAGER's ``Reject`` of a proposal it
#: received: the participant's semantic type, since the shape is the same
#: (ADR-0152); a replica tells the two apart by the payload's ``actor``.
_REJECT_SEMANTIC_TYPE = MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
#: Ledger ``semantic_type`` of the CASE_MANAGER's ``Undo`` of an Invite it sent.
_UNDO_SEMANTIC_TYPE = MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE.value
_INVITE_SEMANTIC_TYPE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value

#: Blackboard key of the proposals to abandon, ``{embargo_id: invite_id}``.
ABANDONED_PROPOSALS_KEY = "abandoned_proposals"

_PROPOSALS_PORT: dict[str, PortInformation] = {
    ABANDONED_PROPOSALS_KEY: PortInformation(data_type=dict, required=True),
}
_PROPOSALS_REMAP: dict[str, str] = {
    ABANDONED_PROPOSALS_KEY: f"/{ABANDONED_PROPOSALS_KEY}"
}


def _holds(datalayer: CasePersistence, invite_id: str) -> bool:
    """Whether this store holds the Invite *invite_id*, received or sent.

    The Reject or Undo is built from the Invite as this store holds it
    (:func:`holds_activity`): a received Invite from its receiver-keyed
    archive, never under the id its sender chose (DL-06-006).
    """
    return holds_activity(datalayer, invite_id)


def relayed_invite_ids(
    entries: list[CaseLedgerEntry],
    manager_id: str,
    embargo_id: str,
    proposal_id: str,
) -> list[str]:
    """Every Invite to *embargo_id* the CASE_MANAGER sent, but the proposal.

    *entries* is the case's ledger, oldest first.  The relays the manager
    committed for the proposal (EP-09-002), to a joiner (EP-09-011) or as a
    re-invite (EMB-17-003) are each an ``invite_to_embargo_on_case`` entry
    whose ``actor`` is *manager_id* and whose object is the embargo.  The
    proposal's own Invite *proposal_id* is not one of them.  Each id once, in
    ledger order.
    """
    ids: list[str] = []
    for entry in entries:
        if entry.semantic_type != _INVITE_SEMANTIC_TYPE:
            continue
        snapshot = entry.payload_snapshot
        invite_id = entry.log_object_id
        if (
            invite_id == proposal_id
            or invite_id in ids
            or snapshot_actor_id(snapshot.get("actor")) != manager_id
            or _extract_id_from_field(snapshot.get("object")) != embargo_id
        ):
            continue
        ids.append(invite_id)
    return ids


def _read_proposals(node: DataLayerActionWithPorts) -> dict[str, str]:
    """Return a copy of ``/abandoned_proposals`` for *node*."""
    return dict(node.get_input(ABANDONED_PROPOSALS_KEY))


class ReadOpenEmbargoProposalsNode(DataLayerActionWithPorts):
    """Map every open proposal of the case to the Invite that proposed it.

    Read-only; the first node of the CASE_MANAGER's arm.  Writes
    ``{embargo_id: invite_id}``, in the case's record order, to
    ``/abandoned_proposals`` — an empty map first, so a reader never sees a
    stale value.  FAILURE, before anything moves, when the case has no open
    proposal, or an open proposal names no Invite in
    ``pending_embargo_proposal_index``, or names one this store cannot
    read: no Reject or Undo could cancel it (MSM-02-006, ADR-0152), and
    failing later, after the
    EM write, would leave the manager at ``NONE`` with no entry to tell any
    replica.
    """

    OUTPUT_PORTS: dict[str, PortInformation] = dict(_PROPOSALS_PORT)

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return dict(_PROPOSALS_REMAP)

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def update(self) -> Status:
        self._set_output(ABANDONED_PROPOSALS_KEY, {})
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        open_ids = case.proposed_embargo_ids
        index = case.pending_embargo_proposal_index
        unindexed = [i for i in open_ids if not index.get(i)]
        if not open_ids:
            self.feedback_message = (
                f"case '{self._case_id}' has no open embargo proposal"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if unindexed:
            self.feedback_message = (
                f"open proposal(s) {unindexed} of case '{self._case_id}' name"
                " no Invite, so no Reject or Undo can cancel them"
                " (MSM-02-006)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        assert self.datalayer is not None
        unreadable = [
            index[i] for i in open_ids if not _holds(self.datalayer, index[i])
        ]
        if unreadable:
            self.feedback_message = (
                f"Invite(s) {unreadable} of case '{self._case_id}' are not in"
                " this store, so no Reject or Undo can cancel them"
                " (MSM-02-006)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self._set_output(
            ABANDONED_PROPOSALS_KEY, {i: index[i] for i in open_ids}
        )
        self.feedback_message = (
            f"{len(open_ids)} open proposal(s) to abandon on case"
            f" '{self._case_id}'"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class AbandonEmbargoProposalsLifecycleNode(_EmbargoLifecycleNode):
    """The CASE_MANAGER's ``STRICT`` abandonment of every open proposal.

    For each proposal, in record order, it commits the activity that cancels
    it and applies that ``CANCEL`` step (ADR-0122) by copying it through the
    one apply function (ADR-0124), which changes no consent; then it commits
    its ``Undo(Invite(EmbargoEvent))`` of each Invite it relayed for the
    proposal (:func:`relayed_invite_ids`), which changes nothing more.  The
    cancelling activity follows the Invite's AS2 shape (ADR-0152): a proposal
    the CASE_MANAGER received is declined with ``Reject(Invite(EmbargoEvent))``
    under ``reject_invite_to_embargo_on_case``, and one it sent itself is
    withdrawn with ``Undo(Invite(EmbargoEvent))`` under
    ``undo_invite_to_embargo_on_case``.  A proposal never relayed is
    cancelled all the same.  Every activity is addressed to nobody.  EM
    reaches ``NONE`` with the last proposal, exactly as a replica replaying
    the entries does (EP-09-007).

    **Commit, then write** (CLP-07-013).  The abandonment is a decision taken
    from local policy, so each proposal's entries are committed before the
    case file changes.  The abandonment is checked as a whole before the
    first commit, so no entry is committed for one the case would then
    refuse.  Every activity is built (which stores it), committed and applied
    in one transaction (CLP-07-015, ADR-0146): a failure on any proposal
    abandons none of them, and the exception escapes to ``BTBridge``
    (BT-14-001).

    Sits inside the CASE_MANAGER gate (EP-09-008).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        **_PROPOSALS_PORT,
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return dict(_PROPOSALS_REMAP)

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id_value = case_id

    def initialise(self) -> None:
        super().initialise()
        self._proposals = _read_proposals(self)

    def _case_id(self) -> str:
        return self._case_id_value

    def update(self) -> Status:
        if self.trigger_activity_factory is None:
            # A composition fault, not a refusal (ARCH-15-001), raised before
            # anything is committed or written.  Checked here rather than in
            # _transition, whose VultronError handler would report it as a
            # refused abandonment.
            raise VultronWiringError(
                f"{self.name}: {TRIGGER_FACTORY_UNAVAILABLE} to build the"
                f" abandonment of case '{self._case_id_value}'"
            )
        return super().update()

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
    ) -> EmbargoLifecycleResult:
        assert self.trigger_activity_factory is not None
        lifecycle.check_abandonable(
            case_id=self._case_id_value, embargo_ids=list(self._proposals)
        )
        dl = cast(CaseOutboxPersistence, self.datalayer)
        em_before = self._em_state()
        entries = recorded_entries_for_case(case_id=self._case_id_value, dl=dl)
        committed = 0
        # One act: every activity is built (which stores it), committed and
        # applied in one transaction, so a failure on any proposal abandons
        # none of them (ADR-0146).
        with dl.transaction():
            for embargo_id, invite_id in self._proposals.items():
                planned = self._planned_entries(
                    dl, actor_id, entries, embargo_id, invite_id
                )
                commit_and_apply_embargo_entries(
                    dl, self._case_id_value, planned
                )
                committed += len(planned)
        self.feedback_message = (
            f"CASE_MANAGER abandoned {len(self._proposals)} open proposal(s)"
            f" on case '{self._case_id_value}' with {committed} committed"
            " entr(y/ies)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=self._em_state(),
            case_changed=bool(self._proposals),
            case_embargo_changed=False,
            participant_changes=[],
        )

    def _planned_entries(
        self,
        dl: CaseOutboxPersistence,
        actor_id: str,
        entries: list[CaseLedgerEntry],
        embargo_id: str,
        invite_id: str,
    ) -> list[PlannedEmbargoEntry]:
        """The entries that abandon one proposal: its cancel, then each ``Undo``.

        Builds each activity now, inside the act's transaction.
        """
        assert self.trigger_activity_factory is not None
        factory = self.trigger_activity_factory
        commit = partial(
            commit_emitted_activity,
            datalayer=dl,
            actor_id=actor_id,
            case_id=self._case_id_value,
        )
        if holds_received_activity(dl, invite_id):
            # Declining the proposal it received (ADR-0152).
            cancel_id, cancel_blob = factory.reject_embargo(
                proposal_id=invite_id,
                case_id=self._case_id_value,
                actor=actor_id,
                to=None,
            )
            cancel = partial(
                commit,
                activity_id=cancel_id,
                activity_blob=cancel_blob,
                semantic_type=_REJECT_SEMANTIC_TYPE,
            )
        else:
            # Withdrawing the proposal it sent itself (ADR-0152).
            cancel_id, cancel_blob = factory.undo_embargo_invite(
                invite_id=invite_id,
                case_id=self._case_id_value,
                actor=actor_id,
                to=None,
            )
            cancel = partial(
                commit,
                activity_id=cancel_id,
                activity_blob=cancel_blob,
                semantic_type=_UNDO_SEMANTIC_TYPE,
            )
        planned = [
            # The cancel is the CANCEL step (ADR-0122): committed, then
            # copied through the one apply function (ADR-0124).
            PlannedEmbargoEntry(
                change=RegisterStep(
                    kind=RegisterStepKind.CANCEL, embargo=embargo_id
                ),
                commit=cancel,
            )
        ]
        for relayed_id in relayed_invite_ids(
            entries, actor_id, embargo_id, invite_id
        ):
            undo_id, undo_blob = factory.undo_embargo_invite(
                invite_id=relayed_id,
                case_id=self._case_id_value,
                actor=actor_id,
                to=None,
            )
            planned.append(
                PlannedEmbargoEntry(
                    change=None,
                    commit=partial(
                        commit,
                        activity_id=undo_id,
                        activity_blob=undo_blob,
                        semantic_type=_UNDO_SEMANTIC_TYPE,
                    ),
                )
            )
        return planned

    def _em_state(self) -> EM:
        """The case's EM state, derived from its register."""
        case, failure = self._require_case(self._case_id_value)
        if failure is not None:
            raise VultronNotFoundError(
                "VulnerabilityCase", self._case_id_value
            )
        return case.em_state


class LeaveAbandonmentToCaseManagerNode(DataLayerActionWithPorts):
    """The non-CASE_MANAGER arm of the abandonment: write nothing, ask nothing.

    A participant that is not the CASE_MANAGER writes no shared EM state
    (EP-09-008), and it sends no ``Reject`` either (EMB-16-002, #4148).  The P/X/A
    status that brought it here is its own declaration to the manager, or
    the manager's declaration to it, so the manager has the signal and
    abandons on its own detection.  A ``Reject`` sent as the abandonment would
    reach the manager as this participant declining the proposal
    (MSM-07-004).  Its replica moves when the manager's abandonment entry is
    replayed (EP-09-007).  A proposal, Invite or revision it *receives* at
    P/X/A is answered with a ``Reject`` of the Invite on the received path
    instead (EMB-01-002), so this node does not stand for "never send a
    Reject".  Always SUCCESS.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def update(self) -> Status:
        self.feedback_message = (
            f"not the CASE_MANAGER of case '{self._case_id}': the manager"
            " abandons the open proposals on its own P/X/A detection, so"
            " nothing is written or sent here (EMB-16-002)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = [
    "ABANDONED_PROPOSALS_KEY",
    "AbandonEmbargoProposalsLifecycleNode",
    "ApplyEmbargoAbandonmentFromLedgerNode",
    "LeaveAbandonmentToCaseManagerNode",
    "ReadOpenEmbargoProposalsNode",
]
