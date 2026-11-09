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

"""The base-versus-head comparison and its command (DEMOCI-11-055, -061, -062).

``TestFixtureStoryMutations`` is the evidence that the comparison sees what a
recording cannot: two mutations that #5596 found — a ``demo_check`` moved out
of its ``demo_gate``, and a wait pointed at another cast member's container —
leave the ledger byte-identical and move only the check tree.
"""

import json
from dataclasses import replace

import pytest
from click.testing import CliRunner
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.demo.helpers.cast import CAST, VENDOR_SLOT, ContainerSlot
from vultron.demo.recordings import compare, runner
from vultron.demo.recordings.compare import (
    DIFFERENT_EXIT_CODE,
    NO_SCENARIOS_EXIT_CODE,
    compare_runs,
)
from vultron.demo.recordings.layout import Recording
from vultron.demo.recordings.traces import ScenarioRun, write_run
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.utils import DataLayerClient
from vultron.demo.utils.check_tree import (
    CheckKind,
    CheckNode,
    CheckOutcome,
    recording_checks,
)
from vultron.demo.utils.failures import (
    demo_check,
    demo_gate,
    demo_step,
    reset_demo_failures,
)

CASE_ID = "urn:uuid:ed045a61-5ca4-4c92-b278-3dff7bb2199f"

#: A character actor, so the two mutations differ in the cast member read and
#: in nothing else.
OTHER_SLOT = CAST[3]


def _ledger() -> str:
    """Two ledger entries, the same in every run here.

    Neither mutation performs a protocol act, so the ledger is literally
    unchanged by both — which is the point (#5596).
    """
    return "".join(
        json.dumps(
            {
                "id": f"{CASE_ID}/log/{index}",
                "type": "CaseLedgerEntry",
                "published": "2026-01-01T00:00:00.560000+00:00",
                "caseId": CASE_ID,
                "logIndex": index,
                "semanticType": "create_case",
                "payloadSnapshot": {"type": "Create"},
                "prevLogHash": "0" * 64,
                "entryHash": "a" * 64,
            }
        )
        + "\n"
        for index in range(2)
    )


def _stub_run(name: str, checks: tuple[CheckNode, ...] = ()) -> ScenarioRun:
    return ScenarioRun(name, ledger=_ledger(), checks=checks)


def _stub_recorded(name: str) -> runner.RecordedRun:
    return runner.RecordedRun(
        Recording(name, ledger=_ledger(), steps=()), checks=()
    )


class TestFixtureStoryMutations:
    """Two check-side mutations the ledger cannot see (DEMOMA-17-002)."""

    @pytest.fixture
    def nodes(self):
        """Two cast containers, both answering one state endpoint."""
        app = FastAPI()

        @app.get("/api/v2/state")
        def state() -> dict[str, str]:
            return {"rmState": "VALID"}

        with TestClient(app) as client:
            yield runner._Nodes(
                clients={
                    runner._node_base(slot.compose_url): client
                    for slot in (VENDOR_SLOT, OTHER_SLOT)
                }
            )

    @staticmethod
    def _story(
        nodes: runner._Nodes,
        *,
        wait_on: ContainerSlot,
        check_inside_the_gate: bool,
    ) -> None:
        """A two-step story: a gate on the Vendor, then one standalone check.

        ``check_inside_the_gate`` places the check inside the gate or after
        it; ``wait_on`` is the cast member whose container the check's wait
        reads (EDF-06-002).
        """

        def wait(slot: ContainerSlot) -> None:
            nodes.call(
                DataLayerClient(base_url=slot.compose_url), "GET", "/state"
            )

        def the_check() -> None:
            with demo_check("the Vendor holds the case"):
                wait(wait_on)

        with demo_step("1. the Reporter tells the Vendor"):
            pass
        with demo_gate("the Vendor reached RM.VALID"):
            wait(VENDOR_SLOT)
            if check_inside_the_gate:
                the_check()
        if not check_inside_the_gate:
            the_check()

    def _run(self, nodes, **kwargs) -> ScenarioRun:
        reset_demo_failures()
        with recording_checks() as recorder:
            self._story(nodes, **kwargs)
        return ScenarioRun("fixture", ledger=_ledger(), checks=recorder.tree())

    @pytest.mark.spec("DEMOCI-11-055", "DEMOCI-11-056")
    def test_moving_a_check_out_of_its_gate_shows_in_the_checks_alone(
        self, nodes
    ):
        base = self._run(
            nodes, wait_on=VENDOR_SLOT, check_inside_the_gate=True
        )
        head = self._run(
            nodes, wait_on=VENDOR_SLOT, check_inside_the_gate=False
        )

        [one] = compare_runs({"fixture": base}, {"fixture": head})
        assert one.ledger == (), "the ledger saw a check-side change"
        assert one.checks, "the check tree missed the moved check"
        assert one.differs

    @pytest.mark.spec("DEMOCI-11-057", "EDF-06-002")
    def test_switching_a_wait_to_another_cast_member_shows_in_the_checks(
        self, nodes
    ):
        base = self._run(
            nodes, wait_on=VENDOR_SLOT, check_inside_the_gate=True
        )
        head = self._run(nodes, wait_on=OTHER_SLOT, check_inside_the_gate=True)

        [one] = compare_runs({"fixture": base}, {"fixture": head})
        assert one.ledger == ()
        assert one.checks
        assert any(OTHER_SLOT.name in line for line in one.checks)

    def test_an_unmutated_story_compares_equal(self, nodes):
        """Guards the two above: the pair differs only by the mutation."""
        runs = [
            self._run(nodes, wait_on=VENDOR_SLOT, check_inside_the_gate=True)
            for _ in range(2)
        ]

        [one] = compare_runs({"fixture": runs[0]}, {"fixture": runs[1]})
        assert not one.differs


