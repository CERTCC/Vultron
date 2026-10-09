#!/usr/bin/env python
"""Integration tests for AnnounceLogEntryReceivedBT."""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.support.embargo_register import (
    activate,
    propose,
    terminate,
    write_consent_rows,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.ledger_snapshots import (
    build_create_case_participant_snapshot,
    build_update_case_participant_snapshot,
)
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.participant_event_types import (
    CREATE_CASE_PARTICIPANT_EVENT_TYPE,
    UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.rsvp_deadline import (
    INVITE_EXPIRED_EVENT_TYPE,
    INVITE_EXPIRED_SNAPSHOT_TYPE,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.cs import CS_vf
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# Populate vocabulary registry as side-effect.
_ = as_VulnerabilityCase

OWNER_ACTOR_ID = "https://example.org/actors/vendor"
PARTICIPANT_ACTOR_ID = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/case-sync"

_ZERO_HASH: str = "0" * 64  # arbitrary prev_log_hash for test chains


@pytest.fixture
def datalayer():
    """The participant's own replica store (ADR-0073).

    Almost every tree here executes as PARTICIPANT_ACTOR_ID, applying an
    announced ledger entry to that participant's replica.  ``case_actor.id_``
    passed to ``_make_event`` is the entry's *author*, not the executing actor.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=PARTICIPANT_ACTOR_ID)


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def case_actor(datalayer):
    actor = CaseActor(
        name="Case Actor",
        attributed_to=OWNER_ACTOR_ID,
        context=CASE_ID,
    )
    datalayer.create(actor)
    return actor


@pytest.fixture
def case_obj(datalayer):
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    datalayer.save(case)
    return case


def _make_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            event_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev_hash,
        )
    )


def _make_event(
    entry: CaseLedgerEntry, actor_id: str
) -> AnnounceLogEntryReceivedEvent:
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(entry=wire_entry, actor=actor_id)
    event = cast(AnnounceLogEntryReceivedEvent, extract_event(activity))
    # The inbox pipeline attaches the core wire activity; intake archives it.
    event.activity = VultronActivity(
        id_=event.activity_id,
        type_="Announce",
        actor=actor_id,
        object_=entry,
    )
    return event


def test_create_announce_log_entry_tree_is_intake_then_role_selector():
    tree = create_announce_log_entry_tree()
    assert tree.name == "AnnounceLogEntryReceivedBT"
    # Intake first (CLP-10-017), then the CASE_MANAGER / participant arms.
    assert tree.children[0].name == "IntakeReceivedActivityNode"
    assert len(tree.children) == 2
    assert len(tree.children[1].children) == 2


def _archived(datalayer, event) -> bool:
    record = datalayer.read(ReceivedActivityRecord.build_id(event.activity_id))
    return isinstance(record, ReceivedActivityRecord)


@pytest.mark.spec("CLP-10-017")
def test_announce_archives_the_received_activity(
    bridge, datalayer, case_actor, case_obj
):
    entry = _make_entry(0, case_obj.genesis_hash)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )

    assert result.status == Status.SUCCESS
    assert _archived(datalayer, event)


@pytest.fixture
def owner_bridge():
    """A BTBridge backed by a DataLayer scoped to OWNER_ACTOR_ID.

    Used by the bootstrap window test so that execute_with_setup(actor_id=
    OWNER_ACTOR_ID) doesn't clone an empty store for a foreign actor.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER_ACTOR_ID)
    participant = CaseParticipant(
        attributed_to=OWNER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(participant)
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    case.case_participants.append(participant)
    dl.save(case)
    return BTBridge(datalayer=dl)


@pytest.mark.spec("ARCH-24-003")
@pytest.mark.spec("CM-02-011")
@pytest.mark.spec("CM-02-012")
def test_case_manager_role_takes_authority_arm_without_service_object(
    owner_bridge,
):
    """CM-02-012 bootstrap window: the authority recognizes its own ledger entry.

    The actor enacting ``CVDRole.CASE_MANAGER`` must take the *authority* arm of
    the announce two-arm split on its own ledger entry even before any
    ``Service`` object carries the case ``context`` — the exact window in which
    the removed hosting-based ``CheckIsOwnCaseActorNode`` made the real
    authority fail its own test and fall through to the participant arm, where
    it would have validated the hash chain of a log it owns (ADR-0088).

    The two arms are ``CheckIsCaseManagerNode`` and its ``Inverter``, so this
    also pins CM-02-011: the split gates on the role, not on hosting.
    """
    entry = _make_entry(0)
    event = _make_event(entry, actor_id=OWNER_ACTOR_ID)

    result = owner_bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
    # Verify no CaseActor Service was involved
    services = list(owner_bridge.datalayer.list_objects("Service"))
    assert not any(getattr(s, "context", None) == CASE_ID for s in services)


@pytest.mark.spec("SYNC-02-001")
@pytest.mark.spec("SYNC-12-002")
def test_participant_persists_valid_entry(
    bridge, datalayer, case_actor, case_obj
):
    entry = _make_entry(0, case_obj.genesis_hash)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )

    assert result.status == Status.SUCCESS
    assert datalayer.read(entry.id_) is not None


@pytest.mark.spec("SYNC-13-005")
@pytest.mark.spec("SYNC-12-003")
def test_case_actor_round_trip_logs_delivery_without_repersisting(
    bridge, datalayer, case_actor
):
    entry = _make_entry(0)
    datalayer.save(entry)
    event = _make_event(entry, actor_id=case_actor.id_)

    # Runs as the replica holder whose store this is.  Neither this test nor
    # the spoofed-sender one below is about *which* participant receives the
    # announcement — they are about not re-persisting a known entry and about
    # rejecting an unauthorised author — so the receiver is the participant,
    # matching every other tree in this file.
    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
    entries = list(datalayer.list_objects("CaseLedgerEntry"))
    assert len(entries) == 1


CASE_ACTOR_ACTOR_ID = "https://example.org/actors/case-actor"


def _seed_case_manager(datalayer, case_obj) -> None:
    """Register the case's CaseActor as a CVDRole.CASE_MANAGER participant.

    Authority is the role (ADR-0088), resolved by resolve_case_manager_id, not a
    Service object — so VerifySenderIsCaseActorNode resolves the CaseActor from
    the participant's ``attributed_to`` (``CASE_ACTOR_ACTOR_ID``), the id the
    legitimate announces are sent from.
    """
    manager = CaseParticipant(
        id_=f"{CASE_ID}/participants/case-manager",
        attributed_to=CASE_ACTOR_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    datalayer.create(manager)
    case_obj.actor_participant_index[CASE_ACTOR_ACTOR_ID] = manager.id_
    case_obj.case_participants.append(manager.id_)
    datalayer.save(case_obj)


@pytest.mark.spec("CLP-01-003")
@pytest.mark.spec("SYNC-13-006")
def test_case_actor_spoofed_sender_fails(bridge, datalayer, case_obj):
    # Discriminating spoof test: the case IS seeded with its CASE_MANAGER
    # (so the CaseActor resolves) and the entry is chain-consistent
    # (prev_log_hash == genesis), so both the missing-case path and the
    # hash-chain check would otherwise ACCEPT and persist this entry. The only
    # reason to reject is that the sender is not the CaseActor — exactly what
    # VerifySenderIsCaseActorNode must catch (CLP-01-003). Verified elsewhere:
    # with that node removed this entry persists.
    _seed_case_manager(datalayer, case_obj)
    entry = _make_entry(0, case_obj.genesis_hash)
    event = _make_event(
        entry, actor_id="https://example.org/actors/attacker-service"
    )

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )

    assert result.status == Status.FAILURE
    assert datalayer.read(entry.id_) is None


@pytest.mark.spec("CLP-01-003")
def test_case_actor_legit_sender_accepted(bridge, datalayer, case_obj):
    """The CASE_MANAGER's own announce passes the participant sender gate."""
    _seed_case_manager(datalayer, case_obj)
    entry = _make_entry(0, case_obj.genesis_hash)
    event = _make_event(entry, actor_id=CASE_ACTOR_ACTOR_ID)

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )

    assert result.status == Status.SUCCESS
    assert datalayer.read(entry.id_) is not None


@pytest.mark.spec("SYNC-03-001")
@pytest.mark.spec("SYNC-08-005")
def test_hash_mismatch_sends_reject_and_does_not_store(
    bridge, datalayer, case_actor
):
    first_entry = _make_entry(0)
    datalayer.save(first_entry)
    bad_entry = _make_entry(1, "badbadbadbadbad0" * 4)
    event = _make_event(bad_entry, actor_id=case_actor.id_)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    assert datalayer.read(bad_entry.id_) is None
    sync_port.send_reject_log_entry.assert_called_once()
    # The refused chain check leaves the archive of what arrived, and only
    # that: the inlined entry is not stored (CLP-10-017, CLP-10-018).
    assert _archived(datalayer, event)


def _make_remove_embargo_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            event_type="remove_embargo_event_from_case",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev_hash,
        )
    )


