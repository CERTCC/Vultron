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
Root pytest configuration file.

Forces SQLite in-memory storage for the entire test session so that no
on-disk database files are created and the test suite stays fast.

Also registers the ``spec`` pytest marker and validates spec IDs referenced
by ``@pytest.mark.spec`` against the loaded SpecRegistry (SR-05-001,
SR-05-002).

Finally, it applies the integration-tier per-test timeout. The 30-second
default in ``pyproject.toml`` is sized for the unit suite; integration tests
exercise the full HTTP stack and legitimately need longer. See
``INTEGRATION_TIMEOUT_SECONDS`` and ``test/AGENTS.md`` § "Per-Test Timeout
Guardrail".
"""

import os
from pathlib import Path

# Set VULTRON_DATABASE__DB_URL BEFORE any vultron module imports so that
# get_config().database.db_url returns the in-memory value.
# The legacy VULTRON_DB_URL is also cleared to avoid confusion.
os.environ.setdefault("VULTRON_DATABASE__DB_URL", "sqlite:///:memory:")

import pytest  # noqa: E402
from vultron.adapters.driven.datalayer_sqlite import (  # noqa: E402
    reset_datalayer,
)
from vultron.metadata.specs import (  # noqa: E402
    load_registry,
    warn_unknown_spec_id,
)

#: Per-test timeout for ``@pytest.mark.integration`` tests, in seconds.
#:
#: The global ``timeout = 30`` in ``pyproject.toml`` is sized for the unit
#: suite, where the slowest honest test runs at ~3.1s. It is still too tight
#: for integration tests: several run at 3.5-4.3s of honest work against a
#: much wider load-dependent spread, and because ``timeout_method = "thread"``
#: kills the *whole pytest process* rather than the one slow test, a single
#: spurious trip aborted the session with no summary line — turning a red
#: integration run into no signal at all. See issue #2270.
#:
#: 60s is still a bounded hang detector (2x the unit ceiling) while leaving
#: ample headroom over the slowest honest integration test. Tests needing more
#: keep their own explicit ``@pytest.mark.timeout(N)``, which wins over this.
INTEGRATION_TIMEOUT_SECONDS = 60


def pytest_configure(config):
    """Register the ``spec`` marker (SR-05-001)."""
    config.addinivalue_line(
        "markers",
        "spec(spec_id): mark test as verifying a specific spec requirement ID",
    )


def apply_integration_timeout(items):
    """Give ``integration``-marked tests the integration-tier timeout.

    Applied to every item marked ``integration`` that does not already carry
    an explicit ``timeout`` marker. An explicit marker always wins, so the
    deliberate per-test values in the demo suite are left untouched.

    Returns the number of items modified (for tests and diagnostics).
    """
    modified = 0
    for item in items:
        if item.get_closest_marker("integration") is None:
            continue
        if item.get_closest_marker("timeout") is not None:
            continue
        item.add_marker(pytest.mark.timeout(INTEGRATION_TIMEOUT_SECONDS))
        modified += 1
    return modified


def pytest_collection_modifyitems(session, config, items):
    """Apply the integration timeout, then warn for unknown spec IDs.

    Spec-ID warnings (SR-05-002) emit
    :class:`~vultron.metadata.specs.UnknownSpecIdWarning` (non-blocking) for
    any ``@pytest.mark.spec`` marker referencing an ID not found in the
    registry. Skips silently when no YAML files exist in ``specs/``.
    """
    apply_integration_timeout(items)

    spec_dir = Path(__file__).parent.parent / "specs"
    if not spec_dir.is_dir():
        return
    try:
        registry = load_registry(spec_dir)
    except Exception:
        return
    if not registry.files:
        return
    for item in items:
        marker = item.get_closest_marker("spec")
        if marker and marker.args and isinstance(marker.args[0], str):
            warn_unknown_spec_id(marker.args[0], registry)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_datalayer():
    """Reset all cached DataLayer instances before and after the session.

    Ensures no stale in-memory database state leaks between test modules.
    """
    reset_datalayer()
    yield
    reset_datalayer()