class TestCompareRuns:
    CHECKS = (
        CheckNode(
            kind=CheckKind.STEP,
            label="1. the Reporter submits",
            outcome=CheckOutcome.PASSED,
        ),
    )

    def test_identical_runs_do_not_differ(self):
        [one] = compare_runs(
            {"rv": _stub_run("rv", self.CHECKS)},
            {"rv": _stub_run("rv", self.CHECKS)},
        )
        assert not one.differs

    def test_every_scenario_either_side_holds_is_compared(self):
        comparisons = compare_runs(
            {"rvv": _stub_run("rvv"), "rv": _stub_run("rv")},
            {"rv": _stub_run("rv"), "rcv": _stub_run("rcv")},
        )
        assert [one.scenario for one in comparisons] == ["rcv", "rv", "rvv"]

    @pytest.mark.parametrize("side", ["base", "head"])
    def test_a_scenario_on_one_side_only_differs(self, side):
        run = {"rv": _stub_run("rv", self.CHECKS)}
        base, head = (run, {}) if side == "base" else ({}, run)
        [one] = compare_runs(base, head)
        assert one.differs
        assert compare.MISSING_RUN in one.report()

    def test_a_report_names_the_scenario_and_each_differing_trace(self):
        [one] = compare_runs(
            {"rv": _stub_run("rv", self.CHECKS)},
            {
                "rv": _stub_run(
                    "rv", (replace(self.CHECKS[0], label="1. moved"),)
                )
            },
        )
        report = one.report()
        assert "rv: the two runs differ" in report
        assert "--- rv checks ---" in report
        assert "--- rv ledger ---" not in report


@pytest.fixture
def stubbed(monkeypatch):
    """Two registered scenarios whose runs are stubbed, not run."""
    specs = [
        spec for spec in discover_scenarios() if spec.name in {"rv", "rvv"}
    ]
    monkeypatch.setattr(compare, "discover_scenarios", lambda: specs)
    monkeypatch.setattr(compare, "load_topology", lambda: None)
    monkeypatch.setattr(
        compare,
        "record_scenario",
        lambda spec, _topology: _stub_recorded(spec.name),
    )
    return specs


