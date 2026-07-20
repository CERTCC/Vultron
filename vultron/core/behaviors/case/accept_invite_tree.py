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
    ├── CreateInviteeParticipantAtAcceptedNode — build participant at RM.ACCEPTED
    ├── MaybeSignEmbargoConsentNode            — sign when embargo is EM.ACTIVE
    ├── PersistInviteeParticipantNode          — dl.create, attach, save case
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

from vultron.core.behaviors.case.nodes import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import validate_roles
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)


class CapturePreCommitBackfillTargetNode(DataLayerAction):
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

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="invitee_already_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="pre_commit_backfill_target",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        try:
            already_participant = self.blackboard.get(
                "invitee_already_participant"
            )
        except KeyError:
            already_participant = False

        if not already_participant:
            # Fresh case: commit fan-out won't reach invitee (not yet
            # registered).  Write None to pre_commit_backfill_target so that
            # BackfillCanonicalLedgerToInviteeNode uses the post-commit target,
            # and any stale value from a prior resume test is overwritten.
            self.blackboard.pre_commit_backfill_target = None
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
            self.blackboard.pre_commit_backfill_target = -1
            return Status.SUCCESS

        entries: list[CaseLedgerEntry] = [
            obj
            for obj in self.datalayer.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry) and obj.case_id == self.case_id
        ]
        target = entries[-1].log_index if entries else -1
        self.blackboard.pre_commit_backfill_target = target
        self.logger.debug(
            "%s: resume case — pre-commit backfill target for case '%s' is %d",
            self.name,
            self.case_id,
            target,
        )
        return Status.SUCCESS


