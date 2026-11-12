#!/usr/bin/env python
"""The sync checks and recorders take the act's instant (ADR-0176, #5651).

Two kinds of test:

- **A read path reads no clock.**  Each runs while every read of the wall
  clock behind ``now_utc`` is recorded
  (:func:`~test.support.act_clock.recorded_clock_reads`), and none may be.
  A path that read the clock, directly or through a model's clock default,
  would decide against a time no act stated (ADR-0176).
- **A recorder stamps the act's instant, and a check is judged at it.**  The
  rate limits keep their windows: the same verdict for the same instant.
"""

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

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
    _make_event,
)
from test.support.act_clock import recorded_clock_reads
from test.support.act_runner import run_tree
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.nodes import (
    canonical_entry,
    invite_resend,
    sender_sequence,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    record_embargo_pause,
)
from vultron.core.behaviors.sync.nodes.genesis_reject import (
    SendGenesisRejectOnMissingCaseNode,
)
from vultron.core.behaviors.sync.nodes.replay_guard import (
    MAX_REPLAY_COOLDOWN_SECONDS,
    REPLAY_COOLDOWN_SECONDS,
    cooldown_elapsed,
    genesis_reject_answered,
    read_replication_state,
    record_replay,
    should_replay,
    update_replication_state,
)
from vultron.core.behaviors.sync.nodes.reseed import (
    RESEED_COOLDOWN_SECONDS,
    record_reseed,
    should_reseed,
)
from vultron.core.models.genesis_reject_record import GenesisRejectRecord
from vultron.core.models.invite_resend_record import InviteResendRecord
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.services.genesis_reject_limit import (
    last_genesis_reject_at,
    record_genesis_reject,
)
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronCanonicalEntryError

#: The act's instant every check and record here is judged at.
_AT = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
_INVITE = "https://example.org/activities/invite-1"
_EMBARGO = "https://example.org/embargoes/em-1"
_POSITION = LedgerPosition(log_index=0, entry_hash="a" * 64)


def _assert_reads_no_clock(path: Callable[[], object]) -> None:
    with recorded_clock_reads() as reads:
        path()
    assert reads == []


@pytest.fixture
def replayed(datalayer: SqliteDataLayer) -> SqliteDataLayer:
    """A peer replayed to from genesis and re-seeded, at :data:`_AT`."""
    record_replay(
        datalayer,
        case_id=CASE_ID,
        peer_id=PARTICIPANT_ACTOR_ID,
        from_hash="",
        through_index=3,
        at=_AT,
    )
    record_reseed(
        datalayer,
        case_id=CASE_ID,
        peer_id=PARTICIPANT_ACTOR_ID,
        position=_POSITION,
        at=_AT,
    )
    return datalayer


_KEYS = {"case_id": CASE_ID, "peer_id": PARTICIPANT_ACTOR_ID}
_LATER = _AT + timedelta(seconds=1)


@pytest.mark.spec("CS-13-002")
@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(
            lambda dl: read_replication_state(dl, **_KEYS) is not None,
            True,
            id="read_replication_state",
        ),
        pytest.param(
            lambda dl: should_replay(
                dl,
                case_id=CASE_ID,
                peer_id=PARTICIPANT_ACTOR_ID,
                from_hash="",
                at=_LATER,
            ),
            False,
            id="should_replay",
        ),
        pytest.param(
            lambda dl: genesis_reject_answered(
                dl, **_KEYS, rejected_index=1, at=_LATER
            ),
            True,
            id="genesis_reject_answered",
        ),
        pytest.param(
            lambda dl: should_reseed(dl, **_KEYS, at=_LATER),
            False,
            id="should_reseed",
        ),
    ],
)
def test_a_replication_state_check_reads_no_clock(
    replayed: SqliteDataLayer,
    path: Callable[[SqliteDataLayer], bool],
    expected: bool,
) -> None:
    """Each check reaches its cooldown (the verdict is the one inside the
    window) and reads no clock doing it."""
    verdicts: list[bool] = []

    _assert_reads_no_clock(lambda: verdicts.append(path(replayed)))

    assert verdicts == [expected]


@pytest.mark.spec("CS-13-002")
def test_a_lookup_of_a_peer_with_no_state_reads_no_clock(
    datalayer: SqliteDataLayer,
) -> None:
    """The key is derived, not read off a model built to get it."""
    _assert_reads_no_clock(lambda: read_replication_state(datalayer, **_KEYS))


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("SYNC-20-005")
def test_the_resend_check_reads_no_clock(datalayer: SqliteDataLayer) -> None:
    invite_resend._record_resend(
        datalayer, _INVITE, PARTICIPANT_ACTOR_ID, at=_AT
    )

    _assert_reads_no_clock(
        lambda: invite_resend._resend_due(
            datalayer, _INVITE, PARTICIPANT_ACTOR_ID, at=_LATER
        )
    )


