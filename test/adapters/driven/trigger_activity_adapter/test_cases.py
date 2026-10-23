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

from test.support.case_owner import CASE_OWNER_ID
from test.support.embargo_register import activate, register
from vultron.adapters.driven.trigger_activity_adapter import _base
from vultron.adapters.driven.trigger_activity_adapter._base import (
    _to_wire_object,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.actor import VultronPerson
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.note import VultronNote
from vultron.errors import (
    VultronActivityConstructionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.object_types import (
    as_Article,
    as_Note,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_ACTOR = "https://example.org/actors/coordinator"
_PEER = "https://example.org/actors/vendor"
_CONTEXT_ID = "https://example.org/contexts/ctx-001"


def _make_case(dl) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, name="CVE-2025-001"
    )
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
            to=[_PEER],
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
            to=[_PEER],
        )

        assert dl.read(activity_id) is not None

    @pytest.mark.spec("PCR-08-005")
    def test_addresses_add_to_given_recipients(self, adapter, dl):
        case = _make_case(dl)
        note = as_Note(name="Finding", content="details")
        dl.create(note)

        activity_id, _ = adapter.add_object_to_case(
            actor=_ACTOR,
            object_id=note.id_,
            case_id=case.id_,
            to=[_PEER],
        )

        activity = dl.read(activity_id)
        assert activity is not None
        assert getattr(activity, "to", None) == [_PEER]


class TestAddObjectToCaseSemantics:
    """The sender-side refusal reads the Add as a receiver would (TRIG-10-001)."""

    @pytest.mark.parametrize(
        ("make_object", "semantics"),
        [
            pytest.param(
                lambda case_id: as_Note(name="N", content="c"),
                MessageSemantics.ADD_NOTE_TO_CASE,
                id="note",
            ),
            pytest.param(
                lambda case_id: as_VulnerabilityReport(name="R", content="c"),
                MessageSemantics.ADD_REPORT_TO_CASE,
                id="report",
            ),
        ],
    )
    @pytest.mark.spec("TRIG-10-001")
    def test_routable_type_returns_its_semantics(
        self, adapter, dl, make_object, semantics
    ):
        case = _make_case(dl)
        obj = make_object(case.id_)
        dl.create(obj)

        assert (
            adapter.add_object_to_case_semantics(
                object_id=obj.id_, case_id=case.id_
            )
            == semantics
        )

    @pytest.mark.parametrize(
        "make_object",
        [
            pytest.param(
                lambda case_id: as_Article(name="A", content="c"),
                id="no-add-pattern",
            ),
            pytest.param(
                lambda case_id: as_EmbargoEvent(
                    context=case_id, end_time=days_from_now_utc(45)
                ),
                id="embargo-event",
            ),
            pytest.param(
                lambda case_id: as_CaseParticipant(
                    attributed_to=_PEER, context=case_id
                ),
                id="case-participant",
            ),
            pytest.param(
                lambda case_id: as_CaseStatus(context=case_id),
                id="case-status",
            ),
            pytest.param(
                # Add(ParticipantStatus, <case URI>) matches the
                # participant-status pattern, whose target is permissive;
                # it is still not an addition to the case.
                lambda case_id: as_ParticipantStatus(context=case_id),
                id="participant-status",
            ),
        ],
    )
    @pytest.mark.spec("TRIG-10-001")
    def test_refused_type_raises_and_persists_nothing(
        self, adapter, dl, make_object
    ):
        case = _make_case(dl)
        obj = make_object(case.id_)
        dl.create(obj)
        before = len(dl.outbox_list())

        with pytest.raises(VultronValidationError, match="cannot be added"):
            adapter.add_object_to_case_semantics(
                object_id=obj.id_, case_id=case.id_
            )

        assert len(dl.outbox_list()) == before

    def test_missing_case_raises_not_found(self, adapter, dl):
        note = as_Note(name="N", content="c")
        dl.create(note)

        with pytest.raises(VultronNotFoundError):
            adapter.add_object_to_case_semantics(
                object_id=note.id_, case_id="urn:test:absent-case"
            )


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
                to=[_PEER],
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
                    to=[_PEER],
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
                    to=[_PEER],
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
                    to=[_PEER],
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
                to=[_PEER],
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
                    to=[_PEER],
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
        """A ``CoreObject`` is its own wire form (ARCH-25-003, ADR-0099).

        No counterpart is resolved by class name: that lookup matched
        ``WIRE_TYPE_MAP`` only by coincidence (``VulnerabilityCase``) and
        otherwise found the class itself through the core-map fallback
        (``VultronPerson``, ``VultronNote``), which ARCH-23-002 forbids and
        VM-06-008 no longer offers by default (ISSUE-3565).
        """
        assert _to_wire_object(core_obj, core_obj.id_) is core_obj

    @pytest.mark.spec("ARCH-23-002")
    def test_package_does_not_resolve_a_wire_counterpart(self):
        """No module in the package names a type registry or its lookups.

        A class-name counterpart lookup needs one of these to look the name up
        in, so naming none of them is what keeps ``_to_wire_object`` — and any
        sibling — from reintroducing it (ISSUE-3694). Import aliases are
        checked too, so ``import find_in_vocabulary as f`` is still caught.
        """
        import vultron.adapters.driven.trigger_activity_adapter as package
        from test.support.source_names import (
            REGISTRY_LOOKUP_NAMES,
            package_modules,
            referenced_names,
        )

        modules = package_modules(package)
        assert len(modules) > 1, "fixture must scan the package's submodules"

        found = {
            module.__name__: hits
            for module in modules
            if (hits := referenced_names(module) & REGISTRY_LOOKUP_NAMES)
        }
        assert found == {}


def _make_owned_case(dl) -> as_VulnerabilityCase:
    """A case with an owner, so it has a genesis hash to anchor its ledger."""
    case = as_VulnerabilityCase(name="CVE-2025-001", attributed_to=_ACTOR)
    dl.create(case)
    return case


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

    @pytest.mark.spec("SYNC-16-005")
    def test_an_empty_ledger_copy_names_the_genesis_position(
        self, adapter, dl
    ):
        """No entry yet: the copy is at index -1 and the case's genesis hash."""
        from vultron.adapters.outbox_sealed_body import read_sealed_body_dict

        case = _make_owned_case(dl)

        activity_id = adapter.announce_vulnerability_case(
            case_id=case.id_, actor=_ACTOR, context_id=case.id_, to=[_PEER]
        )

        body = read_sealed_body_dict(dl, activity_id)
        assert body is not None
        assert body["object"]["ledgerPosition"] == {
            "logIndex": -1,
            "entryHash": case.genesis_hash,
        }


class TestCaseOnTheWireCarriesItsParticipants:
    """CBT-05-005 / CBT-01-012 / AKM-02-004: a case put on the wire carries
    its participants (and reports) inline, not as ids.

    The recipient of a bootstrap ``Create`` or ``Announce`` stores each embedded
    participant as its own record; with ids alone it has no participant at
    ``RM.RECEIVED`` to validate and no CASE_MANAGER participant to route its
    reply to — the vendor's validate-report trigger failed with "no routable
    recipients" and "RM.START -> RM.VALID" in the rcvcv demo once the outbox
    stopped expanding them at delivery time (#3923).
    """

    @staticmethod
    def _case_with_participant_ids(dl):
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        case_id = "https://example.org/cases/wire-participants"
        manager = CaseParticipant(
            context=case_id,
            attributed_to=_ACTOR,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        vendor = CaseParticipant(
            context=case_id, attributed_to=_PEER, case_roles=[CVDRole.VENDOR]
        )
        report = as_VulnerabilityReport(name="CVE-2025-030", content="PoC")
        for obj in (manager, vendor, report):
            dl.create(obj)
        case = as_VulnerabilityCase(
            id_=case_id,
            name="CVE-2025-030",
            attributed_to=_ACTOR,
            case_participants=[str(manager.id_), str(vendor.id_)],
            actor_participant_index={
                _ACTOR: str(manager.id_),
                _PEER: str(vendor.id_),
            },
            vulnerability_reports=[str(report.id_)],
        )
        dl.create(case)
        return case, {str(manager.id_), str(vendor.id_)}, str(report.id_)

    @staticmethod
    def _sealed_case(dl, activity_id):
        from vultron.adapters.outbox_sealed_body import read_sealed_body_dict

        body = read_sealed_body_dict(dl, activity_id)
        assert body is not None
        return body["object"]

    @pytest.mark.spec("CBT-05-005")
    @pytest.mark.spec("CBT-01-007")
    def test_create_case_carries_participants_and_reports(self, adapter, dl):
        case, participant_ids, report_id = self._case_with_participant_ids(dl)

        activity_id, _ = adapter.create_case(
            case_id=case.id_, actor=_ACTOR, to=[_PEER]
        )

        wire_case = self._sealed_case(dl, activity_id)
        carried = wire_case["caseParticipants"]
        assert all(
            isinstance(p, dict) and p["type"] == "CaseParticipant"
            for p in carried
        ), carried
        assert {p["id"] for p in carried} == participant_ids
        [report] = wire_case["vulnerabilityReports"]
        assert report["id"] == report_id and report["content"] == "PoC"

    @pytest.mark.spec("SYNC-16-006")
    @pytest.mark.spec("PCR-02-004")
    def test_an_inline_participant_is_carried_as_the_store_holds_it(
        self, adapter, dl
    ):
        """A case that holds a participant inline carries the stored record,
        not the snapshot it took in: a replica that judges the copy current
        replaces its own participants with what the copy carries."""
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.enums.roles import CVDRole

        case_id = "https://example.org/cases/wire-inline-participant"
        snapshot = CaseParticipant(
            context=case_id, attributed_to=_PEER, case_roles=[CVDRole.VENDOR]
        )
        current = snapshot.model_copy(
            update={"case_roles": [CVDRole.VENDOR, CVDRole.COORDINATOR]}
        )
        dl.create(current)
        case = as_VulnerabilityCase(
            id_=case_id,
            name="CVE-2025-031",
            attributed_to=_ACTOR,
            case_participants=[snapshot],
        )
        dl.create(case)

        activity_id = adapter.announce_vulnerability_case(
            case_id=case_id, actor=_ACTOR, context_id=case_id, to=[_PEER]
        )

        [carried] = self._sealed_case(dl, activity_id)["caseParticipants"]
        assert carried["id"] == snapshot.id_
        assert set(carried["caseRoles"]) == {
            str(CVDRole.VENDOR),
            str(CVDRole.COORDINATOR),
        }

    @pytest.mark.spec("CBT-01-007")
    def test_announce_carries_participants(self, adapter, dl):
        case, participant_ids, _ = self._case_with_participant_ids(dl)

        activity_id = adapter.announce_vulnerability_case(
            case_id=case.id_, actor=_ACTOR, context_id=case.id_, to=[_PEER]
        )

        carried = self._sealed_case(dl, activity_id)["caseParticipants"]
        assert {p["id"] for p in carried} == participant_ids
        assert all(p["type"] == "CaseParticipant" for p in carried)

    def test_the_stored_case_still_holds_ids(self, adapter, dl):
        """Carrying is done on a copy: the store keeps its reference shape."""
        case, participant_ids, _ = self._case_with_participant_ids(dl)

        adapter.create_case(case_id=case.id_, actor=_ACTOR, to=[_PEER])

        stored = dl.read(case.id_)
        assert {
            p if isinstance(p, str) else p.id_
            for p in stored.case_participants
        } == participant_ids

    def test_a_participant_the_store_lacks_stays_an_id(
        self, adapter, dl, caplog
    ):
        case = as_VulnerabilityCase(
            name="CVE-2025-031",
            attributed_to=_ACTOR,
            case_participants=["https://example.org/participants/absent"],
        )
        dl.create(case)

        with caplog.at_level("WARNING"):
            activity_id, _ = adapter.create_case(
                case_id=case.id_, actor=_ACTOR, to=[_PEER]
            )

        assert self._sealed_case(dl, activity_id)["caseParticipants"] == [
            "https://example.org/participants/absent"
        ]
        assert any(
            "cannot be carried inline" in r.message for r in caplog.records
        )

    @pytest.mark.spec("EMB-18-003")
    def test_the_active_embargo_is_carried_inline(self, adapter, dl):
        case = as_VulnerabilityCase(name="CVE-2025-032", attributed_to=_ACTOR)
        embargo = EmbargoEvent(
            id_=f"{case.id_}/embargo_events/e1",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        dl.create(embargo)
        activate(case, embargo.id_)
        dl.create(case)

        activity_id, _ = adapter.create_case(
            case_id=case.id_, actor=_ACTOR, to=[_PEER]
        )

        (entry,) = self._sealed_case(dl, activity_id)["embargoRegister"]
        carried = entry["embargo"]
        assert isinstance(carried, dict) and carried["id"] == embargo.id_

    @pytest.mark.spec("EMB-18-003")
    def test_an_active_embargo_the_store_lacks_is_not_sent(self, adapter, dl):
        case = as_VulnerabilityCase(
            name="CVE-2025-033",
            attributed_to=_ACTOR,
            embargo_register=register(
                active="https://example.org/embargo_events/absent"
            ),
        )
        dl.create(case)

        with pytest.raises(VultronValidationError, match="EMB-18-003"):
            adapter.create_case(case_id=case.id_, actor=_ACTOR, to=[_PEER])

    @pytest.mark.spec("EMB-18-003")
    def test_an_active_embargo_naming_a_non_embargo_record_is_not_sent(
        self, adapter, dl
    ):
        note = VultronNote(content="not an embargo")
        dl.create(note)
        case = as_VulnerabilityCase(
            name="CVE-2025-034",
            attributed_to=_ACTOR,
            embargo_register=register(active=note.id_),
        )
        dl.create(case)

        with pytest.raises(VultronValidationError, match="EMB-18-003"):
            adapter.create_case(case_id=case.id_, actor=_ACTOR, to=[_PEER])

    @pytest.mark.spec("EMB-18-003")
    def test_an_active_embargo_that_cannot_be_projected_is_not_sent(
        self, adapter, dl
    ):
        case = as_VulnerabilityCase(name="CVE-2025-035", attributed_to=_ACTOR)
        embargo = EmbargoEvent(
            id_=f"{case.id_}/embargo_events/e1",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        dl.create(embargo)
        activate(case, embargo.id_)
        dl.create(case)
        real_to_wire = _base._to_wire

        def _refuse_embargo(obj, cls):
            if isinstance(obj, EmbargoEvent):
                raise TypeError("cannot project")
            return real_to_wire(obj, cls)

        with (
            patch.object(_base, "_to_wire", side_effect=_refuse_embargo),
            pytest.raises(VultronValidationError, match="wire shape"),
        ):
            adapter.create_case(case_id=case.id_, actor=_ACTOR, to=[_PEER])


class TestAnnounceVulnerabilityCaseEmbedsEveryReport:
    """AKM-02-004: the Announce embeds each report the case names, or is not
    sent.  The sealed body is delivered as built, so a bare reference here
    would reach a recipient that cannot resolve it."""

    def _case_naming(self, dl, report_ids):
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, name="CVE-2025-020"
        )
        case.vulnerability_reports.extend(report_ids)
        dl.create(case)
        return case

    @pytest.mark.spec("CBT-01-007")
    def test_a_report_the_store_lacks_refuses_the_announce(self, adapter, dl):
        case = self._case_naming(
            dl, ["https://example.org/reports/not-in-this-store"]
        )

        with pytest.raises(VultronNotFoundError):
            adapter.announce_vulnerability_case(
                case_id=case.id_,
                actor=_ACTOR,
                context_id=_CONTEXT_ID,
                to=[_PEER],
            )

        assert dl.outbox_list() == []

    @pytest.mark.spec("CBT-01-007")
    def test_a_held_report_is_embedded_inline(self, adapter, dl):
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = as_VulnerabilityReport(name="CVE-2025-020", content="PoC")
        dl.create(report)
        case = self._case_naming(dl, [report.id_])

        activity_id = adapter.announce_vulnerability_case(
            case_id=case.id_,
            actor=_ACTOR,
            context_id=_CONTEXT_ID,
            to=[_PEER],
        )

        from vultron.adapters.outbox_sealed_body import read_sealed_body_dict

        body = read_sealed_body_dict(dl, activity_id)
        assert body is not None
        [embedded] = body["object"]["vulnerabilityReports"]
        assert embedded["id"] == report.id_
        assert embedded["content"] == "PoC"


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
        # proposal has to be stored for the read-back to resolve it (AKM-03-003).
        assert dl.read(activity_id) is not None
        assert dl.read(proposal["id"]) is not None

    def test_read_back_keeps_the_proposal_inline(self, adapter, dl):
        proposal = self._proposal_dict()

        activity_id, _ = adapter.reject_case_proposal(
            actor=_ACTOR, proposal=proposal, to=[_PEER]
        )

        stored = dl.read(activity_id)
        assert not isinstance(stored.object_, str), (
            "a bare URI is unreadable to the vendor (AKM-03-003)"
        )
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
