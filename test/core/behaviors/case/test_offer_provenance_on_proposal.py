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

"""The report's offer provenance rides on the CaseProposal (CP-01-007, #2548).

The chain this pins, end to end:

1. the actor that received ``Offer(VulnerabilityReport)`` holds the only
   ``VultronOfferRecord`` for it, in its own store;
2. it puts that offer's id on the ``as_CaseProposal`` it sends the CaseActor,
   because the CaseActor cannot read a sibling's store (ADR-0073, PCR-01-003);
3. the CaseActor writes it into the canonical ``add_report_to_case`` ledger
   entry;
4. every invited actor rebuilds its own ``VultronOfferRecord`` from that entry
   (``ApplyOfferReportFromLedgerNode``, ADR-0035 DL-06-002).

Step 2 was missing. Nothing complained at any link: the CaseActor's
``_find_offer_id_for_report`` scanned its own (correct, empty) store,
``build_add_report_to_case_snapshot`` omits ``offerId`` when not given one, and
``ApplyOfferReportFromLedgerNode`` skips a snapshot without one as "non-fatal".
The symptom surfaced four steps and one container away, as the invitee's
``validate-report`` answering ``404 Offer not found`` (#2548, fcvcv).
"""

from typing import Any

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.case.nodes import ProposeReportCaseToActorNode
from vultron.core.behaviors.case.offer_provenance import find_offer_for_report
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

_CASE_ACTOR_SERVICE_URL = "http://case-actor:7999/api/v2"

#: A co-located CaseActor: same authority as the vendor, distinct final segment.
#: Stores are keyed on that segment; if they were shared, the CaseActor would see
#: the vendor's ``OfferRecord`` and every assertion here would pass vacuously.
#: ADR-0081 prevents this: each actor has its own store and no cross-store reads.
_CASE_ACTOR_URI = "https://example.org/actors/case-actor"
_VENDOR_URI = "https://example.org/actors/vendor"
_REPORTER_URI = "https://example.org/actors/reporter"
_REPORT_URI = "https://example.org/reports/r-001"
_OFFER_URI = "urn:uuid:8c744079-25d2-4411-8600-cbd270e94ef7"
_PROPOSAL_URI = "https://example.org/proposals/p-001"


@pytest.fixture(autouse=True)
def configure_case_actor_url(monkeypatch):
    """Configure ``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`` for all tests."""
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _CASE_ACTOR_SERVICE_URL
    )
    from vultron.config.app import reload_config

    reload_config()
    yield
    # Undo the env patch BEFORE reloading, or this URL is re-cached into the
    # module-level config for the rest of the session (#2086).
    monkeypatch.undo()
    reload_config()


def _offer_record(report_id: str = _REPORT_URI) -> VultronOfferRecord:
    return VultronOfferRecord(
        offer_id=_OFFER_URI,
        report_id=report_id,
        offer_actor_id=_REPORTER_URI,
        offer_to=[_VENDOR_URI],
    )


@pytest.mark.spec("CP-01-007")
class TestFindOfferForReport:
    """The one lookup both sides of the round-trip use."""

    def test_the_record_for_this_report_is_found(self, datalayer):
        datalayer.save(_offer_record())
        assert find_offer_for_report(datalayer, _REPORT_URI) == (
            _OFFER_URI,
            _REPORTER_URI,
        )

    def test_a_store_with_no_record_answers_none(self, datalayer):
        """The normal answer for a co-located CaseActor, not an error."""
        assert find_offer_for_report(datalayer, _REPORT_URI) == (None, None)

    def test_a_record_for_a_different_report_is_not_returned(self, datalayer):
        datalayer.save(_offer_record("https://example.org/reports/other"))
        assert find_offer_for_report(datalayer, _REPORT_URI) == (None, None)

    @pytest.mark.parametrize("report_id", [None, ""])
    def test_no_report_id_is_answered_without_a_scan(
        self, datalayer, report_id
    ):
        """A missing report is a caller's normal state (``report_id: str | None``).

        Scanning for it would match the first record whose ``report_id`` happens
        to be falsy — there are none today, and this keeps it that way.
        """
        datalayer.save(_offer_record())
        assert find_offer_for_report(datalayer, report_id) == (None, None)


