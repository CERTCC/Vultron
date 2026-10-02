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

"""Ledger effect nodes for the embargo revision relay (EP-09-007, ADR-0113).

The CASE_MANAGER commits four kinds of entry while it relays an embargo
negotiation: the proposal it received, each ``Invite(EmbargoEvent)`` it relays
to a participant, each participant's ``Accept`` or ``Reject`` of its Invite,
and the case owner's decision (which is an ``Accept`` or ``Reject`` by the
owner).  A participant replica writes none of that state when the activity
reaches it directly (EP-09-003, RSH-08-003); it reconstructs the state from the
``Announce(CaseLedgerEntry)`` broadcast through these nodes (RSH-08-004,
ADR-0108).

Each node goes through :class:`EmbargoLifecycle` in ``OBSERVED`` mode, as the
teardown apply node does — the CASE_MANAGER already decided, so the replica
syncs to its decision rather than re-adjudicating it.  The consent nodes
delegate to the received-side record nodes so that both sides apply one rule
(MSM-07-004, MSM-07-005).

Regime 2 (ADR-0087): a replica that holds no copy of the case skips the entry
with SUCCESS.  A replica that holds the case but cannot reconstruct the
embargo the entry names fails, which blocks persisting the entry
(SYNC-12-001) — persisting it would record a transition the replica never
applied.
"""

from __future__ import annotations

from typing import Any

from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.embargo.nodes.proposal import (
    ALREADY_DECLINED_PREFIX,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
)
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    DecideRejectedEmbargoProposalNode,
)
from vultron.core.behaviors.embargo.nodes.relay import invite_rsvp_deadline
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.errors import VultronNotFoundError


def _answered_invite(snapshot: dict[str, Any]) -> Any:
    """Return the Invite an ``Accept``/``Reject`` snapshot answers."""
    return snapshot.get("object")


def _embargo_of_invite(invite: Any) -> Any:
    """Return the ``EmbargoEvent`` (inline dict or bare id) an Invite carries."""
    if isinstance(invite, dict):
        return invite.get("object")
    return None


