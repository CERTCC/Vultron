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

"""CLP-14/CLP-15 timestamp enforcement at the ``CreateLogEntryNode`` boundary.

``_validate_entry_timestamps`` existed since ``fcc836ce8`` but the only
production call site never supplied the temporal context it needed, so the
guard never ran (ISSUE-2824).  These tests exercise it through the node — the
layer where it actually has to fire — rather than by calling the private
validator directly, so a future regression that unwires the call site fails
here.

Spec: CLP-14-006, CLP-14-007, CLP-14-009, CLP-15-003, CLP-07-011.
"""

from datetime import datetime, timedelta, timezone

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.config.app import config_override
from vultron.core.behaviors.sync.nodes import CreateLogEntryNode
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry

_ZERO_HASH: str = "0" * 64

# The case is created an hour ago so a snapshot can be stamped either side of
# it without tripping the staleness window (CLP-14-008, default seven days).
CASE_CREATED = datetime.now(tz=timezone.utc) - timedelta(hours=1)


def _note_snapshot(actor_id: str, published: datetime) -> dict[str, object]:
    return {
        "type": "Add",
        "actor": actor_id,
        "published": published.isoformat(),
        "object": {
            "type": "Note",
            "id": f"https://example.org/notes/{published.timestamp()}",
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


@pytest.fixture
def datalayer():
    """Owner-scoped store, shadowing the package fixture.

    These trees execute as ``OWNER_ACTOR_ID``, and ``BTBridge._store_for_actor``
    reconciles the store to the executing actor (BT-05-005).  A
    participant-scoped store would leave the seeded case and predecessor entries
    in a store the node never reads, and every timestamp check would silently
    skip for want of context — the exact vacuous-pass shape this file exists to
    prevent.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER_ACTOR_ID)


@pytest.fixture
def timed_case(datalayer):
    """A stored case whose ``published`` is a known hour in the past."""
    case = VulnerabilityCase(
        id_=CASE_ID,
        attributed_to=OWNER_ACTOR_ID,
        published=CASE_CREATED,
    )
    datalayer.save(case)
    return case


def _persist_prior_entry(
    datalayer, actor_id: str, published: datetime, log_index: int = 0
) -> None:
    """Store one recorded entry so the node has a per-actor predecessor."""
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/prior-{log_index}",
            event_type="note_added",
            payload_snapshot=_note_snapshot(actor_id, published),
            prev_log_hash=_ZERO_HASH,
        )
    )
    datalayer.save(entry)


def _run(bridge, snapshot: dict[str, object], tail_index: int = -1):
    return bridge.execute_with_setup(
        tree=CreateLogEntryNode(
            case_id=CASE_ID,
            object_id="https://example.org/activities/act-under-test",
            event_type="note_added",
            payload_snapshot=snapshot,
            name="CreateLogEntry",
        ),
        actor_id=OWNER_ACTOR_ID,
        tail_hash=_ZERO_HASH,
        tail_index=tail_index,
    )


@pytest.mark.spec("CLP-14-006")
def test_create_log_entry_node_rejects_payload_published_before_case_created(
    bridge, timed_case
):
    """An assertion stamped before the case existed is a CLP-14-006 violation."""
    result = _run(
        bridge,
        _note_snapshot(
            PARTICIPANT_ACTOR_ID, CASE_CREATED - timedelta(minutes=30)
        ),
    )

    assert result.status == Status.FAILURE
    assert "CLP-14-006" in result.feedback_message


@pytest.mark.spec("CLP-14-006")
def test_create_log_entry_node_tolerates_small_skew_before_case_created(
    bridge, timed_case
):
    """Clock skew within tolerance is not a violation (ADR-0079 option C)."""
    result = _run(
        bridge,
        _note_snapshot(
            PARTICIPANT_ACTOR_ID, CASE_CREATED - timedelta(seconds=30)
        ),
    )

    assert result.status == Status.SUCCESS


@pytest.mark.spec("CLP-15-003")
def test_create_log_entry_node_rejects_same_actor_timestamp_regression(
    bridge, datalayer, timed_case
):
    """A participant's claimed timestamps MUST NOT regress within its stream."""
    _persist_prior_entry(
        datalayer,
        PARTICIPANT_ACTOR_ID,
        CASE_CREATED + timedelta(minutes=10),
    )

    result = _run(
        bridge,
        _note_snapshot(
            PARTICIPANT_ACTOR_ID, CASE_CREATED + timedelta(minutes=5)
        ),
        tail_index=0,
    )

    assert result.status == Status.FAILURE
    assert "CLP-15-003" in result.feedback_message


@pytest.mark.spec("CLP-15-003")
def test_create_log_entry_node_accepts_cross_actor_clock_skew(
    bridge, datalayer, timed_case
):
    """Monotonicity is per participant — never across participants.

    ADR-0079 rejected wall-clock ordering (option C) precisely because two
    actors' clocks cannot be compared.  A later-committed entry from a
    *different* actor carrying an earlier claimed timestamp is legitimate.
    """
    _persist_prior_entry(
        datalayer, OWNER_ACTOR_ID, CASE_CREATED + timedelta(minutes=10)
    )

    result = _run(
        bridge,
        _note_snapshot(
            PARTICIPANT_ACTOR_ID, CASE_CREATED + timedelta(minutes=5)
        ),
        tail_index=0,
    )

    assert result.status == Status.SUCCESS


@pytest.mark.spec("CLP-15-003")
def test_create_log_entry_node_accepts_redelivery_of_earlier_assertion(
    bridge, datalayer, timed_case
):
    """A retry is a duplicate, not a regression (ADR-0037).

    Out-of-order and retried delivery is designed for.  If the ordering check
    fired on a redelivery, a retry of assertion A arriving after the same
    actor's later assertion B would be rejected outright instead of being
    recognised by the idempotency path.
    """
    retried = _note_snapshot(
        PARTICIPANT_ACTOR_ID, CASE_CREATED + timedelta(minutes=5)
    )
    # A is already recorded, and so is the actor's later assertion B.
    _persist_prior_entry(
        datalayer,
        PARTICIPANT_ACTOR_ID,
        CASE_CREATED + timedelta(minutes=5),
        log_index=0,
    )
    _persist_prior_entry(
        datalayer,
        PARTICIPANT_ACTOR_ID,
        CASE_CREATED + timedelta(minutes=10),
        log_index=1,
    )

    result = _run(bridge, retried, tail_index=1)

    assert result.status == Status.SUCCESS


@pytest.mark.spec("CLP-07-011")
def test_create_log_entry_node_rejects_snapshot_without_published(
    bridge, timed_case
):
    """A snapshot missing ``published`` is not a verbatim AS2 activity."""
    snapshot = _note_snapshot(PARTICIPANT_ACTOR_ID, CASE_CREATED)
    del snapshot["published"]

    result = _run(bridge, snapshot)

    assert result.status == Status.FAILURE
    assert "CLP-07-011" in result.feedback_message


@pytest.mark.spec("CLP-14-007")
def test_create_log_entry_node_rejects_far_future_payload_published(
    bridge, timed_case
):
    """A claimed timestamp far ahead of the CaseActor's clock is rejected."""
    result = _run(
        bridge,
        _note_snapshot(
            PARTICIPANT_ACTOR_ID, datetime(2099, 1, 1, tzinfo=timezone.utc)
        ),
    )

    assert result.status == Status.FAILURE
    assert "CLP-14-007" in result.feedback_message


@pytest.mark.spec("CLP-14-009")
def test_create_log_entry_node_honours_configured_skew_tolerance(
    bridge, timed_case
):
    """CLP-14-009: the deployment can widen the clock-skew tolerance.

    The same snapshot that trips CLP-14-006 at the default tolerance is
    accepted once the tolerance is configured wide enough to cover it.
    """
    snapshot = _note_snapshot(
        PARTICIPANT_ACTOR_ID, CASE_CREATED - timedelta(minutes=30)
    )

    with config_override(
        VULTRON_LEDGER__CLOCK_SKEW_TOLERANCE_SECONDS="3600"
    ) as cfg:
        # Assert the override actually bound.  Without this the test would
        # still pass if the env prefix drifted and the default (300 s) stayed
        # in force only because some other check happened not to fire.
        assert cfg.ledger.clock_skew_tolerance == timedelta(hours=1)
        result = _run(bridge, snapshot)

    assert result.status == Status.SUCCESS
