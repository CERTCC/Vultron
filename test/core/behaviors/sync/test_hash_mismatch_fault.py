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

"""Hash refusal: the replica reports it, the CASE_MANAGER logs and self-checks.

The replica refuses the entry and reports it to the CASE_MANAGER
(SYNC-03-007).  From an active participant, the CASE_MANAGER logs the fault at
ERROR beside a re-check of its own copy of the entry, and changes nothing
(SYNC-03-008, SYNC-03-010); from anyone else it refuses the fault.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import seed_case_participant
from test.support.inbox_replay import held_depth, ledger_announce_event
from test.support.ledger_rebuild import run_use_case
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import ledger_entry_to_wire
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.sync.nodes.hash_mismatch import (
    OwnCopyCheck,
    ReportHashMismatchNode,
)
from vultron.core.models import fault_classes
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_ledger import (
    CaseLedger,
    ledger_entry_hash_intact,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.fault import CreateProcessingFaultReceivedEvent
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases._helpers import outbox_ids
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    announce_log_entry_activity,
    create_processing_fault_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/case-hash-mismatch-001"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_STRANGER_ID = "https://example.org/actors/stranger"
_PARTICIPANT_ID = "https://example.org/actors/participant"
_OTHER_MANAGER_ID = "https://example.org/actors/other-manager"
_HASH_MISMATCH = "https://certcc.github.io/Vultron/ns/errors/LedgerEntryRefused/HashMismatch"


@pytest.mark.spec("SYNC-03-007")
def test_hash_mismatch_failure_class_is_defined() -> None:
    """The replica's fault names the hash refusal by its own failure class.

    It is a sub-path of ``LedgerEntryRefused``, the parent it shares with
    the divergence fault (SYNC-16-001).
    """
    constant = fault_classes.VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH
    assert constant == _HASH_MISMATCH
    assert constant.startswith(
        f"{fault_classes.VULTRON_FAILURE_LEDGER_ENTRY_REFUSED}/"
    )


@pytest.mark.spec("SYNC-03-007")
@pytest.mark.spec("ASK-07-005")
def test_the_wire_vocabulary_carries_the_hash_mismatch_class() -> None:
    """A sealed fault of the class parses back from its wire form unchanged."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_PARTICIPANT_ID)
    fault_id = TriggerActivityAdapter(dl).emit_processing_fault(
        actor=_PARTICIPANT_ID,
        failed_activity_id=f"{_CASE_ID}/ledger/entries/0/announce",
        failure_class=_HASH_MISMATCH,
        to=[_CASE_ACTOR_ID],
    )
    body = read_sealed_body_dict(dl, fault_id)
    assert body is not None

    parsed = parse_activity(body)

    fault = cast(as_ProcessingFault, cast(as_Create, parsed).object_)
    assert fault.failure_class == _HASH_MISMATCH


def _replica() -> SqliteDataLayer:
    """A participant's replica of the case, managed by the CASE_MANAGER."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_PARTICIPANT_ID)
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="hash mismatch",
        attributed_to=_CASE_ACTOR_ID,
        published=datetime(2026, 10, 1, tzinfo=UTC),
    )
    seed_case_participant(dl, case, _CASE_ACTOR_ID, [CVDRole.CASE_MANAGER])
    dl.create(case)
    return dl


def _ledger_entry(genesis_hash: str) -> CaseLedgerEntry:
    """The case's first ledger entry, intact."""
    ledger = CaseLedger(case_id=_CASE_ID, genesis_hash=genesis_hash)
    ledger.append(
        object_id=f"{_CASE_ID}/notes/0",
        semantic_type="add_note_to_case",
        payload_snapshot={"type": "Add", "index": 0},
    )
    return ledger.entries[0].to_ledger_entry()


def _tampered_announce(dl: SqliteDataLayer) -> AnnounceLogEntryReceivedEvent:
    """The CASE_MANAGER's announce of an entry its content does not hash to."""
    case = cast(as_VulnerabilityCase, dl.read(_CASE_ID))
    entry = _ledger_entry(case.genesis_hash)
    tampered = entry.model_copy(update={"payload_snapshot": {"tampered": 1}})
    assert not ledger_entry_hash_intact(tampered)
    return ledger_announce_event(
        tampered, actor=_CASE_ACTOR_ID, to=_PARTICIPANT_ID
    )


