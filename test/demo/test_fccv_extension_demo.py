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

"""Unit tests for the FCCV-extension four-actor CVD demo (DEMOMA-13).

Uses a single TestClient (one FastAPI app instance) to simulate four containers.
All four DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fccv-extension docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit

AC-4 of ISSUE-1976: milestone assertion tests at each phase boundary.
"""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fccv_extension_demo as demo
from test.demo._helpers import make_testclient_call
from vultron.demo.cli import main

# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


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
# CLI command smoke tests
# ---------------------------------------------------------------------------


class TestFccvExtensionCliCommand:
    """Test that the 'fccv-extension' CLI sub-command is registered."""

    def test_fccv_extension_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-extension", "--help"])
        assert result.exit_code == 0, result.output

    def test_fccv_extension_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-extension", "--help"])
        assert "--skip-health-check" in result.output

    def test_fccv_extension_command_finder_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-extension", "--help"])
        assert "--finder-url" in result.output

    def test_fccv_extension_command_c1_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-extension", "--help"])
        assert "--c1-url" in result.output

    def test_fccv_extension_command_c2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-extension", "--help"])
        assert "--c2-url" in result.output

    def test_fccv_extension_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-extension", "--help"])
        assert "--vendor-url" in result.output


# ---------------------------------------------------------------------------
# Milestone assertion tests — AC-4 of ISSUE-1976
# ---------------------------------------------------------------------------


class TestFccvExtensionMilestoneAssertions:
    """Verify that _phase_* functions call the required milestone helpers.

    All network/DataLayer calls are patched so no real HTTP is performed.
    """

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
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        finder = self._actor("urn:test:finder")
        c1 = self._actor("urn:test:c1")
        c2 = self._actor("urn:test:c2")
        vendor = self._actor("urn:test:vendor")
        c1_in_c1 = self._actor("urn:test:c1")
        c2_in_c2 = self._actor("urn:test:c2")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        invite = MagicMock()
        invite.id_ = "urn:test:invite"
        case = self._case()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fccv",
                return_value=(finder, c1, c2, vendor),
            ),
            patch.object(
                demo, "get_actor_by_id", side_effect=[c1_in_c1, c2_in_c2]
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(demo, "receiver_validates_report"),
            patch.object(demo, "find_case_for_offer", return_value=case),
            patch.object(demo, "receiver_engages_case"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={"activity": {"id": invite.id_}},
            ),
            patch.object(demo, "post_to_inbox_and_wait"),
            patch.object(demo, "verify_object_stored"),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(demo, "run_invite_path_rm_triage"),
            patch.object(demo, "verify_case_active") as mock_m1,
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
            mock_ta.model_validate.return_value = invite
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                finder_id=None,
                c1_id=None,
                c2_id=None,
                vendor_id=None,
            )
        mock_m1.assert_called()

    def test_phase_fix_lifecycle_runs_vfd_checks(self):
        """_phase_fix_lifecycle advances vendor through fix-ready VFD states."""
        import contextlib

        c1_client = self._client()
        vendor_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()

        with (
            patch.object(demo, "actor_notifies_fix_ready") as mock_fix_ready,
            patch.object(
                demo, "wait_for_participant_vfd_state"
            ) as mock_wait_vfd,
            patch.object(
                demo, "_check_participant_vfd_state_in"
            ) as mock_check_vfd,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_fix_lifecycle(
                c1_client=c1_client,
                vendor_client=vendor_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
            )
        mock_fix_ready.assert_called()
        mock_wait_vfd.assert_called()
        mock_check_vfd.assert_called()

    def test_phase_publication_calls_verify_publicly_disclosed(self):
        """_phase_publication calls verify_publicly_disclosed at M7."""
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c1 = self._actor("urn:test:c1")
        c1_in_c1 = self._actor("urn:test:c1")
        c2_in_c2 = self._actor("urn:test:c2")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        finder_in_finder = self._actor("urn:test:finder")
        case = self._case()

        with (
            patch.object(demo, "actor_notifies_published"),
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_publicly_disclosed") as mock_m7,
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_publication(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c1=c1,
                c1_in_c1=c1_in_c1,
                c2_in_c2=c2_in_c2,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                finder_in_finder=finder_in_finder,
                case=case,
            )
        mock_m7.assert_called()

    def test_phase_case_closure_calls_verify_case_closed(self):
        """_phase_case_closure calls verify_case_closed at M8."""
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c1_in_c1 = self._actor("urn:test:c1")
        c2_in_c2 = self._actor("urn:test:c2")
        vendor_in_vendor = self._actor("urn:test:vendor")
        finder_in_finder = self._actor("urn:test:finder")
        case = self._case()
        case.id_ = "urn:test:case"
        c1_client.get.return_value = {
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
            patch.object(demo, "verify_case_closed") as mock_m8,
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
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c1_in_c1=c1_in_c1,
                c2_in_c2=c2_in_c2,
                vendor_in_vendor=vendor_in_vendor,
                finder_in_finder=finder_in_finder,
                case=case,
            )
        mock_m8.assert_called()
