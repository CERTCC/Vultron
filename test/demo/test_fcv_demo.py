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

"""Unit tests for the FCV three-actor CVD demo (DEMOMA-12).

Uses a single TestClient (one FastAPI app instance) to simulate three containers.
All three DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fcv docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from unittest.mock import MagicMock, call, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fcv_demo as demo
from test.demo._helpers import make_client, make_testclient_call
from vultron.demo.cli import main
from vultron.demo.helpers.polling import find_case_invite_for_actor

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    """Return the base URL for the single TestClient, matching /api/v2 prefix."""
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
    """Patch DataLayerClient.call at the class level for all tests in this module."""
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
# Unit tests for seed_containers_fcv
# ---------------------------------------------------------------------------


class TestSeedContainersFcv:
    """Test that seeding creates actors on all three containers."""

    def test_seed_creates_all_three_actors(self, base: str):
        finder, coordinator, vendor = demo.seed_containers_fcv(
            finder_client=make_client(base),
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
        )
        assert finder.id_ is not None
        assert finder.name == "Finder"
        assert coordinator.id_ is not None
        assert coordinator.name == "Coordinator"
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_registers_cross_container_peers(self, base: str):
        finder_client = make_client(base)

        demo.seed_containers_fcv(
            finder_client=finder_client,
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
        )

        actors = finder_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Finder" in actor_names
        assert "Coordinator" in actor_names
        assert "Vendor" in actor_names

    def test_seed_with_deterministic_ids(self, base: str):
        finder_id = f"{base}/actors/finder-fcv-det-test"
        coordinator_id = f"{base}/actors/coordinator-fcv-det-test"
        vendor_id = f"{base}/actors/vendor-fcv-det-test"

        finder, coordinator, vendor = demo.seed_containers_fcv(
            finder_client=make_client(base),
            coordinator_client=make_client(base),
            vendor_client=make_client(base),
            reporter_actor_id=finder_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
        )

        assert finder.id_ == finder_id
        assert coordinator.id_ == coordinator_id
        assert vendor.id_ == vendor_id


# ---------------------------------------------------------------------------
# Unit tests for reset_containers
# ---------------------------------------------------------------------------


class TestResetContainersFcv:
    """Test container reset orchestration for FCV scenario."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        finder_client = MagicMock()
        coordinator_client = MagicMock()
        vendor_client = MagicMock()
        finder_client.get.return_value = {}
        coordinator_client.get.return_value = {}
        vendor_client.get.return_value = {}

        with patch(
            "vultron.demo.scenario.fcv_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
            )

        reset_mock.assert_has_calls(
            [
                call(client=finder_client, init=False),
                call(client=coordinator_client, init=False),
                call(client=vendor_client, init=False),
            ]
        )

    def test_reset_includes_case_actor_when_provided(self):
        finder_client = MagicMock()
        coordinator_client = MagicMock()
        vendor_client = MagicMock()
        case_actor_client = MagicMock()

        with patch(
            "vultron.demo.scenario.fcv_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
            )

        called_clients = [
            c.kwargs["client"] for c in reset_mock.call_args_list
        ]
        assert case_actor_client in called_clients


# ---------------------------------------------------------------------------
# find_case_invite_for_actor tests
# ---------------------------------------------------------------------------


