"""Case-ledger invariant tests for the FCCV-handoff scenario.

Reads JSONL case-ledger replica files from ``devlogs/fccv-handoff/`` and
asserts universal invariants (via the shared ``common`` library) plus
FCCV-handoff-specific checks.

Actor set: ``finder``, ``vendor`` (C1 — initial CASE_OWNER),
``coordinator`` (C2 — new CASE_OWNER after the ownership handoff),
``vendor2`` (Vendor), ``case-actor``.

FCCV-handoff-specific invariants:
- ``invite_actor_to_case`` appears at least twice (C1 invites C2, then C2
  — as the new owner — invites Vendor).
- ``accept_invite_actor_to_case`` appears at least twice (C2 and Vendor
  each accept their invitation).
- Vendor is a late joiner — its replica holds the complete log from genesis.

The ``Accept(Offer(VulnerabilityCase))`` for ownership transfer routes through
the CaseActor (ADR-0053, CM-21-006/007).  The CaseActor commits a canonical
``accept_case_ownership_transfer`` ledger entry and broadcasts
``Announce(CaseLedgerEntry)`` to all participants.  All replicas MUST agree on
the same ``entry_hash`` for that index (ISSUE-2252, AC-3).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fccv-handoff/`` is absent.

Spec: DEMOMA-14-009; CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_event_type_count,
    check_late_joiner_has_full_history,
    load_devlogs,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "fccv-handoff"

#: Expected protocol eventTypes in a complete FCCV-handoff run.
_FCCV_HANDOFF_EXPECTED_EVENT_TYPES = [
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
    # DEMOMA-16-006: C1 invites C2 (and later Vendor);
    # C2 and Vendor both accept.
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
    # ADR-0053 / CM-21-007: CaseActor commits one canonical entry when the
    # Accept(Offer(VulnerabilityCase)) for ownership transfer arrives (AC-3).
    pytest.param(
        "accept_case_ownership_transfer",
        id="accept_case_ownership_transfer",
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
#: Container-service name mapping: vendor→C1, coordinator→C2, vendor2→Vendor.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("coordinator"),
    pytest.param("vendor2"),
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fccv_handoff_replicas() -> dict[str, list[dict]]:
    """Load FCCV-handoff scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="fccv_handoff_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_FCCV_HANDOFF_EXPECTED_EVENT_TYPES,
        narrative_path="docs/topics/scenarios/fccv-handoff.md",
    )
)


# ---------------------------------------------------------------------------
# FCCV-handoff-specific invariants  (DEMOMA-14-009)
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fccv_handoff_invite_actor_to_case_at_least_twice(
    fccv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least twice.

    C1 invites C2; then C2 (the new CASE_OWNER after the ownership handoff)
    invites Vendor.
    """
    violations = check_event_type_count(
        fccv_handoff_replicas, "invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fccv_handoff_accept_invite_at_least_twice(
    fccv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` appears at least twice.

    C2 accepts C1's invitation and Vendor accepts C2's invitation — both
    mid-case joins land in the canonical ledger (PCR-08-008).
    """
    violations = check_event_type_count(
        fccv_handoff_replicas, "accept_invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fccv_handoff_accept_ownership_transfer_hash_agreement(
    fccv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """All replicas agree on ``entryHash`` for ``accept_case_ownership_transfer``.

    Regression for ISSUE-2252: the transferee (coordinator) ran an unguarded
    ``CommitCaseLedgerEntryNode``, producing a different ``received_at`` and
    ``payload_snapshot`` and therefore a different hash than the CaseActor's
    canonical entry at the same ``logIndex``.  After the fix only the CaseActor
    writes that entry; all replicas receive it via ``Announce(CaseLedgerEntry)``
    and must carry the identical ``entryHash`` (AC-3).
    """
    transfer_entries: dict[str, list[dict]] = {
        actor: [
            e
            for e in entries
            if e.get("eventType", e.get("event_type", ""))
            == "accept_case_ownership_transfer"
        ]
        for actor, entries in fccv_handoff_replicas.items()
    }
    # Only check actors that have at least one entry for this event type.
    actors_with_entry = {
        actor: entries
        for actor, entries in transfer_entries.items()
        if entries
    }
    if not actors_with_entry:
        pytest.skip("No accept_case_ownership_transfer entries in devlogs")

    # Collect the set of distinct entryHash values across all replicas.
    hashes: set[str] = set()
    for entries in actors_with_entry.values():
        for e in entries:
            h = str(e.get("entryHash", e.get("entry_hash", "")))
            if h:
                hashes.add(h)

    assert len(hashes) == 1, (
        f"Cross-replica entryHash disagreement for accept_case_ownership_transfer"
        f" (ISSUE-2252 regression): found {len(hashes)} distinct hashes across"
        f" actors {sorted(actors_with_entry)}: {hashes}"
    )


@pytest.mark.case_ledger_invariants
def test_fccv_handoff_vendor_late_joiner_has_full_history(
    fccv_handoff_replicas: dict[str, list[dict]],
) -> None:
    """Vendor (vendor2) replica contains all logIndex values present in C1 (vendor) replica.

    Vendor is the last actor to join (after the ownership handoff) and must
    receive the full ledger backfill (LedgerFanout convergence, DEMOMA-14-006).
    """
    if not fccv_handoff_replicas.get(
        "vendor"
    ) or not fccv_handoff_replicas.get("vendor2"):
        pytest.skip(
            "vendor or vendor2 replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fccv_handoff_replicas, early_actor="vendor", late_actor="vendor2"
    )
    assert not violations, "\n".join(violations)
