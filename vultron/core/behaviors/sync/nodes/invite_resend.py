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
"""The CASE_MANAGER resends each Invite a participant owes an answer to.

A participant that states its ledger position, in ``Read(CaseLedgerEntry)``
or as an activity's ``ledgerPosition``, tells the CASE_MANAGER that its
replica holds the case (SYNC-17-008).  That is the moment an Invite it lost,
such as one dropped from its pre-bootstrap queue before its case copy
arrived (CBT-03-003), can be answered, so the CASE_MANAGER resends each
Invite the participant still owes an answer to (SYNC-20-001, ADR-0163).

- **Who** — any participant on the roster that is not removed and not
  closed, active or inert (SYNC-20-001): an Invite asks for an answer, it is
  not case content (CM-10-007), and a resent Invite is one the participant
  was already sent.
- **What is owed** (:func:`owed_invites`, SYNC-20-002) — an
  ``Invite(EmbargoEvent)`` whose consent row is still ``INVITED``, for an
  embargo still open or in force, before its RSVP deadline; and the
  full-case Invite (CM-11-010) until the participant replies to it.  The
  Invite the stating activity itself answers is not owed.
- **How** — the sealed body, as first sent, under its first id
  (SYNC-20-003), skipped while an earlier send is still pending in the
  outbox (SYNC-20-004), and at most once per cooldown that doubles with each
  resend of the same Invite to the same participant (SYNC-20-005).
- **Not a case event** — nothing is committed, and the stating activity's
  outcome does not change (SYNC-20-007).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.config.app import get_config
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.replay_guard import (
    cooldown_elapsed,
    doubling_cooldown_seconds,
)
from vultron.core.models._helpers import _as_id, now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.invite_resend_record import InviteResendRecord
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import ResendOutcome, SyncActivityPort
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.sync_helpers import sorted_case_ledger_entries
from vultron.errors import VultronWiringError
from vultron.primitives import same_actor_id

__all__ = [
    "OwedInvite",
    "ResendOwedInvitesNode",
    "owed_invites",
]

#: Register statuses of an embargo whose Invite can still be answered: an
#: open proposal, or the embargo in force, which a reinstated or late
#: participant is asked to sign (CM-31-013, EMB-17-003).
_ANSWERABLE_EMBARGO: frozenset[EmbargoRegisterStatus] = frozenset(
    {EmbargoRegisterStatus.PROPOSED, EmbargoRegisterStatus.ACTIVE}
)

#: Ledger ``semantic_type`` of an ``Invite(EmbargoEvent)`` emission, the
#: relay's (``embargo.nodes.relay.EMBARGO_INVITE_SEMANTIC_TYPE``).
EMBARGO_INVITE_SEMANTIC_TYPE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value

#: Ledger ``semantic_type`` of the full-case Invite's emission
#: (``case.nodes.full_case_invite.FULL_CASE_INVITE_SEMANTIC_TYPE``).
FULL_CASE_INVITE_SEMANTIC_TYPE = (
    MessageSemantics.INVITE_ACTOR_TO_FULL_CASE.value
)

#: Ledger ``semantic_type`` of each reply to the full-case Invite (CM-11-011).
_FULL_CASE_REPLY_SEMANTIC_TYPES: frozenset[str] = frozenset(
    {
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE.value,
        MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE.value,
        MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE.value,
    }
)


@dataclass(frozen=True, slots=True)
class OwedInvite:
    """One Invite a participant owes an answer to.

    Attributes:
        invite_id: The Invite's id, as first sent.
        label: What it asks, for the log: the embargo it names, or
            ``"full-case"``.
    """

    invite_id: str
    label: str


def _addressed_to(snapshot: dict, peer_id: str) -> bool:
    to = snapshot.get("to") or []
    recipients = to if isinstance(to, list) else [to]
    return any(same_actor_id(_as_id(r) or "", peer_id) for r in recipients)


def _sent_by(snapshot: dict, actor_id: str) -> bool:
    return same_actor_id(_as_id(snapshot.get("actor")) or "", actor_id)


def _latest_embargo_invites(
    entries: Iterable[CaseLedgerEntry], *, manager_id: str, peer_id: str
) -> dict[str, str]:
    """``embargo id → Invite id`` of the last embargo Invite *manager_id*
    sent *peer_id*, for each embargo; *entries* in log order."""
    latest: dict[str, str] = {}
    for entry in entries:
        if entry.semantic_type != EMBARGO_INVITE_SEMANTIC_TYPE:
            continue
        snapshot = entry.payload_snapshot
        embargo_id = _as_id(snapshot.get("object"))
        if (
            embargo_id
            and _sent_by(snapshot, manager_id)
            and _addressed_to(snapshot, peer_id)
        ):
            latest[embargo_id] = entry.log_object_id
    return latest


def _embargo_invite_owed(
    case: VulnerabilityCase, participant: CaseParticipant, embargo_id: str
) -> bool:
    """Whether *participant*'s answer to *embargo_id*'s Invite still counts.

    Its row is ``INVITED``, the embargo is open or in force, and the row's
    RSVP deadline has not passed (EP-09-002, EP-09-011, CM-31-013).
    """
    entry = case.embargo_register_entry(embargo_id)
    if entry is None or entry.status not in _ANSWERABLE_EMBARGO:
        return False
    row = participant.held_row(embargo_id)
    if row is None or row.state is not EmbargoConsentState.INVITED:
        return False
    return row.rsvp_deadline is None or now_utc() < row.rsvp_deadline


def _full_case_invite(
    entries: list[CaseLedgerEntry], *, manager_id: str, peer_id: str
) -> str | None:
    """The full-case Invite *peer_id* has not replied to, or ``None``.

    The CASE_MANAGER asks once per case (CM-11-010); the ledger records any
    reply to it (CM-11-011), and a replied Invite is owed nothing.
    """
    invite_id = next(
        (
            entry.log_object_id
            for entry in entries
            if entry.semantic_type == FULL_CASE_INVITE_SEMANTIC_TYPE
            and _sent_by(entry.payload_snapshot, manager_id)
            and _addressed_to(entry.payload_snapshot, peer_id)
        ),
        None,
    )
    if invite_id is None:
        return None
    replied = any(
        entry.semantic_type in _FULL_CASE_REPLY_SEMANTIC_TYPES
        and _sent_by(entry.payload_snapshot, peer_id)
        and _as_id(entry.payload_snapshot.get("object")) == invite_id
        for entry in entries
    )
    return None if replied else invite_id


def owed_invites(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    manager_id: str,
    peer_id: str,
    excluding: Collection[str] = (),
) -> list[OwedInvite]:
    """The Invites *manager_id* sent *peer_id* that *peer_id* still owes.

    Empty for a participant the CASE_MANAGER may not invite: one removed,
    closed or not on the roster (CM-31-013, CM-10-007).  Otherwise each
    ``Invite(EmbargoEvent)`` whose answer still counts, the last one sent
    for each embargo, then the unanswered full-case Invite, minus the ids in
    *excluding* (the Invite the stating activity answers).  Read from the
    ledger, which records every Invite the CASE_MANAGER sent (ADR-0119).

    Spec: SYNC-20-002.
    """
    if peer_id not in invitation_recipients(case, dl):
        return []
    participant = dl.read(case.actor_participant_index[peer_id])
    if not isinstance(participant, CaseParticipant):
        return []
    entries = sorted_case_ledger_entries(dl, case.id_)
    owed = [
        OwedInvite(invite_id=invite_id, label=embargo_id)
        for embargo_id, invite_id in _latest_embargo_invites(
            entries, manager_id=manager_id, peer_id=peer_id
        ).items()
        if _embargo_invite_owed(case, participant, embargo_id)
    ]
    full_case = _full_case_invite(
        entries, manager_id=manager_id, peer_id=peer_id
    )
    if full_case is not None:
        owed.append(OwedInvite(invite_id=full_case, label="full-case"))
    skip = set(excluding)
    return [invite for invite in owed if invite.invite_id not in skip]


def _resend_due(dl: CasePersistence, invite_id: str, peer_id: str) -> bool:
    """Whether the resend cooldown for *invite_id* to *peer_id* has passed.

    One resend waits the configured base; each further one doubles it, up to
    the configured ceiling (SYNC-20-005, SYNC-20-006).
    """
    record = dl.read(InviteResendRecord.build_id(invite_id, peer_id))
    if not isinstance(record, InviteResendRecord):
        return True
    ledger = get_config().ledger
    cooldown = doubling_cooldown_seconds(
        ledger.invite_resend_cooldown_seconds,
        ledger.invite_resend_max_cooldown_seconds,
        sent=record.resends,
    )
    return cooldown_elapsed(record.last_resent_at, cooldown)


def _record_resend(dl: CasePersistence, invite_id: str, peer_id: str) -> None:
    """Count one more resend of *invite_id* to *peer_id*, stamped now."""
    record = dl.read(InviteResendRecord.build_id(invite_id, peer_id))
    resends = (
        record.resends + 1 if isinstance(record, InviteResendRecord) else 1
    )
    dl.save(
        InviteResendRecord(
            invite_id=invite_id,
            peer_id=peer_id,
            resends=resends,
            last_resent_at=now_utc(),
        )
    )


class ResendOwedInvitesNode(DataLayerActionWithPorts):
    """Resend each Invite *sender_id* owes an answer to in *case_id*.

    Runs at the case's CASE_MANAGER when it acts on a position *sender_id*
    stated, whether or not the sender is an active participant
    (SYNC-20-001).  For each Invite :func:`owed_invites` names, other than
    the one the received activity (``/activity``) answers, it asks the sync
    port to queue the sealed body again (SYNC-20-003), unless the cooldown
    since its last resend to the sender has not passed (SYNC-20-005).  A
    resend the port finds still pending is not counted (SYNC-20-004); one it
    cannot find sealed is logged at WARNING and skipped.  It commits
    nothing (SYNC-20-007) and always succeeds once wired: what it resends is
    no part of the received activity's outcome.  A store fault raises.

    ``resent`` lists the Invite ids queued in the last run, for inspection.

    Spec: SYNC-20-001 to SYNC-20-005, SYNC-20-007.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity", "sync_port": "/sync_port"}

    def __init__(
        self, case_id: str, sender_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.sender_id = sender_id
        self.resent: list[str] = []
        self._sync_port: SyncActivityPort | None = None

    def initialise(self) -> None:
        super().initialise()
        self.resent = []
        self.activity = self.get_input("activity")
        try:
            self._sync_port = cast(
                "SyncActivityPort | None", self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def _answered_ids(self) -> set[str]:
        """The Invite the received activity answers, if it answers one."""
        activity = self.activity
        return {
            ref
            for ref in (
                getattr(activity, "object_id", None),
                getattr(activity, "in_reply_to", None),
            )
            if isinstance(ref, str) and ref
        }

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        if same_actor_id(self.sender_id, self.actor_id):
            return Status.SUCCESS
        dl = cast(CasePersistence, self.datalayer)
        case = dl.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS
        owed = owed_invites(
            case,
            dl,
            manager_id=self.actor_id,
            peer_id=self.sender_id,
            excluding=self._answered_ids(),
        )
        if not owed:
            return Status.SUCCESS
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to resend Invites"
            )
        for invite in owed:
            self._resend(dl, invite)
        return Status.SUCCESS

    def _resend(self, dl: CasePersistence, invite: OwedInvite) -> None:
        assert self._sync_port is not None
        if not _resend_due(dl, invite.invite_id, self.sender_id):
            self.logger.debug(
                "%s: Invite '%s' (%s) to '%s' was resent inside its cooldown;"
                " not resent again (SYNC-20-005)",
                self.name,
                invite.invite_id,
                invite.label,
                self.sender_id,
            )
            return
        outcome = self._sync_port.resend_sealed_activity(invite.invite_id)
        if outcome is ResendOutcome.QUEUED:
            _record_resend(dl, invite.invite_id, self.sender_id)
            self.resent.append(invite.invite_id)
            self.logger.info(
                "%s: resent unanswered Invite '%s' (%s) to '%s' for case"
                " '%s' (SYNC-20-001)",
                self.name,
                invite.invite_id,
                invite.label,
                self.sender_id,
                self.case_id,
            )
        elif outcome is ResendOutcome.PENDING:
            self.logger.debug(
                "%s: Invite '%s' to '%s' is still pending in the outbox; not"
                " resent (SYNC-20-004)",
                self.name,
                invite.invite_id,
                self.sender_id,
            )
        else:
            self.logger.warning(
                "%s: Invite '%s' (%s) to '%s' has no sealed body in this"
                " store; it cannot be resent as first sent (SYNC-20-003)",
                self.name,
                invite.invite_id,
                invite.label,
                self.sender_id,
            )
