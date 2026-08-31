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

"""BT nodes and factory for AcceptInviteActorToCase received use-case.

When the CaseActor receives ``Accept(Invite(actor, case))``, it runs this tree
as itself (the CaseActor) to record the invitee's participation in its own
DataLayer — without spoofing the invitee's identity (PCR-08-010).

Tree structure::

    AcceptInviteActorToCaseBT (Sequence, memory=False)
    ├── CheckInviteeNotAlreadyParticipantNode  — idempotency guard
    ├── CapturePreCommitBackfillTargetNode     — snapshot ledger for resume case
    ├── GuardedCommitCaseLedgerEntryBT         — record receipt (CLP-10-006)
    ├── CreateInviteeParticipantAtReceivedNode — build participant at RM.RECEIVED
    ├── MaybeSignEmbargoConsentNode            — sign when embargo is EM.ACTIVE
    ├── PersistInviteeParticipantNode          — dl.create, attach, save case
    ├── EmitAddCaseParticipantNode             — emit Add(CaseParticipant), commit ledger
    ├── EmitAnnounceCaseToInviteeNode          — queue Announce(VulnerabilityCase)
    └── BackfillCanonicalLedgerToInviteeNode   — send prior ledger to invitee

Specs: PCR-08-010 (identity constraint), CM-10-001/CM-10-003 (embargo
consent), MV-10-003/MV-10-005 (announce after consent resolved).
BT-06-001, BT-15-001.
"""

import logging
from typing import cast

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.case.nodes import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.nodes.accept_invite import (
    EmitAddCaseParticipantNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import validate_roles
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)


