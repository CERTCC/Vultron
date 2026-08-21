"""Case-ledger invariant tests for the FVCV-handoff scenario.

Reads JSONL case-ledger replica files from ``devlogs/fvcv-handoff/`` and
asserts universal invariants (via the shared ``common`` library) plus
FVCV-handoff-specific checks.

Actor set: ``finder``, ``vendor`` (initial CASE_OWNER), ``coordinator``
(new CASE_OWNER after the ownership handoff), ``vendor2``, ``case-actor``.

FVCV-handoff-specific invariants:
- ``invite_actor_to_case`` appears at least twice (Vendor1 invites
  Coordinator, then Coordinator — as the new owner — invites Vendor2).
- ``accept_invite_actor_to_case`` appears at least twice (Coordinator and
  Vendor2 each accept their invitation).
- Vendor2 is a late joiner — its replica holds the complete log from genesis.

Note on the ownership transfer: the ``Offer(VulnerabilityCase)`` /
``Accept(Offer(VulnerabilityCase))`` handoff is a direct Vendor1 ↔
Coordinator exchange (TRIG-11-001/TRIG-11-002) and does not emit a canonical
CaseActor ledger entry, so it is not observable here.  The demo verifies the
resulting ``attributed_to`` change on both the Vendor1 and Coordinator
DataLayers via ``demo_check`` assertions instead.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fvcv-handoff/`` is absent.

Spec: GitHub issue #1561; CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_event_type_count,
    check_late_joiner_has_full_history,
    load_devlogs,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "fvcv-handoff"

#: Expected protocol eventTypes in a complete FVCV-handoff run.
_FVCV_HANDOFF_EXPECTED_EVENT_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
    # DEMOMA-16-001: universal — the shared RM-triage helpers in
    # vultron/demo/helpers/workflow.py engage the case in every scenario.
    pytest.param("engage_case", id="engage_case"),
    # DEMOMA-16-005: Vendor1 invites Coordinator (and later Vendor2);
    # Coordinator and Vendor2 both accept.
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("vendor2"),
    pytest.param("finder"),
    pytest.param("coordinator"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fvcv_handoff_replicas() -> dict[str, list[dict]]:
    """Load FVCV-handoff scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="fvcv_handoff_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_FVCV_HANDOFF_EXPECTED_EVENT_TYPES,
    )
)


# ---------------------------------------------------------------------------
# FVCV-handoff-specific invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fvcv_handoff_invite_actor_to_case_at_least_twice(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least twice.

    Vendor1 invites Coordinator; then Coordinator (the new CASE_OWNER after
    the ownership handoff) invites Vendor2.
    """
    violations = check_event_type_count(
        fvcv_handoff_replicas, "invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fvcv_handoff_accept_invite_at_least_twice(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` appears at least twice.

    Coordinator accepts Vendor1's invitation and Vendor2 accepts
    Coordinator's invitation — both mid-case joins land in the canonical
    ledger (PCR-08-008).
    """
    violations = check_event_type_count(
        fvcv_handoff_replicas, "accept_invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fvcv_handoff_vendor2_rm_triage_observed(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """Vendor2 RM triage cycle (VALID then ACCEPTED) is observed in the ledger.

    Per CM-11-002, Vendor2 SHOULD run the standard triage cycle after
    receiving the full case replica.  Both ``validate_report`` and
    ``engage_case`` entries must appear at least twice in total — the
    original receiver (Vendor1) and Vendor2 each contribute one of each.
    """
    violations = check_event_type_count(
        fvcv_handoff_replicas, "validate_report", min_count=2
    )
    assert not violations, violations[0] if violations else ""

    violations = check_event_type_count(
        fvcv_handoff_replicas, "engage_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fvcv_handoff_vendor2_late_joiner_has_full_history(
    fvcv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """Vendor2 replica contains all logIndex values present in vendor replica.

    Vendor2 is the last actor to join (after the ownership handoff) and must
    receive the full ledger backfill (LedgerFanout convergence).
    """
    if not fvcv_handoff_replicas.get(
        "vendor"
    ) or not fvcv_handoff_replicas.get("vendor2"):
        pytest.skip(
            "vendor or vendor2 replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fvcv_handoff_replicas, early_actor="vendor", late_actor="vendor2"
    )
    assert not violations, "\n".join(violations)
