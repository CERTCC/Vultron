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


"""Join-time ledger-backfill and case-announce leaf nodes for the accept-invite tree.

Snapshot the pre-commit ledger tail, queue ``Announce(VulnerabilityCase)`` to
the invitee, and backfill the canonical ``CaseLedgerEntry`` history in strict
order (MV-10-003/MV-10-005). Composed by
``create_accept_invite_actor_to_case_tree`` (BTND-07-003).
"""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
    _EmitSingleActivityBase,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


class CapturePreCommitBackfillTargetNode(DataLayerActionWithPorts):
    """Snapshot the current last ledger-entry index for resume-case backfill.

    This node MUST appear AFTER ``CheckInviteeNotAlreadyParticipantNode`` in
    the precondition-guards list, so it can read ``invitee_already_participant``
    and ``invitee_joined`` from the blackboard.

    **Resume case** (invitee already registered, ``invitee_already_participant
    = True``, ``invitee_joined = True``): the commit's ``FanOutLogEntryNode``
    will include the invitee in its recipient list (they are a current case
    participant), so ``BackfillCanonicalLedgerToInviteeNode`` must limit its
    window to entries that existed *before* the commit to avoid sending the
    new entry twice.  This node writes ``pre_commit_backfill_target`` to the
    blackboard.

    **Inert-record case** (``invitee_already_participant = True``,
    ``invitee_joined = False``): the invitee has an inert stub record at
    invite-send time (ADR-0114, CM-11-006) but is NOT in the fan-out
    recipients (``is_active_participant()`` is False), so the commit fan-out
    will NOT include them.  Treat as fresh: leave
    ``pre_commit_backfill_target`` unset so backfill covers all entries
    including the new accept entry.

    **Fresh case** (invitee not yet registered, ``invitee_already_participant
    = False``): the receipt commit's fan-out will NOT include the invitee (they
    are not yet a participant), so backfill must include the newly committed
    receipt entry in its window.  This node does *not* write
    ``pre_commit_backfill_target``, leaving
    ``BackfillCanonicalLedgerToInviteeNode`` to compute its target from the
    ledger tail at backfill time.  The full-case Invite's entry
    (``EmitInviteActorToFullCaseNode``) is committed *after* the backfill and
    reaches the invitee through its own fan-out, in chain order (CM-17-004).

    Always returns ``SUCCESS``.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "invitee_already_participant": PortInformation(
            data_type=object, required=False
        ),
        "invitee_joined": PortInformation(data_type=object, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "pre_commit_backfill_target": PortInformation(
            data_type=object, required=False
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_already_participant": "/invitee_already_participant",
            "invitee_joined": "/invitee_joined",
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
        try:
            self._invitee_joined_bb = self.get_input("invitee_joined")
        except (NoDataAvailable, NotImplementedError):
            self._invitee_joined_bb = None

    def update(self) -> Status:
        already_participant = self._already_participant_bb
        # An inert participant (joined=False, ADR-0114) is not included in the
        # fan-out, so treat the same as fresh — no pre-commit snapshot.
        invitee_joined = self._invitee_joined_bb
        is_resume = already_participant and invitee_joined is not False

        if not is_resume:
            # Fresh case (or inert record): the commit fan-out won't reach the
            # invitee.  Write None so BackfillCanonicalLedgerToInviteeNode
            # uses the ledger tail at backfill time, and any stale value from
            # a prior resume test is overwritten.
            self._set_output("pre_commit_backfill_target", None)
            self.logger.debug(
                "%s: fresh/inert invite — clearing pre-commit backfill target"
                " (backfill will include post-commit entry)",
                self.name,
            )
            return Status.SUCCESS

        # Resume case: invitee IS already a fully-joined participant.
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


class BackfillCanonicalLedgerToInviteeNode(DataLayerActionWithPorts):
    """Send canonical CaseLedgerEntry history to a joiner in strict order.

    A missing ``sync_port`` is a wiring fault and raises
    ``VultronWiringError``, as the fan-out does (SYNC-02-003, #4126).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id
        self._sync_port: SyncActivityPort | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "sync_port": PortInformation(data_type=object, required=False),
        "pre_commit_backfill_target": PortInformation(
            data_type=object, required=False
        ),
    }

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
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to backfill the"
                f" ledger of case '{self.case_id}' to '{self.invitee_id}'"
                " (SYNC-02-003, #4126)"
            )

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


class EmitAnnounceCaseToInviteeNode(_EmitSingleActivityBase):
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
            # Route through the shared emit seam (OX-14-001, ASK-04-008).
            # factory.announce_vulnerability_case returns str only;
            # pass an empty blob since no captured dict is present.
            self._emit_through_seam(activity_id, "")
            self.logger.info(
                "%s: queued AnnounceVulnerabilityCase '%s' to '%s'"
                " for case '%s' (MV-10-003)",
                self.name,
                activity_id,
                self.invitee_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: failed to emit AnnounceVulnerabilityCase for case '%s'"
                " to '%s': %s",
                self.name,
                self.case_id,
                self.invitee_id,
                exc,
            )
            return Status.SUCCESS
