#!/usr/bin/env python
"""Unit tests for sync conditions nodes."""

from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    _make_entry,
    _make_event,
)
from vultron.core.behaviors.sync.nodes import (
    CheckIsOwnCaseActorNode,
    CheckLedgerFreshnessNode,
)
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry


def test_check_is_own_case_actor_succeeds_for_case_owner(bridge, case_actor):
    entry = _make_entry(0)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=CheckIsOwnCaseActorNode(name="CheckIsOwnCaseActor"),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS


class TestCheckLedgerFreshnessNodeWithCaseIdArg:
    """Tests using a case_id constructor arg (no blackboard key needed)."""

    def test_empty_ledger_is_fresh(self, bridge):
        """SYNC-10-005: empty prefix is trivially fresh."""
        result = bridge.execute_with_setup(
            tree=CheckLedgerFreshnessNode(
                case_id=CASE_ID, name="CheckFreshness"
            ),
            actor_id=OWNER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

    def test_contiguous_chain_is_fresh(self, bridge, datalayer, case_obj):
        e0 = _make_entry(0, case_obj.genesis_hash)
        datalayer.save(e0)
        e1 = _make_entry(1, e0.entry_hash)
        datalayer.save(e1)

        result = bridge.execute_with_setup(
            tree=CheckLedgerFreshnessNode(
                case_id=CASE_ID, name="CheckFreshness"
            ),
            actor_id=OWNER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

    def test_gap_in_ledger_is_stale(self, bridge, datalayer):
        """SYNC-10-004: any gap blocks the gate."""
        e0 = _make_entry(0)
        datalayer.save(e0)
        # Skip index 1; jump to index 2
        e2 = VultronCaseLedgerEntry(
            case_id=CASE_ID,
            log_index=2,
            log_object_id="https://example.org/activities/log-2",
            event_type="test_event",
            payload_snapshot={"log_index": 2},
            prev_log_hash=e0.entry_hash,
            entry_hash="f" * 64,
        )
        datalayer.save(e2)

        result = bridge.execute_with_setup(
            tree=CheckLedgerFreshnessNode(
                case_id=CASE_ID, name="CheckFreshness"
            ),
            actor_id=OWNER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE

    def test_hash_mismatch_is_stale(self, bridge, datalayer):
        """SYNC-10-004: hash mismatch at any link is stale."""
        e0 = _make_entry(0)
        datalayer.save(e0)
        bad_e1 = VultronCaseLedgerEntry(
            case_id=CASE_ID,
            log_index=1,
            log_object_id="https://example.org/activities/log-1",
            event_type="test_event",
            payload_snapshot={"log_index": 1},
            prev_log_hash="0" * 64,  # wrong: does not match e0.entry_hash
            entry_hash="1" * 64,
        )
        datalayer.save(bad_e1)

        result = bridge.execute_with_setup(
            tree=CheckLedgerFreshnessNode(
                case_id=CASE_ID, name="CheckFreshness"
            ),
            actor_id=OWNER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE

    def test_stale_result_emits_warning(self, bridge, datalayer, caplog):
        """SYNC-10-002: stale gate MUST surface an explicit stale condition."""
        import logging

        # Create a gap
        e0 = _make_entry(0)
        datalayer.save(e0)
        e2 = VultronCaseLedgerEntry(
            case_id=CASE_ID,
            log_index=2,
            log_object_id="https://example.org/activities/log-2",
            event_type="test_event",
            payload_snapshot={"log_index": 2},
            prev_log_hash=e0.entry_hash,
            entry_hash="a" * 64,
        )
        datalayer.save(e2)

        with caplog.at_level(
            logging.WARNING,
            logger="vultron.core.behaviors.sync.nodes.conditions",
        ):
            bridge.execute_with_setup(
                tree=CheckLedgerFreshnessNode(
                    case_id=CASE_ID, name="CheckFreshness"
                ),
                actor_id=OWNER_ACTOR_ID,
            )

        assert any(
            "NOT fresh" in r.message or "stale" in r.message.lower()
            for r in caplog.records
            if r.levelno == logging.WARNING
        )

    def test_fresh_result_no_warning(self, bridge, caplog):
        """Happy path emits no WARNING."""
        import logging

        with caplog.at_level(
            logging.WARNING,
            logger="vultron.core.behaviors.sync.nodes.conditions",
        ):
            bridge.execute_with_setup(
                tree=CheckLedgerFreshnessNode(
                    case_id=CASE_ID, name="CheckFreshness"
                ),
                actor_id=OWNER_ACTOR_ID,
            )

        warning_msgs = [
            r for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert not warning_msgs


class TestCheckLedgerFreshnessNodeWithBlackboard:
    """Tests where case_id is read from the blackboard."""

    def test_blackboard_case_id_fresh(self, bridge):
        result = bridge.execute_with_setup(
            tree=CheckLedgerFreshnessNode(name="CheckFreshness"),
            actor_id=OWNER_ACTOR_ID,
            case_id=CASE_ID,
        )
        assert result.status == Status.SUCCESS

    def test_missing_blackboard_case_id_fails(self, bridge):
        """No case_id on blackboard and none at construction → FAILURE."""
        result = bridge.execute_with_setup(
            tree=CheckLedgerFreshnessNode(name="CheckFreshness"),
            actor_id=OWNER_ACTOR_ID,
            # case_id intentionally omitted
        )
        assert result.status == Status.FAILURE
