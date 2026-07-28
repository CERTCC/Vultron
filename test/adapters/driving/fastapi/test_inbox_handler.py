import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, MagicMock

import pytest

from vultron.adapters.driving.fastapi import inbox_handler as ih
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def test_prepare_for_dispatch_returns_vultron_event(monkeypatch):
    """prepare_for_dispatch should return a VultronEvent from extract_event."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    import vultron.semantic_registry as registry_mod

    monkeypatch.setattr(
        registry_mod,
        "find_matching_semantics",
        lambda activity: MessageSemantics.UNKNOWN,
    )

    mapping_activity = as_Create(
        id_="act-123", actor="actor-1", object_="obj-1"
    )
    event = ih.prepare_for_dispatch(mapping_activity)

    assert isinstance(event, VultronEvent)
    assert event.semantic_type == MessageSemantics.UNKNOWN
    assert event.activity_id == "act-123"


def test_handle_inbox_item_dispatches(monkeypatch):
    class FakeActivity:
        type_ = "TestActivity"
        name = "fake"

        def model_dump_json(self, **kwargs):
            return '{"name":"fake"}'

    fake_activity = FakeActivity()
    mock_dl = MagicMock()

    # Use a real VultronEvent so that model_copy() works correctly when
    # handle_inbox_item injects receiving_actor_id (HP-09-001).
    fake_event = VultronEvent(
        semantic_type=MessageSemantics.UNKNOWN,
        activity_id="https://example.org/activities/aid",
        actor_id="https://example.org/actors/actor1",
    )
    monkeypatch.setattr(
        ih, "prepare_for_dispatch", lambda activity: fake_event
    )

    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)

    ih.handle_inbox_item(
        actor_id="https://example.org/actors/actor1",
        obj=cast(Any, fake_activity),
        dl=mock_dl,
    )

    mock_dispatcher.dispatch.assert_called_once()
    dispatched_event, dispatched_dl = mock_dispatcher.dispatch.call_args[0]
    assert dispatched_dl is mock_dl
    assert (
        dispatched_event.receiving_actor_id
        == "https://example.org/actors/actor1"
    )


def test_inbox_handler_retries_and_aborts_after_too_many_errors(monkeypatch):
    """inbox_handler retries up to 3 errors then aborts, re-appending the item."""
    item_id = "https://example.org/activities/itm-001"
    item = as_Activity(
        id_=item_id,
        type_="irrelevant",
        actor="https://example.org/actors/test",
        name="itm",
    )

    mock_dl = MagicMock()
    mock_dl.read.return_value = None
    # Inbox contains one item; after abort it should still be there
    _queue = [item_id]
    mock_dl.inbox_list.side_effect = lambda: list(_queue)
    mock_dl.inbox_pop.side_effect = lambda: _queue.pop(0) if _queue else None
    mock_dl.inbox_append.side_effect = lambda x: _queue.append(x)
    # Prevent outbox_handler (called at end of inbox_handler) from looping
    mock_dl.outbox_list.return_value = []

    monkeypatch.setattr(ih, "rehydrate", lambda x, dl=None: item)

    def fail_and_requeue(
        actor_id,
        canonical_actor_id,
        item_id,
        item,
        dl,
        queue_dl,
        dispatcher=None,
    ):
        queue_dl.inbox_append(item_id)
        return False

    monkeypatch.setattr(ih, "_process_inbox_item", fail_and_requeue)

    asyncio.run(ih.inbox_handler("actor-xyz", mock_dl))

    # Item should have been re-appended after each error
    assert item_id in _queue


def test_dispatch_uses_explicit_dispatcher(monkeypatch):
    """dispatch() should use the provided dispatcher, not the global."""
    monkeypatch.setattr(ih, "_DISPATCHER", None)
    explicit_dispatcher = Mock()
    fake_event = cast(
        VultronEvent, SimpleNamespace(activity_id="x", semantic_type="y")
    )
    mock_dl = MagicMock()

    ih.dispatch(fake_event, mock_dl, dispatcher=explicit_dispatcher)

    explicit_dispatcher.dispatch.assert_called_once_with(fake_event, mock_dl)


def test_make_dispatcher_add_participant_status_has_both_ports(monkeypatch):
    """make_dispatcher() must inject *both* sync_port and trigger_activity for
    ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.

    Before the fix, dict.update() overwrote the sync factory with the trigger
    factory for this semantic, leaving sync_port=None and silently skipping the
    log-entry fan-out (issue #628).
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    real_dl = SqliteDataLayer("sqlite:///:memory:")

    # Capture which port_factories map was supplied to get_dispatcher
    captured: dict = {}

    def fake_get_dispatcher(use_case_map, port_factories=None):
        captured["port_factories"] = port_factories
        return Mock()

    monkeypatch.setattr(ih, "get_dispatcher", fake_get_dispatcher)

    ih.make_dispatcher()

    sem = MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    assert (
        sem in captured["port_factories"]
    ), f"{sem} must have a port factory registered"

    factory = captured["port_factories"][sem]
    kwargs = factory(real_dl)

    assert (
        "sync_port" in kwargs
    ), "ADD_PARTICIPANT_STATUS_TO_PARTICIPANT factory must provide sync_port"
    assert isinstance(
        kwargs["sync_port"], SyncActivityAdapter
    ), "sync_port must be a SyncActivityAdapter instance, not None"
    assert (
        "trigger_activity" in kwargs
    ), "ADD_PARTICIPANT_STATUS_TO_PARTICIPANT factory must provide trigger_activity"
    assert isinstance(
        kwargs["trigger_activity"], TriggerActivityAdapter
    ), "trigger_activity must be a TriggerActivityAdapter instance, not None"


def test_make_dispatcher_overlapping_semantics_raises(monkeypatch):
    """make_dispatcher() must raise AssertionError when semantics sets overlap.

    This guards against a recurrence of issue #628, where a silent dict.update()
    overwrite dropped a required port.
    """
    from vultron.core.models.events import MessageSemantics

    # Inject an artificial overlap: put one sync-only semantic into the
    # trigger set as well.
    overlapping = frozenset({MessageSemantics.ADD_NOTE_TO_CASE})
    monkeypatch.setattr(ih, "_TRIGGER_ACTIVITY_PORT_SEMANTICS", overlapping)

    with pytest.raises(AssertionError, match="overlap"):
        ih.make_dispatcher()


def test_make_dispatcher_does_not_mutate_global(monkeypatch):
    """make_dispatcher() must not touch the module-level _DISPATCHER."""
    sentinel = object()
    monkeypatch.setattr(ih, "_DISPATCHER", sentinel)

    result = ih.make_dispatcher()

    assert ih._DISPATCHER is sentinel
    assert result is not sentinel
    monkeypatch.setattr(ih, "_DISPATCHER", None)
    fake_event = cast(
        VultronEvent, SimpleNamespace(activity_id="x", semantic_type="y")
    )
    mock_dl = MagicMock()
    with pytest.raises(RuntimeError, match="not initialised"):
        ih.dispatch(fake_event, mock_dl)


def test_init_dispatcher_sets_dispatcher(monkeypatch):
    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", None)
    monkeypatch.setattr(
        ih,
        "get_dispatcher",
        lambda use_case_map, port_factories=None: mock_dispatcher,
    )

    ih.init_dispatcher()
    assert ih._DISPATCHER is mock_dispatcher


def test_dispatch_or_defer_inbox_item_queues_unknown_case_context(monkeypatch):
    actor_id = "https://example.org/actors/participant"
    case_id = "https://example.org/cases/case-unknown"
    item_id = "https://example.org/activities/add-note-1"
    shared_dl = SqliteDataLayer("sqlite:///:memory:")
    queue_dl = shared_dl.clone_for_actor(actor_id)
    item = as_Activity(
        id_=item_id,
        type_="Add",
        actor="https://example.org/actors/case-actor",
        context=case_id,
        name="queued-note",
    )
    fake_event = VultronEvent(
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        activity_id=item_id,
        actor_id="https://example.org/actors/case-actor",
    )

    monkeypatch.setattr(
        ih, "prepare_for_dispatch", lambda activity: fake_event
    )
    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)

    result = ih._dispatch_or_defer_inbox_item(
        actor_id=actor_id,
        obj=item,
        dl=shared_dl,
        queue_dl=queue_dl,
    )

    assert result is None
    pending = queue_dl.read(VultronPendingCaseInbox.build_id(case_id))
    assert isinstance(pending, VultronPendingCaseInbox)
    assert pending.activity_ids == [item_id]
    mock_dispatcher.dispatch.assert_not_called()


