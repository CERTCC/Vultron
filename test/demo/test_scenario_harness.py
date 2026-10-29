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
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

import vultron.demo.helpers.harness as harness_module
from vultron.demo.helpers.harness import (
    StepMark,
    follow_ledger,
    reach_step,
    scenario_harness,
    step_reporter,
)
from vultron.demo.helpers.ledger_dump import (
    DUMP_MANIFEST_FILENAME,
    STEP_MARKS_FILENAME,
)
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.utils import demo_check, reset_demo_failures
from vultron.errors import DemoFailureError, DemoScenarioStepError


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


class TestUnwritableDevlogsRoot:
    """The dump root is not always writable, and that must not lose the cause.

    This is the shape that turned the ``Tests (pytest)`` job red: the default
    devlogs root pointed at a container path, so on a CI runner every write
    raised. A dump that cannot write anywhere is still only ever a *reported*
    failure — never a substitute for the scenario's own exception
    (DEMOCI-10-004, DEMOMA-23-004).
    """

    @pytest.fixture
    def unwritable(self, tmp_path, monkeypatch):
        """Point DEVLOGS_DIR under a regular file, so every mkdir raises."""
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("", encoding="utf-8")
        monkeypatch.setenv("DEVLOGS_DIR", str(blocker / "devlogs"))
        return blocker

    def test_manifest_failure_does_not_mask_the_body_exception(
        self, unwritable
    ) -> None:
        """The no-dump-registered path writes its manifest bare — guard it."""
        with pytest.raises(RuntimeError, match="original cause"):
            with scenario_harness("unit"):
                raise RuntimeError("original cause")

    def test_manifest_failure_does_not_mask_a_registered_dump_failure(
        self, unwritable
    ) -> None:
        with pytest.raises(RuntimeError, match="original cause"):
            with scenario_harness("unit") as harness:
                harness.dump_with(MagicMock(side_effect=OSError("no disk")))
                raise RuntimeError("original cause")

    def test_backstop_failure_does_not_replace_the_dump_error(
        self, unwritable
    ) -> None:
        """The recorded failure is the dump's, not the backstop manifest's."""
        with pytest.raises(DemoFailureError) as exc_info:
            with scenario_harness("unit") as harness:
                harness.dump_with(MagicMock(side_effect=OSError("no disk")))

        assert any(
            "no disk" in failure for failure in exc_info.value.failures
        ), exc_info.value.failures

    def test_unwritable_root_is_reported_not_raised(self, unwritable) -> None:
        """A clean body with an unwritable root fails loudly, via the accumulator."""
        with pytest.raises(DemoFailureError) as exc_info:
            with scenario_harness("unit"):
                pass

        assert exc_info.value.failures


class TestFailureAccumulatorReset:
    def test_harness_clears_failures_from_a_previous_run(
        self, _devlogs
    ) -> None:
        with demo_check("stale failure from an earlier run"):
            raise AssertionError("stale")

        with scenario_harness("unit") as harness:
            harness.dump_with(MagicMock())


