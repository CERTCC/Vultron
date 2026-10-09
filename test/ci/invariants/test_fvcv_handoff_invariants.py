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
``Accept(Offer(VulnerabilityCase))`` handoff routes through the CaseActor
(ADR-0053, CM-21-005/CM-21-007), which commits
``offer_case_ownership_transfer`` and ``accept_case_ownership_transfer``
ledger entries and broadcasts them to every participant.  The acceptance is
in the expected-event-types list below, and the narrative's causal edges
place it between the Coordinator's own invitation acceptance and its invite
of Vendor2.  The demo additionally verifies the resulting ``attributed_to``
change on both the Vendor1 and Coordinator DataLayers via ``demo_check``
assertions.

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
    # DEMOMA-16-005: the Coordinator accepts the ownership transfer and becomes
    # CASE_OWNER (TRIG-11-002, CM-21-007). The scenario already blocks on this
    # entry reaching the *Finder's* replica — ADR-0053's own validation
    # criterion — so Invariant 5 is asserting behaviour the demo guarantees, not
    # adding a new requirement. It was missing here while
    # test_fccv_handoff_invariants.py asserted the same type, which is the
    # one-harness-only divergence DEMOMA-16-008 exists to prevent
    # (ISSUE-3514; the mirror of CONCERN-2243's engage_case case).
    pytest.param(
        "accept_case_ownership_transfer",
        id="accept_case_ownership_transfer",
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
        narrative_path="docs/topics/scenarios/fvcv-handoff.md",
        joined_invitees=2,
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

    Per CM-11-011 and CM-11-020, Vendor2 joined through an Invite, so it
    judges the case by accepting the full-case Invite, not by validating the
    reporter's report.  ``validate_report`` therefore appears once (Vendor1,
    the original receiver), the full-case Invite acceptance appears once
    (Vendor2), and ``engage_case`` appears at least twice (one each).
    """
    violations = check_event_type_count(
        fvcv_handoff_replicas, "validate_report", min_count=1, max_count=1
    )
    assert not violations, violations[0] if violations else ""

    violations = check_event_type_count(
        fvcv_handoff_replicas,
        "accept_invite_actor_to_full_case",
        min_count=1,
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