def test_inbox_handler_replays_deferred_items_after_case_announce(monkeypatch):
    actor_id = "https://example.org/actors/participant"
    case_id = "https://example.org/cases/case-replay"
    note_id = "https://example.org/activities/add-note-2"
    announce_id = "https://example.org/activities/announce-case-1"
    shared_dl = SqliteDataLayer("sqlite:///:memory:")
    shared_dl.save(as_Service(id_=actor_id, name="Participant"))
    queue_dl = shared_dl.clone_for_actor(actor_id)
    queue_dl.inbox_append(note_id)
    queue_dl.inbox_append(announce_id)

    note_item = as_Activity(
        id_=note_id,
        type_="Add",
        actor="https://example.org/actors/case-actor",
        context=case_id,
        name="deferred-note",
    )
    announce_item = as_Activity(
        id_=announce_id,
        type_="Announce",
        actor="https://example.org/actors/case-actor",
        context=case_id,
        name="announce-case",
    )
    items = {note_id: note_item, announce_id: announce_item}

    def fake_prepare(activity: as_Activity) -> VultronEvent:
        if activity.id_ == note_id:
            return VultronEvent(
                semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
                activity_id=note_id,
                actor_id="https://example.org/actors/case-actor",
            )
        return VultronEvent(
            semantic_type=MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
            activity_id=announce_id,
            actor_id="https://example.org/actors/case-actor",
        )

    dispatched: list[str] = []

    def fake_dispatch(event: VultronEvent, dl: SqliteDataLayer) -> None:
        dispatched.append(event.activity_id)
        if event.semantic_type == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE:
            dl.save(as_VulnerabilityCase(id_=case_id, name="Replica"))

    async def fake_outbox_handler(*_args: object, **_kwargs: object) -> None:
        return None

    mock_dispatcher = Mock()
    mock_dispatcher.dispatch.side_effect = fake_dispatch
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)
    monkeypatch.setattr(ih, "prepare_for_dispatch", fake_prepare)
    monkeypatch.setattr(
        ih, "rehydrate", lambda item_id, dl=None: items[item_id]
    )
    monkeypatch.setattr(ih, "outbox_handler", fake_outbox_handler)

    asyncio.run(ih.inbox_handler(actor_id, shared_dl, queue_dl))

    assert dispatched == [announce_id, note_id]
    assert queue_dl.read(VultronPendingCaseInbox.build_id(case_id)) is None


