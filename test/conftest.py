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
from collections.abc import Iterator
from pathlib import Path

# Set VULTRON_DATABASE__DB_URL BEFORE any vultron module imports so that
# get_config().database.db_url returns the in-memory value.
# The legacy VULTRON_DB_URL is also cleared to avoid confusion.
os.environ.setdefault("VULTRON_DATABASE__DB_URL", "sqlite:///:memory:")

import py_trees
import pytest

from test.support.xdist_workers import worker_count
from vultron.adapters.driven.datalayer_sqlite import (
    reset_datalayer,
)
from vultron.metadata.specs import (
    load_registry,
    warn_spec_registry_unavailable,
    warn_unknown_spec_id,
)

#: The actor a test uses when it does not model actor identity at all.
#:
#: Every DataLayer belongs to exactly one actor (ADR-0073), so a test that only
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


@pytest.hookimpl(tryfirst=True, optionalhook=True)
def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """Size ``-n auto`` to the container's cgroup limits (``worker_count``).

    ``PYTEST_XDIST_AUTO_NUM_WORKERS`` still wins: returning ``None`` hands the
    decision back to xdist, which reads it.  ``-n logical`` is left to xdist.
    """
    if os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS"):
        return None
    if config.option.numprocesses == "logical":
        return None
    return worker_count()


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


#: Failure modes ``load_registry`` can raise for a corpus that exists but does
#: not load.  ``pydantic.ValidationError`` is a ``ValueError`` subclass, and a
#: duplicate spec ID raises ``ValueError`` directly; ``OSError`` covers an
#: unreadable file.  A YAML syntax error arrives as a ``ValueError`` too: the
#: loader routes its parse through ``vultron.metadata.file_loading``, which
#: re-raises it attributed to its file (MS-17-002).
#:
#: Deliberately not ``Exception``: an unexpected type means a bug in the loader
#: rather than a bad spec file, and that must surface rather than degrade to a
#: warning (#3331).
_REGISTRY_LOAD_ERRORS = (ValueError, OSError)


def pytest_collection_modifyitems(session, config, items):
    """Apply the integration timeout, then warn for unknown spec IDs.

    Spec-ID warnings (SR-05-002) emit
    :class:`~vultron.metadata.specs.UnknownSpecIdWarning` (non-blocking) for
    any ``@pytest.mark.spec`` marker referencing an ID not found in the
    registry.

    Both warnings are non-blocking, which depends on their ``always::`` entries
    being listed *after* ``"error"`` in ``pyproject.toml`` (SR-05-007).

    Returns early without validating markers in three cases, which are not
    interchangeable (SR-05-006):

    - **No corpus** (``specs/`` absent, or present with no spec files) — there
      is nothing to validate against and nothing is wrong. Silent.
    - **Unloadable corpus** — the gate cannot run, so it says so via
      :class:`~vultron.metadata.specs.SpecRegistryUnavailableWarning`. Returning
      silently here reported the same clean pass as a corpus with no unknown IDs
      in it, which disabled SR-05-002 for a whole session without a trace
      (#3331). The session is allowed to continue on purpose: aborting it would
      mean a malformed spec file blocks the very tests that diagnose it.
    - **Unexpected load failure** — not caught at all; see
      :data:`_REGISTRY_LOAD_ERRORS`.
    """
    apply_integration_timeout(items)

    spec_dir = Path(__file__).parent.parent / "specs"
    if not spec_dir.is_dir():
        return
    try:
        registry = load_registry(spec_dir)
    except _REGISTRY_LOAD_ERRORS as exc:
        warn_spec_registry_unavailable(spec_dir, exc)
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
    """Drop every per-actor store after each test (ADR-0073).

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

    The claimant record is reset alongside the stores, for the same
    "contamination far from its cause" reason but a different mechanism. It is
    deliberately *not* cleared by engine disposal (see
    ``reset_store_claimants``), so it would otherwise live for the whole pytest
    process: one test using ``https://example.org/actors/test-actor`` left the
    slug ``test-actor`` claimed, and a later test using
    ``https://test.example/api/v2/actors/test-actor`` got a cross-authority
    warning it then failed on (#3545).
    """
    yield
    from vultron.adapters.driven.datalayer_sqlite import (
        reset_datalayer,
        reset_store_claimants,
    )

    reset_datalayer()
    reset_store_claimants()