class CapturePreCommitBackfillTargetNode(DataLayerActionWithPorts):
    """Snapshot the current last ledger-entry index for resume-case backfill.

    This node MUST appear AFTER ``CheckInviteeNotAlreadyParticipantNode`` in
    the precondition-guards list, so it can read ``invitee_already_participant``
    from the blackboard.

    **Resume case** (invitee already registered, ``invitee_already_participant
    = True``): the commit's ``FanOutLogEntryNode`` will include the invitee in
    its recipient list (they are a current case participant), so
    ``BackfillCanonicalLedgerToInviteeNode`` must limit its window to entries
    that existed *before* the commit to avoid sending the new entry twice.
    This node writes ``pre_commit_backfill_target`` to the blackboard.

    **Fresh case** (invitee not yet registered, ``invitee_already_participant
    = False``): the commit fan-out will NOT include the invitee (they are not
    yet a participant), so backfill must include the newly committed entry in
    its window.  This node does *not* write ``pre_commit_backfill_target``,
    leaving ``BackfillCanonicalLedgerToInviteeNode`` to compute its target
    from the post-commit ledger state.

    Always returns ``SUCCESS``.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["invitee_already_participant"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "pre_commit_backfill_target": PortInformation(
                data_type=object, required=False
            )
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_already_participant": "/invitee_already_participant",
            "pre_commit_backfill_target": "/pre_commit_backfill_target",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._already_participant_bb = self.get_input(
                "invitee_already_participant"
            )
        except (NoDataAvailable, NotImplementedError):
            self._already_participant_bb = False

    def update(self) -> Status:
        already_participant = self._already_participant_bb

        if not already_participant:
            # Fresh case: commit fan-out won't reach invitee (not yet
            # registered).  Write None to pre_commit_backfill_target so that
            # BackfillCanonicalLedgerToInviteeNode uses the post-commit target,
            # and any stale value from a prior resume test is overwritten.
            self._set_output("pre_commit_backfill_target", None)
            self.logger.debug(
                "%s: fresh invite — clearing pre-commit backfill target"
                " (backfill will include post-commit entry)",
                self.name,
            )
            return Status.SUCCESS

        # Resume case: invitee IS already a participant.
        # Capture the current last index so backfill doesn't re-send the
        # accept-invite entry that the commit fan-out will deliver.
        if self.datalayer is None:
            self._set_output("pre_commit_backfill_target", -1)
            return Status.SUCCESS

        entries: list[CaseLedgerEntry] = [
            obj
            for obj in self.datalayer.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry) and obj.case_id == self.case_id
        ]
        target = entries[-1].log_index if entries else -1
        self._set_output("pre_commit_backfill_target", target)
        self.logger.debug(
            "%s: resume case — pre-commit backfill target for case '%s' is %d",
            self.name,
            self.case_id,
            target,
        )
        return Status.SUCCESS


class CheckInviteeNotAlreadyParticipantNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """Idempotency guard: FAILURE when invitee is already a fully-joined participant.

    Returns SUCCESS (allow proceeding) when the invitee is NOT yet
    registered in ``case.actor_participant_index``, or when the invitee IS
    registered but join-time backfill is still incomplete (resume path).

    Returns FAILURE (abort tree) with no ledger write when the invitee is
    already a participant AND backfill is complete — a true idempotent no-op
    (CLP-13-001, CLP-13-002).

    Three paths:

    1. **Fresh invite**: invitee not yet a participant → SUCCESS, tree runs in full.
    2. **Backfill-incomplete resume**: invitee is a participant but backfill is
       still in progress → SUCCESS with ``invitee_already_participant = True``,
       so downstream effect nodes skip participant-creation while the commit and
       backfill steps still run.
    3. **Backfill-complete (true duplicate)**: invitee is a participant and
       backfill is done → ``_idempotent_failure`` (FAILURE, INFO log, no ledger
       write — CLP-13-001).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "invitee_case": PortInformation(data_type=object, required=True),
            "invitee_already_participant": PortInformation(
                data_type=object, required=True
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_case": "/invitee_case",
            "invitee_already_participant": "/invitee_already_participant",
        }

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.warning(
                "%s: case '%s' not found",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        existing_ids = [_as_id(p) for p in case.case_participants]
        already_participant = (
            self.invitee_id in case.actor_participant_index
            or self.invitee_id in existing_ids
        )
        if already_participant:
            state = self._read_replication_state(case.id_)
            if state is not None and (
                state.join_backfill_complete
                or state.join_backfill_target_index == -1
            ):
                # True duplicate: backfill complete — silent FAILURE, no ledger
                # write (CLP-13-001).
                self._set_output("invitee_already_participant", True)
                return self._idempotent_failure(
                    self.logger,
                    "%s: actor '%s' already participant in case '%s'"
                    " — skipping (idempotent, CLP-13-001)",
                    self.name,
                    self.invitee_id,
                    self.case_id,
                )

            # Resume path: backfill is incomplete (or no marker yet).  Set the
            # flag so downstream effect nodes skip participant-creation, but
            # return SUCCESS to allow the commit + backfill steps to run.
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
            self._set_output("invitee_case", case)
            return Status.SUCCESS

        # Cache the case object for downstream nodes
        self._set_output("invitee_already_participant", False)
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


class CreateInviteeParticipantAtReceivedNode(DataLayerActionWithPorts):
    """Build a ``VultronParticipant`` for the invitee at RM.RECEIVED.

    Per CM-11-001, ``Accept(Invite)`` signals willingness to join; the
    CaseActor records RM.RECEIVED only.  The full triage cycle
    (VALID/ACCEPTED) is a distinct subsequent step run by the invitee
    after the case replica has been delivered (PCR-08-010).

    Writes ``new_invite_participant`` to the blackboard.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["invitee_already_participant"] = PortInformation(
            data_type=object, required=True
        )
        ports["invitee_case"] = PortInformation(
            data_type=object, required=True
        )
        ports["activity"] = PortInformation(data_type=object, required=False)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "new_invite_participant": PortInformation(
                data_type=object, required=True
            )
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_already_participant": "/invitee_already_participant",
            "invitee_case": "/invitee_case",
            "activity": "/activity",
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
        try:
            self._activity_bb = self.get_input("activity")
        except (NoDataAvailable, NotImplementedError):
            self._activity_bb = None

    def _read_invite_roles(self) -> list:
        """Read roles from the Invite embedded in the Accept activity (CM-17-003).

        Resolves roles from ``event.activity.object_`` — the raw wire Invite
        carried inside the received ``Accept`` activity, as hydrated by the
        wire extractor (``include_activity=True`` in the semantic registry).
        This path is race-free: the roles arrive in the protocol message
        itself, so no DataLayer lookup is needed or performed.

        Returns an empty list when no roles are present.
        """
        event = self._activity_bb
        if event is None:
            return []
        activity = getattr(event, "activity", None)
        if activity is None:
            return []
        invite_obj = getattr(activity, "object_", None)
        if invite_obj is None:
            self.logger.warning(
                "%s: Accept activity has no embedded Invite (object_ is None)"
                " — protocol violation",
                self.name,
            )
            return []
        raw_roles = getattr(invite_obj, "roles", None)
        if raw_roles is None:
            self.logger.warning(
                "%s: embedded Invite has no roles field — protocol violation",
                self.name,
            )
            return []
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
        if not isinstance(case, VulnerabilityCase):
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
                "new_invite_participant", cast(VultronParticipant, existing)
            )
            self.logger.info(
                "%s: reusing existing participant '%s' for backfill resume",
                self.name,
                participant_id,
            )
            return Status.SUCCESS

        roles = self._read_invite_roles()
        participant = VultronParticipant(
            id_=f"{self.case_id}/participants/{self.invitee_id.split('/')[-1]}",
            attributed_to=self.invitee_id,
            context=self.case_id,
            case_roles=roles,
        )
        # CM-11-001: Accept(Invite) records RM.RECEIVED only. The full
        # triage cycle is a distinct step run by the invitee after replica
        # delivery (PCR-08-010).
        participant.append_rm_state(
            RM.RECEIVED, actor=self.invitee_id, context=self.case_id
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
            "%s: created participant object for invitee '%s' at RM.RECEIVED"
            " (CM-11-001)",
            self.name,
            self.invitee_id,
        )
        return Status.SUCCESS


class MaybeSignEmbargoConsentNode(py_trees.composites.Selector):
    """Auto-sign embargo consent when the case embargo is fully EM.ACTIVE.

    Selector logic:
    - ``_TrySignEmbargoConsent`` (Sequence): sign if embargo is EM.ACTIVE.
    - ``_AlwaysSucceed`` (leaf): fall-through so the parent Sequence can
      continue when there is no active embargo or it is in REVISE state.

    Only auto-signs when ``em_state == EM.ACTIVE`` — REVISE means terms
    are being renegotiated and the new participant should not be committed.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                _TrySignEmbargoConsentSequence(
                    case_id=case_id, invitee_id=invitee_id
                ),
                _AlwaysSucceedNode(),
            ],
        )