# ---------------------------------------------------------------------------
# CBT-03 / CBT-05-003: Pre-bootstrap queue expiry tests (issue #500)
# ---------------------------------------------------------------------------


def test_pre_bootstrap_activity_queued_not_dispatched(monkeypatch):
    """AC-5: Pre-bootstrap CaseActor activities are queued but NOT dispatched.

    Covers CBT-05-003 (first bullet): pre-bootstrap messages remain unapplied.
    """
    actor_id = "https://example.org/actors/reporter"
    case_id = "https://example.org/cases/cbt-ac5"
    activity_id = "https://example.org/activities/cbt-ac5-note"
    shared_dl = SqliteDataLayer("sqlite:///:memory:")
    queue_dl = shared_dl.clone_for_actor(actor_id)

    item = as_Activity(
        id_=activity_id,
        type_="Add",
        actor="https://example.org/actors/case-actor",
        context=case_id,
        name="pre-bootstrap-note",
    )
    fake_event = VultronEvent(
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        activity_id=activity_id,
        actor_id="https://example.org/actors/case-actor",
    )
    monkeypatch.setattr(
        ih, "prepare_for_dispatch", lambda activity: fake_event
    )
    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)

    result = ih._dispatch_or_defer_inbox_item(
        actor_id=actor_id,
        obj=item,
        dl=shared_dl,
        queue_dl=queue_dl,
    )

    assert (
        result is None
    ), "Pre-bootstrap activity should be deferred, not dispatched"
    mock_dispatcher.dispatch.assert_not_called()

    pending = queue_dl.read(VultronPendingCaseInbox.build_id(case_id))
    assert isinstance(pending, VultronPendingCaseInbox)
    assert activity_id in pending.activity_ids
    assert pending.case_actor_id == "https://example.org/actors/case-actor"


