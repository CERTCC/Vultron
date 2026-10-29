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
"""The CASE_MANAGER resends each Invite a participant owes an answer to (SYNC-20).

When a participant states its ledger position, in ``Read(CaseLedgerEntry)``
or as an activity's ``ledgerPosition``, the CASE_MANAGER resends each Invite
it still owes an answer to, as first sent (ADR-0163).  These tests run the
CASE_MANAGER's store alone: the joiner is admitted through the real accept
tree, its Invites are delivered (the outbox is drained), and then it states
its position.  ``test_invite_resend_after_queue_expiry.py`` drives both
stores through the inbox pipeline.
"""

from datetime import timedelta
from types import SimpleNamespace
from typing import cast

import pytest

from test.core.use_cases.received.test_embargo_revision_relay import (
    MANAGER,
    OTHER_A,
    PROPOSER,
    _active_case_with_revision,
    _consent_of,
    _deliver,
)
from test.core.use_cases.received.test_joiner_revision_relay import (
    JOINER,
    _join,
)
from test.support.embargo_register import activate, reject
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.config import get_config
from vultron.config.ledger import LedgerConfig
from vultron.core.behaviors.case.nodes.full_case_invite import (
    FULL_CASE_INVITE_SEMANTIC_TYPE,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    EMBARGO_INVITE_SEMANTIC_TYPE,
)
from vultron.core.behaviors.sync.nodes import invite_resend
from vultron.core.behaviors.sync.nodes.replay_guard import (
    doubling_cooldown_seconds,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.invite_resend_record import InviteResendRecord
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.sync_activity import ResendOutcome
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.received.actor.full_case_invite import (
    AcceptInviteActorToFullCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    ReadLedgerEntryReceivedUseCase,
)
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    read_ledger_entry_activity,
    rm_accept_full_case_invite_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
)


def _first_proposal(case_id: str, make_payload) -> tuple[SqliteDataLayer, str]:
    """A case with no embargo in force and one open proposal, relayed."""
    dl, proposal_event = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER], active=False
    )
    proposal = em_propose_embargo_activity(
        proposal_event,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/first",
    )
    _deliver(dl, proposal, make_payload, receiving_actor_id=MANAGER)
    return dl, proposal_event.id_


def _open_revision(case_id: str, make_payload) -> tuple[SqliteDataLayer, str]:
    """A case under embargo A with a revision open (EP-09-002)."""
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/revision",
    )
    _deliver(dl, proposal, make_payload, receiving_actor_id=MANAGER)
    return dl, revision.id_


def _drain(dl: SqliteDataLayer) -> None:
    """Deliver everything queued: the outbox holds nothing pending."""
    while dl.outbox_pop() is not None:
        pass


def _tail(dl: SqliteDataLayer, case_id: str) -> CaseLedgerEntry:
    entries = sorted(
        (
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == case_id
        ),
        key=lambda e: e.log_index,
    )
    return entries[-1]


def _ledger_ids(dl: SqliteDataLayer) -> set[str]:
    return {e.id_ for e in dl.list_objects("CaseLedgerEntry")}


def _state_position(
    dl: SqliteDataLayer, case_id: str, sender: str, make_payload
) -> HandlerResult:
    """*sender* states its position at the CASE_MANAGER's tail."""
    read = read_ledger_entry_activity(
        _tail(dl, case_id), actor=sender, to=[MANAGER]
    )
    return ReadLedgerEntryReceivedUseCase(
        dl,
        make_payload(read, receiving_actor_id=MANAGER, at=dl),
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _invite_id(dl: SqliteDataLayer, semantic_type: str, peer: str) -> str:
    """The Invite the CASE_MANAGER's ledger records sending *peer*."""
    (entry,) = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
        and e.semantic_type == semantic_type
        and peer in (e.payload_snapshot.get("to") or [])
    ]
    return entry.log_object_id


def _embargo_invite(dl: SqliteDataLayer, peer: str = JOINER) -> str:
    return _invite_id(dl, EMBARGO_INVITE_SEMANTIC_TYPE, peer)


def _full_case_invite(dl: SqliteDataLayer, peer: str = JOINER) -> str:
    return _invite_id(dl, FULL_CASE_INVITE_SEMANTIC_TYPE, peer)


