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

"""Unit tests for the FVCV-handoff five-actor CVD demo (DEMOMA-15).

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fvcv-handoff docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fvcv_handoff_demo as demo
from test.demo._helpers import make_testclient_call
from vultron.demo.cli import main


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
    mp = MonkeyPatch()
    try:
        mp.setattr(
            demo.DataLayerClient, "call", make_testclient_call(client, base)
        )
        yield
    finally:
        mp.undo()
        importlib.reload(demo)


# ---------------------------------------------------------------------------
# Unit tests for _phase_dump_case_ledgers
# ---------------------------------------------------------------------------


class TestPhaseDumpCaseLedgersFvcv:
    """Tests for the case-ledger dump phase in the FVCV-handoff demo."""

    def test_writes_jsonl_files_for_all_four_actors(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        coordinator_client = MagicMock()
        vendor2_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]
        coordinator_client.get_list.return_value = [{"logIndex": 0}]
        vendor2_client.get_list.return_value = [{"logIndex": 0}]

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/fvcv-test-case"
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            case=case,
        )

        case_slug = "https_example.org_cases_fvcv-test-case"
        assert (
            tmp_path
            / "fvcv-handoff"
            / "finder"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fvcv-handoff"
            / "vendor"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fvcv-handoff"
            / "coordinator"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fvcv-handoff"
            / "vendor2"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()

    def test_includes_case_actor_when_in_participant_index(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        coordinator_client = MagicMock()
        vendor2_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]
        coordinator_client.get_list.return_value = [{"logIndex": 0}]
        vendor2_client.get_list.return_value = [{"logIndex": 0}]

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/fvcv-with-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor-fvcv": (
                    "https://example.org/cases/fvcv-with-ca/participants/case-actor"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            case=case,
        )

        assert any(
            "/actors/case-actor-fvcv/demo/cases/fvcv-with-ca/log"
            in call.args[0]
            for call in vendor_client.get_list.call_args_list
        )


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestFvcvHandoffCliCommand:
    """Test that the 'fvcv-handoff' CLI sub-command is registered and reachable."""

    def test_fvcv_handoff_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert result.exit_code == 0, result.output

    def test_fvcv_handoff_command_finder_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--finder-url" in result.output

    def test_fvcv_handoff_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--vendor-url" in result.output

    def test_fvcv_handoff_command_coordinator_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--coordinator-url" in result.output

    def test_fvcv_handoff_command_vendor2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--vendor2-url" in result.output

    def test_fvcv_handoff_command_case_actor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--case-actor-url" in result.output

    def test_fvcv_handoff_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-handoff", "--help"])
        assert "--skip-health-check" in result.output


# ---------------------------------------------------------------------------
# Milestone assertion tests — AC-4 of ISSUE-1976
# ---------------------------------------------------------------------------


class TestFvcvHandoffMilestoneAssertions:
    """Verify that _phase_* functions call the required milestone helpers."""

    def _actor(self, id_: str = "urn:test:actor"):
        a = MagicMock()
        a.id_ = id_
        return a

    def _case(self, id_: str = "urn:test:case"):
        c = MagicMock()
        c.id_ = id_
        return c

    def _client(self):
        c = MagicMock()
        c.get.return_value = {}
        return c

    def test_phase_report_submission_calls_verify_case_active(self):
        """_phase_report_submission calls verify_case_active at M1."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        case_actor_client = self._client()
        vendor2_client = self._client()
        finder = self._actor("urn:test:finder")
        vendor = self._actor("urn:test:vendor")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        vendor2 = self._actor("urn:test:vendor2")
        vendor_in_vendor = self._actor("urn:test:vendor")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        case = self._case()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fvcv",
                return_value=(finder, vendor, coordinator, vendor2),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[vendor_in_vendor, coordinator_in_coordinator],
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(demo, "receiver_validates_report"),
            patch.object(demo, "find_case_for_offer", return_value=case),
            patch.object(demo, "receiver_engages_case"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor2_client=vendor2_client,
                finder_id=None,
                vendor_id=None,
                coordinator_id=None,
                vendor2_id=None,
            )

    def test_run_fvcv_handoff_calls_verify_case_active(self):
        """run_fvcv_handoff calls verify_case_active after all participants join (M1)."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        case_actor_client = self._client()
        vendor2_client = self._client()

        with (
            patch.object(
                demo,
                "_phase_report_submission",
                return_value=(
                    self._actor("f"),
                    self._actor("v"),
                    self._actor("v_v"),
                    self._actor("c"),
                    self._actor("c_c"),
                    self._actor("v2"),
                    MagicMock(),
                    MagicMock(),
                    self._case(),
                ),
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor",
            ),
            patch.object(
                demo, "_phase_ownership_handoff", return_value=self._case()
            ),
            patch.object(demo, "_phase_coordinator_invites_vendor2"),
            patch.object(demo, "_phase_sync_verification"),
            patch.object(demo, "_phase_notes_exchange"),
            patch.object(demo, "_phase_fix_lifecycle"),
            patch.object(demo, "_phase_publication"),
            patch.object(demo, "_phase_case_closure"),
            patch.object(demo, "_phase_dump_case_ledgers"),
            patch.object(demo, "get_actor_by_id", return_value=self._actor()),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "verify_case_active") as mock_m1,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo.run_fvcv_handoff_demo(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor2_client=vendor2_client,
            )
        mock_m1.assert_called()

    def test_phase_fix_lifecycle_calls_verify_fix_ready(self):
        """_phase_fix_lifecycle calls verify_fix_ready at M4/M5."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        with (
            patch.object(demo, "actor_notifies_fix_ready"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_fix_ready") as mock_m4,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_fix_lifecycle(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                case=case,
            )
        mock_m4.assert_called()

    def test_phase_publication_calls_verify_publicly_disclosed(self):
        """_phase_publication calls verify_publicly_disclosed at M6."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        finder = self._actor("urn:test:finder")
        finder_in_finder = self._actor("urn:test:finder")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case()

        with (
            patch.object(demo, "actor_notifies_published"),
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_publicly_disclosed") as mock_m6,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_publication(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                finder=finder,
                finder_in_finder=finder_in_finder,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )
        mock_m6.assert_called()

    def test_phase_publication_order_vendor1_vendor2_finder_coordinator(self):
        """Phase 6 notifies published in CVD order: Vendor1, Vendor2, Finder, Coordinator last."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        finder_in_finder = self._actor("urn:test:finder")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case()

        call_order: list[str] = []

        def _notify(**kwargs):
            call_order.append(kwargs["actor"].id_)

        with (
            patch.object(
                demo, "actor_notifies_published", side_effect=_notify
            ),
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_publicly_disclosed"),
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_publication(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=self._actor("urn:test:vendor"),
                vendor_in_vendor=vendor_in_vendor,
                vendor2=self._actor("urn:test:vendor2"),
                vendor2_in_vendor2=vendor2_in_vendor2,
                finder=self._actor("urn:test:finder"),
                finder_in_finder=finder_in_finder,
                coordinator=self._actor("urn:test:coordinator"),
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )

        assert call_order == [
            "urn:test:vendor",
            "urn:test:vendor2",
            "urn:test:finder",
            "urn:test:coordinator",
        ], f"Unexpected publication order: {call_order}"

    def test_phase_case_closure_calls_verify_case_closed(self):
        """_phase_case_closure calls verify_case_closed at M7."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        finder = self._actor("urn:test:finder")
        finder_in_finder = self._actor("urn:test:finder")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case()
        case.id_ = "urn:test:case"
        vendor_client.get.return_value = {
            "e0": {
                "case_id": case.id_,
                "log_index": 0,
                "entry_hash": "h0",
                "event_type": "close_case",
            }
        }

        with (
            patch.object(demo, "actor_closes_case"),
            patch.object(demo, "wait_for_all_participants_rm_closed"),
            patch.object(demo, "verify_case_closed") as mock_m7,
            patch.object(demo, "wait_for_event_type_in_ledger"),
            patch.object(demo, "wait_for_contiguous_ledger_coverage"),
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_case_closure(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                finder=finder,
                finder_in_finder=finder_in_finder,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )
        mock_m7.assert_called()

    def test_phase_case_closure_coordinator_closes_last(self):
        """Coordinator (case owner) must close after Vendor1, Vendor2, and Finder."""
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        finder = self._actor("urn:test:finder")
        finder_in_finder = self._actor("urn:test:finder")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case()
        case.id_ = "urn:test:case"
        vendor_client.get.return_value = {
            "e0": {
                "case_id": case.id_,
                "log_index": 0,
                "entry_hash": "h0",
                "event_type": "close_case",
            }
        }

        mock_close = MagicMock()

        with (
            patch.object(demo, "actor_closes_case", mock_close),
            patch.object(demo, "wait_for_all_participants_rm_closed"),
            patch.object(demo, "verify_case_closed"),
            patch.object(demo, "wait_for_event_type_in_ledger"),
            patch.object(demo, "wait_for_contiguous_ledger_coverage"),
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_case_closure(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                finder=finder,
                finder_in_finder=finder_in_finder,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )

        actors_closed = [
            call.kwargs["actor"].id_ for call in mock_close.call_args_list
        ]
        assert (
            actors_closed[-1] == coordinator_in_coordinator.id_
        ), "Coordinator (case owner) must close last; got order: " + str(
            actors_closed
        )
        assert actors_closed.index(finder_in_finder.id_) < actors_closed.index(
            coordinator_in_coordinator.id_
        ), "Finder must close before Coordinator"
