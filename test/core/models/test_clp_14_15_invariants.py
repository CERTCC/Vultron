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

"""Spec coverage stubs for CLP-14 and CLP-15 (CaseLedger causal ordering).

Tests for invariants already enforced by the existing model/ledger code are
written as passing assertions. Tests for invariants NOT YET enforced are marked
@pytest.mark.xfail(strict=True, ...) — runtime enforcement is tracked as #2679.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

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


@pytest.mark.xfail(
    strict=True,
    reason="CLP-14-003: no cross-entry monotonic timestamp check. Tracked by #2679.",
)
@pytest.mark.spec("CLP-14-003")
def test_clp_14_003_published_timestamps_monotonic():
    """Consecutive entries MUST have non-decreasing published timestamps."""
    e1 = CaseLedgerEntry(
        case_id=CASE_ID,
        log_index=0,
        log_object_id=OBJ_ID,
        event_type="t",
        published=T1,
    )
    e2 = CaseLedgerEntry(
        case_id=CASE_ID,
        log_index=1,
        log_object_id=OBJ_ID,
        event_type="t",
        published=T0,
    )
    # T0 < T1 — invariant violated; no current check catches it
    assert e2.published >= e1.published


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


@pytest.mark.xfail(
    strict=True,
    reason="CLP-14-006: no entry.published >= case.published validation. Tracked by #2679.",
)
@pytest.mark.spec("CLP-14-006")
def test_clp_14_006_entry_not_before_case_creation():
    """Entry published timestamp MUST be on or after the case's published timestamp."""
    case_published = T1
    entry_published = T0  # before case creation — violation
    e = CaseLedgerEntry(
        case_id=CASE_ID,
        log_index=0,
        log_object_id=OBJ_ID,
        event_type="t",
        published=entry_published,
    )
    # T0 < T1 — invariant violated; no current check prevents construction
    assert e.published >= case_published


@pytest.mark.xfail(
    strict=True,
    reason="CLP-14-007: future-timestamp SHOULD rejection not implemented. Tracked by #2679.",
)
@pytest.mark.spec("CLP-14-007")
def test_clp_14_007_future_timestamp_payload_rejected():
    """CaseActor SHOULD reject payload assertions timestamped implausibly far in the future."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _validate_canonical_entry,
    )

    far_future = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(published=far_future),
        )


@pytest.mark.xfail(
    strict=True,
    reason="CLP-14-008: stale-timestamp SHOULD rejection not implemented. Tracked by #2679.",
)
@pytest.mark.spec("CLP-14-008")
def test_clp_14_008_stale_timestamp_payload_rejected():
    """CaseActor SHOULD reject payload assertions timestamped implausibly far in the past."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _validate_canonical_entry,
    )

    far_past = datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat()
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(published=far_past),
        )


@pytest.mark.xfail(
    strict=True,
    reason="CLP-14-009: configurable clock-skew tolerance not exposed. Tracked by #2679.",
)
@pytest.mark.spec("CLP-14-009")
def test_clp_14_009_clock_skew_tolerance_configurable():
    """Clock-skew tolerance and staleness window MAY be configurable per deployment."""
    from vultron.config.app import AppConfig

    cfg = AppConfig()
    assert hasattr(
        cfg, "ledger_clock_skew_tolerance_seconds"
    ), "CLP-14-009: AppConfig does not yet expose ledger_clock_skew_tolerance_seconds"


# ---------------------------------------------------------------------------
# CLP-15: Participant Assertion Timestamp Obligations
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="CLP-15-001: participant causal-order enforcement not implemented. Tracked by #2679.",
)
@pytest.mark.spec("CLP-15-001")
def test_clp_15_001_participant_emits_in_causal_order():
    """CaseActor SHOULD detect and reject participant activities received out of causal order."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _validate_canonical_entry,
    )

    t_later = T1.isoformat()
    t_earlier = T0.isoformat()
    # Receiving t_later first, then t_earlier violates causal order
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        disposition="recorded",
        event_type="test",
        payload_snapshot=_minimal_payload(
            published=t_later, obj_id=OBJ_ID + "/b"
        ),
    )
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(
                published=t_earlier, obj_id=OBJ_ID + "/a"
            ),
        )


@pytest.mark.xfail(
    strict=True,
    reason="CLP-15-002: out-of-order batch detection not implemented. Tracked by #2679.",
)
@pytest.mark.spec("CLP-15-002")
def test_clp_15_002_participant_must_not_batch_in_arbitrary_order():
    """Participant MUST NOT submit causally ordered activities in arbitrary order."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _validate_canonical_entry,
    )

    t_c = T2.isoformat()
    t_a = T0.isoformat()
    # Emitting C before A (out of causal order) violates CLP-15-002
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        disposition="recorded",
        event_type="test",
        payload_snapshot=_minimal_payload(published=t_c, obj_id=OBJ_ID + "/c"),
    )
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(
                published=t_a, obj_id=OBJ_ID + "/a"
            ),
        )


@pytest.mark.xfail(
    strict=True,
    reason="CLP-15-003: participant timestamp monotonicity not enforced. Tracked by #2679.",
)
@pytest.mark.spec("CLP-15-003")
def test_clp_15_003_participant_published_timestamps_nondecreasing():
    """Participant published timestamps MUST be non-decreasing for causally related activities."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _validate_canonical_entry,
    )

    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        disposition="recorded",
        event_type="test",
        payload_snapshot=_minimal_payload(
            published=T2.isoformat(), obj_id=OBJ_ID + "/x"
        ),
    )
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(
                published=T0.isoformat(), obj_id=OBJ_ID + "/y"
            ),
        )


@pytest.mark.xfail(
    strict=True,
    reason="CLP-15-004: timestamp accuracy SHOULD-check not implemented. Tracked by #2679.",
)
@pytest.mark.spec("CLP-15-004")
def test_clp_15_004_participant_timestamp_reflects_event_time():
    """Participant SHOULD assign timestamps reflecting actual event time, not far future."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _validate_canonical_entry,
    )

    far_future = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=ACTOR_ID,
            disposition="recorded",
            event_type="test",
            payload_snapshot=_minimal_payload(published=far_future),
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
