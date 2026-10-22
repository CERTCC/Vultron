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

"""Every exchange demo's cases rebuild from their ledgers (#4294 AC-5).

``route_exchange_demo_at_testclient`` rebuilds every case a hosted actor
manages before each demo's teardown clears the node, and the conftest fails
the test that left a case its ledger cannot rebuild (CLP-07-013, CM-23-016).
This module shows the check runs: an embargo demo's negotiated case is
rebuilt, embargo and consent entries included.  The multi-container scenario
demos (``rcv-embargo``, ``rcvv-embargo`` and the ``rcv`` family) need Docker;
their in-process equivalents are the per-actor-store scenarios under
``test/core/use_cases/received/``, each rebuilt by that package's conftest.
"""

import logging
from types import SimpleNamespace

import pytest

import test.demo._helpers as helpers
from test.demo._helpers import route_exchange_demo_at_testclient
from vultron.core.models.case import VulnerabilityCase
from vultron.demo.exchange import (
    establish_embargo_demo as demo,
    initialize_case_demo as init_demo,
)


@pytest.fixture(scope="module")
def demo_env(client):
    with route_exchange_demo_at_testclient(client, demo, init_demo):
        yield


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_an_embargo_demo_case_is_rebuilt_from_its_ledger(demo_env):
    demo.main(skip_health_check=True, demos=[demo.demo_propose_embargo_accept])

    rebuilt = dict(helpers.REBUILT_CASES)
    negotiated = [
        semantic_types
        for semantic_types in rebuilt.values()
        if "activate_embargo_on_case" in semantic_types
    ]
    assert negotiated, f"no negotiated case was rebuilt: {rebuilt}"
    (semantic_types,) = negotiated
    assert semantic_types[0] == "create_case"
    assert "create_embargo_consent" in semantic_types
    assert "update_embargo_consent" in semantic_types
    assert helpers.REBUILD_FAILURES == []
    # The label check read every entry the rebuilt case holds, and more
    # (#4724 AC-3): it reads every hosted store, replicas included.
    assert sum(helpers.LABELLED_ENTRIES) >= len(semantic_types)


@pytest.mark.spec("SE-02-001")
def test_a_mislabelled_entry_is_recorded_not_raised(monkeypatch):
    """An entry whose stored type is not its registry label fails the test.

    The CASE_MANAGER's ``Create(EmbargoConsent)`` stored under another name
    is recorded with the rebuild failures (ADR-0140, #4724 AC-3).
    """
    from vultron.wire.as2.vocab.examples.embargo import (
        create_embargo_consent,
    )

    snapshot = create_embargo_consent().model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    entries = [
        SimpleNamespace(
            case_id="c",
            log_index=0,
            semantic_type="create_embargo_consent",
            payload_snapshot=snapshot,
        ),
        SimpleNamespace(
            case_id="c",
            log_index=1,
            semantic_type="consent_row_written",
            payload_snapshot=snapshot,
        ),
    ]
    monkeypatch.setattr(helpers, "_hosted_ledger_entries", lambda: entries)
    monkeypatch.setattr(helpers, "_managed_cases", lambda: iter([]))
    monkeypatch.setattr(helpers, "_multi_party_cases", set)

    helpers.check_cases_rebuild_from_their_ledgers()

    failures = list(helpers.REBUILD_FAILURES)
    helpers.REBUILD_FAILURES.clear()
    assert helpers.LABELLED_ENTRIES == [2]
    assert len(failures) == 1
    assert "entry 1" in failures[0]
    assert "'consent_row_written'" in failures[0]
    assert "'create_embargo_consent'" in failures[0]


@pytest.mark.parametrize(
    "error", [AssertionError("differs"), ValueError("bad snapshot")]
)
def test_any_rebuild_failure_is_recorded_not_raised(monkeypatch, error):
    """The demo teardown still clears the node; the test fails afterwards."""

    def _fails(*_a, **_k):
        raise error

    monkeypatch.setattr(helpers, "_managed_cases", lambda: iter([(None, "c")]))
    monkeypatch.setattr(helpers, "_multi_party_cases", set)
    monkeypatch.setattr(helpers, "ledger_entries", lambda *_a: [])
    monkeypatch.setattr(helpers, "assert_rebuilds_from_ledger", _fails)

    helpers.check_cases_rebuild_from_their_ledgers()

    assert [
        f"'c': {type(error).__name__}: {error}"
    ] == helpers.REBUILD_FAILURES
    with pytest.raises(AssertionError, match=str(error)):
        helpers.assert_no_rebuild_failures()
    assert helpers.REBUILD_FAILURES == []


def test_each_multi_party_case_not_rebuilt_is_a_failure(monkeypatch):
    """One rebuilt case does not cover another the check passed over."""
    monkeypatch.setattr(helpers, "_managed_cases", lambda: iter([(None, "a")]))
    monkeypatch.setattr(helpers, "ledger_entries", lambda *_a: [])
    monkeypatch.setattr(
        helpers, "assert_rebuilds_from_ledger", lambda *_a, **_k: None
    )
    monkeypatch.setattr(helpers, "_multi_party_cases", lambda: {"a", "b"})

    helpers.check_cases_rebuild_from_their_ledgers()

    failures = list(helpers.REBUILD_FAILURES)
    helpers.REBUILD_FAILURES.clear()
    assert len(failures) == 1
    assert failures[0].startswith("'b': a multi-party case is held")


class _Store:
    def __init__(self, *objects):
        self._objects = list(objects)

    def list_objects(self, _type):
        return self._objects


def _seating(case_id, *actors):
    case = VulnerabilityCase(id_=case_id)
    for n, actor in enumerate(actors):
        case.actor_participant_index[actor] = f"{case_id}/participants/{n}"
    return case


def test_a_case_seating_more_than_one_actor_is_multi_party(monkeypatch):
    stores = {
        "https://example.org/actors/x": _Store(
            _seating("https://example.org/cases/solo", "https://x.example"),
            _seating(
                "https://example.org/cases/pair",
                "https://x.example",
                "https://y.example",
            ),
            object(),  # not a case
        ),
        "https://example.org/actors/y": _Store(),
    }
    monkeypatch.setattr(helpers, "get_all_actor_datalayers", lambda: stores)

    assert helpers._multi_party_cases() == {"https://example.org/cases/pair"}


def test_the_check_restores_the_logging_level_it_found(monkeypatch):
    monkeypatch.setattr(helpers, "_managed_cases", lambda: iter([]))
    monkeypatch.setattr(helpers, "_multi_party_cases", set)
    logging.disable(logging.INFO)
    try:
        helpers.check_cases_rebuild_from_their_ledgers()

        assert logging.root.manager.disable == logging.INFO
    finally:
        logging.disable(logging.NOTSET)
