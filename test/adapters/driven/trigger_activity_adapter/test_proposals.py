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

"""Unit tests for TriggerActivityAdapter case-proposal methods (CP-01-010)."""

import json
from datetime import timedelta

import pytest

from test.support.received import (
    archive_delivered,
    archive_received,
    case_stub,
)
from vultron.core.models.actor import CoreActor, VultronOrganization
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    rm_invite_to_case_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_VENDOR = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/actors/case-actor"


def _vendor_profile(duration: timedelta) -> VultronOrganization:
    """The sender's own profile, with a published policy of *duration*."""
    return VultronOrganization(
        id_=_VENDOR,
        embargo_policy=EmbargoPolicy(
            actor_id=_VENDOR,
            inbox=f"{_VENDOR}/inbox",
            preferred_duration=duration,
        ),
    )


def _make_report(dl) -> as_VulnerabilityReport:
    report = as_VulnerabilityReport(name="CVE-2025-001", content="PoC details")
    dl.create(report)
    return report


class TestCreateCaseProposal:
    @pytest.mark.spec("CP-01-010")
    def test_the_create_carries_the_senders_stored_profile_inline(
        self, adapter, dl
    ):
        """The sender's own profile, policy included, is the Create's actor."""
        report = _make_report(dl)
        dl.save(_vendor_profile(timedelta(days=30)))

        _, blob = adapter.create_case_proposal(
            actor=_VENDOR, report_id=report.id_, case_actor_id=_CASE_ACTOR
        )

        actor = json.loads(blob)["actor"]
        assert isinstance(actor, dict)
        assert actor["id"] == _VENDOR
        assert actor["embargoPolicy"]["actorId"] == _VENDOR
        assert actor["embargoPolicy"]["preferredDuration"] == "P30D"
        assert len(list(dl.list_objects("CaseProposal"))) == 1

    @pytest.mark.spec("CP-01-010")
    def test_a_sender_with_no_stored_profile_is_refused_and_persists_nothing(
        self, adapter, dl
    ):
        """Without a profile the CASE_MANAGER would refuse the proposal, so it
        is not built — and no orphan proposal is left in the store."""
        report = _make_report(dl)

        with pytest.raises(ValueError, match="CP-01-010"):
            adapter.create_case_proposal(
                actor=_VENDOR, report_id=report.id_, case_actor_id=_CASE_ACTOR
            )

        assert list(dl.list_objects("CaseProposal")) == []

    @pytest.mark.spec("CP-01-010")
    def test_a_sender_whose_record_is_not_an_actor_is_refused(
        self, adapter, dl
    ):
        """A record under the sender's id that is not an actor profile is a
        fault, not a profile to send, and nothing is persisted."""
        report = _make_report(dl)
        dl.create(as_VulnerabilityReport(id_=_VENDOR, content="not an actor"))

        with pytest.raises(TypeError, match="CP-01-010"):
            adapter.create_case_proposal(
                actor=_VENDOR, report_id=report.id_, case_actor_id=_CASE_ACTOR
            )

        assert list(dl.list_objects("CaseProposal")) == []

    @pytest.mark.spec("CP-01-010")
    def test_the_sealed_create_parses_and_extracts_the_senders_policy(
        self, adapter, dl
    ):
        """What the sender seals is what the CASE_MANAGER's parse edge
        accepts and hands to core: the profile and its policy survive."""
        report = _make_report(dl)
        dl.save(_vendor_profile(timedelta(days=30)))

        _, blob = adapter.create_case_proposal(
            actor=_VENDOR, report_id=report.id_, case_actor_id=_CASE_ACTOR
        )
        event = extract_event(parse_activity(json.loads(blob)))

        profile = getattr(event, "proposer_profile", None)
        assert isinstance(profile, CoreActor)
        assert profile.id_ == _VENDOR
        assert profile.embargo_policy is not None
        assert profile.embargo_policy.preferred_duration == timedelta(days=30)