@pytest.mark.spec("SYNC-03-006")
@pytest.mark.spec("SYNC-03-007")
@pytest.mark.spec("ASK-07-004")
def test_a_hash_refusal_queues_a_fault_to_the_case_manager_only(
    caplog,
) -> None:
    """The replica refuses the entry and tells the CASE_MANAGER, and no one else.

    The fault names the refused ``Announce`` by reference, its id derives
    from that ``Announce`` and the class, and the entry is neither stored nor
    held.  The refusal is still logged at ERROR.
    """
    dl = _replica()
    event = _tampered_announce(dl)

    with caplog.at_level(logging.ERROR, logger="vultron"):
        verdict = run_use_case(dl, event)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "SYNC-03-006" in (verdict.reason or "")
    expected_id = derived_activity_id(
        "processing-fault", _PARTICIPANT_ID, event.activity_id, _HASH_MISMATCH
    )
    assert dl.outbox_list() == [expected_id]
    body = read_sealed_body_dict(dl, expected_id)
    assert body is not None
    assert body["type"] == "Create"
    assert body["to"] == [_CASE_ACTOR_ID]
    assert not body.get("cc") and not body.get("bto") and not body.get("bcc")
    assert body["object"]["failureClass"] == _HASH_MISMATCH
    assert body["object"]["inReplyTo"] == event.activity_id
    assert event.log_entry is not None
    assert dl.read(event.log_entry.id_) is None
    assert held_depth(dl, _CASE_ID) == 0
    assert any(
        r.levelno == logging.ERROR and "entry_hash" in r.getMessage()
        for r in caplog.records
    ), caplog.text


@pytest.mark.spec("SYNC-03-007")
@pytest.mark.spec("ID-04-004")
def test_a_redelivered_tampered_entry_builds_no_second_fault() -> None:
    """The same refused ``Announce`` names the same fault (ID-04-004)."""
    dl = _replica()
    event = _tampered_announce(dl)

    run_use_case(dl, event)
    run_use_case(dl, event)

    assert len(list(dl.list_objects("Create"))) == 1


@pytest.mark.spec("SYNC-16-002")
@pytest.mark.spec("CLP-04-007")
def test_no_case_ledger_gains_an_entry_for_a_hash_mismatch_fault() -> None:
    """Neither the replica nor the CASE_MANAGER ledgers the fault."""
    replica = _replica()
    run_use_case(replica, _tampered_announce(replica))
    (fault_id,) = replica.outbox_list()
    body = read_sealed_body_dict(replica, fault_id)
    assert body is not None
    manager = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    case = as_VulnerabilityCase(
        id_=_CASE_ID, name="hash mismatch", attributed_to=_CASE_ACTOR_ID
    )
    seed_case_participant(
        manager, case, _CASE_ACTOR_ID, [CVDRole.CASE_MANAGER]
    )
    seed_case_participant(manager, case, _PARTICIPANT_ID)
    manager.create(case)

    run_use_case(
        manager,
        received_event(
            parse_activity(body), receiving_actor_id=_CASE_ACTOR_ID
        ),
    )

    assert list(replica.list_objects("CaseLedgerEntry")) == []
    assert list(manager.list_objects("CaseLedgerEntry")) == []


