#!/usr/bin/env python

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

"""Integration tests for the CaseProposal round-trip (CP-07-003).

Verifies the full ``Create(as_CaseProposal)`` →
``Accept(as_CaseProposal)`` + ``Create(VulnerabilityCase)`` exchange
between a vendor actor and a case-actor service.

Coverage
--------
- **CP-07-003 (AC-5):** Integration test covering the full round-trip per
  the spec requirement.
- **AC-4:** The demo layer exercise is in
  ``vultron/demo/exchange/case_proposal_demo.py``,
  wrapped by ``test_case_proposal_demo`` below.

These tests use two isolated FastAPI apps (vendor + reporter) wired via a
shared ``_TestASGIRouter`` so that all outbound deliveries route in-process
without real HTTP.  They are auto-marked as ``@pytest.mark.integration``
by the conftest hook in ``test/demo/``.

Architecture
------------
When the vendor's inbox receives ``SubmitReport`` from the reporter,
``create_receive_report_case_tree`` runs.  That tree now includes
``ProposeCaseToActorNode`` (CP-04-002) which:

1. Reads ``case_actor_id`` from the blackboard (written by
   ``CreateCaseActorNode``).
2. Delegates to ``TriggerActivityAdapter.create_case_proposal()`` to build
   and persist a proper ``as_Create(as_CaseProposal)`` in the DataLayer.
3. Queues the activity to the vendor's outbox via ``record_outbox_item``.

``UpdateActorOutbox`` then flushes the vendor's outbox.  The
``_TestASGIRouter`` routes the delivery to the case-actor's inbox on the
same app (single-app setup: the case-actor and vendor actor share one
FastAPI instance backed by the same DataLayer).

The case-actor's inbox handler runs ``CreateCaseProposalReceivedUseCase``
which:

1. Creates a ``VulnerabilityCase`` (attributed to the case-actor).
2. Emits ``Accept(as_CaseProposal)`` addressed to the vendor.
3. Emits ``Create(VulnerabilityCase)`` addressed to the vendor.

``run_inbox_pipeline`` automatically calls ``outbox_handler`` after
processing, draining the case-actor's outbox and delivering both
activities to the vendor's inbox.

The vendor's inbox then runs:

- ``AcceptCaseProposalReceivedUseCase`` (for the Accept)
- ``CreateVulnerabilityCaseReceivedUseCase`` (for the Create)

All delivery and processing happens synchronously within TestClient's
BackgroundTask execution model.
"""

import importlib

import pytest
from _pytest.monkeypatch import MonkeyPatch

from test.demo._helpers import make_testclient_call
from test.demo.conftest import _TestASGIRouter, create_isolated_actor_app
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Constants — all IDs use HTTP-routable URIs (required for ASGI routing)
# ---------------------------------------------------------------------------

_VENDOR_BASE = "http://vendor-cp.test"
_REPORTER_BASE = "http://reporter-cp.test"
_VENDOR_SLUG = "vendor-cp"
_REPORTER_SLUG = "reporter-cp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_actor(client, base_api: str, slug: str, name: str) -> str:
    """Create an Organization actor; return its full canonical URI."""
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


def _post_to_inbox(client, actor_slug: str, activity) -> None:
    """POST *activity* JSON to ``/api/v2/actors/{actor_slug}/inbox/``."""
    resp = client.post(
        f"/api/v2/actors/{actor_slug}/inbox/",
        content=activity.model_dump_json(by_alias=True, exclude_none=True),
        headers={"Content-Type": "application/json"},
    )
    assert (
        resp.status_code == 202
    ), f"Inbox POST returned {resp.status_code}: {resp.text}"


