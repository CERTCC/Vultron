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

The global ``timeout = 5`` in ``pyproject.toml`` is sized for the unit suite.
``test/conftest.py`` widens it for ``integration``-marked tests only. These
tests pin that behaviour so the 5s ceiling cannot silently creep back onto the
integration suite and abort the session again.
"""

import pytest

from test.conftest import (
    INTEGRATION_TIMEOUT_SECONDS,
    apply_integration_timeout,
)


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


class TestIntegrationTimeoutValue:
    def test_is_comfortably_above_the_slowest_honest_integration_test(self):
        """The slowest honest integration test measured ~4.3s (issue #2270).

        A ceiling that is merely a little above that is what caused the
        original spurious aborts, so require real headroom.
        """
        assert INTEGRATION_TIMEOUT_SECONDS >= 30

    def test_is_still_a_bounded_hang_detector(self):
        assert INTEGRATION_TIMEOUT_SECONDS <= 300