class TestFindCaseInviteForActor:
    """Test the shared polling helper that locates the CaseActor Invite for the invitee."""

    CASE_ID = "urn:uuid:case-1"
    INVITEE_ID = "http://vendor:7999/api/v2/actors/vendor"

    def _invite(self, target, obj):
        return {"type": "Invite", "target": target, "object": obj}

    def test_matches_invite_with_dict_target_and_object(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-1": self._invite(
                {"id": self.CASE_ID}, {"id": self.INVITEE_ID}
            )
        }
        result = find_case_invite_for_actor(
            client=client,
            case_id=self.CASE_ID,
            invitee_id=self.INVITEE_ID,
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-1"

    def test_matches_invite_with_bare_string_target_and_object(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-2": self._invite(self.CASE_ID, self.INVITEE_ID)
        }
        result = find_case_invite_for_actor(
            client=client,
            case_id=self.CASE_ID,
            invitee_id=self.INVITEE_ID,
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-2"

    def test_ignores_invite_for_other_case(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-3": self._invite(
                {"id": "urn:uuid:other-case"}, {"id": self.INVITEE_ID}
            )
        }
        with pytest.raises(AssertionError, match="Timed out waiting"):
            find_case_invite_for_actor(
                client=client,
                case_id=self.CASE_ID,
                invitee_id=self.INVITEE_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_ignores_invite_for_other_actor(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-4": self._invite(
                {"id": self.CASE_ID}, {"id": "http://elsewhere/actors/x"}
            )
        }
        with pytest.raises(AssertionError, match="Timed out waiting"):
            find_case_invite_for_actor(
                client=client,
                case_id=self.CASE_ID,
                invitee_id=self.INVITEE_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_ignores_non_invite_activities(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:offer-1": {
                "type": "Offer",
                "target": {"id": self.CASE_ID},
                "object": {"id": self.INVITEE_ID},
            }
        }
        with pytest.raises(AssertionError, match="Timed out waiting"):
            find_case_invite_for_actor(
                client=client,
                case_id=self.CASE_ID,
                invitee_id=self.INVITEE_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestFcvCliCommand:
    """Test that the 'fcv' CLI sub-command is registered and reachable."""

    def test_fcv_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert result.exit_code == 0, result.output

    def test_fcv_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--skip-health-check" in result.output

    def test_fcv_command_finder_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--finder-url" in result.output

    def test_fcv_command_coordinator_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--coordinator-url" in result.output

    def test_fcv_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--vendor-url" in result.output

    def test_fcv_command_finder_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--finder-id" in result.output

    def test_fcv_command_coordinator_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--coordinator-id" in result.output

    def test_fcv_command_vendor_id_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fcv", "--help"])
        assert "--vendor-id" in result.output


# ---------------------------------------------------------------------------
# Milestone assertion tests — AC-4 of ISSUE-1976
# ---------------------------------------------------------------------------


class TestFcvMilestoneAssertions:
    """Verify that _phase_* functions call the required milestone helpers.

    Each test patches the milestone function to a Mock and asserts it was
    called during the relevant phase, confirming phase-boundary assertions
    are wired in.  All network/DataLayer calls are patched so no real HTTP
    is performed.
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
        coordinator_client = self._client()
        vendor_client = self._client()
        finder = self._actor("urn:test:finder")
        coordinator = self._actor("urn:test:coordinator")
        vendor = self._actor("urn:test:vendor")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        case = self._case()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_fcv",
                return_value=(finder, coordinator, vendor),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=coordinator_in_coordinator,
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(demo, "run_invite_path_rm_triage"),
            patch.object(demo, "verify_case_active") as mock_m1,
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                case_actor_client=None,
                finder_id=None,
                coordinator_id=None,
                vendor_id=None,
            )
        mock_m1.assert_called_once()

    def test_phase_fix_lifecycle_calls_verify_fix_ready(self):
        """_phase_fix_lifecycle calls verify_fix_ready at M5."""
        import contextlib

        coordinator_client = self._client()
        vendor_client = self._client()
        coordinator = self._actor("urn:test:coordinator")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()

        with (
            patch.object(demo, "actor_notifies_fix_ready"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_fix_ready") as mock_m5,
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_fix_lifecycle(
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                coordinator=coordinator,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
            )
        mock_m5.assert_called()

    def test_phase_publication_calls_verify_publicly_disclosed(self):
        """_phase_publication calls verify_publicly_disclosed at M6."""
        import contextlib

        coordinator_client = self._client()
        vendor_client = self._client()
        finder_client = self._client()
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        vendor_in_vendor = self._actor("urn:test:vendor")
        finder_in_finder = self._actor("urn:test:finder")
        case = self._case()

        with (
            patch.object(demo, "actor_notifies_published"),
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_publicly_disclosed") as mock_m6,
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_publication(
                finder_client=finder_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                vendor_in_vendor=vendor_in_vendor,
                finder_in_finder=finder_in_finder,
                case=case,
            )
        mock_m6.assert_called()

    def test_phase_case_closure_calls_verify_case_closed(self):
        """_phase_case_closure calls verify_case_closed at M7."""
        import contextlib

        coordinator_client = self._client()
        vendor_client = self._client()
        finder_client = self._client()
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        vendor_in_vendor = self._actor("urn:test:vendor")
        finder_in_finder = self._actor("urn:test:finder")
        case = self._case()
        case.id_ = "urn:test:case"
        coordinator_client.get.return_value = {
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
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_case_closure(
                finder_client=finder_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                coordinator_in_coordinator=coordinator_in_coordinator,
                vendor_in_vendor=vendor_in_vendor,
                finder_in_finder=finder_in_finder,
                case=case,
            )
        mock_m7.assert_called()


# ---------------------------------------------------------------------------
# Regression tests for Bug #2135: CLP-08-005 unanchored chain bootstrap
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaWaitBeforeVendorTriage:
    """_phase_invite_vendor must confirm the Finder has the case replica
    before calling run_invite_path_rm_triage for Vendor (Bug #2135).

    Vendor's RM triage broadcasts Announce(CaseLedgerEntry) to all
    participants including the Finder.  If the Finder's DataLayer does not
    yet hold the VulnerabilityCase (genesis hash unavailable), the chain
    bootstrap fails with CLP-08-005.
    """

    @staticmethod
    def _actor(id_: str = "urn:test:actor"):
        a = MagicMock()
        a.id_ = id_
        return a

    @staticmethod
    def _case(id_: str = "urn:test:case"):
        c = MagicMock()
        c.id_ = id_
        return c

    @staticmethod
    def _client():
        c = MagicMock()
        c.get.return_value = {}
        return c

    def test_finder_client_in_signature(self):
        """_phase_invite_vendor must accept finder_client as a parameter."""
        import inspect

        sig = inspect.signature(demo._phase_invite_vendor)
        assert "finder_client" in sig.parameters, (
            "_phase_invite_vendor must accept finder_client to gate Vendor RM "
            "triage on the Finder having the case replica (Bug #2135)"
        )

    def test_finder_wait_before_vendor_triage(self):
        """wait_for_case_on_container(finder_client) precedes run_invite_path_rm_triage."""
        import contextlib

        finder_client = self._client()
        coordinator_client = self._client()
        vendor_client = self._client()
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        finder = self._actor("urn:test:finder")
        case = self._case("urn:test:case")

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is finder_client:
                call_order.append("finder_wait")

        def _triage(**_kwargs):
            call_order.append("triage")

        with (
            patch.object(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch.object(
                demo, "run_invite_path_rm_triage", side_effect=_triage
            ),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={
                    "activity": {"id": "urn:test:act", "type": "Offer"}
                },
            ),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "find_case_invite_for_actor"),
            patch.object(
                demo, "get_actor_by_id", return_value=vendor_in_vendor
            ),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_ta.model_validate.return_value = MagicMock(
                id_="urn:test:invite"
            )
            demo._phase_invite_vendor(
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                finder_client=finder_client,
                coordinator_in_coordinator=coordinator_in_coordinator,
                vendor=vendor,
                case=case,
                offer=MagicMock(id_="urn:test:offer"),
                report=MagicMock(),
                finder=finder,
            )

        assert (
            "finder_wait" in call_order
        ), "wait_for_case_on_container(finder_client) was never called before Vendor triage"
        assert (
            "triage" in call_order
        ), "run_invite_path_rm_triage was never called"
        finder_idx = next(
            i for i, v in enumerate(call_order) if v == "finder_wait"
        )
        triage_idx = next(i for i, v in enumerate(call_order) if v == "triage")
        assert finder_idx < triage_idx, (
            f"Finder case-replica wait (index {finder_idx}) must come BEFORE "
            f"run_invite_path_rm_triage (index {triage_idx}). "
            f"Call order: {call_order} — Bug #2135 (CLP-08-005)"
        )
