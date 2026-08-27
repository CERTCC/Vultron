"""Case-ledger invariant tests for the five-actor FCVCV scenario.

Reads JSONL case-ledger replica files from ``devlogs/fcvcv/`` and asserts
universal invariants (via the shared ``common`` library) plus FCVCV-specific
checks.

Actor set: ``finder``, ``c1``, ``v1``, ``c2``, ``v2``, ``case-actor``.

Container-to-role mapping (docker-compose-multi-actor.yml):
  finder      → Finder container
  c1          → C1/Coordinator1 (coordinator container) — CASE_OWNER
  v1          → V1/Vendor1 (vendor container) — CVDRole.VENDOR only → VFd
  c2          → C2/Coordinator2 (actor5 container) — CVDRole.COORDINATOR
  v2          → V2/VendorDeployer (actor6 container) — VENDOR+DEPLOYER → VFD
  case-actor  → CaseActor (coordinator container sub-actor)

FCVCV-specific invariants:
- ``invite_actor_to_case`` appears at least three times (C1 invites V1, C1
  invites C2, CaseActor invites V2 via ADR-0026).
- ``offer_case_participant`` appears at least once (C2 suggests V2 via
  ADR-0026).
- ``accept_invite_actor_to_case`` appears at least three times.
- V2 (late joiner via ADR-0026) holds the full ledger from genesis (LedgerFanout).
- C1, V1, C2 are also late joiners whose replicas start from genesis.
- CS transition VFd observed for both V1 and V2.
- CS transition VFD observed for V2 only (V1 stops at VFd — DEMOMA-19-004).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fcvcv/`` is absent.

Spec: DEMOMA-19 (GitHub issue #1925).
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

_DEMO_NAME = "fcvcv"

#: Expected protocol eventTypes in a complete FCVCV run.
_FCVCV_EXPECTED_EVENT_TYPES = [
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
    # C1 invites V1, C1 invites C2, CaseActor invites V2 (ADR-0026).
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    # C2 suggests V2 via the ADR-0026 suggest-actor flow.
    pytest.param("offer_case_participant", id="offer_case_participant"),
    # V1 accepts C1 invite; C2 accepts C1 invite; V2 accepts CaseActor invite.
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
    # C1 approves C2's actor recommendation (ADR-0026 suggest-actor flow).
    pytest.param(
        "accept_actor_recommendation", id="accept_actor_recommendation"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("c1"),
    pytest.param("v1"),
    pytest.param("c2"),
    pytest.param("v2"),
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fcvcv_replicas() -> dict[str, list[dict]]:
    """Load FCVCV scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="fcvcv_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_FCVCV_EXPECTED_EVENT_TYPES,
        narrative_path="docs/topics/scenarios/fcvcv.md",
    )
)


# ---------------------------------------------------------------------------
# FCVCV-specific invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fcvcv_invite_actor_to_case_at_least_three(
    fcvcv_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least three times.

    C1 invites V1 (VENDOR), C1 invites C2 (COORDINATOR), CaseActor invites V2
    (VENDOR+DEPLOYER) via the ADR-0026 suggest-actor path.

    Spec: DEMOMA-19-003, DEMOMA-19-009.
    """
    violations = check_event_type_count(
        fcvcv_replicas, "invite_actor_to_case", min_count=3
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcvcv_offer_case_participant_present(
    fcvcv_replicas: dict[str, list[dict]],
) -> None:
    """``offer_case_participant`` appears at least once (C2 suggests V2).

    Spec: DEMOMA-19-009 (C2 uses the ADR-0026 suggest-actor flow).
    """
    violations = check_event_type_present(
        fcvcv_replicas, "offer_case_participant"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcvcv_accept_invite_at_least_three(
    fcvcv_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` appears at least three times.

    V1 accepts C1's invite, C2 accepts C1's invite, V2 accepts CaseActor's
    invite via the ADR-0026 path.

    Spec: DEMOMA-19-003, DEMOMA-19-009.
    """
    violations = check_event_type_count(
        fcvcv_replicas, "accept_invite_actor_to_case", min_count=3
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcvcv_v2_late_joiner_has_full_history(
    fcvcv_replicas: dict[str, list[dict]],
) -> None:
    """V2 replica holds every logIndex present in C1 (the authoritative actor).

    V2 joins via the ADR-0026 path (C2 suggests → C1 approves → CaseActor
    invites) and must receive the full ledger backfill from CaseActor (LedgerFanout).

    Spec: DEMOMA-19-009, LedgerFanout.
    """
    if not fcvcv_replicas.get("c1") or not fcvcv_replicas.get("v2"):
        pytest.skip(
            "c1 or v2 replica absent; cannot check V2 late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fcvcv_replicas, early_actor="c1", late_actor="v2"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fcvcv_c2_late_joiner_has_full_history(
    fcvcv_replicas: dict[str, list[dict]],
) -> None:
    """C2 replica holds every logIndex present in C1 (the authoritative actor).

    C2 joins when C1 invites them; CaseActor must backfill all prior entries
    (LedgerFanout).

    Spec: DEMOMA-19-003, LedgerFanout.
    """
    if not fcvcv_replicas.get("c1") or not fcvcv_replicas.get("c2"):
        pytest.skip(
            "c1 or c2 replica absent; cannot check C2 late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fcvcv_replicas, early_actor="c1", late_actor="c2"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fcvcv_v1_late_joiner_has_full_history(
    fcvcv_replicas: dict[str, list[dict]],
) -> None:
    """V1 replica holds every logIndex present in C1 (the authoritative actor).

    V1 joins when C1 invites them (direct invite, not ADR-0026 path); CaseActor
    still backfills all prior entries (LedgerFanout).

    Spec: DEMOMA-19-003, LedgerFanout.
    """
    if not fcvcv_replicas.get("c1") or not fcvcv_replicas.get("v1"):
        pytest.skip(
            "c1 or v1 replica absent; cannot check V1 late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fcvcv_replicas, early_actor="c1", late_actor="v1"
    )
    assert not violations, "\n".join(violations)
