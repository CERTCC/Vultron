#!/usr/bin/env python
#
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
"""BT leaf node for emitting Add(CaseParticipant) after a successful invite acceptance."""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.sync.commit_tree import (
    commit_emitted_activity,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.recipients import case_content_recipients
from vultron.core.ports.case_outbox import CaseOutboxPersistence

logger = logging.getLogger(__name__)


class EmitAddCaseParticipantNode(_EmitSingleActivityBase):
    """Emit Add(CaseParticipant, Case) and commit a canonical ledger entry.

    Called by the CaseActor after persisting the new invitee participant
    (``PersistInviteeParticipantNode``), announcing the case to it and
    backfilling the prior ledger (CM-17-004 steps 5 and 6).  Fans the
    ``Add(CaseParticipant, Case)`` activity out to all current case
    participants so they can update their local replica, and commits the
    corresponding canonical ``CaseLedgerEntry`` to the hash chain.

    The commit's own fan-out (``CollectLogEntryRecipientsNode``) selects the
    active participants and therefore *does* include the invitee.  That
    is why this node runs last in the effects: earlier, the invitee would
    receive this entry before its case seed (SYNC-15 pre-genesis) or before the
    backfilled entries it extends (SYNC-14 forward gap) — #2898.

    Uses ``trigger_activity_factory.add_participant_to_case()`` to build and
    persist the activity.  The activity's ``payloadSnapshot`` is the blob the
    port returned, unchanged: the factory sets ``context`` to the case URI, so
    ``_validate_canonical_entry`` can verify the ``("Add", "CaseParticipant")``
    signature without core patching anything (CLP-07-005, VM-08-003).

    Recipients are the case's active participants, chosen by the shared
    selection (CM-10-004, CM-10-007), excluding the newly added invitee.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name)
        self.case_id = case_id
        self.invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **_EmitSingleActivityBase.INPUT_PORTS,
        "new_invite_participant": PortInformation(
            data_type=object, required=False
        ),
        "invitee_already_participant": PortInformation(
            data_type=bool, required=False
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "new_invite_participant": "/new_invite_participant",
            "invitee_already_participant": "/invitee_already_participant",
        }

    def initialise(self) -> None:
        super().initialise()
        self._new_invite_participant_bb = None
        self._invitee_already_participant_bb = None
        try:
            self._new_invite_participant_bb = self.get_input(
                "new_invite_participant"
            )
        except (NoDataAvailable, NotImplementedError):
            pass
        try:
            self._invitee_already_participant_bb = self.get_input(
                "invitee_already_participant"
            )
        except (NoDataAvailable, NotImplementedError):
            pass

    def _is_already_done(self) -> bool:
        """Return True if invitee was already a participant (idempotency skip)."""
        return bool(self._invitee_already_participant_bb)

    def _resolve_actor_recipients(self, case: VulnerabilityCase) -> list[str]:
        """Return the active participants to announce the new invitee to.

        Case content, so the shared selection picks them (CM-10-004,
        CM-10-007), less the invitee: it learns of its own record from the
        commit's fan-out, after its case seed and backfill.  The case is
        resolved (and its absence hard-failed) by ``update()`` via
        ``_require_case`` — Regime 1, ADR-0087.
        """
        assert self.datalayer is not None
        return case_content_recipients(
            case, self.datalayer, excluding={self.invitee_id}
        )

    def _call_factory(self) -> tuple[str, str]:
        """Build Add(CaseParticipant) activity and commit the canonical ledger entry."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None

        participant = self._new_invite_participant_bb
        participant_id = _as_id(participant)
        if not participant_id:
            raise ValueError(
                f"{self.name}: could not resolve participant_id from {participant!r}"
            )
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            raise RuntimeError(f"{self.name}: case '{self.case_id}' not found")
        others = self._resolve_actor_recipients(case)
        activity_id, activity_blob = (
            self.trigger_activity_factory.add_participant_to_case(
                participant_id=participant_id,
                case_id=self.case_id,
                actor=self.actor_id,
                to=others or None,
            )
        )
        # The recorded snapshot is the exact blob the port returned; the
        # factory owns its completeness and the outbox delivers the same text
        # (VM-08-003).
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=self.actor_id,
            case_id=self.case_id,
            activity_id=activity_id,
            activity_blob=activity_blob,
            event_type="add_case_participant",
        )
        return activity_id, activity_blob

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        participant_id = _as_id(self._new_invite_participant_bb)
        self.logger.info(
            "%s: emitted Add(CaseParticipant '%s') for case '%s'"
            " and committed canonical ledger entry",
            self.name,
            participant_id,
            self.case_id,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if self._is_already_done():
            return Status.SUCCESS

        # SHOULD-level (ADR-0087): no factory is not an error for this node.
        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: trigger_activity_factory not available;"
                " cannot emit Add(CaseParticipant) for case '%s'",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        participant = self._new_invite_participant_bb
        if not isinstance(participant, CaseParticipant):
            self.logger.error(
                "%s: new_invite_participant not available", self.name
            )
            return Status.FAILURE

        participant_id = _as_id(participant)
        if not participant_id:
            self.logger.error(
                "%s: could not resolve participant_id from %r",
                self.name,
                participant,
            )
            return Status.FAILURE

        try:
            activity_id, activity_blob = self._call_factory()
            self._emit_through_seam(activity_id, activity_blob)
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            # Includes Regime 1 (ADR-0087, #3101) case-not-found:
            # a missing case is an anomaly, not a silent empty-recipient
            # emit+commit.
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: add_case_participant emit failed: %s", self.name, exc
            )
            return Status.FAILURE
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS


__all__ = ["EmitAddCaseParticipantNode"]
