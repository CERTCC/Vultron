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

from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

_ACTOR = "https://example.org/actors/coordinator"
_PEER = "https://example.org/actors/vendor"
_CONTEXT_ID = "https://example.org/contexts/ctx-001"


def _make_case(dl) -> VulnerabilityCase:
    case = VulnerabilityCase(name="CVE-2025-001")
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
        assert isinstance(activity_dict, dict)
        assert "id" in activity_dict

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
        assert isinstance(activity_dict, dict)

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
        assert isinstance(activity_dict, dict)

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
        assert isinstance(activity_dict, dict)

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