def _invited(rsvp_deadline: datetime | None) -> tuple[Any, Any]:
    """A case whose open embargo invited a participant, and the participant."""
    case = SimpleNamespace(
        embargo_register_entry=lambda _id: SimpleNamespace(
            status=EmbargoRegisterStatus.PROPOSED
        )
    )
    participant = SimpleNamespace(
        held_row=lambda _id: SimpleNamespace(
            state=EmbargoConsentState.INVITED, rsvp_deadline=rsvp_deadline
        )
    )
    return case, participant


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("SYNC-20-002")
def test_an_owed_invite_check_reads_no_clock() -> None:
    case, participant = _invited(_AT)

    _assert_reads_no_clock(
        lambda: invite_resend._embargo_invite_owed(
            case, participant, _EMBARGO, at=_LATER
        )
    )


@pytest.mark.spec("SYNC-20-002")
def test_an_rsvp_deadline_is_judged_at_the_acts_instant() -> None:
    case, participant = _invited(_AT)

    def owed(at: datetime) -> bool:
        return invite_resend._embargo_invite_owed(
            case, participant, _EMBARGO, at=at
        )

    assert owed(_AT - timedelta(microseconds=1))
    assert not owed(_AT)


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("CLP-14-007")
@pytest.mark.spec("CLP-14-008")
def test_the_claimed_timestamp_check_reads_no_clock() -> None:
    def check() -> None:
        canonical_entry._validate_entry_timestamps(
            semantic_type="note_added",
            payload_snapshot={"published": _AT.isoformat()},
            case_published=None,
            prev_actor_published=None,
            future_tolerance=timedelta(minutes=5),
            staleness_window=timedelta(days=7),
            skew_tolerance=timedelta(minutes=5),
            at=_AT,
        )

    _assert_reads_no_clock(check)


@pytest.mark.spec("CLP-14-007")
@pytest.mark.spec("CLP-14-008")
@pytest.mark.parametrize(
    ("published", "refused"),
    [
        pytest.param(_AT + timedelta(minutes=5), False, id="at-the-ceiling"),
        pytest.param(
            _AT + timedelta(minutes=5, microseconds=1), True, id="ahead"
        ),
        pytest.param(_AT - timedelta(days=7), False, id="at-the-window"),
        pytest.param(
            _AT - timedelta(days=7, microseconds=1), True, id="stale"
        ),
    ],
)
def test_the_claimed_timestamp_is_judged_at_the_acts_instant(
    published: datetime, refused: bool
) -> None:
    def check() -> None:
        canonical_entry._validate_entry_timestamps(
            semantic_type="note_added",
            payload_snapshot={"published": published.isoformat()},
            case_published=None,
            prev_actor_published=None,
            future_tolerance=timedelta(minutes=5),
            staleness_window=timedelta(days=7),
            skew_tolerance=timedelta(minutes=5),
            at=_AT,
        )

    if refused:
        with pytest.raises(VultronCanonicalEntryError):
            check()
    else:
        check()


@pytest.mark.spec("SYNC-15-003")
@pytest.mark.spec("SYNC-16-004")
@pytest.mark.parametrize(
    "seconds",
    [REPLAY_COOLDOWN_SECONDS, MAX_REPLAY_COOLDOWN_SECONDS, 2.0],
)
def test_a_cooldown_keeps_its_window(seconds: float) -> None:
    window = timedelta(seconds=seconds)

    assert cooldown_elapsed(None, seconds, at=_AT)
    assert cooldown_elapsed(_AT, seconds, at=_AT + window)
    assert not cooldown_elapsed(
        _AT, seconds, at=_AT + window - timedelta(microseconds=1)
    )


def _state(datalayer: SqliteDataLayer) -> VultronReplicationState:
    state = read_replication_state(datalayer, **_KEYS)
    assert state is not None
    return state


@pytest.mark.spec("SYNC-04-002")
@pytest.mark.spec("SYNC-15-003")
@pytest.mark.spec("SYNC-16-004")
def test_the_replay_and_reseed_recorders_stamp_the_acts_instant(
    replayed: SqliteDataLayer,
) -> None:
    state = _state(replayed)

    assert state.last_replayed_at == _AT
    assert state.last_reseeded_at == _AT
    assert state.updated_at == _AT
    assert state.id_ == VultronReplicationState.build_id(
        CASE_ID, PARTICIPANT_ACTOR_ID
    )


@pytest.mark.spec("SYNC-04-002")
def test_a_new_replication_state_is_stamped_with_the_acts_instant(
    datalayer: SqliteDataLayer,
) -> None:
    """A peer with no state gets a fresh record; its clock default never
    fires, so building it reads no clock either."""

    def first_record() -> None:
        update_replication_state(
            datalayer, **_KEYS, change=lambda _state: None, at=_AT
        )

    _assert_reads_no_clock(first_record)
    assert _state(datalayer).updated_at == _AT


