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
import json
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.fvcv_handoff_demo as demo
from test.demo._helpers import make_testclient_call
from test.demo.conftest import _TestClientRouter, create_isolated_actor_app
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


def _bound_client(slug: str) -> MagicMock:
    """A dump client stub bound to a *generated* actor id, as the real one is.

    ``actor_id`` must be a real string: the dump derives its route key from it
    (``replica_route_key``, ADR-0073) and writes the key into the manifest, so a
    bare ``MagicMock()`` leaves an unserialisable object there.  The ids are
    deliberately *not* the docker-compose seed names — that is the whole point of
    deriving the key, and a stub carrying ``actor_id="finder"`` would pass even if
    the derivation were dropped.
    """
    client = MagicMock()
    client.actor_id = f"https://example.org/actors/{slug}"
    client.get_list.return_value = [{"logIndex": 0}]
    return client


class TestPhaseDumpCaseLedgersFvcv:
    """Tests for the case-ledger dump phase in the FVCV-handoff demo."""

    def test_writes_jsonl_files_for_all_four_actors(
        self, tmp_path, monkeypatch
    ):
        finder_client = _bound_client("finder-9f3a")
        vendor_client = _bound_client("vendor-2b71")
        coordinator_client = _bound_client("coordinator-4c05")
        vendor2_client = _bound_client("vendor2-8ade")

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

        # The route key selects the store (ADR-0073), so it must be the client's
        # own actor id — not the seed name the output directory is named after.
        manifest = json.loads(
            (tmp_path / "fvcv-handoff" / "dump-manifest.json").read_text()
        )
        keys = {r["actorName"]: r["routeKey"] for r in manifest["actors"]}
        assert keys == {
            "finder": "finder-9f3a",
            "vendor": "vendor-2b71",
            "coordinator": "coordinator-4c05",
            "vendor2": "vendor2-8ade",
        }

    def test_includes_case_actor_when_in_participant_index(
        self, tmp_path, monkeypatch
    ):
        finder_client = _bound_client("finder-9f3a")
        vendor_client = _bound_client("vendor-2b71")
        coordinator_client = _bound_client("coordinator-4c05")
        vendor2_client = _bound_client("vendor2-8ade")

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
            patch.object(demo, "run_direct_path_rm_triage", return_value=case),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "wait_for_case_on_container"),
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
                # Patched: test verifies call parameters/ordering, not context-manager
                # control flow. demo_gate/demo_check behaviour: test_demo_context_managers.py.
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


# ---------------------------------------------------------------------------
# AC-5c: Finder receives Announce(CaseLedgerEntry) after ownership transfer
# ---------------------------------------------------------------------------

_OTC_VENDOR_BASE = "http://vendor-otc.test"
_OTC_COORDINATOR_BASE = "http://coordinator-otc.test"
_OTC_FINDER_BASE = "http://finder-otc.test"
_OTC_VENDOR_SLUG = "vendor-otc"
_OTC_COORDINATOR_SLUG = "coordinator-otc"
_OTC_FINDER_SLUG = "finder-otc"


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
    assert (
        resp.status_code == 202
    ), f"Inbox POST returned {resp.status_code}: {resp.text}"


