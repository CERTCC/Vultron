#!/usr/bin/env python
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

"""Spec coverage for CLP-14 and CLP-15 (CaseLedger causal ordering, ADR-0079).

Every requirement here is enforced somewhere; what varies is *where*, and
these tests target the layer that actually owns each one.  Getting the layer
right is the whole point — the stubs this file replaces asserted cross-entry
invariants against a single bare ``CaseLedgerEntry``, a layer that structurally
cannot know its predecessor or its parent case, so they were marked
``xfail(strict=True)`` against work that could never land there (ISSUE-2824).

The three layers:

* **Model** — a single entry's own fields (CLP-14-002).
* **Ledger** — ``CaseLedger.append()``, which owns index assignment and so
  guarantees the by-construction properties (CLP-14-001, CLP-14-004,
  CLP-14-005, CLP-15-005).
* **Commit boundary** — ``_validate_canonical_entry``, which owns everything
  about the *claimed* ``payloadSnapshot.published`` of an assertion the
  CaseActor did not author (CLP-14-006 through CLP-14-009, CLP-15-003,
  CLP-15-004).  Enforcement through the production node is covered in
  ``test/core/behaviors/sync/nodes/test_chain_timestamp_guard.py``.

CLP-15-001 and CLP-15-002 are obligations on the *participant*, not the
CaseActor: CLP-15-005 forbids the CaseActor from reconstructing
participant-internal causal order it cannot verify, and ADR-0079 § "Residual
Uncertainty" says the same.  They are verified at the conformance layer by
``check_causal_edges`` (DEMOMA-22-005), which compares declared causal edges
against observed ledger order across a whole scenario — the only vantage point
from which an emission-order obligation is observable at all.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from test.ci.invariants.common import (
    check_causal_edges,
    check_clp14_timestamp_invariants,
)
from vultron.config.app import AppConfig
from vultron.core.behaviors.sync.nodes.canonical_entry import (
    _validate_canonical_entry,
)
from vultron.core.models.case_ledger import CaseLedger, compute_genesis_hash
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.errors import VultronCanonicalEntryError

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

CASE_ID = "https://example.org/cases/test-clp-14-15"
OBJ_ID = "https://example.org/activities/a1"
ACTOR_ID = "https://example.org/actors/participant"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = T0 + timedelta(seconds=1)
T2 = T0 + timedelta(seconds=2)


def _make_ledger() -> CaseLedger:
    genesis = compute_genesis_hash(CASE_ID, T0, CASE_ACTOR_ID)
    return CaseLedger(case_id=CASE_ID, genesis_hash=genesis)


def _minimal_payload(*, published: str, obj_id: str = OBJ_ID) -> dict:
    return {
        "type": "Add",
        "actor": ACTOR_ID,
        "published": published,
        "object": {
            "type": "Note",
            "id": obj_id,
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


def _replica(entries: list[dict]) -> dict[str, list[dict]]:
    """Wrap *entries* as the single-actor replica map the harness expects."""
    return {"case-actor": entries}


def _harness_entry(
    log_index: int,
    published: str | None,
    event_type: str = "add_note_to_case",
) -> dict:
    entry: dict = {
        "caseId": CASE_ID,
        "logIndex": log_index,
        "eventType": event_type,
        "disposition": "recorded",
        "payloadSnapshot": {"actor": ACTOR_ID},
    }
    if published is not None:
        entry["published"] = published
    return entry


# ---------------------------------------------------------------------------
# CLP-14: CaseActor Timestamp Invariants
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-14-001")
def test_clp_14_001_log_index_causal_order_by_construction():
    """CaseLedger.append() assigns sequential log_index, enforcing causal order."""
    lg = _make_ledger()
    e1 = lg.append(
        object_id=OBJ_ID, event_type="test", payload_snapshot={"x": 1}
    )
    e2 = lg.append(
        object_id=OBJ_ID, event_type="test", payload_snapshot={"x": 2}
    )
    assert e1.log_index < e2.log_index


@pytest.mark.spec("CLP-14-002")
def test_clp_14_002_published_non_null_enforced_by_model():
    """CaseLedgerEntry.published cannot be None (CoreObject enforces datetime)."""
    with pytest.raises(ValidationError):
        CaseLedgerEntry(
            case_id=CASE_ID,
            log_object_id=OBJ_ID,
            event_type="test",
            published=None,  # type: ignore[arg-type]
        )


@pytest.mark.spec("CLP-14-003")
def test_clp_14_003_published_timestamps_monotonic():
    """Commit timestamps MUST NOT regress in log_index order.

    This is an invariant *across* entries, so it is owned by the conformance
    harness that can see the whole ledger — not by the entry model, which never
    sees its own predecessor.  ``CaseLedger.append()`` satisfies it by
    construction (one writer, one clock); the harness is what would catch a
    replica that did not.
    """
    violations = check_clp14_timestamp_invariants(
        _replica(
            [
                _harness_entry(0, T1.isoformat(), event_type="create_case"),
                _harness_entry(1, T0.isoformat()),
            ]
        )
    )

    assert any("CLP-14-003" in v for v in violations), violations


@pytest.mark.spec("CLP-14-003")
def test_clp_14_003_monotonic_timestamps_accepted():
    """The same check passes on a well-ordered ledger (guards vacuity)."""
    violations = check_clp14_timestamp_invariants(
        _replica(
            [
                _harness_entry(0, T0.isoformat(), event_type="create_case"),
                _harness_entry(1, T1.isoformat()),
            ]
        )
    )

    assert violations == []


@pytest.mark.spec("CLP-14-004")
def test_clp_14_004_same_case_id_enforced_by_ledger():
    """CaseLedger entries always carry the ledger's own case_id."""
    lg = _make_ledger()
    e = lg.append(
        object_id=OBJ_ID, event_type="test", payload_snapshot={"x": 1}
    )
    assert e.case_id == CASE_ID


