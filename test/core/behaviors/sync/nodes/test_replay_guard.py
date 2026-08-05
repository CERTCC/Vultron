#!/usr/bin/env python
"""Unit tests for the Reject-replay convergence guard (SYNC-15-003)."""

from datetime import timedelta

from vultron.core.behaviors.sync.nodes.replay_guard import (
    GENESIS_REPLAY_COOLDOWN_SECONDS,
    REPLAY_COOLDOWN_SECONDS,
    claim_replay_position,
    replay_from_hash,
)
from vultron.core.models.replication_state import VultronReplicationState

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
)


class TestReplayFromHash:
    """``replay_from_hash`` maps a divergence index to a position hash."""

    def test_negative_index_is_genesis(self):
        assert replay_from_hash([_make_entry(0)], -1) == ""

    def test_returns_hash_at_matching_index(self):
        first = _make_entry(0)
        second = _make_entry(1, first.entry_hash)
        assert replay_from_hash([first, second], 1) == second.entry_hash

    def test_missing_index_falls_back_to_genesis(self):
        assert replay_from_hash([_make_entry(0)], 7) == ""

    def test_empty_entries_is_genesis(self):
        assert replay_from_hash([], 3) == ""


class TestClaimReplayPosition:
    """``claim_replay_position`` admits progress and suppresses stalls."""

    def test_first_claim_is_admitted_and_persists_state(self, datalayer):
        admitted = claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="abc",
        )

        assert admitted is True
        state_id = VultronReplicationState(
            case_id=CASE_ID, peer_id=PARTICIPANT_ACTOR_ID
        ).id_
        stored = datalayer.read(state_id)
        assert stored is not None
        assert stored.last_replayed_from_hash == "abc"

    def test_repeat_claim_at_same_hash_is_suppressed(self, datalayer):
        for _ in range(2):
            admitted = claim_replay_position(
                datalayer,
                case_id=CASE_ID,
                peer_id=PARTICIPANT_ACTOR_ID,
                from_hash="abc",
            )
        assert admitted is False

    def test_suppression_lapses_after_cooldown(self, datalayer):
        """The guard is a rate limit, not permanent suppression — otherwise a
        dropped replay would leave the peer un-synced forever.
        """
        claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="abc",
        )
        state_id = VultronReplicationState(
            case_id=CASE_ID, peer_id=PARTICIPANT_ACTOR_ID
        ).id_
        state = datalayer.read(state_id)
        state.last_replayed_at = state.last_replayed_at - timedelta(
            seconds=REPLAY_COOLDOWN_SECONDS + 1
        )
        datalayer.save(state)

        admitted = claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="abc",
        )

        assert admitted is True

    def test_claim_at_advanced_hash_is_admitted(self, datalayer):
        claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="abc",
        )
        admitted = claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="def",
        )

        assert admitted is True

    def test_genesis_claim_is_admitted_once_then_rate_limited(self, datalayer):
        """``""`` is a real position, not "unset" — it must still converge."""
        first = claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="",
        )
        second = claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="",
        )

        assert first is True
        assert second is False

    def test_genesis_uses_a_shorter_cooldown_than_mid_chain(self, datalayer):
        """A genesis peer is mid-bootstrap (SYNC-15-002) and must not be starved.

        Regression guard: a full-length cooldown at genesis suppressed the
        replay that ``AnnounceCaseOnGenesisRejectNode`` depends on, leaving the
        peer with an empty replica ("SYNC-2 replication did not complete").
        Genesis still gets *a* cooldown, so the storm stays bounded.
        """
        assert GENESIS_REPLAY_COOLDOWN_SECONDS < REPLAY_COOLDOWN_SECONDS

        claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="",
        )
        state_id = VultronReplicationState(
            case_id=CASE_ID, peer_id=PARTICIPANT_ACTOR_ID
        ).id_
        state = datalayer.read(state_id)
        # Older than the genesis cooldown, but well inside the mid-chain one.
        state.last_replayed_at = state.last_replayed_at - timedelta(
            seconds=GENESIS_REPLAY_COOLDOWN_SECONDS + 1
        )
        datalayer.save(state)

        admitted = claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="",
        )

        assert admitted is True

    def test_peers_are_tracked_independently(self, datalayer):
        other_peer = "https://example.org/actors/late-joiner"
        claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=PARTICIPANT_ACTOR_ID,
            from_hash="abc",
        )
        admitted = claim_replay_position(
            datalayer,
            case_id=CASE_ID,
            peer_id=other_peer,
            from_hash="abc",
        )

        assert admitted is True