def test_pending_case_queue_expires_drops_and_warns(monkeypatch, caplog):
    """AC-6: Expired pre-bootstrap queue is dropped with a WARNING.

    Covers CBT-05-003 (second bullet): expire safely.
    """
    import logging
    from datetime import datetime, timedelta, timezone

    actor_id = "https://example.org/actors/reporter"
    case_id = "https://example.org/cases/cbt-ac6"
    activity_id = "https://example.org/activities/cbt-ac6-note"
    shared_dl = SqliteDataLayer("sqlite:///:memory:")
    queue_dl = shared_dl.clone_for_actor(actor_id)

    # Create a pending queue entry that is already "old" (queued 10 minutes ago)
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    pending = VultronPendingCaseInbox(
        case_id=case_id,
        activity_ids=[activity_id],
        case_actor_id="https://example.org/actors/case-actor",
    )
    pending.queued_at = old_time
    queue_dl.save(pending)

    with caplog.at_level(logging.WARNING, logger="vultron"):
        expired = ih._expire_pending_case_activities(
            case_id=case_id,
            actor_id=actor_id,
            dl=shared_dl,
            queue_dl=queue_dl,
            timeout_seconds=60,  # 1 minute; queue is 10 minutes old
        )

    assert expired is True
    assert queue_dl.read(VultronPendingCaseInbox.build_id(case_id)) is None
    assert any("Dropping expired" in r.message for r in caplog.records)
    assert any(activity_id in r.message for r in caplog.records)


def test_inbox_handler_uses_actor_dl_for_queue_pop_and_shared_dl_for_dispatch(
    monkeypatch,
):
    """AC-2: inbox_handler pops from actor_dl; rehydration/dispatch use dl.

    When ``actor_dl`` is passed as a separate actor-scoped instance (distinct
    from the shared ``dl``), queue operations (``inbox_list``, ``inbox_pop``)
    must use ``actor_dl`` while rehydration and dispatch must receive the
    shared ``dl`` (ARCH-13-003, ARCH-13-004).
    """
    actor_id = "https://example.org/actors/participant"
    activity_id = "https://example.org/activities/act-dual-dl"

    shared_dl = SqliteDataLayer("sqlite:///:memory:")
    shared_dl.save(
        as_Service(id_=actor_id, name="Participant")  # type: ignore[call-arg]
    )
    actor_dl = shared_dl.clone_for_actor(actor_id)

    # Item is queued on the actor-scoped DL only
    actor_dl.inbox_append(activity_id)

    item = as_Activity(
        id_=activity_id,
        type_="Create",
        actor="https://example.org/actors/other",
        name="dual-dl-test",
    )
    rehydrate_dl_args: list = []

    def capture_rehydrate(item_id, dl=None):
        rehydrate_dl_args.append(dl)
        return item

    monkeypatch.setattr(ih, "rehydrate", capture_rehydrate)

    fake_event = VultronEvent(
        semantic_type=MessageSemantics.UNKNOWN,
        activity_id=activity_id,
        actor_id="https://example.org/actors/other",
    )
    monkeypatch.setattr(
        ih, "prepare_for_dispatch", lambda activity: fake_event
    )

    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)

    async def fake_outbox_handler(*args, **kwargs):
        return None

    monkeypatch.setattr(ih, "outbox_handler", fake_outbox_handler)

    asyncio.run(ih.inbox_handler(actor_id, shared_dl, actor_dl=actor_dl))

    # Queue pop occurred on actor_dl — its inbox must now be empty
    assert actor_dl.inbox_list() == [], (
        "actor_dl inbox must be empty after processing; "
        "inbox_handler must pop from actor_dl, not shared_dl"
    )

    # Rehydration must have received the shared dl
    assert len(rehydrate_dl_args) == 1
    assert (
        rehydrate_dl_args[0] is shared_dl
    ), "rehydrate must be called with shared dl, not actor_dl"

    # Dispatch must have been called with the shared dl
    mock_dispatcher.dispatch.assert_called_once()
    _, dispatch_dl = mock_dispatcher.dispatch.call_args.args
    assert (
        dispatch_dl is shared_dl
    ), "dispatch must be called with shared dl, not actor_dl"


def test_inbox_port_factories_has_no_demo_import():
    """inbox_port_factories.py must not import from vultron.demo (AC-2, CFG-07-005)."""
    import ast
    import pathlib

    src = (
        pathlib.Path(__file__).parents[4]
        / "vultron"
        / "adapters"
        / "driving"
        / "fastapi"
        / "inbox_port_factories.py"
    ).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                module = ",".join(alias.name for alias in node.names)
            assert "vultron.demo" not in module, (
                f"inbox_port_factories.py must not import from vultron.demo; "
                f"found: {module!r}"
            )


