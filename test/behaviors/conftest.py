import pytest
import py_trees


@pytest.fixture(autouse=True, scope="function")
def clear_py_trees_blackboard() -> None:
    """
    Ensure py_trees blackboard state is cleared before every Behavior Tree test.

    This prevents test state leakage caused by the global py_trees blackboard
    storage and satisfies TB-06-005 in specs/testability.md.
    """
    py_trees.blackboard.Blackboard.storage.clear()
