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


"""Invitee idempotency-guard and participant-construction leaf nodes.

Guards a duplicate ``Accept(Invite(actor, case))`` and constructs the
invitee ``CaseParticipant`` at RM.START (ADR-0089 birth step 1). The
persist/advance steps live in ``invite_participant_persist.py``. Composed by
``create_accept_invite_actor_to_case_tree`` (BTND-07-003).
"""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.replication_state import VultronReplicationState
from vultron.enums.roles import validate_roles

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

    1. **Fresh invite**: invitee not yet in index → SUCCESS (tree runs in full,
       ``invitee_already_participant=False``, ``invitee_joined=False``).
    2. **Inert record** (ADR-0114, CM-11-006): invitee in index but
       ``joined=False``, no backfill marker yet → SUCCESS with
       ``invitee_already_participant=True``, ``invitee_joined=False``.
       Downstream nodes load the existing record instead of creating a new one,
       and the backfill uses the *fresh* path (fan-out doesn't reach an inert
       invitee).
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


class CreateInviteeParticipantNode(DataLayerActionWithPorts):
    """Construct a ``CaseParticipant`` record for the invitee, at RM.START.

    Under ADR-0089 birth is three steps and RM advances only through the sole
    writer.  This node performs step 1 (*construct*): it builds the participant
    auto-seeded at ``RM.START`` (by ``_init_participant_status_if_empty``) and
    writes it to the blackboard.  :class:`PersistInviteeParticipantNode`
    attaches and saves it (step 2), then
    :class:`AdvanceInviteeToReceivedNode` advances it to ``RM.RECEIVED``
    through :class:`CreateParticipantStatusNode` (step 3).  Handing a detached
    participant *already* at ``RM.RECEIVED`` onto the blackboard was the
    pattern ADR-0089 removes.

    Per CM-11-001, ``Accept(Invite)`` records ``RM.RECEIVED`` only; the full
    triage cycle (VALID/ACCEPTED) is a distinct subsequent step run by the
    invitee after the case replica has been delivered (PCR-08-010).

    Writes ``new_invite_participant`` to the blackboard.
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        name: str | None = None,
        *,
        invite_id: str,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id
        self.invite_id = invite_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "invitee_already_participant": PortInformation(
            data_type=object, required=True
        ),
        "invitee_case": PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "new_invite_participant": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_already_participant": "/invitee_already_participant",
            "invitee_case": "/invitee_case",
            "new_invite_participant": "/new_invite_participant",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._invitee_case_bb = self.get_input("invitee_case")
        except (NoDataAvailable, NotImplementedError):
            self._invitee_case_bb = None
        try:
            self._already_participant_bb = self.get_input(
                "invitee_already_participant"
            )
        except (NoDataAvailable, NotImplementedError):
            self._already_participant_bb = False

    def _read_invite_roles(self) -> list:
        """Read roles from the stub Invite this store recorded (CM-11-017).

        The CASE_MANAGER recorded the Invite when it sent it; that record, not
        the copy the invitee's ``Accept`` embeds (which the sender wrote),
        names the roles the participant takes (CM-17-003).

        Returns an empty list when the record is absent or carries no roles.
        """
        assert self.datalayer is not None
        invite = self.datalayer.read(self.invite_id)
        if invite is None:
            self.logger.warning(
                "%s: no recorded Invite '%s' to read roles from [invitee=%s]",
                self.name,
                self.invite_id,
                self.invitee_id,
            )
            return []
        raw_roles = getattr(invite, "roles", None)
        if not raw_roles:
            return []
        try:
            return validate_roles(raw_roles)
        except (TypeError, ValueError, KeyError):
            self.logger.warning(
                "%s: could not coerce invite roles %r — ignoring",
                self.name,
                raw_roles,
            )
            return []

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self._invitee_case_bb
        if case is None:
            self.logger.error(
                "%s: invitee_case not found in blackboard", self.name
            )
            return Status.FAILURE

        if self._already_participant_bb:
            participant_id = case.actor_participant_index.get(self.invitee_id)
            if participant_id is None:
                self.logger.error(
                    "%s: invitee marked as existing but no participant ID"
                    " found for actor '%s'",
                    self.name,
                    self.invitee_id,
                )
                return Status.FAILURE
            existing = self.datalayer.read(participant_id)
            if not isinstance(existing, CaseParticipant):
                self.logger.error(
                    "%s: expected existing participant '%s'",
                    self.name,
                    participant_id,
                )
                return Status.FAILURE
            self._set_output(
                "new_invite_participant", cast(CaseParticipant, existing)
            )
            self.logger.info(
                "%s: reusing existing participant '%s' for backfill resume",
                self.name,
                participant_id,
            )
            return Status.SUCCESS

        roles = self._read_invite_roles()
        if not roles:
            # CM-11-019: never create a participant with an empty role list.
            # The Invite should have been refused at send time, but guard here
            # too in case a malformed Invite arrives (defence in depth).
            self.feedback_message = (
                f"{self.name}: no roles in Accept(Invite) for invitee"
                f" '{self.invitee_id}' — invite must carry roles (CM-11-019)"
            )
            self.logger.error(
                "%s: no roles in invite for invitee '%s' in case '%s'"
                " — refusing participant creation (CM-11-019)",
                self.name,
                self.invitee_id,
                self.case_id,
            )
            return Status.FAILURE
        # ADR-0089 birth step 1 (construct): build the participant auto-seeded
        # at RM.START. PersistInviteeParticipantNode attaches it and
        # AdvanceInviteeToReceivedNode advances it to RM.RECEIVED through the
        # sole writer. CM-11-001: Accept(Invite) records RM.RECEIVED only; the
        # full triage cycle is a later step (PCR-08-010).
        participant = CaseParticipant(
            id_=(
                f"{self.case_id}/participants/{self.invitee_id.split('/')[-1]}"
            ),
            attributed_to=self.invitee_id,
            context=self.case_id,
            case_roles=roles,
        )
        # The record holds a row for every register entry from the moment it
        # exists (ADR-0122): the consent nodes that follow sign it before
        # PersistInviteeParticipantNode attaches it to the case.
        participant.write_uninvited_rows(
            entry.embargo_id for entry in case.embargo_register
        )
        if roles:
            self.logger.info(
                "%s: set case_roles %s on participant '%s' from invite"
                " (CM-17-003)",
                self.name,
                roles,
                self.invitee_id,
            )
        self._set_output("new_invite_participant", participant)
        self.logger.info(
            "%s: constructed participant object for invitee '%s' at RM.START;"
            " to be advanced to RM.RECEIVED through the writer (CM-11-001)",
            self.name,
            self.invitee_id,
        )
        return Status.SUCCESS
