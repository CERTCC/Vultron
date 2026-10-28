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
shared ``InProcessRouter`` so that all outbound deliveries route in-process
without real HTTP.  They are auto-marked as ``@pytest.mark.integration``
by the conftest hook in ``test/demo/``.

Architecture
------------
When the vendor's inbox receives ``SubmitReport`` from the reporter,
``create_receive_report_case_tree`` runs.  That tree now includes
``ProposeReportCaseToActorNode`` (CP-04-002) which:

1. Reads the CaseActor's identity from the configured
   ``case_actor_service_url`` (``case_actor_identity``).
2. Delegates to ``TriggerActivityAdapter.create_case_proposal()`` to build
   and persist a proper ``as_Create(as_CaseProposal)`` in the DataLayer.
3. Queues the activity to the vendor's outbox via ``record_outbox_item``.

``UpdateActorOutbox`` then flushes the vendor's outbox.  The
``InProcessRouter`` routes the delivery to the case-actor's inbox on the
same app (single-app setup: the case-actor and vendor actor share one
FastAPI instance backed by the same DataLayer).

The case-actor's inbox handler runs ``CreateCaseProposalReceivedUseCase``
which:

1. Creates a ``VulnerabilityCase`` attributed to the proposing vendor,
   the CASE_OWNER (CP-09-001).
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
import logging
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch

from test.demo._helpers import (
    expect_trusted_introductions,
    make_testclient_call,
)
from test.demo.conftest import (
    submit_report_through_reporter,
)
from test.support.received import received_event, received_of_type
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.announce import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.demo.in_process import (
    InProcessRouter,
    create_isolated_actor_app,
)
from vultron.demo.utils import case_actor_id_for_report
from vultron.wire.as2.factories import (
    announce_vulnerability_case_activity,
)

# ---------------------------------------------------------------------------
# Constants — all IDs use HTTP-routable URIs (required for InProcessRouter)
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


def _register_peer(client, host_slug: str, peer_id: str, name: str) -> None:
    """Register a peer in the hosted actor's address book (ADR-0081)."""
    resp = client.post(
        f"/api/v2/actors/{host_slug}/peers/",
        json={"id": peer_id, "name": name, "actor_type": "Organization"},
    )
    assert resp.status_code in (
        200,
        201,
    ), f"Peer registration failed ({resp.status_code}): {resp.text}"


def _create_vendor_and_reporter(vendor_tc, reporter_tc) -> tuple[str, str]:
    """Create both actors, each in the other's address book (ADR-0081)."""
    vendor_actor_id = _create_actor(
        vendor_tc, f"{_VENDOR_BASE}/api/v2", _VENDOR_SLUG, "Vendor CP"
    )
    reporter_actor_id = _create_actor(
        reporter_tc, f"{_REPORTER_BASE}/api/v2", _REPORTER_SLUG, "Reporter CP"
    )
    _register_peer(vendor_tc, _VENDOR_SLUG, reporter_actor_id, "Reporter CP")
    _register_peer(reporter_tc, _REPORTER_SLUG, vendor_actor_id, "Vendor CP")
    return vendor_actor_id, reporter_actor_id


def _actor_slug(actor_id: str) -> str:
    """Return the last URL path segment of *actor_id*."""
    return actor_id.rstrip("/").rsplit("/", 1)[-1]


