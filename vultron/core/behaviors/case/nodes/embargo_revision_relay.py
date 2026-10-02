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

"""Relay the creation-time revision to the party whose terms won (EP-04-011).

``RegisterLongerProposalAsRevisionNode`` registers the shortest-wins loser as a
pending revision inside ``InitializeDefaultEmbargoNode`` and publishes it as a
:class:`CreationTimeRevision` for this execution only.
:class:`RecordCreationTimeRevisionRelayNode` turns that into a durable
:class:`PendingCreationTimeRevisionRelay` marker, and
:class:`RelayCreationTimeRevisionNode` sends the revision like any other
(EP-09, ADR-0113) once the case tree has finished its initialization sequence
(CM-14-007), indexes it so the owner's default selection reaches it
(EP-08-002), and deletes the marker.

The marker is what makes a failed relay recoverable (#4121).  Initialization
runs once per case (EP-04-012), so a redelivered proposal never registers the
revision again; the marker survives the failure instead, and the next
delivery's relay or the startup retry runner
(``retry_pending_creation_time_revision_relays``) completes it, in the shape of
the ``PendingCreateCaseActivity`` marker (CP-05-005).

This module is not re-exported from ``vultron.core.behaviors.case.nodes``:
the relay subclasses the embargo relay emit, whose module imports the case
role gates, so a re-export from the case node package would close an import
cycle.  Import it from here.
"""

import logging
from enum import Enum, auto
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.embargo_revision import (
    REVISION_KEY,
    CreationTimeRevision,
)
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CREATE_CASE_EVENT_TYPE,
)
from vultron.core.behaviors.case.report_author import report_author_id
from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
    invite_rsvp_deadline,
)
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.pending_creation_time_revision_relay import (
    LosingSource,
    PendingCreationTimeRevisionRelay,
)
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.embargo_duration import EmbargoDurationSource
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import BtNodePreconditionError, VultronError

logger = logging.getLogger(__name__)

_MARKER_TYPE = "PendingCreationTimeRevisionRelay"


class _RelayState(Enum):
    """Where an owed relay stands, read from the case and its ledger."""

    SEND = auto()
    NOT_YET = auto()  # the case's creation entries are not committed yet
    CLOSED = auto()  # the revision is no longer an open proposal
    COMMITTED = auto()  # its Invite is already in the ledger