class TestCompareCli:
    @pytest.mark.spec("DEMOCI-11-061")
    def test_identical_runs_pass(self, stubbed):
        result = CliRunner().invoke(compare.main, [])
        assert result.exit_code == 0, result.output
        assert "2 scenario(s) compared, none differ." in result.output
        assert "Total wall time:" in result.output

    @pytest.mark.spec("DEMOCI-11-061")
    def test_a_difference_fails_and_prints_the_per_scenario_diff(
        self, tmp_path
    ):
        base, head = tmp_path / "base", tmp_path / "head"
        write_run(_stub_run("rv"), base)
        write_run(
            ScenarioRun(
                "rv",
                ledger=_ledger(),
                checks=(
                    CheckNode(
                        kind=CheckKind.CHECK,
                        label="a check the base did not run",
                        outcome=CheckOutcome.PASSED,
                    ),
                ),
            ),
            head,
        )

        result = CliRunner().invoke(
            compare.main, ["--base", str(base), "--head", str(head)]
        )
        assert result.exit_code == DIFFERENT_EXIT_CODE
        assert "rv: the two runs differ" in result.output
        assert "--- rv checks ---" in result.output
        assert "a check the base did not run" in result.output
        assert "Differing scenarios: rv" in result.output

    def test_a_written_pair_that_agrees_passes(self, tmp_path):
        base, head = tmp_path / "base", tmp_path / "head"
        for root in (base, head):
            write_run(_stub_run("rv"), root)
            write_run(_stub_run("rvv"), root)

        result = CliRunner().invoke(
            compare.main, ["--base", str(base), "--head", str(head)]
        )
        assert result.exit_code == 0, result.output
        assert "rv: unchanged" in result.output

    @pytest.mark.spec("DEMOCI-11-062", "DF-09-009")
    def test_an_empty_written_pair_is_a_distinct_failure(self, tmp_path):
        base, head = tmp_path / "base", tmp_path / "head"
        base.mkdir()
        head.mkdir()
        result = CliRunner().invoke(
            compare.main, ["--base", str(base), "--head", str(head)]
        )
        assert result.exit_code == NO_SCENARIOS_EXIT_CODE
        assert "No scenario was compared" in result.output

    @pytest.mark.spec("DEMOCI-11-062", "DF-09-009")
    def test_an_empty_registry_is_a_distinct_failure(self, monkeypatch):
        monkeypatch.setattr(compare, "discover_scenarios", lambda: ())
        result = CliRunner().invoke(compare.main, [])
        assert result.exit_code == NO_SCENARIOS_EXIT_CODE
        assert "No scenario was selected" in result.output

    def test_write_then_compare_round_trips(self, stubbed, tmp_path):
        base, head = tmp_path / "base", tmp_path / "head"
        for root in (base, head):
            written = CliRunner().invoke(compare.main, ["--write", str(root)])
            assert written.exit_code == 0, written.output
            assert "Wrote" in written.output

        result = CliRunner().invoke(
            compare.main, ["--base", str(base), "--head", str(head)]
        )
        assert result.exit_code == 0, result.output

    def test_one_named_scenario_is_compared_alone(self, stubbed, tmp_path):
        base, head = tmp_path / "base", tmp_path / "head"
        for root in (base, head):
            write_run(_stub_run("rv"), root)
            write_run(_stub_run("rvv"), root)

        result = CliRunner().invoke(
            compare.main,
            [
                "--scenario",
                "rv",
                "--base",
                str(base),
                "--head",
                str(head),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "1 scenario(s) compared" in result.output

    def test_an_unregistered_scenario_is_refused(self, stubbed):
        result = CliRunner().invoke(compare.main, ["--scenario", "nope"])
        assert result.exit_code != 0
        assert "not registered: nope" in result.output

    def test_one_sided_directories_are_refused(self, stubbed, tmp_path):
        result = CliRunner().invoke(compare.main, ["--base", str(tmp_path)])
        assert result.exit_code != 0
        assert "needs both --base and --head" in result.output

    def test_write_with_a_comparison_is_refused(self, stubbed, tmp_path):
        result = CliRunner().invoke(
            compare.main,
            [
                "--write",
                str(tmp_path / "out"),
                "--base",
                str(tmp_path),
                "--head",
                str(tmp_path),
            ],
        )
        assert result.exit_code != 0
        assert "--write records one side" in result.output

    def test_each_recorded_pass_reports_its_wall_time(self, stubbed):
        result = CliRunner().invoke(compare.main, [])
        assert "Recorded rv (first) in" in result.output
        assert "Recorded rv (second) in" in result.output
