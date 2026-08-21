"""Case-ledger invariant tests for the four-actor FVCV-extension scenario.

Reads JSONL case-ledger replica files from ``devlogs/fvcv-extension/`` and
asserts universal invariants (via the shared ``common`` library) plus
FVCV-extension-specific checks.

Actor set: ``finder``, ``vendor``, ``coordinator``, ``vendor2``,
``case-actor``.

FVCV-extension-specific invariants:
- ``invite_actor_to_case`` appears at least twice (Finder, then Vendor2 via CaseActor).
- ``offer_case_participant`` appears at least once (Coordinator suggests Vendor2).
- ``accept_invite_actor_to_case`` appears at least once (Vendor2 accepts CaseActor invite).
- Vendor2 is a late joiner — replica holds the complete log from genesis.
- Finder is a late joiner — replica holds the complete log from genesis.
- Coordinator is a late joiner — replica holds the complete log from genesis.
- CS transitions VFd and VFD observed in vendor-actor status entries.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fvcv-extension/`` is absent.

Spec: DEMOMA-10, CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_event_type_count,
    check_event_type_present,
    check_late_joiner_has_full_history,
    load_devlogs,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "fvcv-extension"

#: Expected protocol eventTypes in a complete FVCV-extension run.
_FVCV_EXPECTED_EVENT_TYPES = [
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
    # DEMOMA-16-004: Vendor1 invites Coordinator; Coordinator uses the
    # suggest-actor flow (offer_case_participant) to propose Vendor2;
    # CaseActor converts the offer to an invite; Vendor2 accepts.
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param("offer_case_participant", id="offer_case_participant"),
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
    # Vendor1 approves Coordinator's actor recommendation (ADR-0026 suggest-actor flow).
    pytest.param(
        "accept_actor_recommendation", id="accept_actor_recommendation"
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
def fvcv_extension_replicas() -> dict[str, list[dict]]:
    """Load FVCV-extension scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="fvcv_extension_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_FVCV_EXPECTED_EVENT_TYPES,
    )
)


# ---------------------------------------------------------------------------
# FVCV-extension-specific invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fvcv_extension_invite_actor_to_case_at_least_twice(
    fvcv_extension_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least twice (Finder + Vendor2 invitations).

    Spec: DEMOMA-10-003 (Coordinator invites Finder), DEMOMA-10-005 (CaseActor
    invites Vendor2).
    """
    violations = check_event_type_count(
        fvcv_extension_replicas, "invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fvcv_extension_offer_case_participant_present(
    fvcv_extension_replicas: dict[str, list[dict]],
) -> None:
    """``offer_case_participant`` appears at least once (Coordinator suggests Vendor2).

    Spec: DEMOMA-16-004 (Coordinator uses the ADR-0026 suggest-actor flow).
    """
    violations = check_event_type_present(
        fvcv_extension_replicas, "offer_case_participant"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fvcv_extension_vendor2_late_joiner_has_full_history(
    fvcv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Vendor2 replica contains all logIndex values present in vendor replica.

    Vendor2 is a late joiner and must receive the full ledger backfill.
    Spec: DEMOMA-10-007 (LedgerFanout convergence).
    """
    if not fvcv_extension_replicas.get(
        "vendor"
    ) or not fvcv_extension_replicas.get("vendor2"):
        pytest.skip(
            "vendor or vendor2 replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fvcv_extension_replicas, early_actor="vendor", late_actor="vendor2"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fvcv_extension_finder_late_joiner_has_full_history(
    fvcv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Finder replica contains all logIndex values present in vendor replica.

    Finder is seeded by the CaseActor's trust-bootstrap Announce; the
    CaseActor must backfill all prior entries to Finder.
    Spec: DEMOMA-10-007 (LedgerFanout convergence).
    """
    if not fvcv_extension_replicas.get(
        "vendor"
    ) or not fvcv_extension_replicas.get("finder"):
        pytest.skip(
            "vendor or finder replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fvcv_extension_replicas, early_actor="vendor", late_actor="finder"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fvcv_extension_coordinator_late_joiner_has_full_history(
    fvcv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Coordinator replica contains all logIndex values present in vendor replica.

    Coordinator joins after case creation when Vendor1 invites them; the
    CaseActor must backfill all prior entries to Coordinator.
    Spec: DEMOMA-10-007 (LedgerFanout convergence).
    """
    if not fvcv_extension_replicas.get(
        "vendor"
    ) or not fvcv_extension_replicas.get("coordinator"):
        pytest.skip(
            "vendor or coordinator replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fvcv_extension_replicas, early_actor="vendor", late_actor="coordinator"
    )
    assert not violations, "\n".join(violations)