@pytest.mark.spec("CLP-14-005")
def test_clp_14_005_log_index_unique_by_construction():
    """CaseLedger.append() assigns unique log_index values."""
    lg = _make_ledger()
    e1 = lg.append(
        object_id=OBJ_ID, event_type="test", payload_snapshot={"x": 1}
    )
    e2 = lg.append(
        object_id=OBJ_ID + "2", event_type="test", payload_snapshot={"x": 2}
    )
    assert e1.log_index != e2.log_index


@pytest.mark.spec("CLP-14-006")
def test_clp_14_006_entry_not_before_case_creation():
    """An assertion stamped before the case was created is rejected.

    Checked at the commit boundary against the *claimed*
    ``payloadSnapshot.published``.  The one-hour offset clears the default
    five-minute clock-skew tolerance; that tolerance itself is covered in
    ``test_chain_timestamp_guard.py``.
    """
    case_created = datetime.now(tz=timezone.utc)
    with pytest.raises(VultronCanonicalEntryError, match="CLP-14-006"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(
                published=(case_created - timedelta(hours=1)).isoformat()
            ),
            case_published=case_created,
        )


@pytest.mark.spec("CLP-14-006")
def test_clp_14_006_harness_flags_entry_predating_case_creation():
    """The commit-timestamp half of CLP-14-006 belongs to the harness."""
    violations = check_clp14_timestamp_invariants(
        _replica(
            [
                _harness_entry(0, T1.isoformat(), event_type="create_case"),
                _harness_entry(1, T2.isoformat()),
                # logIndex 2 predates the create_case entry at logIndex 0.
                _harness_entry(2, T0.isoformat()),
            ]
        )
    )

    assert any("CLP-14-006" in v for v in violations), violations


@pytest.mark.spec("CLP-14-007")
def test_clp_14_007_future_timestamp_payload_rejected():
    """CaseActor SHOULD reject payload assertions timestamped far in the future."""
    far_future = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
    with pytest.raises(VultronCanonicalEntryError, match="CLP-14-007"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(published=far_future),
            case_published=T0,
        )


