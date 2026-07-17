#!/usr/bin/env python
"""Integration tests for AnnounceLogEntryReceivedBT."""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.em import EM
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
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


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def datalayer():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def case_actor(datalayer):
    actor = VultronCaseActor(
        name="Case Actor",
        attributed_to=OWNER_ACTOR_ID,
        context=CASE_ID,
    )
    datalayer.create(actor)
    return actor


@pytest.fixture
def case_obj(datalayer):
    case = as_VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    datalayer.save(case)
    return case


def _make_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> VultronCaseLedgerEntry:
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
    entry: VultronCaseLedgerEntry, actor_id: str
) -> AnnounceLogEntryReceivedEvent:
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(entry=wire_entry, actor=actor_id)
    return cast(AnnounceLogEntryReceivedEvent, extract_event(activity))


def test_create_announce_log_entry_tree_returns_selector():
    tree = create_announce_log_entry_tree()
    assert tree.name == "AnnounceLogEntryReceivedBT"
    assert len(tree.children) == 2


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


def test_case_actor_round_trip_logs_delivery_without_repersisting(
    bridge, datalayer, case_actor
):
    entry = _make_entry(0)
    datalayer.save(entry)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
    entries = list(datalayer.list_objects("CaseLedgerEntry"))
    assert len(entries) == 1


def test_case_actor_spoofed_sender_fails(bridge, datalayer, case_actor):
    entry = _make_entry(0)
    event = _make_event(
        entry, actor_id="https://example.org/actors/attacker-service"
    )

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.FAILURE
    assert datalayer.read(entry.id_) is None


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


def _make_remove_embargo_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> VultronCaseLedgerEntry:
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


def _make_case_with_em_active(
    datalayer: SqliteDataLayer,
) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
    )
    case.current_status.em_state = EM.ACTIVE
    datalayer.create(case)
    return case


class TestAnnounceLogEntryAppliesEmbargoTeardown:
    """Participant receiving remove_embargo log entry must reach EM.EXITED."""

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
        assert updated.current_status.em_state == EM.EXITED

    def test_already_stored_entry_early_exits_successfully(
        self, bridge, datalayer, case_actor
    ):
        """Already-stored entry exits early without re-applying effects (SYNC-12-003)."""
        case = as_VulnerabilityCase(
            id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
        )
        case.current_status.em_state = EM.EXITED  # effect already applied
        datalayer.create(case)
        entry = _make_remove_embargo_entry(0)
        datalayer.save(
            entry
        )  # pre-store to trigger CheckLogEntryAlreadyStored
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(tree, "ApplyEmbargoTeardown")
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
        assert (
            call_count == 0
        ), "ApplyEmbargoTeardown must NOT run on already-stored entry"

    def test_em_exited_is_idempotent(self, bridge, datalayer, case_actor):
        """Running BT when case is already EM.EXITED must succeed silently."""
        case = as_VulnerabilityCase(
            id_=CASE_ID, name="Test Case", attributed_to=OWNER_ACTOR_ID
        )
        case.current_status.em_state = EM.EXITED
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
        assert updated.current_status.em_state == EM.EXITED


NOTE_ID = "https://example.org/notes/test-note-1"


def _make_add_note_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> VultronCaseLedgerEntry:
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


PARTICIPANT_STATUS_ID = "https://example.org/statuses/status-1"
PARTICIPANT_ID = "https://example.org/participants/reporter-participant"


def _make_participant_status_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> VultronCaseLedgerEntry:
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


def _make_accept_invite_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> VultronCaseLedgerEntry:
    """Create a ledger entry with event_type='accept_invite_actor_to_case'."""
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/accept-invite-{log_index}",
            event_type="accept_invite_actor_to_case",
            payload_snapshot={
                "type": "Accept",
                "actor": INVITEE_ACTOR_ID,
                "object": {
                    "type": "Invite",
                    "id": "https://example.org/invites/1",
                },
                "context": CASE_ID,
            },
            prev_log_hash=prev_hash,
        )
    )


class TestAnnounceLogEntryAppliesInviteAccept:
    """Participant receiving accept_invite_actor_to_case ledger entry adds invitee."""

    def test_participant_adds_invitee_on_accept_invite_entry(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """BT adds new participant to case replica when entry is accept_invite_actor_to_case.

        Existing participants (e.g. Finder) must learn about new invitees
        exclusively via Announce(as_CaseLedgerEntry) fan-out (SYNC-02-002).
        """
        entry = _make_accept_invite_entry(0, case_obj.genesis_hash)
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
        assert INVITEE_ACTOR_ID in updated.actor_participant_index

    def test_invite_accept_add_is_idempotent(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """Already-stored accept-invite entry exits early; pre-applied invitee unchanged."""
        # Pre-apply the effect (invitee already registered) to reflect first run.
        invitee_participant = CaseParticipant(
            id_=f"{CASE_ID}/participants/vendor2",
            attributed_to=INVITEE_ACTOR_ID,
            context=CASE_ID,
        )
        datalayer.create(invitee_participant)
        case_obj.add_participant(invitee_participant)
        datalayer.save(case_obj)
        entry = _make_accept_invite_entry(0, case_obj.genesis_hash)
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
        assert (
            list(updated.actor_participant_index.keys()).count(
                INVITEE_ACTOR_ID
            )
            == 1
        )

    def test_invite_accept_not_applied_for_other_event_types(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """InviteAcceptEffects Selector short-circuits for unrelated event types."""
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
        assert INVITEE_ACTOR_ID not in updated.actor_participant_index


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

    def test_apply_embargo_failure_blocks_persist(
        self, bridge, datalayer, case_actor
    ):
        """PersistReceivedLogEntry must NOT run when ApplyEmbargoTeardown returns FAILURE."""
        case = _make_case_with_em_active(datalayer)
        entry = _make_remove_embargo_entry(0, case.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(tree, "ApplyEmbargoTeardown")
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

    def test_apply_invite_accept_failure_blocks_persist(
        self, bridge, datalayer, case_actor, case_obj
    ):
        """PersistReceivedLogEntry must NOT run when ApplyInviteAcceptFromLedger returns FAILURE."""
        entry = _make_accept_invite_entry(0, case_obj.genesis_hash)
        event = _make_event(entry, actor_id=case_actor.id_)

        tree = create_announce_log_entry_tree()
        apply_node = _find_node_by_name(tree, "ApplyInviteAcceptFromLedger")
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
