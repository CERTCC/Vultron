"""Conftest for status BT tests."""

import pytest

from test.support.participant_status import install_impossible_state_guard
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
    """
    install_impossible_state_guard(monkeypatch)