class _CheckEmbargoActiveStateNode(DataLayerActionWithPorts):
    """Return SUCCESS iff the case has an active embargo in EM.ACTIVE state."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["invitee_case"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "active_embargo_id": PortInformation(
                data_type=object, required=False
            )
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_case": "/invitee_case",
            "active_embargo_id": "/active_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._invitee_case_bb = self.get_input("invitee_case")
        except (NoDataAvailable, NotImplementedError):
            self._invitee_case_bb = None

    def update(self) -> Status:
        case = self._invitee_case_bb
        if not isinstance(case, VulnerabilityCase):
            self.logger.error("%s: invitee_case not available", self.name)
            # Initialize key so downstream nodes can safely read it.
            self._set_output("active_embargo_id", None)
            return Status.FAILURE

        active_embargo_id = _as_id(case.active_embargo)
        em_state = case.current_status.em.state
        if active_embargo_id and em_state == EM.ACTIVE:
            self._set_output("active_embargo_id", active_embargo_id)
            return Status.SUCCESS
        # Always write the key so PersistInviteeParticipantNode can read it
        # even when there is no active embargo (py_trees raises KeyError for
        # unwritten READ-registered keys — see AGENTS.md pitfalls).
        self._set_output("active_embargo_id", None)
        return Status.FAILURE


class _SignEmbargoConsentLeafNode(DataLayerActionWithPorts):
    """Sign embargo consent on the participant and record the event."""

    def __init__(self, invitee_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["new_invite_participant"] = PortInformation(
            data_type=object, required=True
        )
        ports["active_embargo_id"] = PortInformation(
            data_type=str, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "new_invite_participant": "/new_invite_participant",
            "active_embargo_id": "/active_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.new_invite_participant = self.get_input("new_invite_participant")
        self.active_embargo_id: str = self.get_input("active_embargo_id")

    def update(self) -> Status:
        participant = self.new_invite_participant
        active_embargo_id = self.active_embargo_id
        if not isinstance(participant, VultronParticipant) or not isinstance(
            active_embargo_id, str
        ):
            self.logger.error(
                "%s: participant or active_embargo_id missing", self.name
            )
            return Status.FAILURE

        participant.accepted_embargo_ids.append(active_embargo_id)
        participant.apply_pec_transition(PEC_Trigger.ACCEPT)
        self.logger.info(
            "%s: signed embargo consent for invitee '%s' (EM.ACTIVE,"
            " CM-10-001)",
            self.name,
            self.invitee_id,
        )
        return Status.SUCCESS


class _TrySignEmbargoConsentSequence(py_trees.composites.Sequence):
    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(
            name=name or "_TrySignEmbargoConsent",
            memory=False,
            children=[
                _CheckEmbargoActiveStateNode(case_id=case_id),
                _SignEmbargoConsentLeafNode(invitee_id=invitee_id),
            ],
        )


class _AlwaysSucceedNode(py_trees.behaviour.Behaviour):
    """Fallback leaf that always returns SUCCESS.

    Used in Selector subtrees as a no-op alternative to optional steps.
    """

    def __init__(self, name: str = "_AlwaysSucceed") -> None:
        super().__init__(name=name)

    def update(self) -> Status:
        return Status.SUCCESS


class PersistInviteeParticipantNode(DataLayerActionWithPorts):
    """Persist the participant, attach to case, record events, save case."""

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["invitee_already_participant"] = PortInformation(
            data_type=object, required=True
        )
        ports["new_invite_participant"] = PortInformation(
            data_type=object, required=True
        )
        ports["invitee_case"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_already_participant": "/invitee_already_participant",
            "new_invite_participant": "/new_invite_participant",
            "invitee_case": "/invitee_case",
        }

    def initialise(self) -> None:
        super().initialise()
        self.invitee_already_participant = self.get_input(
            "invitee_already_participant"
        )
        self.new_invite_participant = self.get_input("new_invite_participant")
        self.invitee_case = self.get_input("invitee_case")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self.invitee_already_participant:
            return Status.SUCCESS

        participant = self.new_invite_participant
        case = self.invitee_case
        if not isinstance(participant, VultronParticipant) or not isinstance(
            case, VulnerabilityCase
        ):
            self.logger.error(
                "%s: new_invite_participant or invitee_case missing",
                self.name,
            )
            return Status.FAILURE

        self.datalayer.create(participant)
        case.add_participant(participant)
        self.datalayer.save(case)
        self.logger.info(
            "%s: participant '%s' persisted and attached to case '%s'"
            " (RM.RECEIVED, CM-11-001)",
            self.name,
            participant.id_,
            self.case_id,
        )
        return Status.SUCCESS


class BackfillCanonicalLedgerToInviteeNode(DataLayerActionWithPorts):
    """Send canonical CaseLedgerEntry history to a joiner in strict order."""

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id
        self._sync_port: SyncActivityPort | None = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["sync_port"] = PortInformation(data_type=object, required=False)
        ports["pre_commit_backfill_target"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "sync_port": "/sync_port",
            "pre_commit_backfill_target": "/pre_commit_backfill_target",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None
        try:
            self._pre_commit_backfill_target = self.get_input(
                "pre_commit_backfill_target"
            )
        except (NoDataAvailable, NotImplementedError):
            self._pre_commit_backfill_target = None

    def _resolve_backfill_target(self, entries: list[CaseLedgerEntry]) -> int:
        """Resolve the backfill target index.

        Uses ``pre_commit_backfill_target`` captured in ``initialise()`` when
        set (resume case: CapturePreCommitBackfillTargetNode wrote the last
        index BEFORE the commit so backfill does not re-send the new entry
        that the commit fan-out already delivered).  ``None`` means fresh case
        — fall back to the post-commit last entry.
        """
        pre_commit_target = self._pre_commit_backfill_target
        if pre_commit_target is not None:
            return int(pre_commit_target)
        return entries[-1].log_index if entries else -1

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        if self._sync_port is None:
            self.logger.error(
                "%s: sync_port not injected; cannot perform join-time backfill",
                self.name,
            )
            return Status.FAILURE

        entries: list[CaseLedgerEntry] = [
            obj
            for obj in self.datalayer.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry) and obj.case_id == self.case_id
        ]
        entries.sort(key=lambda log_entry: log_entry.log_index)

        target_index = self._resolve_backfill_target(entries)
        state = self._load_or_create_state(target_index)

        if state.join_backfill_complete:
            self.logger.info(
                "%s: join-time backfill already complete for '%s' in case '%s'"
                " at log_index=%d",
                self.name,
                self.invitee_id,
                self.case_id,
                state.join_backfill_last_sent_index,
            )
            return Status.SUCCESS

        if state.join_backfill_last_sent_index >= target_index:
            state.join_backfill_complete = True
            self.datalayer.save(state)
            return Status.SUCCESS

        for entry in entries:
            if entry.log_index <= state.join_backfill_last_sent_index:
                continue
            if entry.log_index > target_index:
                break
            self._sync_port.send_announce_log_entry(
                entry=entry,
                actor_id=self.actor_id,
                to=[self.invitee_id],
            )
            state.join_backfill_last_sent_index = entry.log_index
            self.datalayer.save(state)

        state.join_backfill_complete = (
            state.join_backfill_last_sent_index
            >= state.join_backfill_target_index
        )
        self.datalayer.save(state)
        self.logger.info(
            "%s: join-time backfill complete for '%s' in case '%s'"
            " (target_log_index=%d)",
            self.name,
            self.invitee_id,
            self.case_id,
            state.join_backfill_target_index,
        )
        return Status.SUCCESS

    def _load_or_create_state(
        self, target_index: int
    ) -> VultronReplicationState:
        if self.datalayer is None:
            raise RuntimeError(
                "_load_or_create_state requires an injected DataLayer"
            )
        dl = self.datalayer
        state_id = VultronReplicationState(
            case_id=self.case_id, peer_id=self.invitee_id
        ).id_
        existing = dl.read(state_id)
        if isinstance(existing, VultronReplicationState):
            existing.join_backfill_target_index = max(
                existing.join_backfill_target_index,
                target_index,
            )
            if (
                existing.join_backfill_last_sent_index
                < existing.join_backfill_target_index
            ):
                existing.join_backfill_complete = False
            dl.save(existing)
            return existing
        state = VultronReplicationState(
            case_id=self.case_id,
            peer_id=self.invitee_id,
            join_backfill_target_index=target_index,
            join_backfill_last_sent_index=-1,
            join_backfill_complete=(target_index == -1),
        )
        dl.save(state)
        return state


class EmitAnnounceCaseToInviteeNode(DataLayerAction):
    """Queue Announce(VulnerabilityCase) to the invitee from the CaseActor.

    Per MV-10-003/MV-10-005, the CaseActor sends the full case object after
    embargo consent has been resolved (auto-signed above when EM.ACTIVE).
    Failures to enqueue Announce are logged but treated as non-fatal so the
    join-time canonical ledger backfill can still run and establish catch-up
    markers.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        factory = self.trigger_activity_factory
        if factory is None:
            self.logger.warning(
                "%s: trigger_activity_factory not available;"
                " cannot emit AnnounceVulnerabilityCase for case '%s'"
                " (MV-10-003)",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        try:
            activity_id = factory.announce_vulnerability_case(
                case_id=self.case_id,
                actor=self.actor_id,
                context_id=self.case_id,
                to=[self.invitee_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
            self.logger.info(
                "%s: queued AnnounceVulnerabilityCase '%s' to '%s'"
                " for case '%s' (MV-10-003)",
                self.name,
                activity_id,
                self.invitee_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as exc:
            self.logger.error(
                "%s: failed to emit AnnounceVulnerabilityCase for case '%s'"
                " to '%s': %s",
                self.name,
                self.case_id,
                self.invitee_id,
                exc,
            )
            return Status.SUCCESS


def create_accept_invite_actor_to_case_tree(
    case_id: str,
    invitee_id: str,
) -> py_trees.composites.Sequence:
    """Return the BT for handling an inbound ``Accept(Invite(actor, case))``.

    The CaseActor runs this tree **as itself** (not as the invitee) to record
    the invitee's participation in its own DataLayer (PCR-08-010).

    The returned Sequence::

        AcceptInviteActorToCaseBT (memory=False)
        ├── CheckInviteeNotAlreadyParticipantNode  — idempotency guard
        ├── CapturePreCommitBackfillTargetNode     — snapshot ledger for resume case
        ├── GuardedCommitCaseLedgerEntryBT         — record receipt (CLP-10-006)
        ├── CreateInviteeParticipantAtReceivedNode — build participant at RM.RECEIVED
        ├── MaybeSignEmbargoConsentNode            — sign when EM.ACTIVE
        ├── PersistInviteeParticipantNode          — persist, attach, save case
        ├── EmitAddCaseParticipantNode             — emit Add(CaseParticipant), commit ledger
        ├── EmitAnnounceCaseToInviteeNode          — queue Announce to invitee
        └── BackfillCanonicalLedgerToInviteeNode   — send prior ledger to invitee

    The idempotency guard ``CheckInviteeNotAlreadyParticipantNode`` uses
    :class:`~vultron.core.behaviors.idempotency.SilentIdempotencyGuardMixin`
    to enforce CLP-13-001: when a true duplicate is detected (invitee already
    joined AND backfill is complete), the guard returns ``Status.FAILURE`` with
    an INFO log and no ledger write.  When backfill is incomplete, it returns
    SUCCESS with ``invitee_already_participant = True`` so the tree continues
    to the commit + backfill steps without re-creating the participant.

    Args:
        case_id: ID of the VulnerabilityCase the invitee accepted.
        invitee_id: Actor ID of the actor who accepted the invitation.

    Returns:
        Configured ``Sequence`` ready for execution via
        :class:`~vultron.core.behaviors.bridge.BTBridge`.
    """
    return create_receive_activity_tree(
        name="AcceptInviteActorToCaseBT",
        case_id=case_id,
        precondition_guards=[
            CheckInviteeNotAlreadyParticipantNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            CapturePreCommitBackfillTargetNode(case_id=case_id),
        ],
        effect_nodes=[
            CreateInviteeParticipantAtReceivedNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            MaybeSignEmbargoConsentNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            PersistInviteeParticipantNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            EmitAddCaseParticipantNode(case_id=case_id, invitee_id=invitee_id),
            EmitAnnounceCaseToInviteeNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            BackfillCanonicalLedgerToInviteeNode(
                case_id=case_id, invitee_id=invitee_id
            ),
        ],
    )


__all__ = [
    "CapturePreCommitBackfillTargetNode",
    "CheckInviteeNotAlreadyParticipantNode",
    "CreateInviteeParticipantAtReceivedNode",
    "EmitAddCaseParticipantNode",
    "MaybeSignEmbargoConsentNode",
    "PersistInviteeParticipantNode",
    "EmitAnnounceCaseToInviteeNode",
    "BackfillCanonicalLedgerToInviteeNode",
    "create_accept_invite_actor_to_case_tree",
]
