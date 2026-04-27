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
"""

import os
from pathlib import Path

# Set VULTRON_DB_URL BEFORE any vultron module imports so that _DEFAULT_DB_URL
# in datalayer_sqlite.py picks up the in-memory value at import time.
os.environ.setdefault("VULTRON_DB_URL", "sqlite:///:memory:")

import pytest  # noqa: E402
from vultron.adapters.driven.datalayer_sqlite import (  # noqa: E402
    reset_datalayer,
)
from vultron.metadata.specs import (  # noqa: E402
    load_registry,
    warn_unknown_spec_id,
)


def pytest_configure(config):
    """Register the ``spec`` marker (SR-05-001)."""
    config.addinivalue_line(
        "markers",
        "spec(spec_id): mark test as verifying a specific spec requirement ID",
    )


def pytest_collection_modifyitems(session, config, items):
    """Warn for unknown spec IDs in ``@pytest.mark.spec`` markers (SR-05-002).

    Emits :class:`~vultron.metadata.specs.UnknownSpecIdWarning` (non-blocking)
    for any marker that references a spec ID not found in the registry.
    Skips silently when no YAML files exist in ``specs/`` (e.g., before SR.6).
    """
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