def _actor_slug(actor_id: str) -> str:
    """Return the last URL path segment of *actor_id*."""
    return actor_id.rstrip("/").rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_app_setup(monkeypatch):
    """Vendor app + reporter app wired for end-to-end CaseProposal delivery.

    Uses two isolated FastAPI apps each with their own in-memory
    ``SqliteDataLayer``.  A shared ``_TestASGIRouter`` routes outbound
    deliveries in-process so the full outbox → inbox → handler chain is
    exercised without real HTTP.

    The ``VULTRON_SERVER__BASE_URL`` is patched to ``{_VENDOR_BASE}/api/v2``
    so that ``CreateCaseActorNode`` builds the CaseActor ID using a
    routable base URL — the ``_TestASGIRouter`` maps this base URL to the
    vendor's ASGI app.

    Yields:
        Tuple of (vendor_iso, reporter_iso, vendor_tc, reporter_tc).
    """
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
        get_default_emitter,
    )
    from vultron.config import get_config, reload_config

    monkeypatch.setenv("VULTRON_SERVER__BASE_URL", f"{_VENDOR_BASE}/api/v2")
    # ResolveCaseActorUrlsNode reads case_actor_service_url from ActorConfig
    # (CP-08-002); in this single-vendor test setup the vendor IS the case-actor
    # service, so we point it at the same base URL.
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", f"{_VENDOR_BASE}/api/v2"
    )
    reload_config()

    router = _TestASGIRouter()
    vendor_iso = create_isolated_actor_app(
        base_url=_VENDOR_BASE, router=router
    )
    reporter_iso = create_isolated_actor_app(
        base_url=_REPORTER_BASE, router=router
    )

    # Register the configured base URL so CaseActor deliveries route to
    # the vendor app (CreateCaseActorNode builds IDs from the config URL).
    config_base_url = get_config().server.base_url.rstrip("/")
    router.register(config_base_url, vendor_iso.app)

    previous_emitter = get_default_emitter()
    configure_default_emitter(router)  # type: ignore[arg-type]

    with vendor_iso.client as vendor_tc:
        with reporter_iso.client as reporter_tc:
            for iso in (vendor_iso, reporter_iso):
                emitter = getattr(iso.app.state, "emitter", None)
                if hasattr(emitter, "_http_fallback"):
                    emitter._http_fallback = router  # type: ignore[assignment]
            yield vendor_iso, reporter_iso, vendor_tc, reporter_tc

    configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
    vendor_iso.dl.close()
    reporter_iso.dl.close()
    reload_config()