def _accept_embargo_invite(
    dl: SqliteDataLayer, case_id: str, invite_id: str, make_payload
) -> HandlerResult:
    invite = cast(as_Invite, dl.read(invite_id))
    accept = em_accept_embargo_activity(
        proposal=invite, context=case_id, actor=JOINER, to=[MANAGER]
    )
    return AcceptInviteToEmbargoOnCaseReceivedUseCase(
        dl,
        make_payload(accept, receiving_actor_id=MANAGER, at=dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()


def _joined(case_id: str, make_payload) -> tuple[SqliteDataLayer, str]:
    """The joiner is admitted during a revision; its Invites are delivered."""
    dl, revision_id = _open_revision(case_id, make_payload)
    assert _join(dl, case_id, make_payload).disposition is (
        HandlerDisposition.APPLIED
    )
    _drain(dl)
    return dl, revision_id


# ---------------------------------------------------------------------------
# SYNC-20-001, SYNC-20-003: the trigger, and the Invite as first sent
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-20-001", "SYNC-20-003", "SYNC-18-002", "EP-09-011")
def test_a_read_resends_the_relayed_invite_as_first_sent(make_payload):
    case_id = "https://example.org/cases/resend-relay"
    dl, _ = _joined(case_id, make_payload)
    invite_id = _embargo_invite(dl)
    sealed = read_sealed_body_dict(dl, invite_id)

    result = _state_position(dl, case_id, JOINER, make_payload)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert invite_id in dl.outbox_list()
    # Queued under its first id, from the body sealed when first sent: the
    # same ledgerPosition and RSVP deadline (SYNC-18-002, OX-07-001).
    assert read_sealed_body_dict(dl, invite_id) == sealed
    assert sealed is not None and "ledgerPosition" in sealed
    assert "endTime" in sealed


@pytest.mark.spec("SYNC-20-001", "SYNC-20-002", "CM-11-010")
def test_a_read_resends_the_unanswered_full_case_invite(make_payload):
    case_id = "https://example.org/cases/resend-full-case"
    dl, _ = _joined(case_id, make_payload)

    _state_position(dl, case_id, JOINER, make_payload)

    assert _full_case_invite(dl) in dl.outbox_list()


@pytest.mark.spec("SYNC-20-001", "SYNC-17-002", "CM-10-004", "CM-10-007")
def test_an_inert_joiner_is_resent_its_invites_and_still_refused(
    make_payload,
):
    """The reworded trigger: inert senders are resent their Invites too.

    The joiner joins while a first proposal is open, so it is active and
    invited to it (EP-09-011).  The owner then activates the proposal: the
    joiner has not agreed, so it is inert (CM-10-004).  Its statement is
    refused with no replication state, and its Invites are resent.
    """
    case_id = "https://example.org/cases/resend-inert"
    dl, proposal_id = _first_proposal(case_id, make_payload)
    assert _join(dl, case_id, make_payload).disposition is (
        HandlerDisposition.APPLIED
    )
    _drain(dl)
    case = cast(VulnerabilityCase, dl.read(case_id))
    activate(case, proposal_id)
    dl.save(case)
    assert _consent_of(dl, case_id, JOINER, proposal_id) is (
        EmbargoConsentState.INVITED
    )
    ledger_before = _ledger_ids(dl)

    result = _state_position(dl, case_id, JOINER, make_payload)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "not an active participant" in (result.reason or "")
    assert "SYNC-17-002" in (result.reason or "")
    state_id = VultronReplicationState(case_id=case_id, peer_id=JOINER).id_
    assert dl.read(state_id) is None
    queued = dl.outbox_list()
    assert _embargo_invite(dl) in queued
    assert _full_case_invite(dl) in queued
    # Nothing else: no ledger entry replayed, none committed (SYNC-20-007).
    assert set(queued) == {_embargo_invite(dl), _full_case_invite(dl)}
    assert _ledger_ids(dl) == ledger_before


@pytest.mark.spec("SYNC-20-008", "CM-31-013")
def test_a_removed_participant_is_resent_nothing(make_payload):
    case_id = "https://example.org/cases/resend-removed"
    dl, _ = _joined(case_id, make_payload)
    case = cast(VulnerabilityCase, dl.read(case_id))
    record = cast(
        CaseParticipant, dl.read(case.actor_participant_index[JOINER])
    )
    record.record_removal("https://example.org/activities/remove-joiner")
    dl.save(record)

    result = _state_position(dl, case_id, JOINER, make_payload)

    assert result.disposition is HandlerDisposition.REFUSED
    assert dl.outbox_list() == []


@pytest.mark.spec("SYNC-20-001")
def test_an_inert_participant_invited_to_a_revision_is_resent_it(
    make_payload,
):
    """A participant that never signed the embargo in force is inert, and
    still owes the revision it was relayed an answer (EP-09-002)."""
    case_id = "https://example.org/cases/resend-unsigned"
    dl, revision_id = _open_revision(case_id, make_payload)
    _drain(dl)
    assert _consent_of(dl, case_id, OTHER_A, revision_id) is (
        EmbargoConsentState.INVITED
    )

    result = _state_position(dl, case_id, OTHER_A, make_payload)

    assert result.disposition is HandlerDisposition.REFUSED
    assert dl.outbox_list() == [_embargo_invite(dl, OTHER_A)]


# ---------------------------------------------------------------------------
# SYNC-20-002: what is owed
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-20-002")
def test_an_answered_embargo_invite_is_not_resent(make_payload):
    case_id = "https://example.org/cases/resend-answered"
    dl, revision_id = _joined(case_id, make_payload)
    invite_id = _embargo_invite(dl)
    _accept_embargo_invite(dl, case_id, invite_id, make_payload)
    assert _consent_of(dl, case_id, JOINER, revision_id) is (
        EmbargoConsentState.AGREED
    )
    _drain(dl)
    # The Accept's own stamp resent the full-case Invite; let its cooldown
    # pass so this statement resends it again.
    _age_resend(dl, _full_case_invite(dl), timedelta(hours=1))

    _state_position(dl, case_id, JOINER, make_payload)

    assert invite_id not in dl.outbox_list()
    # The resend ran: the unanswered full-case Invite is resent.
    assert _full_case_invite(dl) in dl.outbox_list()


@pytest.mark.spec("SYNC-20-002")
def test_an_invite_for_a_decided_proposal_is_not_resent(make_payload):
    case_id = "https://example.org/cases/resend-decided"
    dl, revision_id = _joined(case_id, make_payload)
    case = cast(VulnerabilityCase, dl.read(case_id))
    reject(case, revision_id)
    dl.save(case)

    _state_position(dl, case_id, JOINER, make_payload)

    assert _embargo_invite(dl) not in dl.outbox_list()
    # The resend ran: the unanswered full-case Invite is resent.
    assert _full_case_invite(dl) in dl.outbox_list()


@pytest.mark.spec("SYNC-20-002")
def test_an_invite_for_a_withdrawn_proposal_is_not_resent(make_payload):
    """A withdrawn proposal leaves the register's open entries (EP-02)."""
    case_id = "https://example.org/cases/resend-withdrawn"
    dl, revision_id = _joined(case_id, make_payload)
    case = cast(VulnerabilityCase, dl.read(case_id))
    case.embargo_register = [
        entry.model_copy(update={"status": "CANCELLED"})
        if entry.embargo_id == revision_id
        else entry
        for entry in case.embargo_register
    ]
    dl.save(case)

    _state_position(dl, case_id, JOINER, make_payload)

    assert _embargo_invite(dl) not in dl.outbox_list()
    # The resend ran: the unanswered full-case Invite is resent.
    assert _full_case_invite(dl) in dl.outbox_list()


@pytest.mark.spec("SYNC-20-002", "CM-28-001")
def test_an_invite_past_its_rsvp_deadline_is_not_resent(make_payload):
    case_id = "https://example.org/cases/resend-expired"
    dl, revision_id = _joined(case_id, make_payload)
    case = cast(VulnerabilityCase, dl.read(case_id))
    record = cast(
        CaseParticipant, dl.read(case.actor_participant_index[JOINER])
    )
    record.embargo_consents = [
        row.model_copy(
            update={"rsvp_deadline": now_utc() - timedelta(hours=1)}
        )
        if row.embargo_id == revision_id
        else row
        for row in record.embargo_consents
    ]
    dl.save(record)

    _state_position(dl, case_id, JOINER, make_payload)

    assert _embargo_invite(dl) not in dl.outbox_list()
    # The resend ran: the unanswered full-case Invite is resent.
    assert _full_case_invite(dl) in dl.outbox_list()


@pytest.mark.spec("SYNC-20-002", "CM-11-012")
def test_a_replied_full_case_invite_is_not_resent_and_a_reply_still_counts(
    make_payload,
):
    """A reply at the resent Invite's floor still passes CM-11-012."""
    case_id = "https://example.org/cases/resend-full-case-reply"
    dl, _ = _joined(case_id, make_payload)
    invite_id = _full_case_invite(dl)
    _state_position(dl, case_id, JOINER, make_payload)
    assert invite_id in dl.outbox_list()
    _drain(dl)

    sealed = read_sealed_body_dict(dl, invite_id)
    assert sealed is not None
    invite = as_Invite.model_validate(sealed)
    floor = invite.ledger_position
    assert floor is not None
    # A reply at the resent Invite's floor (CM-11-012).
    reply = rm_accept_full_case_invite_activity(
        invite,
        LedgerPosition(log_index=floor.log_index, entry_hash=floor.entry_hash),
        actor=JOINER,
        to=[MANAGER],
    )
    accepted = AcceptInviteActorToFullCaseReceivedUseCase(
        dl,
        make_payload(reply, receiving_actor_id=MANAGER, at=dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()
    assert accepted.disposition is HandlerDisposition.APPLIED, accepted.reason
    _drain(dl)
    # Let both cooldowns pass, so only the reply keeps the full-case Invite
    # from being resent; the embargo Invite, still owed, shows the resend ran.
    _age_resend(dl, invite_id, timedelta(hours=1))
    _age_resend(dl, _embargo_invite(dl), timedelta(hours=1))

    _state_position(dl, case_id, JOINER, make_payload)

    assert invite_id not in dl.outbox_list()
    assert _embargo_invite(dl) in dl.outbox_list()


# ---------------------------------------------------------------------------
# SYNC-20-004, SYNC-20-005: the rate bound
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-20-004", "OX-06-002")
def test_an_invite_still_pending_in_the_outbox_is_not_resent(make_payload):
    case_id = "https://example.org/cases/resend-pending"
    dl, _ = _open_revision(case_id, make_payload)
    _join(dl, case_id, make_payload)
    invite_id = _embargo_invite(dl)
    pending = dl.outbox_list()
    assert invite_id in pending

    _state_position(dl, case_id, JOINER, make_payload)

    assert dl.outbox_list().count(invite_id) == 1
    # A skipped resend is not counted against the cooldown.
    assert dl.read(InviteResendRecord.build_id(invite_id, JOINER)) is None


def _age_resend(dl: SqliteDataLayer, invite_id: str, by: timedelta) -> None:
    record = cast(
        InviteResendRecord,
        dl.read(InviteResendRecord.build_id(invite_id, JOINER)),
    )
    dl.save(record.model_copy(update={"last_resent_at": now_utc() - by}))


@pytest.mark.spec("SYNC-20-005")
def test_each_consecutive_resend_doubles_the_cooldown(make_payload):
    case_id = "https://example.org/cases/resend-cooldown"
    dl, _ = _joined(case_id, make_payload)
    invite_id = _embargo_invite(dl)
    base = get_config().ledger.invite_resend_cooldown_seconds

    _state_position(dl, case_id, JOINER, make_payload)
    assert invite_id in dl.outbox_list()
    _drain(dl)

    # Inside the base cooldown: not resent.
    _state_position(dl, case_id, JOINER, make_payload)
    assert invite_id not in dl.outbox_list()

    # Past the base: resent, and the next wait is twice the base.
    _age_resend(dl, invite_id, timedelta(seconds=base + 1))
    _state_position(dl, case_id, JOINER, make_payload)
    assert invite_id in dl.outbox_list()
    _drain(dl)
    record = cast(
        InviteResendRecord,
        dl.read(InviteResendRecord.build_id(invite_id, JOINER)),
    )
    assert record.resends == 2

    _age_resend(dl, invite_id, timedelta(seconds=base + 1))
    _state_position(dl, case_id, JOINER, make_payload)
    assert invite_id not in dl.outbox_list(), "the second wait is doubled"

    _age_resend(dl, invite_id, timedelta(seconds=2 * base + 1))
    _state_position(dl, case_id, JOINER, make_payload)
    assert invite_id in dl.outbox_list()


@pytest.mark.spec("SYNC-20-005", "SYNC-15-013")
def test_the_doubled_cooldown_stops_at_its_ceiling():
    assert doubling_cooldown_seconds(30.0, 600.0, sent=1) == 30.0
    assert doubling_cooldown_seconds(30.0, 600.0, sent=2) == 60.0
    assert doubling_cooldown_seconds(30.0, 600.0, sent=5) == 480.0
    assert doubling_cooldown_seconds(30.0, 600.0, sent=6) == 600.0
    assert doubling_cooldown_seconds(30.0, 600.0, sent=10_000) == 600.0


@pytest.mark.spec("SYNC-20-006", "SYNC-05-003")
def test_the_resend_cooldown_defaults_are_the_replay_defaults():
    config = LedgerConfig()
    assert config.invite_resend_cooldown_seconds == 30.0
    assert config.invite_resend_max_cooldown_seconds == 600.0


@pytest.mark.spec("SYNC-20-006")
def test_a_resend_ceiling_below_its_base_is_refused():
    with pytest.raises(ValueError, match="SYNC-20-005"):
        LedgerConfig(
            invite_resend_cooldown_seconds=60,
            invite_resend_max_cooldown_seconds=30,
        )


# ---------------------------------------------------------------------------
# SYNC-20-007: not a case event; a stamped position triggers it too
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-20-001", "SYNC-20-007", "SYNC-18-007")
def test_a_stamped_position_resends_and_keeps_the_activitys_outcome(
    make_payload,
):
    """The joiner's Accept of the revision states its position too.

    The Accept answers the embargo Invite, so that one is not resent; the
    unanswered full-case Invite is.  The Accept is applied as it would be
    without the resend, and only its own entries are committed.
    """
    case_id = "https://example.org/cases/resend-stamped"
    dl, revision_id = _joined(case_id, make_payload)
    embargo_invite = _embargo_invite(dl)
    ledger_before = _ledger_ids(dl)

    result = _accept_embargo_invite(dl, case_id, embargo_invite, make_payload)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _consent_of(dl, case_id, JOINER, revision_id) is (
        EmbargoConsentState.AGREED
    )
    queued = dl.outbox_list()
    assert _full_case_invite(dl) in queued
    assert embargo_invite not in queued
    # The new entries are the Accept's own act; none records a resend.
    new = [
        cast(CaseLedgerEntry, dl.read(i))
        for i in _ledger_ids(dl) - ledger_before
    ]
    assert new
    assert all(
        e.log_object_id not in {embargo_invite, _full_case_invite(dl)}
        for e in new
    )


@pytest.mark.spec("SYNC-20-007", "SYNC-17-006")
def test_a_resend_commits_no_ledger_entry(make_payload):
    case_id = "https://example.org/cases/resend-no-entry"
    dl, _ = _joined(case_id, make_payload)
    ledger_before = _ledger_ids(dl)

    _state_position(dl, case_id, JOINER, make_payload)

    assert dl.outbox_list()
    assert _ledger_ids(dl) == ledger_before


@pytest.mark.spec("SYNC-20-003")
def test_an_invite_with_no_sealed_body_is_logged_and_skipped(
    make_payload, monkeypatch, caplog
):
    """Nothing is rebuilt: an Invite this store did not seal is not sent."""
    case_id = "https://example.org/cases/resend-unsealed"
    dl, _ = _joined(case_id, make_payload)
    monkeypatch.setattr(
        SyncActivityAdapter,
        "resend_sealed_activity",
        lambda self, activity_id: ResendOutcome.NOT_SEALED,
    )

    with caplog.at_level("WARNING", logger=invite_resend.__name__):
        result = _state_position(dl, case_id, JOINER, make_payload)

    assert result.disposition is HandlerDisposition.APPLIED
    assert dl.outbox_list() == []
    assert "no sealed body" in caplog.text


# ---------------------------------------------------------------------------
# SYNC-20-002: which of several Invites is owed
# ---------------------------------------------------------------------------

_PEER = "https://example.org/users/peer"
_OTHER = "https://example.org/users/other"
_EMBARGO = "https://example.org/embargoes/e1"


def _entry(
    log_index: int,
    semantic_type: str,
    *,
    actor: str = MANAGER,
    to: str = _PEER,
    obj: object = _EMBARGO,
) -> CaseLedgerEntry:
    """A stand-in for a ledger entry: the fields ``owed_invites`` reads."""
    return cast(
        CaseLedgerEntry,
        SimpleNamespace(
            log_index=log_index,
            semantic_type=semantic_type,
            log_object_id=f"https://example.org/activities/{log_index}",
            payload_snapshot={"actor": actor, "to": [to], "object": obj},
        ),
    )


_INVITE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value
_FULL_CASE = MessageSemantics.INVITE_ACTOR_TO_FULL_CASE.value


@pytest.mark.spec("SYNC-20-002", "EMB-17-003")
def test_only_the_last_invite_sent_for_an_embargo_is_owed():
    entries = [_entry(0, _INVITE), _entry(1, _INVITE)]

    latest = invite_resend._latest_embargo_invites(
        entries, manager_id=MANAGER, peer_id=_PEER
    )

    assert latest == {_EMBARGO: "https://example.org/activities/1"}


@pytest.mark.spec("SYNC-20-002")
def test_an_invite_to_another_participant_or_from_another_actor_is_not_owed():
    """Only the CASE_MANAGER's own Invite to the stating participant counts:
    not its Invite to someone else, and not the proposer's Invite it
    received."""
    entries = [
        _entry(0, _INVITE),
        _entry(1, _INVITE, to=_OTHER),
        _entry(2, _INVITE, actor=PROPOSER, to=MANAGER),
        _entry(3, _INVITE, obj={"id": "https://example.org/embargoes/e2"}),
    ]

    latest = invite_resend._latest_embargo_invites(
        entries, manager_id=MANAGER, peer_id=_PEER
    )

    assert latest == {
        _EMBARGO: "https://example.org/activities/0",
        "https://example.org/embargoes/e2": "https://example.org/activities/3",
    }


@pytest.mark.spec("SYNC-20-002", "CM-11-011")
def test_a_full_case_invite_is_owed_until_its_invitee_replies():
    invite = _entry(0, _FULL_CASE, obj=_PEER)
    invite_id = invite.log_object_id
    other_reply = _entry(
        1,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE.value,
        actor=_OTHER,
        to=MANAGER,
        obj=invite_id,
    )
    reply = _entry(
        2,
        MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE.value,
        actor=_PEER,
        to=MANAGER,
        obj={"id": invite_id},
    )

    def owed(entries: list[CaseLedgerEntry]) -> str | None:
        return invite_resend._full_case_invite(
            entries, manager_id=MANAGER, peer_id=_PEER
        )

    assert owed([invite]) == invite_id
    assert owed([invite, other_reply]) == invite_id
    assert owed([invite, other_reply, reply]) is None
    assert owed([_entry(0, _FULL_CASE, to=_OTHER, obj=_OTHER)]) is None


@pytest.mark.spec("SYNC-20-005")
def test_a_failed_cooldown_record_keeps_no_resend(make_payload, monkeypatch):
    """The requeue and its cooldown record commit together (ADR-0146)."""
    case_id = "https://example.org/cases/resend-record-fails"
    dl, _ = _joined(case_id, make_payload)

    def _fail(*_args: object) -> None:
        raise RuntimeError("record write failed")

    monkeypatch.setattr(invite_resend, "_record_resend", _fail)

    with pytest.raises(Exception, match="record write failed"):
        _state_position(dl, case_id, JOINER, make_payload)

    assert dl.outbox_list() == []