@pytest.mark.spec("CM-21-007")
class TestOwnershipTransferAnnounceReachesFinderAC5c:
    """AC-5c: Finder receives Announce(CaseLedgerEntry) after ownership transfer.

    Three-actor setup:
    - Vendor  — case owner, offers ownership transfer
    - Coordinator — CaseActor, receives Offer (as CaseActor) and Accept,
                    commits the ledger entry, broadcasts Announce
    - Finder  — observer / case participant; must receive the
                Announce(CaseLedgerEntry) without any manual trigger

    All three actors use isolated FastAPI apps wired via _TestClientRouter.
    The test seeds the case and participants directly on the Coordinator's
    DataLayer, then delivers the Accept(Offer) to the Coordinator's inbox
    via HTTP POST.  The outbox drains automatically (TestClient processes
    BackgroundTasks synchronously), routing the Announce to Finder's inbox.
    Finder's DataLayer is then checked for an Announce whose object is a
    CaseLedgerEntry with event_type == "accept_case_ownership_transfer".
    """

    def test_finder_receives_announce_ledger_entry(self, monkeypatch):
        from vultron.adapters.driving.fastapi.outbox_handler import (
            configure_default_emitter,
            get_default_emitter,
        )
        from vultron.config import reload_config
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.factories.case import (
            offer_case_ownership_transfer_activity,
            accept_case_ownership_transfer_activity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        monkeypatch.setenv(
            "VULTRON_SERVER__BASE_URL",
            f"{_OTC_COORDINATOR_BASE}/api/v2",
        )
        monkeypatch.setenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL",
            f"{_OTC_COORDINATOR_BASE}/api/v2",
        )
        reload_config()

        router = _TestClientRouter()
        # `actor_slug` decides which actor's store `iso.dl` is. These actors are
        # created under the module slugs below, and a store belongs to exactly one
        # actor (ADR-0073), so leaving the default `"primary"` points `dl` at an
        # empty database — the finder's Announce assertion then reads a store
        # nothing was ever delivered to.
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
        finder_iso = create_isolated_actor_app(
            base_url=_OTC_FINDER_BASE,
            router=router,
            actor_slug=_OTC_FINDER_SLUG,
        )

        previous_emitter = get_default_emitter()
        configure_default_emitter(router)  # type: ignore[arg-type]

        try:
            with (
                vendor_iso.client as vendor_tc,
                coordinator_iso.client as coordinator_tc,
                finder_iso.client as _finder_tc,
            ):
                coordinator_base_api = f"{_OTC_COORDINATOR_BASE}/api/v2"
                vendor_base_api = f"{_OTC_VENDOR_BASE}/api/v2"
                finder_base_api = f"{_OTC_FINDER_BASE}/api/v2"

                vendor_id = _otc_create_actor(
                    vendor_tc, vendor_base_api, _OTC_VENDOR_SLUG, "Vendor OTC"
                )
                coordinator_id = _otc_create_actor(
                    coordinator_tc,
                    coordinator_base_api,
                    _OTC_COORDINATOR_SLUG,
                    "Coordinator OTC",
                )
                finder_id = _otc_create_actor(
                    _finder_tc,
                    finder_base_api,
                    _OTC_FINDER_SLUG,
                    "Finder OTC",
                )

                # Build a case on the Coordinator's DataLayer directly so
                # CommitCaseLedgerEntryNode can read participants and the
                # FanOutLogEntryNode knows to broadcast to Finder.
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
                finder_p = as_CaseParticipant(
                    attributed_to=finder_id,
                    context=case_id,
                    case_roles=[CVDRole.FINDER],
                )
                case.actor_participant_index[vendor_id] = vendor_p.id_
                case.actor_participant_index[coordinator_id] = (
                    coordinator_p.id_
                )
                case.actor_participant_index[finder_id] = finder_p.id_
                case.case_participants.extend(
                    [vendor_p.id_, coordinator_p.id_, finder_p.id_]
                )

                cdl = coordinator_iso.dl
                cdl.create(case)
                cdl.create(vendor_p)
                cdl.create(coordinator_p)
                cdl.create(finder_p)
                # Coordinator's DL needs to know about the other actors for
                # outbox delivery routing.
                from vultron.wire.as2.vocab.base.objects.actors import (
                    as_Service,
                )

                cdl.create(as_Service(id_=vendor_id, name="Vendor OTC"))
                cdl.create(as_Service(id_=finder_id, name="Finder OTC"))

                # Seed the Offer on the Coordinator's DL (as if the Vendor
                # had already sent it and the Coordinator stored it).
                case_wire = as_VulnerabilityCase.model_validate(
                    {"id": case_id, "name": case.name or "OTC Test Case"}
                )
                offer = offer_case_ownership_transfer_activity(
                    case=case_wire,
                    target=coordinator_id,
                    actor=vendor_id,
                    to=[coordinator_id],
                )
                cdl.create(offer)

                # Build and deliver Accept(Offer) to Coordinator's inbox.
                # The Coordinator IS the CaseActor so it processes the Accept,
                # updates attributed_to, commits the ledger entry, and fans out
                # Announce(CaseLedgerEntry) to all case participants.
                accept = accept_case_ownership_transfer_activity(
                    offer=offer,
                    actor=coordinator_id,
                    to=[coordinator_id],
                )
                _otc_post_inbox(coordinator_tc, _OTC_COORDINATOR_SLUG, accept)

                # The TestClient processes BackgroundTasks synchronously;
                # the outbox drains during the POST and _TestClientRouter
                # delivers Announce(CaseLedgerEntry) to Finder's inbox.
                # by_type returns a dict keyed by ID; values are model dicts
                # with type_ / object_ fields (SQLite DataLayer row format).
                announces = finder_iso.dl.by_type("Announce")
                announce_values = (
                    list(announces.values())
                    if isinstance(announces, dict)
                    else list(announces)
                )

                def _is_ot_announce(a: object) -> bool:
                    obj = (
                        a.get("object_")
                        if isinstance(a, dict)
                        else getattr(a, "object_", None)
                    )
                    if obj is None:
                        return False
                    event_type = (
                        obj.get("event_type")
                        if isinstance(obj, dict)
                        else getattr(obj, "event_type", None)
                    )
                    return event_type == "accept_case_ownership_transfer"

                ot_announces = [
                    a for a in announce_values if _is_ot_announce(a)
                ]
                assert len(ot_announces) >= 1, (
                    "Finder's DataLayer must contain at least one "
                    "Announce(CaseLedgerEntry[event_type=accept_case_ownership_transfer]) "
                    "after ownership transfer — no manual trigger (AC-5c). "
                    f"Got announces: {announce_values!r}"
                )
        finally:
            configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
            vendor_iso.dl.close()
            coordinator_iso.dl.close()
            finder_iso.dl.close()
            # Undo the env patches BEFORE reloading, otherwise the reload
            # re-caches this test's coordinator URLs and every subsequent test
            # in the session inherits them (#2086).  monkeypatch's own undo
            # runs after this fixture teardown, which is too late.
            monkeypatch.undo()
            reload_config()


