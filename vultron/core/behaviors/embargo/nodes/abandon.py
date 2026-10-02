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
  proposal to the Invite that proposed it before anything moves.  The ER the
  wire carries is a ``Reject`` of that Invite (MSM-02-006), so a proposal
  with no indexed Invite cannot be answered and the tree fails closed.
  :class:`AbandonEmbargoProposalsLifecycleNode` then writes the abandonment
  through ``EmbargoLifecycle``, and :class:`CommitEmbargoAbandonmentNode`
  commits one ER per proposal as a ledger entry of its own event type,
  addressed to nobody: the manager never mails itself (CLP-10-001,
  ADR-0109), and every replica learns the decision from the entry
  (EP-09-009).
- Any other participant sends nothing (EMB-16-002, #4148):
  :class:`LeaveAbandonmentToCaseManagerNode` succeeds without a write or an
  ask.  Its P/X/A signal already reached the manager as its status
  declaration, and the manager abandons on its own detection.  An ER from it
  would be read as that participant declining the proposal (MSM-07-004),
  which nobody decided.
- On a replica, :class:`ApplyEmbargoAbandonmentFromLedgerNode` replays an
  entry in ``OBSERVED`` mode (EP-09-007, RSH-08-004).  The replica drops the
  proposal because the entry is the manager's committed decision, not
  because of who rejected: a ``Reject`` decides a proposal only when the
  case owner sends it (EP-08-003), and the manager need not be the owner.
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.lifecycle import (
    _EmbargoLifecycleNode,
)
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    _CommitEmbargoDecisionBase,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    _answered_invite,
    _embargo_of_invite,
    _EmbargoRelayEffectNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.behaviors.sync.nodes.event_conditions import (
    EMBARGO_ABANDONMENT_EVENT_TYPE,
)
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.errors import VultronError

#: Blackboard key of the proposals to abandon, ``{embargo_id: invite_id}``.
ABANDONED_PROPOSALS_KEY = "abandoned_proposals"

_PROPOSALS_PORT: dict[str, PortInformation] = {
    ABANDONED_PROPOSALS_KEY: PortInformation(data_type=dict, required=True),
}
_PROPOSALS_REMAP: dict[str, str] = {
    ABANDONED_PROPOSALS_KEY: f"/{ABANDONED_PROPOSALS_KEY}"
}


def _read_proposals(node: DataLayerActionWithPorts) -> dict[str, str]:
    """Return a copy of ``/abandoned_proposals`` for *node*."""
    return dict(node.get_input(ABANDONED_PROPOSALS_KEY))


class ReadOpenEmbargoProposalsNode(DataLayerActionWithPorts):
    """Map every open proposal of the case to the Invite that proposed it.

    Read-only; the first node of the CASE_MANAGER's arm.  Writes ``{embargo_id: invite_id}``, in the case's record
    order, to ``/abandoned_proposals`` — an empty map first, so a reader never
    sees a stale value.  FAILURE, before anything moves, when the case has no
    open proposal or an open proposal names no Invite in
    ``pending_embargo_proposal_index``: no ER could name it (MSM-02-006).
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
                " no Invite, so no ER can answer them (MSM-02-006)"
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

    Calls ``EmbargoLifecycle.abandon_embargo_proposals`` (EMB-18-001), which
    drives ``PROPOSED → NONE`` and changes no consent.  Sits inside the
    CASE_MANAGER gate (EP-09-008).
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

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
        em_before: EM,
    ) -> EmbargoLifecycleResult:
        return lifecycle.abandon_embargo_proposals(
            case_id=self._case_id_value,
            embargo_ids=list(self._proposals),
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
            em_before=em_before,
        )


class CommitEmbargoAbandonmentNode(_CommitEmbargoDecisionBase):
    """Commit the CASE_MANAGER's ER for each abandoned proposal.

    One ``Reject(Invite(EmbargoEvent))`` per proposal (MSM-02-006), each
    committed under :data:`EMBARGO_ABANDONMENT_EVENT_TYPE` and addressed to
    nobody: the announced entry tells every replica (EP-09-009), and the
    manager never addresses itself (CLP-10-001).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        **_PROPOSALS_PORT,
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return dict(_PROPOSALS_REMAP)

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(
            case_id=case_id,
            event_type=EMBARGO_ABANDONMENT_EVENT_TYPE,
            notify_participants=False,
            name=name,
        )

    def initialise(self) -> None:
        super().initialise()
        self._proposals = _read_proposals(self)

    def _build_all(self, to: list[str] | None) -> list[tuple[str, str]]:
        assert self.trigger_activity_factory is not None
        return [
            self.trigger_activity_factory.reject_embargo(
                proposal_id=invite_id,
                case_id=self._case_id,
                actor=cast(str, self.actor_id),
                to=to,
            )
            for invite_id in self._proposals.values()
        ]


class LeaveAbandonmentToCaseManagerNode(DataLayerActionWithPorts):
    """The non-CASE_MANAGER arm of the abandonment: write nothing, ask nothing.

    A participant that is not the CASE_MANAGER writes no shared EM state
    (EP-09-008), and it sends no ER either (EMB-16-002, #4148).  The P/X/A
    status that brought it here is its own declaration to the manager, or
    the manager's declaration to it, so the manager has the signal and
    abandons on its own detection.  An ER would reach the manager as this
    participant declining the proposal (MSM-07-004).  Its replica moves when
    the manager's abandonment entry is replayed (EP-09-007).  Always SUCCESS.
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


class ApplyEmbargoAbandonmentFromLedgerNode(_EmbargoRelayEffectNode):
    """Replay the CASE_MANAGER's abandonment of one proposal (EMB-16-001).

    Calls ``EmbargoLifecycle.abandon_embargo_proposals`` in ``OBSERVED``
    mode for the embargo the entry's Invite names: the proposal leaves this
    replica's open proposals, and EM returns to ``NONE`` with the last one
    (EP-09-007).  A proposal this replica no longer holds as open is a no-op,
    so a repeated or late entry never blocks the persist (SYNC-12-001).
    """

    def update(self) -> Status:
        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        resolved = self._resolve(
            _embargo_of_invite(_answered_invite(snapshot))
        )
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        assert self.datalayer is not None
        if embargo_id not in case.proposed_embargo_ids:
            self.feedback_message = (
                f"embargo '{embargo_id}' is not an open proposal of case"
                f" '{case.id_}' here — nothing to replay"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        manager_id = _extract_id_from_field(snapshot.get("actor")) or None
        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).abandon_embargo_proposals(
                case_id=case.id_,
                embargo_ids=[embargo_id],
                actor_id=manager_id,
                transition_mode=TransitionMode.OBSERVED,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        log_em_transition(
            self.logger,
            manager_id or "",
            case.id_,
            result.em_before,
            result.em_after,
        )
        self.feedback_message = (
            f"Replayed abandonment of embargo '{embargo_id}' on case"
            f" '{case.id_}' (EM {result.em_before} → {result.em_after})"
        )
        return Status.SUCCESS


__all__ = [
    "ABANDONED_PROPOSALS_KEY",
    "AbandonEmbargoProposalsLifecycleNode",
    "ApplyEmbargoAbandonmentFromLedgerNode",
    "CommitEmbargoAbandonmentNode",
    "LeaveAbandonmentToCaseManagerNode",
    "ReadOpenEmbargoProposalsNode",
]
