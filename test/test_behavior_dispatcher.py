import logging
from vultron import behavior_dispatcher as bd
from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.enums import as_TransitiveActivityType

MessageSemantics = bd.MessageSemantics


def test_prepare_for_dispatch_parses_activity_and_constructs_dispatchactivity(
    monkeypatch,
):
    """prepare_for_dispatch should parse the passed activity and let pydantic construct the payload model."""
    # keep semantics resolution deterministic
    monkeypatch.setattr(
        bd,
        "find_matching_semantics",
        lambda activity: MessageSemantics.UNKNOWN,
    )

    mapping_activity = as_Create(
        as_id="act-123", actor="actor-1", object="obj-1"
    )
    dispatch_msg = bd.prepare_for_dispatch(mapping_activity)

    assert dispatch_msg.semantic_type == MessageSemantics.UNKNOWN
    assert dispatch_msg.activity_id == "act-123"

    # payload should be a real as_Activity instance
    assert isinstance(dispatch_msg.payload, bd.as_Activity)
    # and retain the expected field values
    assert getattr(dispatch_msg.payload, "as_id", None) == "act-123"
    assert (
        getattr(dispatch_msg.payload, "as_type", None)
        == as_TransitiveActivityType.CREATE
    )


def test_get_dispatcher_returns_local_dispatcher():
    """get_dispatcher should return an object implementing dispatch()."""
    dispatcher = bd.get_dispatcher()
    assert hasattr(dispatcher, "dispatch") and callable(dispatcher.dispatch)


def test_local_dispatcher_dispatch_logs_payload(caplog):
    """
    DirectActivityDispatcher.dispatch should log an info message about dispatching and a debug
    message containing the activity dump (ensure the activity id appears in the debug output).
    """
    caplog.set_level(logging.DEBUG)
    dispatcher = bd.DirectActivityDispatcher()

    # Create a proper VulnerabilityReport and Create activity
    report = VulnerabilityReport(
        name="TEST-REPORT-001", content="Test vulnerability report"
    )
    activity = as_Create(
        as_id="act-xyz",
        actor="https://example.org/users/tester",
        object=report,
    )

    # Construct a DispatchActivity using a real as_Activity payload
    # Use CREATE_REPORT semantics to match the activity structure
    dispatchable = bd.DispatchActivity(
        semantic_type=MessageSemantics.CREATE_REPORT,
        activity_id=activity.as_id,
        payload=activity,
    )

    dispatcher.dispatch(dispatchable)

    info_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.INFO
    ]
    debug_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG
    ]

    assert any("Dispatching activity" in m for m in info_msgs)
    # debug should include the activity id produced by model_dump_json
    assert any("act-xyz" in m for m in debug_msgs)
