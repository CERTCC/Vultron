"""Tests for vultron.demo.fuzzer.messaging."""

import pytest
import py_trees

from vultron.demo.fuzzer.base import UniformSucceedFail
from vultron.demo.fuzzer.messaging import FollowUpOnErrorMessage


class TestFollowUpOnErrorMessage:
    """Tests for FollowUpOnErrorMessage."""

    def test_is_behaviour(self):
        """Must be a py_trees Behaviour."""
        node = FollowUpOnErrorMessage()
        assert isinstance(node, py_trees.behaviour.Behaviour)

    def test_has_docstring(self):
        """Must have a non-empty docstring (BT-16-003)."""
        assert FollowUpOnErrorMessage.__doc__
        assert FollowUpOnErrorMessage.__doc__.strip()

    def test_name_defaults_to_class_name(self):
        """Default name must be the class name."""
        node = FollowUpOnErrorMessage()
        assert node.name == "FollowUpOnErrorMessage"

    def test_name_custom(self):
        """Custom name must be respected."""
        node = FollowUpOnErrorMessage(name="custom")
        assert node.name == "custom"

    def test_update_returns_status(self):
        """update() must return a valid py_trees Status."""
        node = FollowUpOnErrorMessage()
        node.setup()
        status = node.update()
        assert status in (
            py_trees.common.Status.SUCCESS,
            py_trees.common.Status.FAILURE,
        )

    def test_base_type(self):
        """Must subclass UniformSucceedFail (p=0.50)."""
        assert issubclass(FollowUpOnErrorMessage, UniformSucceedFail)

    def test_success_rate(self):
        """Success rate must be 0.50."""
        assert FollowUpOnErrorMessage.success_rate == pytest.approx(0.5)
