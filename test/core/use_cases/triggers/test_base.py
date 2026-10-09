"""Tests for the SvcBTTriggerBase family's hook contracts."""

from unittest.mock import MagicMock

import py_trees.behaviour
import pytest

from vultron.core.models.use_case_result import ActivityResult, OfferResult
from vultron.core.use_cases.triggers._base import (
    SvcActivityTriggerBase,
    SvcBTTriggerBase,
    SvcEmbargoTriggerBase,
)

_ACTOR_ID = "https://example.org/actor"
_CASE_ID = "https://example.org/cases/c1"

# ---------------------------------------------------------------------------
# Minimal concrete subclasses for testing base-class hooks
# ---------------------------------------------------------------------------


class _MinimalTrigger(SvcActivityTriggerBase):
    """Simplest concrete subclass: records hook calls and raises nothing."""

    def __init__(self, dl, request, trigger_activity=None):
        super().__init__(dl, request, trigger_activity)
        self.prepare_called = False
        self.build_tree_called = False
        self.handle_result_called = False

    def _prepare(self) -> None:
        self.prepare_called = True
        self._actor_id = "https://example.org/actor"

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        self.build_tree_called = True
        from py_trees.behaviours import Success

        return Success(name="test-tree")

    def _handle_result(self) -> None:
        self.handle_result_called = True


class _EmbargoTrigger(SvcEmbargoTriggerBase):
    """Minimal concrete embargo subclass for testing."""

    _assertion_event_type = "test_embargo_event"

    def __init__(self, dl, request, trigger_activity=None, subject=None):
        super().__init__(dl, request, trigger_activity)
        self.log_called = False
        self.tree_built = False
        self._subject: str | None = subject
        self._case = MagicMock(id_=_CASE_ID)

    def _prepare(self) -> None:
        self._actor_id = _ACTOR_ID

    def _assertion_subject(self) -> str | None:
        return self._subject

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        from py_trees.behaviours import Success

        self.tree_built = True
        return Success(name="embargo-test-tree")

    def _log_lifecycle_result(self) -> None:
        self.log_called = True


# ---------------------------------------------------------------------------
# SvcBTTriggerBase: missing TriggerActivityPort raises RuntimeError
# ---------------------------------------------------------------------------


def test_missing_trigger_activity_raises():
    """execute() raises RuntimeError when trigger_activity is None."""
    uc = _MinimalTrigger(
        dl=MagicMock(), request=object(), trigger_activity=None
    )
    with pytest.raises(RuntimeError, match="requires a TriggerActivityPort"):
        uc.execute()


def test_missing_trigger_activity_calls_prepare_first():
    """_prepare() is called before the TriggerActivityPort guard."""
    uc = _MinimalTrigger(
        dl=MagicMock(), request=object(), trigger_activity=None
    )
    with pytest.raises(RuntimeError):
        uc.execute()
    assert uc.prepare_called, "_prepare() must run before the port guard"


# ---------------------------------------------------------------------------
# SvcBTTriggerBase: hook ordering with a mock trigger port
# ---------------------------------------------------------------------------


def test_hooks_called_in_order():
    """Template method calls hooks in the correct sequence."""
    uc = _MinimalTrigger(
        dl=MagicMock(), request=object(), trigger_activity=MagicMock()
    )
    result = uc.execute()

    assert uc.prepare_called
    assert uc.build_tree_called
    assert uc.handle_result_called
    assert result == ActivityResult(
        activity=None,
        emitting_actor_id="https://example.org/actor",
    )
    assert result.model_dump() == {
        "activity": None,
        "emitting_actor_id": "https://example.org/actor",
    }


def test_execute_returns_captured_activity():
    """execute() returns the activity captured by _build_tree's closure."""

    class _CapturingTrigger(_MinimalTrigger):
        def _build_tree(self) -> py_trees.behaviour.Behaviour:
            self.build_tree_called = True
            self._captured["activity"] = {"type": "TestActivity"}
            from py_trees.behaviours import Success

            return Success(name="capturing-tree")

    uc = _CapturingTrigger(
        dl=MagicMock(), request=object(), trigger_activity=MagicMock()
    )
    result = uc.execute()
    assert result == ActivityResult(
        activity={"type": "TestActivity"},
        emitting_actor_id="https://example.org/actor",
    )


def test_invalid_result_is_an_internal_error_not_a_validation_error():
    """A result the subtype refuses is a use-case bug, never a client 422.

    The routers translate pydantic ``ValidationError`` to 422, so the template
    re-raises a construction failure as ``RuntimeError``.
    """

    class _BrokenTrigger(_MinimalTrigger):
        def _build_result(self) -> ActivityResult:
            return ActivityResult.model_validate(
                {"activity": None, "emitting_actor_id": ""}
            )

    uc = _BrokenTrigger(
        dl=MagicMock(), request=object(), trigger_activity=MagicMock()
    )
    with pytest.raises(RuntimeError, match="built an invalid result"):
        uc.execute()


def test_execute_returns_the_subtype_a_generic_subclass_binds():
    """A verb whose body differs binds the generic base to its own subtype."""

    class _OfferTrigger(SvcBTTriggerBase[OfferResult]):
        def _prepare(self) -> None:
            self._actor_id = "https://example.org/actor"

        def _build_tree(self) -> py_trees.behaviour.Behaviour:
            self._captured["offer"] = {"type": "Offer"}
            from py_trees.behaviours import Success

            return Success(name="offer-tree")

        def _handle_result(self) -> None:
            pass

        def _build_result(self) -> OfferResult:
            return OfferResult(offer=self._captured.get("offer"))

    uc = _OfferTrigger(
        dl=MagicMock(), request=object(), trigger_activity=MagicMock()
    )
    result = uc.execute()
    assert result == OfferResult(offer={"type": "Offer"})
    assert set(result.model_dump()) == {"offer"}