@pytest.mark.spec("CM-10-005")
def test_an_embargo_pause_is_stamped_with_the_acts_instant(
    datalayer: SqliteDataLayer,
) -> None:
    record_embargo_pause(datalayer, **_KEYS, from_index=2, at=_AT)

    assert _state(datalayer).updated_at == _AT


@pytest.mark.spec("SYNC-20-005")
def test_a_resend_is_stamped_with_the_acts_instant(
    datalayer: SqliteDataLayer,
) -> None:
    invite_resend._record_resend(
        datalayer, _INVITE, PARTICIPANT_ACTOR_ID, at=_AT
    )

    record = datalayer.read(
        InviteResendRecord.build_id(_INVITE, PARTICIPANT_ACTOR_ID)
    )
    assert isinstance(record, InviteResendRecord)
    assert record.last_resent_at == _AT


def _early_entry_event() -> Any:
    """An early entry's Announce, built outside any seeded run: building it
    stamps its own times."""
    return _make_event(_make_entry(1), actor_id=OWNER_ACTOR_ID)


def _run_genesis_reject(
    datalayer: SqliteDataLayer, at: datetime, event: Any = None
) -> Any:
    """Run the genesis-Reject node for an early entry, as one act at *at*."""
    sync_port = MagicMock()
    py_trees.blackboard.Blackboard.storage.clear()
    result = run_tree(
        BTBridge(datalayer=datalayer),
        tree=SendGenesisRejectOnMissingCaseNode(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event if event is not None else _early_entry_event(),
        tail_hash="",
        sync_port=sync_port,
        at=at,
    )
    assert result.status is Status.FAILURE
    assert not result.internal_error, result.feedback_message
    return sync_port


@pytest.mark.spec("SYNC-15-016")
@pytest.mark.spec("SYNC-15-017")
def test_a_genesis_reject_is_stamped_with_the_acts_instant(
    datalayer: SqliteDataLayer,
) -> None:
    sync_port = _run_genesis_reject(datalayer, _AT)

    sync_port.send_reject_log_entry.assert_called_once()
    assert sync_port.send_reject_log_entry.call_args.kwargs["asked_at"] == _AT
    assert last_genesis_reject_at(datalayer, CASE_ID) == _AT


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("SYNC-15-016")
def test_a_withheld_genesis_reject_reads_no_clock(
    datalayer: SqliteDataLayer,
) -> None:
    record_genesis_reject(datalayer, CASE_ID, _AT)
    inside = _AT + timedelta(seconds=MAX_REPLAY_COOLDOWN_SECONDS - 1)
    event = _early_entry_event()

    sync_ports: list[Any] = []
    _assert_reads_no_clock(
        lambda: sync_ports.append(
            _run_genesis_reject(datalayer, inside, event)
        )
    )

    for sync_port in sync_ports:
        sync_port.send_reject_log_entry.assert_not_called()
    stored = datalayer.read(GenesisRejectRecord.build_id(CASE_ID))
    assert isinstance(stored, GenesisRejectRecord)
    assert stored.last_sent_at == _AT


@pytest.mark.spec("SYNC-15-016")
def test_a_genesis_reject_after_the_interval_is_sent(
    datalayer: SqliteDataLayer,
) -> None:
    record_genesis_reject(datalayer, CASE_ID, _AT)
    after = _AT + timedelta(seconds=MAX_REPLAY_COOLDOWN_SECONDS)

    sync_port = _run_genesis_reject(datalayer, after)

    sync_port.send_reject_log_entry.assert_called_once()
    assert last_genesis_reject_at(datalayer, CASE_ID) == after


@pytest.mark.spec("SYNC-21-010")
@pytest.mark.spec("SYNC-21-011")
def test_a_hold_past_a_gap_is_timed_from_the_acts_instant(
    datalayer: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    held_at: list[datetime] = []

    def _hold(*args: object, **_kwargs: object) -> None:
        held_at.append(cast(datetime, args[4]))

    monkeypatch.setattr(sender_sequence, "hold_past_gap", _hold)
    classify = cast(
        sender_sequence.ClassifySequenceNumberNode,
        SimpleNamespace(
            order=MagicMock(), number=3, activity_id="urn:uuid:held"
        ),
    )

    result = run_tree(
        BTBridge(datalayer=datalayer),
        tree=sender_sequence.HoldPastGapNode(classify),
        actor_id=OWNER_ACTOR_ID,
        at=_AT,
    )

    assert result.status is Status.SUCCESS, result.feedback_message
    assert held_at == [_AT]


@pytest.mark.spec("SYNC-16-004")
def test_a_reseed_inside_its_cooldown_waits(
    replayed: SqliteDataLayer,
) -> None:
    window = timedelta(seconds=RESEED_COOLDOWN_SECONDS)

    assert not should_reseed(
        replayed, **_KEYS, at=_AT + window - timedelta(microseconds=1)
    )
    assert should_reseed(replayed, **_KEYS, at=_AT + window)
