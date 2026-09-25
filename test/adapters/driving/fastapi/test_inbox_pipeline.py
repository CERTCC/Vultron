import logging
from typing import TypeAlias

import pytest
from pytest import MonkeyPatch

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_pipeline import (
    MAX_REQUEUE_ATTEMPTS,
    InboxPipeline,
)
from vultron.errors import (
    VultronProtocolViolationError,
    VultronValidationError,
)
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
    AnnounceLedgerEntryReceivedUseCase,
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
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
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


def _base_case(case_id: str = CASE_ID) -> as_VulnerabilityCase:
    return as_VulnerabilityCase(id_=case_id, name="CASE-IBP")


def _store_note_activity(dl: SqliteDataLayer, note_id: str) -> str:
    """Store a case, a note and an Add(Note, Case) activity; return its ID."""
    case = _base_case()
    note = as_Note(id_=note_id, content=note_id)
    activity = add_note_to_case_activity(
        note,
        target=case,
        context=case.id_,
        actor=SENDER_ID,
        to=[RECEIVER_ID],
    )
    for obj in (case, note, activity):
        dl.save(obj)
    return activity.id_


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
    report = as_VulnerabilityReport(
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
    embargo = as_EmbargoEvent(
        id_="https://example.org/embargoes/e-ibp-1",
        context=case.id_,
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
    status = as_CaseStatus(
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
        monkeypatch, AnnounceLedgerEntryReceivedUseCase, marker_id
    )
    entry = as_CaseLedgerEntry(
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
    assert event.semantic_type.name == "ANNOUNCE_CASE_LEDGER_ENTRY"
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


def test_create_case_with_correct_context_not_deferred(
    test_pipeline, monkeypatch
):
    """AC-4 (ADR-0045): Create(VulnerabilityCase) with context=case_uri is NOT
    deferred even when the case does not yet exist in the DataLayer.

    This is the bootstrap path: CREATE_CASE is in CASE_BOOTSTRAP_SEMANTICS, so
    the deferral guard is bypassed and the activity is dispatched immediately.
    The corrected CP-05-003 field assignment (context=case_uri, not Accept URI)
    ensures the deferral guard works here: if context carried the Accept URI, the
    guard would read an activity URI as the case ID and queue it indefinitely.
    """
    marker_id = "https://example.org/markers/create-case-ac4"
    _patch_execute_with_marker(
        monkeypatch, CreateCaseReceivedUseCase, marker_id
    )

    new_case_id = "https://example.org/cases/case-ac4-new"
    case = as_VulnerabilityCase(id_=new_case_id, name="AC4-New")
    # Build a Create(VulnerabilityCase) whose context = case_uri (ADR-0045).
    activity = create_case_activity(
        case,
        actor=SENDER_ID,
        to=[RECEIVER_ID],
        context=new_case_id,
    )

    pipeline, dl = test_pipeline
    # The DataLayer stores object_ by URI reference (not inline). Both the
    # VulnerabilityCase and the activity must be saved so rehydration can
    # reconstruct the full wire object.  The case is "new" in the sense
    # that no use-case has processed it yet — CreateCaseReceivedUseCase
    # would normally establish it, which is what the monkeypatched marker
    # proves was invoked.
    dl.save(case)
    dl.save(activity)

    result = pipeline.process(activity.id_)

    assert result is not None, (
        "Create(VulnerabilityCase) bootstrap MUST NOT be deferred"
        " — it must be dispatched immediately (ADR-0045 AC-4)"
    )
    assert result.semantic_type.name == "CREATE_CASE"
    # Marker proves execute() ran (i.e. the activity was dispatched, not deferred).
    assert dl.read(marker_id) is not None


def test_process_requeues_activity_on_validation_error(
    test_pipeline, monkeypatch
):
    """VultronValidationError from dispatch must re-queue the item for retry.

    State-dependent validation errors (e.g. genesis-backfill-not-started) clear
    once upstream state progresses.  Treating them as permanent failures silently
    drops activities that would succeed on the next cycle.  The handler must
    re-queue rather than discard (#2766).
    """
    import vultron.adapters.driving.fastapi.inbox_pipeline as ip_module

    pipeline, dl = test_pipeline
    activity_id = _store_note_activity(
        dl, "https://example.org/notes/n-ibp-val-err"
    )

    def _raise_validation_error(**kwargs):
        raise VultronValidationError("injected validation failure")

    monkeypatch.setattr(ip_module, "dispatch", _raise_validation_error)

    result = pipeline.process(activity_id)

    assert result is None, "VultronValidationError must return None"
    queue_dl = dl.clone_for_actor(RECEIVER_ID)
    assert (
        activity_id in queue_dl.inbox_list()
    ), "A transient validation failure MUST re-queue the activity for retry (#2766)"


# ---------------------------------------------------------------------------
# Regression: rehydrate() outside try (#3044 / #2905)
# ---------------------------------------------------------------------------


def test_rehydrate_protocol_violation_returns_none_not_raises(
    test_pipeline, monkeypatch
):
    """AC-2 (#3044): VultronProtocolViolationError from rehydrate() must not
    propagate — it is a permanent failure, return None, do not re-queue.

    Before the fix rehydrate() was called outside the try/except block in
    InboxPipeline.process(), so this exception escaped the pipeline entirely.
    """
    import vultron.adapters.driving.fastapi.inbox_pipeline as ip_module

    def _raise_protocol(*args, **kwargs):
        raise VultronProtocolViolationError("rehydrate protocol violation")

    monkeypatch.setattr(ip_module, "rehydrate", _raise_protocol)

    pipeline, dl = test_pipeline
    result = pipeline.process("https://example.org/activities/bad-rehydrate")

    assert result is None, (
        "VultronProtocolViolationError from rehydrate() must be caught and"
        " return None rather than propagating (#3044)"
    )


def test_rehydrate_generic_exception_returns_none_not_raises(
    test_pipeline, monkeypatch
):
    """AC-2 (#3044): Any exception from rehydrate() must not propagate out of
    the pipeline — return None and re-queue for transient failures.

    Before the fix an unhandled exception from rehydrate() escaped
    InboxPipeline.process() entirely.
    """
    import vultron.adapters.driving.fastapi.inbox_pipeline as ip_module

    def _raise_generic(*args, **kwargs):
        raise RuntimeError("simulated rehydration failure")

    monkeypatch.setattr(ip_module, "rehydrate", _raise_generic)

    pipeline, dl = test_pipeline
    activity_id = "https://example.org/activities/transient-rehydrate"
    result = pipeline.process(activity_id)

    assert result is None, (
        "A generic exception from rehydrate() must be caught and return None"
        " (#3044)"
    )


def test_protocol_violation_error_does_not_requeue(test_pipeline, monkeypatch):
    """VultronProtocolViolationError from dispatch must NOT re-queue the item.

    A protocol violation (e.g. bare-URI participants in Create(VulnerabilityCase))
    is a permanent failure — the same malformed message will fail on every retry.
    Re-queuing it creates an infinite retry loop (#2861).
    """
    import vultron.adapters.driving.fastapi.inbox_pipeline as ip_module

    pipeline, dl = test_pipeline
    activity_id = _store_note_activity(
        dl, "https://example.org/notes/n-ibp-proto-viol"
    )

    def _raise_protocol_violation(**kwargs):
        raise VultronProtocolViolationError(
            "injected protocol violation — bare-URI participant"
        )

    monkeypatch.setattr(ip_module, "dispatch", _raise_protocol_violation)

    result = pipeline.process(activity_id)

    assert result is None, "VultronProtocolViolationError must return None"
    queue_dl = dl.clone_for_actor(RECEIVER_ID)
    assert (
        activity_id not in queue_dl.inbox_list()
    ), "A protocol violation MUST NOT re-queue — it creates an infinite retry loop (#2861)"


# ---------------------------------------------------------------------------
# Regression: re-queue without a retry limit (#2901)
# ---------------------------------------------------------------------------


def _drain_cycles(
    pipeline: InboxPipeline, queue_dl: SqliteDataLayer, activity_id: str
) -> int:
    """Poll the inbox like a drain loop until it is empty; return the number
    of times *activity_id* was processed."""
    processed = 0
    pipeline.process(activity_id)
    processed += 1
    while (item_id := queue_dl.inbox_pop()) is not None:
        assert item_id == activity_id
        pipeline.process(item_id)
        processed += 1
        assert processed <= MAX_REQUEUE_ATTEMPTS + 1, "unbounded re-queue"
    return processed


@pytest.mark.parametrize(
    "exc",
    [
        VultronValidationError("permanent validation failure"),
        RuntimeError("persistent unexpected failure"),
    ],
    ids=["validation-error", "generic-exception"],
)
def test_requeue_stops_after_max_attempts(
    test_pipeline: PipelineFixture,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
) -> None:
    """An item that fails on every attempt is re-queued at most
    ``MAX_REQUEUE_ATTEMPTS`` times, then dropped — not looped forever (#2901).
    """
    import vultron.adapters.driving.fastapi.inbox_pipeline as ip_module

    pipeline, dl = test_pipeline
    activity_id = _store_note_activity(
        dl, "https://example.org/notes/n-ibp-requeue-cap"
    )

    def _raise(**_kwargs: object) -> None:
        raise exc

    monkeypatch.setattr(ip_module, "dispatch", _raise)
    queue_dl = dl.clone_for_actor(RECEIVER_ID)

    with caplog.at_level(logging.ERROR, logger=ip_module.__name__):
        assert _drain_cycles(pipeline, queue_dl, activity_id) == (
            MAX_REQUEUE_ATTEMPTS + 1
        )
    assert activity_id not in queue_dl.inbox_list()
    drops = [r for r in caplog.records if "retry limit reached" in r.message]
    assert len(drops) == 1
    assert drops[0].levelno == logging.ERROR
    assert activity_id in drops[0].message
    assert RECEIVER_ID in drops[0].message


def test_successful_dispatch_resets_requeue_budget(
    test_pipeline: PipelineFixture, monkeypatch: MonkeyPatch
) -> None:
    """A dispatch that succeeds clears the item's failure count, so a later
    failure of the same item gets the full retry budget again (#2901)."""
    import vultron.adapters.driving.fastapi.inbox_pipeline as ip_module

    pipeline, dl = test_pipeline
    activity_id = _store_note_activity(
        dl, "https://example.org/notes/n-ibp-requeue-reset"
    )
    queue_dl = dl.clone_for_actor(RECEIVER_ID)
    fail = True

    def _dispatch(**_kwargs: object) -> None:
        if fail:
            raise VultronValidationError("transient validation failure")

    monkeypatch.setattr(ip_module, "dispatch", _dispatch)

    for _ in range(MAX_REQUEUE_ATTEMPTS):
        pipeline.process(queue_dl.inbox_pop() or activity_id)
    fail = False
    assert pipeline.process(queue_dl.inbox_pop() or activity_id) is not None

    fail = True
    assert _drain_cycles(pipeline, queue_dl, activity_id) == (
        MAX_REQUEUE_ATTEMPTS + 1
    )


def test_failure_after_dispatch_is_still_bounded(
    test_pipeline: PipelineFixture, monkeypatch: MonkeyPatch
) -> None:
    """A failure raised after a successful dispatch — here, the pending-case
    replay that follows a case bootstrap — still spends the retry budget, so
    the item is not re-dispatched forever (#2901)."""
    import vultron.adapters.driving.fastapi.inbox_pipeline as ip_module

    pipeline, dl = test_pipeline
    activity_id = _store_note_activity(
        dl, "https://example.org/notes/n-ibp-requeue-replay"
    )

    def _replay_fails(**_kwargs: object) -> None:
        raise RuntimeError("replay failure")

    monkeypatch.setattr(ip_module, "dispatch", lambda **_kwargs: None)
    monkeypatch.setattr(ip_module, "is_case_bootstrap", lambda _event: True)
    monkeypatch.setattr(
        ip_module, "_replay_pending_case_activities", _replay_fails
    )
    queue_dl = dl.clone_for_actor(RECEIVER_ID)

    assert _drain_cycles(pipeline, queue_dl, activity_id) == (
        MAX_REQUEUE_ATTEMPTS + 1
    )
    assert activity_id not in queue_dl.inbox_list()


def test_deferral_resets_requeue_budget(
    test_pipeline: PipelineFixture, monkeypatch: MonkeyPatch
) -> None:
    """An item deferred to the pending-case queue after earlier failures is
    replayed with the full retry budget, not what was left of it (#2901)."""
    import vultron.adapters.driving.fastapi.inbox_pipeline as ip_module

    pipeline, dl = test_pipeline
    activity_id = _store_note_activity(
        dl, "https://example.org/notes/n-ibp-requeue-defer"
    )
    queue_dl = dl.clone_for_actor(RECEIVER_ID)

    def _raise(**_kwargs: object) -> None:
        raise VultronValidationError("transient validation failure")

    monkeypatch.setattr(ip_module, "dispatch", _raise)
    for _ in range(MAX_REQUEUE_ATTEMPTS):
        pipeline.process(queue_dl.inbox_pop() or activity_id)

    class _NoCaseYet:
        """Stand-in that no stored case matches, forcing the deferral path."""

    with monkeypatch.context() as m:
        m.setattr(ip_module, "VulnerabilityCase", _NoCaseYet)
        assert pipeline.process(queue_dl.inbox_pop() or activity_id) is None
    assert activity_id not in queue_dl.inbox_list()

    assert _drain_cycles(pipeline, queue_dl, activity_id) == (
        MAX_REQUEUE_ATTEMPTS + 1
    )