def _manager(
    *, receiver_is_manager: bool = True
) -> tuple[SqliteDataLayer, CaseLedgerEntry, str]:
    """The CASE_MANAGER's store: its case, an active participant, a stored
    ledger entry and the ``Announce`` of it the CASE_MANAGER sent.

    With *receiver_is_manager* false, the store's actor holds only a
    participant's role, and another actor manages the case.  Returns the
    store, the entry and the ``Announce``'s id.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    case = as_VulnerabilityCase(
        id_=_CASE_ID, name="hash mismatch", attributed_to=_CASE_ACTOR_ID
    )
    if receiver_is_manager:
        seed_case_participant(dl, case, _CASE_ACTOR_ID, [CVDRole.CASE_MANAGER])
    else:
        seed_case_participant(dl, case, _CASE_ACTOR_ID)
        seed_case_participant(
            dl, case, _OTHER_MANAGER_ID, [CVDRole.CASE_MANAGER]
        )
    seed_case_participant(dl, case, _PARTICIPANT_ID)
    dl.create(case)
    entry = _ledger_entry(case.genesis_hash)
    dl.save(entry)
    announce = announce_log_entry_activity(
        entry=ledger_entry_to_wire(entry),
        actor=_CASE_ACTOR_ID,
        to=[_PARTICIPANT_ID],
    )
    dl.save(announce)
    return dl, entry, announce.id_


def _fault(
    dl: SqliteDataLayer, sender: str, announce_id: str | None
) -> HandlerResult:
    """Deliver *sender*'s hash-mismatch fault naming *announce_id* (none
    when ``None``)."""
    activity = create_processing_fault_activity(
        actor=sender,
        fault=as_ProcessingFault(
            failure_class=_HASH_MISMATCH, in_reply_to=announce_id
        ),
        to=[_CASE_ACTOR_ID],
    )
    return CreateProcessingFaultReceivedUseCase(
        dl,
        cast(
            CreateProcessingFaultReceivedEvent,
            received_event(activity, receiving_actor_id=_CASE_ACTOR_ID, at=dl),
        ),
    ).execute()


def _replication_state(dl: SqliteDataLayer) -> VultronReplicationState:
    """A replication record for the participant, to show it is untouched."""
    state = VultronReplicationState(
        case_id=_CASE_ID,
        peer_id=_PARTICIPANT_ID,
        last_acknowledged_hash="a" * 64,
    )
    dl.create(state)
    return state


@pytest.mark.spec("SYNC-03-008")
@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("CM-10-004")
def test_hash_mismatch_fault_from_a_non_participant_is_refused() -> None:
    """A stranger's fault about a real case is refused, nothing changing.

    The case and the named ``Announce`` exist, so the sender rule, not an
    unknown case, decides the outcome.
    """
    dl, _, announce_id = _manager()
    state = _replication_state(dl)
    before = dl.read(state.id_)

    result = _fault(dl, _STRANGER_ID, announce_id)

    assert result.disposition is HandlerDisposition.REFUSED, result.reason
    assert outbox_ids(_CASE_ACTOR_ID, dl) == set()
    assert dl.read(state.id_) == before
    assert len(list(dl.list_objects("ReplicationState"))) == 1
    assert len(list(dl.list_objects("CaseLedgerEntry"))) == 1


@pytest.mark.spec("SYNC-03-008")
@pytest.mark.spec("SYNC-16-002")
def test_hash_mismatch_fault_from_an_active_participant_changes_nothing() -> (
    None
):
    """An active participant's fault is ``SKIPPED``: nothing sent, re-seeded,
    recorded or ledgered."""
    dl, _, announce_id = _manager()
    state = _replication_state(dl)
    before = dl.read(state.id_)

    result = _fault(dl, _PARTICIPANT_ID, announce_id)

    assert result.disposition is HandlerDisposition.SKIPPED, result.reason
    assert outbox_ids(_CASE_ACTOR_ID, dl) == set()
    assert dl.read(state.id_) == before
    assert len(list(dl.list_objects("ReplicationState"))) == 1
    assert len(list(dl.list_objects("CaseLedgerEntry"))) == 1


@pytest.mark.spec("SYNC-03-008")
def test_hash_mismatch_fault_naming_no_announce_sent_is_refused() -> None:
    """A fault naming no ``Announce(CaseLedgerEntry)`` this actor sent names
    no case, so it is refused with nothing sent (ASK-07-004)."""
    dl, _, _ = _manager()

    result = _fault(dl, _PARTICIPANT_ID, f"{_CASE_ID}/ledger/entries/7")

    assert result.disposition is HandlerDisposition.REFUSED
    assert "names no case" in (result.reason or "")
    assert outbox_ids(_CASE_ACTOR_ID, dl) == set()


def _break_own_copy(dl: SqliteDataLayer, entry: CaseLedgerEntry) -> None:
    dl.save(entry.model_copy(update={"payload_snapshot": {"tampered": 1}}))


def _drop_own_copy(dl: SqliteDataLayer, entry: CaseLedgerEntry) -> None:
    assert dl.delete("CaseLedgerEntry", entry.id_)


@pytest.mark.spec("SYNC-03-010")
@pytest.mark.parametrize(
    ("damage", "expected", "says"),
    [
        (None, OwnCopyCheck.INTACT, "the copy the replica received is broken"),
        (
            _break_own_copy,
            OwnCopyCheck.NOT_INTACT,
            "this CASE_MANAGER's own ledger is broken",
        ),
        (
            _drop_own_copy,
            OwnCopyCheck.NO_STORED_COPY,
            "holds no stored copy of the entry",
        ),
    ],
    ids=["intact", "not-intact", "no-stored-copy"],
)
def test_hash_mismatch_fault_from_an_active_participant_is_logged_at_error(
    caplog,
    damage: Callable[[SqliteDataLayer, CaseLedgerEntry], None] | None,
    expected: OwnCopyCheck,
    says: str,
) -> None:
    """One ERROR record names the case, the ``Announce``, the entry, the
    sender and what the self-check of the CASE_MANAGER's own copy found."""
    dl, entry, announce_id = _manager()
    if damage is not None:
        damage(dl, entry)

    with caplog.at_level(logging.ERROR, logger="vultron"):
        result = _fault(dl, _PARTICIPANT_ID, announce_id)

    assert result.disposition is HandlerDisposition.SKIPPED, result.reason
    assert expected.value in (result.reason or "")
    (record,) = [r for r in caplog.records if r.levelno == logging.ERROR]
    message = record.getMessage()
    for named in (_CASE_ID, announce_id, entry.id_, _PARTICIPANT_ID, says):
        assert named in message, message
    assert f"Self-check: {expected.value};" in message


