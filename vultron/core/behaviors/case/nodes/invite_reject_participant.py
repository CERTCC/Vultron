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

"""Reject-effect node for the stub Invite (CM-11-007, CM-11-009, ADR-0114).

Split from :mod:`~vultron.core.behaviors.case.nodes.invite_inert_participant`
to keep each leaf module under the BTND-07-004 line limit.  The Reject closes
the invitee's inert record; each state change it makes -- the closing status
(RM ``CLOSED``, a vendor's VF ``Vf``) and the ``DECLINED`` consent row -- emits
its own ledger entry, so a replica stores what the entries carry.
"""

import logging
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.case.participant_ledger import (
    commit_case_participant_updated,
    commit_participant_status_added,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models._helpers import now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.states.cs import CS_vf
from vultron.core.states.participant_embargo_consent import PEC_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def _commit_latest_status(
    node: DataLayerActionWithPorts,
    participant: CaseParticipant,
    *,
    case_id: str,
    actor_id: str | None,
) -> Status | None:
    """Commit the participant's newest status as its own entry; None on success.

    Every state change the CASE_MANAGER makes emits an entry (ADR-0114), so the
    status the writer just appended is ledgered from the very object it stored.
    """
    assert node.datalayer is not None and actor_id is not None
    try:
        commit_participant_status_added(
            datalayer=cast(CaseOutboxPersistence, node.datalayer),
            actor_id=actor_id,
            case_id=case_id,
            participant=participant,
            status=participant.participant_statuses[-1],
            wire_render_port=node._require_wire_render_port(),
        )
    except RuntimeError as exc:
        node.feedback_message = f"{node.name}: {exc}"
        node.logger.exception("%s", node.feedback_message)
        return Status.FAILURE
    return None


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
        # has no store here (the CASE_MANAGER's own store).
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

        # The closing status (RM CLOSED, a vendor's Vf) is a state change, so
        # it emits its own entry.
        if (
            failure := _commit_latest_status(
                self,
                participant,
                case_id=self.case_id,
                actor_id=self.actor_id,
            )
        ) is not None:
            return failure

        # Apply PEC DECLINE when an embargo is in force
        case = self.datalayer.read_case(self.case_id)
        active_embargo_id = (
            case.active_embargo_id if case is not None else None
        )
        if (
            case is not None
            and active_embargo_id
            and participant.apply_pec_transition_if_legal(
                active_embargo_id,
                PEC_Trigger.DECLINE,
                entry_status=case.embargo_register_status(active_embargo_id),
            )
        ):
            participant.updated = now_utc()
            self.datalayer.save(participant)
            self.logger.info(
                "%s: applied PEC DECLINED for invitee '%s' (active embargo,"
                " CM-11-007)",
                self.name,
                self.invitee_id,
            )
            # The consent change is a state change, so it emits its own entry.
            try:
                commit_case_participant_updated(
                    datalayer=cast(CaseOutboxPersistence, self.datalayer),
                    actor_id=self.actor_id,
                    case_id=self.case_id,
                    participant=participant,
                    wire_render_port=self._require_wire_render_port(),
                )
            except RuntimeError as exc:
                self.feedback_message = f"{self.name}: {exc}"
                self.logger.exception("%s", self.feedback_message)
                return Status.FAILURE

        self.logger.info(
            "%s: reject-invite effects applied for invitee '%s' in case '%s'"
            " (RM.CLOSED, CM-11-007)",
            self.name,
            self.invitee_id,
            self.case_id,
        )
        return Status.SUCCESS


__all__ = ["ApplyInviteRejectToParticipantNode"]
