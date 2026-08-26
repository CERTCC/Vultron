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

"""Unit tests for the FVCV-extension four-actor CVD demo (D5-6).

Uses a single TestClient (one FastAPI app instance) to simulate four containers.
All four DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fvcv-extension docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from unittest.mock import MagicMock, call, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fvcv_extension_demo as demo
from test.demo._helpers import make_client, make_testclient_call
from vultron.demo.cli import main

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
# Unit tests for seed_containers_fvcv
# ---------------------------------------------------------------------------


class TestSeedContainersFvcv:
    """Test that seeding creates actors on all four containers."""

    def test_seed_creates_all_four_actors(self, base: str):
        finder, vendor, coordinator, vendor2 = demo.seed_containers_fvcv(
            finder_client=make_client(base),
            vendor_client=make_client(base),
            coordinator_client=make_client(base),
            vendor2_client=make_client(base),
        )
        assert finder.id_ is not None
        assert finder.name == "Finder"
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"
        assert coordinator.id_ is not None
        assert coordinator.name == "Coordinator"
        assert vendor2.id_ is not None
        assert vendor2.name == "Vendor2"

    def test_seed_registers_cross_container_peers(self, base: str):
        finder_client = make_client(base)

        demo.seed_containers_fvcv(
            finder_client=finder_client,
            vendor_client=make_client(base),
            coordinator_client=make_client(base),
            vendor2_client=make_client(base),
        )

        actors = finder_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Finder" in actor_names
        assert "Vendor" in actor_names
        assert "Coordinator" in actor_names
        assert "Vendor2" in actor_names

    def test_seed_with_deterministic_ids(self, base: str):
        finder_id = f"{base}/actors/finder-fvcv-det-test"
        vendor_id = f"{base}/actors/vendor-fvcv-det-test"
        coordinator_id = f"{base}/actors/coordinator-fvcv-det-test"
        vendor2_id = f"{base}/actors/vendor2-fvcv-det-test"

        finder, vendor, coordinator, vendor2 = demo.seed_containers_fvcv(
            finder_client=make_client(base),
            vendor_client=make_client(base),
            coordinator_client=make_client(base),
            vendor2_client=make_client(base),
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
            coordinator_actor_id=coordinator_id,
            vendor2_actor_id=vendor2_id,
        )

        assert finder.id_ == finder_id
        assert vendor.id_ == vendor_id
        assert coordinator.id_ == coordinator_id
        assert vendor2.id_ == vendor2_id


# ---------------------------------------------------------------------------
# Unit tests for reset_containers
# ---------------------------------------------------------------------------


class TestResetContainersFvcv:
    """Test container reset orchestration for FVCV-extension scenario."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        finder_client = MagicMock()
        vendor_client = MagicMock()
        coordinator_client = MagicMock()
        vendor2_client = MagicMock()
        finder_client.get.return_value = {}
        vendor_client.get.return_value = {}
        coordinator_client.get.return_value = {}
        vendor2_client.get.return_value = {}

        with patch(
            "vultron.demo.scenario.fvcv_extension_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
            )

        reset_mock.assert_has_calls(
            [
                call(client=finder_client),
                call(client=vendor_client),
                call(client=coordinator_client),
                call(client=vendor2_client),
            ]
        )


# ---------------------------------------------------------------------------
# Invite-finder helper tests (ADR-0026 Vendor2 accept step)
# ---------------------------------------------------------------------------