ACTIVE_EMBARGO_ID = f"{CASE_ID}/embargo_events/active"


def _make_case_with_em_active(
    datalayer: SqliteDataLayer,
) -> VulnerabilityCase:
    case = VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
    )
    activate(case, ACTIVE_EMBARGO_ID)
    datalayer.create(case)
    return case


class TestAnnounceLogEntryAppliesEmbargoTeardown:
    """Participant receiving remove_embargo log entry must reach EM.EXITED."""

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_participant_reaches_em_exited_on_remove_embargo_entry(
        self, bridge, datalayer, case_actor
    ):
        """BT applies EM.EXITED when entry has remove_embargo_event_from_case."""
        case = _make_case_with_em_active(datalayer)
        entry = _make_remove_embargo_entry(0, case.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert updated.current_status.em.state == EM.EXITED

    @pytest.mark.spec("SYNC-12-003")
    def test_already_stored_entry_early_exits_successfully(
        self, bridge, datalayer, case_actor
    ):
        """Already-stored entry exits early without re-applying effects (SYNC-12-003)."""
        case = VulnerabilityCase(
            id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
        )
        # effect already applied
        activate(case, ACTIVE_EMBARGO_ID)
        terminate(case)
        datalayer.create(case)
        entry = _make_remove_embargo_entry(0)
        datalayer.save(
            entry
        )  # pre-store to trigger CheckLogEntryAlreadyStored
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(tree, "ApplyEmbargoTeardownFromLedger")
        assert apply_node is not None
        call_count = 0
        real_update = apply_node.update

        def tracking_update() -> Status:
            nonlocal call_count
            call_count += 1
            return cast(Status, real_update())

        apply_node.update = tracking_update  # type: ignore[method-assign]

        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        assert call_count == 0, (
            "ApplyEmbargoTeardown must NOT run on already-stored entry"
        )

    @pytest.mark.spec("SYNC-12-003")
    def test_em_exited_is_idempotent(self, bridge, datalayer, case_actor):
        """Running BT when case is already EM.EXITED must succeed silently."""
        case = VulnerabilityCase(
            id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
        )
        activate(case, ACTIVE_EMBARGO_ID)
        terminate(case)
        datalayer.create(case)
        entry = _make_remove_embargo_entry(0, case.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert updated.current_status.em.state == EM.EXITED


NOTE_ID = "https://example.org/notes/test-note-1"


def _make_relayed_invite_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    """Entry the CASE_MANAGER commits for a relayed ``Invite(EmbargoEvent)``.

    The relayed Invite carries the manager's RSVP deadline as ``endTime``
    (CM-28-012); the replica apply node records it on the invitee (CM-28-013).
    """
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/invite-{log_index}",
            event_type="invite_to_embargo_on_case",
            payload_snapshot={
                "type": "Invite",
                "id": f"https://example.org/activities/invite-{log_index}",
                "actor": CASE_ACTOR_ACTOR_ID,
                "attributedTo": OWNER_ACTOR_ID,
                "to": [PARTICIPANT_ACTOR_ID],
                "context": CASE_ID,
                "published": "2026-09-30T12:00:00+00:00",
                "endTime": "2026-10-07T12:00:00+00:00",
                "object": {
                    "type": "EmbargoEvent",
                    "id": f"{CASE_ID}/embargo_events/e1",
                    "context": CASE_ID,
                    "endTime": "2026-11-14T12:00:00+00:00",
                },
            },
            prev_log_hash=prev_hash,
        )
    )