def test_resolve_actor_config_delegates_to_load_actor_config(monkeypatch):
    """_resolve_actor_config() must call load_actor_config() (AC-2, CFG-07-005).

    The production adapter must not import SeedConfig; instead it delegates
    to load_actor_config() from vultron.config.
    """
    from vultron.config.actor import ActorConfig
    import vultron.adapters.driving.fastapi.inbox_port_factories as pf
    import vultron.config.app as app_mod

    called = []

    def fake_load_actor_config():
        called.append(True)
        return ActorConfig(auto_create_case=False)

    monkeypatch.setattr(app_mod, "load_actor_config", fake_load_actor_config)
    # Patch the name in pf's namespace (imported at module load time)
    monkeypatch.setattr(pf, "load_actor_config", fake_load_actor_config)

    result = pf._resolve_actor_config()
    assert called, "load_actor_config must have been called"
    assert isinstance(result, ActorConfig)
    assert result.auto_create_case is False


def test_submit_report_port_factory_injects_actor_config(monkeypatch):
    """_submit_report_port_factory returns actor_config from load_actor_config.

    When load_actor_config() is available, the factory must include an
    ``actor_config`` key so that ``SubmitReportReceivedUseCase`` can
    honour the local actor's ``auto_create_case`` policy (CM-15-001,
    issue #1319).
    """
    from vultron.config.actor import ActorConfig
    import vultron.adapters.driving.fastapi.inbox_port_factories as pf

    fake_actor_config = ActorConfig(auto_create_case=False)
    monkeypatch.setattr(pf, "_resolve_actor_config", lambda: fake_actor_config)

    real_dl = SqliteDataLayer("sqlite:///:memory:")
    kwargs = pf._submit_report_port_factory(real_dl)

    assert "actor_config" in kwargs, "factory must include actor_config"
    assert isinstance(kwargs["actor_config"], ActorConfig)
    assert kwargs["actor_config"].auto_create_case is False
    assert "sync_port" in kwargs
    assert "trigger_activity" in kwargs


def test_submit_report_port_factory_omits_actor_config_when_unavailable(
    monkeypatch,
):
    """_submit_report_port_factory omits actor_config when SeedConfig fails.

    When SeedConfig cannot be loaded (e.g. env vars absent), the factory
    must still return sync_port + trigger_activity and must NOT include an
    ``actor_config`` key — so the use case falls back to always-create (CM-15-001).
    """
    import vultron.adapters.driving.fastapi.inbox_port_factories as pf

    monkeypatch.setattr(pf, "_resolve_actor_config", lambda: None)

    real_dl = SqliteDataLayer("sqlite:///:memory:")
    kwargs = pf._submit_report_port_factory(real_dl)

    assert "actor_config" not in kwargs
    assert "sync_port" in kwargs
    assert "trigger_activity" in kwargs


def test_make_dispatcher_submit_report_uses_actor_config_factory(monkeypatch):
    """make_dispatcher() must register _submit_report_port_factory for SUBMIT_REPORT.

    SUBMIT_REPORT was moved out of _SYNC_AND_TRIGGER_PORT_SEMANTICS to
    _SUBMIT_REPORT_SEMANTICS (issue #1319), so it must be wired to the
    factory that also injects actor_config.
    """
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.config.actor import ActorConfig
    import vultron.adapters.driving.fastapi.inbox_port_factories as pf

    captured: dict = {}

    def fake_get_dispatcher(use_case_map, port_factories=None):
        captured["port_factories"] = port_factories
        return Mock()

    monkeypatch.setattr(ih, "get_dispatcher", fake_get_dispatcher)
    monkeypatch.setattr(
        pf,
        "_resolve_actor_config",
        lambda: ActorConfig(auto_create_case=False),
    )

    ih.make_dispatcher()

    sem = MessageSemantics.SUBMIT_REPORT
    assert (
        sem in captured["port_factories"]
    ), "SUBMIT_REPORT must have a factory"

    real_dl = SqliteDataLayer("sqlite:///:memory:")
    kwargs = captured["port_factories"][sem](real_dl)

    assert isinstance(kwargs.get("sync_port"), SyncActivityAdapter)
    assert isinstance(kwargs.get("trigger_activity"), TriggerActivityAdapter)
    assert isinstance(kwargs.get("actor_config"), ActorConfig)
    assert kwargs["actor_config"].auto_create_case is False


