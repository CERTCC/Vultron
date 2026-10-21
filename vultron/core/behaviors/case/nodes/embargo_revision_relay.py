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
pending revision inside ``InitializeDefaultEmbargoNode``.
:class:`RelayCreationTimeRevisionNode` sends the revision like any other
(EP-09, ADR-0113) once the case tree has finished its initialization sequence
(CM-14-007), and indexes it so the owner's default selection reaches it
(EP-08-002).

The relay is part of the creation act: the case tree runs it in the same
``ActTransaction`` as the creation, after the ledger commit (ADR-0146,
CLP-07-015).  A failed relay rolls the whole creation back, so a redelivered
proposal creates the case again and registers and relays the revision in one
act.  Nothing is kept for a later run.

This module is not re-exported from ``vultron.core.behaviors.case.nodes``:
the relay subclasses the embargo relay emit, whose module imports the case
role gates, so a re-export from the case node package would close an import
cycle.  Import it from here.
"""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.embargo_revision import (
    CANDIDATE_KEY,
    CreationTimeRevisionCandidate,
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
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.recipients import invitation_recipients
from vultron.errors import BtNodePreconditionError, VultronError

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig

logger = logging.getLogger(__name__)


class RelayCreationTimeRevisionNode(RelayEmbargoInviteToEachNode):
    """Relay the creation-time revision to the party whose terms won (EP-04-011).

    The #3913 relay emit, fed from the case rather than from a received
    embargo proposal: the CASE_MANAGER emits ``Invite(EmbargoEvent)`` as
    ``actor`` with the losing party in ``attributedTo`` (CM-24-001,
    CM-24-002) and commits it in this tree once it is queued (ADR-0119).  The
    committed Invite is the revision's proposal entry: no proposal activity
    exists at creation, and #4099's replay recognises the entry as a relayed
    Invite (EP-09-007).  The losing party is the proposer and is not invited
    (EP-09-002).  The case tree places this node after its ledger commit, so
    no modification is initiated before the initialization sequence is
    complete (CM-14-007).

    **What it relays.**  ``ResolveCreationTimeRevisionNode`` publishes the
    contested proposal and whose terms lost (``CANDIDATE_KEY``) only in the
    execution whose ``InitializeCreationEmbargoNode`` registers it, so the
    node relays only in the act that registered the revision.  It reads the
    revision from the case: the registration left it as the case's one open
    proposal.  A redelivered proposal whose case was already created skips
    the initialization, publishes no candidate, and relays nothing.

    **The Invite's id is derived** from the proposal that created the case
    (*answers*), the case, the revision and the invitee, never minted
    (ID-04-004, OX-06-002), so the same act relays under one id however often
    it runs.  A rolled-back creation sent nothing, so the redelivery that
    creates the case again relays under its own new case's id.  The index is written after
    the Invite is sent, never at registration: the bootstrap
    ``Create(VulnerabilityCase)`` carries the case whole, and had it carried
    ``embargo → Invite id`` the invitee's idempotency guard
    (``EmbargoProposalNotYetRecordedNode``) would read the Invite as already
    answered and skip it.  The invitee indexes the Invite when it answers, and
    the proposer's replica learns it from the replayed entry
    (``ApplyEmbargoInviteFromLedgerNode``), so the owner's default selection
    reaches it on either side (EP-08-002).

    A reporter that is itself the CASE_OWNER leaves nobody to invite:
    nothing is sent or indexed.  A revision the case does not hold open,
    a revision whose parties cannot be resolved, or a winning party that is
    not an invitation recipient raises: the creation act rolls back, since
    the fault is the manager's own, never a refusal of the sender's proposal.

    Args:
        proposal_id: The ``Create(as_CaseProposal)``'s proposal; the relay
            answers it.
        report_id: The report the case is created from; its author is the
            reporter (EP-04-004).
        actor_config: Source of the RSVP windows (CM-28-012).
        name: Optional node name.
    """

    def __init__(
        self,
        proposal_id: str,
        report_id: str | None,
        actor_config: "ActorConfig | None" = None,
        name: str | None = None,
    ) -> None:
        # The case, embargo and proposer are known only at tick time;
        # ``_load_relay_inputs`` and ``_resolve_parties`` set them, so the
        # base constructor gets placeholders.
        super().__init__(
            case_id="",
            embargo_id="",
            proposer_id="",
            name=name or self.__class__.__name__,
            actor_config=actor_config,
            answers=proposal_id,
        )
        self._report_id = report_id
        self._candidate: CreationTimeRevisionCandidate | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        CANDIDATE_KEY: PortInformation(
            data_type=CreationTimeRevisionCandidate | None, required=False
        ),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            CANDIDATE_KEY: f"/{CANDIDATE_KEY}",
            "sync_port": "/sync_port",
        }

    def _load_relay_inputs(self) -> None:
        self._recipients = []
        case_id = self._try_get_input("case_id")
        self._case_id = case_id if isinstance(case_id, str) else ""
        candidate = self._try_get_input(CANDIDATE_KEY)
        self._candidate = (
            candidate
            if isinstance(candidate, CreationTimeRevisionCandidate)
            else None
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        candidate = self._candidate
        if candidate is None:
            self.feedback_message = "no creation-time revision to relay"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        try:
            self._embargo_id = self._open_revision(case, candidate)
            self._resolve_parties(case, candidate)
        except VultronError as exc:
            # The proposal was already accepted and the case initialized, so
            # this is a fault in the manager's own records, never the
            # sender's.  BTBridge reads a VultronError as a protocol outcome,
            # so it is re-raised as the internal error it is, which the
            # handler raises rather than refusing (ADR-0095), as the base
            # relay does for its own store's anomalies.
            raise RuntimeError(
                f"{self.name}: cannot relay the creation-time revision on"
                f" case '{self._case_id}': {exc}"
            ) from exc
        if not self._recipients:
            # The owner reported to itself, so there is nobody to invite.
            return Status.SUCCESS
        if (status := super().update()) is not Status.SUCCESS:
            return status
        self._index_relayed()
        return Status.SUCCESS

    @staticmethod
    def _open_revision(
        case: VulnerabilityCase, candidate: CreationTimeRevisionCandidate
    ) -> str:
        """The revision the registration left open on *case*.

        Raises:
            BtNodePreconditionError: the case does not hold the registered
                revision as an open proposal.
        """
        revision_id = candidate.embargo.id_
        if revision_id not in case.proposed_embargo_ids:
            raise BtNodePreconditionError(
                f"case '{case.id_}' holds no open proposal '{revision_id}',"
                " though this act registered it (EP-04-003)"
            )
        return revision_id

    def _index_relayed(self) -> None:
        """Index the sent Invite for the owner's default selection (EP-08-002)."""
        assert self.datalayer is not None
        (winner_id,) = self._recipients
        invite_id = self._activity_id_for(winner_id)
        assert invite_id is not None  # derived: the relay answers a proposal
        record_embargo_proposal_index(
            self.datalayer, self._case_id, self._embargo_id, invite_id
        )

    def _resolve_parties(
        self, case: VulnerabilityCase, candidate: CreationTimeRevisionCandidate
    ) -> None:
        """Set the proposer (the loser) and the one invitee (the winner)."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        # The loser proposed the revision (MSM-07-005, #4152); the reporter's
        # terms arrived as the sender proposal (EP-04-004).
        self._proposer_id, winner_id = creation_revision_parties(
            self.datalayer, case, candidate.losing_source, self._report_id
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
                self._embargo_id,
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
