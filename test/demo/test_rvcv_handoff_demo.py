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

"""Unit tests for the RVCV-handoff five-actor CVD demo (DEMOMA-15).

True multi-container isolation is validated by the acceptance test runnable via:
    DEMO=rvcv-handoff docker compose -f docker/docker-compose-multi-actor.yml up --abort-on-container-exit
"""

import contextlib
import importlib
import json
from collections.abc import Iterator
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.rvcv_handoff_demo as demo
from test.demo._helpers import (
    make_testclient_call,
    patch_chain_shared,
    stub_closure_gate,
)
from test.demo.conftest import (
    IsolatedActorApp,
    _TestClientRouter,
    create_isolated_actor_app,
)
from test.support.case_owner import CASE_OWNER_ID
from test.support.received import received_of_type
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main
from vultron.demo.helpers import invite_chain


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


def _bound_client(slug: str) -> MagicMock:
    """A dump client stub bound to a *generated* actor id, as the real one is.

    ``actor_id`` must be a real string: the dump derives its route key from it
    (``replica_route_key``, ADR-0073) and writes the key into the manifest, so a
    bare ``MagicMock()`` leaves an unserialisable object there.  The ids are
    deliberately *not* the docker-compose seed names — that is the whole point of
    deriving the key, and a stub carrying ``actor_id="reporter"`` would pass even if
    the derivation were dropped.
    """
    client = MagicMock()
    client.actor_id = f"https://example.org/actors/{slug}"
    client.get_list.return_value = [{"logIndex": 0}]
    return client


class TestPhaseDumpCaseLedgersRvcv:
    """Tests for the case-ledger dump phase in the RVCV-handoff demo."""

    def test_writes_jsonl_files_for_all_four_actors(
        self, tmp_path, monkeypatch
    ):
        reporter_client = _bound_client("reporter-9f3a")
        vendor_client = _bound_client("vendor-2b71")
        coordinator_client = _bound_client("coordinator-4c05")
        vendor2_client = _bound_client("vendor2-8ade")
        case_actor_client = _bound_client("case-actor")

        case = demo.as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvcv-test-case",
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            case_actor_client=case_actor_client,
            case=case,
        )

        case_slug = "https_example.org_cases_rvcv-test-case"
        assert (
            tmp_path
            / "rvcv-handoff"
            / "reporter"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "rvcv-handoff"
            / "vendor"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "rvcv-handoff"
            / "coordinator"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()
        assert (
            tmp_path
            / "rvcv-handoff"
            / "vendor2"
            / f"{case_slug}-case-ledger.jsonl"
        ).exists()

        # The route key selects the store (ADR-0073), so it must be the client's
        # own actor id — not the seed name the output directory is named after.
        manifest = json.loads(
            (tmp_path / "rvcv-handoff" / "dump-manifest.json").read_text()
        )
        keys = {r["actorName"]: r["routeKey"] for r in manifest["actors"]}
        assert keys == {
            "reporter": "reporter-9f3a",
            "vendor": "vendor-2b71",
            "coordinator": "coordinator-4c05",
            "vendor2": "vendor2-8ade",
            "case-actor": "case-actor",
        }

    def test_reads_case_actor_ledger_from_dedicated_container(
        self, tmp_path, monkeypatch
    ):
        """The canonical ledger comes from the case-actor container (DEMOMA-06-005).

        Never from Vendor1's container: the CaseActor is not hosted there, and
        Vendor1's replica is not the canonical ledger.
        """
        reporter_client = _bound_client("reporter-9f3a")
        vendor_client = _bound_client("vendor-2b71")
        coordinator_client = _bound_client("coordinator-4c05")
        vendor2_client = _bound_client("vendor2-8ade")
        case_actor_client = _bound_client("case-actor")

        case = demo.as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvcv-with-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor": (
                    "https://example.org/cases/rvcv-with-ca/participants/case-actor"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._phase_dump_case_ledgers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            case_actor_client=case_actor_client,
            case=case,
        )

        log_path = "/actors/case-actor/demo/cases/rvcv-with-ca/log"
        assert any(
            log_path in call.args[0]
            for call in case_actor_client.get_list.call_args_list
        )
        assert not any(
            log_path in call.args[0]
            for call in vendor_client.get_list.call_args_list
        )


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestRvcvHandoffCliCommand:
    """Test that the 'rvcv-handoff' CLI sub-command is registered and reachable."""

    def test_rvcv_handoff_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvcv-handoff", "--help"])
        assert result.exit_code == 0, result.output

    def test_rvcv_handoff_command_reporter_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvcv-handoff", "--help"])
        assert "--reporter-url" in result.output

    def test_rvcv_handoff_command_vendor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvcv-handoff", "--help"])
        assert "--vendor-url" in result.output

    def test_rvcv_handoff_command_coordinator_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvcv-handoff", "--help"])
        assert "--coordinator-url" in result.output

    def test_rvcv_handoff_command_vendor2_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvcv-handoff", "--help"])
        assert "--vendor2-url" in result.output

    def test_rvcv_handoff_command_case_actor_url_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvcv-handoff", "--help"])
        assert "--case-actor-url" in result.output

    def test_rvcv_handoff_command_skip_health_check_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rvcv-handoff", "--help"])
        assert "--skip-health-check" in result.output


# ---------------------------------------------------------------------------
# Milestone assertion tests — AC-4 of ISSUE-1976
# ---------------------------------------------------------------------------