@pytest.fixture(autouse=True)
def _reset_pending_assertion_stores_between_tests():
    """Drop every per-actor pending-assertion store after each test.

    The stores are process-global and in-memory (SYNC-11-002).  An embargo
    trigger run by a participant that is not the CASE_MANAGER records its ask
    there and suppresses a repeat of it (EP-09-008), so an entry left by one
    test would silently suppress the same trigger in the next.
    """
    yield
    from vultron.core.models.pending_assertion import _reset_stores

    _reset_stores()


@pytest.fixture(autouse=True)
def _reset_ledger_gap_buffers_between_tests():
    """Drop every per-actor ledger gap buffer after each test.

    ``get_ledger_gap_buffer()`` returns a process-global, in-memory singleton
    per actor, and the received sync and actor-announce use cases buffer
    out-of-order ledger entries in it.  An entry one test buffers under an
    actor id would otherwise be waiting in the next test that names the same
    actor, and be applied there as if it had just arrived (TB-06-003).
    """
    yield
    from vultron.core.models.ledger_gap_buffer import _reset_buffers

    _reset_buffers()


@pytest.fixture(autouse=True)
def _restore_third_party_log_levels_between_tests():
    """Undo third-party log-level suppression after each test (TB-06-003).

    ``suppress_third_party_info_noise()`` records each noisy logger's original
    level in a process-global map on first call, and only
    ``restore_third_party_log_levels()`` empties it.  The demo CLI and several
    logging tests suppress without restoring, so a later test in the same
    process inherited the stale map: its own ``restore`` call then reset a
    logger it had just configured.  Serial runs hid this behind collection
    order; xdist split it across workers.
    """
    yield
    from vultron.logging_setup import restore_third_party_log_levels

    restore_third_party_log_levels()


@pytest.fixture(autouse=True)
def clear_py_trees_blackboard() -> Iterator[None]:
    """Clear the ``py_trees`` blackboard before and after every test (TB-06-005).

    ``py_trees.blackboard.Blackboard.storage`` is process-global, and
    ``BTBridge.execute_with_setup`` restores only the keys on its
    ``managed_keys`` list when an execution ends.  Any other key a node writes
    outlives the execution, and so the test.

    This lives at the root, for every test, because trees run far outside
    ``test/core/behaviors/``: received and trigger use cases, adapters and demo
    scenarios all execute them through the bridge.  When the clearing lived
    only in a few directory conftests, a received-side embargo test read the
    ``/participant`` an earlier test's tree had left behind and transitioned
    that participant instead of its own (#3996).
    """
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def isolated_core_registries():
    """Restore ``CORE_VOCABULARY`` and ``CORE_TYPE_MAP`` after the test.

    Request this fixture from any test that defines a local ``CoreObject`` or
    ``CoreRecord`` subclass (TB-06-003, TB-06-004).  It lives in the root
    conftest because such tests exist under ``test/core/``, ``test/adapters/``
    and ``test/architecture/`` alike, and the suite is meant to share one
    registry-isolation mechanism.  The snapshot/restore itself is
    :func:`test.support.core_vocab.restore_core_registries`, which is where its
    behaviour is tested.
    """
    from test.support.core_vocab import restore_core_registries

    with restore_core_registries():
        yield


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


def seed_case_owner_participant(dl, case):
    """Seed the CASE_OWNER participant of *case* — the actor ``attributed_to``
    names (CM-02-008) — and index it on *case*; return the participant.

    Embargo initialization seeds that participant as a signatory, with an
    ``AGREED`` row for the embargo (CM-14-003), and fails when it is missing, because the owner's record is created before the
    embargo (CM-14-002).  Call this before persisting *case*.
    """
    from vultron.core.models._helpers import _as_id
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole

    owner_id = _as_id(case.attributed_to)
    assert owner_id is not None, "case.attributed_to names no owner"
    owner = CaseParticipant(
        attributed_to=owner_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case.add_participant(owner)
    dl.create(owner)
    return owner
