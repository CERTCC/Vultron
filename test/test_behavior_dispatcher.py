import logging
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from vultron.core.dispatcher import DirectActivityDispatcher, get_dispatcher
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreObject
from vultron.core.models.events import (
    AddNoteToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    CreateReportReceivedEvent,
    MessageSemantics,
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import HandlerResult
from vultron.errors import (
    VultronApiHandlerNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.factories import (
    em_propose_embargo_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


@dataclass
class _LedgerEntry:
    case_id: str
    log_index: int


def _use_case_returning(
    result: object = HandlerResult.applied(),
) -> tuple[MagicMock, MagicMock]:
    """Return ``(instance, class)`` mocks whose ``execute()`` yields *result*.

    *result* defaults to ``HandlerResult.applied()``, the verdict every
    received use case returns today. ``None`` is passed through, so a use
    case that still returns nothing can be tested.
    """
    instance = MagicMock()
    instance.execute.return_value = result
    return instance, MagicMock(return_value=instance)


def test_get_dispatcher_returns_local_dispatcher():
    """get_dispatcher should return an object implementing dispatch()."""
    dispatcher = get_dispatcher(use_case_map={})
    assert hasattr(dispatcher, "dispatch") and callable(dispatcher.dispatch)


def test_local_dispatcher_dispatch_logs_payload(caplog):
    """DirectActivityDispatcher.dispatch should log info + debug messages."""
    caplog.set_level(logging.DEBUG)
    mock_dl = MagicMock()
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: _use_case_returning()[1]}
    )

    event = CreateReportReceivedEvent(
        activity_id="act-xyz",
        actor_id="https://example.org/users/tester",
        object_=VulnerabilityReport(content="test report"),
        activity=VultronActivity(
            type_="Create", actor="https://example.org/users/tester"
        ),
    )

    dispatcher.dispatch(event, mock_dl)

    info_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.INFO
    ]
    debug_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG
    ]

    assert any("Dispatching" in m for m in info_msgs)
    assert any("act-xyz" in m for m in debug_msgs)


def test_dispatcher_blocks_gated_semantic_without_contiguous_genesis_prefix():
    mock_dl = MagicMock()
    use_case_class = MagicMock()
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.ADD_NOTE_TO_CASE: use_case_class}
    )

    actor_id = "https://example.org/users/late-joiner"
    case = as_VulnerabilityCase(id_="https://example.org/cases/case-gate")
    event = AddNoteToCaseReceivedEvent(
        activity_id="act-gate-1",
        actor_id=actor_id,
        target=case,
        activity=VultronActivity(type_="Add", actor=actor_id),
    )
    state_id = VultronReplicationState(
        case_id=case.id_,
        peer_id=actor_id,
    ).id_
    mock_dl.list_objects.return_value = [
        _LedgerEntry(case_id=case.id_, log_index=0),
        _LedgerEntry(case_id=case.id_, log_index=1),
        _LedgerEntry(case_id=case.id_, log_index=2),
    ]
    mock_dl.read.return_value = VultronReplicationState(
        case_id=case.id_,
        peer_id=actor_id,
        join_backfill_target_index=3,
        join_backfill_last_sent_index=-1,
        join_backfill_complete=False,
    )

    with pytest.raises(VultronValidationError) as excinfo:
        dispatcher.dispatch(event, mock_dl)
    exc = excinfo.value
    assert "no contiguous canonical ledger prefix" in str(exc)
    mock_dl.read.assert_called_with(state_id)
    use_case_class.assert_not_called()


def test_dispatcher_allows_gated_semantic_with_contiguous_prefix_but_tip_lag():
    mock_dl = MagicMock()
    use_case_instance, use_case_class = _use_case_returning()
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.ADD_NOTE_TO_CASE: use_case_class}
    )

    actor_id = "https://example.org/users/late-joiner"
    case = as_VulnerabilityCase(id_="https://example.org/cases/case-gate-ok")
    event = AddNoteToCaseReceivedEvent(
        activity_id="act-gate-2",
        actor_id=actor_id,
        target=case,
        activity=VultronActivity(type_="Add", actor=actor_id),
    )
    mock_dl.list_objects.return_value = [
        _LedgerEntry(case_id=case.id_, log_index=0),
        _LedgerEntry(case_id=case.id_, log_index=1),
        _LedgerEntry(case_id=case.id_, log_index=2),
        _LedgerEntry(case_id=case.id_, log_index=3),
    ]
    mock_dl.read.return_value = VultronReplicationState(
        case_id=case.id_,
        peer_id=actor_id,
        join_backfill_target_index=3,
        join_backfill_last_sent_index=1,
        join_backfill_complete=False,
    )

    dispatcher.dispatch(event, mock_dl)
    use_case_class.assert_called_once()
    use_case_instance.execute.assert_called_once()