def _provision_case_actor(vendor_tc) -> str:
    """Host the CaseActor on the vendor's node; return its id.

    The vendor is the case-actor service here, so its node must host the
    CaseActor the proposal is addressed to, or the ``Create(CaseProposal)``
    delivery answers 404 and the round trip never begins.  One CaseActor per
    container (#1872), so it is provisioned before the report id exists.
    """
    case_actor_id = case_actor_id_for_report("")
    _create_actor(
        vendor_tc,
        f"{_VENDOR_BASE}/api/v2",
        _actor_slug(case_actor_id),
        "Case Actor CP",
    )
    return case_actor_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_app_setup():
    """Vendor app + reporter app wired for end-to-end CaseProposal delivery.

    Uses two isolated FastAPI apps each with their own in-memory
    ``SqliteDataLayer``.  A shared ``InProcessRouter`` routes outbound
    deliveries in-process so the full outbox → inbox → handler chain is
    exercised without real HTTP.

    The ``VULTRON_SERVER__BASE_URL`` is patched to ``{_VENDOR_BASE}/api/v2``
    so that IDs minted from the server base URL are routable — the
    ``InProcessRouter`` maps this base URL to the vendor's ASGI app.

    Yields:
        Tuple of (vendor_iso, reporter_iso, vendor_tc, reporter_tc).
    """
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
        get_default_emitter,
    )
    from vultron.config import config_override

    # config_override atomically sets env vars, reloads the cache, and
    # restores both on exit — the ordering footgun (#2086) is impossible
    # by construction (CFG-06-006).
    with config_override(
        VULTRON_SERVER__BASE_URL=f"{_VENDOR_BASE}/api/v2",
        # ResolveCaseActorUrlsNode reads case_actor_service_url from ActorConfig
        # (CP-08-002); in this single-vendor test setup the vendor IS the
        # case-actor service, so we point it at the same base URL.
        VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=f"{_VENDOR_BASE}/api/v2",
    ) as cfg:
        router = InProcessRouter()
        # `actor_slug` matters: it decides which actor's store `iso.dl` is.  These
        # tests create their actors under the module slugs below, and a store
        # belongs to exactly one actor (ADR-0073), so leaving the default
        # `"primary"` would point `dl` at an empty database and the assertions
        # would fail for the wrong reason.
        vendor_iso = create_isolated_actor_app(
            base_url=_VENDOR_BASE, router=router, actor_slug=_VENDOR_SLUG
        )
        reporter_iso = create_isolated_actor_app(
            base_url=_REPORTER_BASE, router=router, actor_slug=_REPORTER_SLUG
        )

        # Register the configured base URL so CaseActor deliveries route to
        # the vendor app (IDs are minted from the configured base URL).
        config_base_url = cfg.server.base_url.rstrip("/")
        router.register(config_base_url, vendor_iso.client)

        previous_emitter = get_default_emitter()
        configure_default_emitter(router)  # type: ignore[arg-type]

        with vendor_iso.client as vendor_tc:
            with reporter_iso.client as reporter_tc:
                yield vendor_iso, reporter_iso, vendor_tc, reporter_tc

        configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
        vendor_iso.dl.close()
        reporter_iso.dl.close()