# ---------------------------------------------------------------------------
# Bug #2120: finder case-replica must be seeded in _phase_report_submission
# (genesis-level race: Finder gets Announce(CaseLedgerEntry) before
# Create(VulnerabilityCase) is delivered — genesis hash absent).
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaGenesisWaitInReportSubmission:
    """_phase_report_submission must wait for Finder's case replica
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

    def test_finder_genesis_wait_before_first_invitation(self):
        """wait_for_case_on_container(finder_client) is called in _phase_report_submission
        before any invite-to-case trigger fires (genesis-level guard)."""
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
        case = self._case("urn:test:case")

        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kw):
            if client is finder_client:
                call_order.append("finder_genesis_wait")

        def _wait_for_case_participants(**_kw):
            call_order.append("case_participants_wait")

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
            patch.object(
                demo,
                "wait_for_case_participants",
                side_effect=_wait_for_case_participants,
            ),
            patch.object(
                demo, "wait_for_case_on_container", side_effect=_wait_for_case
            ),
            patch.object(demo, "post_to_trigger"),
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

        assert "finder_genesis_wait" in call_order, (
            "wait_for_case_on_container(finder_client) was never called in "
            "_phase_report_submission — genesis hash unavailable race (Bug #2120)"
        )
        # The genesis wait must come after wait_for_case_participants
        assert (
            "case_participants_wait" in call_order
        ), "wait_for_case_participants was never called in _phase_report_submission"
        participants_idx = next(
            i
            for i, v in enumerate(call_order)
            if v == "case_participants_wait"
        )
        genesis_idx = next(
            i for i, v in enumerate(call_order) if v == "finder_genesis_wait"
        )
        assert participants_idx < genesis_idx, (
            f"wait_for_case_participants (index {participants_idx}) must precede "
            f"Finder genesis wait (index {genesis_idx}). "
            f"Call order: {call_order} — Bug #2120 (CLP-08-005)"
        )


# Bug #2120: finder case-replica must be seeded before Vendor2 RM triage
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-08-005")
class TestFinderCaseReplicaWaitBeforeVendor2Triage:
    """_phase_coordinator_invites_vendor2 must wait for the Finder's case
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

    def test_finder_client_in_signature(self):
        """_phase_coordinator_invites_vendor2 must accept finder_client."""
        import inspect

        sig = inspect.signature(demo._phase_coordinator_invites_vendor2)
        assert "finder_client" in sig.parameters, (
            "_phase_coordinator_invites_vendor2 must accept finder_client "
            "to gate Vendor2 RM triage on the Finder having the case replica "
            "(Bug #2120, CLP-08-005)"
        )

    def test_finder_wait_before_vendor2_triage(self):
        """wait_for_case_on_container(finder_client) precedes run_invite_path_rm_triage for Vendor2."""
        import inspect

        sig = inspect.signature(demo._phase_coordinator_invites_vendor2)
        if "finder_client" not in sig.parameters:
            pytest.skip(
                "finder_client not yet in signature — prerequisite missing"
            )

        finder_client = self._client()
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
            if client is finder_client:
                call_order.append("finder_wait")

        def _triage(**_kw):
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
                    "activity": {"id": "urn:t:act", "type": "Offer"}
                },
            ),
            patch.object(demo, "find_case_invite_for_actor"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
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
        ):
            # actor="urn:t:ca" matches the case_actor_id passed below: the
            # phase now asserts the Invite went out attributed to the CaseActor
            # (PCR-08-008), which is the property that used to be pursued by
            # posting the trigger to the CaseActor's container instead.
            mock_ta.model_validate.return_value = MagicMock(
                id_="urn:t:invite", actor="urn:t:ca"
            )
            demo._phase_coordinator_invites_vendor2(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case_actor_id="urn:t:ca",
                vendor2=vendor2,
                vendor2_in_vendor2=vendor2_in_vendor2,
                case=case,
                offer=MagicMock(id_="urn:t:offer"),
                report=MagicMock(),
                finder=self._actor("urn:t:finder"),
            )

        assert (
            "finder_wait" in call_order
        ), "wait_for_case_on_container(finder_client) was never called before Vendor2 triage"
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
                {"activity": {"id": "urn:test:invite", "type": "Invite"}},
                {
                    "activity": {
                        "id": "urn:test:accept-invite",
                        "type": "Accept",
                    }
                },
                {"activity": {"id": original_offer.id_, "type": "Offer"}},
                {
                    "activity": {
                        "id": "urn:test:accept-ownership",
                        "type": "Accept",
                    }
                },
            ]
        )
        trigger_calls: list[dict] = []

        def _trigger(**kwargs):
            trigger_calls.append(kwargs)
            return next(trigger_seq)

        ta_seq = iter(
            [
                MagicMock(id_="urn:test:invite"),
                original_offer,
                MagicMock(id_="urn:test:accept"),
            ]
        )

        with (
            patch.object(demo, "post_to_trigger", side_effect=_trigger),
            patch.object(demo, "as_TransitiveActivity") as mock_ta,
            patch.object(
                demo,
                "find_ownership_transfer_offer_for_actor",
                return_value=forwarded_offer_id,
            ) as mock_find,
            patch.object(demo, "find_case_invite_for_actor"),
            patch.object(demo, "wait_for_case_on_container"),
            patch.object(demo, "wait_for_case_participants"),
            patch.object(demo, "_wait_for_case_attributed_to"),
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
            mock_ta.model_validate.side_effect = lambda x: next(ta_seq)
            mock_vc.model_validate.return_value = case
            demo._phase_ownership_handoff(
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor=self._actor("urn:test:vendor"),
                vendor_in_vendor=vendor_in_vendor,
                coordinator=coordinator,
                coordinator_in_coordinator=coordinator_in_coordinator,
                case=case,
            )

        return (
            trigger_calls,
            mock_find,
            coordinator_client,
            coordinator,
            case,
            original_offer,
        )

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
        assert (
            len(accept_calls) == 1
        ), f"Expected exactly 1 accept-case-ownership-transfer trigger, got: {accept_calls}"
        body = accept_calls[0].get("body", {})
        assert body.get("offer_id") == forwarded_offer_id, (
            f"accept trigger must use forwarded offer ID {forwarded_offer_id!r}, "
            f"got {body.get('offer_id')!r} — Bug #2178: original offer ID "
            f"{original_offer_id!r} is never stored in Coordinator's DataLayer"
        )


class TestFvcvHandoffCausalGates:
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

        finder_client = self._client()
        vendor_client = self._client()
        coordinator_client = self._client()
        case_actor_client = self._client()
        vendor2_client = self._client()
        finder = self._actor("urn:test:finder")
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
                "seed_containers_fvcv",
                return_value=(finder, vendor, coordinator, vendor2),
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
            patch.object(
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

        case_on_container_called.assert_not_called()
