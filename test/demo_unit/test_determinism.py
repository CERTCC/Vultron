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

"""Tests for the seeded ids and stepping clock of a recording run (#3901)."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

import vultron.adapters.utils as adapter_utils
from vultron.core.models import _helpers
from vultron.core.models._helpers import now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.demo.determinism import (
    RECORDING_CLOCK_STEP,
    RECORDING_EPOCH,
    SeededUuid4,
    SteppingClock,
    deterministic_run,
)

_START = datetime(2026, 3, 1, tzinfo=UTC)


class TestSeededUuid4:
    def test_one_seed_gives_one_sequence(self):
        first, second = SeededUuid4("rv"), SeededUuid4("rv")
        assert [first() for _ in range(5)] == [second() for _ in range(5)]

    def test_different_seeds_give_different_sequences(self):
        assert SeededUuid4("rv")() != SeededUuid4("rcv")()

    def test_ids_are_version_4_uuids(self):
        generated = SeededUuid4("rv")()
        assert generated.version == 4
        assert generated.variant == uuid.RFC_4122

    def test_concurrent_draws_never_repeat(self):
        ids = SeededUuid4("rv")
        drawn: list[uuid.UUID] = []
        lock = threading.Lock()

        def draw() -> None:
            for _ in range(200):
                value = ids()
                with lock:
                    drawn.append(value)

        threads = [threading.Thread(target=draw) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(set(drawn)) == 800


class TestSteppingClock:
    def test_each_read_moves_one_step(self):
        clock = SteppingClock(_START, step=timedelta(seconds=2))
        assert [clock.now(), clock.now()] == [
            _START + timedelta(seconds=2),
            _START + timedelta(seconds=4),
        ]

    def test_a_zero_step_freezes_the_clock(self):
        clock = SteppingClock(_START, step=timedelta(0))
        assert clock.now() == clock.now() == _START

    def test_a_naive_start_is_refused(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            SteppingClock(datetime(2026, 3, 1))  # noqa: DTZ001


class TestDeterministicRun:
    def test_now_utc_reads_the_recording_clock(self):
        # The first read moves the clock one step, less than a second, and
        # `now_utc()` keeps whole seconds.
        assert timedelta(seconds=1) > RECORDING_CLOCK_STEP
        with deterministic_run("rv"):
            assert now_utc() == RECORDING_EPOCH

    def test_the_clock_advances_across_reads(self):
        with deterministic_run("rv", start=_START, step=timedelta(seconds=1)):
            assert [now_utc(), now_utc()] == [
                _START + timedelta(seconds=1),
                _START + timedelta(seconds=2),
            ]

    def test_a_captured_default_factory_reads_the_recording_clock(self):
        # `published` defaults through a `now_utc` reference the field captured
        # at class creation, which only the `_helpers.datetime` seam reaches.
        with deterministic_run("rv", start=_START, step=timedelta(seconds=1)):
            entry = CaseLedgerEntry.model_validate(
                {
                    "caseId": "urn:uuid:case",
                    "logIndex": 0,
                    "logObjectId": "urn:uuid:obj",
                    "semanticType": "create_case",
                    "payloadSnapshot": {
                        "id": "urn:uuid:obj",
                        "type": "Create",
                    },
                    "prevLogHash": "0" * 64,
                    "entryHash": "1" * 64,
                }
            )
        assert entry.published is not None
        assert entry.published.year == _START.year
        assert entry.published.month == _START.month

    def test_module_and_from_import_bindings_are_both_seeded(self):
        expected = SeededUuid4("rv")
        with deterministic_run("rv"):
            assert uuid.uuid4() == expected()
            # `vultron.adapters.utils` binds `uuid4` with `from uuid import`.
            assert adapter_utils.uuid4() == expected()

    def test_everything_is_restored_on_exit(self):
        real_uuid4 = uuid.uuid4
        real_datetime = _helpers.datetime
        with deterministic_run("rv"):
            pass
        assert uuid.uuid4 is real_uuid4
        assert adapter_utils.uuid4 is real_uuid4
        assert _helpers.datetime is real_datetime

    def test_everything_is_restored_when_the_block_raises(self):
        real_uuid4 = uuid.uuid4
        real_datetime = _helpers.datetime
        with pytest.raises(RuntimeError), deterministic_run("rv"):
            raise RuntimeError("boom")
        assert uuid.uuid4 is real_uuid4
        assert _helpers.datetime is real_datetime
