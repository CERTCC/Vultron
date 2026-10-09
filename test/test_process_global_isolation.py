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

"""Process-global state is reset between tests by the root conftest (TB-06-003).

Each class is an **ordered pair**: the first test leaves process-global state
behind exactly as production code would, and the second asserts it starts
without it. They live at the test root, outside every directory that used to
carry its own clearing fixture, so they exercise the root ``test/conftest.py``
fixtures and nothing else.

The pair only means something when both tests run, in order, in one process.
The first sets a module flag; the second fails loudly when the flag is unset
rather than passing on an empty precondition (a vacuous assertion).  Under
``-n`` the module-wide ``xdist_group`` mark keeps every pair on one worker;
the ``--dist loadgroup`` in ``addopts`` is what makes xdist honor it.

Regression for #3996: a node that wrote ``/participant`` only when it found a
participant left the previous test's participant on the process-global
``py_trees`` blackboard, and a later use-case test outside
``test/core/behaviors/`` (which had no clearing fixture) transitioned it.
"""

from __future__ import annotations

import logging

import py_trees
import pytest
from py_trees.common import Status

from test.conftest import TEST_ACTOR_ID
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_gap_buffer import get_ledger_gap_buffer
from vultron.logging_setup import (
    restore_third_party_log_levels,
    suppress_third_party_info_noise,
)

pytestmark = pytest.mark.xdist_group("process_global_isolation")

#: A node-written key that is *not* on ``BTBridge``'s ``managed_keys`` list, so
#: the bridge does not restore it when the execution ends.
_LEAKED_KEY = "participant"

_CASE_ID = "https://example.org/cases/isolation"

#: Set by the first test of each pair; read by the second.
_RAN: dict[str, bool] = {
    "blackboard": False,
    "gap_buffer": False,
    "log_levels": False,
}


class _WriteParticipantNode(py_trees.behaviour.Behaviour):
    """Writes an output key straight to storage, as a port-based node does."""

    def update(self) -> Status:
        py_trees.blackboard.Blackboard.storage[f"/{_LEAKED_KEY}"] = (
            "stale-participant-from-a-previous-test"
        )
        return Status.SUCCESS


def _require_writer(name: str) -> None:
    assert _RAN[name], (
        f"the {name!r} writer test did not run before this one in this "
        "process, so this assertion would pass on nothing — run the whole "
        "module, in order, without xdist splitting it"
    )


class TestBlackboardIsClearedBetweenTests:
    def test_1_bt_execution_leaves_an_unmanaged_key_behind(self):
        bridge = BTBridge(
            datalayer=SqliteDataLayer(
                "sqlite:///:memory:", actor_id=TEST_ACTOR_ID
            )
        )

        result = bridge.execute_with_setup(
            _WriteParticipantNode(name="WriteParticipant"),
            actor_id=TEST_ACTOR_ID,
        )

        assert result.status == Status.SUCCESS
        # The precondition of the next test: the bridge does not clean this up.
        storage = py_trees.blackboard.Blackboard.storage
        assert f"/{_LEAKED_KEY}" in storage
        _RAN["blackboard"] = True

    def test_2_next_test_starts_without_the_stale_key(self):
        _require_writer("blackboard")
        assert f"/{_LEAKED_KEY}" not in py_trees.blackboard.Blackboard.storage


def _gap_entry() -> CaseLedgerEntry:
    """An entry far enough ahead of an empty chain to be buffered as a gap."""
    chain = HashChainLedgerRecord(
        case_id=_CASE_ID,
        log_index=3,
        object_id=f"{_CASE_ID}/activities/act-3",
        event_type="test_event",
        payload_snapshot={"log_index": 3},
        prev_log_hash="a" * 64,
    )
    return CaseLedgerEntry(
        case_id=chain.case_id,
        log_index=chain.log_index,
        term=chain.term,
        log_object_id=chain.object_id,
        event_type=chain.event_type,
        payload_snapshot=dict(chain.payload_snapshot),
        prev_log_hash=chain.prev_log_hash,
        entry_hash=chain.entry_hash,
    )


class TestLedgerGapBufferIsResetBetweenTests:
    def test_1_received_sync_buffers_an_out_of_order_entry(self):
        buffer = get_ledger_gap_buffer(TEST_ACTOR_ID)

        assert buffer.buffer(_gap_entry()) is True
        assert buffer.depth(_CASE_ID) == 1
        _RAN["gap_buffer"] = True

    def test_2_next_test_starts_with_an_empty_buffer(self):
        _require_writer("gap_buffer")
        assert get_ledger_gap_buffer(TEST_ACTOR_ID).depth(_CASE_ID) == 0


class TestThirdPartyLogSuppressionIsUndoneBetweenTests:
    def test_1_entry_point_suppresses_without_restoring(self):
        logging.getLogger("transitions").setLevel(logging.NOTSET)

        # As the demo CLI does: suppress, and never restore.
        suppress_third_party_info_noise(logging.INFO)

        assert logging.getLogger("transitions").level == logging.WARNING
        _RAN["log_levels"] = True

    def test_2_next_tests_restore_keeps_the_level_it_set(self):
        _require_writer("log_levels")
        transitions_logger = logging.getLogger("transitions")
        transitions_logger.setLevel(logging.ERROR)

        # A stale saved-levels map would reset this to the previous test's
        # NOTSET.
        restore_third_party_log_levels()

        assert transitions_logger.level == logging.ERROR
