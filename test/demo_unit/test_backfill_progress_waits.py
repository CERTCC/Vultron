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

"""Waits that follow a late joiner's backfill wait on its progress (#4424).

The CASE_MANAGER queues the full-case Invite after the last replayed ledger
entry (CM-11-010), and the joiner's inbox applies that replay one entry at a
time.  How long the Invite takes to land is therefore the backfill's length
times the per-entry apply time under load — 26 s on one CI run and 75 s on
another for the same scenario.  A fixed budget can be outrun by the backfill
it is waiting on; these waits instead fail only when the joiner's ledger copy
stops advancing (EDF-06, ADR-0058), up to a ceiling.

The clock is faked: ``time.sleep`` advances ``time.monotonic``, so each test
is deterministic and runs instantly.
"""

from typing import Any, NamedTuple
from unittest.mock import MagicMock

import pytest

from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.routers.datalayer import (
    get_datalayer_contents,
    get_objects,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.demo.helpers import polling
from vultron.demo.helpers.invite_chain import FULL_CASE_REPLY_TIMEOUT
from vultron.demo.helpers.polling import (
    BACKFILL_PROGRESS_CEILING,
    ProgressDeadline,
    find_full_case_invite_for_actor,
    wait_for_contiguous_ledger_coverage,
)
from vultron.wire.as2.factories import rm_invite_to_full_case_activity

CASE_ID = "http://example.com/cases/case-1"
OTHER_CASE_ID = "http://example.com/cases/case-2"
INVITEE = "http://example.com/actors/vendor2"
MANAGER = "http://example.com/actors/case-actor"
INVITE_ID = "http://example.com/activities/full-invite-1"


@pytest.fixture
def clock(monkeypatch) -> list[float]:
    """A fake monotonic clock that ``time.sleep`` advances."""
    now = [1000.0]

    def _sleep(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(polling.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(polling.time, "sleep", _sleep)
    return now


def _entry(index: int, case_id: str = CASE_ID) -> CaseLedgerEntry:
    return CaseLedgerEntry(
        case_id=case_id,
        log_index=index,
        log_object_id=f"http://example.com/activities/a{index}",
        semantic_type="test",
    )


def _full_case_invite():
    return rm_invite_to_full_case_activity(
        INVITEE,
        CASE_ID,
        LedgerPosition(log_index=3, entry_hash="ab" * 32),
        actor=MANAGER,
        id_=INVITE_ID,
    )


class _Store:
    """A real invitee store, read through the real DataLayer routes.

    The fakes are not hand-written dicts: the type-filtered dump and the
    ``CaseLedgerEntrys/`` collection are what the routes serve for these saved
    objects, so a change to either serialization reaches these tests.
    """

    def __init__(self) -> None:
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)

    def add_entries(self, start: int, stop: int, case_id: str = CASE_ID):
        for index in range(start, stop):
            self.dl.save(_entry(index, case_id))
        return self

    def add_invite(self):
        archive_received(self.dl, _full_case_invite())
        return self

    def invite_dump(self) -> dict[str, dict]:
        """The dump the full-case Invite poll reads: Invite types only."""
        return get_datalayer_contents(
            datalayer=self.dl, types=list(polling._RECEIVED_INVITE_TYPES)
        )

    def invite_poll(self) -> "_PollReads":
        """Both reads one Invite poll makes, as of now."""
        return _PollReads(self.invite_dump(), self.ledger_collection())

    def ledger_collection(self) -> dict[str, dict]:
        # The route is unannotated; it serves DataLayer.by_type's mapping.
        collection: dict[str, dict] = get_objects(
            "CaseLedgerEntry", datalayer=self.dl
        )
        return collection


class _PollReads(NamedTuple):
    """What the two reads of one full-case Invite poll return."""

    invites: dict[str, dict]
    ledger: dict[str, dict]


def _backfill(
    count: int, *, reads_per_entry: int, read, invite: bool = False
) -> list[Any]:
    """Snapshots of a store applying *count* entries, one at a time.

    Each stage is read *reads_per_entry* times (one read per poll), so with
    the 0.5 s poll interval an entry lands every ``reads_per_entry / 2`` s.
    """
    store = _Store()
    snapshots: list[Any] = []
    for applied in range(count):
        snapshots += [read(store)] * reads_per_entry
        store.add_entries(applied, applied + 1)
    if invite:
        store.add_invite()
    snapshots.append(read(store))
    return snapshots


def _client(dumps: list[dict[str, dict]]) -> MagicMock:
    """A client whose successive reads return *dumps*, then the last forever."""
    client = MagicMock()
    client.base_url = "http://vendor2:7999"
    client.dl_path.side_effect = lambda path="": f"/datalayer/{path}"
    reads = iter(dumps)
    last: list[dict[str, dict]] = [dumps[-1]]

    def _get(_path: str) -> dict[str, dict]:
        try:
            last[0] = next(reads)
        except StopIteration:
            pass
        return last[0]

    client.get.side_effect = _get
    return client


def _invite_poll_client(polls: list[_PollReads]) -> MagicMock:
    """A client whose successive Invite polls see *polls*, then the last.

    A poll is one read of the Invite types and, when that finds nothing, one
    of the ledger collection; both come from the same snapshot, and the next
    Invite read moves on to the next one.
    """
    client = MagicMock()
    client.base_url = "http://vendor2:7999"
    client.dl_path.side_effect = lambda path="": f"/datalayer/{path}"
    remaining = iter(polls)
    current: list[_PollReads] = [polls[0]]

    def _get(path: str, **_kwargs: Any) -> dict[str, dict]:
        if path.endswith("CaseLedgerEntrys/"):
            return current[0].ledger
        current[0] = next(remaining, current[0])
        return current[0].invites

    client.get.side_effect = _get
    return client


class TestProgressDeadline:
    def test_expires_after_the_stall_budget_without_progress(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=100.0)

        clock[0] += 9.9
        assert not deadline.expired()
        clock[0] += 0.1
        assert deadline.expired()

    def test_progress_moves_the_deadline(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=100.0)
        deadline.observe(0)

        clock[0] += 8.0
        deadline.observe(1)
        clock[0] += 8.0

        assert not deadline.expired()

    def test_a_repeated_or_lower_reading_is_not_progress(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=100.0)
        deadline.observe(5)

        clock[0] += 8.0
        deadline.observe(5)
        deadline.observe(4)
        clock[0] += 2.0

        assert deadline.expired()

    def test_a_late_first_reading_only_sets_the_baseline(self, clock):
        """Progress made before the first reading earns no extra time."""
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=100.0)

        clock[0] += 8.0
        deadline.observe(50)
        clock[0] += 2.0

        assert deadline.expired()

    def test_progress_never_moves_the_deadline_past_the_ceiling(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=25.0)

        for reading in range(5):
            deadline.observe(reading)
            clock[0] += 6.0

        assert deadline.expired()

    def test_a_ceiling_below_the_stall_budget_is_raised_to_it(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=4.0)

        clock[0] += 9.9
        assert not deadline.expired()
        clock[0] += 0.1
        assert deadline.expired()

    def test_describe_says_the_measure_stalled(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=25.0)
        deadline.observe(7)

        message = deadline.describe()

        assert "reached 7" in message
        assert "did not advance for 10 s" in message
        assert "ceiling" not in message

    def test_describe_says_the_wait_hit_the_ceiling(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=25.0)
        for reading in range(5):
            deadline.observe(reading)
            clock[0] += 6.0

        message = deadline.describe()

        assert "reached 4" in message
        assert "still advancing" in message
        assert "25 s ceiling" in message

    def test_describe_without_a_reading(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=25.0)

        assert deadline.describe() == "no progress reading was taken"


class TestPollUntilKeepsItsFixedDeadline:
    """Without a progress measure, ``_poll_until`` behaves as before."""

    def test_a_zero_budget_still_tries_the_condition_once(self, clock):
        calls: list[float] = []

        polling._poll_until(lambda: calls.append(clock[0]) or True, 0.0)

        assert len(calls) == 1

    def test_fails_after_the_fixed_budget(self, clock):
        start = clock[0]

        with pytest.raises(AssertionError, match=r"^never$"):
            polling._poll_until(lambda: False, 5.0, error_msg="never")

        assert 5.0 <= clock[0] - start < 5.5


class TestFullCaseInviteWaitFollowsTheBackfill:
    """The Invite lands behind the backfill, so its wait follows the backfill."""

    @pytest.mark.spec("CM-11-010")
    @pytest.mark.spec("EDF-06-005")
    def test_waits_past_the_stall_budget_while_the_backfill_advances(
        self, clock
    ):
        """A backfill longer than the budget no longer outruns the gate (#4424)."""
        # One entry applied every 2 s for 40 entries: 80 s, four times the
        # 20 s budget that failed in CI, with the Invite behind the last one.
        polls = _backfill(
            40, reads_per_entry=4, read=_Store.invite_poll, invite=True
        )
        client = _invite_poll_client(polls)
        start = clock[0]

        found = find_full_case_invite_for_actor(
            client,
            CASE_ID,
            INVITEE,
            timeout_seconds=FULL_CASE_REPLY_TIMEOUT,
        )

        assert found == INVITE_ID
        assert clock[0] - start > FULL_CASE_REPLY_TIMEOUT

    def test_fails_once_the_backfill_stops_advancing(self, clock):
        client = _invite_poll_client(
            _backfill(3, reads_per_entry=1, read=_Store.invite_poll)
        )
        start = clock[0]

        with pytest.raises(AssertionError, match="reached 3, then did not"):
            find_full_case_invite_for_actor(
                client, CASE_ID, INVITEE, timeout_seconds=5.0
            )

        assert clock[0] - start < 10.0

    def test_another_cases_ledger_is_not_progress(self, clock):
        """Only the invited case's backfill delays its Invite."""
        store = _Store()
        polls = []
        for index in range(100):
            store.add_entries(index, index + 1, case_id=OTHER_CASE_ID)
            polls.append(store.invite_poll())
        client = _invite_poll_client(polls)
        start = clock[0]

        with pytest.raises(AssertionError):
            find_full_case_invite_for_actor(
                client, CASE_ID, INVITEE, timeout_seconds=5.0
            )

        assert clock[0] - start < 10.0

    def test_a_backfill_that_never_ends_fails_at_the_ceiling(self, clock):
        # A new entry on every 0.5 s poll, for longer than the 30 s ceiling.
        client = _invite_poll_client(
            _backfill(100, reads_per_entry=1, read=_Store.invite_poll)
        )
        start = clock[0]

        with pytest.raises(AssertionError, match="30 s ceiling"):
            find_full_case_invite_for_actor(
                client,
                CASE_ID,
                INVITEE,
                timeout_seconds=5.0,
                progress_ceiling=30.0,
            )

        assert 30.0 <= clock[0] - start < 31.0

    def test_a_progress_reading_that_raises_does_not_hide_the_invite(
        self, clock, monkeypatch
    ):
        def _broken(_client: object, _case_id: str) -> int:
            raise RuntimeError("progress reading failed")

        monkeypatch.setattr(polling, "_count_case_ledger_entries", _broken)
        client = _invite_poll_client(
            [_Store().add_entries(0, 3).add_invite().invite_poll()]
        )

        assert (
            find_full_case_invite_for_actor(
                client, CASE_ID, INVITEE, timeout_seconds=5.0
            )
            == INVITE_ID
        )

    def test_the_ceiling_defaults_to_the_backfill_ceiling(self):
        import inspect

        params = inspect.signature(find_full_case_invite_for_actor).parameters
        assert params["progress_ceiling"].default == BACKFILL_PROGRESS_CEILING


class TestContiguousCoverageFollowsTheBackfill:
    """A late joiner's coverage wait follows its backfill the same way."""

    @pytest.mark.spec("SYNC-10-004")
    def test_waits_past_the_stall_budget_while_entries_keep_arriving(
        self, clock
    ):
        dumps = _backfill(30, reads_per_entry=4, read=_Store.ledger_collection)
        client = _client(dumps)
        start = clock[0]

        wait_for_contiguous_ledger_coverage(
            client, CASE_ID, expected_tail_index=29, timeout_seconds=10.0
        )

        assert clock[0] - start > 10.0

    def test_fails_once_entries_stop_arriving(self, clock):
        client = _client([_Store().add_entries(0, 3).ledger_collection()])
        start = clock[0]

        with pytest.raises(AssertionError, match="reached 3"):
            wait_for_contiguous_ledger_coverage(
                client, CASE_ID, expected_tail_index=29, timeout_seconds=10.0
            )

        assert clock[0] - start < 11.0
