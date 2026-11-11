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

import subprocess
import sys
import textwrap
import threading
import uuid
from datetime import UTC, datetime, timedelta

import py_trees
import pytest

from test.support.child_env import REPO_ROOT, child_env
from test.support.objects import make
from vultron.core.models._helpers import (
    URN_UUID_PREFIX,
    clock as helpers_clock,
    install_id_source,
    new_object_id,
    now_utc,
)
from vultron.core.models.base import CoreRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.demo.determinism import (
    RECORDING_CLOCK_STEP,
    RECORDING_EPOCH,
    SeededUuid4,
    SteppingClock,
    deterministic_run,
)
from vultron.errors import VultronIdSourceInstalledError

_START = datetime(2026, 3, 1, tzinfo=UTC)


def _seeded_ids(seed: str, count: int) -> list[str]:
    """The first *count* object ids a run seeded with *seed* mints."""
    expected = SeededUuid4(seed)
    return [f"{URN_UUID_PREFIX}{expected()}" for _ in range(count)]


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
        # The first read moves the clock one step, and `now_utc()` keeps
        # microseconds, so the step shows (CS-13-007).
        with deterministic_run("rv"):
            assert now_utc() == RECORDING_EPOCH + RECORDING_CLOCK_STEP

    def test_the_clock_advances_across_reads(self):
        with deterministic_run("rv", start=_START, step=timedelta(seconds=1)):
            assert [now_utc(), now_utc()] == [
                _START + timedelta(seconds=1),
                _START + timedelta(seconds=2),
            ]

    def test_a_captured_default_factory_reads_the_recording_clock(self):
        # `published` defaults through a `now_utc` reference the field captured
        # at class creation, which only the `_helpers.clock.datetime` seam
        # reaches.  An object time still has the default (#5758 removes it
        # last); a record's time no longer does.
        with deterministic_run("rv", start=_START, step=timedelta(seconds=1)):
            report = make(VulnerabilityReport, name="r", content="c")
        assert report.published is not None
        assert report.published.year == _START.year
        assert report.published.month == _START.month

    @pytest.mark.spec("OID-01-004")
    def test_the_shared_minter_repeats_its_ids(self):
        with deterministic_run("rv"):
            minted = [new_object_id(), CoreRecord().id_]
        assert minted == _seeded_ids("rv", 2)

    @pytest.mark.spec("OID-01-012")
    def test_no_uuid4_binding_is_patched(self):
        # Covers `uuid.uuid4` and every `from uuid import uuid4` binding a
        # loaded module holds, such as the FastAPI app's.
        import vultron.adapters.driving.fastapi.app  # noqa: F401

        real_uuid4 = uuid.uuid4
        with deterministic_run("rv"):
            assert uuid.uuid4 is real_uuid4
            replaced = sorted(
                name
                for name, module in list(sys.modules.items())
                if module is not None
                and "uuid4" in vars(module)
                and vars(module)["uuid4"] is not real_uuid4
            )
            drawn = uuid.uuid4()
        assert replaced == []
        assert drawn != uuid.UUID(
            _seeded_ids("rv", 1)[0].removeprefix(URN_UUID_PREFIX)
        )

    @pytest.mark.spec("OID-01-011")
    def test_building_py_trees_behaviours_draws_no_seeded_id(self):
        # py_trees draws `uuid.uuid4()` for each behaviour and blackboard
        # client; under the scoped install those draws stay random, so a
        # tree's shape moves no object id (ADR-0185).
        with deterministic_run("rv"):
            tree = py_trees.composites.Sequence(
                name="root",
                memory=False,
                children=[
                    py_trees.behaviours.Success(name=f"leaf-{n}")
                    for n in range(5)
                ],
            )
            client = py_trees.blackboard.Client(name="recording-test")
            minted = new_object_id()
        assert minted == _seeded_ids("rv", 1)[0]
        seeded = {
            uuid.UUID(i.removeprefix(URN_UUID_PREFIX))
            for i in _seeded_ids("rv", 10)
        }
        assert tree.id not in seeded
        assert not {child.id for child in tree.children} & seeded
        assert client.id() not in seeded

    def test_everything_is_restored_on_exit(self):
        real_datetime = helpers_clock.datetime
        with deterministic_run("rv"):
            pass
        assert helpers_clock.datetime is real_datetime
        # The seeded source is uninstalled: the minter no longer draws from
        # it, and another install is admitted.
        assert new_object_id() != _seeded_ids("rv", 1)[0]
        with install_id_source(SeededUuid4("after")):
            assert new_object_id() == _seeded_ids("after", 1)[0]

    def test_everything_is_restored_when_the_block_raises(self):
        real_datetime = helpers_clock.datetime
        with pytest.raises(RuntimeError), deterministic_run("rv"):
            raise RuntimeError("boom")
        assert helpers_clock.datetime is real_datetime
        assert new_object_id() != _seeded_ids("rv", 1)[0]
        with install_id_source(SeededUuid4("after")):
            assert new_object_id() == _seeded_ids("after", 1)[0]

    def test_a_nested_run_is_refused(self):
        real_datetime = helpers_clock.datetime
        with deterministic_run("rv"):
            with (
                pytest.raises(VultronIdSourceInstalledError),
                deterministic_run("rcv"),
            ):
                pass
            # The refused run leaves the outer one's ids in place.
            assert new_object_id() == _seeded_ids("rv", 1)[0]
        assert helpers_clock.datetime is real_datetime


def _run_fresh(code: str) -> subprocess.CompletedProcess[str]:
    """Run *code* in a fresh interpreter, so no earlier test imported anything.

    Under the unit tier's 30-second test timeout, so a hung child fails here.
    """
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        cwd=REPO_ROOT,
        env=child_env(),
    )


class TestDocsExamplesLoadBeforeTheInstall:
    """No first import of the docs examples runs inside a recording's install.

    The examples build shared objects at first import inside their own
    id-source scope (#6117), which may not nest inside another install, and a
    first import inside the block would draw from the seeded stream.
    """

    @pytest.mark.spec("OID-01-011")
    def test_the_harness_loads_the_examples_before_its_ids(self):
        result = _run_fresh(
            """
            import sys

            from vultron.core.models._helpers import new_object_id
            from vultron.demo.determinism import SeededUuid4, deterministic_run

            assert "vultron.wire.as2.vocab.examples._base" in sys.modules
            assert "vultron.wire.as2.vocab.examples.vocab_examples" in sys.modules
            with deterministic_run("rv"):
                import vultron.wire.as2.vocab.examples.vocab_examples  # noqa
                minted = new_object_id()
            assert minted == f"urn:uuid:{SeededUuid4('rv')()}", minted
            """
        )
        assert result.returncode == 0, result.stderr
