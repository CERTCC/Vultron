"""Case-ledger invariants for the rv-csaf scenario (DEMOMA-28, DEMOMA-16-019).

Reads JSONL case-ledger replica files from ``devlogs/rv-csaf/`` and asserts
the universal invariants, plus the late-joiner check ``rv`` makes: the
Reporter is seated when the case is created from its CSAF report, and its
replica must still hold every entry the Vendor's does.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/rv-csaf/`` is absent.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_late_joiner_has_full_history,
    load_devlogs,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "rv-csaf"

#: Expected protocol semanticTypes in a complete rv-csaf run (DEMOMA-16-019).
_RV_CSAF_EXPECTED_SEMANTIC_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
    pytest.param("engage_case", id="engage_case"),
    # The CSAF disclosure date is the shorter term, so the CASE_MANAGER
    # relays the Vendor's longer default as a revision (EP-04-027), its
    # invitation is accepted, and the Vendor's publication ends the embargo.
    pytest.param("invite_to_embargo_on_case", id="invite_to_embargo_on_case"),
    pytest.param(
        "accept_invite_to_embargo_on_case",
        id="accept_invite_to_embargo_on_case",
    ),
    pytest.param(
        "remove_embargo_event_from_case", id="remove_embargo_event_from_case"
    ),
]

#: Actors with per-actor hash-chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("reporter"),
]


@pytest.fixture(scope="module")
def rv_csaf_replicas() -> dict[str, list[dict]]:
    """Load rv-csaf scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


globals().update(
    make_universal_invariant_tests(
        replicas_fixture="rv_csaf_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_semantic_types=_RV_CSAF_EXPECTED_SEMANTIC_TYPES,
        narrative_path="docs/topics/scenarios/rv-csaf.md",
    )
)


@pytest.mark.case_ledger_invariants
def test_invariant_8_late_joiner_has_full_history(
    rv_csaf_replicas: dict[str, list[dict]],
) -> None:
    """Reporter replica contains all logIndex values present in the vendor replica."""
    if not rv_csaf_replicas.get("vendor") or not rv_csaf_replicas.get(
        "reporter"
    ):
        pytest.skip(
            "vendor or reporter replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        rv_csaf_replicas, early_actor="vendor", late_actor="reporter"
    )
    assert not violations, "\n".join(violations)
