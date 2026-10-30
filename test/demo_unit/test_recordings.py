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

"""Tests for the committed scenario recordings and the recorder's parts (#3901).

Running a scenario takes up to two minutes.  The smoke test that runs one is in
``test/demo_recordings/``, in the integration suite, and the check that the
committed recordings are current is the scheduled ``demo-recordings`` workflow.
The checks here read only committed files or stub the run.
"""

import asyncio
import contextlib
import importlib
import json
from pathlib import Path

import httpx2 as httpx
import py_trees
import pytest
from click.testing import CliRunner
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi import outbox_handler
from vultron.adapters.driving.fastapi.outbox_lanes import (
    RowOutcome,
    StallOrder,
    deliver_batch,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.demo.determinism import TREE_RECORDING_SEED
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.helpers.cast import (
    CASE_ACTOR,
    CHARACTER_SLOTS,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
    ContainerSlot,
)
from vultron.demo.helpers.harness import StepMark
from vultron.demo.in_process import InProcessRouter
from vultron.demo.recordings import (
    cli,
    layout,
    ledgers as ledger_dump,
    prefix,
    runner,
)
from vultron.demo.recordings.layout import (
    RECORDINGS_DIR,
    Recording,
    write_recording,
)
from vultron.demo.recordings.topology import (
    REPO_ROOT,
    ContainerTopology,
    load_topology,
)
from vultron.demo.scenario.registry import (
    ScenarioSpec,
    discover_scenarios,
    scenario_tree,
)
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.errors import DemoRecordingError

SYNTHETIC_DIR = REPO_ROOT / "ui" / "src" / "synthetic-ledgers"


def _spec(name: str) -> ScenarioSpec:
    return next(spec for spec in discover_scenarios() if spec.name == name)


def _marks(spec: ScenarioSpec, *tails: int) -> tuple[StepMark, ...]:
    """Marks for *spec*'s declared steps, at *tails* in order."""
    return tuple(
        StepMark(branch_point, choice, tail)
        for (branch_point, choice), tail in zip(spec.path, tails, strict=True)
    )


def _stub_recording(name: str) -> Recording:
    """The recording a stubbed run of *name* returns: one line, no marks."""
    return Recording(name, f"{name}\n", ())


def _ledger_files() -> list[Path]:
    return sorted(RECORDINGS_DIR.glob("*/*.jsonl")) + sorted(
        SYNTHETIC_DIR.glob("*.jsonl")
    )


class TestCommittedRecordings:
    def test_the_recorded_scenarios_are_the_registered_ones(self):
        names = tuple(spec.name for spec in discover_scenarios())
        assert layout.layout_problems(names) == []

    @pytest.mark.parametrize(
        "path",
        _ledger_files(),
        ids=lambda p: str(p.relative_to(REPO_ROOT / "ui" / "src")),
    )
    def test_every_line_is_a_case_ledger_entry(self, path: Path):
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines, f"{path} is empty"
        for number, line in enumerate(lines, start=1):
            try:
                CaseLedgerEntry.model_validate(json.loads(line))
            except ValueError as exc:
                pytest.fail(f"{path}:{number}: {exc}")

    def test_the_synthetic_fixtures_are_checked(self):
        # The violation fixture is the only ledger that exercises flagging.
        assert (
            SYNTHETIC_DIR / "violations-case-ledger.jsonl"
        ) in _ledger_files()


class TestLoadTopology:
    def test_every_scenario_role_has_a_container_slot(self):
        topology = load_topology()
        for spec in discover_scenarios():
            module = importlib.import_module(spec.module_name)
            for role in module.ROLES:
                assert topology.url_for(role).startswith("http://")

    def test_container_case_roles_come_from_the_compose_file(self):
        """Only the fixed-role cast slots declare default case roles.

        A character actor takes its role from the act that seats it, so its
        container names none (DEMOCI-11-021); a Reporter's comes from
        submitting the report.
        """
        topology = load_topology()
        assert topology.case_roles[VENDOR_SLOT.name] == [CVDRole.VENDOR]
        assert topology.case_roles[COORDINATOR_SLOT.name] == [
            CVDRole.COORDINATOR
        ]
        assert REPORTER_SLOT.name not in topology.case_roles
        for slot in CHARACTER_SLOTS:
            assert slot.name not in topology.case_roles
        assert topology.case_actor_service_url == CASE_ACTOR.compose_url

    def test_case_roles_are_looked_up_by_the_actors_host(self):
        topology = load_topology()
        assert topology.case_roles_for(
            f"{VENDOR_SLOT.compose_url}/actors/abc"
        ) == [CVDRole.VENDOR]
        assert topology.case_roles_for(
            f"{COORDINATOR_SLOT.compose_url}/actors/abc"
        ) == [CVDRole.COORDINATOR]
        assert (
            topology.case_roles_for(f"{REPORTER_SLOT.compose_url}/actors/abc")
            == []
        )

    def test_an_unknown_slot_is_refused(self):
        topology = ContainerTopology(
            slot_urls={}, case_roles={}, case_actor_service_url="http://x"
        )
        role = ActorRole(
            name="reporter",
            slot=ContainerSlot(name="nowhere", port=1),
            title="Nobody",
        )
        with pytest.raises(DemoRecordingError, match="VULTRON_NOWHERE"):
            topology.url_for(role)

    def test_a_compose_file_without_services_is_refused(self, tmp_path):
        compose = tmp_path / "compose.yml"
        compose.write_text("version: '3'\n", encoding="utf-8")
        with pytest.raises(DemoRecordingError, match="services"):
            load_topology(compose)

    def test_a_mapping_environment_is_read(self, tmp_path):
        compose = tmp_path / "compose.yml"
        compose.write_text(
            "services:\n"
            "  demo-runner:\n"
            "    environment:\n"
            "      VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL: http://ca/api/v2\n"
            "      VULTRON_VENDOR_BASE_URL: http://vendor:7999/api/v2\n"
            "  vendor:\n"
            "    environment:\n"
            "      VULTRON_ACTOR__DEFAULT_CASE_ROLES: '[\"vendor\"]'\n"
            "  coordinator: {}\n",
            encoding="utf-8",
        )
        topology = load_topology(compose)
        assert topology.slot_urls == {
            "VULTRON_VENDOR_BASE_URL": "http://vendor:7999/api/v2"
        }
        assert topology.case_roles == {"vendor": [CVDRole.VENDOR]}

    def test_a_compose_file_without_the_runner_is_refused(self, tmp_path):
        compose = tmp_path / "compose.yml"
        compose.write_text("services:\n  vendor: {}\n", encoding="utf-8")
        with pytest.raises(DemoRecordingError, match="demo-runner"):
            load_topology(compose)

    def test_a_runner_without_a_case_actor_url_is_refused(self, tmp_path):
        compose = tmp_path / "compose.yml"
        compose.write_text(
            "services:\n  demo-runner:\n    environment: []\n",
            encoding="utf-8",
        )
        with pytest.raises(DemoRecordingError, match="CASE_ACTOR_SERVICE_URL"):
            load_topology(compose)

    def test_malformed_case_roles_are_refused(self, tmp_path):
        compose = tmp_path / "compose.yml"
        compose.write_text(
            "services:\n"
            "  demo-runner:\n"
            "    environment:\n"
            "      - VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=http://ca/api/v2\n"
            "  vendor:\n"
            "    environment:\n"
            '      - VULTRON_ACTOR__DEFAULT_CASE_ROLES=["wizard"]\n',
            encoding="utf-8",
        )
        with pytest.raises(DemoRecordingError, match="wizard"):
            load_topology(compose)


class _StopBeforeTheRun(Exception):
    """Raised in place of entering the recorder's deterministic context."""


class TestRecordingSeed:
    """One seed for the whole tree (DEMOCI-11-025)."""

    @staticmethod
    def _seeds_used(monkeypatch: pytest.MonkeyPatch) -> list[str]:
        """The seed ``record_scenario`` asks for, once per registered scenario.

        Captured by replacing ``deterministic_run`` with a context manager that
        raises on entry: the seed is chosen before the scenario runs, so this
        reads the real call without paying two minutes per scenario.
        """
        seeds: list[str] = []

        @contextlib.contextmanager
        def capture(seed: str, **kwargs: object):
            seeds.append(seed)
            raise _StopBeforeTheRun
            yield  # pragma: no cover - unreachable, keeps this a generator

        monkeypatch.setattr(runner, "deterministic_run", capture)
        for spec in discover_scenarios():
            with pytest.raises(_StopBeforeTheRun):
                runner.record_scenario(spec)
        return seeds

    def test_every_scenario_records_with_the_same_seed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A per-scenario seed gave siblings different ids for a shared step."""
        seeds = self._seeds_used(monkeypatch)
        assert seeds, "no scenario was recorded"
        assert set(seeds) == {TREE_RECORDING_SEED}

    def test_the_seed_is_not_a_scenario_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guards the guard: a name-shaped seed would pass the check above
        only if every scenario shared one name, but a future refactor could
        reintroduce ``seed=spec.name`` for a single-scenario tree."""
        names = {spec.name for spec in discover_scenarios()}
        assert TREE_RECORDING_SEED not in names


class TestLayoutProblems:
    @pytest.fixture
    def recorded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(layout, "RECORDINGS_DIR", tmp_path)
        for name in ("rv", "retired"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "case-actor.jsonl").write_text("{}\n")
            (tmp_path / name / "steps.json").write_text('{"steps": []}\n')
        (tmp_path / "rvv").mkdir()
        (tmp_path / "rvv" / "vendor.jsonl").write_text("{}\n")
        (tmp_path / "rcv").mkdir()
        (tmp_path / "rcv" / "case-actor.jsonl").write_text("{}\n")
        return tmp_path

    def test_each_disagreement_is_named(self, recorded):
        assert layout.layout_problems(("rv", "rvv", "rcv", "rcvcv")) == [
            "rcvcv: registered but not recorded",
            "retired: recorded but not a registered scenario",
            "rcv: has no steps.json",
            "rvv: has no case-actor.jsonl",
            "rvv: has no steps.json",
            "rvv: holds files other than case-actor.jsonl and steps.json: "
            "['vendor.jsonl']",
        ]

    def test_the_check_option_fails_on_a_disagreement(self, recorded):
        result = CliRunner().invoke(cli.main, ["--check"])
        assert result.exit_code == 1
        assert (
            "retired: recorded but not a registered scenario" in result.output
        )
        assert cli.REGENERATE_COMMAND in result.output

    def test_the_check_option_takes_no_scenario(self):
        result = CliRunner().invoke(cli.main, ["--check", "--scenario", "rv"])
        assert result.exit_code == 2
        assert "takes no --scenario" in result.output

    def test_the_check_option_passes_on_the_committed_recordings(self):
        result = CliRunner().invoke(cli.main, ["--check"])
        assert result.exit_code == 0, result.output


class TestReadDump:
    def test_an_uncaptured_ledger_is_refused(self, tmp_path):
        (tmp_path / "rv").mkdir()
        (tmp_path / "rv" / "dump-manifest.json").write_text(
            json.dumps(
                {
                    "actors": [
                        {
                            "actorName": "vendor",
                            "captured": False,
                            "ledgerFile": None,
                            "reason": "404 from the vendor container",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(DemoRecordingError, match=r"vendor.*404"):
            ledger_dump.read_dump(tmp_path, "rv")

    def test_an_entry_without_a_reason_still_names_the_actor(self, tmp_path):
        (tmp_path / "rv").mkdir()
        (tmp_path / "rv" / "dump-manifest.json").write_text(
            json.dumps({"actors": [{"actorName": "vendor"}]}), encoding="utf-8"
        )
        with pytest.raises(DemoRecordingError, match="no reason recorded"):
            ledger_dump.read_dump(tmp_path, "rv")

    def test_captured_ledgers_are_returned_in_dump_order(self, tmp_path):
        scenario = tmp_path / "rv"
        (scenario / "vendor").mkdir(parents=True)
        (scenario / "reporter").mkdir()
        (scenario / "vendor" / "c.jsonl").write_text("v\n", encoding="utf-8")
        (scenario / "reporter" / "c.jsonl").write_text("r\n", encoding="utf-8")
        actors = [
            {
                "actorName": name,
                "captured": True,
                "ledgerFile": f"{name}/c.jsonl",
            }
            for name in ("vendor", "reporter")
        ]
        (scenario / "dump-manifest.json").write_text(
            json.dumps({"actors": actors}), encoding="utf-8"
        )
        assert ledger_dump.read_dump(tmp_path, "rv") == {
            "vendor": "v\n",
            "reporter": "r\n",
        }


class TestWriteRecording:
    def test_only_the_ledger_and_its_steps_are_left(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(layout, "RECORDINGS_DIR", tmp_path)
        (tmp_path / "rv").mkdir()
        (tmp_path / "rv" / "vendor.jsonl").write_text("old\n")
        path = write_recording(
            Recording(
                "rv", "c\n", (StepMark("reporter-whom-to-tell", "vendor", 0),)
            )
        )
        assert path == tmp_path / "rv" / "case-actor.jsonl"
        assert sorted(p.name for p in (tmp_path / "rv").iterdir()) == [
            "case-actor.jsonl",
            "steps.json",
        ]
        assert path.read_text() == "c\n"
        assert json.loads((tmp_path / "rv" / "steps.json").read_text()) == {
            "steps": [
                {
                    "branchPoint": "reporter-whom-to-tell",
                    "choice": "vendor",
                    "ledgerTail": 0,
                }
            ]
        }

    def test_a_written_recording_reads_back(self, tmp_path, monkeypatch):
        monkeypatch.setattr(layout, "RECORDINGS_DIR", tmp_path)
        spec = _spec("rv")
        recording = Recording("rv", "a\nb\n", _marks(spec, 0, 2))
        write_recording(recording)
        assert layout.read_recording("rv", spec.path) == recording
        assert layout.is_current(recording)
        assert not layout.is_current(
            Recording("rv", "a\nb\n", _marks(spec, 0, 1))
        )

    def test_a_step_past_the_ledger_is_refused(self):
        with pytest.raises(DemoRecordingError, match="past the 1 entries"):
            Recording("rv", "a\n", _marks(_spec("rv"), 0, 2))


def _line(index: int, tag: str = "") -> str:
    return json.dumps({"logIndex": index, "tag": tag})


class TestCanonicalLedger:
    CANONICAL = "\n".join(_line(i) for i in range(3)) + "\n"

    def test_replicas_that_copy_the_canonical_entries_pass(self):
        ledgers = {
            "case-actor": self.CANONICAL,
            "vendor": self.CANONICAL,
            # A participant that left early holds a shorter replica.
            "reporter": _line(0) + "\n" + _line(1) + "\n",
        }
        assert ledger_dump.canonical_ledger("rv", ledgers) == self.CANONICAL

    def test_a_replica_entry_that_differs_is_refused(self):
        ledgers = {
            "case-actor": self.CANONICAL,
            "vendor": _line(0) + "\n" + _line(1, "edited") + "\n",
        }
        with pytest.raises(
            DemoRecordingError, match=r"'vendor'.*logIndex 1.*differs"
        ):
            ledger_dump.canonical_ledger("rv", ledgers)

    def test_a_replica_entry_the_canonical_ledger_lacks_is_refused(self):
        ledgers = {"case-actor": self.CANONICAL, "vendor": _line(7) + "\n"}
        with pytest.raises(DemoRecordingError, match="does not"):
            ledger_dump.canonical_ledger("rv", ledgers)

    def test_a_dump_without_the_canonical_ledger_is_refused(self):
        with pytest.raises(DemoRecordingError, match="no 'case-actor'"):
            ledger_dump.canonical_ledger("rv", {"vendor": self.CANONICAL})

    def test_a_line_without_a_log_index_is_refused(self):
        ledgers = {"case-actor": self.CANONICAL, "vendor": '{"id": 1}\n'}
        with pytest.raises(DemoRecordingError, match="'vendor', line 1"):
            ledger_dump.canonical_ledger("rv", ledgers)


class TestNodesCall:
    @pytest.fixture
    def nodes(self):
        app = FastAPI()

        @app.get("/api/v2/missing")
        def missing() -> PlainTextResponse:
            return PlainTextResponse("gone", status_code=404)

        @app.get("/api/v2/text")
        def text() -> PlainTextResponse:
            return PlainTextResponse("plain words")

        @app.get("/api/v2/json")
        def as_json(q: str) -> dict[str, str]:
            return {"q": q}

        with TestClient(app) as client:
            yield runner._Nodes(clients={"http://vendor:7999": client})

    @pytest.fixture
    def client(self):
        return DataLayerClient(base_url="http://vendor:7999/api/v2")

    def test_a_host_no_role_names_is_refused(self, client):
        elsewhere = DataLayerClient(base_url="http://elsewhere:7999/api/v2")
        with pytest.raises(DemoRecordingError, match="elsewhere"):
            runner._Nodes().call(elsewhere, "GET", "/actors/")

    def test_an_error_status_raises_as_the_real_client_does(
        self, nodes, client
    ):
        # Callers branch on the status: a 404 from the ledger endpoint means
        # "this container does not hold the case".
        with pytest.raises(httpx.HTTPStatusError) as caught:
            nodes.call(client, "GET", "/missing")
        assert caught.value.response.status_code == 404

    def test_the_query_string_reaches_the_node(self, nodes, client):
        assert nodes.call(client, "GET", "/json?q=yes", timeout=5) == {
            "q": "yes"
        }

    def test_a_body_that_is_not_json_is_returned_as_text(self, nodes, client):
        assert nodes.call(client, "GET", "/text") == "plain words"


class TestOneRowAtATime:
    @staticmethod
    def _run(batch) -> list[str]:
        events: list[str] = []

        async def deliver(activity_id: str) -> RowOutcome:
            events.append(f"start {activity_id}")
            await asyncio.sleep(0)
            events.append(f"end {activity_id}")
            return RowOutcome.DELIVERED

        rows = [(aid, frozenset({f"lane-{aid}"})) for aid in ("a", "b", "c")]
        assert asyncio.run(batch(rows, deliver, StallOrder())) == []
        return events

    def test_the_outbox_alone_overlaps_rows_in_distinct_lanes(self):
        # The race the wrapper removes: distinct lanes run concurrently.
        events = self._run(deliver_batch)
        assert events[:2] == ["start a", "start b"]

    def test_wrapped_rows_run_one_at_a_time_in_pop_order(self):
        events = self._run(runner._one_row_at_a_time(deliver_batch))
        assert events == [
            "start a",
            "end a",
            "start b",
            "end b",
            "start c",
            "end c",
        ]


class TestScenarioNodes:
    def test_the_default_emitter_is_restored_on_exit(self):
        slot = outbox_handler._DEFAULT_EMITTER_SLOT
        before = slot.value
        with runner._scenario_nodes([], load_topology()):
            assert isinstance(slot.value, InProcessRouter)
        assert slot.value is before

    def test_the_default_emitter_is_restored_when_the_run_raises(self):
        slot = outbox_handler._DEFAULT_EMITTER_SLOT
        before = slot.value
        with (
            pytest.raises(RuntimeError),
            runner._scenario_nodes([], load_topology()),
        ):
            raise RuntimeError("scenario failed")
        assert slot.value is before

    def test_the_blackboard_registry_is_cleared_around_a_run(self):
        """A second run must not meet the first run's py_trees clients.

        The registry is process-global and keyed by a uuid4 that nothing
        unregisters, so with one tree-wide seed (DEMOCI-11-025) the second run
        redraws the first run's client ids and py_trees refuses them.
        """
        registry = py_trees.blackboard.Blackboard.clients
        py_trees.blackboard.Client(name="left over by an earlier run")
        assert registry
        with runner._scenario_nodes([], load_topology()):
            assert not registry
            py_trees.blackboard.Client(name="drawn during the run")
            assert registry
        assert not registry

    def test_the_blackboard_registry_is_cleared_when_the_run_raises(self):
        """A failed scenario must not leave its clients for the next one."""
        registry = py_trees.blackboard.Blackboard.clients
        with (
            pytest.raises(RuntimeError),
            runner._scenario_nodes([], load_topology()),
        ):
            py_trees.blackboard.Client(name="drawn before the failure")
            raise RuntimeError("scenario failed")
        assert not registry


class TestCli:
    def test_an_unregistered_scenario_is_refused(self):
        result = CliRunner().invoke(cli.main, ["--scenario", "nope"])
        assert result.exit_code != 0
        assert "not registered: nope" in result.output

    def test_a_named_scenario_is_recorded_alone(self, tmp_path, monkeypatch):
        (tmp_path / "retired-scenario").mkdir()
        monkeypatch.setattr(layout, "RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(layout, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(cli, "load_topology", lambda: None)
        monkeypatch.setattr(
            cli,
            "record_scenario",
            lambda spec, _topology: _stub_recording(spec.name),
        )
        result = CliRunner().invoke(cli.main, ["--scenario", "rv"])
        assert result.exit_code == 0, result.output
        # Only a full run drops the recordings of unregistered scenarios.
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "retired-scenario",
            "rv",
        ]

    @pytest.fixture
    def stubbed(self, tmp_path, monkeypatch):
        """Two registered scenarios whose recordings are "<name>\\n"."""
        specs = [
            spec for spec in discover_scenarios() if spec.name in {"rv", "rvv"}
        ]
        monkeypatch.setattr(layout, "RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(layout, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(cli, "discover_scenarios", lambda: specs)
        monkeypatch.setattr(cli, "load_topology", lambda: None)
        monkeypatch.setattr(
            cli,
            "record_scenario",
            lambda spec, _topology: _stub_recording(spec.name),
        )
        for name in ("rv", "rvv"):
            write_recording(_stub_recording(name))
        return tmp_path

    def test_report_changes_passes_when_nothing_changed(self, stubbed):
        result = CliRunner().invoke(cli.main, ["--report-changes"])
        assert result.exit_code == 0, result.output

    def test_report_changes_names_a_changed_recording(self, stubbed):
        write_recording(Recording("rvv", "an older run\n", ()))
        result = CliRunner().invoke(cli.main, ["--report-changes"])
        assert result.exit_code == cli.CHANGED_EXIT_CODE
        assert "Changed recordings: rvv" in result.output
        # The fresh recording is written, ready to commit or upload.
        assert layout.recording_path("rvv").read_text() == "rvv\n"

    def test_report_changes_counts_a_removed_scenario(self, stubbed):
        write_recording(Recording("retired", "x\n", ()))
        result = CliRunner().invoke(cli.main, ["--report-changes"])
        assert result.exit_code == cli.CHANGED_EXIT_CODE
        assert "Changed recordings: retired" in result.output

    def test_without_report_changes_a_change_still_exits_zero(self, stubbed):
        write_recording(Recording("rv", "an older run\n", ()))
        result = CliRunner().invoke(cli.main, [])
        assert result.exit_code == 0, result.output

    def test_a_full_run_records_every_scenario_and_drops_stale_ones(
        self, tmp_path, monkeypatch
    ):
        specs = [
            spec for spec in discover_scenarios() if spec.name in {"rv", "rvv"}
        ]
        (tmp_path / "retired-scenario").mkdir()
        monkeypatch.setattr(layout, "RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(layout, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(cli, "discover_scenarios", lambda: specs)
        monkeypatch.setattr(cli, "load_topology", lambda: None)
        monkeypatch.setattr(
            cli,
            "record_scenario",
            lambda spec, _topology: _stub_recording(spec.name),
        )
        result = CliRunner().invoke(cli.main, [])
        assert result.exit_code == 0, result.output
        assert sorted(p.name for p in tmp_path.iterdir()) == ["rv", "rvv"]
        assert (tmp_path / "rvv" / "case-actor.jsonl").read_text() == "rvv\n"


class TestParseStepMarks:
    PATH = (("reporter-whom-to-tell", "vendor"), ("vendor-after-answer", "x"))

    @staticmethod
    def _text(*steps: tuple[str, str, object]) -> str:
        return json.dumps(
            {
                "steps": [
                    {"branchPoint": bp, "choice": choice, "ledgerTail": tail}
                    for bp, choice, tail in steps
                ]
            }
        )

    def test_marks_that_cover_the_path_are_returned(self):
        marks = ledger_dump.parse_step_marks(
            self._text(
                ("reporter-whom-to-tell", "vendor", 0),
                ("vendor-after-answer", "x", 4),
            ),
            "rv",
            self.PATH,
        )
        assert marks == (
            StepMark("reporter-whom-to-tell", "vendor", 0),
            StepMark("vendor-after-answer", "x", 4),
        )

    def test_a_missing_step_is_refused(self):
        with pytest.raises(DemoRecordingError, match="reach_step"):
            ledger_dump.parse_step_marks(
                self._text(("reporter-whom-to-tell", "vendor", 0)),
                "rv",
                self.PATH,
            )

    def test_steps_out_of_order_are_refused(self):
        with pytest.raises(DemoRecordingError, match="declared path"):
            ledger_dump.parse_step_marks(
                self._text(
                    ("vendor-after-answer", "x", 0),
                    ("reporter-whom-to-tell", "vendor", 4),
                ),
                "rv",
                self.PATH,
            )

    @pytest.mark.parametrize("tails", [(4, 2), (0, -1), (0, "4"), (0, True)])
    def test_a_tail_that_is_not_a_rising_count_is_refused(self, tails):
        with pytest.raises(DemoRecordingError, match="ledger tails"):
            ledger_dump.parse_step_marks(
                self._text(
                    ("reporter-whom-to-tell", "vendor", tails[0]),
                    ("vendor-after-answer", "x", tails[1]),
                ),
                "rv",
                self.PATH,
            )

    @pytest.mark.parametrize("text", ["not json", "{}", '{"steps": [{}]}'])
    def test_malformed_marks_are_refused(self, text):
        with pytest.raises(DemoRecordingError, match="not readable"):
            ledger_dump.parse_step_marks(text, "rv", self.PATH)

    def test_a_mark_round_trips_through_its_json_shape(self):
        mark = StepMark("vendor-after-answer", "x", 4)
        assert StepMark.from_json(mark.as_json()) == mark

    def test_a_run_without_marks_is_refused(self, tmp_path):
        with pytest.raises(DemoRecordingError, match="left no step marks"):
            ledger_dump.read_step_marks(tmp_path, "rv", self.PATH)


def _entry(index: int, actor: str, obj: str, kind: str = "Add") -> dict:
    """A ledger-entry-shaped fixture: *actor* does *kind* to *obj*."""
    return {
        "id": f"urn:uuid:00000000-0000-4000-8000-{index:012d}",
        "logIndex": index,
        "published": f"2026-01-01T00:00:0{index}+00:00",
        "payloadSnapshot": {
            "type": kind,
            "actor": actor,
            "object": obj,
            "name": f"{actor} {kind} {obj}",
        },
    }


#: Two unrelated sets of addresses for the same three objects.  The comparison
#: is address-independent on purpose (DEMOCI-11-017): the fixed cast makes
#: siblings agree on addresses, and byte identity is the stronger check that
#: then applies to a composed family (DEMOCI-11-018).
_FIRST = (
    "http://one.test/api/v2/actors/a",
    "urn:uuid:" + "1" * 8 + "-1111-4111-8111-" + "1" * 12,
)
_SECOND = (
    "http://two.test/api/v2/actors/b",
    "urn:uuid:" + "2" * 8 + "-2222-4222-8222-" + "2" * 12,
)


class TestIsomorphism:
    """The shared-prefix check's comparison (DEMOCI-11-017)."""

    def test_the_same_story_at_other_addresses_is_isomorphic(self):
        actor, case = _FIRST
        other_actor, other_case = _SECOND
        first = [_entry(0, actor, case), _entry(1, actor, case, "Join")]
        second = [
            _entry(0, other_actor, other_case),
            _entry(1, other_actor, other_case, "Join"),
        ]
        # Shift the second ledger's own ids and clock, too.
        for entry in second:
            entry["id"] = entry["id"].replace("8000", "9000")
            entry["published"] = "2026-03-04T05:06:07.890000+00:00"
        assert prefix.isomorphism_mismatch(first, second) is None

    def test_a_reordered_step_is_not_isomorphic(self):
        actor, case = _FIRST
        first = [
            _entry(0, actor, case, "Offer"),
            _entry(1, actor, case, "Join"),
        ]
        second = [
            _entry(0, actor, case, "Join"),
            _entry(1, actor, case, "Offer"),
        ]
        mismatch = prefix.isomorphism_mismatch(first, second)
        assert mismatch is not None and mismatch.startswith("entry 0 differs")

    def test_references_that_map_inconsistently_are_not_isomorphic(self):
        actor, case = _FIRST
        other_actor, other_case = _SECOND
        # The first ledger acts on one case twice; the second on two cases.
        first = [_entry(0, actor, case), _entry(1, actor, case)]
        second = [
            _entry(0, other_actor, other_case),
            _entry(1, other_actor, actor),
        ]
        mismatch = prefix.isomorphism_mismatch(first, second)
        assert mismatch is not None and mismatch.startswith("entry 1 differs")

    def test_an_id_inside_a_string_and_a_key_maps_with_the_rest(self):
        actor, case = _FIRST
        other_actor, other_case = _SECOND
        first = [{"index": {actor: case}, "name": f"{actor} owns {case}"}]
        second = [
            {
                "index": {other_actor: other_case},
                "name": f"{other_actor} owns {other_case}",
            }
        ]
        swapped = [
            {
                "index": {other_actor: other_case},
                "name": f"{other_case} owns {other_actor}",
            }
        ]
        assert prefix.isomorphism_mismatch(first, second) is None
        assert prefix.isomorphism_mismatch(first, swapped) is not None

    def test_a_named_participant_id_maps_like_a_uuid_one(self):
        _, case = _FIRST
        uuid = "3" * 8 + "-3333-4333-8333-" + "3" * 12
        named = [{"participant": f"{case}/participants/vendor"}]
        unnamed = [{"participant": f"{case}/participants/{uuid}"}]
        assert prefix.isomorphism_mismatch(named, unnamed) is None

    def test_different_literal_text_is_not_isomorphic(self):
        actor, case = _FIRST
        first = [_entry(0, actor, case)]
        second = [_entry(0, actor, case)]
        second[0]["payloadSnapshot"]["content"] = "a different note"
        mismatch = prefix.isomorphism_mismatch(first, second)
        assert mismatch is not None and "content" in mismatch

    def test_a_longer_prefix_is_not_isomorphic(self):
        actor, case = _FIRST
        first = [_entry(0, actor, case)]
        second = [_entry(0, actor, case), _entry(1, actor, case)]
        mismatch = prefix.isomorphism_mismatch(first, second)
        assert mismatch is not None and "1 and 2 entries" in mismatch


class TestByteIdentity:
    """The composed families' comparison (DEMOCI-11-018)."""

    def test_identical_prefixes_pass(self):
        assert prefix.byte_mismatch(["a", "b"], ["a", "b"]) is None

    def test_one_byte_before_the_branch_point_fails(self):
        mismatch = prefix.byte_mismatch(['{"x": 1}', "b"], ['{"x": 2}', "b"])
        assert mismatch == "entry 0 differs from byte 6 on."

    def test_an_isomorphic_pair_is_not_byte_identical(self):
        actor, case = _FIRST
        other_actor, other_case = _SECOND
        first = [json.dumps(_entry(0, actor, case))]
        second = [json.dumps(_entry(0, other_actor, other_case))]
        assert prefix.byte_mismatch(first, second) is not None

    def test_a_longer_prefix_fails(self):
        assert prefix.byte_mismatch(["a"], ["a", "b"]) == (
            "the prefixes hold 1 and 2 entries."
        )


def _committed(name: str) -> Recording:
    return layout.read_recording(name, _spec(name).path)


class TestSharedPrefixes:
    """Every two scenarios agree up to where their paths part (DEMOCI-11-017)."""

    def test_every_pair_of_scenarios_is_checked(self):
        names = {spec.name for spec in discover_scenarios()}
        pairs = prefix.shared_prefixes(scenario_tree())
        assert len(pairs) == len(names) * (len(names) - 1) // 2
        assert {p.first for p in pairs} | {p.second for p in pairs} == names

    def test_the_depth_is_where_the_paths_part(self):
        by_id = {p.id: p for p in prefix.shared_prefixes(scenario_tree())}
        assert "rv~rvv@1" in by_id
        assert "rcv~rv@0" in by_id
        assert "rvcv-extension~rvcv-handoff@2" in by_id

    @pytest.mark.parametrize(
        "name", sorted(spec.name for spec in discover_scenarios())
    )
    def test_each_recording_marks_its_declared_steps(self, name):
        recording = _committed(name)
        assert [(m.branch_point, m.choice) for m in recording.steps] == list(
            _spec(name).path
        )

    @pytest.mark.parametrize(
        "pair",
        prefix.shared_prefixes(scenario_tree()),
        ids=lambda pair: pair.id,
    )
    def test_the_ledgers_are_isomorphic_up_to_the_branch_point(self, pair):
        mismatch = prefix.pair_isomorphism_mismatch(
            pair, _committed(pair.first), _committed(pair.second)
        )
        assert mismatch is None, (
            f"{pair.first} and {pair.second} share their path for "
            f"{pair.depth} steps, but their ledgers differ before "
            f"{_spec(pair.first).path[pair.depth][0]}: {mismatch} "
            f"Regenerate with {cli.REGENERATE_COMMAND} after fixing the order."
        )

    def test_a_missing_committed_recording_names_the_command(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(layout, "RECORDINGS_DIR", tmp_path)
        with pytest.raises(DemoRecordingError, match="export-demo-recordings"):
            layout.read_recording("rv", _spec("rv").path)


#: Two fixture recordings of rv's path: the root at 0, the Vendor's decision
#: after two entries, then one entry each that differs.
_RV_MARKS = (
    StepMark("reporter-whom-to-tell", "vendor", 0),
    StepMark("vendor-after-answer", "report-fix-ready", 2),
)


def _fixture(name: str, lines: list[str]) -> Recording:
    return Recording(name, "".join(f"{line}\n" for line in lines), _RV_MARKS)


class TestComposedFamilies:
    """A composed family is byte-identical up to the branch point (DEMOCI-11-018)."""

    # Parametrizes over no pair until the first family is written as
    # composition (#4733) and named in COMPOSED_FAMILIES: until then every
    # sibling seeds its own actor ids, slots and ports, so only the
    # isomorphism above can hold.  pytest reports the empty set as one skip.
    @pytest.mark.parametrize(
        "pair",
        prefix.composed_pairs(prefix.shared_prefixes(scenario_tree())),
        ids=lambda pair: pair.id,
    )
    def test_the_ledgers_are_byte_identical_up_to_the_branch_point(self, pair):
        mismatch = prefix.pair_byte_mismatch(
            pair, _committed(pair.first), _committed(pair.second)
        )
        assert mismatch is None, (
            f"{pair.first} and {pair.second} are one composed family, but "
            f"their ledgers differ before the branch point: {mismatch}"
        )

    def test_every_composed_family_names_registered_scenarios(self):
        names = {spec.name for spec in discover_scenarios()}
        for family in prefix.COMPOSED_FAMILIES:
            assert len(family) >= 2 and family <= names, family

    def test_only_pairs_inside_one_family_are_selected(self):
        pairs = prefix.shared_prefixes(scenario_tree())
        selected = prefix.composed_pairs(
            pairs, [frozenset({"rv", "rvv"}), frozenset({"rcv", "rcv-reject"})]
        )
        assert [pair.id for pair in selected] == [
            "rcv~rcv-reject@2",
            "rv~rvv@1",
        ]

    def test_a_marked_family_pair_one_byte_apart_fails(self):
        (pair,) = prefix.composed_pairs(
            prefix.shared_prefixes(scenario_tree()), [frozenset({"rv", "rvv"})]
        )
        first = _fixture("rv", ['{"a": 1}', '{"b": 2}', '{"rv": 3}'])
        second = _fixture("rvv", ['{"a": 1}', '{"b": 3}', '{"rvv": 3}'])
        assert prefix.pair_byte_mismatch(pair, first, second) == (
            "entry 1 differs from byte 6 on."
        )

    def test_a_marked_family_pair_that_differs_after_the_branch_passes(self):
        (pair,) = prefix.composed_pairs(
            prefix.shared_prefixes(scenario_tree()), [frozenset({"rv", "rvv"})]
        )
        first = _fixture("rv", ['{"a": 1}', '{"b": 2}', '{"rv": 3}'])
        second = _fixture("rvv", ['{"a": 1}', '{"b": 2}', '{"rvv": 3}'])
        assert prefix.pair_byte_mismatch(pair, first, second) is None
        assert prefix.pair_isomorphism_mismatch(pair, first, second) is None