def _make_invite_expired_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    """Entry the CASE_MANAGER commits when an invitation expires (CM-28-009)."""
    invite_id = f"https://example.org/activities/invite-{log_index}"
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=invite_id,
            event_type=INVITE_EXPIRED_EVENT_TYPE,
            payload_snapshot={
                "type": INVITE_EXPIRED_SNAPSHOT_TYPE,
                "actor": PARTICIPANT_ACTOR_ID,
                "context": CASE_ID,
                "published": "2026-10-08T12:00:00+00:00",
                "object": {
                    "type": "Invite",
                    "id": invite_id,
                    "object": {
                        "type": "EmbargoEvent",
                        "id": f"{CASE_ID}/embargo_events/e1",
                    },
                },
            },
            prev_log_hash=prev_hash,
        )
    )


_ENTRY_EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"


def _seed_invited_participant(
    datalayer, case_obj, consent: EmbargoConsentState | None
) -> str:
    """Give the replica a participant record for this store's actor.

    The embargo the ledger entries name is an open proposal, as the replica
    holds it once the proposal's entry has replayed.  *consent* is the state of
    the participant's row for it, or ``None`` for a participant never asked
    about it (``UNINVITED``, ADR-0122).
    """
    propose(case_obj, _ENTRY_EMBARGO_ID)
    participant = CaseParticipant(
        attributed_to=PARTICIPANT_ACTOR_ID,
        context=CASE_ID,
        embargo_consents=(
            []
            if consent is None
            else [EmbargoConsent(embargo_id=_ENTRY_EMBARGO_ID, state=consent)]
        ),
    )
    case_obj.add_participant(participant)
    datalayer.create(participant)
    datalayer.save(case_obj)
    write_consent_rows(datalayer, case_obj)
    return participant.id_


class TestAnnounceLogEntryAppliesEmbargoInviteRelay:
    """Replicas learn the RSVP deadline and an expiry from the ledger, never
    by computing either themselves (CM-28-013, CM-28-014; ADR-0113)."""

    @pytest.mark.spec("CM-28-013")
    @pytest.mark.spec("EP-09-007")
    def test_replica_records_invitee_deadline_from_relayed_invite_entry(
        self, bridge, datalayer, case_obj
    ):
        """The invitee's deadline appears in the replica after replay."""
        _seed_case_manager(datalayer, case_obj)
        participant_id = _seed_invited_participant(datalayer, case_obj, None)
        entry = _make_relayed_invite_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=CASE_ACTOR_ACTOR_ID)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(participant_id)
        assert isinstance(updated, CaseParticipant)
        assert updated.rsvp_deadline_for(_ENTRY_EMBARGO_ID) is not None
        assert (
            updated.consent_for(_ENTRY_EMBARGO_ID)
            is EmbargoConsentState.INVITED
        )

    @pytest.mark.spec("CM-28-014")
    def test_replica_reads_expired_from_expiry_entry(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """A replica learns an expiry from the entry and never computes one."""
        participant_id = _seed_invited_participant(
            datalayer, case_obj, EmbargoConsentState.INVITED
        )
        entry = _make_invite_expired_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(participant_id)
        assert isinstance(updated, CaseParticipant)
        assert (
            updated.consent_for(_ENTRY_EMBARGO_ID)
            is EmbargoConsentState.TIMED_OUT
        )


def _make_add_note_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    """Create a ledger entry with event_type='add_note_to_case'."""
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/add-note-{log_index}",
            event_type="add_note_to_case",
            payload_snapshot={"object": NOTE_ID},
            prev_log_hash=prev_hash,
        )
    )


