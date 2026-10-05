"""Shared fixtures for Behavior Tree tests.

The ``py_trees`` blackboard is cleared before and after every test by
``clear_py_trees_blackboard`` in the root ``test/conftest.py`` (TB-06-005).
"""

# Re-export harness fixtures so they are available to all sub-directories.
from test.core.behaviors.bt_harness import (  # noqa: F401
    bt_scenario,
    bt_scenario_factory,
    shared_dl_actors,
)