# ---------------------------------------------------------------------------
# CP-07-003 round-trip test
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-07-003")
class TestCaseProposalRoundTrip:
    """CP-07-003: full Create(CaseProposal) → Accept + Create(Case) round-trip."""

    @pytest.mark.spec("CP-04-001")
    def test_proposal_queued_after_submit_report(self, two_app_setup):
        """ProposeReportCaseToActorNode queues Create(as_CaseProposal) after SubmitReport.

        After the vendor processes a SubmitReport, a ``Create`` activity
        whose ``object_`` is an ``as_CaseProposal`` must exist in the
        DataLayer (CP-04-001, CP-04-002).
        """
        vendor_iso, _reporter_iso, vendor_tc, reporter_tc = two_app_setup
        vendor_actor_id, reporter_actor_id = _create_vendor_and_reporter(
            vendor_tc, reporter_tc
        )
        _provision_case_actor(vendor_tc)
        submit_report_through_reporter(
            reporter_tc,
            reporter_actor_id,
            vendor_actor_id,
            report_name="CP-07-003 round-trip report",
            report_content=(
                "A vulnerability discovered during CaseProposal integration "
                "testing (CP-07-003)."
            ),
        )

        # Verify a CaseProposal object was created and stored by
        # ProposeReportCaseToActorNode via TriggerActivityAdapter.create_case_proposal()
        # (CP-04-001).  The DataLayer stores objects by type; by_type("Create")
        # returns raw dicts with dehydrated object_ ID strings, so we check the
        # proposal object directly rather than scanning Create activities.
        proposal_records = vendor_iso.dl.by_type("CaseProposal")
        assert len(proposal_records) >= 1, (
            "Expected at least one CaseProposal object in the vendor DataLayer "
            "after SubmitReport processing.  "
            "ProposeReportCaseToActorNode may not have run (CP-04-001, CP-04-002)."
        )

    def _submit_report(self, two_app_setup, caplog, label):
        """Run the report-to-case round trip; return the isolates and actor ids."""
        vendor_iso, reporter_iso, vendor_tc, reporter_tc = two_app_setup
        vendor_actor_id, reporter_actor_id = _create_vendor_and_reporter(
            vendor_tc, reporter_tc
        )
        _provision_case_actor(vendor_tc)
        with caplog.at_level(logging.WARNING):
            submit_report_through_reporter(
                reporter_tc,
                reporter_actor_id,
                vendor_actor_id,
                report_name=label,
                report_content=(
                    "Verifying that Accept(as_CaseProposal) is delivered to "
                    "the vendor during the CaseProposal round-trip (CP-05-003)."
                ),
            )
        return vendor_iso, reporter_iso, vendor_actor_id, reporter_actor_id

    @pytest.mark.spec("CP-09-001")
    @pytest.mark.spec("CM-02-004")
    @pytest.mark.spec("CP-05-003")
    def test_case_actor_sends_accept_and_create_case(
        self, two_app_setup, caplog
    ):
        """Case-actor responds with Accept(CaseProposal) + Create(VulnerabilityCase).

        After the vendor's outbox flushes Create(as_CaseProposal) to the
        case-actor inbox, the case-actor service must emit Accept and
        Create(VulnerabilityCase) back to the vendor (CP-05-003).
        """
        vendor_iso, _reporter_iso, vendor_actor_id, _reporter_actor_id = (
            self._submit_report(
                two_app_setup, caplog, "CP-07-003 accept round-trip report"
            )
        )

        # The full chain runs synchronously inside TestClient's
        # BackgroundTask model:
        #   vendor inbox → ProposeReportCaseToActorNode → vendor outbox flush →
        #   case-actor inbox → CreateCaseProposalReceivedUseCase →
        #   Accept + Create(VulnerabilityCase) → case-actor outbox flush
        #   (via run_inbox_pipeline's outbox_handler call) →
        #   vendor inbox → AcceptCaseProposalReceivedUseCase +
        #   CreateVulnerabilityCaseReceivedUseCase

        accept_activities = received_of_type(vendor_iso.dl, "Accept")
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

        # The replica keeps the owner the CASE_MANAGER recorded: the proposing
        # vendor, never the CaseActor that created the case (CP-09-001).
        replicas = [
            case
            for case in vendor_iso.dl.list_objects("VulnerabilityCase")
            if isinstance(case, VulnerabilityCase)
        ]
        assert replicas, "the vendor holds no VulnerabilityCase replica"
        assert {_as_id(case.attributed_to) for case in replicas} == {
            vendor_actor_id
        }

        # EMB-18-003: the vendor's replica names the default embargo the
        # CASE_MANAGER minted, so the Create must have carried that record and
        # the vendor must hold it — a bare id would have been refused.
        from vultron.core.services.embargo_ordering import read_embargo_event

        cases = [
            vendor_iso.dl.read(case_id) for case_id in vulnerability_cases
        ]
        embargoed = [c for c in cases if getattr(c, "active_embargo", None)]
        assert embargoed, (
            "Expected the vendor's case replica to name an embargo"
        )
        for case in embargoed:
            ref = case.active_embargo
            read_embargo_event(vendor_iso.dl, getattr(ref, "id_", ref))
        refusals = [
            r.getMessage()
            for r in caplog.records
            if "EMB-18-003" in r.getMessage()
        ]
        assert not refusals, refusals

    def _submit_report_through_the_reporter(self, two_app_setup, label):
        """Run the round trip from the reporter's own ``submit-report`` trigger.

        The trigger is how the reporter writes its trust anchor: the pending
        ``ReportCaseLink`` naming the actor it sent the report to
        (CBT-01-005).  Posting the Offer straight to the vendor would leave
        the reporter nothing to check the introduction against.
        """
        vendor_iso, reporter_iso, vendor_tc, reporter_tc = two_app_setup
        vendor_actor_id, reporter_actor_id = _create_vendor_and_reporter(
            vendor_tc, reporter_tc
        )
        case_actor_id = _provision_case_actor(vendor_tc)
        submit_report_through_reporter(
            reporter_tc,
            reporter_actor_id,
            vendor_actor_id,
            report_name=label,
            report_content="Checking the reporter's introduction.",
        )
        return (
            vendor_iso,
            reporter_iso,
            vendor_actor_id,
            reporter_actor_id,
            case_actor_id,
        )

    @pytest.mark.spec("CBT-01-001")
    @pytest.mark.spec("CBT-01-006")
    @pytest.mark.spec("CBT-05-005")
    def test_report_receiver_sends_the_reporter_the_case(self, two_app_setup):
        """The reporter's bootstrap Create comes from the report receiver.

        It arrives on the trusted route: the reporter binds its own link to
        the case, records the receiver as the introducer and the
        CASE_MANAGER the introduction names (CBT-01-006), and stores the
        embedded participants (CBT-05-005).
        """
        (
            _vendor_iso,
            reporter_iso,
            vendor_actor_id,
            reporter_actor_id,
            case_actor_id,
        ) = self._submit_report_through_the_reporter(
            two_app_setup, "CBT-01-001 receiver introduces report"
        )

        senders = {
            _as_id(create.actor)
            for create in received_of_type(reporter_iso.dl, "Create")
        }
        assert senders == {vendor_actor_id}

        [link] = [
            link
            for link in reporter_iso.dl.list_objects("ReportCaseLink")
            if isinstance(link, VultronReportCaseLink)
        ]
        assert link.case_creator_id == vendor_actor_id
        assert link.case_manager_id == case_actor_id
        assert link.case_id is not None
        replica = reporter_iso.dl.read(link.case_id)
        assert isinstance(replica, VulnerabilityCase)
        assert _as_id(replica.attributed_to) == vendor_actor_id
        assert reporter_actor_id in replica.actor_participant_index
        assert isinstance(
            reporter_iso.dl.read(
                replica.actor_participant_index[reporter_actor_id]
            ),
            CaseParticipant,
        )

    @pytest.mark.spec("CBT-05-001")
    @pytest.mark.spec("CBT-05-005")
    def test_reporter_accepts_the_case_managers_announce_after_the_introduction(
        self, two_app_setup
    ):
        """After the introduction, the CASE_MANAGER's Announce is accepted.

        The introduction named the CASE_MANAGER, so its later
        ``Announce(VulnerabilityCase)`` is trusted; the same Announce from an
        actor the introduction did not name is refused (CBT-02-003).
        """
        (
            _vendor_iso,
            reporter_iso,
            _vendor_actor_id,
            reporter_actor_id,
            case_actor_id,
        ) = self._submit_report_through_the_reporter(
            two_app_setup, "CBT-05-001 announce after introduction"
        )
        [link] = [
            link
            for link in reporter_iso.dl.list_objects("ReportCaseLink")
            if isinstance(link, VultronReportCaseLink)
        ]
        assert link.case_id is not None
        replica = reporter_iso.dl.read(link.case_id)
        assert isinstance(replica, VulnerabilityCase)

        def _announce_from(sender: str):
            activity = announce_vulnerability_case_activity(
                replica, actor=sender, to=[reporter_actor_id]
            )
            event = cast(
                AnnounceVulnerabilityCaseReceivedEvent,
                received_event(activity),
            ).model_copy(update={"receiving_actor_id": reporter_actor_id})
            return AnnounceVulnerabilityCaseReceivedUseCase(
                reporter_iso.dl, event
            ).execute()

        accepted = _announce_from(case_actor_id)
        assert accepted.disposition is not HandlerDisposition.REFUSED, (
            accepted.reason
        )

        impostor = _announce_from(f"{_VENDOR_BASE}/api/v2/actors/impostor")
        assert impostor.disposition is HandlerDisposition.REFUSED