class TestAnnounceLogEntryAppliesNoteAttachment:
    """Participant receiving add_note_to_case ledger entry attaches note."""

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-02-001")
    def test_participant_attaches_note_on_add_note_entry(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """BT attaches note ID to case replica when entry is add_note_to_case.

        A non-CaseActor participant must learn about note additions exclusively
        via Announce(as_CaseLedgerEntry) fan-out (SYNC-02-002, ADR-0022).
        """
        entry = _make_add_note_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert NOTE_ID in updated.notes

    @pytest.mark.spec("SYNC-12-003")
    def test_note_attachment_is_idempotent(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """Running BT twice with same note entry attaches note exactly once."""
        case_obj.notes.append(NOTE_ID)
        datalayer.save(case_obj)

        entry = _make_add_note_entry(0, case_obj.genesis_hash)
        # Pre-store entry so second run takes the already-stored path.
        datalayer.save(entry)
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert updated.notes.count(NOTE_ID) == 1

    def test_note_not_attached_for_non_note_entry(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """NoteEffects Selector short-circuits for unrelated event types."""
        entry = _make_entry(
            0, case_obj.genesis_hash
        )  # event_type="test_event"
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert updated.notes == []


class TestAnnounceLogEntryAppliesNoteRemoval:
    """A replica receiving remove_note_from_case detaches the note (RSH-08-004)."""

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("RSH-08-004")
    def test_participant_detaches_note_on_remove_note_entry(
        self, bridge, datalayer, case_actor, case_obj
    ):
        case_obj.notes.append(NOTE_ID)
        datalayer.save(case_obj)
        entry = _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=CASE_ID,
                log_index=0,
                object_id="https://example.org/activities/remove-note-0",
                event_type="remove_note_from_case",
                payload_snapshot={"object": NOTE_ID},
                prev_log_hash=case_obj.genesis_hash,
            )
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert NOTE_ID not in updated.notes


class TestAnnounceLogEntryAppliesReportAddition:
    """A replica receiving add_report_to_case lists the report (RSH-08-004)."""

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("RSH-08-004")
    def test_participant_lists_report_on_add_report_entry(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """An entry with no offer still converges the report list."""
        report_id = "https://example.org/reports/added-later"
        entry = _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=CASE_ID,
                log_index=0,
                object_id="https://example.org/activities/add-report-0",
                event_type="add_report_to_case",
                payload_snapshot={"object": report_id},
                prev_log_hash=case_obj.genesis_hash,
            )
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert list(updated.vulnerability_reports) == [report_id]


PARTICIPANT_STATUS_ID = "https://example.org/statuses/status-1"
PARTICIPANT_ID = "https://example.org/participants/reporter-participant"


def _make_participant_status_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    """Create a ledger entry with event_type='add_participant_status_to_participant'."""
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/status-{log_index}",
            event_type="add_participant_status_to_participant",
            payload_snapshot={
                "object": {
                    "id": PARTICIPANT_STATUS_ID,
                    "type": "ParticipantStatus",
                    "name": "test_status",
                    "context": CASE_ID,
                },
                "target": PARTICIPANT_ID,
            },
            prev_log_hash=prev_hash,
        )
    )


class TestAnnounceLogEntryAppliesParticipantStatus:
    """Participant receiving add_participant_status_to_participant ledger entry updates participant."""

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_participant_status_applied_on_matching_entry(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """BT applies participant status when entry has add_participant_status_to_participant."""
        from vultron.core.models.case_participant import CaseParticipant

        participant = CaseParticipant(
            id_=PARTICIPANT_ID,
            attributed_to=PARTICIPANT_ACTOR_ID,
            context=CASE_ID,
        )
        datalayer.create(participant)

        entry = _make_participant_status_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(PARTICIPANT_ID)
        assert updated is not None
        status_ids = [
            getattr(s, "id_", s) for s in updated.participant_statuses
        ]
        assert PARTICIPANT_STATUS_ID in status_ids

    def test_participant_status_not_applied_for_other_event_types(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """ParticipantStatusEffects Selector short-circuits for unrelated event types."""
        entry = _make_entry(
            0, case_obj.genesis_hash
        )  # event_type="test_event"
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS


INVITEE_ACTOR_ID = "https://example.org/actors/vendor2"
INVITEE_RECORD_ID = f"{CASE_ID}/participants/vendor2"
_CREATED_AT = datetime(2026, 10, 9, 12, 0, 0, tzinfo=UTC)
_JOINED_AT = datetime(2026, 10, 9, 13, 0, 0, tzinfo=UTC)


def _invitee_record(*, joined: bool = False) -> CaseParticipant:
    """The inert record as the CASE_MANAGER stored it, ids and times fixed."""
    status = ParticipantStatus(
        id_=f"{CASE_ID}/statuses/birth",
        context=CASE_ID,
        attributed_to=INVITEE_ACTOR_ID,
        rm=RmDimension(state=RM.RECEIVED),
        vf=VfDimension(state=CS_vf.vf),
        cvd_role=[CVDRole.VENDOR],
        published=_CREATED_AT,
        updated=_CREATED_AT,
    )
    record = CaseParticipant(
        id_=INVITEE_RECORD_ID,
        attributed_to=INVITEE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[status],
        joined=joined,
        published=_CREATED_AT,
        updated=_JOINED_AT if joined else _CREATED_AT,
    )
    record.embargo_consents = [
        EmbargoConsent(
            embargo_id=ACTIVE_EMBARGO_ID,
            state=(
                EmbargoConsentState.AGREED
                if joined
                else EmbargoConsentState.INVITED
            ),
        )
    ]
    return record


def _participant_entry(
    event_type: str,
    record: CaseParticipant,
    log_index: int,
    prev_hash: str = _ZERO_HASH,
) -> CaseLedgerEntry:
    """A ledger entry that carries *record*, rendered as the CASE_MANAGER does."""
    port = As2WireRenderAdapter()
    if event_type == CREATE_CASE_PARTICIPANT_EVENT_TYPE:
        snapshot = build_create_case_participant_snapshot(
            record, "https://example.org/actors/manager", CASE_ID, port
        )
    else:
        snapshot = build_update_case_participant_snapshot(
            record,
            "https://example.org/actors/manager",
            CASE_ID,
            f"urn:uuid:update-{log_index}",
            port,
        )
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"urn:uuid:participant-entry-{log_index}",
            event_type=event_type,
            payload_snapshot=snapshot,
            prev_log_hash=prev_hash,
        )
    )