@pytest.mark.spec("SYNC-03-010")
def test_a_strangers_hash_mismatch_fault_runs_no_self_check(caplog) -> None:
    """The sender rule stops the fault before the CASE_MANAGER reports it."""
    dl, _, announce_id = _manager()

    with caplog.at_level(logging.ERROR, logger="vultron"):
        _fault(dl, _STRANGER_ID, announce_id)

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.spec("SYNC-03-008")
@pytest.mark.spec("HP-01-005")
def test_a_hash_mismatch_fault_at_a_participant_is_refused(caplog) -> None:
    """Only the case's CASE_MANAGER reports the fault; a participant that
    receives one, even from the CASE_MANAGER, changes nothing and refuses
    it at the CASE_MANAGER gate."""
    dl, _, announce_id = _manager(receiver_is_manager=False)

    with caplog.at_level(logging.ERROR, logger="vultron"):
        result = _fault(dl, _OTHER_MANAGER_ID, announce_id)

    assert result.disposition is HandlerDisposition.REFUSED, result.reason
    assert f"not the CASE_MANAGER of case '{_CASE_ID}'" in (
        result.reason or ""
    )
    assert outbox_ids(_CASE_ACTOR_ID, dl) == set()
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.spec("SYNC-03-008")
def test_a_hash_mismatch_fault_naming_no_announce_is_refused(caplog) -> None:
    """A fault with no ``inReplyTo`` names no case: it is only archived and
    refused, with no report and no self-check."""
    dl, _, _ = _manager()

    with caplog.at_level(logging.ERROR, logger="vultron"):
        result = _fault(dl, _PARTICIPANT_ID, None)

    assert result.disposition is HandlerDisposition.REFUSED, result.reason
    assert "names no case to report on (SYNC-03-008" in (result.reason or "")
    assert outbox_ids(_CASE_ACTOR_ID, dl) == set()
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.spec("SYNC-03-010")
def test_the_report_node_fails_without_a_datalayer() -> None:
    """With no store to read, the node fails and records no self-check."""
    node = ReportHashMismatchNode(
        _ledger_entry("0" * 64),
        peer_id=_PARTICIPANT_ID,
        announce_id="urn:x:announce",
    )

    assert node.update() is Status.FAILURE
    assert node.own_copy is None
