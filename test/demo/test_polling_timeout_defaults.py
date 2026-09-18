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

"""Regression tests for polling helper timeout defaults (#2305).

``wait_for_case_participants`` shipped with a 5.0 s default that fires before
cross-container participant-count convergence under CI contention.  The new
default must be at least 15.0 s.
"""

import inspect
from unittest.mock import MagicMock, patch

import vultron.demo.helpers.polling as polling
from vultron.demo.helpers.polling import (
    LATE_JOINER_REPLICA_TIMEOUT,
    REPLICA_PARTICIPANT_TIMEOUT,
    wait_for_case_participants,
    wait_for_participants_on_replicas,
)


def test_wait_for_case_participants_default_is_at_least_15s():
    """Default timeout must survive cross-container CI contention (#2305)."""
    sig = inspect.signature(wait_for_case_participants)
    default = sig.parameters["timeout_seconds"].default
    assert default >= 15.0, (
        f"wait_for_case_participants default ({default}s) is too short; "
        "must be >=15 s for cross-container convergence under CI load"
    )


# ---------------------------------------------------------------------------
# wait_for_participants_on_replicas — the single implementation of the
# per-scenario replica participant-wait loop (#2852).
# ---------------------------------------------------------------------------


def _capture_participant_timeouts():
    """Return (recorder_dict, fake_wait) capturing timeout per replica client."""
    timeouts_by_client_id: dict[int, float] = {}

    def _fake_wait(
        vendor_client, case_id, expected_actor_ids, timeout_seconds, **_kw
    ):
        timeouts_by_client_id[id(vendor_client)] = timeout_seconds

    return timeouts_by_client_id, _fake_wait


def test_replica_loop_gives_late_joiner_extended_timeout():
    """Late joiners must receive at least 30 s for participant propagation (#2852).

    fvv previously omitted the loop entirely, so its late joiner used the 15 s
    default and could time out spuriously under CI load.  The consolidated
    helper must grant late joiners the 30 s budget.
    """
    finder = MagicMock()
    late = MagicMock()
    timeouts, fake_wait = _capture_participant_timeouts()

    with patch.object(polling, "wait_for_case_participants", fake_wait):
        wait_for_participants_on_replicas(
            replica_clients=(finder, late),
            case_id="urn:test:case",
            expected_actor_ids={"a", "b"},
            late_joiners=(late,),
        )

    assert timeouts[id(late)] == LATE_JOINER_REPLICA_TIMEOUT
    assert timeouts[id(late)] >= 30.0
    assert timeouts[id(finder)] == REPLICA_PARTICIPANT_TIMEOUT


def test_replica_loop_polls_every_replica_once():
    """Each replica in the sequence is polled exactly once, in order."""
    clients = [MagicMock(name=f"c{i}") for i in range(3)]
    polled: list[int] = []

    def _fake_wait(vendor_client, case_id, expected_actor_ids, **_kw):
        polled.append(id(vendor_client))

    with patch.object(polling, "wait_for_case_participants", _fake_wait):
        wait_for_participants_on_replicas(
            replica_clients=tuple(clients),
            case_id="urn:test:case",
            expected_actor_ids={"a"},
        )

    assert polled == [id(c) for c in clients]


def test_replica_loop_uses_default_when_no_late_joiners():
    """With no late joiners, every replica uses the default timeout."""
    clients = [MagicMock() for _ in range(2)]
    timeouts, fake_wait = _capture_participant_timeouts()

    with patch.object(polling, "wait_for_case_participants", fake_wait):
        wait_for_participants_on_replicas(
            replica_clients=tuple(clients),
            case_id="urn:test:case",
            expected_actor_ids={"a"},
        )

    assert all(t == REPLICA_PARTICIPANT_TIMEOUT for t in timeouts.values())