# ---------------------------------------------------------------------------
# CP-05-002 reject-path round-trip
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-05-002")
@pytest.mark.spec("CP-05-004")
@pytest.mark.spec("CP-07-003")
class TestCaseProposalRejectRoundTrip:
    """CP-05-002 is "evaluate and **either** accept or reject".

    The accept half is covered above.  This is the other half end to end, and it
    is worth an integration test rather than only unit coverage for two reasons:

    - The admission bundle is injected by the **adapter**
      (``inbox_port_factories``), so a unit test that passes a bundle straight to
      the tree builder cannot show the seam is reachable in a running deployment.
      Patching the adapter's module-level singleton is what a deployment with an
      admission policy does.
    - ``RejectCaseProposalReceivedUseCase`` existed long before anything could
      emit a ``Reject(as_CaseProposal)``, which is why #3399 described it as
      unreachable in practice.  Only a round-trip shows it is now reached.
    """

    def test_declining_case_actor_sends_reject_and_creates_no_case(
        self, two_app_setup, monkeypatch
    ):
        from vultron.core.behaviors.call_out.bundles.case_proposal import (
            CaseProposalCallOutBundle,
        )
        from vultron.core.behaviors.call_out.nodes import AlwaysFail

        vendor_iso, _reporter_iso, vendor_tc, reporter_tc = two_app_setup

        # The deployment's admission policy: refuse.  Patched on the adapter
        # module, which is where a real deployment substitutes its own bundle.
        declining = CaseProposalCallOutBundle(
            evaluate_proposal_factory=AlwaysFail,  # type: ignore[arg-type]
        )
        monkeypatch.setattr(
            importlib.import_module(
                "vultron.adapters.driving.fastapi.inbox_port_factories"
            ),
            "CASE_PROPOSAL_DETERMINISTIC",
            declining,
        )

        vendor_actor_id, reporter_actor_id = _create_vendor_and_reporter(
            vendor_tc, reporter_tc
        )
        _provision_case_actor(vendor_tc)
        submit_report_through_reporter(
            reporter_tc,
            reporter_actor_id,
            vendor_actor_id,
            report_name="CP-05-002 reject round-trip report",
            report_content=(
                "Verifying that a declining case actor service sends "
                "Reject(as_CaseProposal) and creates nothing (CP-05-002, "
                "CP-05-004)."
            ),
        )

        reject_activities = received_of_type(vendor_iso.dl, "Reject")
        assert len(reject_activities) >= 1, (
            "A declining case actor service MUST send Reject(as_CaseProposal) "
            "back to the proposer (CP-05-002, CP-05-004).  No Reject reached "
            "the vendor's store, so the refusal never left the case actor."
        )

        assert not received_of_type(vendor_iso.dl, "Accept"), (
            "the service refused, so it must not also acknowledge the proposal"
        )
        assert not vendor_iso.dl.by_type("VulnerabilityCase"), (
            "a refusal creates nothing: no case may be delivered to the "
            "proposer (CLP-10-009)"
        )


