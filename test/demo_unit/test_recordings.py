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
import importlib
import json
from pathlib import Path

import httpx2 as httpx
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
from vultron.demo import recordings
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.in_process import InProcessRouter
from vultron.demo.recordings import (
    RECORDINGS_DIR,
    REPO_ROOT,
    ContainerTopology,
    load_topology,
    write_recording,
)
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.errors import DemoRecordingError

SYNTHETIC_DIR = REPO_ROOT / "ui" / "src" / "synthetic-ledgers"


def _ledger_files() -> list[Path]:
    return sorted(RECORDINGS_DIR.glob("*/*.jsonl")) + sorted(
        SYNTHETIC_DIR.glob("*.jsonl")
    )


class TestCommittedRecordings:
    def test_the_recorded_scenarios_are_the_registered_ones(self):
        names = tuple(spec.name for spec in discover_scenarios())
        assert recordings.layout_problems(names) == []

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
        topology = load_topology()
        assert topology.case_roles["vendor"] == [CVDRole.VENDOR]
        assert topology.case_roles["actor6"] == [
            CVDRole.VENDOR,
            CVDRole.DEPLOYER,
        ]
        assert "coordinator" not in topology.case_roles
        assert topology.case_actor_service_url == (
            "http://case-actor:7999/api/v2"
        )

    def test_case_roles_are_looked_up_by_the_actors_host(self):
        topology = load_topology()
        assert topology.case_roles_for(
            "http://vendor:7999/api/v2/actors/abc"
        ) == [CVDRole.VENDOR]
        assert (
            topology.case_roles_for(
                "http://coordinator:7999/api/v2/actors/abc"
            )
            == []
        )

    def test_an_unknown_slot_is_refused(self):
        topology = ContainerTopology(
            slot_urls={}, case_roles={}, case_actor_service_url="http://x"
        )
        role = ActorRole(
            name="reporter",
            url_env="VULTRON_NOWHERE_BASE_URL",
            default_url="http://localhost:1/api/v2",
            url_help="Nowhere.",
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


class TestLayoutProblems:
    @pytest.fixture
    def recorded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(recordings, "RECORDINGS_DIR", tmp_path)
        for name in ("rv", "retired"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "case-actor.jsonl").write_text("{}\n")
        (tmp_path / "rvv").mkdir()
        (tmp_path / "rvv" / "vendor.jsonl").write_text("{}\n")
        return tmp_path

    def test_each_disagreement_is_named(self, recorded):
        assert recordings.layout_problems(("rv", "rvv", "rcv")) == [
            "rcv: registered but not recorded",
            "retired: recorded but not a registered scenario",
            "rvv: has no case-actor.jsonl",
            "rvv: holds files other than case-actor.jsonl: ['vendor.jsonl']",
        ]

    def test_the_check_option_fails_on_a_disagreement(self, recorded):
        result = CliRunner().invoke(recordings.main, ["--check"])
        assert result.exit_code == 1
        assert (
            "retired: recorded but not a registered scenario" in result.output
        )
        assert recordings.REGENERATE_COMMAND in result.output

    def test_the_check_option_takes_no_scenario(self):
        result = CliRunner().invoke(
            recordings.main, ["--check", "--scenario", "rv"]
        )
        assert result.exit_code == 2
        assert "takes no --scenario" in result.output

    def test_the_check_option_passes_on_the_committed_recordings(self):
        result = CliRunner().invoke(recordings.main, ["--check"])
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
            recordings._read_dump(tmp_path, "rv")

    def test_an_entry_without_a_reason_still_names_the_actor(self, tmp_path):
        (tmp_path / "rv").mkdir()
        (tmp_path / "rv" / "dump-manifest.json").write_text(
            json.dumps({"actors": [{"actorName": "vendor"}]}), encoding="utf-8"
        )
        with pytest.raises(DemoRecordingError, match="no reason recorded"):
            recordings._read_dump(tmp_path, "rv")

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
        assert recordings._read_dump(tmp_path, "rv") == {
            "vendor": "v\n",
            "reporter": "r\n",
        }


class TestWriteRecording:
    def test_only_the_canonical_ledger_is_left(self, tmp_path, monkeypatch):
        monkeypatch.setattr(recordings, "RECORDINGS_DIR", tmp_path)
        (tmp_path / "rv").mkdir()
        (tmp_path / "rv" / "vendor.jsonl").write_text("old\n")
        path = write_recording("rv", "c\n")
        assert path == tmp_path / "rv" / "case-actor.jsonl"
        assert sorted(p.name for p in (tmp_path / "rv").iterdir()) == [
            "case-actor.jsonl"
        ]
        assert path.read_text() == "c\n"


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
        assert recordings.canonical_ledger("rv", ledgers) == self.CANONICAL

    def test_a_replica_entry_that_differs_is_refused(self):
        ledgers = {
            "case-actor": self.CANONICAL,
            "vendor": _line(0) + "\n" + _line(1, "edited") + "\n",
        }
        with pytest.raises(
            DemoRecordingError, match=r"'vendor'.*logIndex 1.*differs"
        ):
            recordings.canonical_ledger("rv", ledgers)

    def test_a_replica_entry_the_canonical_ledger_lacks_is_refused(self):
        ledgers = {"case-actor": self.CANONICAL, "vendor": _line(7) + "\n"}
        with pytest.raises(DemoRecordingError, match="does not"):
            recordings.canonical_ledger("rv", ledgers)

    def test_a_dump_without_the_canonical_ledger_is_refused(self):
        with pytest.raises(DemoRecordingError, match="no 'case-actor'"):
            recordings.canonical_ledger("rv", {"vendor": self.CANONICAL})

    def test_a_line_without_a_log_index_is_refused(self):
        ledgers = {"case-actor": self.CANONICAL, "vendor": '{"id": 1}\n'}
        with pytest.raises(DemoRecordingError, match="'vendor', line 1"):
            recordings.canonical_ledger("rv", ledgers)


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
            yield recordings._Nodes(clients={"http://vendor:7999": client})

    @pytest.fixture
    def client(self):
        return DataLayerClient(base_url="http://vendor:7999/api/v2")

    def test_a_host_no_role_names_is_refused(self, client):
        elsewhere = DataLayerClient(base_url="http://elsewhere:7999/api/v2")
        with pytest.raises(DemoRecordingError, match="elsewhere"):
            recordings._Nodes().call(elsewhere, "GET", "/actors/")

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
        events = self._run(recordings._one_row_at_a_time(deliver_batch))
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
        with recordings._scenario_nodes([], load_topology()):
            assert isinstance(slot.value, InProcessRouter)
        assert slot.value is before

    def test_the_default_emitter_is_restored_when_the_run_raises(self):
        slot = outbox_handler._DEFAULT_EMITTER_SLOT
        before = slot.value
        with (
            pytest.raises(RuntimeError),
            recordings._scenario_nodes([], load_topology()),
        ):
            raise RuntimeError("scenario failed")
        assert slot.value is before


class TestCli:
    def test_an_unregistered_scenario_is_refused(self):
        result = CliRunner().invoke(recordings.main, ["--scenario", "nope"])
        assert result.exit_code != 0
        assert "not registered: nope" in result.output

    def test_a_named_scenario_is_recorded_alone(self, tmp_path, monkeypatch):
        (tmp_path / "retired-scenario").mkdir()
        monkeypatch.setattr(recordings, "RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(recordings, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(recordings, "load_topology", lambda: None)
        monkeypatch.setattr(
            recordings,
            "record_scenario",
            lambda spec, _topology: f"{spec.name}\n",
        )
        result = CliRunner().invoke(recordings.main, ["--scenario", "rv"])
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
        monkeypatch.setattr(recordings, "RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(recordings, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(recordings, "discover_scenarios", lambda: specs)
        monkeypatch.setattr(recordings, "load_topology", lambda: None)
        monkeypatch.setattr(
            recordings,
            "record_scenario",
            lambda spec, _topology: f"{spec.name}\n",
        )
        for name in ("rv", "rvv"):
            write_recording(name, f"{name}\n")
        return tmp_path

    def test_report_changes_passes_when_nothing_changed(self, stubbed):
        result = CliRunner().invoke(recordings.main, ["--report-changes"])
        assert result.exit_code == 0, result.output

    def test_report_changes_names_a_changed_recording(self, stubbed):
        write_recording("rvv", "an older run\n")
        result = CliRunner().invoke(recordings.main, ["--report-changes"])
        assert result.exit_code == recordings.CHANGED_EXIT_CODE
        assert "Changed recordings: rvv" in result.output
        # The fresh recording is written, ready to commit or upload.
        assert recordings.recording_path("rvv").read_text() == "rvv\n"

    def test_report_changes_counts_a_removed_scenario(self, stubbed):
        write_recording("retired", "x\n")
        result = CliRunner().invoke(recordings.main, ["--report-changes"])
        assert result.exit_code == recordings.CHANGED_EXIT_CODE
        assert "Changed recordings: retired" in result.output

    def test_without_report_changes_a_change_still_exits_zero(self, stubbed):
        write_recording("rv", "an older run\n")
        result = CliRunner().invoke(recordings.main, [])
        assert result.exit_code == 0, result.output

    def test_a_full_run_records_every_scenario_and_drops_stale_ones(
        self, tmp_path, monkeypatch
    ):
        specs = [
            spec for spec in discover_scenarios() if spec.name in {"rv", "rvv"}
        ]
        (tmp_path / "retired-scenario").mkdir()
        monkeypatch.setattr(recordings, "RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(recordings, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(recordings, "discover_scenarios", lambda: specs)
        monkeypatch.setattr(recordings, "load_topology", lambda: None)
        monkeypatch.setattr(
            recordings,
            "record_scenario",
            lambda spec, _topology: f"{spec.name}\n",
        )
        result = CliRunner().invoke(recordings.main, [])
        assert result.exit_code == 0, result.output
        assert sorted(p.name for p in tmp_path.iterdir()) == ["rv", "rvv"]
        assert (tmp_path / "rvv" / "case-actor.jsonl").read_text() == "rvv\n"