# ---------------------------------------------------------------------------
# CP-07-003 round-trip test
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-07-003")
class TestCaseProposalRoundTrip:
    """CP-07-003: full Create(CaseProposal) → Accept + Create(Case) round-trip."""

    def test_proposal_queued_after_submit_report(self, two_app_setup):
        """ProposeCaseToActorNode queues Create(as_CaseProposal) after SubmitReport.

        After the vendor processes a SubmitReport, a ``Create`` activity
        whose ``object_`` is an ``as_CaseProposal`` must exist in the
        DataLayer (CP-04-001, CP-04-002).
        """
        vendor_iso, reporter_iso, vendor_tc, reporter_tc = two_app_setup

        vendor_base_api = f"{_VENDOR_BASE}/api/v2"
        reporter_base_api = f"{_REPORTER_BASE}/api/v2"

        vendor_actor_id = _create_actor(
            vendor_tc, vendor_base_api, _VENDOR_SLUG, "Vendor CP"
        )
        reporter_actor_id = _create_actor(
            reporter_tc, reporter_base_api, _REPORTER_SLUG, "Reporter CP"
        )
        # Register reporter on vendor app so the outbox emitter can route
        # any outbound deliveries back to the reporter.
        _create_actor(
            vendor_tc, reporter_base_api, _REPORTER_SLUG, "Reporter CP"
        )

        report = as_VulnerabilityReport(
            attributed_to=reporter_actor_id,
            name="CP-07-003 round-trip report",
            content=(
                "A vulnerability discovered during CaseProposal integration "
                "testing (CP-07-003)."
            ),
        )
        offer = rm_submit_report_activity(
            report,
            actor=reporter_actor_id,
            to=vendor_actor_id,
        )
        _post_to_inbox(vendor_tc, _actor_slug(vendor_actor_id), offer)

        # Verify a CaseProposal object was created and stored by
        # ProposeCaseToActorNode via TriggerActivityAdapter.create_case_proposal()
        # (CP-04-001).  The DataLayer stores objects by type; by_type("Create")
        # returns raw dicts with dehydrated object_ ID strings, so we check the
        # proposal object directly rather than scanning Create activities.
        proposal_records = vendor_iso.dl.by_type("CaseProposal")
        assert len(proposal_records) >= 1, (
            "Expected at least one CaseProposal object in the vendor DataLayer "
            "after SubmitReport processing.  "
            "ProposeCaseToActorNode may not have run (CP-04-001, CP-04-002)."
        )

    def test_case_actor_sends_accept_and_create_case(self, two_app_setup):
        """Case-actor responds with Accept(CaseProposal) + Create(VulnerabilityCase).

        After the vendor's outbox flushes Create(as_CaseProposal) to the
        case-actor inbox, the case-actor service must emit Accept and
        Create(VulnerabilityCase) back to the vendor (CP-05-003).
        """
        vendor_iso, reporter_iso, vendor_tc, reporter_tc = two_app_setup

        vendor_base_api = f"{_VENDOR_BASE}/api/v2"
        reporter_base_api = f"{_REPORTER_BASE}/api/v2"

        vendor_actor_id = _create_actor(
            vendor_tc, vendor_base_api, _VENDOR_SLUG, "Vendor CP"
        )
        reporter_actor_id = _create_actor(
            reporter_tc, reporter_base_api, _REPORTER_SLUG, "Reporter CP"
        )
        _create_actor(
            vendor_tc, reporter_base_api, _REPORTER_SLUG, "Reporter CP"
        )

        report = as_VulnerabilityReport(
            attributed_to=reporter_actor_id,
            name="CP-07-003 accept round-trip report",
            content=(
                "Verifying that Accept(as_CaseProposal) is delivered to "
                "the vendor during the CaseProposal round-trip (CP-05-003)."
            ),
        )
        offer = rm_submit_report_activity(
            report,
            actor=reporter_actor_id,
            to=vendor_actor_id,
        )
        _post_to_inbox(vendor_tc, _actor_slug(vendor_actor_id), offer)

        # The full chain runs synchronously inside TestClient's
        # BackgroundTask model:
        #   vendor inbox → ProposeCaseToActorNode → vendor outbox flush →
        #   case-actor inbox → CreateCaseProposalReceivedUseCase →
        #   Accept + Create(VulnerabilityCase) → case-actor outbox flush
        #   (via run_inbox_pipeline's outbox_handler call) →
        #   vendor inbox → AcceptCaseProposalReceivedUseCase +
        #   CreateVulnerabilityCaseReceivedUseCase

        accept_activities = vendor_iso.dl.by_type("Accept")
        assert len(accept_activities) >= 1, (
            "Expected at least one Accept activity in the vendor DataLayer "
            "after the CaseProposal round-trip.  "
            "CreateCaseProposalReceivedUseCase may not have sent "
            "Accept(as_CaseProposal) back to the vendor (CP-05-003)."
        )

        # Verify at least one VulnerabilityCase was created by the case-actor.
        vulnerability_cases = vendor_iso.dl.by_type("VulnerabilityCase")
        assert len(vulnerability_cases) >= 1, (
            "Expected at least one VulnerabilityCase in the vendor DataLayer "
            "after the CaseProposal round-trip.  "
            "The case-actor may not have emitted Create(VulnerabilityCase) "
            "(CP-05-003)."
        )


# ---------------------------------------------------------------------------
# Demo layer exercise (AC-4)
# ---------------------------------------------------------------------------


class TestCaseProposalDemo:
    """AC-4: demo layer exercises the CaseProposal round-trip.

    Wraps ``case_proposal_demo.demo_case_proposal_round_trip`` using the
    same monkeypatching pattern as the other demo integration tests.
    """

    @pytest.fixture
    def demo_env(self, client):
        """Set up the demo environment, patching BASE_URL and DataLayerClient."""
        from vultron.demo.exchange import case_proposal_demo as demo

        mp = MonkeyPatch()
        base = str(client.base_url).rstrip("/") + "/api/v2"
        try:
            mp.setattr(demo, "BASE_URL", base)
            mp.setattr(
                demo.DataLayerClient,
                "call",
                make_testclient_call(client, base),
            )
            yield
        finally:
            mp.undo()
            importlib.reload(demo)

    def test_demo_round_trip(self, demo_env, caplog):
        """Demo completes the round-trip without errors (CP-07-003, AC-4)."""
        import logging

        from vultron.demo.exchange import case_proposal_demo as demo

        with caplog.at_level(logging.ERROR):
            demo.main(
                skip_health_check=True,
                demos=[demo.demo_case_proposal_round_trip],
            )

        assert "ERROR SUMMARY" not in caplog.text, (
            "Expected CaseProposal demo to succeed, but got errors:\n"
            + caplog.text
        )