# ---------------------------------------------------------------------------
# Demo layer exercise (AC-4)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-07-003")
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

        # WARNING, not ERROR: a refused case introduction (CBT-01-011) is
        # logged at WARNING, and the run must log none (#4675).
        with (
            caplog.at_level(logging.WARNING),
            expect_trusted_introductions(caplog),
        ):
            demo.main(
                skip_health_check=True,
                demos=[demo.demo_case_proposal_round_trip],
            )

        assert "ERROR SUMMARY" not in caplog.text, (
            "Expected CaseProposal demo to succeed, but got errors:\n"
            + caplog.text
        )

    @pytest.mark.parametrize(
        "received_accepts",
        [
            [],
            [{"type": "Accept", "object": {"type": "Offer", "id": "urn:x"}}],
        ],
        ids=["no-accept", "accept-of-another-object"],
    )
    def test_a_failed_check_is_reported(
        self, demo_env, caplog, monkeypatch, received_accepts
    ):
        """A failed demo_check fails the run, not just its log line (#4884).

        With no Accept of a CaseProposal received — none at all, or only an
        Accept of something else — the Accept check fails; the run must
        report it in the error summary, which is what the success test above
        asserts is absent.
        """
        import logging

        from vultron.demo.exchange import case_proposal_demo as demo

        monkeypatch.setattr(
            demo,
            "read_received_activities",
            lambda *_a, **_kw: received_accepts,
        )
        with caplog.at_level(logging.WARNING):
            demo.main(
                skip_health_check=True,
                demos=[demo.demo_case_proposal_round_trip],
            )

        assert "ERROR SUMMARY" in caplog.text
        assert "Accept(as_CaseProposal) exists" in caplog.text