class RecordCreationTimeRevisionRelayNode(DataLayerActionWithPorts):
    """Persist the registered creation-time revision as a relay obligation.

    Placed right after ``InitializeDefaultEmbargoNode``, so the obligation is
    durable before anything else in the case tree can fail.  Reads the
    :class:`CreationTimeRevision` the registration published and writes a
    :class:`PendingCreationTimeRevisionRelay` keyed on the case, carrying the
    report the reporter is resolved from and the CASE_MANAGER that owes the
    relay.  Writing a record initiates no embargo modification, so this does
    not run ahead of CM-14-007's sequence the way the relay itself would.

    Writes nothing, and succeeds, when no revision was registered in this
    execution (no contest, a tie, or a case already initialized) or when the
    published revision names another case.  A registered revision with no
    report to resolve the reporter from raises: no relay could ever be sent
    for it, so recording it would only fail at every retry.  That and a store
    fault are the manager's own, and ``BTBridge`` reports them as internal
    errors.
    """

    def __init__(self, report_id: str | None, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        REVISION_KEY: PortInformation(
            data_type=CreationTimeRevision | None, required=False
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id", REVISION_KEY: f"/{REVISION_KEY}"}

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        revision = self._try_get_input(REVISION_KEY)
        if not isinstance(revision, CreationTimeRevision) or (
            revision.case_id != self._try_get_input("case_id")
        ):
            self.feedback_message = "no creation-time revision registered"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        if not self._report_id:
            raise RuntimeError(
                f"{self.name}: creation-time revision '{revision.embargo_id}'"
                f" on case '{revision.case_id}' has no report, so the reporter"
                " it is relayed to or for cannot be resolved (EP-04-011)"
            )
        marker = PendingCreationTimeRevisionRelay(
            case_id=revision.case_id,
            embargo_id=revision.embargo_id,
            proposal_id=revision.proposal_id,
            losing_source=cast(LosingSource, revision.losing_source.value),
            report_id=self._report_id,
            case_actor_id=self.actor_id,
        )
        self.datalayer.save(marker)
        self.feedback_message = (
            f"recorded relay of creation-time revision"
            f" '{revision.embargo_id}' on case '{revision.case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class RelayCreationTimeRevisionNode(RelayEmbargoInviteToEachNode):
    """Relay the creation-time revision to the party whose terms won (EP-04-011).

    The #3913 relay emit, fed from the case's
    :class:`PendingCreationTimeRevisionRelay` marker rather than from a
    received proposal: the CASE_MANAGER emits ``Invite(EmbargoEvent)`` as
    ``actor`` with the losing party in ``attributedTo`` (CM-24-001,
    CM-24-002), under the proposal id the registration minted, and commits it
    in this tree.  The committed Invite is the revision's proposal entry: no
    proposal activity exists at creation, and #4099's replay recognises the
    entry as a relayed Invite (EP-09-007).  The losing party is the proposer
    and is not invited (EP-09-002).  The case tree places this node after its
    ledger commit, so no modification is initiated before the initialization
    sequence is complete (CM-14-007).

    **The input is read from the store, not the blackboard**, so the relay is
    retried wherever it runs again: a later delivery of a proposal for the
    case, or the startup retry runner, which passes *case_id* (#4121).  The
    marker is deleted once the obligation is discharged, and kept whenever
    the relay fails, so a failure is never final.

    **The index is written after the Invite is sent**, never at registration.
    The bootstrap ``Create(VulnerabilityCase)`` carries the case whole; had it
    carried ``embargo → Invite id``, the invitee's idempotency guard
    (``EmbargoProposalNotYetRecordedNode``) would read the Invite as already
    answered and skip it.  The invitee indexes the Invite when it answers, and
    the proposer's replica learns it from the replayed entry
    (``ApplyEmbargoInviteFromLedgerNode``), so the owner's default selection
    reaches it on either side (EP-08-002).

    Outcomes, all decided from the store:

    - no marker: nothing is owed, SUCCESS;
    - the case's genesis ledger entry is not committed yet (a case tree that
      failed before its ledger commit): nothing is sent and the marker is
      kept, since a relay now would fan an entry out ahead of the case's
      creation (CM-14-007, CM-14-011);
    - the revision is no longer an open proposal: nothing to relay, the
      marker is deleted;
    - its Invite is already in the ledger (a relay that failed after its
      commit): it is not sent again, but the winner's PEC INVITE is applied
      where still legal and the Invite indexed, and the marker is deleted.
      Whether the Invite reached the outbox cannot be told from the store,
      since delivery empties it, so it is not queued again;
    - a reporter that is itself the CASE_OWNER: nobody to invite, nothing is
      indexed, the marker is deleted;
    - otherwise the Invite is sent, indexed, and the marker deleted.

    A revision whose parties cannot be resolved, or whose winning party is not
    an invitation recipient, raises and keeps the marker: the case is already
    created and announced, so the fault is the manager's own, never a refusal
    of the sender's proposal.
    """

    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        # The embargo and proposer are known only at tick time, from the
        # marker; ``update`` and ``_resolve_parties`` set them, so the base
        # constructor gets placeholders.
        super().__init__(
            case_id=case_id or "",
            embargo_id="",
            proposer_id="",
            name=name or self.__class__.__name__,
        )
        self._fixed_case_id = case_id
        self._marker: PendingCreationTimeRevisionRelay | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id", "sync_port": "/sync_port"}

    def _load_relay_inputs(self) -> None:
        self._recipients = []
        self._marker = None
        case_id = self._fixed_case_id or self._try_get_input("case_id")
        self._case_id = case_id if isinstance(case_id, str) else ""

    def _activity_id_for(self, recipient_id: str) -> str | None:
        return self._marker.proposal_id if self._marker else None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        marker = self._pending_marker()
        if marker is None:
            self.feedback_message = "no creation-time revision to relay"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        self._marker = marker
        self._embargo_id = marker.embargo_id
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        entries = recorded_entries_for_case(
            case_id=case.id_, dl=self.datalayer
        )
        state = self._relay_state(case, marker, entries)
        if state is _RelayState.NOT_YET:
            return Status.SUCCESS  # kept: a later run relays it
        if state is _RelayState.CLOSED:
            self._discharge(marker)
            return Status.SUCCESS
        try:
            self._resolve_parties(case, marker)
        except VultronError as exc:
            # The proposal was already accepted and the case created and
            # announced, so this is a fault in the manager's own records,
            # never the sender's.  BTBridge reads a VultronError as a protocol
            # outcome, so it is re-raised as the internal error it is, which
            # the handler raises rather than refusing (ADR-0095), as the
            # base relay does for its own store's anomalies.
            raise RuntimeError(
                f"{self.name}: cannot relay creation-time revision"
                f" '{self._embargo_id}' on case '{self._case_id}': {exc}"
            ) from exc
        if state is _RelayState.COMMITTED:
            self._complete_committed(marker, entries)
        elif self._recipients:
            if (status := super().update()) is not Status.SUCCESS:
                return status
            self._index_relayed(marker)
        # else: the owner reported to itself, so there is nobody to invite.
        self._discharge(marker)
        return Status.SUCCESS

    def _pending_marker(self) -> PendingCreationTimeRevisionRelay | None:
        """The case's relay obligation, if one is still recorded."""
        assert self.datalayer is not None
        if not self._case_id:
            return None
        stored = self.datalayer.read(
            PendingCreationTimeRevisionRelay.build_id(self._case_id)
        )
        return (
            stored
            if isinstance(stored, PendingCreationTimeRevisionRelay)
            else None
        )

    def _index_relayed(self, marker: PendingCreationTimeRevisionRelay) -> None:
        """Index the sent Invite for the owner's default selection (EP-08-002)."""
        assert self.datalayer is not None
        record_embargo_proposal_index(
            self.datalayer,
            marker.case_id,
            marker.embargo_id,
            marker.proposal_id,
        )

    def _discharge(self, marker: PendingCreationTimeRevisionRelay) -> None:
        """Delete the marker: the relay is no longer owed."""
        assert self.datalayer is not None
        self.datalayer.delete(_MARKER_TYPE, marker.id_)
        self.logger.info(
            "%s: relay of creation-time revision '%s' on case '%s' discharged",
            self.name,
            marker.embargo_id,
            marker.case_id,
        )

    def _relay_state(
        self,
        case: VulnerabilityCase,
        marker: PendingCreationTimeRevisionRelay,
        entries: list[CaseLedgerEntry],
    ) -> _RelayState:
        """Decide, without writing anything, what the owed relay still needs."""
        if not any(e.event_type == CREATE_CASE_EVENT_TYPE for e in entries):
            # Only a retry outside the case tree reaches this: the tree runs
            # the relay after its ledger commit.
            reason = (
                "waits for the case's creation entries (CM-14-007, CM-14-011)"
            )
            state = _RelayState.NOT_YET
        elif marker.embargo_id not in {
            _as_id(e) for e in case.proposed_embargoes
        }:
            reason, state = "is no longer an open proposal", _RelayState.CLOSED
        elif any(e.log_object_id == marker.proposal_id for e in entries):
            reason, state = "was already relayed", _RelayState.COMMITTED
        else:
            return _RelayState.SEND
        self.feedback_message = (
            f"creation-time revision '{marker.embargo_id}' on case"
            f" '{case.id_}' {reason} — nothing sent"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return state

    def _complete_committed(
        self,
        marker: PendingCreationTimeRevisionRelay,
        entries: list[CaseLedgerEntry],
    ) -> None:
        """Finish a relay that failed after committing its Invite.

        The PEC INVITE is legality-gated, so applying it again changes nothing
        it already changed (EP-09-004); the index follows the send (EP-08-002).
        """
        entry = next(
            e for e in entries if e.log_object_id == marker.proposal_id
        )
        deadline = invite_rsvp_deadline(entry.payload_snapshot)
        dl = cast(CaseOutboxPersistence, self.datalayer)
        for recipient_id in self._recipients:
            self._invite_where_legal(dl, recipient_id, deadline)
        self._index_relayed(marker)

    def _resolve_parties(
        self, case: VulnerabilityCase, marker: PendingCreationTimeRevisionRelay
    ) -> None:
        """Set the proposer (the loser) and the one invitee (the winner)."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        owner_id = _as_id(case.attributed_to)
        if not owner_id:
            raise BtNodePreconditionError(
                f"case '{case.id_}' names no CASE_OWNER (CP-09-001)"
            )
        # The reporter's terms arrived as the sender proposal (EP-04-004).
        reporter_id = report_author_id(self.datalayer, marker.report_id)
        if marker.losing_source == EmbargoDurationSource.SENDER_PROPOSAL:
            self._proposer_id, winner_id = reporter_id, owner_id
        else:
            self._proposer_id, winner_id = owner_id, reporter_id
        # Shared recipient selection (CM-10-007), narrowed to the other party:
        # nobody else held terms at creation (EP-04-011).
        self._recipients = [
            actor_id
            for actor_id in invitation_recipients(
                case,
                self.datalayer,
                excluding={self.actor_id, self._proposer_id},
            )
            if actor_id == winner_id
        ]
        if not self._recipients and winner_id == self._proposer_id:
            # The owner reported to itself: one party held both sets of terms,
            # so there is nobody else to invite.
            self.logger.info(
                "%s: '%s' is both reporter and CASE_OWNER — no other party to"
                " relay revision '%s' to",
                self.name,
                winner_id,
                marker.embargo_id,
            )
            return
        if not self._recipients:
            # EP-04-011 says MUST relay; a registered revision whose Invite is
            # never sent is a revision nobody can answer.
            raise BtNodePreconditionError(
                f"winning party '{winner_id}' is not an invitation recipient"
                f" on case '{case.id_}' (proposer '{self._proposer_id}')"
            )


__all__ = [
    "RecordCreationTimeRevisionRelayNode",
    "RelayCreationTimeRevisionNode",
]