class TestAnnounceLogEntryAppliesParticipantRecord:
    """A replica stores the participant record the CASE_MANAGER's entries carry."""

    def _announce(self, bridge, case_actor, entry):
        return bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=_make_event(entry, actor_id=case_actor.id_),
            sync_port=MagicMock(spec=SyncActivityPort),
        )

    def _held(self, datalayer) -> CaseParticipant:
        case = datalayer.read(CASE_ID)
        record = datalayer.read(case.actor_participant_index[INVITEE_ACTOR_ID])
        assert isinstance(record, CaseParticipant)
        return record

    @pytest.mark.spec("CM-11-006")
    @pytest.mark.spec("SYNC-12-001")
    def test_create_entry_stores_the_record_exactly_as_carried(
        self, bridge, datalayer, case_actor, case_obj
    ):
        sent = _invitee_record()
        entry = _participant_entry(
            CREATE_CASE_PARTICIPANT_EVENT_TYPE, sent, 0, case_obj.genesis_hash
        )

        assert (
            self._announce(bridge, case_actor, entry).status == Status.SUCCESS
        )

        held = self._held(datalayer)
        assert held.model_dump(mode="json") == sent.model_dump(mode="json")
        case = datalayer.read(CASE_ID)
        assert INVITEE_RECORD_ID in {str(p) for p in case.case_participants}

    @pytest.mark.spec("CM-31-012")
    def test_update_entry_copies_joined_and_consent_as_carried(
        self, bridge, datalayer, case_actor, case_obj
    ):
        create = _participant_entry(
            CREATE_CASE_PARTICIPANT_EVENT_TYPE,
            _invitee_record(),
            0,
            case_obj.genesis_hash,
        )
        joined = _invitee_record(joined=True)
        update = _participant_entry(
            UPDATE_CASE_PARTICIPANT_EVENT_TYPE, joined, 1, create.entry_hash
        )

        assert self._announce(bridge, case_actor, create).status == (
            Status.SUCCESS
        )
        assert self._announce(bridge, case_actor, update).status == (
            Status.SUCCESS
        )

        held = self._held(datalayer)
        assert held.model_dump(mode="json") == joined.model_dump(mode="json")

    @pytest.mark.spec("CM-31-012")
    def test_update_entry_with_no_record_fails_and_stores_nothing(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """No record held: a broken invariant, so the entry is refused."""
        update = _participant_entry(
            UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
            _invitee_record(joined=True),
            0,
            case_obj.genesis_hash,
        )

        result = self._announce(bridge, case_actor, update)

        assert result.status == Status.FAILURE
        assert INVITEE_ACTOR_ID not in (
            datalayer.read(CASE_ID).actor_participant_index
        )
        assert datalayer.read(update.id_) is None

    @pytest.mark.spec("SYNC-12-003")
    def test_the_same_entries_applied_again_leave_one_identical_record(
        self, bridge, datalayer, case_actor, case_obj
    ):
        create = _participant_entry(
            CREATE_CASE_PARTICIPANT_EVENT_TYPE,
            _invitee_record(),
            0,
            case_obj.genesis_hash,
        )
        update = _participant_entry(
            UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
            _invitee_record(joined=True),
            1,
            create.entry_hash,
        )
        for entry in (create, update):
            assert self._announce(bridge, case_actor, entry).status == (
                Status.SUCCESS
            )
        once = self._held(datalayer).model_dump(mode="json")

        # A replay of the stream: the entries are stored, so each exits early
        # (CheckLedgerEntryAlreadyStored); applying them again by hand is the
        # same.
        for entry in (create, update):
            assert self._announce(bridge, case_actor, entry).status == (
                Status.SUCCESS
            )

        case = datalayer.read(CASE_ID)
        assert list(case.actor_participant_index).count(INVITEE_ACTOR_ID) == 1
        assert self._held(datalayer).model_dump(mode="json") == once

    @pytest.mark.spec("SYNC-12-003")
    def test_create_entry_for_a_record_already_held_changes_nothing(
        self, bridge, datalayer, case_actor, case_obj
    ):
        held = _invitee_record(joined=True)
        datalayer.create(held)
        case_obj.add_participant(held)
        datalayer.save(case_obj)
        before = held.model_dump(mode="json")
        entry = _participant_entry(
            CREATE_CASE_PARTICIPANT_EVENT_TYPE,
            _invitee_record(),
            0,
            case_obj.genesis_hash,
        )

        assert (
            self._announce(bridge, case_actor, entry).status == Status.SUCCESS
        )

        assert self._held(datalayer).model_dump(mode="json") == before

    @pytest.mark.spec("SYNC-15-002")
    @pytest.mark.spec("CM-31-012")
    def test_a_stale_update_replayed_over_a_seed_that_is_ahead_changes_nothing(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """A late joiner is seeded, then replays the ledger from genesis.

        The seed already holds the record at a later state than an old
        ``update_case_participant`` entry describes, so applying the old entry
        must not move it backwards: ``joined`` stays set and a row the entry
        does not mention stays.
        """
        ahead = _invitee_record(joined=True)
        later = f"{CASE_ID}/embargo_events/later"
        ahead.embargo_consents = [
            *ahead.embargo_consents,
            EmbargoConsent(embargo_id=later, state=EmbargoConsentState.AGREED),
        ]
        datalayer.create(ahead)
        case_obj.add_participant(ahead)
        datalayer.save(case_obj)
        before = ahead.model_dump(mode="json")
        stale = _invitee_record()  # joined=False, one INVITED row
        entry = _participant_entry(
            UPDATE_CASE_PARTICIPANT_EVENT_TYPE, stale, 0, case_obj.genesis_hash
        )

        assert (
            self._announce(bridge, case_actor, entry).status == Status.SUCCESS
        )

        assert self._held(datalayer).model_dump(mode="json") == before

    @pytest.mark.spec("CM-18-003")
    def test_an_update_applies_a_legal_consent_move_and_a_new_row(
        self, bridge, datalayer, case_actor, case_obj
    ):
        held = _invitee_record()
        later = f"{CASE_ID}/embargo_events/later"
        datalayer.create(held)
        case_obj.add_participant(held)
        datalayer.save(case_obj)
        carried = _invitee_record(joined=True)  # INVITED -> AGREED on the one
        carried.embargo_consents = [
            *carried.embargo_consents,
            EmbargoConsent(
                embargo_id=later, state=EmbargoConsentState.INVITED
            ),
        ]
        entry = _participant_entry(
            UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
            carried,
            0,
            case_obj.genesis_hash,
        )

        assert (
            self._announce(bridge, case_actor, entry).status == Status.SUCCESS
        )

        after = self._held(datalayer)
        assert after.joined is True
        assert after.consent_for(ACTIVE_EMBARGO_ID) == (
            EmbargoConsentState.AGREED
        )
        assert after.consent_for(later) == EmbargoConsentState.INVITED

    def test_participant_slots_do_not_apply_to_other_event_types(
        self, bridge, datalayer, case_actor, case_obj
    ):
        entry = _make_entry(
            0, case_obj.genesis_hash
        )  # event_type="test_event"

        assert (
            self._announce(bridge, case_actor, entry).status == Status.SUCCESS
        )
        assert INVITEE_ACTOR_ID not in (
            datalayer.read(CASE_ID).actor_participant_index
        )


def _find_node_by_name(
    root: py_trees.behaviour.Behaviour, name: str
) -> py_trees.behaviour.Behaviour | None:
    """Depth-first search for a node by its .name attribute."""
    if root.name == name:
        return root
    for child in getattr(root, "children", []):
        found = _find_node_by_name(child, name)
        if found is not None:
            return found
    return None


class TestEffectsFailureBlocksPersist:
    """Apply* FAILURE must prevent PersistReceivedLogEntry from running (SYNC-12-001)."""

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_apply_embargo_failure_blocks_persist(
        self, bridge, datalayer, case_actor
    ):
        """PersistReceivedLogEntry must NOT run when ApplyEmbargoTeardown returns FAILURE."""
        case = _make_case_with_em_active(datalayer)
        entry = _make_remove_embargo_entry(0, case.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(tree, "ApplyEmbargoTeardownFromLedger")
        assert apply_node is not None
        apply_node.update = lambda: Status.FAILURE  # type: ignore[method-assign]

        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.FAILURE
        assert datalayer.read(entry.id_) is None

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_apply_participant_status_failure_blocks_persist(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """PersistReceivedLogEntry must NOT run when ApplyParticipantStatusFromLedger returns FAILURE."""
        entry = _make_participant_status_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(
            tree, "ApplyParticipantStatusFromLedger"
        )
        assert apply_node is not None
        apply_node.update = lambda: Status.FAILURE  # type: ignore[method-assign]

        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.FAILURE
        assert datalayer.read(entry.id_) is None

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_apply_note_failure_blocks_persist(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """PersistReceivedLogEntry must NOT run when ApplyNoteFromLedger returns FAILURE."""
        entry = _make_add_note_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(tree, "ApplyNoteFromLedger")
        assert apply_node is not None
        apply_node.update = lambda: Status.FAILURE  # type: ignore[method-assign]

        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.FAILURE
        assert datalayer.read(entry.id_) is None

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_apply_update_case_participant_failure_blocks_persist(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """PersistReceivedLogEntry must NOT run when the update apply FAILS."""
        entry = _participant_entry(
            UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
            _invitee_record(joined=True),
            0,
            case_obj.genesis_hash,
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(
            tree, "ApplyUpdateCaseParticipantFromLedger"
        )
        assert apply_node is not None
        apply_node.update = lambda: Status.FAILURE  # type: ignore[method-assign]

        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.FAILURE
        assert datalayer.read(entry.id_) is None

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_apply_close_case_failure_blocks_persist(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """PersistReceivedLogEntry must NOT run when ApplyCloseCaseFromLedger returns FAILURE."""
        entry = _make_close_case_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(tree, "ApplyCloseCaseFromLedger")
        assert apply_node is not None
        apply_node.update = lambda: Status.FAILURE  # type: ignore[method-assign]

        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.FAILURE
        assert datalayer.read(entry.id_) is None


# ---------------------------------------------------------------------------
# Announce tree applies close_case ledger entry (CloseCaseEffects slot)
# ---------------------------------------------------------------------------

DEPARTING_ACTOR_ID = "https://example.org/actors/departing"
DEPARTING_PARTICIPANT_ID = "https://example.org/participants/departing"


def _make_close_case_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    """Build a close_case ledger entry with payload_snapshot carrying actor."""
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/leave-{log_index}",
            event_type="close_case",
            payload_snapshot={"actor": DEPARTING_ACTOR_ID},
            prev_log_hash=prev_hash,
        )
    )


def _make_case_with_departing_participant(
    datalayer: SqliteDataLayer,
) -> VulnerabilityCase:
    """Seed CASE_ID with a departing participant so the apply node can find them."""
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    participant = CaseParticipant(
        id_=DEPARTING_PARTICIPANT_ID,
        attributed_to=DEPARTING_ACTOR_ID,
        context=CASE_ID,
    )
    datalayer.create(participant)
    case.actor_participant_index[DEPARTING_ACTOR_ID] = DEPARTING_PARTICIPANT_ID
    datalayer.save(case)
    return case


class TestAnnounceLogEntryAppliesCloseCase:
    """Participant receiving close_case ledger entry must advance departing actor to RM.CLOSED."""

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_participant_advances_departing_actor_to_rm_closed(
        self, bridge, datalayer, case_actor
    ):
        """BT advances the departing actor to RM.CLOSED on close_case entry (CM-23-003, CM-23-004)."""
        case_obj = _make_case_with_departing_participant(datalayer)
        entry = _make_close_case_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(DEPARTING_PARTICIPANT_ID)
        assert updated is not None
        rm_states = [
            ps.rm.state
            for ps in updated.participant_statuses
            if hasattr(ps, "rm") and ps.rm is not None
        ]
        assert RM.CLOSED in rm_states, (
            f"Departing actor must reach RM.CLOSED after close_case announce;"
            f" rm_states={rm_states}"
        )

    def test_close_case_not_applied_for_other_event_types(
        self, bridge, datalayer, case_actor
    ):
        """CloseCaseEffects Selector short-circuits for unrelated event_types."""
        # Use the helper's case, not the ``case_obj`` fixture: the helper saves
        # a fresh case over the same id, and ``genesis_hash`` is derived from
        # the second-resolution ``published`` stamp, so the fixture's hash is
        # stale whenever the two constructions straddle a second boundary.
        case_obj = _make_case_with_departing_participant(datalayer)
        entry = _make_entry(
            0, case_obj.genesis_hash
        )  # event_type="test_event"
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(DEPARTING_PARTICIPANT_ID)
        assert updated is not None
        rm_states = [
            ps.rm.state
            for ps in updated.participant_statuses
            if hasattr(ps, "rm") and ps.rm is not None
        ]
        assert RM.CLOSED not in rm_states, (
            f"Non-close-case entry must NOT advance departing actor to RM.CLOSED;"
            f" rm_states={rm_states}"
        )

    @pytest.mark.spec("SYNC-12-003")
    def test_close_case_apply_is_idempotent(self, datalayer):
        """ApplyCloseCaseFromLedgerNode called twice must not create duplicate RM.CLOSED entries.

        Calls the apply node directly (bypassing CheckLogEntryAlreadyStored)
        so we verify the node's own idempotency guard, not the tree-level guard.
        """
        from vultron.core.behaviors.case.nodes.leave import (
            AdvanceParticipantToRMClosedNode,
        )

        _make_case_with_departing_participant(datalayer)

        def _run_advance() -> None:
            node = AdvanceParticipantToRMClosedNode(
                leaving_actor_id=DEPARTING_ACTOR_ID,
                case_id=CASE_ID,
            )
            node.datalayer = datalayer
            node.setup()
            node.update()

        _run_advance()
        _run_advance()

        updated = datalayer.read(DEPARTING_PARTICIPANT_ID)
        assert updated is not None
        closed_count = sum(
            1
            for ps in updated.participant_statuses
            if hasattr(ps, "rm")
            and ps.rm is not None
            and ps.rm.state == RM.CLOSED
        )
        assert closed_count == 1, (
            f"Expected exactly 1 RM.CLOSED ParticipantStatus;"
            f" found {closed_count}"
        )


NEW_OWNER_ID = "https://example.org/actors/new-owner"


def _make_ownership_transfer_entry(
    log_index: int, new_owner_id: str, prev_hash: str = _ZERO_HASH
) -> CaseLedgerEntry:
    """Create a ledger entry with event_type='accept_case_ownership_transfer'."""
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/ownership-{log_index}",
            event_type="accept_case_ownership_transfer",
            payload_snapshot={"actor": new_owner_id},
            prev_log_hash=prev_hash,
        )
    )


class TestAnnounceLogEntryAppliesOwnershipTransfer:
    """Participant receiving accept_case_ownership_transfer entry updates attributed_to."""

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-12-002")
    def test_participant_updates_attributed_to_on_ownership_transfer(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """BT updates attributed_to on case replica when entry is accept_case_ownership_transfer."""
        entry = _make_ownership_transfer_entry(
            0, NEW_OWNER_ID, case_obj.genesis_hash
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert updated.attributed_to == NEW_OWNER_ID

    @pytest.mark.spec("SYNC-12-003")
    def test_ownership_transfer_is_idempotent(
        self, bridge, datalayer, case_actor
    ):
        """Running BT when case already has correct owner must succeed silently."""
        case = VulnerabilityCase(id_=CASE_ID, attributed_to=NEW_OWNER_ID)
        datalayer.save(case)
        entry = _make_ownership_transfer_entry(
            0, NEW_OWNER_ID, case.genesis_hash
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert updated.attributed_to == NEW_OWNER_ID

    def test_ownership_transfer_not_applied_for_unrelated_event(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """OwnershipTransferEffects Selector short-circuits for unrelated event types."""
        entry = _make_entry(
            0, case_obj.genesis_hash
        )  # event_type="test_event"
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.SUCCESS
        updated = datalayer.read(CASE_ID)
        assert updated is not None
        assert updated.attributed_to == OWNER_ACTOR_ID


# ---------------------------------------------------------------------------
# RSH-05-021: Selector(ApplyOrFault) — fault emission and persist blocking
# ---------------------------------------------------------------------------


def _make_participant_status_entry_with_states(
    log_index: int,
    prev_hash: str,
    status_id: str,
    participant_id: str,
    rm_state: str,
    vf_state: str,
) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/status-{log_index}",
            event_type="add_participant_status_to_participant",
            payload_snapshot={
                "object": {
                    "id": status_id,
                    "type": "ParticipantStatus",
                    "rmState": rm_state,
                    "vfState": vf_state,
                    "context": CASE_ID,
                },
                "target": {"id": participant_id},
            },
            prev_log_hash=prev_hash,
        )
    )


class TestAnnounceTreeEmitImpossibleStateFault:
    """Full-tree tests: Selector(ApplyOrFault) emits fault and blocks persist.

    Covers RSH-05-021 (impossible composite state) and ARCH-15-001
    (malformed local participant record) end-to-end through
    ``create_announce_log_entry_tree()``.
    """

    @pytest.mark.spec("RSH-05-021")
    @pytest.mark.spec("SYNC-12-001")
    def test_impossible_composite_state_emits_fault_and_blocks_persist(
        self, datalayer, case_actor, case_obj
    ):
        """Full tree: rm=VALID+vf=VF violates RM↔VF entailment.

        EmitImpossibleStateFaultNode must fire (emit_processing_fault called
        with ImpossibleState class), and PersistReceivedLogEntry must NOT
        store the entry (RSH-05-021, SYNC-12-001).
        """
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.fault_classes import (
            VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE,
        )
        from vultron.core.ports.trigger_activity import TriggerActivityPort

        trigger_activity = MagicMock(spec=TriggerActivityPort)
        trigger_bridge = BTBridge(
            datalayer=datalayer, trigger_activity=trigger_activity
        )

        participant = CaseParticipant(
            id_=PARTICIPANT_ID,
            attributed_to=PARTICIPANT_ACTOR_ID,
            context=CASE_ID,
        )
        datalayer.create(participant)

        status_id = "https://example.org/statuses/impossible-rm-valid-vf"
        entry = _make_participant_status_entry_with_states(
            log_index=0,
            prev_hash=case_obj.genesis_hash,
            status_id=status_id,
            participant_id=PARTICIPANT_ID,
            rm_state="VALID",
            vf_state="VF",
        )
        event = _make_event(entry, actor_id=case_actor.id_)

        result = trigger_bridge.execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.FAILURE
        assert datalayer.read(entry.id_) is None, "entry must not be stored"
        trigger_activity.emit_processing_fault.assert_called_once()
        call_kwargs = trigger_activity.emit_processing_fault.call_args.kwargs
        assert (
            call_kwargs["failure_class"]
            == VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE
        )
        assert case_actor.id_ in call_kwargs["to"]

    @pytest.mark.spec("ARCH-15-001")
    @pytest.mark.spec("RSH-05-021")
    @pytest.mark.spec("SYNC-12-001")
    def test_malformed_local_record_emits_fault_and_blocks_persist(
        self, datalayer, case_actor, case_obj
    ):
        """Full tree: malformed local participant record → fault emitted, entry not stored.

        Simulates ARCH-15-001 by patching _apply_rm_ratchet to return None,
        representing a participant whose local status record is not core-shaped.
        EmitImpossibleStateFaultNode fires because it is the Selector fallback
        for ANY FAILURE from ApplyParticipantStatusFromLedgerNode.
        """
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.fault_classes import (
            VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_CORRUPT_LOCAL_RECORD,
        )
        from vultron.core.ports.trigger_activity import TriggerActivityPort

        trigger_activity = MagicMock(spec=TriggerActivityPort)
        trigger_bridge = BTBridge(
            datalayer=datalayer, trigger_activity=trigger_activity
        )

        participant = CaseParticipant(
            id_=PARTICIPANT_ID,
            attributed_to=PARTICIPANT_ACTOR_ID,
            context=CASE_ID,
        )
        datalayer.create(participant)

        entry = _make_participant_status_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(
            tree, "ApplyParticipantStatusFromLedger"
        )
        assert apply_node is not None
        # Simulate ARCH-15-001: replica's recorded status is not core-shaped.
        apply_node._apply_rm_ratchet = (  # type: ignore[method-assign]
            lambda *args, **kwargs: None
        )

        result = trigger_bridge.execute_with_setup(
            tree=tree,
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert result.status == Status.FAILURE
        assert datalayer.read(entry.id_) is None, "entry must not be stored"
        trigger_activity.emit_processing_fault.assert_called_once()
        call_kwargs = trigger_activity.emit_processing_fault.call_args.kwargs
        assert (
            call_kwargs["failure_class"]
            == VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_CORRUPT_LOCAL_RECORD
        )