def test_make_dispatcher_ac2_auto_create_false_no_case_via_dispatcher(
    monkeypatch,
):
    """AC-2: DirectActivityDispatcher honours auto_create_case=False end-to-end.

    With _resolve_actor_config returning auto_create_case=False,
    dispatching an inbound Offer(Report) via DirectActivityDispatcher must
    store the report and Offer activity but must NOT create a
    as_VulnerabilityCase and must leave the actor's outbox empty (CM-15-001,
    issue #1319).
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.config.actor import ActorConfig
    from vultron.core.models.activity import VultronActivity
    from vultron.core.models.case_actor import VultronCaseActor
    from vultron.core.models.events.report import SubmitReportReceivedEvent
    from vultron.core.models.report import VultronReport
    import vultron.adapters.driving.fastapi.inbox_port_factories as pf

    VENDOR_ID = "https://example.org/actors/vendor-ac2"
    FINDER_ID = "https://example.org/users/finder-ac2"
    REPORT_ID = "https://example.org/reports/r-ac2"
    OFFER_ID = "https://example.org/activities/offer-ac2"

    # Inject auto_create_case=False via the factory that make_dispatcher uses.
    monkeypatch.setattr(
        pf,
        "_resolve_actor_config",
        lambda: ActorConfig(auto_create_case=False),
    )

    # Build a real dispatcher the same way make_dispatcher() does, but
    # without the full FastAPI lifespan — call make_dispatcher directly.
    dispatcher = ih.make_dispatcher()

    dl = SqliteDataLayer("sqlite:///:memory:")
    dl.save(VultronCaseActor(id_=VENDOR_ID))

    report = VultronReport(id_=REPORT_ID)
    activity = VultronActivity(
        id_=OFFER_ID,
        type_="Offer",
        actor=FINDER_ID,
        to=[VENDOR_ID],
    )
    event = SubmitReportReceivedEvent(
        semantic_type=MessageSemantics.SUBMIT_REPORT,
        activity_id=OFFER_ID,
        actor_id=FINDER_ID,
        object_=report,
        activity=activity,
        receiving_actor_id=VENDOR_ID,
    )

    dispatcher.dispatch(event, dl)

    # Report and Offer are persisted.
    assert dl.read(REPORT_ID) is not None, "VulnerabilityReport must be stored"
    offer_ids = [row.get("id_") for row in dl.get_all("Offer")]
    assert OFFER_ID in offer_ids, "Offer activity must be stored"
    # No case created.
    assert (
        dl.get_all("VulnerabilityCase") == []
    ), "No as_VulnerabilityCase should be created when auto_create_case=False"
    # Outbox must remain empty.
    assert (
        dl.outbox_list_for_actor(VENDOR_ID) == []
    ), "Outbox must be empty when auto_create_case=False"


def test_pending_case_queue_expiry_emits_question(monkeypatch):
    """AC-7: A replay Question is appended to the actor outbox on expiry.

    Covers CBT-05-003 (third bullet): generate a replay request.
    """
    from datetime import datetime, timedelta, timezone

    actor_id = "https://example.org/actors/reporter"
    case_id = "https://example.org/cases/cbt-ac7"
    activity_id = "https://example.org/activities/cbt-ac7-note"
    case_actor_id = "https://example.org/actors/case-actor"
    shared_dl = SqliteDataLayer("sqlite:///:memory:")
    queue_dl = shared_dl.clone_for_actor(actor_id)

    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    pending = VultronPendingCaseInbox(
        case_id=case_id,
        activity_ids=[activity_id],
        case_actor_id=case_actor_id,
    )
    pending.queued_at = old_time
    queue_dl.save(pending)

    expired = ih._expire_pending_case_activities(
        case_id=case_id,
        actor_id=actor_id,
        dl=shared_dl,
        queue_dl=queue_dl,
        timeout_seconds=60,
    )

    assert expired is True

    outbox = queue_dl.outbox_list()
    assert (
        len(outbox) == 1
    ), "One Question should have been queued in the outbox"

    question_id = outbox[0]
    from vultron.wire.as2.vocab.base.objects.activities.intransitive import (
        as_Question,
    )

    question = shared_dl.read(question_id)
    assert isinstance(question, as_Question)
    assert question.context == case_id
    assert question.actor == actor_id
    assert question.to == case_actor_id
