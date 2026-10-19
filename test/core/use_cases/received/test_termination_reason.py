"""The termination reason a received ``Remove(EmbargoEvent)`` carries (#4293).

ADR-0122: the ``Remove``'s ``content`` is the termination's what, exactly
``END_TIME_REACHED`` or ``EARLY``, checked at the parse edge.  The receiver
records it on the ``TERMINATED`` register entry, and refuses an
``END_TIME_REACHED`` published before the embargo's end time — at the
CASE_MANAGER before the commit, at a replica on replay.  The why the
``Remove`` carries beside it, ``terminationCause``, is covered in
``test_termination_cause.py`` (EMB-13-005).
"""

from datetime import timedelta
from typing import cast

import pytest
from py_trees.common import Status

from test.support.clock_decisions import run_end_time_check
from test.support.embargo_register import activate
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.embargo.nodes import ApplyEmbargoTeardownNode
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.use_cases.received.embargo import (
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.factories import remove_embargo_from_case_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import make_embargo_case_with_actor

OWNER = "https://example.org/users/owner"


def _case_with_embargo(case_id: str, *, ended: bool):
    """The CASE_MANAGER's store, its embargo in force; *ended* puts the end
    time an hour in the past."""
    dl, _, case, embargo = make_embargo_case_with_actor(
        case_id, OWNER, case_manager_actor_id=OWNER
    )
    if ended:
        embargo = as_EmbargoEvent(
            id_=embargo.id_,
            context=case_id,
            end_time=now_utc() - timedelta(hours=1),
        )
        dl.save(embargo)
    stored = cast(VulnerabilityCase, dl.read(case.id_))
    activate(stored, embargo.id_)
    dl.save(stored)
    return dl, stored, embargo


def _receive(dl, event):
    return RemoveEmbargoEventFromCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _ledger(dl, case_id: str) -> list[CaseLedgerEntry]:
    return [
        cast(CaseLedgerEntry, obj)
        for obj in dl.list_objects("CaseLedgerEntry")
        if cast(CaseLedgerEntry, obj).case_id == case_id
    ]


# ---------------------------------------------------------------------------
# AC-1: the parse edge
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-004")
@pytest.mark.parametrize("content", [None, "", "THREAT_SIGNAL", "early"])
def test_parse_edge_refuses_a_remove_without_a_termination_reason(
    make_payload, content
) -> None:
    _dl, case, embargo = _case_with_embargo(
        "https://example.org/cases/tr-parse", ended=False
    )
    activity = remove_embargo_from_case_activity(
        embargo, origin=case.id_, actor=OWNER, reason=TerminationReason.EARLY
    )
    # Bypass the factory's validation to model a sender that got it wrong.
    tampered = activity.model_copy(update={"content": content})

    with pytest.raises(VultronParseValidationError, match="END_TIME_REACHED"):
        make_payload(tampered)


@pytest.mark.spec("EMB-13-004")
@pytest.mark.parametrize("reason", list(TerminationReason))
def test_parse_edge_promotes_the_reason_onto_the_event(
    make_payload, reason
) -> None:
    _dl, case, embargo = _case_with_embargo(
        "https://example.org/cases/tr-promote", ended=False
    )
    activity = remove_embargo_from_case_activity(
        embargo, origin=case.id_, actor=OWNER, reason=reason
    )

    event = make_payload(activity)

    assert event.termination_reason is reason
    assert activity.summary  # human-readable; the protocol ignores it


# ---------------------------------------------------------------------------
# AC-2: the received termination records its reason
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-004")
def test_case_manager_records_an_early_remove_as_early(make_payload) -> None:
    dl, case, embargo = _case_with_embargo(
        "https://example.org/cases/tr-early", ended=False
    )
    activity = remove_embargo_from_case_activity(
        embargo, origin=case.id_, actor=OWNER, reason=TerminationReason.EARLY
    )

    result = _receive(dl, make_payload(activity, receiving_actor_id=OWNER))

    assert result.disposition is HandlerDisposition.APPLIED
    ended = cast(VulnerabilityCase, dl.read(case.id_))
    assert ended.em_state is EM.EXITED
    assert ended.embargo_termination == EmbargoTermination.early()


@pytest.mark.spec("EMB-13-003")
def test_case_manager_records_an_end_time_remove_after_the_end_time(
    make_payload,
) -> None:
    dl, case, embargo = _case_with_embargo(
        "https://example.org/cases/tr-end", ended=True
    )
    activity = remove_embargo_from_case_activity(
        embargo,
        origin=case.id_,
        actor=OWNER,
        reason=TerminationReason.END_TIME_REACHED,
    )

    result = _receive(dl, make_payload(activity, receiving_actor_id=OWNER))

    assert result.disposition is HandlerDisposition.APPLIED
    ended = cast(VulnerabilityCase, dl.read(case.id_))
    assert ended.embargo_termination == EmbargoTermination.end_time_reached()


@pytest.mark.spec("EMB-13-003")
def test_case_manager_refuses_an_end_time_remove_before_the_end_time(
    make_payload,
) -> None:
    dl, case, embargo = _case_with_embargo(
        "https://example.org/cases/tr-too-early", ended=False
    )
    activity = remove_embargo_from_case_activity(
        embargo,
        origin=case.id_,
        actor=OWNER,
        reason=TerminationReason.END_TIME_REACHED,
    )

    result = _receive(dl, make_payload(activity, receiving_actor_id=OWNER))

    assert result.disposition is HandlerDisposition.REFUSED
    kept = cast(VulnerabilityCase, dl.read(case.id_))
    assert kept.em_state is EM.ACTIVE
    # Refused before the commit (CLP-10-006): nothing is ledgered.
    assert _ledger(dl, case.id_) == []


# ---------------------------------------------------------------------------
# AC-2: a replica's replay learns the what
# ---------------------------------------------------------------------------


def _teardown_entry(case_id: str, content: object, published) -> dict:
    return {
        "type": "Remove",
        "object": {
            "id": f"{case_id}/embargo_events/e1",
            "type": "EmbargoEvent",
        },
        "content": content,
        "published": published.isoformat(),
        "context": case_id,
    }


def _replay(dl, case_id: str, snapshot: dict) -> Status:
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=case_id,
            log_index=0,
            object_id=f"{case_id}/activities/remove",
            event_type="remove_embargo_event_from_case",
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )
    node = ApplyEmbargoTeardownNode()
    node.datalayer = dl
    node.actor_id = OWNER
    node.activity = type("Carrier", (), {"log_entry": entry})()
    return node.update()


