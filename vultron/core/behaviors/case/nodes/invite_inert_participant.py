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
  Writes ``new_invite_participant`` and ``invitee_already_participant=False``
  to the blackboard so :class:`~vultron.core.behaviors.case.nodes.accept_invite.EmitAddCaseParticipantNode`
  can fan the creation out to existing participants.

- :class:`AdvanceInviteeVFToVendorAwareNode` — after ``Accept`` or ``Reject``
  of the stub Invite, records vendor awareness (VF ``Vf``) on a VENDOR
  invitee's participant record (CM-11-009).  A no-op for non-VENDOR roles.

- :class:`ApplyInviteRejectToParticipantNode` — on ``Reject``, moves the
  inert participant to RM ``CLOSED``, sets VF ``Vf`` (VENDOR), and applies
  PEC ``DECLINED`` when an active embargo is in force (CM-11-007, CM-11-009).
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant.roles import (
    suggested_roles_key,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.participant_status import ParticipantStatus
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
    for VENDOR invitees, and PEC ``INVITED`` when the case carries an active
    embargo; PEC ``UNBOUND`` otherwise.  These are the exact values the
    CASE_MANAGER's acceptance of the future stub-Invite reply will start from
    (CM-11-009, CM-11-007).

    Writes:
    - ``new_invite_participant`` — the newly created :class:`CaseParticipant`
      object, for :class:`~vultron.core.behaviors.case.nodes.accept_invite.EmitAddCaseParticipantNode`.
    - ``invitee_already_participant = False`` — clears any stale blackboard
      value so the same node's ``_is_already_done()`` runs the emit.

    PRM-06-001: only a single status is written (the birth status at
    RM ``RECEIVED``).
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

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "new_invite_participant": PortInformation(
            data_type=object, required=True
        ),
        "invitee_already_participant": PortInformation(
            data_type=object, required=True
        ),
    }

    def _instance_port_remappings(self) -> dict[str, str]:
        if self._roles_key is None:
            return {}
        return {"suggested_roles": self._roles_key}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "new_invite_participant": "/new_invite_participant",
            "invitee_already_participant": "/invitee_already_participant",
        }

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

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure

        # Idempotency: if participant already exists and is joined, skip
        existing_id = case.actor_participant_index.get(self.invitee_id)
        if existing_id is not None:
            existing = self.datalayer.read(existing_id)
            if isinstance(existing, CaseParticipant) and existing.joined:
                self.logger.info(
                    "%s: invitee '%s' already joined case '%s' — skip inert creation",
                    self.name,
                    self.invitee_id,
                    self.case_id,
                )
                self._set_output("new_invite_participant", existing)
                self._set_output("invitee_already_participant", True)
                return Status.SUCCESS

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

        # Apply PEC INVITE if the case has an active embargo (CM-11-006)
        active_embargo_id = _as_id(case.active_embargo)
        if active_embargo_id and participant.accepts_pec_trigger(
            active_embargo_id, PEC_Trigger.INVITE
        ):
            participant.apply_pec_transition(
                active_embargo_id, PEC_Trigger.INVITE
            )
            self.logger.info(
                "%s: set PEC INVITED for invitee '%s' (active embargo '%s',"
                " CM-11-006)",
                self.name,
                self.invitee_id,
                active_embargo_id,
            )

        self.datalayer.create(participant)
        case.add_participant(participant)
        self.datalayer.save(case)

        self._set_output("new_invite_participant", participant)
        self._set_output("invitee_already_participant", False)
        self.logger.info(
            "%s: created inert participant '%s' for invitee '%s' in case '%s'"
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

        # Run as the receiving actor (case manager), not the invitee —
        # _store_for_actor resolves the DL from the actor_id and the invitee
        # has no store here (same pattern as AdvanceInviteeToReceivedNode).
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
        else:
            self.logger.info(
                "%s: advanced VF to Vf for VENDOR invitee '%s' (CM-11-009)",
                self.name,
                self.invitee_id,
            )
        return result.status


class ApplyInviteRejectToParticipantNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Close the invitee's inert record and mark vendor-aware on Reject.

    CM-11-007: ``Reject(Invite(stub))`` moves the inert participant record
    from RM ``RECEIVED`` to RM ``CLOSED`` and leaves it in place as history.
    CM-11-009: also advances VF to ``Vf`` for VENDOR invitees.
    PEC: applies ``DECLINED`` when the case has an active embargo.

    Uses :class:`~vultron.core.behaviors.case.nodes.participant.status.CreateParticipantStatusNode`
    via an inner BTBridge for the RM transition.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    def _make_close_node(
        self, is_vendor: bool
    ) -> "CreateParticipantStatusNode":
        """Return a close node that sets VF only for VENDOR invitees (CM-11-009)."""
        return CreateParticipantStatusNode(
            actor_id=self.invitee_id,
            rm_state=RM.CLOSED,
            vf_state=CS_vf.Vf if is_vendor else None,
            d_state=None,
            pxa_state=None,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        # Verify that the participant exists before attempting transitions
        participant_id = (
            f"{self.case_id}/participants/{self.invitee_id.split('/')[-1]}"
        )
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.feedback_message = (
                f"no invited participant record for '{self.invitee_id}'"
                f" in case '{self.case_id}'"
                f" — Reject refused (CM-11-018)"
            )
            self.logger.warning(
                "%s: no invited participant record for invitee '%s'"
                " in case '%s' — refusing Reject(Invite) (CM-11-018)",
                self.name,
                self.invitee_id,
                self.case_id,
            )
            return Status.FAILURE

        # CM-11-009: advance VF to Vf only for VENDOR invitees.  For other
        # roles the VF dimension is absent and the transition would violate
        # the VF role gate, so pass vf_state=None for non-VENDOR participants.
        is_vendor = CVDRole.VENDOR in participant.roles
        close_node = self._make_close_node(is_vendor)

        # RM RECEIVED → CLOSED (+ VF Vf for VENDOR) via the status writer.
        # Run as the receiving actor (case manager), not the invitee —
        # _store_for_actor resolves the DL from actor_id, and the invitee
        # has no store here (same pattern as AdvanceInviteeToReceivedNode).
        result = BTBridge(datalayer=self.datalayer).execute_with_setup(
            close_node,
            actor_id=self.actor_id,
            case_id=self.case_id,
        )
        if result.status != Status.SUCCESS:
            self.logger.error(
                "%s: failed to close participant '%s' (CM-11-007)",
                self.name,
                participant_id,
            )
            return result.status

        # Re-read the participant to apply PEC DECLINED (the status write
        # may have saved a new version)
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.logger.error(
                "%s: participant '%s' vanished after RM close write",
                self.name,
                participant_id,
            )
            return Status.FAILURE

        # Apply PEC DECLINE when an embargo is in force
        case = self.datalayer.read_case(self.case_id)
        active_embargo_id = (
            case.active_embargo_id if case is not None else None
        )
        if active_embargo_id and participant.accepts_pec_trigger(
            active_embargo_id, PEC_Trigger.DECLINE
        ):
            participant.apply_pec_transition(
                active_embargo_id, PEC_Trigger.DECLINE
            )
            self.datalayer.save(participant)
            self.logger.info(
                "%s: applied PEC DECLINED for invitee '%s' (active embargo,"
                " CM-11-007)",
                self.name,
                self.invitee_id,
            )

        self.logger.info(
            "%s: reject-invite effects applied for invitee '%s' in case '%s'"
            " (RM.CLOSED, CM-11-007)",
            self.name,
            self.invitee_id,
            self.case_id,
        )
        return Status.SUCCESS


__all__ = [
    "AdvanceInviteeVFToVendorAwareNode",
    "ApplyInviteRejectToParticipantNode",
    "CreateInertInviteeParticipantNode",
]
