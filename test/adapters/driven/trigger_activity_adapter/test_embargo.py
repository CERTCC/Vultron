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

"""Unit tests for TriggerActivityAdapter embargo-domain methods."""

from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

_ACTOR = "https://example.org/actors/coordinator"
_PEER = "https://example.org/actors/vendor"
_CASE_ID = "https://example.org/cases/case-001"


def _make_embargo(dl) -> EmbargoEvent:
    embargo = EmbargoEvent()
    dl.create(embargo)
    return embargo


def _make_proposal(adapter, dl) -> tuple[str, str]:
    """Return (proposal_id, embargo_id)."""
    embargo = _make_embargo(dl)
    proposal_id, _ = adapter.propose_embargo(
        embargo_id=embargo.id_,
        case_id=_CASE_ID,
        actor=_ACTOR,
        to=[_PEER],
    )
    return proposal_id, embargo.id_


class TestProposeEmbargo:
    def test_returns_id_and_dict(self, adapter, dl):
        embargo = _make_embargo(dl)

        activity_id, activity_dict = adapter.propose_embargo(
            embargo_id=embargo.id_,
            case_id=_CASE_ID,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)
        assert "id" in activity_dict

    def test_persists_invite_activity(self, adapter, dl):
        embargo = _make_embargo(dl)

        activity_id, _ = adapter.propose_embargo(
            embargo_id=embargo.id_,
            case_id=_CASE_ID,
            actor=_ACTOR,
            to=[_PEER],
        )

        assert dl.read(activity_id) is not None


class TestAcceptEmbargo:
    def test_returns_id_and_dict(self, adapter, dl):
        proposal_id, _ = _make_proposal(adapter, dl)

        activity_id, activity_dict = adapter.accept_embargo(
            proposal_id=proposal_id,
            case_id=_CASE_ID,
            actor=_PEER,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)

    def test_persists_accept_activity(self, adapter, dl):
        proposal_id, _ = _make_proposal(adapter, dl)

        activity_id, _ = adapter.accept_embargo(
            proposal_id=proposal_id,
            case_id=_CASE_ID,
            actor=_PEER,
            to=[_ACTOR],
        )

        assert dl.read(activity_id) is not None


class TestRejectEmbargo:
    def test_returns_id_and_dict(self, adapter, dl):
        proposal_id, _ = _make_proposal(adapter, dl)

        activity_id, activity_dict = adapter.reject_embargo(
            proposal_id=proposal_id,
            case_id=_CASE_ID,
            actor=_PEER,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)

    def test_persists_reject_activity(self, adapter, dl):
        proposal_id, _ = _make_proposal(adapter, dl)

        activity_id, _ = adapter.reject_embargo(
            proposal_id=proposal_id,
            case_id=_CASE_ID,
            actor=_PEER,
            to=[_ACTOR],
        )

        assert dl.read(activity_id) is not None


class TestAnnounceEmbargo:
    def test_returns_id_and_dict(self, adapter, dl):
        embargo = _make_embargo(dl)

        activity_id, activity_dict = adapter.announce_embargo(
            embargo_id=embargo.id_,
            case_id=_CASE_ID,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)

    def test_persists_announce_activity(self, adapter, dl):
        embargo = _make_embargo(dl)

        activity_id, _ = adapter.announce_embargo(
            embargo_id=embargo.id_,
            case_id=_CASE_ID,
            actor=_ACTOR,
            to=[_PEER],
        )

        assert dl.read(activity_id) is not None


class TestTerminateEmbargo:
    def test_returns_id_and_dict(self, adapter, dl):
        embargo = _make_embargo(dl)

        activity_id, activity_dict = adapter.terminate_embargo(
            embargo_id=embargo.id_,
            case_id=_CASE_ID,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)

    def test_persists_remove_activity(self, adapter, dl):
        embargo = _make_embargo(dl)

        activity_id, _ = adapter.terminate_embargo(
            embargo_id=embargo.id_,
            case_id=_CASE_ID,
            actor=_ACTOR,
            to=[_PEER],
        )

        assert dl.read(activity_id) is not None
