"""Case-ledger invariant tests for the four-actor FCCV-extension scenario.

Reads JSONL case-ledger replica files from ``devlogs/fccv-extension/`` and
asserts universal invariants (via the shared ``common`` library) plus
FCCV-extension-specific checks.

Actor set: ``finder``, ``vendor`` (C1/Coordinator1 on coordinator container),
``coordinator`` (C2/Coordinator2 on actor5 container), ``vendor2`` (Vendor on
vendor container), ``case-actor``.

Note on actor-name mapping: the devlog dump uses FVCV-style directory names to
reuse the same docker-compose containers.  ``vendor`` == C1 (coordinator
container); ``coordinator`` == C2 (actor5 container); ``vendor2`` == Vendor
(vendor container).

FCCV-extension-specific invariants:
- ``invite_actor_to_case`` appears at least twice (C2 invitation + Vendor
  invitation via CaseActor).
- ``offer_case_participant`` appears at least once (C2 suggests Vendor via
  ADR-0026).
- Vendor (``vendor2``) is a late joiner — its replica holds the complete log
  from genesis (LedgerFanout backfill).
- CS transitions VFd and VFD observed in Vendor actor-status entries.
- CS transition P (public-aware) observed in C1 (``vendor``) actor-status
  entries (C1 triggers CS.P as CASE_OWNER).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fccv-extension/`` is absent.

Spec: DEMOMA-13 (GitHub issue #1620), CLP-07.
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

_DEMO_NAME = "fccv-extension"

#: Expected protocol eventTypes in a complete FCCV-extension run.
_FCCV_EXTENSION_EXPECTED_EVENT_TYPES = [
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
    # C1 invites C2, then CaseActor invites Vendor (via ADR-0026 path).
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    # C2 suggests Vendor via the ADR-0026 suggest-actor flow.
    pytest.param("offer_case_participant", id="offer_case_participant"),
    # C2 accepts C1's invite; Vendor accepts CaseActor's invite.
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
    # C1 approves C2's actor recommendation (ADR-0026 suggest-actor flow).
    pytest.param(
        "accept_actor_recommendation", id="accept_actor_recommendation"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
#: Directory names follow FVCV convention: vendor=C1, coordinator=C2, vendor2=Vendor.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),  # C1 (coordinator container)
    pytest.param("coordinator"),  # C2 (actor5 container, coordinator2)
    pytest.param("vendor2"),  # Vendor (vendor container)
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fccv_extension_replicas() -> dict[str, list[dict]]:
    """Load FCCV-extension scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="fccv_extension_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_FCCV_EXTENSION_EXPECTED_EVENT_TYPES,
        narrative_path="docs/topics/scenarios/fccv-extension.md",
    )
)


# ---------------------------------------------------------------------------
# FCCV-extension-specific invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fccv_extension_invite_actor_to_case_at_least_twice(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least twice (C2 + Vendor invitations).

    Spec: DEMOMA-13-003 (C1 invites C2), DEMOMA-13-005 (CaseActor invites
    Vendor via ADR-0026 path).
    """
    violations = check_event_type_count(
        fccv_extension_replicas, "invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fccv_extension_offer_case_participant_present(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """``offer_case_participant`` appears at least once (C2 suggests Vendor).

    Spec: DEMOMA-13-004 (C2 uses the ADR-0026 suggest-actor flow).
    """
    violations = check_event_type_present(
        fccv_extension_replicas, "offer_case_participant"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fccv_extension_vendor_late_joiner_has_full_history(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """Vendor (vendor2) replica contains all logIndex values present in C1 (vendor) replica.

    Vendor is a late joiner and must receive the full ledger backfill from
    CaseActor (LedgerFanout).
    Spec: DEMOMA-13-007 (LedgerFanout convergence).
    """
    if not fccv_extension_replicas.get(
        "vendor"
    ) or not fccv_extension_replicas.get("vendor2"):
        pytest.skip(
            "vendor (C1) or vendor2 (Vendor) replica absent; "
            "cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fccv_extension_replicas, early_actor="vendor", late_actor="vendor2"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fccv_extension_c2_late_joiner_has_full_history(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """C2 (coordinator) replica contains all logIndex values present in C1 (vendor) replica.

    C2 joins after initial case creation when C1 invites them; CaseActor must
    backfill all prior entries to C2.
    Spec: DEMOMA-13-007 (LedgerFanout convergence).
    """
    if not fccv_extension_replicas.get(
        "vendor"
    ) or not fccv_extension_replicas.get("coordinator"):
        pytest.skip(
            "vendor (C1) or coordinator (C2) replica absent; "
            "cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fccv_extension_replicas, early_actor="vendor", late_actor="coordinator"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fccv_extension_accept_invite_at_least_twice(
    fccv_extension_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` appears at least twice (C2 + Vendor accepts).

    Spec: DEMOMA-13-003 (C2 accepts C1 invite), DEMOMA-13-005 (Vendor accepts
    CaseActor invite via ADR-0026 path).
    """
    violations = check_event_type_count(
        fccv_extension_replicas, "accept_invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""
