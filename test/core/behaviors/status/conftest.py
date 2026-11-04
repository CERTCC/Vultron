"""Conftest for status BT tests."""

import pytest

from test.support.participant_status import (
    drain_recorded_violations,
    install_impossible_state_guard,
)
from test.support.received import received_event


@pytest.fixture
def make_payload():
    """Return a helper that extracts the received event for an AS2 activity."""
    return received_event


@pytest.fixture(autouse=True)
def _refuse_impossible_participant_states(monkeypatch):
    """Fail any status test that stores an impossible participant state.

    The status trees are where the RM↔VF, RM↔D and VF↔D entailments
    (CSB-18-001, CSB-17-001) are decided, so this package is where a fixture
    chosen for convenience does the most damage: five tests here once paired a
    pre-acceptance RM state with the VFD F bit, and adding the receive-path
    entailment check turned a real enforcement improvement into five apparent
    regressions (#2906, #3046).

    Autouse and package-wide, because the point is that nobody has to remember.
    It keys on ``composite_state_violations`` rather than on any fixture
    builder's name, so a test that hand-rolls its own participant record — as
    several in this package do — is covered too.

    The drain after the yield is what makes the guard hold on *tree* writes:
    a node's ``except Exception`` or the bridge's own handler turns the guard's
    raise into ``Status.FAILURE`` or an ``internal_error`` result, so a test
    that does not inspect either would stay green (``notes/bt-integration.md``
    § "``internal_error is False`` is not the same as no bug").
    """
    install_impossible_state_guard(monkeypatch)
    yield
    recorded = drain_recorded_violations()
    assert recorded == [], (
        "the guard refused a participant state during this test, and the"
        " raise did not reach the assertions — a node or the bridge caught it"
        f" (#3046):\n{chr(10).join(recorded)}"
    )
