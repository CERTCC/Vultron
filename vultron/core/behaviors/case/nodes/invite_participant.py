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


"""Invitee idempotency and record-exists guard nodes.

Guards a duplicate ``Accept(Invite(actor, case))`` and refuses an Accept whose
invitee has no participant record (CM-11-021): the record is created when the
stub Invite is sent (CM-11-006), never on the Accept.  The activation step
lives in ``invite_participant_persist.py``. Composed by
``create_accept_invite_actor_to_case_tree`` (BTND-07-003).
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.replication_state import VultronReplicationState

logger = logging.getLogger(__name__)


class CheckInviteeNotAlreadyParticipantNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """Idempotency guard: FAILURE when invitee is already a fully-joined participant.

    Returns SUCCESS (allow proceeding) when the invitee is NOT yet
    registered in ``case.actor_participant_index``, or when the invitee IS
    registered but join-time backfill is still incomplete (resume path), or
    when the invitee IS in the index as an *inert* record (``joined=False``,
    CM-11-006) that has not yet accepted the stub Invite.

    Returns FAILURE (abort tree) with no ledger write when the invitee is
    already a participant AND backfill is complete — a true idempotent no-op
    (CLP-13-001, CLP-13-002).

    Four paths:

    1. **No record**: invitee not yet in index → SUCCESS
       (``invitee_already_participant=False``, ``invitee_joined=False``).
       ``InviteeHasParticipantRecordNode`` refuses it next, before any write:
       an Accept never creates a participant (CM-11-021).
    2. **Inert record** (ADR-0114, CM-11-006): invitee in index but
       ``joined=False``, no backfill marker yet → SUCCESS with
       ``invitee_already_participant=True``, ``invitee_joined=False``.
       Downstream nodes activate the existing record, and the backfill uses
       the *fresh* path (fan-out doesn't reach an inert invitee).
    3. **Backfill-incomplete resume**: invitee in index, ``joined=True``, but
       backfill is still in progress → SUCCESS with
       ``invitee_already_participant=True``, ``invitee_joined=True``.
    4. **Backfill-complete (true duplicate)**: invitee in index, backfill done
       → ``_idempotent_failure`` (FAILURE, INFO log, no ledger write —
       CLP-13-001).  A *removed* participant (CM-31-001) takes this path
       whatever its backfill state: it is sent no full-case Invite and no
       backfill until it is reinstated (CM-31-013).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "invitee_case": PortInformation(data_type=object, required=True),
        "invitee_already_participant": PortInformation(
            data_type=object, required=True
        ),
        "invitee_joined": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_case": "/invitee_case",
            "invitee_already_participant": "/invitee_already_participant",
            "invitee_joined": "/invitee_joined",
        }

    def _read_participant(self, case: object) -> CaseParticipant | None:
        """Return the invitee's stored participant record, or None if absent."""
        assert self.datalayer is not None
        index = getattr(case, "actor_participant_index", {}) or {}
        participant_id = index.get(self.invitee_id)
        if not participant_id:
            return None
        p = self.datalayer.read(participant_id)
        if not isinstance(p, CaseParticipant):
            return None
        return p

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        existing_ids = [_as_id(p) for p in case.case_participants]
        in_index = (
            self.invitee_id in case.actor_participant_index
            or self.invitee_id in existing_ids
        )
        if not in_index:
            # Fresh: not in index at all
            self._set_output("invitee_already_participant", False)
            self._set_output("invitee_joined", False)
            self._set_output("invitee_case", case)
            return Status.SUCCESS

        # In index — check whether the participant has joined
        record = self._read_participant(case)
        joined = record.joined if record is not None else None

        if joined is False:
            # Inert record from invite-send time (ADR-0114, CM-11-006).
            # Not a true duplicate; treat as fresh-Accept path so the commit
            # fan-out (which skips inert participants) is handled correctly.
            self.logger.info(
                "%s: actor '%s' has an inert record in case '%s' (joined=False)"
                " — treating as fresh Accept",
                self.name,
                self.invitee_id,
                self.case_id,
            )
            self._set_output("invitee_already_participant", True)
            self._set_output("invitee_joined", False)
            self._set_output("invitee_case", case)
            return Status.SUCCESS

        if record is not None and record.removed:
            # A removed participant joined long ago and is sent no Invite,
            # case seed or backfill until the Case Owner reinstates it
            # (CM-31-013): a replayed Accept moves nothing (CLP-13-001).
            self._set_output("invitee_already_participant", True)
            self._set_output("invitee_joined", True)
            return self._idempotent_failure(
                self.logger,
                "%s: actor '%s' was removed from case '%s'"
                " — skipping (CM-31-013, CLP-13-001)",
                self.name,
                self.invitee_id,
                self.case_id,
            )

        # joined=True (or unknown): check backfill state
        state = self._read_replication_state(case.id_)
        if state is not None and (
            state.join_backfill_complete
            or state.join_backfill_target_index == -1
        ):
            # True duplicate: backfill complete — silent FAILURE, no ledger
            # write (CLP-13-001).
            self._set_output("invitee_already_participant", True)
            self._set_output("invitee_joined", True)
            return self._idempotent_failure(
                self.logger,
                "%s: actor '%s' already participant in case '%s'"
                " — skipping (idempotent, CLP-13-001)",
                self.name,
                self.invitee_id,
                self.case_id,
            )

        # Resume path: backfill is incomplete (or no marker yet).
        if state is None:
            self.logger.info(
                "%s: actor '%s' already participant in case '%s' with no "
                "replication marker; resuming join-time backfill",
                self.name,
                self.invitee_id,
                self.case_id,
            )
        else:
            self.logger.info(
                "%s: actor '%s' already participant in case '%s' but"
                " backfill is incomplete; resuming join-time backfill",
                self.name,
                self.invitee_id,
                self.case_id,
            )
        self._set_output("invitee_already_participant", True)
        self._set_output("invitee_joined", True)
        self._set_output("invitee_case", case)
        return Status.SUCCESS

    def _read_replication_state(
        self, case_id: str
    ) -> VultronReplicationState | None:
        if self.datalayer is None:
            return None
        state_id = VultronReplicationState(
            case_id=case_id,
            peer_id=self.invitee_id,
        ).id_
        state = self.datalayer.read(state_id)
        if isinstance(state, VultronReplicationState):
            return state
        return None


class InviteeHasParticipantRecordNode(DataLayerConditionWithPorts):
    """Guard: the invitee already has a participant record (CM-11-021).

    The CASE_MANAGER creates the record when it sends the stub Invite
    (CM-11-006), so an ``Accept(Invite(Actor, VulnerabilityCaseStub))`` finds
    it; an Accept never creates one.  FAILURE, with the reason as
    ``feedback_message``, when the case holds no record for the invitee.  The
    guard runs before the tree commits anything, so a refused Accept writes
    nothing.

    Writes the record to ``new_invite_participant`` for the downstream nodes.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "new_invite_participant": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"new_invite_participant": "/new_invite_participant"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        participant_id = case.actor_participant_index.get(self.invitee_id)
        record = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if not isinstance(record, CaseParticipant):
            self.feedback_message = (
                f"no participant record for '{self.invitee_id}' in case"
                f" '{self.case_id}' — Accept refused (CM-11-021)"
            )
            self.logger.warning(
                "%s: no participant record for invitee '%s' in case '%s'"
                " — refusing Accept(Invite) (CM-11-021)",
                self.name,
                self.invitee_id,
                self.case_id,
            )
            return Status.FAILURE
        self._set_output("new_invite_participant", record)
        return Status.SUCCESS
