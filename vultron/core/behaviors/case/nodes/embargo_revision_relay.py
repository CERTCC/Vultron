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

``InitializeCreationEmbargoNode`` registers the shortest-wins loser as a
pending revision inside ``InitializeDefaultEmbargoNode`` and publishes it as a
:class:`CreationTimeRevision`.  :class:`RelayCreationTimeRevisionNode` sends it
like any other revision (EP-09, ADR-0113) once the case tree has finished its
initialization sequence (CM-14-007), then indexes it so the owner's default
selection reaches it (EP-08-002).

This module is not re-exported from ``vultron.core.behaviors.case.nodes``:
the relay subclasses the embargo relay emit, whose module imports the case
role gates, so a re-export from the case node package would close an import
cycle.  Import it from here.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.embargo_revision import (
    REVISION_KEY,
    CreationTimeRevision,
    creation_revision_parties,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
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
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import BtNodePreconditionError, VultronError

logger = logging.getLogger(__name__)


class RelayCreationTimeRevisionNode(RelayEmbargoInviteToEachNode):
    """Relay the creation-time revision to the party whose terms won (EP-04-011).

    The #3913 relay emit, fed from what ``InitializeCreationEmbargoNode``
    published rather than from a received proposal: the CASE_MANAGER emits
    ``Invite(EmbargoEvent)`` as ``actor`` with the losing party in
    ``attributedTo`` (CM-24-001, CM-24-002), under the proposal id the
    registration minted, and commits it in this tree.  The committed Invite is
    the revision's proposal entry: no proposal activity exists at creation, and
    #4099's replay recognises the entry as a relayed Invite (EP-09-007).  The
    losing party is the proposer and is not invited (EP-09-002).  The case
    tree places this node after its ledger commit, so no modification is
    initiated before the initialization sequence is complete (CM-14-007).

    **The index is written after the Invite is sent**, never at registration.
    The bootstrap ``Create(VulnerabilityCase)`` carries the case whole; had it
    carried ``embargo → Invite id``, the invitee's idempotency guard
    (``EmbargoProposalNotYetRecordedNode``) would read the Invite as already
    answered and skip it.  The invitee indexes the Invite when it answers, and
    the proposer's replica learns it from the replayed entry
    (``ApplyEmbargoInviteFromLedgerNode``), so the owner's default selection
    reaches it on either side (EP-08-002).

    Nothing is relayed, and the node succeeds, when no revision was registered
    in this execution (no contest, a tie, or a case already initialized), when
    the published revision names another case, when it is no longer open, or
    when its Invite is already in the ledger.  The last two are read from the
    store, not the blackboard.  A reporter that is itself the CASE_OWNER has
    nobody to invite, so nothing is relayed or indexed.  A revision whose
    parties cannot be resolved, or whose winning party is not an invitation
    recipient, raises: the case is already created and announced, so the
    fault is the manager's own, never a refusal of the sender's proposal.  A
    failed relay is not retried by a redelivery,
    which never reaches the registration (#4121).
    """

    def __init__(self, report_id: str | None, name: str | None = None) -> None:
        # The case, embargo and proposer are known only at tick time, from the
        # published revision; ``_load_relay_inputs`` and ``_resolve_parties``
        # set them, so the base constructor gets placeholders.
        super().__init__(
            case_id="",
            embargo_id="",
            proposer_id="",
            name=name or self.__class__.__name__,
        )
        self._report_id = report_id
        self._revision: CreationTimeRevision | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        REVISION_KEY: PortInformation(
            data_type=CreationTimeRevision | None, required=False
        ),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            REVISION_KEY: f"/{REVISION_KEY}",
            "sync_port": "/sync_port",
        }

    def _load_relay_inputs(self) -> None:
        self._recipients = []
        revision = self._try_get_input(REVISION_KEY)
        current_case_id = self._try_get_input("case_id")
        self._revision = (
            revision
            if isinstance(revision, CreationTimeRevision)
            and revision.case_id == current_case_id
            else None
        )
        if self._revision is not None:
            self._case_id = self._revision.case_id
            self._embargo_id = self._revision.embargo_id

    def _activity_id_for(self, recipient_id: str) -> str | None:
        return self._revision.proposal_id if self._revision else None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if self._revision is None:
            self.feedback_message = "no creation-time revision to relay"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        if not self._still_to_relay(case, self._revision):
            return Status.SUCCESS
        try:
            self._resolve_parties(case, self._revision)
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
        if not self._recipients:
            return Status.SUCCESS  # the owner reported to itself
        status = super().update()
        if status is Status.SUCCESS:
            self._index_relayed(self._revision)
        return status

    def _index_relayed(self, revision: CreationTimeRevision) -> None:
        """Index the sent Invite for the owner's default selection (EP-08-002)."""
        assert self.datalayer is not None
        record_embargo_proposal_index(
            self.datalayer,
            revision.case_id,
            revision.embargo_id,
            revision.proposal_id,
        )

    def _still_to_relay(
        self, case: VulnerabilityCase, revision: CreationTimeRevision
    ) -> bool:
        """True while the revision is open and its Invite is not yet committed."""
        assert self.datalayer is not None
        if revision.embargo_id not in {
            _as_id(e) for e in case.proposed_embargoes
        }:
            reason = "is no longer an open proposal"
        elif any(
            entry.log_object_id == revision.proposal_id
            for entry in recorded_entries_for_case(
                case_id=case.id_, dl=self.datalayer
            )
        ):
            reason = "was already relayed"
        else:
            return True
        self.feedback_message = (
            f"creation-time revision '{revision.embargo_id}' on case"
            f" '{case.id_}' {reason} — nothing to relay"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return False

    def _resolve_parties(
        self, case: VulnerabilityCase, revision: CreationTimeRevision
    ) -> None:
        """Set the proposer (the loser) and the one invitee (the winner)."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        self._proposer_id, winner_id = creation_revision_parties(
            self.datalayer, case, revision.losing_source, self._report_id
        )
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
                revision.embargo_id,
            )
            return
        if not self._recipients:
            # EP-04-011 says MUST relay; a registered revision whose Invite is
            # never sent is a revision nobody can answer.
            raise BtNodePreconditionError(
                f"winning party '{winner_id}' is not an invitation recipient"
                f" on case '{case.id_}' (proposer '{self._proposer_id}')"
            )


__all__ = ["RelayCreationTimeRevisionNode"]