def test_dispatcher_allows_gated_semantic_without_replication_state():
    mock_dl = MagicMock()
    use_case_instance, use_case_class = _use_case_returning()
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.ADD_NOTE_TO_CASE: use_case_class}
    )

    actor_id = "https://example.org/users/case-owner"
    case = as_VulnerabilityCase(
        id_="https://example.org/cases/case-gate-owner"
    )
    event = AddNoteToCaseReceivedEvent(
        activity_id="act-gate-owner",
        actor_id=actor_id,
        target=case,
        activity=VultronActivity(type_="Add", actor=actor_id),
    )
    mock_dl.list_objects.return_value = [
        _LedgerEntry(case_id=case.id_, log_index=0),
        _LedgerEntry(case_id=case.id_, log_index=1),
    ]
    mock_dl.read.return_value = None

    dispatcher.dispatch(event, mock_dl)
    use_case_class.assert_called_once()
    use_case_instance.execute.assert_called_once()


def test_dispatcher_allows_gated_semantic_when_backfill_complete():
    """A genesis participant whose replication state was created by the
    Reject(CaseLedgerEntry) sync path carries the -1/True field defaults
    (join_backfill_last_sent_index=-1, join_backfill_complete=True).  The
    gate must treat a completed backfill as holding the full prefix and NOT
    reject on the -1 sentinel — otherwise a settled genesis participant (e.g.
    the Finder reporting RM.CLOSED) is wrongly blocked and the case never
    reaches auto-close.  Regression for PR #1746 fvcv-handoff failure.
    """
    mock_dl = MagicMock()
    use_case_instance, use_case_class = _use_case_returning()
    dispatcher = DirectActivityDispatcher(
        use_case_map={
            MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: use_case_class
        }
    )

    actor_id = "https://example.org/users/finder"
    participant_id = "https://example.org/cases/case-closed/participants/p1"
    case_id = "https://example.org/cases/case-closed"
    event = AddParticipantStatusToParticipantReceivedEvent(
        activity_id="act-closed",
        actor_id=actor_id,
        object_=ParticipantStatus(
            id_=f"{participant_id}/status/closed",
            context=case_id,
        ),
        target=CoreObject(id_=participant_id, type_="CaseParticipant"),
        activity=VultronActivity(type_="Add", actor=actor_id),
    )
    mock_dl.list_objects.return_value = [
        _LedgerEntry(case_id=case_id, log_index=0),
        _LedgerEntry(case_id=case_id, log_index=1),
    ]
    mock_dl.read.return_value = VultronReplicationState(
        case_id=case_id,
        peer_id=actor_id,
        join_backfill_target_index=-1,
        join_backfill_last_sent_index=-1,
        join_backfill_complete=True,
    )

    dispatcher.dispatch(event, mock_dl)
    use_case_class.assert_called_once()
    use_case_instance.execute.assert_called_once()


