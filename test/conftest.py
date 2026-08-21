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

#: The actor a test uses when it does not model actor identity at all.
#:
#: Every DataLayer belongs to exactly one actor (ADR-0069), so a test that only
#: needs "somewhere to put objects" still has to name whose store that is. This
#: is that name. It is deliberately one shared constant rather than a per-file
#: literal so the set of tests that don't distinguish actors stays greppable.
#:
#: A test that *does* distinguish actors MUST NOT use it for more than one of
#: them. Two logical actors sharing one store is the condition that hides
#: missing-write defects: the reader finds the writer's row and the test passes
#: for the wrong reason. Give each actor its own store instead — the BT's store
#: follows its executing actor, so running a tree as actor X against Y's store
#: now reads an empty store rather than silently borrowing Y's data.
TEST_ACTOR_ID = "https://test.example/api/v2/actors/test-actor"

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


@pytest.fixture(autouse=True)
def _dispose_actor_stores_between_tests():
    """Drop every per-actor store after each test (ADR-0069).

    In-memory stores are **named** — ``actor_db_url`` maps an actor to
    ``sqlite:///file:{base}-{slug}?mode=memory&cache=shared&uri=true`` — so the
    engine cache is keyed by that URL rather than by engine-object identity.
    Two tests using the same actor id therefore reach the *same* in-memory
    database, and without disposal the first test's rows leak into the second
    (seen as ``ValueError: record with id_=... already exists``).

    Naming the database is what makes store identity live entirely in the URL
    (the property that stops two in-process applications sharing a store), so
    the disposal duty is the price of that guarantee rather than an accident.
    Disposing closes the last connection, which is what actually destroys an
    in-memory database.

    Autouse and session-wide: individual tests should not have to remember, and
    forgetting produces cross-test contamination that presents as a confusing
    duplicate-id error far from its cause.
    """
    yield
    from vultron.adapters.driven.datalayer_sqlite import reset_datalayer

    reset_datalayer()


def seed_case_actor_replica(dl, case_actor_id, case, *extra):
    """Give the CaseActor its own replica of *case*, and return its store.

    A delegated emit (CM-24-001) is authored as the CaseActor and committed to the
    CaseActor's ledger, so the tree runs in the **CaseActor's** store. That store
    must therefore hold the case: ``CommitCaseLedgerEntryNode`` anchors the chain
    on the case's deterministic per-case genesis hash (CLP-08-001/002), and
    without the case there is nothing to anchor to — the commit fails with
    "ledger is empty and per-case genesis hash is unavailable".

    In production the CaseActor always has the case; it is the actor that manages
    it. Only the tests were seeding a single store, which a shared pool made
    sufficient.
    """
    case_actor_dl = dl.clone_for_actor(case_actor_id)
    case_actor_dl.create(case)
    for obj in extra:
        case_actor_dl.create(obj)
    return case_actor_dl