@pytest.mark.spec("CP-01-007")
class TestProposalCarriesTheProvenance:
    """Vendor side: the store that has the ``OfferRecord`` puts it on the wire."""

    def _propose(
        self, bridge, datalayer, actor_id: str, report_id: str
    ) -> as_CaseProposal:
        node = ProposeReportCaseToActorNode(report_id=report_id)
        result = bridge.execute_with_setup(tree=node, actor_id=actor_id)
        assert result.status == Status.SUCCESS, node.feedback_message
        proposals = [
            p
            for p in datalayer.list_objects("CaseProposal")
            if isinstance(p, as_CaseProposal)
        ]
        assert len(proposals) == 1
        return proposals[0]

    def test_the_offer_id_and_sender_are_carried(
        self, datalayer, actor, report, bridge
    ):
        datalayer.save(_offer_record(report.id_))
        proposal = self._propose(bridge, datalayer, actor.id_, report.id_)
        assert proposal.offer_id == _OFFER_URI
        assert proposal.offer_actor_id == _REPORTER_URI

    def test_they_serialise_under_their_wire_names(
        self, datalayer, actor, report, bridge
    ):
        """The CaseActor reads them out of a ``by_alias=True`` dump."""
        datalayer.save(_offer_record(report.id_))
        proposal = self._propose(bridge, datalayer, actor.id_, report.id_)
        dumped = proposal.model_dump(by_alias=True, serialize_as_any=True)
        assert dumped["offerId"] == _OFFER_URI
        assert dumped["offerActorId"] == _REPORTER_URI

    def test_they_survive_a_wire_round_trip(self):
        """The receiving side validates the dump back into a model."""
        original = as_CaseProposal(
            id_=_PROPOSAL_URI,
            attributed_to=_VENDOR_URI,
            object_=_REPORT_URI,
            target=_CASE_ACTOR_URI,
            offer_id=_OFFER_URI,
            offer_actor_id=_REPORTER_URI,
        )
        restored = as_CaseProposal.model_validate(
            original.model_dump(by_alias=True, serialize_as_any=True)
        )
        assert restored.offer_id == _OFFER_URI
        assert restored.offer_actor_id == _REPORTER_URI

    def test_a_report_with_no_offer_record_still_proposes(
        self, datalayer, actor, report, bridge
    ):
        """Provenance is best-effort at the source: a report can arrive by a
        path that mints no ``OfferRecord``, and that must not stop the case."""
        proposal = self._propose(bridge, datalayer, actor.id_, report.id_)
        assert proposal.offer_id is None
        assert proposal.offer_actor_id is None


def _case_actor_store() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)


def _run_received_bt(
    dl: SqliteDataLayer,
    *,
    offer_id: str | None,
    offer_actor_id: str | None,
) -> None:
    """Deliver ``Create(as_CaseProposal)`` to the CaseActor and run its tree."""
    from vultron.core.models.events.case_proposal import (
        CreateCaseProposalReceivedEvent,
    )
    from vultron.core.use_cases.received.case_proposal import (
        CreateCaseProposalReceivedUseCase,
    )
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    dl.save(VulnerabilityReport(id_=_REPORT_URI, attributed_to=_REPORTER_URI))
    proposal = as_CaseProposal(
        id_=_PROPOSAL_URI,
        attributed_to=_VENDOR_URI,
        object_=as_VulnerabilityReport(
            id_=_REPORT_URI, attributed_to=_REPORTER_URI
        ),
        target=_CASE_ACTOR_URI,
        offer_id=offer_id,
        offer_actor_id=offer_actor_id,
    )
    activity = as_Create(
        actor=_VENDOR_URI, object_=proposal, to=[_CASE_ACTOR_URI]
    )
    event = extract_event(activity).model_copy(
        update={"receiving_actor_id": _CASE_ACTOR_URI}
    )
    # The registry types its return as the VultronEvent base; narrow it so the
    # use case's declared parameter type is what actually gets checked here.
    assert isinstance(event, CreateCaseProposalReceivedEvent)
    CreateCaseProposalReceivedUseCase(
        dl, event, wire_render_port=As2WireRenderAdapter()
    ).execute()


def _add_report_snapshot(dl: SqliteDataLayer) -> dict[str, Any]:
    entries = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if getattr(e, "event_type", None) == "add_report_to_case"
    ]
    assert len(entries) == 1, "one canonical add_report_to_case entry (AC-4)"
    snapshot = getattr(entries[0], "payload_snapshot", None)
    assert isinstance(snapshot, dict)
    return snapshot


@pytest.mark.spec("CP-01-007")
@pytest.mark.spec("PCR-01-003")
class TestCaseActorCommitsTheProvenance:
    """CaseActor side: what the proposal carried reaches the ledger entry.

    This is the assertion the invited actor's ``validate-report`` depends on,
    four steps downstream and in another container.
    """

    def test_the_snapshot_names_the_offer_the_proposal_carried(self):
        dl = _case_actor_store()
        _run_received_bt(dl, offer_id=_OFFER_URI, offer_actor_id=_REPORTER_URI)
        snapshot = _add_report_snapshot(dl)
        assert snapshot["offerId"] == _OFFER_URI
        assert snapshot["offerActorId"] == _REPORTER_URI

    def test_its_own_store_is_consulted_first(self):
        """A CaseActor that received the Offer itself trusts its own record.

        The proposal is a claim by a peer; a record in this store is this
        actor's own extraction of the Offer it handled (ADR-0035 DL-06-002).
        """
        dl = _case_actor_store()
        dl.save(_offer_record())
        _run_received_bt(
            dl,
            offer_id="urn:uuid:00000000-0000-4000-8000-000000000000",
            offer_actor_id="https://example.org/actors/someone-else",
        )
        snapshot = _add_report_snapshot(dl)
        assert snapshot["offerId"] == _OFFER_URI
        assert snapshot["offerActorId"] == _REPORTER_URI

    def test_no_provenance_anywhere_leaves_the_key_absent(self):
        """The pre-fix state, kept explicit: absent, never invented.

        ``ApplyOfferReportFromLedgerNode`` reads a missing ``offerId`` as "this
        entry is not about an offer" and skips. A placeholder would instead have
        it mint a ``VultronOfferRecord`` naming an offer nobody ever sent.
        """
        dl = _case_actor_store()
        _run_received_bt(dl, offer_id=None, offer_actor_id=None)
        snapshot = _add_report_snapshot(dl)
        assert "offerId" not in snapshot
        assert "offerActorId" not in snapshot