class TestStepMarks:
    """A scenario reports each declared step; the harness marks the ledger tail.

    The marks tell the shared-prefix check where each branch point falls in
    the ledger (DEMOCI-11-017).  ``rv``'s path is the root, then
    ``vendor-after-answer``.
    """

    @pytest.fixture(autouse=True)
    def _registered(self):
        # The harness reads the declared path from the registry.
        discover_scenarios()

    @pytest.fixture
    def tails(self, monkeypatch):
        """The canonical ledger's length on each read, in order."""
        reads: Iterator[int] = iter([7, 9])
        calls: list[tuple[object, str]] = []

        def length(client: object, case_id: str) -> int:
            calls.append((client, case_id))
            return next(reads)

        monkeypatch.setattr(harness_module, "case_ledger_length", length)
        return calls

    @staticmethod
    def _marks(devlogs, demo_name="rv"):
        return json.loads(
            (devlogs / demo_name / STEP_MARKS_FILENAME).read_text(
                encoding="utf-8"
            )
        )["steps"]

    def test_each_step_marks_the_ledger_tail_there(
        self, _devlogs, tails
    ) -> None:
        client = MagicMock()
        with scenario_harness("rv") as harness:
            harness.reach_step("reporter-whom-to-tell", "vendor")
            harness.follow_ledger(client, "urn:case")
            harness.reach_step("vendor-after-answer", "report-fix-ready")
        assert harness.marks == [
            StepMark("reporter-whom-to-tell", "vendor", 0),
            StepMark("vendor-after-answer", "report-fix-ready", 7),
        ]
        assert tails == [(client, "urn:case")]
        assert self._marks(_devlogs) == [
            {
                "branchPoint": "reporter-whom-to-tell",
                "choice": "vendor",
                "ledgerTail": 0,
            },
            {
                "branchPoint": "vendor-after-answer",
                "choice": "report-fix-ready",
                "ledgerTail": 7,
            },
        ]

    def test_the_marks_are_written_when_the_body_raises(
        self, _devlogs
    ) -> None:
        with pytest.raises(RuntimeError, match="later phase"):
            with scenario_harness("rv") as harness:
                harness.reach_step("reporter-whom-to-tell", "vendor")
                raise RuntimeError("later phase")
        assert [step["branchPoint"] for step in self._marks(_devlogs)] == [
            "reporter-whom-to-tell"
        ]

    @pytest.mark.parametrize(
        "step",
        [
            ("vendor-after-answer", "report-fix-ready"),
            ("reporter-whom-to-tell", "coordinator"),
        ],
    )
    def test_a_step_that_is_not_the_next_declared_one_is_refused(
        self, _devlogs, step
    ) -> None:
        with pytest.raises(DemoScenarioStepError, match="declared path"):
            with scenario_harness("rv") as harness:
                harness.reach_step(*step)

    def test_a_step_past_the_end_of_the_path_is_refused(
        self, _devlogs, tails
    ) -> None:
        with pytest.raises(DemoScenarioStepError, match="already reached"):
            with scenario_harness("rv") as harness:
                harness.reach_step("reporter-whom-to-tell", "vendor")
                harness.follow_ledger(MagicMock(), "urn:case")
                harness.reach_step("vendor-after-answer", "report-fix-ready")
                harness.reach_step("vendor-after-answer", "report-fix-ready")

    def test_a_later_step_needs_a_followed_ledger(self, _devlogs) -> None:
        with pytest.raises(DemoScenarioStepError, match="follow_ledger"):
            with scenario_harness("rv") as harness:
                harness.reach_step("reporter-whom-to-tell", "vendor")
                harness.reach_step("vendor-after-answer", "report-fix-ready")

    def test_an_unregistered_scenario_has_no_path(self, _devlogs) -> None:
        with pytest.raises(DemoScenarioStepError, match="no registered"):
            with scenario_harness("unit") as harness:
                harness.reach_step("reporter-whom-to-tell", "vendor")

    def test_module_functions_report_to_the_running_harness(
        self, _devlogs, tails
    ) -> None:
        with scenario_harness("rv") as harness:
            step_reporter("reporter-whom-to-tell", "vendor")()
            follow_ledger(MagicMock(), "urn:case")
            reach_step("vendor-after-answer", "report-fix-ready")
        assert [mark.ledger_tail for mark in harness.marks] == [0, 7]

    def test_module_functions_do_nothing_outside_a_harness(
        self, tails
    ) -> None:
        follow_ledger(MagicMock(), "urn:case")
        reach_step("vendor-after-answer", "report-fix-ready")
        step_reporter("reporter-whom-to-tell", "vendor")()
        assert tails == []

    def test_the_running_harness_is_cleared_on_exit(self, _devlogs) -> None:
        with pytest.raises(RuntimeError):
            with scenario_harness("rv"):
                raise RuntimeError("boom")
        # A step after the run is not recorded anywhere, nor refused.
        reach_step("vendor-after-answer", "report-fix-ready")
