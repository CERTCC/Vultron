import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.wire.as2.factories import create_processing_fault_activity
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault

_RECEIVER = "https://example.org/actors/sender-of-failed-activity"
_EMITTER = "https://example.org/actors/receiver-that-refused"
_CASE_DIVERGED = "https://certcc.github.io/Vultron/ns/errors/LedgerEntryRefused/CaseDiverged"
_FAILED_ACTIVITY = "https://example.org/activities/failed"
_STATUS_REFUSED = "https://vultron.example/faults/status-refused"


@pytest.mark.spec("ASK-07-004")
def test_fault_event_carries_failed_activity_id(make_payload):
    """The received event carries the fault's ``inReplyTo`` as ``failed_activity_id``.

    The parse edge extracts it from the fault object at the wire boundary
    (ASK-07-004, ADR-0032), so core never reads the wire object for it.
    """
    fault = as_ProcessingFault(
        failure_class="https://vultron.example/faults/status-refused",
        in_reply_to=_FAILED_ACTIVITY,
    )
    activity = create_processing_fault_activity(
        actor=_EMITTER,
        fault=fault,
        to=[_RECEIVER],
    )
    event = make_payload(activity)

    assert event.failed_activity_id == _FAILED_ACTIVITY


@pytest.mark.spec("CLP-04-008")
def test_fault_without_in_reply_to_is_logged_as_unnamed(make_payload, caplog):
    """A fault that names no failed activity is still logged and skipped.

    ``inReplyTo`` is optional on the wire, so ``failed_activity_id`` stays
    ``None`` (taken as received) and the WARNING says the activity is not
    named instead of printing ``None``.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    activity = create_processing_fault_activity(
        actor=_EMITTER,
        fault=as_ProcessingFault(failure_class=_STATUS_REFUSED),
        to=[_RECEIVER],
    )
    event = make_payload(activity, at=dl)

    assert event.failed_activity_id is None

    with caplog.at_level(logging.WARNING, logger="vultron"):
        result = CreateProcessingFaultReceivedUseCase(dl, event).execute()

    assert result.disposition == HandlerDisposition.SKIPPED
    warning_messages = [
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert any(
        _EMITTER in msg
        and activity.id_ in msg
        and "not named: no inReplyTo" in msg
        and "'None'" not in msg
        for msg in warning_messages
    ), caplog.text


@pytest.mark.spec("ASK-07-005")
def test_fault_event_carries_failure_class(make_payload):
    """The parse edge carries the fault's class, which picks the response."""
    activity = create_processing_fault_activity(
        actor=_EMITTER,
        fault=as_ProcessingFault(
            failure_class=_CASE_DIVERGED, in_reply_to=_FAILED_ACTIVITY
        ),
        to=[_RECEIVER],
    )

    assert make_payload(activity).failure_class == _CASE_DIVERGED


@pytest.mark.spec("SYNC-16-003")
@pytest.mark.spec("HP-01-003")
def test_case_diverged_fault_naming_no_announce_is_refused(make_payload):
    """A divergence fault with no ``inReplyTo`` names no case to re-seed.

    It is still archived (CLP-10-018), and nothing is sent.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    activity = create_processing_fault_activity(
        actor=_EMITTER,
        fault=as_ProcessingFault(failure_class=_CASE_DIVERGED),
        to=[_RECEIVER],
    )

    result = CreateProcessingFaultReceivedUseCase(
        dl, make_payload(activity, at=dl)
    ).execute()

    assert result.disposition == HandlerDisposition.REFUSED
    assert "names no case" in (result.reason or "")
    assert isinstance(
        dl.read(ReceivedActivityRecord.build_id(activity.id_)),
        ReceivedActivityRecord,
    )
    assert dl.outbox_list() == []


@pytest.mark.spec("HP-01-003")
def test_received_fault_is_skipped_until_ask_register_exists(make_payload):
    """Nothing correlates a NACK to its ask yet (#2883), so it is a no-op.

    The Create that carried it is still archived (CLP-10-017).
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    activity = create_processing_fault_activity(
        actor=_EMITTER,
        fault=as_ProcessingFault(
            failure_class="https://vultron.example/faults/status-refused",
            in_reply_to=_FAILED_ACTIVITY,
        ),
        to=[_RECEIVER],
    )
    event = make_payload(activity, at=dl)

    result = CreateProcessingFaultReceivedUseCase(dl, event).execute()

    assert result.disposition == HandlerDisposition.SKIPPED
    assert result.reason is not None and "#2883" in result.reason
    assert isinstance(
        dl.read(ReceivedActivityRecord.build_id(activity.id_)),
        ReceivedActivityRecord,
    )


@pytest.mark.spec("CLP-04-008")
def test_received_fault_is_logged_naming_its_sender_and_fault(
    make_payload, caplog
):
    """A fault reporting a failure to apply an entry is surfaced in the log.

    The WARNING names the sender, the failed activity id (the fault's
    ``inReplyTo``, ASK-07-004), and the fault object id, each labelled
    correctly (CLP-04-008).
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    fault = as_ProcessingFault(
        failure_class=_CASE_DIVERGED,
        in_reply_to=_FAILED_ACTIVITY,
    )
    activity = create_processing_fault_activity(
        actor=_EMITTER,
        fault=fault,
        to=[_RECEIVER],
    )
    event = make_payload(activity, at=dl)

    with caplog.at_level(logging.WARNING, logger="vultron"):
        CreateProcessingFaultReceivedUseCase(dl, event).execute()

    warning_messages = [
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert any(_EMITTER in msg for msg in warning_messages), caplog.text
    assert any(_FAILED_ACTIVITY in msg for msg in warning_messages), (
        f"failed activity id {_FAILED_ACTIVITY!r} not in log: {caplog.text}"
    )
    assert any(fault.id_ in msg for msg in warning_messages), (
        f"fault id {fault.id_!r} not in log: {caplog.text}"
    )


@pytest.mark.spec("ASK-07-005")
def test_a_create_without_a_parsed_fault_is_refused_at_the_parse_edge():
    """Never read as a fault of no class: the class picks the response."""
    from vultron.core.models.events import MessageSemantics
    from vultron.core.models.events.fault import (
        CreateProcessingFaultReceivedEvent,
    )
    from vultron.wire.as2.errors import VultronParseValidationError
    from vultron.wire.as2.extractor._extract import extract_intent
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    activity = as_Create(
        actor=_EMITTER,
        object_="https://example.org/objects/not-a-fault",
        to=[_RECEIVER],
    )

    with pytest.raises(VultronParseValidationError, match="ASK-07-005"):
        extract_intent(
            activity,
            MessageSemantics.CREATE_PROCESSING_FAULT,
            CreateProcessingFaultReceivedEvent,
        )