class TestCreateCaseProposalCarriesTheHeldOffer:
    """CP-01-008: the Offer travels inline when this store holds it."""

    _FINDER = "https://example.org/actors/finder"

    @pytest.mark.spec("CP-01-008")
    @pytest.mark.spec("DL-06-006")
    def test_a_received_offer_is_carried_from_its_archive(self, adapter, dl):

        report = _make_report(dl)
        dl.save(_vendor_profile(timedelta(days=30)))
        offer = rm_submit_report_activity(
            report, to=_VENDOR, actor=self._FINDER
        )
        archive_received(dl, offer)
        assert dl.read(offer.id_) is None

        _, blob = adapter.create_case_proposal(
            actor=_VENDOR,
            report_id=report.id_,
            case_actor_id=_CASE_ACTOR,
            offer_id=offer.id_,
            offer_actor_id=self._FINDER,
        )

        carried = json.loads(blob)["object"]["inReplyTo"]
        assert carried["id"] == offer.id_
        assert carried["object"]["id"] == report.id_

    @pytest.mark.spec("CP-01-008")
    @pytest.mark.spec("DL-06-004")
    def test_the_carried_offer_is_the_body_the_reporter_sent(
        self, adapter, dl
    ):
        """The inline Offer is the archived body verbatim, so a ``cc``, an
        ``endTime`` and a key no vocabulary names reach the case-actor as
        the Reporter sent them (ADR-0149)."""
        report = _make_report(dl)
        dl.save(_vendor_profile(timedelta(days=30)))
        offer = rm_submit_report_activity(
            report, to=_VENDOR, actor=self._FINDER
        )
        body = {
            **offer.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
                serialize_as_any=True,
            ),
            "cc": ["https://example.org/actors/watcher"],
            "endTime": "2031-01-01T00:00:00+00:00",
            "x-reporterNote": "please hurry",
        }
        archive_delivered(dl, body)

        _, blob = adapter.create_case_proposal(
            actor=_VENDOR,
            report_id=report.id_,
            case_actor_id=_CASE_ACTOR,
            offer_id=offer.id_,
            offer_actor_id=self._FINDER,
        )

        assert json.loads(blob)["object"]["inReplyTo"] == body

    @pytest.mark.spec("CP-01-007")
    def test_a_held_activity_that_is_not_a_report_offer_is_not_carried(
        self, adapter, dl, caplog
    ):
        """Only the bare provenance travels when the held activity under the
        Offer's id is some other kind of activity."""

        report = _make_report(dl)
        dl.save(_vendor_profile(timedelta(days=30)))
        other = rm_invite_to_case_activity(
            _VENDOR,
            target=case_stub("https://example.org/cases/other"),
            actor=self._FINDER,
        )
        archive_received(dl, other)

        with caplog.at_level("WARNING"):
            _, blob = adapter.create_case_proposal(
                actor=_VENDOR,
                report_id=report.id_,
                case_actor_id=_CASE_ACTOR,
                offer_id=other.id_,
                offer_actor_id=self._FINDER,
            )

        proposal = json.loads(blob)["object"]
        assert proposal.get("inReplyTo") is None
        assert proposal["offerId"] == other.id_
        assert "bare provenance only" in caplog.text
        # The archive was found and refused as a report Offer, not missed.
        assert "invalid offer data" in caplog.text
        assert dl.read(other.id_) is None

    @pytest.mark.spec("CP-01-007")
    def test_an_offer_this_store_does_not_hold_is_not_carried(
        self, adapter, dl, caplog
    ):
        report = _make_report(dl)
        dl.save(_vendor_profile(timedelta(days=30)))
        offer_id = "https://example.org/activities/offer-not-held"

        with caplog.at_level("WARNING"):
            _, blob = adapter.create_case_proposal(
                actor=_VENDOR,
                report_id=report.id_,
                case_actor_id=_CASE_ACTOR,
                offer_id=offer_id,
                offer_actor_id=self._FINDER,
            )

        proposal = json.loads(blob)["object"]
        assert proposal.get("inReplyTo") is None
        assert proposal["offerId"] == offer_id
        assert "bare provenance only" in caplog.text
        assert "invalid offer data" not in caplog.text
