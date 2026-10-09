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

"""Relay of every open embargo proposal to a participant that has just joined.

A participant that joins while a revision (or a first proposal) is on the
table was not on the roster when the CASE_MANAGER relayed that proposal
(EP-09-002), so nobody asks it about the proposal.  It signs the embargo in
force (CM-10-001) but would lapse on arrival if the owner activated longer
terms (EP-05-001) without ever having been asked.  This node closes the gap
(EP-09-011): after the joiner is seated, the CASE_MANAGER emits one
``Invite(EmbargoEvent)`` per open proposal to the joiner, as ``actor`` with
the original proposer in ``attributedTo`` (CM-24-001, CM-24-002), and commits
each as a ledger entry, exactly as for the participants who were present when
the proposal was made.

The emission is the shared relay emit
(:class:`~vultron.core.behaviors.embargo.nodes.relay.RelayEmbargoInviteToEachNode`);
this subclass supplies only what differs: one recipient, many proposals, and
the proposer recovered from the proposal's committed ledger entry.
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.wire_keys import wire_key
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.sync_helpers import recorded_entries_for_case


class RelayOpenProposalsToJoinerNode(RelayEmbargoInviteToEachNode):
    """Invite a new joiner to each embargo proposal open when it joins.

    Skips a proposal the joiner's row for has already left ``UNINVITED``.
    Each relay applies PEC ``INVITE`` to the joiner's row, so a re-run of the
    effects (a resumed accept) does not invite the joiner twice.  Everything that
    goes wrong here is the manager's own store failing, never a refusal of
    the joiner's Accept, so it raises (Regime 1, ADR-0087).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(
            case_id=case_id,
            embargo_id="",
            proposer_id="",
            name=name or self.__class__.__name__,
        )
        self._invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"sync_port": "/sync_port"}

    def _load_relay_inputs(self) -> None:
        self._recipients = [self._invitee_id]

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        if self._invitee_id == self.actor_id:
            return Status.SUCCESS
        pending = [
            embargo_id
            for embargo_id in case.proposed_embargo_ids
            if self._consent_row_for(case, embargo_id)
            == EmbargoConsentState.UNINVITED
        ]
        if not pending:
            return Status.SUCCESS
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f
        if self._invitee_id not in invitation_recipients(
            case, self.datalayer, excluding={self.actor_id}
        ):
            raise RuntimeError(
                f"{self.name}: joiner '{self._invitee_id}' is not an"
                f" invitation recipient on case '{self._case_id}'"
            )
        entries = recorded_entries_for_case(
            case_id=case.id_, dl=self.datalayer
        )
        for embargo_id in pending:
            self._embargo_id = embargo_id
            self._proposer_id = self._proposer_of(case, embargo_id, entries)
            self._relay_to(self._invitee_id)
        self.feedback_message = (
            f"Relayed {len(pending)} open embargo proposal(s) on case"
            f" '{self._case_id}' to joiner '{self._invitee_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _consent_row_for(
        self, case: VulnerabilityCase, embargo_id: str
    ) -> EmbargoConsentState:
        """The joiner's consent to *embargo_id*; ``UNINVITED`` when never asked."""
        assert self.datalayer is not None
        participant_id = case.actor_participant_index.get(self._invitee_id)
        record = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if record is None:
            raise RuntimeError(
                f"{self.name}: no participant record for joiner"
                f" '{self._invitee_id}' on case '{self._case_id}'"
            )
        return cast(CaseParticipant, record).consent_for(embargo_id)

    def _proposer_of(
        self,
        case: VulnerabilityCase,
        embargo_id: str,
        entries: list[CaseLedgerEntry],
    ) -> str:
        """Who proposed *embargo_id*, read from its committed proposal entry.

        A relayed or creation-time Invite names the proposer in
        ``attributedTo``; a proposal the proposer sent itself names it as
        ``actor``.
        """
        proposal_id = case.pending_embargo_proposal_index.get(embargo_id)
        entry = next(
            (
                e
                for e in entries
                if proposal_id is not None and e.log_object_id == proposal_id
            ),
            None,
        )
        if entry is None:
            raise RuntimeError(
                f"{self.name}: open proposal '{embargo_id}' on case"
                f" '{self._case_id}' has no committed proposal entry, so its"
                " proposer is unknown"
            )
        snapshot = entry.payload_snapshot
        proposer = _as_id(
            snapshot.get(wire_key("attributed_to"))
            or snapshot.get(wire_key("actor"))
        )
        if not proposer:
            raise RuntimeError(
                f"{self.name}: proposal entry '{proposal_id}' names no"
                " proposer"
            )
        return cast(str, proposer)


__all__ = ["RelayOpenProposalsToJoinerNode"]
