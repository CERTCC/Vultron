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
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={"activity": {"id": invite.id_}},
            ),
            patch.object(demo, "post_to_inbox_and_wait"),
            patch.object(demo, "verify_object_stored"),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(demo, "run_invite_path_rm_triage"),
            patch.object(demo, "verify_case_active") as mock_m1,
            patch.object(
                demo,
                "demo_gate",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
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
            patch.object(demo, "wait_for_participant_rm_state"),
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

    def test_phase_fix_lifecycle_gates_on_rm_accepted(self):
        """_phase_fix_lifecycle polls vendor RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (ADR-0058/CSB-18-001)."""
        from vultron.core.states.rm import RM

        c1_client = self._client()
        vendor_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()

        call_order = []
        rm_calls = []

        def _rm_wait(*a, **kw):
            rm_calls.append(kw)
            call_order.append("rm_wait")

        with (
            patch.object(demo, "wait_for_participant_rm_state", _rm_wait),
            patch.object(
                demo,
                "actor_notifies_fix_ready",
                side_effect=lambda *a, **kw: call_order.append("fix_ready"),
            ),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "_check_participant_vfd_state_in"),
        ):
            demo._phase_fix_lifecycle(
                c1_client=c1_client,
                vendor_client=vendor_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
            )

        assert (
            rm_calls
        ), "wait_for_participant_rm_state must be called (ADR-0058/CSB-18-001)"
        assert all(
            c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), "expected_states must be {ACCEPTED, DEFERRED, CLOSED} (CSB-18-001)"
        assert "rm_wait" in call_order and "fix_ready" in call_order
        assert call_order.index("rm_wait") < call_order.index(
            "fix_ready"
        ), "wait_for_participant_rm_state must precede actor_notifies_fix_ready (ADR-0058)"

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


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaWaitBeforeVendorTriage:
    """CLP-08-005: Finder replica wait must precede invite-path RM triage in fccv-extension."""

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

    def test_finder_client_in_signature(self):
        import inspect

        sig = inspect.signature(demo._phase_c2_suggests_vendor)
        assert "finder_client" in sig.parameters

    def test_finder_wait_before_vendor_triage(self):
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c1_in_c1 = self._actor("urn:test:c1")
        c2_in_c2 = self._actor("urn:test:c2")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()
        offer = MagicMock()
        report = MagicMock()
        finder = self._actor("urn:test:finder")

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kw):
            if client is finder_client:
                call_order.append("finder_wait")

        def _triage(**_kw):
            call_order.append("triage")

        with (
            patch.object(
                demo,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            patch.object(
                demo, "run_invite_path_rm_triage", side_effect=_triage
            ),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={"activity": {"id": "urn:test:activity"}},
            ),
            patch.object(
                demo, "find_cp_offer_for_case", return_value="urn:test:offer"
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor",
            ),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
            patch.object(demo, "wait_for_case_participants"),
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
            demo._phase_c2_suggests_vendor(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c1_in_c1=c1_in_c1,
                c2_in_c2=c2_in_c2,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
                offer=offer,
                report=report,
                finder=finder,
            )

        assert (
            "finder_wait" in call_order
        ), "wait_for_case_on_container(finder_client) never called"
        assert "triage" in call_order, "run_invite_path_rm_triage never called"
        finder_idx = next(
            i for i, v in enumerate(call_order) if v == "finder_wait"
        )
        triage_idx = next(i for i, v in enumerate(call_order) if v == "triage")
        assert finder_idx < triage_idx, (
            "Finder replica wait must precede run_invite_path_rm_triage; "
            f"got order: {call_order}"
        )


class TestFccvExtensionCausalGates:
    """Verify causal demo_gate sites skip dependent steps on timeout.

    Each test simulates an async-commit timeout at the precondition and
    confirms the dependent step is never reached.
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

    def test_sync_verification_skips_coverage_wait_when_finder_case_not_seeded(
        self,
    ):
        """demo_gate skips ledger coverage wait when wait_for_case_on_container times out."""
        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c1 = self._actor("urn:test:c1")
        finder = self._actor("urn:test:finder")
        c2_in_c2 = self._actor("urn:test:c2")
        vendor = self._actor("urn:test:vendor")
        case = self._case()

        coverage_wait_called = MagicMock()

        with (
            patch.object(
                demo,
                "_get_log_entries_for_case",
                return_value=[
                    {"log_index": 5, "entry_hash": "abc123def456789a"}
                ],
            ),
            patch.object(
                demo,
                "wait_for_case_on_container",
                side_effect=AssertionError(
                    "timed out waiting for case on container"
                ),
            ),
            patch.object(
                demo,
                "wait_for_contiguous_ledger_coverage",
                side_effect=coverage_wait_called,
            ),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "verify_replica_state"),
        ):
            demo._phase_sync_verification(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c1=c1,
                finder=finder,
                case=case,
                c2_in_c2=c2_in_c2,
                vendor=vendor,
            )

        coverage_wait_called.assert_not_called()

    def test_accept_not_called_when_cp_offer_gate_fails(self):
        """demo_gate skips accept-actor-recommendation when find_cp_offer_for_case times out."""
        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c1_in_c1 = self._actor("urn:test:c1-in-c1")
        c2_in_c2 = self._actor("urn:test:c2-in-c2")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor-in-vendor")
        finder = self._actor("urn:test:finder")
        case = self._case()

        mock_post_to_trigger = MagicMock()

        with (
            patch.object(
                demo,
                "find_cp_offer_for_case",
                side_effect=AssertionError(
                    "timed out polling for Offer(CaseParticipant)"
                ),
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor",
            ),
            patch.object(demo, "post_to_trigger", mock_post_to_trigger),
            patch.object(
                demo,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "run_invite_path_rm_triage"),
        ):
            demo._phase_c2_suggests_vendor(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c1_in_c1=c1_in_c1,
                c2_in_c2=c2_in_c2,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
                offer=MagicMock(),
                report=MagicMock(),
                finder=finder,
            )

        accept_calls = [
            c
            for c in mock_post_to_trigger.call_args_list
            if c.kwargs.get("behavior") == "accept-actor-recommendation"
        ]
        assert not accept_calls, (
            "accept-actor-recommendation must not be called when "
            f"cp_offer gate fails: {accept_calls}"
        )