def test_dispatcher_blocks_when_case_ledger_prefix_has_gaps():
    mock_dl = MagicMock()
    use_case_class = MagicMock()
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.ADD_NOTE_TO_CASE: use_case_class}
    )

    actor_id = "https://example.org/users/late-joiner-gap"
    case = as_VulnerabilityCase(id_="https://example.org/cases/case-gate-gap")
    event = AddNoteToCaseReceivedEvent(
        activity_id="act-gate-gap",
        actor_id=actor_id,
        target=case,
        activity=VultronActivity(type_="Add", actor=actor_id),
    )
    state_id = VultronReplicationState(
        case_id=case.id_,
        peer_id=actor_id,
    ).id_
    mock_dl.list_objects.return_value = [
        _LedgerEntry(case_id=case.id_, log_index=1),
        _LedgerEntry(case_id=case.id_, log_index=3),
        _LedgerEntry(case_id=case.id_, log_index=5),
        _LedgerEntry(case_id=case.id_, log_index=6),
    ]
    mock_dl.read.return_value = VultronReplicationState(
        case_id=case.id_,
        peer_id=actor_id,
        join_backfill_target_index=6,
        join_backfill_last_sent_index=1,
        join_backfill_complete=False,
    )

    with pytest.raises(VultronValidationError):
        dispatcher.dispatch(event, mock_dl)

    mock_dl.read.assert_called_with(state_id)
    use_case_class.assert_not_called()


def test_dispatcher_uses_case_context_for_participant_status_gate():
    mock_dl = MagicMock()
    use_case_class = MagicMock()
    dispatcher = DirectActivityDispatcher(
        use_case_map={
            MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: use_case_class
        }
    )

    actor_id = "https://example.org/users/late-joiner"
    participant_id = "https://example.org/cases/case-gate-part/participants/p1"
    case_id = "https://example.org/cases/case-gate-part"
    event = AddParticipantStatusToParticipantReceivedEvent(
        activity_id="act-gate-3",
        actor_id=actor_id,
        object_=ParticipantStatus(
            id_=f"{participant_id}/status/1",
            context=case_id,
        ),
        target=CoreObject(id_=participant_id, type_="CaseParticipant"),
        activity=VultronActivity(type_="Add", actor=actor_id),
    )
    state_id = VultronReplicationState(
        case_id=case_id,
        peer_id=actor_id,
    ).id_
    mock_dl.list_objects.return_value = [
        _LedgerEntry(case_id=case_id, log_index=0),
        _LedgerEntry(case_id=case_id, log_index=1),
    ]
    mock_dl.read.return_value = VultronReplicationState(
        case_id=case_id,
        peer_id=actor_id,
        join_backfill_target_index=1,
        join_backfill_last_sent_index=-1,
        join_backfill_complete=False,
    )

    with pytest.raises(VultronValidationError):
        dispatcher.dispatch(event, mock_dl)

    mock_dl.read.assert_called_with(state_id)
    use_case_class.assert_not_called()


def test_dispatcher_resolves_case_for_reject_embargo_invite_gate():
    mock_dl = MagicMock()
    use_case_class = MagicMock()
    dispatcher = DirectActivityDispatcher(
        use_case_map={
            MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: use_case_class
        }
    )

    actor_id = "https://example.org/users/late-joiner"
    case_id = "https://example.org/cases/case-gate-embargo"
    invite = em_propose_embargo_activity(
        embargo=as_EmbargoEvent(
            id_=f"{case_id}/embargo_events/e1",
            content="Embargo proposal",
            context=case_id,
            end_time=days_from_now_utc(45),
        ),
        context=case_id,
        actor="https://example.org/users/vendor",
        id_=f"{case_id}/embargo_proposals/1",
    )
    event = RejectInviteToEmbargoOnCaseReceivedEvent(
        activity_id="act-gate-4",
        actor_id=actor_id,
        # Event slots carry the extractor's minimal core references; the
        # dispatcher reads the full invite back from the DataLayer.
        object_=CoreObject(id_=invite.id_, type_=invite.type_),
        inner_context=CoreObject(id_=case_id, type_="VulnerabilityCase"),
        activity=VultronActivity(type_="Reject", actor=actor_id),
    )
    state_id = VultronReplicationState(
        case_id=case_id,
        peer_id=actor_id,
    ).id_

    def _read_side_effect(object_id: str):
        if object_id == invite.id_:
            return invite
        if object_id == state_id:
            return VultronReplicationState(
                case_id=case_id,
                peer_id=actor_id,
                join_backfill_target_index=2,
                join_backfill_last_sent_index=-1,
                join_backfill_complete=False,
            )
        return None

    mock_dl.read.side_effect = _read_side_effect
    mock_dl.list_objects.return_value = [
        _LedgerEntry(case_id=case_id, log_index=0),
        _LedgerEntry(case_id=case_id, log_index=1),
        _LedgerEntry(case_id=case_id, log_index=2),
    ]

    with pytest.raises(VultronValidationError):
        dispatcher.dispatch(event, mock_dl)

    assert any(
        call.args == (state_id,) for call in mock_dl.read.call_args_list
    )
    use_case_class.assert_not_called()


