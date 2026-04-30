import pytest
import py_trees

# Re-export harness fixtures so they are available to all sub-directories.
from test.core.behaviors.bt_harness import (  # noqa: F401
    bt_scenario,
    bt_scenario_factory,
    shared_dl_actors,
)


@pytest.fixture(autouse=True, scope="function")
def clear_py_trees_blackboard() -> None:
    """
    Ensure py_trees blackboard state is cleared before every Behavior Tree test.

    This prevents test state leakage caused by the global py_trees blackboard
    storage and satisfies TB-06-005 in specs/testability.yaml.
    """
    py_trees.blackboard.Blackboard.storage.clear()
