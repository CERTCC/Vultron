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

from unittest.mock import MagicMock

import pytest

from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
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


def _ledger_entry(index: int, case_id: str = CASE_ID) -> tuple[str, dict]:
    """A ledger entry as the whole-store dump serializes it (camelCase)."""
    entry_id = f"{case_id}/log/{index}"
    return entry_id, {
        "id": entry_id,
        "type": "CaseLedgerEntry",
        "caseId": case_id,
        "logIndex": index,
    }


def _full_case_invite() -> tuple[str, dict]:
    invite = rm_invite_to_full_case_activity(
        INVITEE,
        CASE_ID,
        LedgerPosition(log_index=3, entry_hash="ab" * 32),
        actor=MANAGER,
        id_=INVITE_ID,
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)
    record = archive_received(dl, invite)
    return record.id_, record.model_dump(
        mode="json", exclude_none=True, by_alias=True
    )


def _dump(ledger_count: int, *, invite: bool = False) -> dict[str, dict]:
    objects = dict(_ledger_entry(i) for i in range(ledger_count))
    if invite:
        objects.update([_full_case_invite()])
    return objects


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

    def test_progress_never_moves_the_deadline_past_the_ceiling(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=25.0)

        for reading in range(5):
            deadline.observe(reading)
            clock[0] += 6.0

        assert deadline.expired()

    def test_describe_names_the_last_progress_reading(self, clock):
        deadline = ProgressDeadline(stall_seconds=10.0, ceiling_seconds=25.0)
        deadline.observe(7)

        assert "7" in deadline.describe()


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
        dumps: list[dict[str, dict]] = []
        for applied in range(40):
            dumps += [_dump(applied)] * 4
        dumps.append(_dump(40, invite=True))
        client = _client(dumps)
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
        client = _client([_dump(1), _dump(2), _dump(3)])
        start = clock[0]

        with pytest.raises(AssertionError, match="reached 3"):
            find_full_case_invite_for_actor(
                client, CASE_ID, INVITEE, timeout_seconds=5.0
            )

        assert clock[0] - start < 10.0

    def test_another_cases_ledger_is_not_progress(self, clock):
        """Only the invited case's backfill delays its Invite."""
        dumps = [
            dict(_ledger_entry(i, OTHER_CASE_ID) for i in range(n))
            for n in range(1, 100)
        ]
        client = _client(dumps)
        start = clock[0]

        with pytest.raises(AssertionError):
            find_full_case_invite_for_actor(
                client, CASE_ID, INVITEE, timeout_seconds=5.0
            )

        assert clock[0] - start < 10.0

    def test_a_backfill_that_never_ends_fails_at_the_ceiling(self, clock):
        # A new entry on every 0.5 s poll, for longer than the 30 s ceiling.
        dumps = [_dump(n) for n in range(1, 100)]
        client = _client(dumps)
        start = clock[0]

        with pytest.raises(AssertionError):
            find_full_case_invite_for_actor(
                client,
                CASE_ID,
                INVITEE,
                timeout_seconds=5.0,
                progress_ceiling=30.0,
            )

        assert 30.0 <= clock[0] - start < 31.0

    def test_the_ceiling_defaults_to_the_backfill_ceiling(self):
        import inspect

        params = inspect.signature(find_full_case_invite_for_actor).parameters
        assert params["progress_ceiling"].default == BACKFILL_PROGRESS_CEILING


class TestContiguousCoverageFollowsTheBackfill:
    """A late joiner's coverage wait follows its backfill the same way."""

    @staticmethod
    def _ledger(count: int) -> dict[str, dict]:
        # The CaseLedgerEntrys/ collection is served snake_case.
        return {
            f"{CASE_ID}/log/{i}": {"case_id": CASE_ID, "log_index": i}
            for i in range(count)
        }

    @pytest.mark.spec("SYNC-10-004")
    def test_waits_past_the_stall_budget_while_entries_keep_arriving(
        self, clock
    ):
        dumps: list[dict[str, dict]] = []
        for applied in range(30):
            dumps += [self._ledger(applied)] * 4
        dumps.append(self._ledger(30))
        client = _client(dumps)
        start = clock[0]

        wait_for_contiguous_ledger_coverage(
            client, CASE_ID, expected_tail_index=29, timeout_seconds=10.0
        )

        assert clock[0] - start > 10.0

    def test_fails_once_entries_stop_arriving(self, clock):
        client = _client([self._ledger(3)])
        start = clock[0]

        with pytest.raises(AssertionError, match="reached 3"):
            wait_for_contiguous_ledger_coverage(
                client, CASE_ID, expected_tail_index=29, timeout_seconds=10.0
            )

        assert clock[0] - start < 11.0