class CheckInviteeNotAlreadyParticipantNode(DataLayerCondition):
    """Idempotency guard: FAILURE when invitee is already a participant.

    Returns SUCCESS (allow proceeding) when the invitee is NOT yet
    registered in ``case.actor_participant_index``.
    Returns FAILURE (abort tree) when the invitee is already a participant.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="invitee_case",
            access=py_trees.common.Access.WRITE,
        )
        self.blackboard.register_key(
            key="invitee_already_participant",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

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
                self.logger.info(
                    "%s: actor '%s' already participant in case '%s'"
                    " — skipping (idempotent)",
                    self.name,
                    self.invitee_id,
                    self.case_id,
                )
                self.blackboard.invitee_already_participant = True
                return Status.FAILURE

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
            self.blackboard.invitee_already_participant = True
            self.blackboard.invitee_case = case
            return Status.SUCCESS

        # Cache the case object for downstream nodes
        self.blackboard.invitee_already_participant = False
        self.blackboard.invitee_case = case
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


class CreateInviteeParticipantAtAcceptedNode(DataLayerAction):
    """Build a ``VultronParticipant`` for the invitee at RM.ACCEPTED.

    Per PCR-08-010, ``Accept(Invite)`` IS the engage signal.  The
    participant's full RECEIVED→VALID→ACCEPTED arc is implicit; the
    CaseActor records RM.ACCEPTED directly in its own DataLayer rather
    than running an engage-case BT as the invitee.

    Writes ``new_invite_participant`` to the blackboard.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="invitee_already_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="invitee_case",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="new_invite_participant",
            access=py_trees.common.Access.WRITE,
        )
        self.blackboard.register_key(
            key="activity",
            access=py_trees.common.Access.READ,
        )

    def _read_invite_roles(self) -> list:
        """Read roles from the Invite stored in DataLayer (CM-17-003).

        Resolves invite_id via the ``activity`` blackboard key, reads the
        stored Invite, and coerces any ``roles`` strings to ``CVDRole``.
        Returns an empty list when the invite carries no roles or cannot
        be read.
        """
        try:
            event = self.blackboard.get("activity")
        except (AttributeError, KeyError):
            return []
        invite_id = getattr(event, "object_id", None)
        if not invite_id or self.datalayer is None:
            return []
        invite = self.datalayer.read(invite_id)
        raw_roles = getattr(invite, "roles", None)
        if not raw_roles:
            return []
        try:
            return validate_roles(raw_roles)
        except (ValueError, KeyError):
            self.logger.warning(
                "%s: could not coerce invite roles %r — ignoring",
                self.name,
                raw_roles,
            )
            return []

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        case = self.blackboard.get("invitee_case")
        if not isinstance(case, VulnerabilityCase):
            self.logger.error(
                "%s: invitee_case not found in blackboard", self.name
            )
            return Status.FAILURE

        if self.blackboard.get("invitee_already_participant"):
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
            self.blackboard.new_invite_participant = cast(
                VultronParticipant, existing
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
            case_roles=roles if roles else [],
        )
        # PCR-08-010: Accept(Invite) IS the engage signal; record all three
        # RM transitions on behalf of the invitee in the CaseActor's DataLayer.
        participant.append_rm_state(
            RM.RECEIVED, actor=self.invitee_id, context=self.case_id
        )
        participant.append_rm_state(
            RM.VALID, actor=self.invitee_id, context=self.case_id
        )
        participant.append_rm_state(
            RM.ACCEPTED, actor=self.invitee_id, context=self.case_id
        )
        if roles:
            self.logger.info(
                "%s: set case_roles %s on participant '%s' from invite"
                " (CM-17-003)",
                self.name,
                roles,
                self.invitee_id,
            )
        self.blackboard.new_invite_participant = participant
        self.logger.info(
            "%s: created participant object for invitee '%s' at RM.ACCEPTED"
            " (PCR-08-010)",
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


class _CheckEmbargoActiveStateNode(DataLayerAction):
    """Return SUCCESS iff the case has an active embargo in EM.ACTIVE state."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="invitee_case",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="active_embargo_id",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        case = self.blackboard.get("invitee_case")
        if not isinstance(case, VulnerabilityCase):
            self.logger.error("%s: invitee_case not available", self.name)
            # Initialize key so downstream nodes can safely read it.
            self.blackboard.active_embargo_id = None
            return Status.FAILURE

        active_embargo_id = _as_id(case.active_embargo)
        em_state = case.current_status.em_state
        if active_embargo_id and em_state == EM.ACTIVE:
            self.blackboard.active_embargo_id = active_embargo_id
            return Status.SUCCESS
        # Always write the key so PersistInviteeParticipantNode can read it
        # even when there is no active embargo (py_trees raises KeyError for
        # unwritten READ-registered keys — see AGENTS.md pitfalls).
        self.blackboard.active_embargo_id = None
        return Status.FAILURE


class _SignEmbargoConsentLeafNode(DataLayerAction):
    """Sign embargo consent on the participant and record the event."""

    def __init__(self, invitee_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="new_invite_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="active_embargo_id",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        participant = self.blackboard.get("new_invite_participant")
        active_embargo_id = self.blackboard.get("active_embargo_id")
        if not isinstance(participant, VultronParticipant) or not isinstance(
            active_embargo_id, str
        ):
            self.logger.error(
                "%s: participant or active_embargo_id missing", self.name
            )
            return Status.FAILURE

        participant.accepted_embargo_ids.append(active_embargo_id)
        participant.embargo_consent_state = apply_pec_trigger(
            PEC.NO_EMBARGO, PEC_Trigger.ACCEPT
        )
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


class PersistInviteeParticipantNode(DataLayerAction):
    """Persist the participant, attach to case, record events, save case."""

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="invitee_already_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="new_invite_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="invitee_case",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        if self.blackboard.get("invitee_already_participant"):
            return Status.SUCCESS

        participant = self.blackboard.get("new_invite_participant")
        case = self.blackboard.get("invitee_case")
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
            " (RM.ACCEPTED, PCR-08-010)",
            self.name,
            participant.id_,
            self.case_id,
        )
        return Status.SUCCESS


class BackfillCanonicalLedgerToInviteeNode(DataLayerAction):
    """Send canonical CaseLedgerEntry history to a joiner in strict order."""

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id
        self._sync_port: SyncActivityPort | None = None

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="sync_port", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="pre_commit_backfill_target",
            access=py_trees.common.Access.READ,
        )

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = cast(SyncActivityPort, self.blackboard.sync_port)
        except (AttributeError, KeyError):
            self._sync_port = None

    def _resolve_backfill_target(self, entries: list[CaseLedgerEntry]) -> int:
        """Resolve the backfill target index.

        Reads ``pre_commit_backfill_target`` from the blackboard when set to a
        non-None int (resume case: CapturePreCommitBackfillTargetNode wrote the
        last index BEFORE the commit so backfill does not re-send the new entry
        that the commit fan-out already delivered).  ``None`` or a missing key
        means fresh case — fall back to the post-commit last entry.
        """
        try:
            pre_commit_target = self.blackboard.get(
                "pre_commit_backfill_target"
            )
        except KeyError:
            pre_commit_target = None
        if pre_commit_target is not None:
            return int(pre_commit_target)
        return entries[-1].log_index if entries else -1

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE
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
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

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
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
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
        ├── CreateInviteeParticipantAtAcceptedNode — build participant at ACCEPTED
        ├── MaybeSignEmbargoConsentNode            — sign when EM.ACTIVE
        ├── PersistInviteeParticipantNode          — persist, attach, save case
        ├── EmitAnnounceCaseToInviteeNode          — queue Announce to invitee
        └── BackfillCanonicalLedgerToInviteeNode   — send prior ledger to invitee

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
            CreateInviteeParticipantAtAcceptedNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            MaybeSignEmbargoConsentNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            PersistInviteeParticipantNode(
                case_id=case_id, invitee_id=invitee_id
            ),
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
    "CreateInviteeParticipantAtAcceptedNode",
    "MaybeSignEmbargoConsentNode",
    "PersistInviteeParticipantNode",
    "EmitAnnounceCaseToInviteeNode",
    "BackfillCanonicalLedgerToInviteeNode",
    "create_accept_invite_actor_to_case_tree",
]
