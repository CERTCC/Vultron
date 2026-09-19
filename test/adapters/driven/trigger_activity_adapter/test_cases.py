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

"""Unit tests for TriggerActivityAdapter case-domain methods."""

import json

import pytest
from pydantic import ValidationError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_ACTOR = "https://example.org/actors/coordinator"
_PEER = "https://example.org/actors/vendor"
_CONTEXT_ID = "https://example.org/contexts/ctx-001"


def _make_case(dl) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(name="CVE-2025-001")
    dl.create(case)
    return case


class TestCreateCase:
    def test_returns_id_and_dict(self, adapter, dl):
        case = _make_case(dl)

        activity_id, activity_dict = adapter.create_case(
            case_id=case.id_,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, str)
        assert "id" in json.loads(activity_dict)

    def test_persists_create_activity(self, adapter, dl):
        case = _make_case(dl)

        activity_id, _ = adapter.create_case(
            case_id=case.id_,
            actor=_ACTOR,
            to=[_PEER],
        )

        assert dl.read(activity_id) is not None


class TestEngageCase:
    def test_returns_id_and_dict(self, adapter, dl):
        case = _make_case(dl)

        activity_id, activity_dict = adapter.engage_case(
            case_id=case.id_,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, str)

    def test_persists_accept_activity(self, adapter, dl):
        case = _make_case(dl)

        activity_id, _ = adapter.engage_case(
            case_id=case.id_,
            actor=_ACTOR,
            to=[_PEER],
        )

        assert dl.read(activity_id) is not None


class TestDeferCase:
    def test_returns_id_and_dict(self, adapter, dl):
        case = _make_case(dl)

        activity_id, activity_dict = adapter.defer_case(
            case_id=case.id_,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, str)

    def test_persists_tentative_reject_activity(self, adapter, dl):
        case = _make_case(dl)

        activity_id, _ = adapter.defer_case(
            case_id=case.id_,
            actor=_ACTOR,
            to=[_PEER],
        )

        assert dl.read(activity_id) is not None


class TestAddObjectToCase:
    def test_returns_id_and_dict(self, adapter, dl):
        case = _make_case(dl)
        note = as_Note(name="Finding", content="details")
        dl.create(note)

        activity_id, activity_dict = adapter.add_object_to_case(
            actor=_ACTOR,
            object_id=note.id_,
            case_id=case.id_,
        )

        assert activity_id
        assert isinstance(activity_dict, str)

    def test_persists_add_activity(self, adapter, dl):
        case = _make_case(dl)
        note = as_Note(name="Finding", content="details")
        dl.create(note)

        activity_id, _ = adapter.add_object_to_case(
            actor=_ACTOR,
            object_id=note.id_,
            case_id=case.id_,
        )

        assert dl.read(activity_id) is not None


class TestAnnounceVulnerabilityCase:
    def test_returns_activity_id(self, adapter, dl):
        case = _make_case(dl)

        activity_id = adapter.announce_vulnerability_case(
            case_id=case.id_,
            actor=_ACTOR,
            context_id=_CONTEXT_ID,
            to=[_PEER],
        )

        assert activity_id

    def test_persists_announce_activity(self, adapter, dl):
        case = _make_case(dl)

        activity_id = adapter.announce_vulnerability_case(
            case_id=case.id_,
            actor=_ACTOR,
            context_id=_CONTEXT_ID,
            to=[_PEER],
        )

        assert dl.read(activity_id) is not None


class TestRejectCaseProposal:
    """CP-05-004: the case actor service's refusal of a proposal."""

    @staticmethod
    def _proposal_dict(*, attributed_to: str = _PEER) -> dict:
        from vultron.wire.as2.vocab.objects.case_proposal import (
            as_CaseProposal,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        proposal = as_CaseProposal(
            attributed_to=attributed_to,
            object_=as_VulnerabilityReport(attributed_to=_PEER),
            target=_ACTOR,
        )
        return proposal.model_dump(by_alias=True, serialize_as_any=True)

    def test_returns_id_and_json(self, adapter):
        activity_id, activity_json = adapter.reject_case_proposal(
            actor=_ACTOR,
            proposal=self._proposal_dict(),
            to=[_PEER],
        )

        assert activity_id
        payload = json.loads(activity_json)
        assert payload["type"] == "Reject"
        assert payload["object"]["type"] == "CaseProposal"

    def test_persists_the_activity_and_the_proposal(self, adapter, dl):
        proposal = self._proposal_dict()

        activity_id, _ = adapter.reject_case_proposal(
            actor=_ACTOR, proposal=proposal, to=[_PEER]
        )

        # Storage dehydrates an inline Activity sub-field to its URI, so the
        # proposal has to be stored for the read-back to resolve it (AKM-03-001).
        assert dl.read(activity_id) is not None
        assert dl.read(proposal["id"]) is not None

    def test_read_back_keeps_the_proposal_inline(self, adapter, dl):
        proposal = self._proposal_dict()

        activity_id, _ = adapter.reject_case_proposal(
            actor=_ACTOR, proposal=proposal, to=[_PEER]
        )

        stored = dl.read(activity_id)
        assert not isinstance(
            stored.object_, str
        ), "a bare URI is unreadable to the vendor (AKM-03-001)"
        assert stored.object_.id_ == proposal["id"]

    def test_addresses_the_proposer_when_no_recipients_given(self, adapter):
        """The proposing vendor is the only party owed the refusal."""
        _, activity_json = adapter.reject_case_proposal(
            actor=_ACTOR, proposal=self._proposal_dict()
        )

        assert json.loads(activity_json)["to"] == [_PEER]

    def test_refuses_a_proposal_that_names_no_proposer(self, adapter):
        """attributed_to is required, so there is always a vendor to address.

        CP-01-003 makes the field mandatory on the wire model, which is why the
        adapter needs no separate "no recipient" guard: a proposal that could not
        be addressed never validates.
        """
        proposal = self._proposal_dict()
        proposal.pop("attributedTo", None)
        proposal.pop("attributed_to", None)

        with pytest.raises(ValidationError, match="attributedTo"):
            adapter.reject_case_proposal(actor=_ACTOR, proposal=proposal)

    def test_duplicate_proposal_does_not_abort_the_reject(self, adapter, dl):
        """A proposal already in the store is reused, not treated as an error."""
        proposal = self._proposal_dict()
        adapter.reject_case_proposal(
            actor=_ACTOR, proposal=proposal, to=[_PEER]
        )

        second_id, _ = adapter.reject_case_proposal(
            actor=_ACTOR, proposal=proposal, to=[_PEER]
        )

        assert dl.read(second_id) is not None