def _create_report_event() -> CreateReportReceivedEvent:
    return CreateReportReceivedEvent(
        activity_id="act-verdict",
        actor_id="https://example.org/users/tester",
        object_=VulnerabilityReport(content="test report"),
        activity=VultronActivity(
            type_="Create", actor="https://example.org/users/tester"
        ),
    )


@pytest.mark.spec("UCORG-05-010")
@pytest.mark.parametrize(
    "verdict",
    [
        HandlerResult.applied(),
        HandlerResult.skipped("duplicate"),
        HandlerResult.deferred("awaiting predecessor"),
        HandlerResult.refused("not a participant"),
    ],
)
def test_dispatch_returns_the_use_case_verdict(verdict):
    """The dispatcher carries the handler's result instead of dropping it."""
    _, use_case_class = _use_case_returning(verdict)
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: use_case_class}
    )

    assert dispatcher.dispatch(_create_report_event(), MagicMock()) == verdict


@pytest.mark.spec("UCORG-05-001")
@pytest.mark.parametrize("not_a_verdict", [None, {"ok": True}, "applied"])
def test_dispatch_rejects_a_use_case_that_returns_no_handler_result(
    not_a_verdict,
):
    """A non-HandlerResult return is a contract breach and fails fast."""
    _, use_case_class = _use_case_returning(not_a_verdict)
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: use_case_class}
    )

    with pytest.raises(TypeError, match="not HandlerResult"):
        dispatcher.dispatch(_create_report_event(), MagicMock())


@pytest.mark.spec("DR-03-002")
def test_dispatch_lets_a_handler_exception_propagate():
    """An exception raised inside ``execute()`` escapes ``dispatch()`` unchanged.

    The dispatcher converts only ``UnroutableActivityError`` into a verdict;
    every other handler failure belongs to the adapter boundary (IE-06-004).
    """

    class HandlerFailure(RuntimeError):
        pass

    class RaisingUseCase:
        def __init__(self, dl, request) -> None:
            pass

        def execute(self) -> HandlerResult:
            raise HandlerFailure("handler blew up")

    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: RaisingUseCase}
    )

    with pytest.raises(HandlerFailure, match="handler blew up"):
        dispatcher.dispatch(_create_report_event(), MagicMock())


@pytest.mark.spec("HP-02-001")
@pytest.mark.spec("HP-02-002")
@pytest.mark.spec("HP-05-001")
def test_dispatch_refuses_a_semantics_with_no_registered_use_case():
    """The handler is resolved from ``event.semantic_type`` before any runs.

    A semantics with no entry in the routing table is a contract breach the
    dispatcher raises on (HP-05-001), not a silent no-op; no ``execute()`` is
    reached.
    """
    dispatcher = DirectActivityDispatcher(use_case_map={})

    with pytest.raises(VultronApiHandlerNotFoundError, match="create_report"):
        dispatcher.dispatch(_create_report_event(), MagicMock())


@pytest.mark.spec("HP-06-001")
def test_dispatch_logs_handler_entry_at_debug_with_handler_name(caplog):
    """Handler entry is one DEBUG record naming the handler class and activity."""
    caplog.set_level(logging.DEBUG, logger="vultron.core.dispatcher")

    class NamedStubUseCase:
        """A real class, so the asserted name is the handler's, not a mock's."""

        def __init__(self, dl, request) -> None:
            pass

        def execute(self) -> HandlerResult:
            return HandlerResult.applied()

    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: NamedStubUseCase}
    )

    dispatcher.dispatch(_create_report_event(), MagicMock())

    entries = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.DEBUG and "Entering handler" in r.getMessage()
    ]
    assert len(entries) == 1, caplog.text
    assert "NamedStubUseCase" in entries[0]
    assert "act-verdict" in entries[0]
    assert str(MessageSemantics.CREATE_REPORT) in entries[0]
