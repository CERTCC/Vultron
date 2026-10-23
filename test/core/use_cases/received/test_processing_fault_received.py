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
            in_reply_to="https://example.org/activities/failed",
        ),
        to=[_RECEIVER],
    )
    event = make_payload(activity)

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

    The line names the sender and the ``Create`` that carried the fault. It
    does not yet name the failed activity the fault's ``inReplyTo`` names,
    which the event does not carry (#5129).
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    activity = create_processing_fault_activity(
        actor=_EMITTER,
        fault=as_ProcessingFault(
            failure_class=_CASE_DIVERGED,
            in_reply_to="https://example.org/activities/failed",
        ),
        to=[_RECEIVER],
    )
    event = make_payload(activity)

    with caplog.at_level(logging.WARNING, logger="vultron"):
        CreateProcessingFaultReceivedUseCase(dl, event).execute()

    assert any(
        r.levelno >= logging.WARNING
        and _EMITTER in r.getMessage()
        and activity.id_ in r.getMessage()
        for r in caplog.records
    ), caplog.text
