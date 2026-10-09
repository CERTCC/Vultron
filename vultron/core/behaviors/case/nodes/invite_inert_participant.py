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

"""Invite-time inert-participant creation and reply-effect nodes (AC-1, AC-2, AC-3).

Nodes in this module handle the three lifecycle steps that ADR-0114 adds to
the stub-Invite workflow:

- :class:`CreateInertInviteeParticipantNode` — at invite-send time, records
  the invitee at RM ``RECEIVED``, VF ``vf`` (VENDOR), and PEC ``INVITED``
  (when an embargo is in force).  Sets ``joined=False`` so the participant is
  inert and does not receive case content until it accepts (CM-11-006).
  Creating the record is the CASE_MANAGER's own act, with no wire message of
  its own, so it commits its own ``create_case_participant`` entry carrying the
  record as stored; replicas store it as received (ADR-0114, CM-31-012).  The
  status a later node adds (VF ``Vf``, an RM closure) has its own entry; the
  invitee's Accept and Reject messages are the entries for their consent and
  ``joined`` effects.

- :class:`AdvanceInviteeVFToVendorAwareNode` — after ``Accept`` or ``Reject``
  of the stub Invite, records vendor awareness (VF ``Vf``) on a VENDOR
  invitee's participant record (CM-11-009).  A no-op for non-VENDOR roles.

- :class:`~vultron.core.behaviors.case.nodes.invite_reject_participant.ApplyInviteRejectToParticipantNode`
  — on ``Reject``, moves the inert participant to RM ``CLOSED``, sets VF ``Vf``
  (VENDOR), and applies PEC ``DECLINED`` when an active embargo is in force
  (CM-11-007, CM-11-009); lives in its own module (BTND-07-004).
"""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
)
from vultron.core.behaviors.case.nodes.participant.roles import (
    suggested_roles_key,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.case.participant_ledger import (
    commit_case_participant_created,
)
from vultron.core.behaviors.case.stub_invite_lifetime import invitee_record
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.states.cs import CS_vf
from vultron.core.states.participant_embargo_consent import PEC_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole, validate_roles

logger = logging.getLogger(__name__)


class CreateInertInviteeParticipantNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Create the invitee's inert participant record at invite-send time.

    ADR-0114 / CM-11-006: the CASE_MANAGER records the invitee the moment it
    sends the stub Invite, before the invitee has had a chance to reply.  The
    record is *inert* (``joined=False``) so it does not receive case content
    through the active-participant filter (CM-10-004).

    The initial status is RM ``RECEIVED``, VF ``vf`` (vendor not yet aware)
    for VENDOR invitees, an ``UNINVITED`` consent row for every embargo
    register entry, and ``INVITED`` on the row for the active embargo when the
    case carries one (ADR-0122).  These are the exact values the
    CASE_MANAGER's acceptance of the future stub-Invite reply will start from
    (CM-11-009, CM-11-007).

    PRM-06-001: only a single status is written (the birth status at
    RM ``RECEIVED``).

    The record is built and attached through the shared
    ``_create_and_attach_participant`` helper (BTND-05-003); this node
    supplies only the seating policy (roles, birth status, consent row).
    An invitee that already has a record is decided before anything is
    built (:meth:`_existing_record_outcome`): a re-invite keeps the same
    record (CM-11-015), so the node never resets or re-seats it.
    """

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        recommendation_id: str | None = None,
        roles: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id
        self._injected_roles = roles
        self._roles_key = (
            f"/{suggested_roles_key(recommendation_id)}"
            if recommendation_id is not None
            else None
        )
        self._suggested_roles_bb: list | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "suggested_roles": PortInformation(data_type=list, required=False),
    }

    def _instance_port_remappings(self) -> dict[str, str]:
        if self._roles_key is None:
            return {}
        return {"suggested_roles": self._roles_key}

    def initialise(self) -> None:
        super().initialise()
        self._suggested_roles_bb = None
        if self._roles_key is None:
            return
        try:
            self._suggested_roles_bb = self.get_input("suggested_roles")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _resolve_roles(self) -> list[CVDRole]:
        """Resolve roles: injected > blackboard > default VENDOR."""
        if self._injected_roles:
            try:
                return validate_roles(self._injected_roles)
            except (TypeError, ValueError, KeyError):
                pass
        if (
            isinstance(self._suggested_roles_bb, list)
            and self._suggested_roles_bb
        ):
            if all(isinstance(r, CVDRole) for r in self._suggested_roles_bb):
                return list(self._suggested_roles_bb)
            try:
                return validate_roles(self._suggested_roles_bb)
            except (TypeError, ValueError, KeyError):
                pass
        return []

    def _build_initial_status(
        self, roles: list[CVDRole], case_id: str
    ) -> ParticipantStatus:
        """Return a single birth status at RM.RECEIVED (PRM-06-001)."""
        vf: VfDimension | None = None
        if CVDRole.VENDOR in roles:
            vf = VfDimension(state=CS_vf.vf)
        return ParticipantStatus(
            context=case_id,
            attributed_to=self.invitee_id,
            rm=RmDimension(state=RM.RECEIVED),
            vf=vf,
            cvd_role=roles,
        )

    def _existing_record_outcome(
        self, case: VulnerabilityCase
    ) -> Status | None:
        """Decide the outcome when the invitee already has a record.

        Runs before the role check, so a re-run without roles still succeeds
        on a record that is already there.  Returns ``None`` when the invitee
        has no record and must be seated.

        A record at ``RM.CLOSED`` is terminal, joined or not, and refused
        (FAILURE, CM-11-015, ADR-0085), as ``ReinviteNotToClosedParticipantNode``
        refuses it.  Any other record is kept: a joined one is never
        re-seated, and a re-invite keeps the same inert record (CM-11-015).
        Both are left unchanged.
        """
        assert self.datalayer is not None
        existing = invitee_record(self.datalayer, case, self.invitee_id)
        if existing is None:
            return None
        if existing.rm_closed:
            self.feedback_message = (
                f"{self.name}: invitee '{self.invitee_id}' is at RM.CLOSED in"
                f" case '{self.case_id}' — no rejoin (CM-11-015)"
            )
            self.logger.warning("%s", self.feedback_message)
            return Status.FAILURE
        self.logger.info(
            "%s: invitee '%s' already has %s record '%s' in case '%s'"
            " — kept unchanged",
            self.name,
            self.invitee_id,
            "a joined" if existing.joined else "an inert",
            existing.id_,
            self.case_id,
        )
        return Status.SUCCESS

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure

        if (done := self._existing_record_outcome(case)) is not None:
            return done

        roles = self._resolve_roles()
        if not roles:
            self.feedback_message = (
                f"{self.name}: no roles resolved for invitee '{self.invitee_id}'"
                f" — inviter must specify the invitee's roles (CM-11-019)"
            )
            self.logger.error(
                "%s: no roles resolved for invitee '%s' in case '%s'"
                " — refusing inert-participant creation (CM-11-019)",
                self.name,
                self.invitee_id,
                self.case_id,
            )
            return Status.FAILURE
        status = self._build_initial_status(roles, self.case_id)
        participant_id = (
            f"{self.case_id}/participants/{self.invitee_id.split('/')[-1]}"
        )
        participant = CaseParticipant(
            id_=participant_id,
            attributed_to=self.invitee_id,
            context=self.case_id,
            case_roles=roles,
            participant_statuses=[status],
            joined=False,
        )

        # The record gets an UNINVITED row for every register entry (ADR-0122)
        # before it is first stored, then INVITE on the embargo in force
        # (CM-11-006).
        participant.write_uninvited_rows(case.register_embargo_ids)
        active_embargo_id = case.active_embargo_id
        if active_embargo_id and participant.apply_pec_transition_if_legal(
            active_embargo_id,
            PEC_Trigger.INVITE,
            entry_status=case.embargo_register_status(active_embargo_id),
        ):
            self.logger.info(
                "%s: set PEC INVITED for invitee '%s' (active embargo '%s',"
                " CM-11-006)",
                self.name,
                self.invitee_id,
                active_embargo_id,
            )

        updated_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id=self.case_id,
            actor_id_for_index=self.invitee_id,
            logger=self.logger,
        )
        if updated_case is None:
            self.feedback_message = (
                f"{self.name}: case '{self.case_id}' vanished"
            )
            return Status.FAILURE
        self.datalayer.save(updated_case)

        # Creating the record is the CASE_MANAGER's own act, with no wire
        # message of its own, so it has its own entry (ADR-0114): the record as
        # stored, ids and times as minted here.
        stored = self.datalayer.read(participant_id)
        if not isinstance(stored, CaseParticipant):
            self.feedback_message = (
                f"{self.name}: record '{participant_id}' not stored"
            )
            return Status.FAILURE
        try:
            commit_case_participant_created(
                datalayer=cast(CaseOutboxPersistence, self.datalayer),
                actor_id=cast(str, self.actor_id),
                case_id=self.case_id,
                participant=stored,
                wire_render_port=self._require_wire_render_port(),
            )
        except RuntimeError as exc:
            self.feedback_message = f"{self.name}: {exc}"
            self.logger.exception("%s", self.feedback_message)
            return Status.FAILURE

        self.logger.info(
            "%s: seated inert participant '%s' for invitee '%s' in case '%s'"
            " (RM.RECEIVED, joined=False, CM-11-006)",
            self.name,
            participant_id,
            self.invitee_id,
            self.case_id,
        )
        return Status.SUCCESS


class AdvanceInviteeVFToVendorAwareNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Record VF ``Vf`` (vendor aware) on a VENDOR invitee after a stub reply.

    CM-11-009: any reply to the stub Invite — Accept or Reject — is evidence
    the vendor knows of the case, so VF advances to ``Vf``.  For non-VENDOR
    roles the node is a no-op (SUCCESS).

    Uses :class:`~vultron.core.behaviors.case.nodes.participant.status.CreateParticipantStatusNode`
    via an inner BTBridge to append the new status through the sole writer
    (BTND-10-001).
    """

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "invitee_vf_status_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"invitee_vf_status_id": "/invitee_vf_status_id"}

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id
        self._vf_node = CreateParticipantStatusNode(
            actor_id=invitee_id,
            rm_state=None,
            vf_state=CS_vf.Vf,
            d_state=None,
            pxa_state=None,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        # Always written, so a value left by an earlier execution is not read
        # as this Accept's (the blackboard is process-global).
        self._set_output("invitee_vf_status_id", "")

        participant_id = (
            f"{self.case_id}/participants/{self.invitee_id.split('/')[-1]}"
        )
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.logger.warning(
                "%s: invitee participant '%s' not found — skipping VF advance",
                self.name,
                participant_id,
            )
            return Status.SUCCESS

        if CVDRole.VENDOR not in participant.case_roles:
            self.logger.debug(
                "%s: invitee '%s' is not a VENDOR — VF advance is a no-op",
                self.name,
                self.invitee_id,
            )
            return Status.SUCCESS

        # A vendor already aware (a resumed Accept) is left as it is: a second
        # Vf status would be a second state change to ledger.
        latest = (
            participant.participant_statuses[-1]
            if participant.participant_statuses
            else None
        )
        if (
            latest is not None
            and latest.vf is not None
            and latest.vf.state is not CS_vf.vf
        ):
            self.logger.debug(
                "%s: invitee '%s' is already vendor-aware — VF advance is a"
                " no-op",
                self.name,
                self.invitee_id,
            )
            return Status.SUCCESS

        # Run as the receiving actor (case manager), not the invitee —
        # _store_for_actor resolves the DL from the actor_id and the invitee
        # has no store here (the CASE_MANAGER's own store).
        result = BTBridge(datalayer=self.datalayer).execute_with_setup(
            self._vf_node,
            actor_id=self.actor_id,
            case_id=self.case_id,
        )
        if result.status != Status.SUCCESS:
            self.logger.error(
                "%s: failed to advance VF to Vf for invitee '%s'",
                self.name,
                self.invitee_id,
            )
            return result.status
        # The new status is a state change; CommitInviteeAcceptEntriesNode
        # ledgers it after the announce and the backfill (ADR-0114, #2898).
        stored = self.datalayer.read(participant_id)
        if isinstance(stored, CaseParticipant) and stored.participant_statuses:
            self._set_output(
                "invitee_vf_status_id", stored.participant_statuses[-1].id_
            )
        self.logger.info(
            "%s: advanced VF to Vf for VENDOR invitee '%s' (CM-11-009)",
            self.name,
            self.invitee_id,
        )
        return Status.SUCCESS


__all__ = [
    "AdvanceInviteeVFToVendorAwareNode",
    "CreateInertInviteeParticipantNode",
]