# ---------------------------------------------------------------------------
# SvcEmbargoTriggerBase: _handle_result validates lifecycle_result
# ---------------------------------------------------------------------------


def test_embargo_handle_result_raises_when_lifecycle_result_missing():
    """_handle_result raises RuntimeError when lifecycle_result is absent."""
    uc = _EmbargoTrigger(
        dl=MagicMock(),
        request=object(),
        trigger_activity=MagicMock(),
    )
    uc._result_out = {}
    with pytest.raises(RuntimeError, match="did not capture lifecycle result"):
        uc._handle_result()


def test_embargo_handle_result_raises_for_wrong_type():
    """_handle_result raises RuntimeError for a non-EmbargoLifecycleResult."""
    uc = _EmbargoTrigger(
        dl=MagicMock(),
        request=object(),
        trigger_activity=MagicMock(),
    )
    uc._result_out = {"lifecycle_result": "not-the-right-type"}
    with pytest.raises(RuntimeError, match="did not capture lifecycle result"):
        uc._handle_result()


def test_embargo_handle_result_stores_lifecycle_result_and_delegates():
    """_handle_result stores lifecycle_result and calls _log_lifecycle_result."""
    from vultron.core.services.embargo_lifecycle import EmbargoLifecycleResult
    from vultron.core.states.em import EM

    lr = EmbargoLifecycleResult(
        em_before=EM.NONE,
        em_after=EM.PROPOSED,
        case_changed=True,
        case_embargo_changed=False,
    )
    uc = _EmbargoTrigger(
        dl=MagicMock(),
        request=object(),
        trigger_activity=MagicMock(),
    )
    uc._result_out = {"lifecycle_result": lr}
    uc._handle_result()
    assert uc._lifecycle_result is lr
    assert uc.log_called


@pytest.mark.spec("EP-09-008", "SYNC-11-002")
def test_embargo_handle_result_records_the_ask_and_skips_the_lifecycle():
    """An ask of the CASE_MANAGER is recorded pending; no lifecycle result.

    The non-manager arm writes no EM state, so ``lifecycle_result`` is absent
    and is not demanded.
    """
    from vultron.core.behaviors.embargo.trigger_tree import (
        ASSERTED_ACTIVITY_KEY,
    )
    from vultron.core.models.pending_assertion import (
        get_pending_assertion_store,
    )

    uc = _EmbargoTrigger(
        dl=MagicMock(),
        request=object(),
        trigger_activity=MagicMock(),
        subject="proposal-1",
    )
    uc._actor_id = _ACTOR_ID
    uc._result_out = {ASSERTED_ACTIVITY_KEY: "https://example.org/act/1"}
    uc._handle_result()

    assert not uc.log_called
    pending = get_pending_assertion_store(_ACTOR_ID).pending_for_subject(
        _CASE_ID, "test_embargo_event", "proposal-1"
    )
    assert pending is not None
    assert pending.object_id == "https://example.org/act/1"


@pytest.mark.spec("SYNC-11-002")
def test_embargo_duplicate_ask_is_suppressed_before_the_tree_runs():
    """A repeat of a pending ask is reported with no activity, not re-sent."""
    from vultron.core.models.pending_assertion import (
        record_pending_assertion,
    )

    record_pending_assertion(
        _ACTOR_ID,
        _CASE_ID,
        "test_embargo_event",
        "https://example.org/act/1",
        subject_id="proposal-1",
    )
    uc = _EmbargoTrigger(
        dl=MagicMock(),
        request=object(),
        trigger_activity=MagicMock(),
        subject="proposal-1",
    )
    result = uc.execute()

    assert result == ActivityResult(activity=None, emitting_actor_id=_ACTOR_ID)
    assert not uc.tree_built


def test_embargo_ask_about_another_subject_is_not_suppressed():
    """Only the same subject is a duplicate; other asks still run."""
    from vultron.core.models.pending_assertion import (
        record_pending_assertion,
    )

    record_pending_assertion(
        _ACTOR_ID,
        _CASE_ID,
        "test_embargo_event",
        "https://example.org/act/1",
        subject_id="proposal-1",
    )
    uc = _EmbargoTrigger(
        dl=MagicMock(),
        request=object(),
        trigger_activity=MagicMock(),
        subject="proposal-2",
    )
    uc._actor_id = _ACTOR_ID
    assert uc._suppressed_duplicate() is None


# ---------------------------------------------------------------------------
# SvcBTTriggerBase: the WireRenderPort reaches the tree (ARCH-20-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("ARCH-20-004")
def test_wire_render_port_is_published_to_the_tree():
    """The base hands its port to ``BTBridge``, which publishes it.

    Trigger trees commit ledger entries whose snapshots only the port can
    render (ARCH-20-001), so a subclass must not have to wire it itself.
    """
    seen: dict[str, object] = {}
    port = object()

    class _ReadsPort(py_trees.behaviour.Behaviour):
        def update(self) -> py_trees.common.Status:
            seen["port"] = py_trees.blackboard.Blackboard.storage.get(
                "/wire_render_port"
            )
            return py_trees.common.Status.SUCCESS

    class _PortTrigger(SvcActivityTriggerBase):
        def _prepare(self) -> None:
            self._actor_id = "https://example.org/actor"

        def _build_tree(self) -> py_trees.behaviour.Behaviour:
            return _ReadsPort(name="reads-port")

        def _handle_result(self) -> None:
            pass

    _PortTrigger(
        dl=MagicMock(),
        request=object(),
        trigger_activity=MagicMock(),
        wire_render_port=port,  # type: ignore[arg-type]
    ).execute()

    assert seen["port"] is port
