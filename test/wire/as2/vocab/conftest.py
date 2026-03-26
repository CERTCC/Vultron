import py_trees
import pytest
from collections.abc import Generator


@pytest.fixture(autouse=True, scope="function")
def clear_py_trees_blackboard() -> Generator[None, None, None]:
    """
    Ensure py_trees blackboard state is cleared before every test in this
    directory.

    This prevents test state leakage caused by the global py_trees blackboard
    storage and satisfies TB-06-006 in specs/testability.md.
    """
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()
