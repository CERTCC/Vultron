import logging
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from vultron.core.dispatcher import DirectActivityDispatcher, get_dispatcher
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import (
    AddNoteToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    CreateReportReceivedEvent,
    MessageSemantics,
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.report import VultronReport
from vultron.errors import VultronValidationError
from vultron.wire.as2.factories import (
    em_propose_embargo_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseStub,
)


@dataclass
class _LedgerEntry:
    case_id: str
    log_index: int


def test_get_dispatcher_returns_local_dispatcher():
    """get_dispatcher should return an object implementing dispatch()."""
    dispatcher = get_dispatcher(use_case_map={})
    assert hasattr(dispatcher, "dispatch") and callable(dispatcher.dispatch)


def test_local_dispatcher_dispatch_logs_payload(caplog):
    """DirectActivityDispatcher.dispatch should log info + debug messages."""
    caplog.set_level(logging.DEBUG)
    mock_dl = MagicMock()
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: MagicMock()}
    )

    event = CreateReportReceivedEvent(
        activity_id="act-xyz",
        actor_id="https://example.org/users/tester",
        object_=VultronReport(content="test report"),
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
    case = VulnerabilityCase(id_="https://example.org/cases/case-gate")
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
    use_case_instance = MagicMock()
    use_case_class = MagicMock(return_value=use_case_instance)
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.ADD_NOTE_TO_CASE: use_case_class}
    )

    actor_id = "https://example.org/users/late-joiner"
    case = VulnerabilityCase(id_="https://example.org/cases/case-gate-ok")
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


def test_dispatcher_blocks_when_case_ledger_prefix_has_gaps():
    mock_dl = MagicMock()
    use_case_class = MagicMock()
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.ADD_NOTE_TO_CASE: use_case_class}
    )

    actor_id = "https://example.org/users/late-joiner-gap"
    case = VulnerabilityCase(id_="https://example.org/cases/case-gate-gap")
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
        target=VulnerabilityCaseStub(id_=participant_id),
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
        embargo=EmbargoEvent(
            id_=f"{case_id}/embargo_events/e1", content="Embargo proposal"
        ),
        context=case_id,
        actor="https://example.org/users/vendor",
        id_=f"{case_id}/embargo_proposals/1",
    )
    event = RejectInviteToEmbargoOnCaseReceivedEvent(
        activity_id="act-gate-4",
        actor_id=actor_id,
        object_=invite,
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
        call.args == (invite.id_,) for call in mock_dl.read.call_args_list
    )
    assert any(
        call.args == (state_id,) for call in mock_dl.read.call_args_list
    )
    use_case_class.assert_not_called()
