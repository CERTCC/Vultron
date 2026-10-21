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

"""Divergence recovery: a diverged replica reports, the CASE_MANAGER re-seeds.

The tests of the replica's side of a repair, the ledger tail a case copy
names and how a replica that holds the case judges the copy by it
(SYNC-16-005 through SYNC-16-007), are behaviour tests.  The others are a
strict ``xfail`` for unbuilt behaviour (ADR-0142), except one that pins a
SYNC-16 property that already holds.  Each implementation issue removes the
``xfail`` from the tests it makes pass, and replaces a probe with a full
behaviour test where the probe only pins a name.
"""

import logging
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from pydantic import ValidationError

from test.support.inbox_replay import ledger_announce_event
from test.support.ledger_rebuild import run_use_case
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIQueuePort,
)
from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models import fault_classes
from vultron.core.models.case_copy_position import CaseCopyPosition
from vultron.core.models.case_ledger import CaseLedger
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.events.fault import CreateProcessingFaultReceivedEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.services.case_copy import (
    entry_reflected_by_case_copy,
    records_a_reflected_entry_adds,
)
from vultron.core.services.case_replica_seeding import (
    store_embedded_participants,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.actor.announce import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError
from vultron.metadata.wire_context.sync import build_context_document
from vultron.wire.as2.factories import (
    announce_vulnerability_case_activity,
    create_processing_fault_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
)
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/case-diverged-001"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_REPLICA_ID = "https://example.org/actors/replica"
_STRANGER_ID = "https://example.org/actors/stranger"
_CASE_DIVERGED = "https://certcc.github.io/Vultron/ns/errors/LedgerEntryRefused/CaseDiverged"
_PUBLISHED = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-16-001: no case-diverged failure class yet. Tracked by #4798.",
)
@pytest.mark.spec("SYNC-16-001")
def test_case_diverged_failure_class_is_defined() -> None:
    """The replica's fault names the divergence by its own failure class."""
    # getattr until #4798 defines the name, so the type checkers pass now.
    constant = getattr(  # noqa: B009
        fault_classes,
        "VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED",
    )
    assert constant == _CASE_DIVERGED


@pytest.mark.spec("SYNC-16-002")
def test_case_manager_does_not_ledger_a_divergence_fault() -> None:
    """The CASE_MANAGER commits no ledger entry for a divergence fault.

    Holds already, because the fault use case only logs. #4798 adds the
    replica side when it builds the fault's emission.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    dl.create(as_VulnerabilityCase(id_=_CASE_ID, name="current copy"))
    activity = create_processing_fault_activity(
        actor=_REPLICA_ID,
        fault=as_ProcessingFault(
            failure_class=_CASE_DIVERGED,
            in_reply_to=f"{_CASE_ID}/ledger/entries/7/announce",
        ),
        to=[_CASE_ACTOR_ID],
    )

    CreateProcessingFaultReceivedUseCase(
        dl, cast(CreateProcessingFaultReceivedEvent, received_event(activity))
    ).execute()

    assert list(dl.list_objects("CaseLedgerEntry")) == []


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-16-003: the fault use case only logs. Tracked by #4799.",
)
@pytest.mark.spec("SYNC-16-003")
def test_case_diverged_fault_from_a_non_participant_is_refused() -> None:
    """Only an active participant's divergence fault earns a re-seed."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    activity = create_processing_fault_activity(
        actor=_STRANGER_ID,
        fault=as_ProcessingFault(
            failure_class=_CASE_DIVERGED,
            in_reply_to=f"{_CASE_ID}/ledger/entries/7/announce",
        ),
        to=[_CASE_ACTOR_ID],
    )

    result = CreateProcessingFaultReceivedUseCase(
        dl, cast(CreateProcessingFaultReceivedEvent, received_event(activity))
    ).execute()

    assert result.disposition == HandlerDisposition.REFUSED


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-16-004: no per-peer re-seed record yet. Tracked by #4799.",
)
@pytest.mark.spec("SYNC-16-004")
@pytest.mark.spec("SYNC-16-008")
def test_replication_state_records_the_last_reseed() -> None:
    """The re-seed rate bound and the repeat check read per-peer state."""
    assert any(
        "reseed" in field for field in VultronReplicationState.model_fields
    )


