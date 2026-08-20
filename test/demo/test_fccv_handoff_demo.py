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

"""Unit tests for the FCCV-handoff four-actor CVD demo (DEMOMA-14).

Uses a single TestClient (one FastAPI app instance) to simulate five containers.
All DataLayerClient instances route through the same TestClient but address
different actor namespaces via their respective actor IDs.

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=fccv-handoff docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import importlib
from unittest.mock import MagicMock, call, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fccv_handoff_demo as demo
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
# Unit tests for seed_containers_fccv
# ---------------------------------------------------------------------------


class TestSeedContainersFccv:
    """Test that seeding creates actors on all four containers."""

    def test_seed_creates_all_four_actors(self, base: str):
        from vultron.demo.helpers.seeding import seed_containers_fccv

        finder, c1, c2, vendor = seed_containers_fccv(
            finder_client=make_client(base),
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
        )
        assert finder.id_ is not None
        assert finder.name == "Finder"
        assert c1.id_ is not None
        assert c1.name == "Coordinator1"
        assert c2.id_ is not None
        assert c2.name == "Coordinator2"
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_registers_cross_container_peers(self, base: str):
        from vultron.demo.helpers.seeding import seed_containers_fccv

        finder_client = make_client(base)

        seed_containers_fccv(
            finder_client=finder_client,
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
        )

        actors = finder_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Finder" in actor_names
        assert "Coordinator1" in actor_names
        assert "Coordinator2" in actor_names
        assert "Vendor" in actor_names

    def test_seed_with_deterministic_ids(self, base: str):
        from vultron.demo.helpers.seeding import seed_containers_fccv

        finder_id = f"{base}/actors/finder-fccv-det-test"
        c1_id = f"{base}/actors/c1-fccv-det-test"
        c2_id = f"{base}/actors/c2-fccv-det-test"
        vendor_id = f"{base}/actors/vendor-fccv-det-test"

        finder, c1, c2, vendor = seed_containers_fccv(
            finder_client=make_client(base),
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
            reporter_actor_id=finder_id,
            c1_actor_id=c1_id,
            c2_actor_id=c2_id,
            vendor_actor_id=vendor_id,
        )

        assert finder.id_ == finder_id
        assert c1.id_ == c1_id
        assert c2.id_ == c2_id
        assert vendor.id_ == vendor_id


# ---------------------------------------------------------------------------
# Unit tests for reset_containers
# ---------------------------------------------------------------------------


class TestResetContainersFccv:
    """Test container reset orchestration for FCCV-handoff scenario."""

    def test_reset_containers_calls_reset_for_all_targets(self):
        finder_client = MagicMock()
        c1_client = MagicMock()
        c2_client = MagicMock()
        case_actor_client = MagicMock()
        vendor_client = MagicMock()
        finder_client.get.return_value = {}
        c1_client.get.return_value = {}
        c2_client.get.return_value = {}
        case_actor_client.get.return_value = {}
        vendor_client.get.return_value = {}

        with patch(
            "vultron.demo.scenario.fccv_handoff_demo.reset_datalayer",
            return_value={"status": "ok"},
        ) as reset_mock:
            demo.reset_containers(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                case_actor_client=case_actor_client,
                vendor_client=vendor_client,
            )

        reset_mock.assert_has_calls(
            [
                call(client=finder_client),
                call(client=c1_client),
                call(client=c2_client),
                call(client=case_actor_client),
                call(client=vendor_client),
            ]
        )


# ---------------------------------------------------------------------------
# Unit tests for _wait_for_case_attributed_to
# ---------------------------------------------------------------------------


class TestWaitForCaseAttributedTo:
    """Test the polling helper that waits for case attributed_to to match."""

    def test_returns_immediately_when_attributed_to_matches(self):
        client = MagicMock()
        client.get.return_value = {
            "attributedTo": {"id": "http://c2/actors/c2"}
        }
        demo._wait_for_case_attributed_to(
            client=client,
            case_id="urn:uuid:case-1",
            expected_attributed_to="http://c2/actors/c2",
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1

    def test_raises_on_timeout_when_attributed_to_never_matches(self):
        client = MagicMock()
        client.get.return_value = {
            "attributedTo": {"id": "http://c1/actors/c1"}
        }
        with pytest.raises(AssertionError, match="Timed out waiting"):
            demo._wait_for_case_attributed_to(
                client=client,
                case_id="urn:uuid:case-1",
                expected_attributed_to="http://c2/actors/c2",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_accepts_bare_string_attributed_to(self):
        client = MagicMock()
        client.get.return_value = {"attributedTo": "http://c2/actors/c2"}
        demo._wait_for_case_attributed_to(
            client=client,
            case_id="urn:uuid:case-1",
            expected_attributed_to="http://c2/actors/c2",
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1


# ---------------------------------------------------------------------------
# wait_for_object_stored tests
# ---------------------------------------------------------------------------


class TestWaitForObjectStored:
    """Test the polling helper that waits for an arbitrary object in a DataLayer."""

    OBJ_ID = "urn:uuid:offer-abc"

    def test_returns_when_object_present(self):
        from vultron.demo.helpers.polling import wait_for_object_stored

        client = MagicMock()
        client.get.return_value = {"id": self.OBJ_ID, "type": "Offer"}
        client.dl_path.side_effect = (
            lambda key="": f"/actors/an-actor/datalayer/{key}"
        )
        wait_for_object_stored(
            client=client,
            obj_id=self.OBJ_ID,
            timeout_seconds=1.0,
        )
        # The read must be actor-scoped, and must ask the client to build the
        # path rather than hand-writing it (ADR-0066): a MagicMock would happily
        # accept any string, so assert the delegation too.
        client.dl_path.assert_called_with(self.OBJ_ID)
        client.get.assert_called_with(client.dl_path(self.OBJ_ID))

    def test_raises_on_timeout_when_object_absent(self):
        from vultron.demo.helpers.polling import wait_for_object_stored

        client = MagicMock()
        client.get.return_value = None
        with pytest.raises(AssertionError, match="Timed out waiting"):
            wait_for_object_stored(
                client=client,
                obj_id=self.OBJ_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_raises_on_timeout_when_object_returns_empty_dict(self):
        from vultron.demo.helpers.polling import wait_for_object_stored

        client = MagicMock()
        client.get.return_value = {}
        with pytest.raises(AssertionError, match="Timed out waiting"):
            wait_for_object_stored(
                client=client,
                obj_id=self.OBJ_ID,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_swallows_get_exception_and_retries(self):
        from vultron.demo.helpers.polling import wait_for_object_stored

        client = MagicMock()
        client.get.side_effect = [
            RuntimeError("transient network error"),
            {"id": self.OBJ_ID, "type": "Offer"},
        ]
        wait_for_object_stored(
            client=client,
            obj_id=self.OBJ_ID,
            timeout_seconds=1.0,
        )
        assert client.get.call_count == 2


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestFccvHandoffCliCommand:
    """Test that the 'fccv-handoff' CLI sub-command is registered and reachable."""

    def test_fccv_handoff_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert result.exit_code == 0, result.output
        assert "Finder" in result.output or "fccv" in result.output.lower()

    def test_fccv_handoff_command_finder_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--finder-url" in result.output

    def test_fccv_handoff_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--skip-health-check" in result.output

    def test_fccv_handoff_command_c1_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--c1-url" in result.output

    def test_fccv_handoff_command_c2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--c2-url" in result.output

    def test_fccv_handoff_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--vendor-url" in result.output

    def test_fccv_handoff_command_case_actor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["fccv-handoff", "--help"])
        assert "--case-actor-url" in result.output


# ---------------------------------------------------------------------------
# Unit tests for _phase_dump_case_ledgers
# ---------------------------------------------------------------------------


class TestPhaseDumpCaseLedgersFccv:
    """Tests for the case-ledger dump phase in the FCCV-handoff demo."""

    def test_writes_jsonl_files_for_all_four_actors(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        c1_client = MagicMock()
        c2_client = MagicMock()
        vendor_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        c1_client.get_list.return_value = [{"logIndex": 0}]
        c2_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/fccv-test-case"
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            c1_client=c1_client,
            c2_client=c2_client,
            vendor_client=vendor_client,
            case=case,
        )

        case_slug = "https_example.org_cases_fccv-test-case"
        assert (
            tmp_path
            / "fccv-handoff"
            / "finder"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fccv-handoff"
            / "vendor"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fccv-handoff"
            / "coordinator"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "fccv-handoff"
            / "vendor2"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()

    def test_includes_case_actor_when_in_participant_index(
        self, tmp_path, monkeypatch
    ):
        finder_client = MagicMock()
        c1_client = MagicMock()
        c2_client = MagicMock()
        vendor_client = MagicMock()
        finder_client.get_list.return_value = [{"logIndex": 0}]
        c1_client.get_list.return_value = [{"logIndex": 0}]
        c2_client.get_list.return_value = [{"logIndex": 0}]
        vendor_client.get_list.return_value = [{"logIndex": 0}]

        case = demo.as_VulnerabilityCase(
            id_="https://example.org/cases/fccv-with-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor-fccv": (
                    "https://example.org/cases/fccv-with-ca/participants/case-actor"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            finder_client=finder_client,
            c1_client=c1_client,
            c2_client=c2_client,
            vendor_client=vendor_client,
            case=case,
        )

        assert any(
            "/actors/case-actor-fccv/demo/cases/fccv-with-ca/log"
            in call.args[0]
            for call in c1_client.get_list.call_args_list
        )


# ---------------------------------------------------------------------------
# Milestone assertion tests — AC-4 of ISSUE-1976
# ---------------------------------------------------------------------------


class TestFccvHandoffMilestoneAssertions:
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
        """_phase_report_submission calls verify_case_active (via run_fccv_handoff_demo).

        The _phase_report_submission function itself does not call verify_case_active;
        the M1 check is done in run_fccv_handoff_demo after all participants join.
        This test verifies the phase runs without error and returns a case.
        """
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        case_actor_client = self._client()
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
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
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
            result = demo._phase_report_submission(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                case_actor_client=case_actor_client,
                vendor_client=vendor_client,
                finder_id=None,
                c1_id=None,
                c2_id=None,
                vendor_id=None,
            )
        assert result is not None

    def test_run_fccv_handoff_calls_verify_case_active(self):
        """run_fccv_handoff_demo calls verify_case_active at M1."""
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        case_actor_client = self._client()
        vendor_client = self._client()

        with (
            patch.object(
                demo,
                "_phase_report_submission",
                return_value=(
                    self._actor("f"),
                    self._actor("c1"),
                    self._actor("c1_c1"),
                    self._actor("c2"),
                    self._actor("c2_c2"),
                    self._actor("v"),
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
            patch.object(demo, "_phase_c2_invites_vendor"),
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
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo.run_fccv_handoff_demo(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                case_actor_client=case_actor_client,
                vendor_client=vendor_client,
            )
        mock_m1.assert_called()

    def test_phase_fix_lifecycle_calls_verify_fix_ready(self):
        """_phase_fix_lifecycle calls verify_fix_ready at M4/M5."""
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        vendor_client = self._client()
        c1 = self._actor("urn:test:c1")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()

        with (
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
                c1_client=c1_client,
                vendor_client=vendor_client,
                c1=c1,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
            )
        mock_m4.assert_called()

    def test_phase_publication_calls_verify_publicly_disclosed(self):
        """_phase_publication calls verify_publicly_disclosed at M6."""
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c1 = self._actor("urn:test:c1")
        c1_in_c1 = self._actor("urn:test:c1")
        c2 = self._actor("urn:test:c2")
        c2_in_c2 = self._actor("urn:test:c2")
        finder = self._actor("urn:test:finder")
        finder_in_finder = self._actor("urn:test:finder")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
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
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c1=c1,
                c1_in_c1=c1_in_c1,
                c2=c2,
                c2_in_c2=c2_in_c2,
                finder=finder,
                finder_in_finder=finder_in_finder,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
            )
        mock_m6.assert_called()

    def test_phase_case_closure_calls_verify_case_closed(self):
        """_phase_case_closure calls verify_case_closed at M7."""
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c1 = self._actor("urn:test:c1")
        c1_in_c1 = self._actor("urn:test:c1")
        c2 = self._actor("urn:test:c2")
        c2_in_c2 = self._actor("urn:test:c2")
        finder = self._actor("urn:test:finder")
        finder_in_finder = self._actor("urn:test:finder")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()
        case.id_ = "urn:test:case"
        c2_client.get.return_value = {
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
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c1=c1,
                c1_in_c1=c1_in_c1,
                c2=c2,
                c2_in_c2=c2_in_c2,
                finder=finder,
                finder_in_finder=finder_in_finder,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                case=case,
            )
        mock_m7.assert_called()

    def test_phase_case_closure_c2_closes_last(self):
        """C2 (case owner post-handoff) must close after C1, Vendor, and Finder."""
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c1_in_c1 = self._actor("urn:test:c1")
        c2_in_c2 = self._actor("urn:test:c2")
        finder_in_finder = self._actor("urn:test:finder")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()
        case.id_ = "urn:test:case"
        c2_client.get.return_value = {
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
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c1=self._actor("urn:test:c1"),
                c1_in_c1=c1_in_c1,
                c2=self._actor("urn:test:c2"),
                c2_in_c2=c2_in_c2,
                finder=self._actor("urn:test:finder"),
                finder_in_finder=finder_in_finder,
                vendor=self._actor("urn:test:vendor"),
                vendor_in_vendor=vendor_in_vendor,
                case=case,
            )

        actors_closed = [
            call.kwargs["actor"].id_ for call in mock_close.call_args_list
        ]
        assert (
            actors_closed[-1] == c2_in_c2.id_
        ), "C2 (case owner post-handoff) must close last; got order: " + str(
            actors_closed
        )
        assert actors_closed.index(finder_in_finder.id_) < actors_closed.index(
            c2_in_c2.id_
        ), "Finder must close before C2"


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaWaitBeforeVendorTriage:
    """CLP-08-005: Finder replica wait must precede invite-path RM triage in fccv-handoff."""

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

        sig = inspect.signature(demo._phase_c2_invites_vendor)
        assert "finder_client" in sig.parameters

    def test_finder_wait_before_vendor_triage(self):
        import contextlib

        finder_client = self._client()
        c1_client = self._client()
        c2_client = self._client()
        vendor_client = self._client()
        c2 = self._actor("urn:test:c2")
        c2_in_c2 = self._actor("urn:test:c2")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        case = self._case()
        offer = MagicMock()
        report = MagicMock()
        finder = self._actor("urn:test:finder")
        invite = MagicMock()
        invite.id_ = "urn:test:invite"

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
                return_value={"activity": {"id": invite.id_}},
            ),
            patch.object(demo, "find_case_invite_for_actor"),
            patch.object(demo, "wait_for_case_participants"),
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
            mock_ta.model_validate.return_value = invite
            demo._phase_c2_invites_vendor(
                finder_client=finder_client,
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                c2=c2,
                c2_in_c2=c2_in_c2,
                case_actor_id="urn:test:case-actor",
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
