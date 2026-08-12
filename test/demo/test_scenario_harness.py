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

"""Tests for the shared scenario harness (ISSUE-2239, DEMOMA-23).

These exercise the real ``demo_step`` / ``demo_check`` context managers rather
than patching them out with ``nullcontext`` — patching them out is what let the
gap in ADR-0058's gating primitive go unnoticed, and it would defeat the point
here, since the harness's whole job is to control what happens when a phase
raises.
"""

import json
from unittest.mock import MagicMock

import pytest

from vultron.demo.helpers.harness import scenario_harness
from vultron.demo.helpers.ledger_dump import DUMP_MANIFEST_FILENAME
from vultron.demo.utils import demo_check, reset_demo_failures
from vultron.errors import DemoFailureError


@pytest.fixture(autouse=True)
def _devlogs(tmp_path, monkeypatch):
    """Point the dump at a temporary devlogs root and isolate failure state."""
    monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
    reset_demo_failures()
    yield tmp_path
    reset_demo_failures()


def _manifest(devlogs, demo_name="unit"):
    return json.loads(
        (devlogs / demo_name / DUMP_MANIFEST_FILENAME).read_text(
            encoding="utf-8"
        )
    )


class TestDumpAlwaysRuns:
    def test_dump_runs_on_the_happy_path(self, _devlogs) -> None:
        dump = MagicMock()
        with scenario_harness("unit") as harness:
            harness.dump_with(dump)
        dump.assert_called_once_with()

    def test_dump_runs_when_the_body_raises(self, _devlogs) -> None:
        dump = MagicMock()
        with pytest.raises(RuntimeError, match="phase blew up"):
            with scenario_harness("unit") as harness:
                harness.dump_with(dump)
                raise RuntimeError("phase blew up")
        dump.assert_called_once_with()

    def test_manifest_written_when_no_dump_was_registered(
        self, _devlogs
    ) -> None:
        with pytest.raises(RuntimeError):
            with scenario_harness("unit"):
                raise RuntimeError("died before the case existed")

        payload = _manifest(_devlogs)
        assert payload["demoName"] == "unit"
        assert payload["ledgerFileCount"] == 0
        assert payload["actors"] == []
        assert "before a case existed" in payload["reason"]

    def test_no_crash_manifest_when_the_dump_succeeds(self, _devlogs) -> None:
        """A dump that ran is never retroactively reported as having crashed.

        The real dump writes its own manifest, so the harness's backstop must
        fire only on the failing path — otherwise every run whose dump wrote no
        manifest (a stubbed dump, in practice) gets stamped with the
        "dump crashed" reason it never earned.
        """
        with scenario_harness("unit") as harness:
            harness.dump_with(MagicMock())

        assert not (_devlogs / "unit" / DUMP_MANIFEST_FILENAME).exists()

    def test_manifest_written_when_the_dump_itself_crashes(
        self, _devlogs
    ) -> None:
        """A dump that dies before recording anything still leaves an artifact."""
        with pytest.raises(RuntimeError, match="original cause"):
            with scenario_harness("unit") as harness:
                harness.dump_with(MagicMock(side_effect=OSError("no disk")))
                raise RuntimeError("original cause")

        payload = _manifest(_devlogs)
        assert payload["ledgerFileCount"] == 0
        assert payload["reason"]


class TestExceptionPropagation:
    def test_body_exception_is_not_masked_by_a_dump_failure(
        self, _devlogs
    ) -> None:
        with pytest.raises(RuntimeError, match="original cause") as exc_info:
            with scenario_harness("unit") as harness:
                harness.dump_with(MagicMock(side_effect=OSError("no disk")))
                raise RuntimeError("original cause")

        assert not isinstance(exc_info.value, DemoFailureError)

    def test_body_exception_carries_accumulated_failures_as_notes(
        self, _devlogs
    ) -> None:
        """Soft failures are still reported, without replacing the real cause."""
        with pytest.raises(RuntimeError, match="original cause") as exc_info:
            with scenario_harness("unit") as harness:
                harness.dump_with(MagicMock())
                with demo_check("a soft precondition"):
                    raise AssertionError("precondition not met")
                raise RuntimeError("original cause")

        notes = getattr(exc_info.value, "__notes__", [])
        assert any("a soft precondition" in note for note in notes)

    def test_accumulated_failures_raise_when_the_body_succeeds(
        self, _devlogs
    ) -> None:
        with pytest.raises(DemoFailureError) as exc_info:
            with scenario_harness("unit") as harness:
                harness.dump_with(MagicMock())
                with demo_check("a soft precondition"):
                    raise AssertionError("precondition not met")

        assert any(
            "a soft precondition" in failure
            for failure in exc_info.value.failures
        )

    def test_dump_failure_alone_fails_the_scenario(self, _devlogs) -> None:
        """A successful run whose dump failed must not report success."""
        with pytest.raises(DemoFailureError) as exc_info:
            with scenario_harness("unit") as harness:
                harness.dump_with(MagicMock(side_effect=OSError("no disk")))

        assert any(
            "Dumping case ledgers" in failure
            for failure in exc_info.value.failures
        )


class TestFailureAccumulatorReset:
    def test_harness_clears_failures_from_a_previous_run(
        self, _devlogs
    ) -> None:
        with demo_check("stale failure from an earlier run"):
            raise AssertionError("stale")

        with scenario_harness("unit") as harness:
            harness.dump_with(MagicMock())