class _EmbargoRelayEffectNode(_LedgerEffectNode):
    """Shared frame: resolve the replica case and the embargo the entry names."""

    def _resolve(
        self, embargo_data: Any
    ) -> tuple[VulnerabilityCase, str] | Status:
        """Return ``(case, embargo_id)``, or the ``Status`` to return early.

        SUCCESS when this replica holds no copy of the case (Regime 2).
        FAILURE when the entry names no embargo, or names one this replica can
        neither find nor reconstruct (EMB-18-003).
        """
        if (f := self._require_datalayer()) is not None:
            return f
        entry = self._get_entry()
        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica

        embargo_id = _extract_id_from_field(embargo_data)
        if not embargo_id:
            self.feedback_message = (
                f"'{entry.event_type}' entry on case '{entry.case_id}' names"
                " no embargo"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if not self._store_embargo(embargo_data, embargo_id):
            return Status.FAILURE
        return case, embargo_id

    def _store_embargo(self, embargo_data: Any, embargo_id: str) -> bool:
        """Persist the entry's inline ``EmbargoEvent`` unless already stored.

        The canonical entry carries the object inline, so the replica stores
        it from there rather than fetching it from the proposer (EMB-18-003,
        CLP-10-017).  A bare id is enough when the record is already here.
        """
        assert self.datalayer is not None
        if self.datalayer.read(embargo_id) is not None:
            return True
        if not isinstance(embargo_data, dict):
            self.feedback_message = (
                f"embargo '{embargo_id}' is not stored here and the entry"
                " names it by id only, so it cannot be reconstructed"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return False
        try:
            embargo = EmbargoEvent.model_validate(
                project_wire_snapshot_to_core(EmbargoEvent, embargo_data)
            )
        except ValidationError as exc:
            self.feedback_message = (
                f"embargo '{embargo_id}' in the entry is malformed: {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return False
        self.datalayer.create(embargo)
        self.logger.debug(
            "%s: stored embargo '%s' from the canonical entry",
            self.name,
            embargo_id,
        )
        return True

    def _delegate(self, node: DataLayerActionWithPorts) -> Status:
        """Run a received-side record node in this node's store and actor."""
        node.datalayer = self.datalayer
        node.actor_id = self.actor_id
        status = node.update()
        self.feedback_message = node.feedback_message
        return status


class ApplyEmbargoProposalFromLedgerNode(_EmbargoRelayEffectNode):
    """Replay the embargo proposal the CASE_MANAGER received (EP-09-001).

    Stores the proposed ``EmbargoEvent`` and moves this replica's case through
    ``EmbargoLifecycle.propose_embargo`` in ``OBSERVED`` mode — ``PROPOSED``
    for a first proposal, ``REVISE`` for a revision of an active embargo —
    recording the proposer's consent to its own terms (ADR-0093).  Records the
    proposal in ``pending_embargo_proposal_index`` only when this replica has
    no entry for the embargo yet, so the Invite actually addressed to this
    replica keeps its place there.
    """

    def update(self) -> Status:
        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        resolved = self._resolve(snapshot.get("object"))
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        assert self.datalayer is not None

        proposer_id = _extract_id_from_field(snapshot.get("actor"))
        EmbargoLifecycle(persistence=self.datalayer).propose_embargo(
            case_id=case.id_,
            embargo_id=embargo_id,
            actor_id=proposer_id,
            transition_mode=TransitionMode.OBSERVED,
        )

        proposal_id = _extract_id_from_field(snapshot.get("id"))
        if proposal_id:
            record_embargo_proposal_index(
                self.datalayer,
                case.id_,
                embargo_id,
                proposal_id,
                overwrite=False,
            )

        self.feedback_message = (
            f"Replayed proposal of embargo '{embargo_id}' by '{proposer_id}'"
            f" on case '{case.id_}' (EP-09-007)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyEmbargoInviteFromLedgerNode(_EmbargoRelayEffectNode):
    """Replay an Invite the CASE_MANAGER relayed (EP-09-002, EP-09-004).

    Calls ``EmbargoLifecycle.record_embargo_invite`` for the invitee — the
    Invite's sole ``to`` — the operation the CASE_MANAGER ran at its commit:
    PEC ``INVITE`` where CM-18-003 allows it, so a ``SIGNATORY`` asked about
    a revision keeps its state, and the Invite's RSVP deadline (``endTime``)
    when it carries one (CM-28-013).  An invitee with no participant record
    here is skipped.
    """

    def update(self) -> Status:
        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        resolved = self._resolve(snapshot.get("object"))
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        assert self.datalayer is not None

        recipients = snapshot.get("to") or []
        invitee_id = (
            _extract_id_from_field(recipients[0])
            if isinstance(recipients, list) and len(recipients) == 1
            else None
        )
        if invitee_id is None:
            self.feedback_message = (
                f"relayed Invite on case '{case.id_}' names {len(recipients)}"
                " recipients; a relayed Invite has exactly one (EP-09-010)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).record_embargo_invite(
                case_id=case.id_,
                invitee_id=invitee_id,
                rsvp_deadline=invite_rsvp_deadline(snapshot),
            )
        except VultronNotFoundError:
            self.feedback_message = (
                f"no participant record for invitee '{invitee_id}' on case"
                f" '{case.id_}' — skipping (partial replica)"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        self.feedback_message = (
            f"Replayed relayed Invite of embargo '{embargo_id}' to"
            f" '{invitee_id}' on case '{case.id_}'"
            f" ({len(result.participant_changes)} PEC state change(s))"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyEmbargoAcceptanceFromLedgerNode(_EmbargoRelayEffectNode):
    """Replay an ``Accept`` of an embargo Invite (MSM-07-003, MSM-07-005).

    Delegates to :class:`RecordParticipantAcceptanceNode` for the accepting
    actor: a participant's Accept records its consent; the case owner's Accept
    activates the embargo, with the EP-05-001 consent cascade.
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
        accepting_actor_id = _extract_id_from_field(snapshot.get("actor"))
        if not accepting_actor_id:
            self.feedback_message = (
                f"Accept on case '{case.id_}' names no actor"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return self._delegate(
            RecordParticipantAcceptanceNode(
                case_id=case.id_,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
            )
        )


class ApplyEmbargoRejectionFromLedgerNode(_EmbargoRelayEffectNode):
    """Replay a ``Reject`` of an embargo Invite (MSM-07-004).

    Delegates to :class:`RecordParticipantRejectionNode` for the rejecting
    actor, then to :class:`DecideRejectedEmbargoProposalNode` in ``OBSERVED``
    mode, which — only when the rejecting actor is the case owner — forgets
    the open proposal and returns EM to the prior terms (EP-08-003).  A
    rejection this replica already holds is replayed as a no-op: the record
    node reports the repeat, and a repeat is not a fault.  So is a Reject of
    an embargo this replica no longer holds as active or open.
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
        rejecting_actor_id = _extract_id_from_field(snapshot.get("actor"))
        if not rejecting_actor_id:
            self.feedback_message = (
                f"Reject on case '{case.id_}' names no actor"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if (
            embargo_id != case.active_embargo_id
            and embargo_id not in case.proposed_embargo_ids
        ):
            # The CASE_MANAGER commits only a Reject it could apply (its
            # IsRejectableEmbargoNode guard), so a replica that no longer holds
            # the embargo as active or open has already applied what followed
            # (a later decision or teardown).  Failing here would block the
            # persist and buffer every later entry (SYNC-12-001, SYNC-14-001).
            self.feedback_message = (
                f"Reject of embargo '{embargo_id}' on case '{case.id_}' names"
                " neither the active embargo nor an open proposal here —"
                " nothing to replay"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        status = self._delegate(
            RecordParticipantRejectionNode(
                case_id=case.id_,
                embargo_id=embargo_id,
                rejecting_actor_id=rejecting_actor_id,
            )
        )
        if status is not Status.SUCCESS and not (
            self.feedback_message or ""
        ).startswith(ALREADY_DECLINED_PREFIX):
            return status
        return self._delegate(
            DecideRejectedEmbargoProposalNode(
                case_id=case.id_,
                embargo_id=embargo_id,
                rejecting_actor_id=rejecting_actor_id,
                transition_mode=TransitionMode.OBSERVED,
            )
        )


__all__ = [
    "ApplyEmbargoProposalFromLedgerNode",
    "ApplyEmbargoInviteFromLedgerNode",
    "ApplyEmbargoAcceptanceFromLedgerNode",
    "ApplyEmbargoRejectionFromLedgerNode",
]