@pytest.mark.spec("CLP-14-008")
def test_clp_14_008_stale_timestamp_payload_rejected():
    """CaseActor SHOULD reject payload assertions timestamped far in the past."""
    far_past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    case_created = datetime(1999, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(VultronCanonicalEntryError, match="CLP-14-008"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(published=far_past.isoformat()),
            case_published=case_created,
        )


@pytest.mark.spec("CLP-14-009")
def test_clp_14_009_clock_skew_tolerance_configurable():
    """CLP-14-009: the CLP-14-007/008 thresholds are deployment-configurable.

    Nested under ``AppConfig.ledger`` to match the ``server``/``database``/
    ``actor`` convention, and settable from the environment as
    ``VULTRON_LEDGER__*`` — exercised end-to-end in
    ``test_chain_timestamp_guard.py``.
    """
    cfg = AppConfig()

    assert cfg.ledger.clock_skew_tolerance == timedelta(minutes=5)
    assert cfg.ledger.future_tolerance == timedelta(minutes=5)
    assert cfg.ledger.staleness_window == timedelta(days=7)


# ---------------------------------------------------------------------------
# CLP-15: Participant Assertion Timestamp Obligations
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-15-001")
@pytest.mark.spec("CLP-15-002")
def test_clp_15_001_002_out_of_order_emission_detected_at_ledger_order():
    """Emission-order obligations are observable only across a whole scenario.

    CLP-15-001 ("a participant MUST emit in causal order") and CLP-15-002
    ("MUST NOT batch in arbitrary order") bind the *participant*.  The CaseActor
    cannot enforce them per-assertion — CLP-15-005 forbids it from
    reconstructing participant-internal causal order it cannot verify.  What is
    verifiable is the consequence: a declared causal edge A → B must appear in
    the authoritative ledger with A before B (DEMOMA-22-005).  A participant
    that batched B ahead of A shows up here as an edge violation.
    """
    edges = [{"antecedent": "offer_report", "consequent": "add_note_to_case"}]
    replicas = _replica(
        [
            _harness_entry(0, T0.isoformat(), event_type="create_case"),
            # Consequent recorded before its antecedent.
            _harness_entry(1, T1.isoformat(), event_type="add_note_to_case"),
            _harness_entry(2, T2.isoformat(), event_type="offer_report"),
        ]
    )

    assert check_causal_edges(replicas, edges)

    ordered = _replica(
        [
            _harness_entry(0, T0.isoformat(), event_type="create_case"),
            _harness_entry(1, T1.isoformat(), event_type="offer_report"),
            _harness_entry(2, T2.isoformat(), event_type="add_note_to_case"),
        ]
    )

    assert check_causal_edges(ordered, edges) == []


@pytest.mark.spec("CLP-15-003")
def test_clp_15_003_participant_published_timestamps_nondecreasing():
    """A participant's claimed timestamps MUST NOT regress within its stream."""
    with pytest.raises(VultronCanonicalEntryError, match="CLP-15-003"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(
                published=T0.isoformat(), obj_id=OBJ_ID + "/y"
            ),
            case_published=T0,
            prev_actor_published=T2,
            staleness_window=None,
        )


@pytest.mark.spec("CLP-15-003")
def test_clp_15_003_monotonicity_is_scoped_to_one_actor():
    """Cross-actor timestamp comparison is never performed (ADR-0079 option C).

    Two participants' clocks are not comparable, so ``prev_actor_published`` is
    resolved per snapshot actor.  With no predecessor for *this* actor, an
    earlier claimed timestamp is legitimate and MUST be accepted.
    """
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        disposition="recorded",
        event_type="test",
        payload_snapshot=_minimal_payload(
            published=T0.isoformat(), obj_id=OBJ_ID + "/y"
        ),
        case_published=T0,
        prev_actor_published=None,
        staleness_window=None,
    )


@pytest.mark.spec("CLP-15-004")
def test_clp_15_004_participant_timestamp_reflects_event_time():
    """A timestamp that cannot be an event time is rejected as inaccurate.

    CLP-15-004 asks participants to stamp the actual event time rather than the
    batch-submission or retry time.  The CaseActor cannot know the true event
    time, but it can reject a claim that is impossible — one ahead of its own
    clock.  This is the same guard as CLP-14-007, cited from the participant
    obligation it enforces.
    """
    far_future = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
    with pytest.raises(VultronCanonicalEntryError, match="CLP-14-007"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(published=far_future),
            case_published=T0,
        )


@pytest.mark.spec("CLP-15-005")
def test_clp_15_005_caseactor_records_observation_order():
    """CaseActor records observation-order sequence via CaseLedger.append()."""
    lg = _make_ledger()
    e1 = lg.append(
        object_id=OBJ_ID + "/first",
        event_type="first",
        payload_snapshot={"x": 1},
    )
    e2 = lg.append(
        object_id=OBJ_ID + "/second",
        event_type="second",
        payload_snapshot={"x": 2},
    )
    assert e1.log_index < e2.log_index