class TestRvcvHandoffMilestoneAssertions:
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

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        case_actor_client = self._client()
        vendor2_client = self._client()
        reporter = self._actor("urn:test:reporter")
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
                "seed_containers_rvcv",
                return_value=(reporter, vendor, coordinator, vendor2),
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
            patch_chain_shared(demo, "wait_for_case_on_container"),
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
            demo._phase_report_submission(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor2_client=vendor2_client,
                reporter_id=None,
                vendor_id=None,
                coordinator_id=None,
                vendor2_id=None,
            )

    def test_run_rvcv_handoff_calls_verify_case_active(self):
        """run_rvcv_handoff calls verify_case_active after all participants join (M1)."""
        import contextlib

        reporter_client = self._client()
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
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo.run_rvcv_handoff_demo(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor2_client=vendor2_client,
            )
        mock_m1.assert_called()

    def test_phase_fix_lifecycle_calls_verify_fix_ready(self):
        """_phase_fix_lifecycle calls verify_fix_ready at M4/M5."""
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        with (
            patch.object(demo, "wait_for_participant_rm_state"),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(demo, "wait_for_participant_vf_state"),
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
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                case=case,
            )
        mock_m4.assert_called()

    def test_phase_fix_lifecycle_gates_on_rm_accepted(self):
        """_phase_fix_lifecycle polls each vendor RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (ADR-0058/CSB-18-001)."""
        from vultron.core.states.rm import RM

        reporter_client = self._client()
        vendor_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        call_order = []
        rm_calls = []

        def _rm_wait(*a, **kw):
            rm_calls.append(kw)
            call_order.append("rm_wait")

        with (
            patch.object(demo, "wait_for_participant_rm_state", _rm_wait),
            patch.object(
                ActorSession,
                "notify_fix_ready",
                side_effect=lambda *a, **kw: call_order.append("fix_ready"),
            ),
            patch.object(demo, "wait_for_participant_vf_state"),
            patch.object(demo, "verify_fix_ready"),
        ):
            demo._phase_fix_lifecycle(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                case=case,
            )

        assert len(rm_calls) == 2, (
            f"wait_for_participant_rm_state must be called once per vendor (got {len(rm_calls)}) (ADR-0058/CSB-18-001)"
        )
        assert all(
            c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), (
            "expected_states must be {ACCEPTED, DEFERRED, CLOSED} for each vendor (CSB-18-001)"
        )
        assert "rm_wait" in call_order and "fix_ready" in call_order
        assert call_order.index("rm_wait") < call_order.index("fix_ready"), (
            "wait_for_participant_rm_state must precede actor_notifies_fix_ready (ADR-0058)"
        )

    def test_phase_publication_calls_verify_publicly_disclosed(self):
        """_phase_publication calls verify_publicly_disclosed at M6."""
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        reporter = self._actor("urn:test:reporter")
        reporter_in_reporter = self._actor("urn:test:reporter")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case()

        with (
            patch.object(ActorSession, "notify_published"),
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vf_state"),
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
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                reporter=reporter,
                reporter_in_reporter=reporter_in_reporter,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )
        mock_m6.assert_called()

    def test_phase_publication_order_vendor1_vendor2_reporter_coordinator(
        self,
    ):
        """Phase 6 notifies published in CVD order: V1, V2, Reporter, Coordinator last."""
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        reporter_in_reporter = self._actor("urn:test:reporter")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case()

        call_order: list[str] = []

        def _notify(session, *a, **kw):
            call_order.append(session.actor.id_)

        with (
            patch.object(
                ActorSession,
                "notify_published",
                autospec=True,
                side_effect=_notify,
            ),
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vf_state"),
            patch.object(demo, "verify_publicly_disclosed"),
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_publication(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=self._actor("urn:test:vendor"),
                vendor_in_vendor=vendor_in_vendor,
                vendor2=self._actor("urn:test:vendor2"),
                vendor2_in_vendor2=vendor2_in_vendor2,
                reporter=self._actor("urn:test:reporter"),
                reporter_in_reporter=reporter_in_reporter,
                coordinator=self._actor("urn:test:coordinator"),
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )

        assert call_order == [
            "urn:test:vendor",
            "urn:test:vendor2",
            "urn:test:reporter",
            "urn:test:coordinator",
        ], f"Unexpected publication order: {call_order}"

    def test_phase_case_closure_runs_the_closure_milestone(self):
        """_phase_case_closure runs the shared closure milestone (CM-23-004).

        The milestone checks the CASE_MANAGER's store and each leaver's own
        replica inside ``close_case_owner_last``; the scenario only names it.
        """
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        reporter = self._actor("urn:test:reporter")
        reporter_in_reporter = self._actor("urn:test:reporter")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case()
        case.id_ = "urn:test:case"
        vendor_client.get.return_value = {
            "e0": {
                "case_id": case.id_,
                "log_index": 0,
                "entry_hash": "h0",
                "semantic_type": "close_case",
            }
        }

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(demo, "close_case_owner_last") as mock_m7,
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_case_closure(
                case_actor_client=MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                reporter=reporter,
                reporter_in_reporter=reporter_in_reporter,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )
        mock_m7.assert_called_once()
        assert mock_m7.call_args.kwargs.get("milestone") is None

    def test_phase_case_closure_coordinator_closes_last(self):
        """Coordinator (case owner) must close after Vendor1, Vendor2, and Reporter."""
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        reporter = self._actor("urn:test:reporter")
        reporter_in_reporter = self._actor("urn:test:reporter")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case()
        case.id_ = "urn:test:case"
        vendor_client.get.return_value = {
            "e0": {
                "case_id": case.id_,
                "log_index": 0,
                "entry_hash": "h0",
                "semantic_type": "close_case",
            }
        }

        with (
            patch.object(
                ActorSession, "leave_case", autospec=True
            ) as mock_close,
            stub_closure_gate(),
            patch.object(
                demo,
                "demo_check",
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            demo._phase_case_closure(
                case_actor_client=MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                vendor=vendor,
                vendor_in_vendor=vendor_in_vendor,
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                reporter=reporter,
                reporter_in_reporter=reporter_in_reporter,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )

        actors_closed = [
            call.args[0].actor.id_ for call in mock_close.call_args_list
        ]
        assert actors_closed[-1] == coordinator_in_coordinator.id_, (
            "Coordinator (case owner) must close last; got order: "
            + str(actors_closed)
        )
        assert actors_closed.index(
            reporter_in_reporter.id_
        ) < actors_closed.index(coordinator_in_coordinator.id_), (
            "Reporter must close before Coordinator"
        )


# ---------------------------------------------------------------------------
# AC-5c: Reporter receives Announce(CaseLedgerEntry) after ownership transfer
# ---------------------------------------------------------------------------

_OTC_VENDOR_BASE = "http://vendor-otc.test"
_OTC_COORDINATOR_BASE = "http://coordinator-otc.test"
_OTC_REPORTER_BASE = "http://reporter-otc.test"
_OTC_VENDOR_SLUG = "vendor-otc"
_OTC_COORDINATOR_SLUG = "coordinator-otc"
_OTC_REPORTER_SLUG = "reporter-otc"


def _otc_create_actor(client, base_api: str, slug: str, name: str) -> str:
    """POST an Organization actor; return its canonical URI."""
    actor_id = f"{base_api}/actors/{slug}"
    resp = client.post(
        "/api/v2/actors/",
        json={"type": "Organization", "name": name, "id": actor_id},
    )
    assert resp.status_code in (
        200,
        201,
    ), f"Actor creation failed ({resp.status_code}): {resp.text}"
    return actor_id


def _otc_post_inbox(client, actor_slug: str, activity) -> None:
    resp = client.post(
        f"/api/v2/actors/{actor_slug}/inbox/",
        content=activity.model_dump_json(by_alias=True, exclude_none=True),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 202, (
        f"Inbox POST returned {resp.status_code}: {resp.text}"
    )


def _otc_make_offer(dl, proposal, case_manager_id: str) -> Any:
    """Run the CASE_MANAGER's received proposal use case on *dl*.

    The CASE_MANAGER ledgers the proposal and makes the Offer (ADR-0148);
    returns that Offer, the one the transferee answers.
    """
    from test.support.received import received_event
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
    from vultron.core.models.events.actor import (
        ProposeCaseOwnershipTransferReceivedEvent,
    )
    from vultron.core.models.use_case_result import HandlerDisposition
    from vultron.core.participants.ownership_offer import ownership_offer_id
    from vultron.core.use_cases.received.actor.ownership import (
        ProposeCaseOwnershipTransferReceivedUseCase,
    )

    event = received_event(proposal, receiving_actor_id=case_manager_id)
    assert isinstance(event, ProposeCaseOwnershipTransferReceivedEvent)
    result = ProposeCaseOwnershipTransferReceivedUseCase(
        dl,
        event,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()
    assert result.disposition is HandlerDisposition.APPLIED, result
    # The proposal's and the Offer's fan-out are not this test's subject;
    # drop them so only the Accept's deliveries are observed.
    while dl.outbox_pop() is not None:
        pass
    offer = dl.read(
        ownership_offer_id(
            case_manager_id, event.case_id or "", proposal.id_, event.actor_id
        )
    )
    assert offer is not None
    return offer


@contextlib.contextmanager
def _otc_ownership_transferred(
    router: _TestClientRouter,
) -> Iterator[IsolatedActorApp]:
    """Run the AC-5c ownership transfer and yield the Reporter's app.

    Three isolated actor apps wired through *router*: the Vendor (case owner),
    the Coordinator (CASE_MANAGER, which makes the Offer from the Vendor's
    proposal and receives the Accept) and the Reporter, the transferee.
    The case lives only on the Coordinator, so
    neither peer can anchor its chain: each Rejects every ledger entry it is
    sent, which is what drives the Reject/replay loop SYNC-15-003 bounds.
    Yields once the Accept's inbox POST — and every delivery it set off — has
    returned.
    """
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
        get_default_emitter,
    )
    from vultron.config import config_override
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.factories.case import (
        accept_case_ownership_transfer_activity,
        propose_case_ownership_transfer_activity,
    )
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    with config_override(
        VULTRON_SERVER__BASE_URL=f"{_OTC_COORDINATOR_BASE}/api/v2",
        VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=f"{_OTC_COORDINATOR_BASE}/api/v2",
    ):
        # `actor_slug` decides which actor's store `iso.dl` is. These actors
        # are created under the module slugs below, and a store belongs to
        # exactly one actor (ADR-0073), so leaving the default `"primary"`
        # points `dl` at an empty database — the reporter's Announce assertion
        # then reads a store nothing was ever delivered to.
        vendor_iso = create_isolated_actor_app(
            base_url=_OTC_VENDOR_BASE,
            router=router,
            actor_slug=_OTC_VENDOR_SLUG,
        )
        coordinator_iso = create_isolated_actor_app(
            base_url=_OTC_COORDINATOR_BASE,
            router=router,
            actor_slug=_OTC_COORDINATOR_SLUG,
        )
        reporter_iso = create_isolated_actor_app(
            base_url=_OTC_REPORTER_BASE,
            router=router,
            actor_slug=_OTC_REPORTER_SLUG,
        )

        previous_emitter = get_default_emitter()
        configure_default_emitter(router)  # type: ignore[arg-type]

        try:
            with (
                vendor_iso.client as vendor_tc,
                coordinator_iso.client as coordinator_tc,
                reporter_iso.client as reporter_tc,
            ):
                coordinator_base_api = f"{_OTC_COORDINATOR_BASE}/api/v2"
                vendor_base_api = f"{_OTC_VENDOR_BASE}/api/v2"
                reporter_base_api = f"{_OTC_REPORTER_BASE}/api/v2"

                vendor_id = _otc_create_actor(
                    vendor_tc,
                    vendor_base_api,
                    _OTC_VENDOR_SLUG,
                    "Vendor OTC",
                )
                coordinator_id = _otc_create_actor(
                    coordinator_tc,
                    coordinator_base_api,
                    _OTC_COORDINATOR_SLUG,
                    "Coordinator OTC",
                )
                reporter_id = _otc_create_actor(
                    reporter_tc,
                    reporter_base_api,
                    _OTC_REPORTER_SLUG,
                    "Reporter OTC",
                )

                # Build a case on the Coordinator's DataLayer directly so
                # CommitCaseLedgerEntryNode can read participants and the
                # FanOutLogEntryNode knows to broadcast to Reporter.
                case = as_VulnerabilityCase(
                    name="OTC Test Case",
                    attributed_to=vendor_id,
                    content="AC-5c integration test case",
                )
                case_id = case.id_

                vendor_p = as_CaseParticipant(
                    attributed_to=vendor_id,
                    context=case_id,
                    case_roles=[CVDRole.CASE_OWNER],
                )
                coordinator_p = as_CaseParticipant(
                    attributed_to=coordinator_id,
                    context=case_id,
                    case_roles=[CVDRole.CASE_MANAGER],
                )
                reporter_p = as_CaseParticipant(
                    attributed_to=reporter_id,
                    context=case_id,
                    case_roles=[CVDRole.REPORTER],
                )
                case.actor_participant_index[vendor_id] = vendor_p.id_
                case.actor_participant_index[coordinator_id] = (
                    coordinator_p.id_
                )
                case.actor_participant_index[reporter_id] = reporter_p.id_
                case.case_participants.extend(
                    [vendor_p.id_, coordinator_p.id_, reporter_p.id_]
                )

                cdl = coordinator_iso.dl
                cdl.create(case)
                cdl.create(vendor_p)
                cdl.create(coordinator_p)
                cdl.create(reporter_p)
                # Coordinator's DL needs to know about the other actors
                # for outbox delivery routing.
                from vultron.wire.as2.vocab.base.objects.actors import (
                    as_Service,
                )

                cdl.create(as_Service(id_=vendor_id, name="Vendor OTC"))
                cdl.create(as_Service(id_=reporter_id, name="Reporter OTC"))

                # The Vendor proposes the transfer to the Reporter; the
                # Coordinator, the CASE_MANAGER, makes and ledgers the Offer
                # (ADR-0148).  It runs in-process: the Offer's own delivery
                # is not this test's subject.
                case_wire = as_VulnerabilityCase.model_validate(
                    {
                        "attributed_to": CASE_OWNER_ID,
                        "id": case_id,
                        "name": case.name or "OTC Test Case",
                    }
                )
                proposal = propose_case_ownership_transfer_activity(
                    case_wire,
                    # Inline, as the inbox rehydrates it: the ledger
                    # commit refuses a bare-id target (CLP-07).
                    target=as_Service(id_=reporter_id, name="Reporter OTC"),
                    actor=vendor_id,
                    to=[coordinator_id],
                )
                offer = _otc_make_offer(cdl, proposal, coordinator_id)

                # The Reporter accepts, at the Coordinator's inbox.  The
                # Coordinator IS the CaseActor so it processes the Accept,
                # updates attributed_to, commits the ledger entry, and fans
                # out Announce(CaseLedgerEntry) to all case participants.
                accept = accept_case_ownership_transfer_activity(
                    offer=offer,
                    actor=reporter_id,
                    to=[coordinator_id],
                )
                _otc_post_inbox(coordinator_tc, _OTC_COORDINATOR_SLUG, accept)

                yield reporter_iso
        finally:
            configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
            vendor_iso.dl.close()
            coordinator_iso.dl.close()
            reporter_iso.dl.close()


@pytest.mark.spec("CM-21-007")
class TestOwnershipTransferAnnounceReachesReporterAC5c:
    """AC-5c: Reporter receives Announce(CaseLedgerEntry) after ownership transfer.

    Three-actor setup:
    - Vendor  — case owner, proposes the ownership transfer
    - Coordinator — CaseActor, makes the Offer from the proposal and
                    receives the Accept, commits the ledger entry,
                    broadcasts Announce
    - Reporter  — the transferee; must receive the
                Announce(CaseLedgerEntry) without any manual trigger

    All three actors use isolated FastAPI apps wired via _TestClientRouter.
    The test seeds the case and participants directly on the Coordinator's
    DataLayer, has the Coordinator make the Offer from the Vendor's
    proposal, then delivers the Reporter's Accept(Offer) to the
    Coordinator's inbox
    via HTTP POST.  The outbox drains automatically (TestClient processes
    BackgroundTasks synchronously), routing the Announce to Reporter's inbox.
    Reporter's DataLayer is then checked for an Announce whose object is a
    CaseLedgerEntry with semantic_type == "accept_case_ownership_transfer".
    """

    def test_reporter_receives_announce_ledger_entry(self):
        with _otc_ownership_transferred(_TestClientRouter()) as reporter_iso:
            # The TestClient processes BackgroundTasks synchronously;
            # the outbox drains during the POST and _TestClientRouter
            # delivers Announce(CaseLedgerEntry) to Reporter's inbox.
            # A received Announce is held only as intake archived it
            # (DL-06-006).
            announce_values = received_of_type(reporter_iso.dl, "Announce")

            def _is_ot_announce(a: object) -> bool:
                obj = (
                    a.get("object_")
                    if isinstance(a, dict)
                    else getattr(a, "object_", None)
                )
                if obj is None:
                    return False
                semantic_type = (
                    obj.get("semantic_type")
                    if isinstance(obj, dict)
                    else getattr(obj, "semantic_type", None)
                )
                return semantic_type == "accept_case_ownership_transfer"

            ot_announces = [a for a in announce_values if _is_ot_announce(a)]
            assert len(ot_announces) >= 1, (
                "Reporter's DataLayer must contain at least one "
                "Announce(CaseLedgerEntry[semantic_type="
                "accept_case_ownership_transfer]) "
                "after ownership transfer — no manual trigger (AC-5c). "
                f"Got announces: {announce_values!r}"
            )


class _CountingRouter(_TestClientRouter):
    """A router that counts deliveries and drops every one past *cap*.

    The cap turns a Reject/replay storm into a fast, readable failure instead
    of a test that never returns.
    """

    def __init__(self, cap: int) -> None:
        super().__init__()
        self.cap = cap
        self.attempted = 0

    async def emit(
        self, activity_id: str, json_body: str, recipients: list[str]
    ) -> None:
        self.attempted += len(recipients)
        if self.attempted > self.cap:
            return
        await super().emit(activity_id, json_body, recipients)


@pytest.mark.spec("SYNC-15-013")
@pytest.mark.spec("SYNC-15-014")
class TestUnanchoredPeerRejectStormIsBounded:
    """A peer that can never anchor its chain does not keep a replay loop alive.

    In the AC-5c setup neither peer holds the case, and each refuses the case
    announce because it has no CASE_MANAGER on record (PCR-03-004), so every
    replayed entry comes back as a genesis Reject.  With a fixed cooldown the
    loop stopped only when one round trip beat it: on a loaded host it ran
    until the test timed out (#4882).  The fake clock here advances on every
    read, so each round looks slower than any fixed cooldown.
    """

    #: A healthy transfer makes a few dozen deliveries; the storm made
    #: over a thousand in two minutes.
    _DELIVERY_CAP = 300

    def test_reject_storm_terminates_under_slow_rounds(self):
        from vultron.core.models._helpers import now_utc as real_now

        start = real_now()
        reads = 0

        def slow_clock():
            nonlocal reads
            reads += 1
            return start + timedelta(seconds=3 * reads)

        router = _CountingRouter(cap=self._DELIVERY_CAP)
        with patch(
            "vultron.core.behaviors.sync.nodes.replay_guard.now_utc",
            slow_clock,
        ):
            with _otc_ownership_transferred(router):
                pass

        assert router.attempted <= self._DELIVERY_CAP, (
            f"{router.attempted} deliveries for one ownership transfer: the"
            " Reject/replay loop to the unanchored peers did not settle"
            " (SYNC-15-003)"
        )


# ---------------------------------------------------------------------------
# Bug #2120: reporter case-replica must be seeded in _phase_report_submission
# (genesis-level race: Reporter gets Announce(CaseLedgerEntry) before
# Create(VulnerabilityCase) is delivered — genesis hash absent).
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-08-005")
class TestReporterCaseReplicaGenesisWaitInReportSubmission:
    """_phase_report_submission must wait for Reporter's case replica
    immediately after wait_for_case_participants — before any invitation
    sequence starts (Bug #2120, genesis-level race)."""

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

    def test_reporter_genesis_wait_before_first_invitation(self):
        """wait_for_case_on_container(reporter_client) is called in _phase_report_submission
        before any invite-to-case trigger fires (genesis-level guard)."""
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        case_actor_client = self._client()
        vendor2_client = self._client()

        reporter = self._actor("urn:test:reporter")
        vendor = self._actor("urn:test:vendor")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        vendor2 = self._actor("urn:test:vendor2")
        vendor_in_vendor = self._actor("urn:test:vendor")
        report = MagicMock()
        offer = MagicMock()
        offer.id_ = "urn:test:offer"
        case = self._case("urn:test:case")

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kw):
            if client is reporter_client:
                call_order.append("reporter_genesis_wait")

        def _wait_for_case_participants(**_kw):
            call_order.append("case_participants_wait")

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_rvcv",
                return_value=(reporter, vendor, coordinator, vendor2),
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
            patch.object(
                demo,
                "wait_for_case_participants",
                side_effect=_wait_for_case_participants,
            ),
            patch_chain_shared(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch("vultron.demo.actor_session.post_to_trigger"),
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
            demo._phase_report_submission(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor2_client=vendor2_client,
                reporter_id=None,
                vendor_id=None,
                coordinator_id=None,
                vendor2_id=None,
            )

        assert "reporter_genesis_wait" in call_order, (
            "wait_for_case_on_container(reporter_client) was never called in "
            "_phase_report_submission — genesis hash unavailable race (Bug #2120)"
        )
        # The genesis wait must come after wait_for_case_participants
        assert "case_participants_wait" in call_order, (
            "wait_for_case_participants was never called in _phase_report_submission"
        )
        participants_idx = next(
            i
            for i, v in enumerate(call_order)
            if v == "case_participants_wait"
        )
        genesis_idx = next(
            i for i, v in enumerate(call_order) if v == "reporter_genesis_wait"
        )
        assert participants_idx < genesis_idx, (
            f"wait_for_case_participants (index {participants_idx}) must precede "
            f"Reporter genesis wait (index {genesis_idx}). "
            f"Call order: {call_order} — Bug #2120 (CLP-08-005)"
        )


# Bug #2120: reporter case-replica must be seeded before Vendor2 RM triage
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-08-005")
class TestReporterCaseReplicaWaitBeforeVendor2Triage:
    """_phase_coordinator_invites_vendor2 must wait for the Reporter's case
    replica before running Vendor2's RM triage (Bug #2120)."""

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

    def test_reporter_client_in_signature(self):
        """_phase_coordinator_invites_vendor2 must accept reporter_client."""
        import inspect

        sig = inspect.signature(demo._phase_coordinator_invites_vendor2)
        assert "reporter_client" in sig.parameters, (
            "_phase_coordinator_invites_vendor2 must accept reporter_client "
            "to gate Vendor2 RM triage on the Reporter having the case replica "
            "(Bug #2120, CLP-08-005)"
        )

    def test_reporter_wait_before_vendor2_triage(self):
        """The reporter case wait precedes run_invite_path_rm_triage for Vendor2."""
        import inspect

        sig = inspect.signature(demo._phase_coordinator_invites_vendor2)
        if "reporter_client" not in sig.parameters:
            pytest.skip(
                "reporter_client not yet in signature — prerequisite missing"
            )

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        vendor2 = self._actor("urn:test:vendor2")
        vendor2_in_vendor2 = self._actor("urn:test:vendor2")
        case = self._case("urn:test:case")

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kw):
            if client is reporter_client:
                call_order.append("reporter_wait")

        def _triage(**_kw):
            call_order.append("triage")

        with (
            patch_chain_shared(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch.object(
                demo, "run_invite_path_rm_triage", side_effect=_triage
            ),
            # actor="urn:t:ca" matches the case_actor_id passed below: the
            # phase now asserts the Invite went out attributed to the CaseActor
            # (PCR-08-008), which is the property that used to be pursued by
            # posting the trigger to the CaseActor's container instead.
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(
                    activity=MagicMock(id_="urn:t:invite", actor="urn:t:ca")
                ),
            ),
            patch.object(
                ActorSession,
                "accept_case_invite",
                return_value=SimpleNamespace(
                    activity={
                        "type": "Accept",
                        "id": "http://t/acc",
                        "actor": "http://t/a",
                        "object": "http://t/o",
                    }
                ),
            ),
            patch.object(invite_chain, "find_case_invite_for_actor"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(
                demo,
                "demo_check",
                side_effect=lambda _: __import__("contextlib").nullcontext(),
            ),
            patch.object(
                demo,
                "demo_step",
                side_effect=lambda _: __import__("contextlib").nullcontext(),
            ),
            # set_stub_summary is seeding infrastructure not under test here.
            patch.object(ActorSession, "set_stub_summary"),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=self._actor("urn:t:case-actor"),
            ),
        ):
            case_actor_client = MagicMock()
            case_actor_client.get.return_value = {}
            demo._phase_coordinator_invites_vendor2(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor2_client=vendor2_client,
                reporter=self._actor("urn:t:reporter"),
                vendor=self._actor("urn:t:vendor"),
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case_actor_id="urn:t:ca",
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                case=case,
                offer=MagicMock(id_="urn:t:offer"),
                report=MagicMock(),
            )

        assert "reporter_wait" in call_order, (
            "wait_for_case_on_container(reporter_client) was never called before Vendor2 triage"
        )
        assert "triage" in call_order, (
            "run_invite_path_rm_triage was never called"
        )
        reporter_idx = next(
            i for i, v in enumerate(call_order) if v == "reporter_wait"
        )
        triage_idx = next(i for i, v in enumerate(call_order) if v == "triage")
        assert reporter_idx < triage_idx, (
            f"Reporter case-replica wait (index {reporter_idx}) must come BEFORE "
            f"run_invite_path_rm_triage (index {triage_idx}). "
            f"Call order: {call_order} — Bug #2120 (CLP-08-005)"
        )


# ---------------------------------------------------------------------------
# Bug #2178: _phase_ownership_handoff must poll for the FORWARDED offer ID
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-21-005")
class TestPhaseOwnershipHandoffForwardedOfferId:
    """_phase_ownership_handoff must discover and use the FORWARDED offer ID (Bug #2178).

    OfferCaseOwnershipTransferReceivedUseCase creates a new Offer (forwarded_id)
    when the CaseActor processes Vendor1's Offer.  The forwarded Offer is stored
    in Coordinator's DataLayer under a different ID.  Polling for the original
    offer ID (wait_for_object_stored with ownership_offer.id_) never terminates
    because the original Offer exists only in the CaseActor's DataLayer.

    The fix: replace wait_for_object_stored with find_ownership_transfer_offer_for_actor,
    which scans Coordinator's DataLayer for any Offer(VulnerabilityCase, target=coordinator),
    and use the returned (forwarded) ID for the accept-case-ownership-transfer trigger.
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

    def _invoke_phase(
        self, forwarded_offer_id: str, *, capture_trigger_calls: bool = False
    ):
        """Run _phase_ownership_handoff with find_ownership_transfer_offer_for_actor mocked.

        Returns (trigger_calls_list, mock_find, coordinator_client, coordinator, case, original_offer).
        """
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor_in_vendor = self._actor("urn:test:vendor")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        case = self._case("urn:test:case")

        original_offer = MagicMock()
        original_offer.id_ = "urn:test:original-offer"

        trigger_seq = iter(
            [
                {
                    "activity": {
                        "id": "urn:test:invite",
                        "type": "Invite",
                        "actor": "http://t/a",
                        "object": "http://t/o",
                    }
                },
                {
                    "activity": {
                        "id": "urn:test:accept-invite",
                        "type": "Accept",
                        "actor": "http://t/a",
                        "object": "http://t/o",
                    }
                },
                {
                    "activity": {
                        "id": original_offer.id_,
                        "type": "Offer",
                        "actor": "http://t/a",
                        "object": "http://t/o",
                    }
                },
                {
                    "activity": {
                        "id": "urn:test:accept-ownership",
                        "type": "Accept",
                        "actor": "http://t/a",
                        "object": "http://t/o",
                    }
                },
            ]
        )
        trigger_calls: list[dict] = []

        def _trigger(**kwargs):
            trigger_calls.append(kwargs)
            return next(trigger_seq)

        with (
            patch(
                "vultron.demo.actor_session.post_to_trigger",
                side_effect=_trigger,
            ),
            patch.object(
                demo,
                "find_ownership_transfer_offer_for_actor",
                return_value=forwarded_offer_id,
            ) as mock_find,
            patch.object(invite_chain, "find_case_invite_for_actor"),
            patch_chain_shared(demo, "wait_for_case_on_container"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_case_attributed_to"),
            patch.object(demo, "wait_for_case_actor_ledger_event"),
            patch.object(
                demo, "wait_for_semantic_type_in_ledger"
            ) as mock_ledger_wait,
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
            # set_stub_summary is seeding infrastructure; stub it out so it
            # does not consume a trigger_seq slot before the invite call.
            patch.object(ActorSession, "set_stub_summary"),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=self._actor("urn:test:case-actor"),
            ),
        ):
            case_actor_client = MagicMock()
            case_actor_client.get.return_value = {}
            mock_vc.model_validate.return_value = case
            demo._phase_ownership_handoff(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                reporter=self._actor("urn:test:reporter"),
                vendor=self._actor("urn:test:vendor"),
                vendor_in_vendor=vendor_in_vendor,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )

        self._last_reporter_client = reporter_client
        self._last_ledger_wait = mock_ledger_wait
        return (
            trigger_calls,
            mock_find,
            coordinator_client,
            coordinator,
            case,
            original_offer,
        )

    @pytest.mark.spec("CM-21-007")
    def test_reporter_ledger_entry_is_awaited_on_reporters_own_replica(self):
        """The phase must gate on the Reporter's replica holding the transfer entry.

        ADR-0053's validation criterion: an actor outside the negotiation learns
        of the completed transfer from ``Announce(CaseLedgerEntry)`` alone.  The
        observable therefore has to be read on the *Reporter's* container — reading
        it on Vendor1's proves only that the CaseActor's own copy replicated to
        the offerer (EDF-06-002).
        """
        _, _, _, _, case, _ = self._invoke_phase("urn:test:forwarded-offer")

        self._last_ledger_wait.assert_called_once()
        kwargs = self._last_ledger_wait.call_args.kwargs
        assert kwargs["client"] is self._last_reporter_client, (
            "the ownership-transfer ledger entry must be awaited on the"
            " Reporter's own container, not the offerer's"
        )
        assert kwargs["case_id"] == case.id_
        assert kwargs["semantic_type"] == "accept_case_ownership_transfer"

    def test_find_ownership_transfer_offer_for_actor_is_called(self):
        """find_ownership_transfer_offer_for_actor must be called (not wait_for_object_stored)."""
        _, mock_find, _, _, _, _ = self._invoke_phase(
            "urn:test:forwarded-offer"
        )
        mock_find.assert_called_once()

    def test_find_called_with_coordinator_client_and_correct_ids(self):
        """find_ownership_transfer_offer_for_actor receives coordinator as transferee."""
        forwarded = "urn:test:forwarded-offer"
        _, mock_find, coordinator_client, coordinator, case, _ = (
            self._invoke_phase(forwarded)
        )

        mock_find.assert_called_once_with(
            client=coordinator_client,
            case_id=case.id_,
            transferee_id=coordinator.id_,
            timeout_seconds=90.0,
        )

    def test_accept_trigger_uses_forwarded_offer_id_not_original(self):
        """accept-case-ownership-transfer trigger must use the FORWARDED offer ID."""
        original_offer_id = "urn:test:original-offer"
        forwarded_offer_id = "urn:test:forwarded-offer"
        assert original_offer_id != forwarded_offer_id

        trigger_calls, _, _, _, _, _ = self._invoke_phase(forwarded_offer_id)

        accept_calls = [
            c
            for c in trigger_calls
            if c.get("behavior") == "accept-case-ownership-transfer"
        ]
        assert len(accept_calls) == 1, (
            f"Expected exactly 1 accept-case-ownership-transfer trigger, got: {accept_calls}"
        )
        body = accept_calls[0].get("body", {})
        assert body.get("offer_id") == forwarded_offer_id, (
            f"accept trigger must use forwarded offer ID {forwarded_offer_id!r}, "
            f"got {body.get('offer_id')!r} — Bug #2178: original offer ID "
            f"{original_offer_id!r} is never stored in Coordinator's DataLayer"
        )


class TestRvcvHandoffCausalGates:
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

    def test_report_submission_skips_case_on_container_when_participants_never_ready(
        self,
    ):
        """demo_gate skips wait_for_case_on_container when wait_for_case_participants times out."""
        import contextlib

        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        case_actor_client = self._client()
        vendor2_client = self._client()
        reporter = self._actor("urn:test:reporter")
        vendor = self._actor("urn:test:vendor")
        vendor_in_vendor = self._actor("urn:test:vendor")
        coordinator = self._actor("urn:test:coordinator")
        coordinator_in_coordinator = self._actor("urn:test:coordinator")
        vendor2 = self._actor("urn:test:vendor2")
        case = self._case()

        case_on_container_called = MagicMock()

        with (
            patch.object(demo, "reset_containers"),
            patch.object(
                demo,
                "seed_containers_rvcv",
                return_value=(reporter, vendor, coordinator, vendor2),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[vendor_in_vendor, coordinator_in_coordinator],
            ),
            patch.object(
                demo,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(
                demo,
                "wait_for_case_participants",
                side_effect=AssertionError(
                    "timed out waiting for participants"
                ),
            ),
            patch_chain_shared(
                demo,
                "wait_for_case_on_container",
                side_effect=case_on_container_called,
            ),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            patch.object(
                demo,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_report_submission(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                vendor2_client=vendor2_client,
                reporter_id=None,
                vendor_id=None,
                coordinator_id=None,
                vendor2_id=None,
            )

        case_on_container_called.assert_not_called()


# ---------------------------------------------------------------------------
# Regression test — ISSUE-2811 timeout fix
# ---------------------------------------------------------------------------


class TestRvcvHandoffRmTriageTimeout:
    """_phase_report_submission must forward timeout_seconds=60.0 to
    run_direct_path_rm_triage so the causal gate (ADR-0058) does not race
    under 4-container CI load (ISSUE-2811)."""

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

    def test_phase_report_submission_passes_60s_timeout_to_rm_triage(self):
        """Regression: rvcv_handoff CI timed out at 20 s default (ISSUE-2811)."""
        import contextlib

        reporter = self._actor("urn:test:reporter")
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
                "seed_containers_rvcv",
                return_value=(reporter, vendor, coordinator, vendor2),
            ),
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[vendor_in_vendor, coordinator_in_coordinator],
            ),
            patch.object(
                demo, "reporter_submits_report", return_value=(report, offer)
            ),
            patch.object(
                demo, "run_direct_path_rm_triage", return_value=case
            ) as mock_rm_triage,
            patch.object(demo, "wait_for_case_participants"),
            patch_chain_shared(demo, "wait_for_case_on_container"),
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
                reporter_client=self._client(),
                vendor_client=self._client(),
                coordinator_client=self._client(),
                case_actor_client=self._client(),
                vendor2_client=self._client(),
                reporter_id=None,
                vendor_id=None,
                coordinator_id=None,
                vendor2_id=None,
            )

        _call = mock_rm_triage.call_args
        assert _call is not None
        assert _call.kwargs.get("timeout_seconds") == 60.0, (
            "run_direct_path_rm_triage must receive timeout_seconds=60.0; "
            "the 20-second default races under 4-container CI load (ISSUE-2811)"
        )


# ---------------------------------------------------------------------------
# #3602: the handoff phase gates on the CaseActor's commit before any replica
# ---------------------------------------------------------------------------


@pytest.mark.spec("EDF-06-002")
@pytest.mark.spec("CM-21-007")
class TestPhaseOwnershipHandoffGatesOnCaseActorCommit:
    """The transfer reaches a replica in two hops, and the phase waits on each.

    Hop 1 is the CaseActor committing ``update_case_owner``, the last entry
    the accepted transfer commits (CLP-07-013); hop 2 is the
    ``Announce(CaseLedgerEntry)`` fan-out applying it on every replica —
    the *only* thing that updates Vendor1's replica, since the CaseActor's own
    node writes only the CaseActor's store (ADR-0073).  In CI run 35917721682
    the fan-out row to Vendor1 waited 14.4 s in the CaseActor's outbox behind
    replay rows for another peer and the single 20 s replica wait expired
    (#3602).  The phase now gates on the commit, read from the CaseActor's own
    store, then checks the replicas against one shared budget, so a late
    fan-out is reported as such.

    These tests run the real ``demo_gate`` / ``demo_check`` context managers:
    patching them out would let the assertion propagate and prove nothing
    about the gate (``vultron/demo/AGENTS.md`` rule 8).
    """

    COMMIT_EVENT = "update_case_owner"

    @staticmethod
    def _actor(id_: str):
        a = MagicMock()
        a.id_ = id_
        return a

    def _run(self, *, commit_raises: bool = False) -> tuple[list, dict]:
        """Run the phase with every network wait recorded in call order.

        Returns ``(calls, clients)`` where ``calls`` is a list of
        ``(kind, kwargs)`` in the order the waits were invoked.
        """
        import contextlib

        from vultron.demo import utils as demo_utils

        clients = {
            name: MagicMock(name=name)
            for name in ("reporter", "vendor", "coordinator", "case-actor")
        }
        for c in clients.values():
            c.get.return_value = {}
        coordinator = self._actor("urn:test:coordinator")
        case = MagicMock()
        case.id_ = "urn:test:case"
        calls: list[tuple[str, dict]] = []

        def _record(kind: str, *, raises: bool = False):
            def _side_effect(**kwargs):
                calls.append((kind, kwargs))
                if raises:
                    raise AssertionError(f"{kind} timed out")

            return _side_effect

        trigger_seq = iter(
            {
                "activity": {
                    "id": f"urn:test:{n}",
                    "type": t,
                    "actor": "http://t/a",
                    "object": "http://t/o",
                }
            }
            for n, t in (
                ("invite", "Invite"),
                ("accept-invite", "Accept"),
                ("offer", "Offer"),
                ("accept-ownership", "Accept"),
            )
        )

        demo_utils.reset_demo_failures()
        with (
            patch(
                "vultron.demo.actor_session.post_to_trigger",
                side_effect=lambda **_: next(trigger_seq),
            ),
            patch.object(
                demo,
                "find_ownership_transfer_offer_for_actor",
                return_value="urn:test:forwarded-offer",
            ),
            patch.object(invite_chain, "find_case_invite_for_actor"),
            patch_chain_shared(demo, "wait_for_case_on_container"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(
                demo,
                "wait_for_case_actor_ledger_event",
                side_effect=_record("commit", raises=commit_raises),
            ),
            patch.object(
                demo,
                "wait_for_case_attributed_to",
                side_effect=_record("attributed_to"),
            ),
            patch.object(
                demo,
                "wait_for_semantic_type_in_ledger",
                side_effect=_record("replica_ledger"),
            ),
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            # demo_step is not under test here; demo_gate / demo_check are
            # deliberately the real ones.
            patch.object(
                demo,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            # set_stub_summary is seeding infrastructure; stub it out so it
            # does not consume a trigger_seq slot before the invite call.
            patch.object(ActorSession, "set_stub_summary"),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=self._actor("urn:test:case-actor"),
            ),
        ):
            mock_vc.model_validate.return_value = case
            demo._phase_ownership_handoff(
                reporter_client=clients["reporter"],
                vendor_client=clients["vendor"],
                coordinator_client=clients["coordinator"],
                case_actor_client=clients["case-actor"],
                reporter=self._actor("urn:test:reporter"),
                vendor=self._actor("urn:test:vendor"),
                vendor_in_vendor=self._actor("urn:test:vendor"),
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator,
                case=case,
            )
        self._failures = list(demo_utils._demo_failures)
        demo_utils.reset_demo_failures()
        return calls, clients

    def test_commit_is_awaited_on_the_case_actor_before_any_replica(self):
        """Hop 1 first: the CaseActor's own ledger, on its own container."""
        calls, clients = self._run()

        kinds = [k for k, _ in calls]
        assert kinds[0] == "commit", kinds
        commit_kwargs = calls[0][1]
        assert commit_kwargs["client"] is clients["case-actor"], (
            "the commit gate reads the CaseActor's store on the dedicated"
            " case-actor container that hosts it, not Vendor1's replica"
        )
        assert commit_kwargs["semantic_type"] == self.COMMIT_EVENT
        assert kinds[1:] == [
            "attributed_to",
            "attributed_to",
            "replica_ledger",
        ], kinds

    def test_replica_waits_share_one_fan_out_budget(self):
        """Hop 2's three waits draw on one budget, never exceeding it."""
        calls, _ = self._run()

        budgets = [kw["timeout_seconds"] for k, kw in calls if k != "commit"]
        assert len(budgets) == 3
        assert all(0 < b <= demo.LATE_JOINER_TIMEOUT for b in budgets), budgets
        assert budgets == sorted(budgets, reverse=True), (
            "each replica wait must receive what is left of the shared budget"
        )

    def test_failed_commit_gate_skips_every_replica_wait(self):
        """A missing commit is one GATE FAILED, not three misleading CHECK FAILEDs."""
        calls, _ = self._run(commit_raises=True)

        assert [k for k, _ in calls] == ["commit"]
        assert len(self._failures) == 1
        assert self._failures[0].startswith("GATE FAILED: CaseActor committed")

    def test_replica_wait_failure_does_not_block_the_other_replicas(self):
        """Hop-2 waits are checks: one late replica still lets the others be read."""
        import contextlib

        from vultron.demo import utils as demo_utils

        # Reuse _run but make the *first* attributed_to wait fail.
        calls: list[str] = []

        def attributed_to(**kwargs):
            calls.append("attributed_to")
            if len(calls) == 1:
                raise AssertionError("Vendor1 replica late")

        demo_utils.reset_demo_failures()
        with (
            patch(
                "vultron.demo.actor_session.post_to_trigger",
                return_value={
                    "activity": {
                        "id": "urn:test:x",
                        "type": "Accept",
                        "actor": "http://t/a",
                        "object": "http://t/o",
                    }
                },
            ),
            patch.object(
                demo,
                "find_ownership_transfer_offer_for_actor",
                return_value="urn:test:forwarded-offer",
            ),
            patch.object(invite_chain, "find_case_invite_for_actor"),
            patch_chain_shared(demo, "wait_for_case_on_container"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_case_actor_ledger_event"),
            patch.object(
                demo, "wait_for_case_attributed_to", side_effect=attributed_to
            ),
            patch.object(
                demo, "wait_for_semantic_type_in_ledger"
            ) as reporter_wait,
            patch.object(demo, "as_VulnerabilityCase"),
            patch.object(
                demo,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(ActorSession, "set_stub_summary"),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=self._actor("urn:test:case-actor"),
            ),
        ):
            client = MagicMock()
            client.get.return_value = {}
            actor = self._actor("urn:test:a")
            demo._phase_ownership_handoff(
                reporter_client=client,
                vendor_client=client,
                coordinator_client=client,
                case_actor_client=client,
                reporter=actor,
                vendor=actor,
                vendor_in_vendor=actor,
                coordinator=actor,
                coordinator_in_coordinator=actor,
                case=self._actor("urn:test:case"),
            )
        failures = list(demo_utils._demo_failures)
        demo_utils.reset_demo_failures()

        assert calls == ["attributed_to", "attributed_to"]
        reporter_wait.assert_called_once()
        assert len(failures) == 1
        assert failures[0].startswith("CHECK FAILED")


class TestRvcvHandoffOwnershipHandoffSkipsDependents:
    """Phase 2: a failed trigger or lookup skips the steps that depend on it.

    Before the fix the invite and offer trigger results were read as
    ``<x>_result.activity`` on a ``None`` sentinel after the suppressing
    ``demo_step`` (crash, #3038 sibling), and the forwarded-offer lookup was a
    ``demo_check`` whose ``""`` sentinel flowed into the accept as
    ``offer_id`` (EDF-06-005).
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

    def _run(
        self,
        *,
        invite_trigger: dict[str, Any] | None = None,
        invite_lookup: dict[str, Any] | None = None,
        offer_trigger: dict[str, Any] | None = None,
        offer_lookup: dict[str, Any] | None = None,
    ):
        invite_trigger = invite_trigger or {
            "return_value": SimpleNamespace(
                activity=MagicMock(id_="urn:test:invite")
            )
        }
        invite_lookup = invite_lookup or {"return_value": "urn:test:invite"}
        offer_trigger = offer_trigger or {
            "return_value": SimpleNamespace(
                activity=MagicMock(id_="urn:test:ownership-offer")
            )
        }
        offer_lookup = offer_lookup or {
            "return_value": "urn:test:forwarded-offer"
        }
        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        case = self._case()

        with (
            patch.object(demo, "wait_for_case_participants"),
            patch_chain_shared(
                demo, "wait_for_case_on_container"
            ) as replica_wait,
            patch.object(demo, "wait_for_case_actor_ledger_event"),
            patch.object(demo, "wait_for_case_attributed_to"),
            patch.object(demo, "wait_for_semantic_type_in_ledger"),
            patch.object(
                ActorSession, "invite_actor_to_case", **invite_trigger
            ),
            patch.object(
                ActorSession, "offer_case_ownership_transfer", **offer_trigger
            ),
            patch.object(ActorSession, "accept_case_invite") as accept_invite,
            patch.object(
                ActorSession, "accept_case_ownership_transfer"
            ) as accept_transfer,
            patch.object(
                invite_chain, "find_case_invite_for_actor", **invite_lookup
            ) as find_invite,
            patch.object(
                demo, "find_ownership_transfer_offer_for_actor", **offer_lookup
            ) as find_offer,
            patch.object(demo, "as_VulnerabilityCase") as mock_vc,
            # set_stub_summary is seeding infrastructure not under test here.
            patch.object(ActorSession, "set_stub_summary"),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=self._actor("urn:test:case-actor"),
            ),
        ):
            mock_vc.model_validate.return_value = case
            # Must not raise: every failure is accumulated, never escaped.
            demo._phase_ownership_handoff(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=self._client(),
                reporter=self._actor("urn:test:reporter"),
                vendor=self._actor("urn:test:vendor"),
                vendor_in_vendor=self._actor("urn:test:vendor"),
                coordinator=self._actor("urn:test:coordinator"),
                coordinator_in_coordinator=self._actor("urn:test:coordinator"),
                case=case,
            )
        return SimpleNamespace(
            find_invite=find_invite,
            accept_invite=accept_invite,
            find_offer=find_offer,
            accept_transfer=accept_transfer,
            replica_wait=replica_wait,
            coordinator_client=coordinator_client,
        )

    def test_invite_trigger_failure_skips_lookup_and_accept(self):
        r = self._run(
            invite_trigger={
                "side_effect": RuntimeError("invite trigger failed")
            }
        )
        r.find_invite.assert_not_called()
        r.accept_invite.assert_not_called()
        assert not [
            c
            for c in r.replica_wait.call_args_list
            if c.kwargs.get("client") is r.coordinator_client
        ], "replica wait ran for the skipped accept"

    def test_invite_lookup_failure_skips_accept(self):
        r = self._run(
            invite_lookup={
                "side_effect": AssertionError("timed out polling for Invite")
            }
        )
        r.accept_invite.assert_not_called()

    def test_offer_trigger_failure_skips_lookup_and_accept(self):
        r = self._run(
            offer_trigger={"side_effect": RuntimeError("offer trigger failed")}
        )
        r.find_offer.assert_not_called()
        r.accept_transfer.assert_not_called()

    def test_offer_lookup_failure_skips_accept(self):
        """The forwarded-offer wait is a demo_gate: a timeout never posts offer_id=""."""
        r = self._run(
            offer_lookup={
                "side_effect": AssertionError(
                    "timed out polling for Offer(VulnerabilityCase)"
                )
            }
        )
        r.accept_transfer.assert_not_called()


class TestRvcvHandoffVendor2InviteChainSkipsDependents:
    """Phase 3 (Coordinator invites Vendor2): failed trigger or lookup skips dependents."""

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

    def _run(self, *, invite_trigger, invite_lookup):
        reporter_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        vendor2_client = self._client()
        case = self._case()

        with (
            patch_chain_shared(
                demo, "wait_for_case_on_container"
            ) as replica_wait,
            patch.object(demo, "run_invite_path_rm_triage"),
            patch.object(
                ActorSession, "invite_actor_to_case", **invite_trigger
            ),
            patch.object(ActorSession, "accept_case_invite") as accept_invite,
            patch.object(
                invite_chain, "find_case_invite_for_actor", **invite_lookup
            ) as find_invite,
            patch.object(demo, "wait_for_case_participants"),
            # set_stub_summary is seeding infrastructure not under test here.
            patch.object(ActorSession, "set_stub_summary"),
            patch.object(
                demo,
                "get_actor_by_id",
                return_value=self._actor("urn:t:case-actor"),
            ),
        ):
            demo._phase_coordinator_invites_vendor2(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                case_actor_client=self._client(),
                vendor2_client=vendor2_client,
                reporter=self._actor("urn:t:reporter"),
                vendor=self._actor("urn:t:vendor"),
                coordinator=self._actor("urn:t:coordinator"),
                coordinator_in_coordinator=self._actor("urn:t:coordinator"),
                case_actor_id="urn:t:ca",
                vendor2=self._actor("urn:t:vendor2"),
                vendor2_in_vendor2=self._actor("urn:t:vendor2"),
                case=case,
                offer=MagicMock(id_="urn:t:offer"),
                report=MagicMock(),
            )
        return find_invite, accept_invite, replica_wait, vendor2_client

    def test_invite_trigger_failure_skips_lookup_and_accept(self):
        find_invite, accept_invite, replica_wait, vendor2_client = self._run(
            invite_trigger={
                "side_effect": RuntimeError("invite trigger failed")
            },
            invite_lookup={"return_value": "urn:t:invite"},
        )
        find_invite.assert_not_called()
        accept_invite.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is vendor2_client
        ], "replica_wait ran for the skipped dependent: " + str(
            replica_wait.call_args_list
        )

    def test_invite_lookup_failure_skips_accept(self):
        _, accept_invite, replica_wait, vendor2_client = self._run(
            invite_trigger={
                "return_value": SimpleNamespace(
                    activity=MagicMock(id_="urn:t:invite", actor="urn:t:ca")
                )
            },
            invite_lookup={
                "side_effect": AssertionError("timed out polling for Invite")
            },
        )
        accept_invite.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is vendor2_client
        ], "replica_wait ran for the skipped dependent: " + str(
            replica_wait.call_args_list
        )
