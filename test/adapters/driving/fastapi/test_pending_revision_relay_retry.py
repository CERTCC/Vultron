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

"""The startup retry of an owed creation-time revision relay (EP-04-011, #4121).

``retry_pending_creation_time_revision_relays`` finds every
``PendingCreationTimeRevisionRelay`` marker and re-runs the relay for its
case, so a relay a previous process run failed is completed even if the
proposal is never delivered again.  The node's own outcomes are pinned in
``test/core/behaviors/case/nodes/test_embargo_revision.py``; these tests pin
the runner: what it scans, what it counts, and that a failure never escapes
into server startup.
"""

import logging
from typing import Any, cast

import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.case.nodes.revision_relay_fixtures import (
    CASE_ID,
    EMBARGO_ID,
    MANAGER,
    OWNER,
    PROPOSAL_ID,
    index,
    invites,
    owe,
    owed,
    participant,
    seed,
)
from vultron.adapters.driving.fastapi import pending_retry
from vultron.adapters.driving.fastapi.pending_retry import (
    retry_pending_creation_time_revision_relays,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.enums.roles import CVDRole


@pytest.fixture()
def scenario() -> BTTestScenario:
    """The CASE_MANAGER's own store, holding a REVISE case it owes a relay."""
    owed = BTTestScenario(MANAGER)
    seed(owed)
    owe(owed)
    return owed


@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("EP-08-002")
def test_an_owed_relay_is_sent_indexed_and_discharged(
    scenario: BTTestScenario,
) -> None:
    count = retry_pending_creation_time_revision_relays(
        datalayers_factory=lambda: {MANAGER: scenario.dl}
    )

    assert count == 1
    (invite,) = invites(scenario)
    assert invite.id_ == PROPOSAL_ID
    assert index(scenario) == {EMBARGO_ID: PROPOSAL_ID}
    assert owed(scenario) is None


@pytest.mark.spec("EP-04-011")
def test_a_second_run_sends_nothing(scenario: BTTestScenario) -> None:
    stores = {MANAGER: scenario.dl}
    retry_pending_creation_time_revision_relays(
        datalayers_factory=lambda: stores
    )

    assert (
        retry_pending_creation_time_revision_relays(
            datalayers_factory=lambda: stores
        )
        == 0
    )
    assert len(invites(scenario)) == 1


@pytest.mark.spec("EP-04-011")
def test_a_store_owing_nothing_counts_nothing() -> None:
    clean = BTTestScenario(MANAGER)
    seed(clean)

    assert (
        retry_pending_creation_time_revision_relays(
            datalayers_factory=lambda: {MANAGER: clean.dl}
        )
        == 0
    )
    assert invites(clean) == []


@pytest.mark.spec("EP-04-011")
def test_a_failed_relay_is_logged_and_kept_for_the_next_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A relay that cannot complete must not stop the server starting; the
    obligation stays so a later run can finish it."""
    broken = BTTestScenario(MANAGER)
    seed(broken, report_author=None)
    owe(broken)

    with caplog.at_level(logging.ERROR, logger=pending_retry.__name__):
        count = retry_pending_creation_time_revision_relays(
            datalayers_factory=lambda: {MANAGER: broken.dl}
        )

    assert count == 0
    assert owed(broken) is not None
    assert invites(broken) == []
    assert any(CASE_ID in r.getMessage() for r in caplog.records)


@pytest.mark.spec("EP-04-011")
def test_a_store_that_cannot_be_scanned_does_not_stop_the_others(
    scenario: BTTestScenario, caplog: pytest.LogCaptureFixture
) -> None:
    class _Unreadable:
        def list_objects(self, _table: str) -> list[Any]:
            raise RuntimeError("store unavailable")

    with caplog.at_level(logging.ERROR, logger=pending_retry.__name__):
        count = retry_pending_creation_time_revision_relays(
            datalayers_factory=lambda: {
                "https://example.org/actors/unreadable": cast(
                    DataLayer, _Unreadable()
                ),
                MANAGER: scenario.dl,
            }
        )

    assert count == 1
    assert any("store unavailable" in r.getMessage() for r in caplog.records)


@pytest.mark.spec("EP-04-011")
def test_the_default_scan_covers_every_hosted_actor(
    scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On restart the actor cache is empty; the hosted actors' own stores are
    still scanned (ADR-0073)."""
    monkeypatch.setattr(pending_retry, "get_all_actor_datalayers", lambda: {})
    monkeypatch.setattr(
        pending_retry.actor_hosts, "hosted_actor_ids", lambda: [MANAGER]
    )
    monkeypatch.setattr(
        pending_retry,
        "get_datalayer",
        lambda actor_id: scenario.dl if actor_id == MANAGER else None,
    )

    assert retry_pending_creation_time_revision_relays() == 1
    assert owed(scenario) is None


@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("CM-14-007")
def test_a_case_not_yet_created_keeps_its_obligation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With no genesis entry the relay waits: nothing is sent, the obligation
    is kept, and the runner says so at INFO (a designed deferral, not an
    error)."""
    pending = BTTestScenario(MANAGER)
    seed(pending, created=False)
    owe(pending)

    with caplog.at_level(logging.INFO, logger=pending_retry.__name__):
        count = retry_pending_creation_time_revision_relays(
            datalayers_factory=lambda: {MANAGER: pending.dl}
        )

    assert count == 0
    assert invites(pending) == []
    assert owed(pending) is not None
    kept = [r for r in caplog.records if "still owed" in r.getMessage()]
    assert [r.levelno for r in kept] == [logging.INFO]


@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("BT-17-001")
def test_an_actor_no_longer_case_manager_relays_nothing(
    scenario: BTTestScenario, caplog: pytest.LogCaptureFixture
) -> None:
    """CASE_MANAGER moved to another actor after the relay failed: the gate
    turns the former holder away, so it emits nothing, and the obligation is
    kept rather than discharged by an actor no longer entitled to it."""
    scenario.dl.save(participant(MANAGER, CVDRole.FINDER))
    scenario.dl.save(participant(OWNER, CVDRole.VENDOR, CVDRole.CASE_MANAGER))

    with caplog.at_level(logging.INFO, logger=pending_retry.__name__):
        count = retry_pending_creation_time_revision_relays(
            datalayers_factory=lambda: {MANAGER: scenario.dl}
        )

    assert count == 0
    # The gate skipped (the tree succeeded with the obligation still held),
    # rather than the relay failing.
    # Only the runner's own records: other tests may leave BTBridge's
    # INFO lifecycle lines propagating into caplog.
    runner = [r for r in caplog.records if r.name == pending_retry.__name__]
    assert [r.levelno for r in runner] == [logging.INFO]
    assert "still owed" in runner[0].getMessage()
    assert invites(scenario) == []
    assert owed(scenario) is not None
