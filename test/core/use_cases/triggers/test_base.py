"""Tests for SvcBTTriggerBase and SvcEmbargoTriggerBase hook contracts."""

from unittest.mock import MagicMock

import py_trees.behaviour
import pytest

from vultron.core.use_cases.triggers._base import (
    SvcBTTriggerBase,
    SvcEmbargoTriggerBase,
)

# ---------------------------------------------------------------------------
# Minimal concrete subclasses for testing base-class hooks
# ---------------------------------------------------------------------------


class _MinimalTrigger(SvcBTTriggerBase):
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

    def __init__(self, dl, request, trigger_activity=None):
        super().__init__(dl, request, trigger_activity)
        self.log_called = False

    def _prepare(self) -> None:
        self._actor_id = "https://example.org/actor"

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        from py_trees.behaviours import Success

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
    assert result == {"activity": None}


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
    assert result == {"activity": {"type": "TestActivity"}}


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
        pec_reset=False,
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