_MANAGER_PARTICIPANT_ID = f"{_CASE_ID}/participants/case-manager"


def _replica_holding(name: str) -> SqliteDataLayer:
    """A replica that holds the case, whose roster names its CASE_MANAGER."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPLICA_ID)
    dl.create(
        CaseParticipant(
            id_=_MANAGER_PARTICIPANT_ID,
            attributed_to=_CASE_ACTOR_ID,
            context=_CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
    )
    dl.create(_owned_case(name))
    return dl


def _owned_case(name: str) -> as_VulnerabilityCase:
    """The case, with an owner so it has a genesis hash to anchor its chain."""
    return as_VulnerabilityCase(
        id_=_CASE_ID,
        name=name,
        attributed_to=_CASE_ACTOR_ID,
        published=_PUBLISHED,
        case_participants=[_MANAGER_PARTICIPANT_ID],
        actor_participant_index={_CASE_ACTOR_ID: _MANAGER_PARTICIPANT_ID},
    )


def _chain(
    dl: SqliteDataLayer, snapshots: list[dict[str, Any]]
) -> list[CaseLedgerEntry]:
    """The case's chain of entries carrying *snapshots*, built, not stored."""
    case = cast(as_VulnerabilityCase, dl.read(_CASE_ID))
    ledger = CaseLedger(case_id=_CASE_ID, genesis_hash=case.genesis_hash)
    for index, snapshot in enumerate(snapshots):
        ledger.append(
            object_id=f"{_CASE_ID}/notes/{index}",
            semantic_type="add_note_to_case",
            payload_snapshot=snapshot,
        )
    return [record.to_ledger_entry() for record in ledger.entries]


def _store_chain(dl: SqliteDataLayer, length: int) -> list[CaseLedgerEntry]:
    """Store a chain of *length* entries for the case, as a replica holds it."""
    entries = _chain(
        dl, [{"type": "Add", "index": index} for index in range(length)]
    )
    for entry in entries:
        dl.create(entry)
    return entries


def _announce(
    copy: as_VulnerabilityCase,
    dl: SqliteDataLayer,
    *,
    with_sync_port: bool = True,
) -> HandlerResult:
    activity = announce_vulnerability_case_activity(
        copy, actor=_CASE_ACTOR_ID, to=[_REPLICA_ID], context=_CASE_ID
    )
    return AnnounceVulnerabilityCaseReceivedUseCase(
        dl,
        cast(
            AnnounceVulnerabilityCaseReceivedEvent,
            received_event(activity, receiving_actor_id=_REPLICA_ID),
        ),
        sync_port=SyncActivityAdapter(dl) if with_sync_port else None,
    ).execute()


def _case_name(dl: SqliteDataLayer) -> str | None:
    return cast(as_VulnerabilityCase, dl.read(_CASE_ID)).name


@pytest.mark.spec("SYNC-16-005")
def test_a_case_copy_carries_its_ledger_tail_on_the_wire() -> None:
    """The tail travels as ``ledgerTail`` and parses back onto the copy.

    It is not a field of the case: the case's own record never stores it,
    and the Vultron JSON-LD context declares the property (VM-10-001).
    """
    tail = LedgerPosition(log_index=4, entry_hash="ab" * 32)
    copy = _owned_case("current copy").with_ledger_tail(tail)
    activity = announce_vulnerability_case_activity(
        copy, actor=_CASE_ACTOR_ID, context=_CASE_ID
    )

    sent = activity.model_dump(by_alias=True, exclude_none=True, mode="json")
    parsed = parse_activity(sent)

    assert "ledger_tail" not in as_VulnerabilityCase.model_fields
    assert sent["object"]["ledgerTail"] == {
        "logIndex": 4,
        "entryHash": "ab" * 32,
    }
    assert cast(as_Announce, parsed).object_ is not None
    assert (
        cast(as_VulnerabilityCase, cast(as_Announce, parsed).object_)
    ).ledger_tail == tail
    terms = cast(list[dict[str, str]], build_context_document()["@context"])
    assert terms[1]["ledgerTail"] == "vultron:ledgerTail"
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPLICA_ID)
    dl.create(copy)
    assert cast(as_VulnerabilityCase, dl.read(_CASE_ID)).ledger_tail is None


