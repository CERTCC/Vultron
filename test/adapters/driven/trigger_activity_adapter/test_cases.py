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
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.trigger_activity_adapter._base import (
    _to_wire_object,
)
from vultron.core.models.actor import VultronPerson
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.note import VultronNote
from vultron.errors import (
    VultronActivityConstructionError,
    VultronNotFoundError,
)
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


_TO_WIRE_OBJECT_PATH = (
    "vultron.adapters.driven.trigger_activity_adapter.cases._to_wire_object"
)


class TestAddObjectToCaseConversionBranch:
    """Tests for the core→wire conversion path in add_object_to_case."""

    def _patched_read(self, dl, fake_id, fake_obj):
        """Return side_effect that serves fake_obj for fake_id, real dl otherwise."""
        original = dl.read

        def _side_effect(id_):
            if id_ == fake_id:
                return fake_obj
            return original(id_)

        return _side_effect

    def test_core_object_converted_to_wire_type(self, adapter, dl):
        """Successful core→wire conversion: non-as_Object is looked up and from_core called."""
        from vultron.core.models.case import VulnerabilityCase

        case = _make_case(dl)
        fake_id = "urn:test:core-vuln-case-1"
        core_obj = VulnerabilityCase(attributed_to=_ACTOR)

        with patch.object(
            dl, "read", side_effect=self._patched_read(dl, fake_id, core_obj)
        ):
            activity_id, activity_dict = adapter.add_object_to_case(
                actor=_ACTOR,
                object_id=fake_id,
                case_id=case.id_,
            )

        assert activity_id
        assert isinstance(activity_dict, str)

    def test_non_as2_object_raises_construction_error(self, adapter, dl):
        """An object that is neither ``as_Object`` nor ``CoreObject`` is refused."""
        case = _make_case(dl)
        fake_id = "urn:test:unregistered-1"

        class _UnknownDomainObj:
            pass

        with patch.object(
            dl,
            "read",
            side_effect=self._patched_read(dl, fake_id, _UnknownDomainObj()),
        ):
            with pytest.raises(
                VultronActivityConstructionError,
                match="'_UnknownDomainObj' is not an AS2 object",
            ):
                adapter.add_object_to_case(
                    actor=_ACTOR,
                    object_id=fake_id,
                    case_id=case.id_,
                )

    def test_core_record_raises_construction_error(self, adapter, dl):
        """A ``CoreRecord`` bookkeeping type has no AS2 form and is refused.

        ``VultronOfferRecord`` declares a ``type`` and is registered in
        ``CORE_TYPE_MAP``, so the class-name lookup this replaced found it and
        let it through to ``as_Add`` (ISSUE-3565).
        """
        from vultron.core.models.offer_record import VultronOfferRecord

        case = _make_case(dl)
        fake_id = "urn:test:offer-record-1"
        record = VultronOfferRecord(
            id_=fake_id,
            offer_id="urn:test:offer-1",
            report_id="urn:test:report-1",
            offer_actor_id=_ACTOR,
        )

        with patch.object(
            dl, "read", side_effect=self._patched_read(dl, fake_id, record)
        ):
            with pytest.raises(
                VultronActivityConstructionError,
                match="'VultronOfferRecord' is not an AS2 object",
            ):
                adapter.add_object_to_case(
                    actor=_ACTOR,
                    object_id=fake_id,
                    case_id=case.id_,
                )

    def test_core_only_class_error_names_its_type(self, adapter, dl):
        """A core class registered as its own wire class, but with no wire
        ``type`` (the abstract ``CoreActor``), fails with its type named.

        ``as_Add`` admits any ``CoreObject`` under ADR-0099, so the refusal is
        ``_to_wire_object``'s, not a Pydantic rejection of the ``Add``.
        """
        from vultron.core.models import CoreActor

        case = _make_case(dl)
        fake_id = "urn:test:core-actor-1"
        core_actor = CoreActor(id_=fake_id, name="Some Actor")

        with patch.object(
            dl,
            "read",
            side_effect=self._patched_read(dl, fake_id, core_actor),
        ):
            with pytest.raises(
                VultronActivityConstructionError,
                match="'CoreActor' declares no wire type",
            ):
                adapter.add_object_to_case(
                    actor=_ACTOR,
                    object_id=fake_id,
                    case_id=case.id_,
                )

    def test_missing_object_raises_not_found(self, adapter, dl):
        """A dl.read miss is a not-found error, not a vocabulary error.

        Before #3437 the ``None`` fell through to the vocabulary lookup and
        surfaced as "no wire class registered for 'NoneType'".
        """
        case = _make_case(dl)

        with pytest.raises(VultronNotFoundError) as exc_info:
            adapter.add_object_to_case(
                actor=_ACTOR,
                object_id="urn:test:absent-1",
                case_id=case.id_,
            )

        assert exc_info.value.resource_id == "urn:test:absent-1"
        assert "NoneType" not in str(exc_info.value)

    def test_add_construction_failure_raises_construction_error(
        self, adapter, dl
    ):
        """A ValidationError from as_Add crosses the port as a VultronError."""
        case = _make_case(dl)
        note = as_Note(name="Finding", content="details")
        dl.create(note)

        class _NotAnAS2Object:
            pass

        with patch(_TO_WIRE_OBJECT_PATH, return_value=_NotAnAS2Object()):
            with pytest.raises(
                VultronActivityConstructionError,
                match="cannot be carried in an Add activity",
            ) as exc_info:
                adapter.add_object_to_case(
                    actor=_ACTOR,
                    object_id=note.id_,
                    case_id=case.id_,
                )

        assert isinstance(exc_info.value.__cause__, ValidationError)


class TestToWireObject:
    """Tests for the shared generic core→wire helper in ``_base``."""

    def test_none_raises_not_found(self):
        with pytest.raises(VultronNotFoundError, match="urn:test:absent-2"):
            _to_wire_object(None, "urn:test:absent-2")

    def test_as_object_returned_unchanged(self):
        note = as_Note(name="Finding", content="details")

        assert _to_wire_object(note, note.id_) is note

    @pytest.mark.spec("ARCH-23-002")
    @pytest.mark.parametrize(
        "core_obj",
        [
            pytest.param(
                VulnerabilityCase(attributed_to=_ACTOR),
                id="paired-VulnerabilityCase",
            ),
            pytest.param(
                VultronPerson(name="Pat"),
                id="class-name-differs-from-type-VultronPerson",
            ),
            pytest.param(
                VultronNote(content="details"), id="unpaired-VultronNote"
            ),
        ],
    )
    def test_core_object_is_carried_as_itself(self, core_obj):
        """A ``CoreObject`` is its own wire form (ADR-0099 detail 3).

        No counterpart is resolved by class name: that lookup matched
        ``WIRE_TYPE_MAP`` only by coincidence (``VulnerabilityCase``) and
        otherwise found the class itself through the core-map fallback
        (``VultronPerson``, ``VultronNote``), which ARCH-23-002 forbids and
        VM-06-008 no longer offers by default (ISSUE-3565).
        """
        assert _to_wire_object(core_obj, core_obj.id_) is core_obj


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

        The refusal surfaces as a ``VultronError``, not a raw
        ``ValidationError``. The proposal is peer-supplied, so a malformed one is
        a protocol outcome; ``BTBridge`` classifies any non-``VultronError``
        escaping a node as ``internal_error=True``, which would report another
        actor's bad message as a fault in this service.
        """
        proposal = self._proposal_dict()
        proposal.pop("attributedTo", None)
        proposal.pop("attributed_to", None)

        with pytest.raises(
            VultronActivityConstructionError, match="as_CaseProposal"
        ):
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
