#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Tests for the integration-tier per-test timeout (issue #2270).

The global ``timeout = 30`` in ``pyproject.toml`` is sized for the unit suite.
``test/conftest.py`` widens it for ``integration``-marked tests only. These
tests pin both tiers so neither ceiling can silently creep back down and abort
the session again.

``TestApplyIntegrationTimeout`` exercises the hook against a stub item, which
pins its own contract but cannot show that pytest-timeout honours a marker
added at collection time. ``TestResolvedTimeoutsUnderRealPytest`` closes that
gap by running a real pytest session and reading the timeout each item
actually resolved to.
"""

import json

import pytest

from test.conftest import (
    INTEGRATION_TIMEOUT_SECONDS,
    apply_integration_timeout,
)

pytest_plugins = ["pytester"]


class FakeItem:
    """Minimal stand-in for a pytest ``Item``.

    Only the two marker operations the hook uses are implemented:
    ``get_closest_marker`` and ``add_marker``.
    """

    def __init__(self, *marker_names, timeout=None):
        self.names = set(marker_names)
        self.added = []
        self.explicit_timeout = timeout

    def get_closest_marker(self, name):
        if name == "timeout":
            if self.explicit_timeout is not None:
                return pytest.mark.timeout(self.explicit_timeout).mark
            for mark in self.added:
                if mark.name == "timeout":
                    return mark
            return None
        return (
            pytest.mark.__getattr__(name).mark if name in self.names else None
        )

    def add_marker(self, marker):
        self.added.append(marker.mark)

    @property
    def applied_timeout(self):
        for mark in self.added:
            if mark.name == "timeout":
                return mark.args[0]
        return None


class TestApplyIntegrationTimeout:
    def test_integration_item_gets_the_integration_tier_timeout(self):
        item = FakeItem("integration")

        assert apply_integration_timeout([item]) == 1
        assert item.applied_timeout == INTEGRATION_TIMEOUT_SECONDS

    def test_unit_item_is_left_at_the_global_default(self):
        item = FakeItem()

        assert apply_integration_timeout([item]) == 0
        assert item.applied_timeout is None

    def test_explicit_timeout_marker_wins(self):
        """A deliberate per-test value must not be overwritten."""
        item = FakeItem("integration", timeout=180)

        assert apply_integration_timeout([item]) == 0
        assert item.applied_timeout is None

    def test_explicit_shorter_timeout_also_wins(self):
        """Tests that assert on a timeout firing must keep their short value."""
        item = FakeItem("integration", timeout=1)

        assert apply_integration_timeout([item]) == 0
        assert item.applied_timeout is None

    def test_mixed_collection_only_touches_integration_items(self):
        integration = FakeItem("integration")
        unit = FakeItem()
        explicit = FakeItem("integration", timeout=10)

        assert apply_integration_timeout([integration, unit, explicit]) == 1
        assert integration.applied_timeout == INTEGRATION_TIMEOUT_SECONDS
        assert unit.applied_timeout is None
        assert explicit.applied_timeout is None

    def test_applying_twice_is_idempotent(self):
        """Re-running the hook must not stack duplicate timeout markers."""
        item = FakeItem("integration")

        apply_integration_timeout([item])
        assert apply_integration_timeout([item]) == 0
        assert [m.name for m in item.added].count("timeout") == 1

    def test_empty_collection_is_a_no_op(self):
        assert apply_integration_timeout([]) == 0


_UNIT_TIER_FOR_PROBE = 30

_PROBE_CONFTEST = """
import json
import pathlib

import pytest_timeout

from test.conftest import apply_integration_timeout

_resolved = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: integration test")


def pytest_collection_modifyitems(items):
    apply_integration_timeout(items)


def pytest_runtest_setup(item):
    _resolved[item.name] = pytest_timeout._get_item_settings(item).timeout


def pytest_sessionfinish(session, exitstatus):
    pathlib.Path(session.config.rootpath / "resolved.json").write_text(
        json.dumps(_resolved)
    )
"""

_PROBE_TESTS = """
import pytest


@pytest.mark.integration
def test_integration_tier():
    pass


def test_unit_tier():
    pass


@pytest.mark.integration
@pytest.mark.timeout(7)
def test_explicit_marker_wins():
    pass
"""


class TestResolvedTimeoutsUnderRealPytest:
    """Assert the timeout each item *actually* resolves to (issue #2270).

    The stub-based tests above verify the hook's own logic. This one runs a
    real pytest session and asks pytest-timeout what it resolved for each
    item, which is the only way to catch a hook-ordering regression: the
    marker is added at collection time, but pytest-timeout reads it much
    later, in ``pytest_runtest_protocol``.
    """

    @pytest.fixture
    def resolved(self, pytester):
        pytester.makeconftest(_PROBE_CONFTEST)
        pytester.makepyfile(test_probe=_PROBE_TESTS)

        result = pytester.runpytest(
            "-p",
            "no:randomly",
            "-o",
            f"timeout={_UNIT_TIER_FOR_PROBE}",
            "-o",
            "timeout_method=thread",
        )
        result.assert_outcomes(passed=3)

        return json.loads((pytester.path / "resolved.json").read_text())

    def test_integration_item_resolves_to_the_integration_tier(self, resolved):
        assert resolved["test_integration_tier"] == INTEGRATION_TIMEOUT_SECONDS

    def test_unit_item_resolves_to_the_unit_tier(self, resolved):
        assert resolved["test_unit_tier"] == _UNIT_TIER_FOR_PROBE

    def test_explicit_marker_beats_the_tier_default(self, resolved):
        """The demo suite's deliberate values (10, 180) depend on this."""
        assert resolved["test_explicit_marker_wins"] == 7


class TestIntegrationTimeoutValue:
    def test_is_comfortably_above_the_slowest_honest_integration_test(self):
        """The slowest honest integration test measured ~4.3s (issue #2270).

        A ceiling that is merely a little above that is what caused the
        original spurious aborts, so require real headroom.
        """
        assert INTEGRATION_TIMEOUT_SECONDS >= 30

    def test_is_still_a_bounded_hang_detector(self):
        assert INTEGRATION_TIMEOUT_SECONDS <= 300


class TestUnitTierTimeout:
    """Pin the unit-tier ceiling in ``pyproject.toml`` (issue #2270).

    Four sessions re-diagnosed a too-tight unit ceiling as flakiness before it
    was raised. These assertions make a silent revert fail loudly.
    """

    @staticmethod
    def _configured_timeout(pytestconfig):
        return int(pytestconfig.getini("timeout"))

    def test_unit_tier_clears_the_slowest_ast_ratchet(self, pytestconfig):
        """AST-walking architecture ratchets run ~3.4s in isolation.

        Under full-suite load they were tripping a 5s ceiling. Require enough
        headroom that load variance cannot reach it.
        """
        assert self._configured_timeout(pytestconfig) >= 15

    def test_unit_tier_is_still_a_bounded_hang_detector(self, pytestconfig):
        assert self._configured_timeout(pytestconfig) <= 60

    def test_integration_tier_is_wider_than_the_unit_tier(self, pytestconfig):
        assert INTEGRATION_TIMEOUT_SECONDS > self._configured_timeout(
            pytestconfig
        )

    def test_thread_method_is_still_in_use(self, pytestconfig):
        """Documents the coupling the tier values depend on.

        If this ever changes to "signal", a timeout fails one test instead of
        aborting the session, and the generous ceilings above can be revisited.
        """
        assert pytestconfig.getini("timeout_method") == "thread"