@pytest.mark.spec("SYNC-16-006")
@pytest.mark.spec("HP-01-003")
def test_a_copy_the_chain_is_past_is_skipped() -> None:
    """A late, older copy leaves the case unchanged and reads ``SKIPPED``."""
    dl = _replica_holding("replica case")
    entries = _store_chain(dl, 3)

    result = _announce(
        _owned_case("old copy").with_ledger_tail(
            LedgerPosition(log_index=1, entry_hash=entries[1].entry_hash)
        ),
        dl,
    )

    assert result.disposition is HandlerDisposition.SKIPPED, result.reason
    assert _case_name(dl) == "replica case"


@pytest.mark.spec("SYNC-16-006")
def test_a_copy_that_conflicts_with_the_chain_is_refused_at_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A different entry at the tail's index: ``REFUSED``, ERROR, unchanged."""
    dl = _replica_holding("replica case")
    _store_chain(dl, 3)

    with caplog.at_level(logging.ERROR):
        result = _announce(
            _owned_case("conflicting copy").with_ledger_tail(
                LedgerPosition(log_index=2, entry_hash="cd" * 32)
            ),
            dl,
        )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "conflict" in (result.reason or "")
    assert _case_name(dl) == "replica case"
    assert any(
        r.levelno == logging.ERROR and "conflicts" in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.spec("SYNC-16-006")
def test_a_copy_of_a_held_case_with_no_tail_is_refused() -> None:
    """Without a tail the replica cannot tell the copy from a stale one."""
    dl = _replica_holding("replica case")

    result = _announce(_owned_case("untailed copy"), dl)

    assert result.disposition is HandlerDisposition.REFUSED
    assert _case_name(dl) == "replica case"


@pytest.mark.spec("PCR-02-004")
@pytest.mark.spec("SYNC-16-006")
def test_a_copy_at_the_replicas_tail_replaces_its_case() -> None:
    """A current copy from the CASE_MANAGER replaces the replica's case file,
    and sends no Reject: the chain is not short of it."""
    dl = _replica_holding("diverged copy")
    entries = _store_chain(dl, 2)

    result = _announce(
        _owned_case("current copy").with_ledger_tail(
            LedgerPosition(log_index=1, entry_hash=entries[1].entry_hash)
        ),
        dl,
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _case_name(dl) == "current copy"
    assert dl.read(CaseCopyPosition.build_id(_CASE_ID)) is None
    assert dl.outbox_list() == []


@pytest.mark.spec("SYNC-16-007")
def test_a_copy_ahead_of_the_chain_asks_for_the_rest() -> None:
    """The replica records the copy's tail and sends ``Reject(CaseLedgerEntry)``
    naming its own tail, so the CASE_MANAGER replays from there."""
    dl = _replica_holding("short replica")
    entries = _store_chain(dl, 2)

    result = _announce(
        _owned_case("copy ahead").with_ledger_tail(
            LedgerPosition(log_index=5, entry_hash="ef" * 32)
        ),
        dl,
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _case_name(dl) == "copy ahead"
    position = dl.read(CaseCopyPosition.build_id(_CASE_ID))
    assert isinstance(position, CaseCopyPosition)
    assert (position.log_index, position.entry_hash) == (5, "ef" * 32)
    (reject_id,) = dl.outbox_list()
    reject = read_sealed_body_dict(dl, reject_id)
    assert reject is not None
    assert reject["type"] == "Reject"
    assert reject["to"] == [_CASE_ACTOR_ID]
    assert reject["context"] == entries[-1].entry_hash


@pytest.mark.spec("SYNC-16-007")
def test_a_backfill_without_a_sync_port_is_a_wiring_fault() -> None:
    """A Reject that is due but cannot be sent is our fault, not a refusal."""
    dl = _replica_holding("short replica")
    _store_chain(dl, 1)

    with pytest.raises(VultronBTInternalError, match="sync_port"):
        _announce(
            _owned_case("copy ahead").with_ledger_tail(
                LedgerPosition(log_index=5, entry_hash="ef" * 32)
            ),
            dl,
            with_sync_port=False,
        )


@pytest.mark.spec("SYNC-16-007")
def test_a_replica_with_no_entry_records_the_copy_and_waits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With no stored entry there is nothing for a Reject to name: the
    replica records the copy's tail, sends nothing, and says so; the next
    entry fanned out arrives as a forward gap (SYNC-14-002)."""
    dl = _replica_holding("empty replica")

    with caplog.at_level(logging.WARNING):
        result = _announce(
            _owned_case("copy ahead").with_ledger_tail(
                LedgerPosition(log_index=3, entry_hash="ef" * 32)
            ),
            dl,
        )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _case_name(dl) == "copy ahead"
    assert isinstance(
        dl.read(CaseCopyPosition.build_id(_CASE_ID)), CaseCopyPosition
    )
    assert dl.outbox_list() == []
    assert any("no entry" in r.getMessage() for r in caplog.records)


@pytest.mark.spec("SYNC-16-006")
def test_a_copy_behind_the_last_replacement_is_stale() -> None:
    """Until the chain catches up, the copy that replaced the case is the
    replica's position, so an older copy cannot move the case back."""
    dl = _replica_holding("short replica")
    _store_chain(dl, 1)
    assert (
        _announce(
            _owned_case("newer copy").with_ledger_tail(
                LedgerPosition(log_index=6, entry_hash="ef" * 32)
            ),
            dl,
        ).disposition
        is HandlerDisposition.APPLIED
    )

    result = _announce(
        _owned_case("older copy").with_ledger_tail(
            LedgerPosition(log_index=4, entry_hash="12" * 32)
        ),
        dl,
    )

    assert result.disposition is HandlerDisposition.SKIPPED, result.reason
    assert _case_name(dl) == "newer copy"


@pytest.mark.spec("SYNC-16-006")
@pytest.mark.spec("IO-03-004")
def test_the_inbox_routes_the_copy_not_the_held_case() -> None:
    """Through the real inbox the use case judges the copy that arrived.

    Ingress stores nothing (IO-03-004), and its rebuild keeps the copy inline
    rather than reading back the case the replica holds, so a stale copy
    leaves the case unchanged and a current one replaces it (AC-7).
    """
    dl = _replica_holding("replica case")
    entries = _store_chain(dl, 2)

    def deliver(copy: as_VulnerabilityCase) -> InboxOutcome:
        activity = announce_vulnerability_case_activity(
            copy, actor=_CASE_ACTOR_ID, to=[_REPLICA_ID], context=_CASE_ID
        )
        staging = InlineObjectStaging(dl)
        return process_payload(
            activity.model_dump(mode="json", by_alias=True, exclude_none=True),
            FastAPIIngressAdapter(dl=dl, staging=staging),
            FastAPIDispatchAdapter(
                dl=dl, actor_id=_REPLICA_ID, dispatcher=make_dispatcher()
            ),
            FastAPIQueuePort(
                dl=dl, actor_dl=dl, actor_id=_REPLICA_ID, staging=staging
            ),
        )

    stale = deliver(
        _owned_case("stale copy").with_ledger_tail(
            LedgerPosition(log_index=0, entry_hash=entries[0].entry_hash)
        )
    )
    assert _case_name(dl) == "replica case", stale

    current = deliver(
        _owned_case("current copy").with_ledger_tail(
            LedgerPosition(log_index=1, entry_hash=entries[1].entry_hash)
        )
    )
    assert current.status is InboxOutcomeStatus.PROCESSED, current
    assert _case_name(dl) == "current copy"


@pytest.mark.spec("SYNC-16-006")
def test_a_genesis_copy_naming_another_genesis_hash_is_refused() -> None:
    """At index -1 the hash compared is the case's genesis hash."""
    dl = _replica_holding("replica case")

    result = _announce(
        _owned_case("foreign copy").with_ledger_tail(
            LedgerPosition(log_index=-1, entry_hash="cd" * 32)
        ),
        dl,
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert _case_name(dl) == "replica case"


@pytest.mark.spec("SYNC-16-006")
def test_a_genesis_copy_the_chain_is_past_is_skipped() -> None:
    dl = _replica_holding("replica case")
    _store_chain(dl, 1)
    genesis = cast(as_VulnerabilityCase, dl.read(_CASE_ID)).genesis_hash

    result = _announce(
        _owned_case("genesis copy").with_ledger_tail(
            LedgerPosition(log_index=-1, entry_hash=genesis)
        ),
        dl,
    )

    assert result.disposition is HandlerDisposition.SKIPPED, result.reason
    assert _case_name(dl) == "replica case"


@pytest.mark.spec("SYNC-16-006")
def test_a_copy_conflicting_with_the_last_replacement_is_refused() -> None:
    """While the chain is short of the last replacing copy, that copy's tail
    is the entry held at its index, so a copy naming another hash there
    conflicts."""
    dl = _replica_holding("short replica")
    _store_chain(dl, 1)
    _announce(
        _owned_case("first copy").with_ledger_tail(
            LedgerPosition(log_index=4, entry_hash="ef" * 32)
        ),
        dl,
    )

    result = _announce(
        _owned_case("rival copy").with_ledger_tail(
            LedgerPosition(log_index=4, entry_hash="12" * 32)
        ),
        dl,
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert _case_name(dl) == "first copy"


@pytest.mark.spec("SYNC-16-007")
def test_only_the_entry_the_copy_named_at_its_tail_is_reflected() -> None:
    dl = _replica_holding("short replica")
    entries = _chain(dl, [{"type": "Add", "index": i} for i in range(3)])
    dl.create(entries[0])
    dl.save(
        CaseCopyPosition(
            case_id=_CASE_ID, log_index=2, entry_hash=entries[2].entry_hash
        )
    )
    other = entries[2].model_copy(update={"entry_hash": "34" * 32})

    assert entry_reflected_by_case_copy(entries[1], dl)
    assert entry_reflected_by_case_copy(entries[2], dl)
    assert not entry_reflected_by_case_copy(other, dl)


@pytest.mark.spec("SYNC-16-007")
@pytest.mark.spec("CM-23-016")
def test_a_reflected_entry_stores_the_record_the_copy_names(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The copy names its note by id; the reflected entry that carries the
    note is stored without effects, and the note itself is copied (#5052)."""
    note_id = f"{_CASE_ID}/notes/n-1"
    dl = _replica_holding("short replica")
    entries = _chain(
        dl,
        [
            {"type": "Add", "index": 0},
            {
                "type": "Add",
                "object": {
                    "id": note_id,
                    "type": "Note",
                    "content": "a note the copy names",
                    "context": _CASE_ID,
                },
                "target": _CASE_ID,
            },
            {"type": "Add", "index": 2},
        ],
    )
    dl.create(entries[0])
    copy = _owned_case("copy ahead").model_copy(update={"notes": [note_id]})
    assert (
        _announce(
            copy.with_ledger_tail(
                LedgerPosition(log_index=2, entry_hash=entries[2].entry_hash)
            ),
            dl,
        ).disposition
        is HandlerDisposition.APPLIED
    )

    with caplog.at_level(logging.INFO):
        result = run_use_case(
            dl,
            ledger_announce_event(
                entries[1], actor=_CASE_ACTOR_ID, to=_REPLICA_ID
            ),
        )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert any("as a no-op" in r.getMessage() for r in caplog.records)
    assert dl.read(entries[1].id_) is not None
    note = dl.read(note_id)
    assert note is not None
    assert getattr(note, "content", None) == "a note the copy names"
    assert cast(as_VulnerabilityCase, dl.read(_CASE_ID)).notes == [note_id]


@pytest.mark.spec("SYNC-16-005")
def test_a_carried_value_under_two_disagreeing_spellings_is_refused() -> None:
    data = _owned_case("copy").model_dump(mode="json")
    data["ledgerTail"] = {"logIndex": 1, "entryHash": "ab" * 32}
    data["ledger_tail"] = {"log_index": 2, "entry_hash": "ab" * 32}

    with pytest.raises(ValidationError, match="disagree"):
        as_VulnerabilityCase.model_validate(data)


@pytest.mark.spec("SYNC-16-005")
def test_a_malformed_tail_is_refused_under_its_own_name() -> None:
    data = _owned_case("copy").model_dump(mode="json")
    data["ledgerTail"] = {"logIndex": -7, "entryHash": ""}

    with pytest.raises(ValidationError, match="ledger_tail"):
        as_VulnerabilityCase.model_validate(data)


@pytest.mark.spec("SYNC-16-005")
def test_only_a_declared_carried_value_can_be_attached() -> None:
    case = _owned_case("copy")

    with pytest.raises(ValueError, match="carries no"):
        case.with_carried("other", LedgerPosition(log_index=0, entry_hash="a"))
    with pytest.raises(ValueError, match="carries no"):
        case.with_carried("ledger_tail", case)


@pytest.mark.spec("PCR-02-004")
def test_a_current_copy_replaces_a_participant_the_replica_holds_ahead() -> (
    None
):
    """A copy judged current is authoritative: its participant replaces the
    stored one even where the stored RM state is further along, which is
    how a diverged replica is repaired (ADR-0142)."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPLICA_ID)
    participant_id = f"{_CASE_ID}/participants/vendor"

    def participant(rm: RM) -> CaseParticipant:
        return CaseParticipant(
            id_=participant_id,
            attributed_to=_REPLICA_ID,
            context=_CASE_ID,
            participant_statuses=[
                ParticipantStatus(
                    context=_CASE_ID,
                    attributed_to=_REPLICA_ID,
                    rm=RmDimension(state=rm),
                )
            ],
        )

    dl.create(participant(RM.ACCEPTED))
    copy = _owned_case("copy").model_copy(
        update={"case_participants": [participant(RM.VALID)]}
    )

    store_embedded_participants(copy, dl, _CASE_ID)
    kept = cast(CaseParticipant, dl.read(participant_id))
    store_embedded_participants(copy, dl, _CASE_ID, authoritative=True)
    replaced = cast(CaseParticipant, dl.read(participant_id))

    assert kept.participant_status is not None
    assert replaced.participant_status is not None
    assert kept.participant_status.rm.state is RM.ACCEPTED
    assert replaced.participant_status.rm.state is RM.VALID


@pytest.mark.spec("SYNC-16-007")
@pytest.mark.spec("CM-23-016")
def test_a_reflected_entry_copies_each_record_the_case_names_and_no_other() -> (
    None
):
    """An embargo proposal and a nested case status the copy names by id are
    copied from the entry; a record the case does not name is not (#5052)."""
    dl = _replica_holding("replaced replica")
    proposal_id = f"{_CASE_ID}/embargo_events/proposal"
    status_id = f"{_CASE_ID}/statuses/s-1"
    stray_id = f"{_CASE_ID}/notes/removed"
    case = cast(as_VulnerabilityCase, dl.read(_CASE_ID))
    dl.save(
        case.model_copy(
            update={
                "pending_embargo_proposal_index": {"proposer": proposal_id},
                "case_statuses": [*case.case_statuses, status_id],
            }
        )
    )
    proposal = EmbargoEvent(
        id_=proposal_id,
        context=_CASE_ID,
        end_time=datetime(2026, 12, 1, tzinfo=UTC),
    )
    status = CaseStatus(id_=status_id, context=_CASE_ID)
    (entry,) = _chain(
        dl,
        [
            {
                "type": "Offer",
                "object": proposal.model_dump(mode="json", by_alias=True),
                "result": {
                    "status": status.model_dump(mode="json", by_alias=True),
                    "note": {
                        "id": stray_id,
                        "type": "Note",
                        "content": "named by no one",
                        "context": _CASE_ID,
                    },
                },
            }
        ],
    )

    records = records_a_reflected_entry_adds(entry, dl)

    assert sorted(r.id_ for r in records) == sorted([proposal_id, status_id])
    dl.create(proposal)
    assert [r.id_ for r in records_a_reflected_entry_adds(entry, dl)] == [
        status_id
    ]
