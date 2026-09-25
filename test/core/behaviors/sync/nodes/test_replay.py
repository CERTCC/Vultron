#!/usr/bin/env python
"""Unit tests for sync replay and fan-out nodes."""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
)
from vultron.core.behaviors.sync.nodes import (
    CollectAndSortCaseLedgerEntriesNode,
    CollectLogEntryRecipientsNode,
    FanOutLogEntryNode,
    FindCaseActorNode,
    FindDivergenceIndexNode,
    ReplayMissingEntriesNode,
    SendLogEntryToEachNode,
    SendMissingEntriesNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import reject_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains


def _make_reject_event(
    *, tail_hash: str, entry_log_index: int = 1
) -> RejectLogEntryReceivedEvent:
    prev_hash = _ZERO_HASH if entry_log_index == 0 else "deadbeef" * 8
    entry = _make_entry(entry_log_index, prev_hash)
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = reject_log_entry_activity(
        entry=wire_entry,
        context=tail_hash,
        actor=PARTICIPANT_ACTOR_ID,
        to=[OWNER_ACTOR_ID],
    )
    return cast(RejectLogEntryReceivedEvent, extract_event(activity))


@pytest.fixture
def datalayer():
    """The owner's own store: replay runs as the owner (OWNER_ACTOR_ID).

    Shadows the package fixture, which is the participant's store.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER_ACTOR_ID)


@pytest.mark.spec("SYNC-03-002")
def test_replay_missing_entries_node_is_sequence_with_named_leaf_nodes():
    tree = ReplayMissingEntriesNode(name="ReplayMissingEntries")
    assert isinstance(tree, py_trees.composites.Sequence)
    assert len(tree.children) == 3
    assert isinstance(tree.children[0], CollectAndSortCaseLedgerEntriesNode)
    assert isinstance(tree.children[1], FindDivergenceIndexNode)
    assert isinstance(tree.children[2], SendMissingEntriesNode)


@pytest.mark.spec("SYNC-03-002")
def test_send_missing_entries_node_replays_entries_after_divergence(
    bridge, case_actor
):
    first_entry = _make_entry(0)
    second_entry = _make_entry(1, first_entry.entry_hash)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=SendMissingEntriesNode(name="SendMissingEntries"),
        actor_id=OWNER_ACTOR_ID,
        sync_port=sync_port,
        case_actor_id=case_actor.id_,
        replay_entry=second_entry,
        replay_peer_id=PARTICIPANT_ACTOR_ID,
        replay_case_ledger_entries=[first_entry, second_entry],
        replay_from_index=0,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_called_once()
    kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert kwargs["entry"].id_ == second_entry.id_
    assert kwargs["actor_id"] == case_actor.id_
    assert kwargs["to"] == [PARTICIPANT_ACTOR_ID]


#: A CASE_MANAGER that is deliberately *not* the store owner or the executing
#: actor.  When all three collapse onto one id, publishing ``self.actor_id``
#: instead of resolving the role passes every assertion here — verified by
#: mutation, 34 tests stayed green — so the role resolution ADR-0088 introduces
#: would be untested.
MANAGER_ACTOR_ID = "https://example.org/actors/the-case-manager"


def _seed_case_with_manager(datalayer, manager_actor_id: str) -> None:
    """Seed a case whose CASE_MANAGER is *manager_actor_id*."""
    participant = CaseParticipant(
        id_=f"{CASE_ID}/participants/manager",
        attributed_to=manager_actor_id,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    datalayer.create(participant)
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    case.add_participant(participant)
    datalayer.save(case)


class TestFindCaseActorNode:
    """``FindCaseActorNode`` resolves an *address* from the role (ADR-0088).

    It publishes ``case_actor_id`` for the downstream announce/replay nodes and
    ``case_id`` for the role gate in ``create_reject_log_entry_tree``.  It does
    not decide authority — that is the separate ``CheckIsCaseManagerNode`` in
    that tree (ARCH-24-005).
    """

    @pytest.mark.spec("ARCH-24-001")
    @pytest.mark.spec("CM-02-011")
    def test_resolves_the_case_manager_and_publishes_both_outputs(
        self, bridge, datalayer
    ):
        _seed_case_with_manager(datalayer, MANAGER_ACTOR_ID)
        event = _make_reject_event(tail_hash="")

        result = bridge.execute_with_setup(
            tree=FindCaseActorNode(name="FindCaseActor"),
            actor_id=OWNER_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS
        storage = py_trees.blackboard.Blackboard.storage
        assert storage.get("/case_actor_id") == MANAGER_ACTOR_ID
        # The role gate downstream reads this; without it the guard's selector
        # silently took its skip branch and the announce never fired.
        assert storage.get("/case_id") == CASE_ID

    @pytest.mark.spec("CM-02-012")
    def test_resolves_without_any_service_object_carrying_context(
        self, bridge, datalayer
    ):
        """The bootstrap window the retired ``Service`` scan could not answer in.

        ADR-0041 writes the CaseActor ``Service`` with no ``context``, so a
        ``context == case_id`` scan found nothing here and the node failed.
        """
        _seed_case_with_manager(datalayer, MANAGER_ACTOR_ID)
        datalayer.create(
            VultronCaseActor(id_=MANAGER_ACTOR_ID, name="CaseActor")
        )
        event = _make_reject_event(tail_hash="")

        result = bridge.execute_with_setup(
            tree=FindCaseActorNode(name="FindCaseActor"),
            actor_id=OWNER_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.SUCCESS
        assert (
            py_trees.blackboard.Blackboard.storage.get("/case_actor_id")
            == MANAGER_ACTOR_ID
        )

    @pytest.mark.spec("ARCH-24-004")
    def test_an_unrelated_service_object_is_not_borrowed_as_the_address(
        self, bridge, datalayer
    ):
        """The retired helper returned *the first arbitrary Service* on a miss.

        That fallback made a failed lookup indistinguishable from a successful
        one: the node reported SUCCESS and published a plausible-looking address
        belonging to some other case entirely.  With no CASE_MANAGER on the
        roster the honest answer is FAILURE.
        """
        datalayer.create(
            VultronCaseActor(
                id_="https://example.org/actors/some-other-case-actor",
                name="Unrelated CaseActor",
                context="https://example.org/cases/a-different-case",
            )
        )
        datalayer.save(
            VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
        )
        event = _make_reject_event(tail_hash="")

        result = bridge.execute_with_setup(
            tree=FindCaseActorNode(name="FindCaseActor"),
            actor_id=OWNER_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.FAILURE
        # The node has three FAILURE paths and a bare status assertion cannot
        # tell them apart: deleting the case seeding above still left this test
        # green, satisfied by the case-absent branch instead of the branch it
        # names.  `_require_case` sets a canonical feedback_message; the
        # no-CASE_MANAGER path does not, so its absence pins the right branch.
        assert "not found in DataLayer" not in result.feedback_message

    def test_fails_when_the_case_is_absent_from_this_store(
        self, bridge, datalayer
    ):
        """Regime 1 (ADR-0087): a peer asking us to replay a log we do not hold.

        Distinguished from the no-CASE_MANAGER failure by the canonical
        `_require_case` feedback message.
        """
        event = _make_reject_event(tail_hash="")

        result = bridge.execute_with_setup(
            tree=FindCaseActorNode(name="FindCaseActor"),
            actor_id=OWNER_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.FAILURE
        assert "not found in DataLayer" in result.feedback_message


@pytest.mark.spec("SYNC-03-002")
def test_collect_and_find_replay_context_writes_blackboard(bridge, datalayer):
    first_entry = _make_entry(0)
    second_entry = _make_entry(1, first_entry.entry_hash)
    datalayer.save(second_entry)
    datalayer.save(first_entry)
    event = _make_reject_event(tail_hash=first_entry.entry_hash)

    collect_result = bridge.execute_with_setup(
        tree=CollectAndSortCaseLedgerEntriesNode(
            name="CollectAndSortCaseLedgerEntries"
        ),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert collect_result.status == Status.SUCCESS
    replay_entries = py_trees.blackboard.Blackboard.storage.get(
        "/replay_case_ledger_entries"
    )
    assert replay_entries is not None
    assert [entry.log_index for entry in replay_entries] == [0, 1]
    assert (
        py_trees.blackboard.Blackboard.storage.get("/replay_peer_id")
        == PARTICIPANT_ACTOR_ID
    )

    find_result = bridge.execute_with_setup(
        tree=FindDivergenceIndexNode(name="FindDivergenceIndex"),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        replay_case_ledger_entries=replay_entries,
    )

    assert find_result.status == Status.SUCCESS
    assert (
        py_trees.blackboard.Blackboard.storage.get("/replay_from_index") == 0
    )


@pytest.mark.spec("SYNC-02-001")
@pytest.mark.spec("SYNC-02-003")
def test_fanout_log_entry_node_is_sequence_with_named_leaf_nodes():
    tree = FanOutLogEntryNode(case_id=CASE_ID, name="FanOutLogEntry")
    assert isinstance(tree, py_trees.composites.Sequence)
    assert len(tree.children) == 2
    assert isinstance(tree.children[0], CollectLogEntryRecipientsNode)
    assert isinstance(tree.children[1], SendLogEntryToEachNode)


@pytest.mark.spec("SYNC-03-002")
def test_replay_missing_entries_node_replays_from_divergence(
    bridge, datalayer, case_actor
):
    first_entry = _make_entry(0)
    second_entry = _make_entry(1, first_entry.entry_hash)
    datalayer.save(first_entry)
    datalayer.save(second_entry)
    event = _make_reject_event(tail_hash=first_entry.entry_hash)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=ReplayMissingEntriesNode(name="ReplayMissingEntries"),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        case_actor_id=case_actor.id_,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_called_once()
    kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert kwargs["entry"].id_ == second_entry.id_
    assert kwargs["actor_id"] == case_actor.id_
    assert kwargs["to"] == [PARTICIPANT_ACTOR_ID]


@pytest.mark.spec("SYNC-02-001")
@pytest.mark.spec("SYNC-02-003")
def test_fanout_log_entry_node_sends_to_case_addressees(bridge, datalayer):
    case_obj = VulnerabilityCase(
        id_=CASE_ID,
        attributed_to=OWNER_ACTOR_ID,
        actor_participant_index={
            OWNER_ACTOR_ID: f"{CASE_ID}/participants/vendor",
            PARTICIPANT_ACTOR_ID: f"{CASE_ID}/participants/reporter",
        },
    )
    datalayer.save(case_obj)
    entry = _make_entry(0)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=FanOutLogEntryNode(case_id=CASE_ID, name="FanOutLogEntry"),
        actor_id=OWNER_ACTOR_ID,
        log_entry=entry,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_called_once()
    kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert kwargs["entry"].id_ == entry.id_
    assert kwargs["actor_id"] == OWNER_ACTOR_ID
    assert kwargs["to"] == [PARTICIPANT_ACTOR_ID]