class TestFindCaseInviteForActor:
    """Test the helper that locates the CaseActor's Invite for the invitee.

    In the ADR-0026 flow the CaseActor auto-delivers an Invite(Actor, Case) to
    the suggested actor; the demo must find it so it can drive Vendor2's
    accept-case-invite step (MV-10-004 seeds the replica only after Accept).
    """

    CASE_ID = "urn:uuid:case-1"
    INVITEE_ID = "http://vendor2:7999/api/v2/actors/v2"

    def _invite(self, target, obj):
        return {"type": "Invite", "target": target, "object": obj}

    def test_matches_invite_with_dict_target_and_object(self):
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-1": self._invite(
                {"id": self.CASE_ID}, {"id": self.INVITEE_ID}
            )
        }
        result = demo.find_case_invite_for_actor(
            client=client,
            case_id=self.CASE_ID,
            invitee_id=self.INVITEE_ID,
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-1"

    def test_matches_invite_with_bare_string_target_and_object(self):
        """Target/object may arrive as bare URI strings after wire round-trip."""
        client = MagicMock()
        client.get.return_value = {
            "urn:uuid:invite-2": self._invite(self.CASE_ID, self.INVITEE_ID)
        }
        result = demo.find_case_invite_for_actor(
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
            demo.find_case_invite_for_actor(
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
            demo.find_case_invite_for_actor(
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
            demo.find_case_invite_for_actor(
                client=client,
                case_id=self.CASE_ID,
                invitee_id=self.INVITEE_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


# ---------------------------------------------------------------------------
# Publication phase ordering tests
# ---------------------------------------------------------------------------


class TestPhasePublicationEmWaitOrdering:
    """Verify that wait_for_case_em_terminated is called on finder's client
    before actor_notifies_published is called for finder.

    Regression test for issue #1690: finder previously called notify-published
    before the EM teardown had propagated to its replica, producing an
    out-of-causal-order EM=ACTIVE ledger entry after embargo removal.
    """

    def _make_actor(self, id_: str = "urn:test:actor"):
        actor = MagicMock()
        actor.id_ = id_
        return actor

    def _make_client(self):
        return MagicMock()

    def test_finder_em_wait_precedes_finder_notify_published(self):
        """wait_for_case_em_terminated(finder) must be called before
        actor_notifies_published for finder.
        """
        case_id = "urn:test:case-1"
        call_log: list[str] = []

        finder_client = self._make_client()
        vendor_client = self._make_client()
        coordinator_client = self._make_client()
        vendor2_client = self._make_client()

        finder = self._make_actor("urn:test:finder")
        finder_in_finder = self._make_actor("urn:test:finder")
        vendor = self._make_actor("urn:test:vendor")
        vendor_in_vendor = self._make_actor("urn:test:vendor")
        vendor2 = self._make_actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._make_actor("urn:test:vendor2")
        coordinator = self._make_actor("urn:test:coordinator")
        coordinator_in_coordinator = self._make_actor("urn:test:coordinator")

        case = MagicMock()
        case.id_ = case_id

        def track_em_wait(client, case_id, **kwargs):
            if client is finder_client:
                call_log.append("em_wait_finder")

        def track_notify_published(client, actor, case_id, **kwargs):
            if client is finder_client:
                call_log.append("notify_published_finder")

        with (
            patch.object(
                demo,
                "wait_for_case_em_terminated",
                side_effect=track_em_wait,
            ),
            patch.object(
                demo,
                "actor_notifies_published",
                side_effect=track_notify_published,
            ),
            patch.object(demo, "verify_publicly_disclosed"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "demo_check"),
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

        assert (
            "em_wait_finder" in call_log
        ), "wait_for_case_em_terminated was not called for finder_client"
        assert (
            "notify_published_finder" in call_log
        ), "actor_notifies_published was not called for finder"
        em_idx = call_log.index("em_wait_finder")
        pub_idx = call_log.index("notify_published_finder")
        assert em_idx < pub_idx, (
            f"wait_for_case_em_terminated (pos {em_idx}) must precede "
            f"actor_notifies_published for finder (pos {pub_idx})"
        )


# ---------------------------------------------------------------------------
# CLI integration test
# ---------------------------------------------------------------------------


class TestFvcvExtensionCliCommand:
    """Test that the 'fvcv-extension' CLI sub-command is registered and reachable."""

    def test_fvcv_extension_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-extension", "--help"])
        assert result.exit_code == 0, result.output
        assert "Finder" in result.output or "fvcv" in result.output.lower()

    def test_fvcv_extension_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-extension", "--help"])
        assert "--skip-health-check" in result.output

    def test_fvcv_extension_command_vendor2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-extension", "--help"])
        assert "--vendor2-url" in result.output

    def test_fvcv_extension_command_coordinator_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fvcv-extension", "--help"])
        assert "--coordinator-url" in result.output


# ---------------------------------------------------------------------------
# Milestone assertion tests — AC-4 of ISSUE-1976
# ---------------------------------------------------------------------------


class TestFvcvExtensionMilestoneAssertions:
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
        invite = MagicMock()
        invite.id_ = "urn:test:invite"
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
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(
                demo,
                "post_to_trigger",
                return_value={"activity": {"id": invite.id_}},
            ),
            patch.object(demo, "find_case_invite_for_actor"),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
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
            mock_ta.model_validate.return_value = invite
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                finder_id=None,
                vendor_id=None,
                coordinator_id=None,
                vendor2_id=None,
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
            patch.object(demo, "wait_for_participant_rm_state"),
            patch.object(demo, "actor_notifies_fix_ready"),
            patch.object(demo, "wait_for_participant_vfd_state"),
            patch.object(demo, "verify_fix_ready") as mock_m4,
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
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
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
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
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
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

    def test_phase_case_closure_vendor1_closes_last(self):
        """Vendor1 (case owner) must close after Vendor2, Coordinator, and Finder."""
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
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_case_closure(
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

        actors_closed = [
            call.kwargs["actor"].id_ for call in mock_close.call_args_list
        ]
        assert (
            actors_closed[-1] == vendor_in_vendor.id_
        ), "Vendor1 (case owner) must close last; got order: " + str(
            actors_closed
        )
        assert actors_closed.index(finder_in_finder.id_) < actors_closed.index(
            vendor_in_vendor.id_
        ), "Finder must close before Vendor1"


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaWaitBeforeVendor2Triage:
    """CLP-08-005: Finder replica wait must precede invite-path RM triage in fvcv-extension."""

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

        sig = inspect.signature(demo._phase_coordinator_suggests_vendor2)
        assert "finder_client" in sig.parameters

    def test_finder_wait_before_vendor2_triage(self):
        import contextlib

        finder_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
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
            demo._phase_coordinator_suggests_vendor2(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                coordinator_in_coordinator=coordinator_in_coordinator,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
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
