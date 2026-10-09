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