@pytest.mark.spec("EMB-13-003")
def test_replica_replay_records_the_what_the_remove_carries() -> None:
    dl, case, _ = _case_with_embargo(
        "https://example.org/cases/tr-replica", ended=True
    )

    status = _replay(
        dl,
        case.id_,
        _teardown_entry(case.id_, "END_TIME_REACHED", now_utc()),
    )

    assert status == Status.SUCCESS
    ended = cast(VulnerabilityCase, dl.read(case.id_))
    # The entry names no cause, and the replica slot copies the what alone
    # even when it does (EMB-13-005); copying the why is #4748.
    assert ended.embargo_termination == EmbargoTermination.end_time_reached()


@pytest.mark.spec("EMB-13-003")
def test_replica_replay_refuses_an_end_time_entry_before_the_end_time() -> (
    None
):
    dl, case, _ = _case_with_embargo(
        "https://example.org/cases/tr-replica-early", ended=False
    )

    status = _replay(
        dl,
        case.id_,
        _teardown_entry(case.id_, "END_TIME_REACHED", now_utc()),
    )

    assert status == Status.FAILURE
    assert cast(VulnerabilityCase, dl.read(case.id_)).em_state is EM.ACTIVE


@pytest.mark.spec("EMB-13-004")
def test_replica_replay_refuses_an_entry_without_a_reason() -> None:
    dl, case, _ = _case_with_embargo(
        "https://example.org/cases/tr-replica-bad", ended=False
    )

    status = _replay(dl, case.id_, _teardown_entry(case.id_, None, now_utc()))

    assert status == Status.FAILURE
    assert cast(VulnerabilityCase, dl.read(case.id_)).em_state is EM.ACTIVE


@pytest.mark.spec("CLP-02-013")
@pytest.mark.spec("EMB-07-003")
def test_an_owner_remove_after_the_end_time_termination_changes_nothing(
    make_payload,
) -> None:
    """The lazy check ended the embargo first; the case owner's later
    ``Remove`` is admitted and ledgered, and leaves the recorded
    termination as it was."""
    dl, case, embargo = _case_with_embargo(
        "https://example.org/cases/tr-late-owner", ended=True
    )
    run_end_time_check(dl, case.id_, OWNER)
    before = {e.id_ for e in _ledger(dl, case.id_)}
    assert cast(VulnerabilityCase, dl.read(case.id_)).em_state is EM.EXITED
    activity = remove_embargo_from_case_activity(
        embargo, origin=case.id_, actor=OWNER, reason=TerminationReason.EARLY
    )

    result = _receive(dl, make_payload(activity, receiving_actor_id=OWNER))

    assert result.disposition is HandlerDisposition.APPLIED
    ended = cast(VulnerabilityCase, dl.read(case.id_))
    assert ended.em_state is EM.EXITED
    assert ended.embargo_termination == EmbargoTermination.end_time_reached()
    # Admitted at the case layer, so ledgered (CLP-02-013), with no effect.
    (added,) = [e for e in _ledger(dl, case.id_) if e.id_ not in before]
    assert added.log_object_id == activity.id_
