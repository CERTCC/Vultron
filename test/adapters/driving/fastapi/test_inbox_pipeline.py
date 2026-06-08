from typing import TypeAlias

from pytest import MonkeyPatch

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_pipeline import InboxPipeline
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.use_cases.received.actor import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case import CreateCaseReceivedUseCase
from vultron.core.use_cases.received.embargo import (
    InviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.note import AddNoteToCaseReceivedUseCase
from vultron.core.use_cases.received.report import CreateReportReceivedUseCase
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    AnnounceLogEntryReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    add_status_to_case_activity,
    announce_log_entry_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    em_propose_embargo_activity,
    rm_create_report_activity,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry
from vultron.wire.as2.vocab.objects.case_status import CaseStatus
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

PipelineFixture: TypeAlias = tuple[InboxPipeline, SqliteDataLayer]

SENDER_ID = "https://example.org/actors/sender"
RECEIVER_ID = "https://example.org/actors/receiver"
CASE_ID = "https://example.org/cases/case-ibp"
UNKNOWN_CASE_ID = "https://example.org/cases/case-unknown"


def _patch_execute_with_marker(
    monkeypatch: MonkeyPatch, use_case_class: type, marker_id: str
) -> None:
    def _execute(self) -> None:
        self._dl.save(as_Note(id_=marker_id, content=marker_id))

    monkeypatch.setattr(use_case_class, "execute", _execute)


def _base_case(case_id: str = CASE_ID) -> VulnerabilityCase:
    return VulnerabilityCase(id_=case_id, name="CASE-IBP")


def _save_and_process(
    test_pipeline: PipelineFixture,
    *,
    activity: PersistableModel,
    objects: list[PersistableModel],
):
    pipeline, dl = test_pipeline
    for obj in objects:
        dl.save(obj)
    dl.save(activity)
    return pipeline.process(activity.id_), dl


def test_routing_safety_net_report_domain(test_pipeline, monkeypatch):
    marker_id = "https://example.org/markers/report"
    _patch_execute_with_marker(
        monkeypatch, CreateReportReceivedUseCase, marker_id
    )
    report = VulnerabilityReport(
        id_="https://example.org/reports/r-ibp-1",
        content="report content",
    )
    activity = rm_create_report_activity(
        report, actor=SENDER_ID, to=[RECEIVER_ID]
    )

    event, dl = _save_and_process(
        test_pipeline, activity=activity, objects=[report]
    )

    assert event is not None
    assert event.semantic_type.name == "CREATE_REPORT"
    assert dl.read(marker_id) is not None


def test_routing_safety_net_case_domain(test_pipeline, monkeypatch):
    marker_id = "https://example.org/markers/case"
    _patch_execute_with_marker(
        monkeypatch, CreateCaseReceivedUseCase, marker_id
    )
    case = _base_case()
    activity = create_case_activity(case, actor=SENDER_ID, to=[RECEIVER_ID])

    event, dl = _save_and_process(
        test_pipeline, activity=activity, objects=[case]
    )

    assert event is not None
    assert event.semantic_type.name == "CREATE_CASE"
    assert dl.read(marker_id) is not None


def test_routing_safety_net_embargo_domain(test_pipeline, monkeypatch):
    marker_id = "https://example.org/markers/embargo"
    _patch_execute_with_marker(
        monkeypatch, InviteToEmbargoOnCaseReceivedUseCase, marker_id
    )
    case = _base_case()
    embargo = EmbargoEvent(
        id_="https://example.org/embargoes/e-ibp-1",
        context=case,
    )
    activity = em_propose_embargo_activity(
        embargo, context=case.id_, actor=SENDER_ID, to=[RECEIVER_ID]
    )

    event, dl = _save_and_process(
        test_pipeline, activity=activity, objects=[case, embargo]
    )

    assert event is not None
    assert event.semantic_type.name == "INVITE_TO_EMBARGO_ON_CASE"
    assert dl.read(marker_id) is not None


def test_routing_safety_net_note_domain(test_pipeline, monkeypatch):
    marker_id = "https://example.org/markers/note"
    _patch_execute_with_marker(
        monkeypatch, AddNoteToCaseReceivedUseCase, marker_id
    )
    case = _base_case()
    note = as_Note(id_="https://example.org/notes/n-ibp-1", content="hello")
    activity = add_note_to_case_activity(
        note,
        target=case,
        context=case.id_,
        actor=SENDER_ID,
        to=[RECEIVER_ID],
    )

    event, dl = _save_and_process(
        test_pipeline, activity=activity, objects=[case, note]
    )

    assert event is not None
    assert event.semantic_type.name == "ADD_NOTE_TO_CASE"
    assert dl.read(marker_id) is not None


def test_routing_safety_net_actor_domain(test_pipeline, monkeypatch):
    marker_id = "https://example.org/markers/actor"
    _patch_execute_with_marker(
        monkeypatch, AnnounceVulnerabilityCaseReceivedUseCase, marker_id
    )
    case = _base_case()
    activity = announce_vulnerability_case_activity(
        case,
        actor=SENDER_ID,
        to=[RECEIVER_ID],
    )

    event, dl = _save_and_process(
        test_pipeline, activity=activity, objects=[case]
    )

    assert event is not None
    assert event.semantic_type.name == "ANNOUNCE_VULNERABILITY_CASE"
    assert dl.read(marker_id) is not None


def test_routing_safety_net_status_domain(test_pipeline, monkeypatch):
    marker_id = "https://example.org/markers/status"
    _patch_execute_with_marker(
        monkeypatch, AddCaseStatusToCaseReceivedUseCase, marker_id
    )
    case = _base_case()
    status = CaseStatus(
        id_="https://example.org/status/cs-ibp-1", context=case.id_
    )
    activity = add_status_to_case_activity(
        status,
        target=case,
        context=case.id_,
        actor=SENDER_ID,
        to=[RECEIVER_ID],
    )

    event, dl = _save_and_process(
        test_pipeline, activity=activity, objects=[case, status]
    )

    assert event is not None
    assert event.semantic_type.name == "ADD_CASE_STATUS_TO_CASE"
    assert dl.read(marker_id) is not None


def test_routing_safety_net_sync_domain(test_pipeline, monkeypatch):
    marker_id = "https://example.org/markers/sync"
    _patch_execute_with_marker(
        monkeypatch, AnnounceLogEntryReceivedUseCase, marker_id
    )
    entry = CaseLogEntry(
        id_="https://example.org/log/entry-ibp-1",
        case_id=CASE_ID,
        log_index=0,
        log_object_id="https://example.org/activities/a-1",
        event_type="announce",
        prev_log_hash="0",
        entry_hash="1",
    )
    activity = announce_log_entry_activity(
        entry,
        context=CASE_ID,
        actor=SENDER_ID,
        to=[RECEIVER_ID],
    )

    event, dl = _save_and_process(
        test_pipeline, activity=activity, objects=[_base_case(), entry]
    )

    assert event is not None
    assert event.semantic_type.name == "ANNOUNCE_CASE_LOG_ENTRY"
    assert dl.read(marker_id) is not None


def test_process_defers_unknown_case_activity(test_pipeline):
    pipeline, dl = test_pipeline
    note = as_Note(id_="https://example.org/notes/n-ibp-def", content="defer")
    activity = add_note_to_case_activity(
        note,
        target=UNKNOWN_CASE_ID,
        context=UNKNOWN_CASE_ID,
        actor=SENDER_ID,
        to=[RECEIVER_ID],
    )

    dl.save(note)
    dl.save(activity)

    result = pipeline.process(activity.id_)

    assert result is None
    queue_dl = dl.clone_for_actor(RECEIVER_ID)
    pending = queue_dl.read(VultronPendingCaseInbox.build_id(UNKNOWN_CASE_ID))
    assert isinstance(pending, VultronPendingCaseInbox)
    assert activity.id_ in pending.activity_ids
