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
"""Regression tests for INLINE-OBJ-B.

All Accept/Reject/TentativeReject activity classes must reject bare string IDs
in their ``object_`` field.  Passing a string where a typed activity object is
required must raise ``pydantic.ValidationError`` at construction time.
"""

import unittest

import pytest
from pydantic import ValidationError

from vultron.wire.as2.vocab.activities.actor import (
    AcceptActorRecommendationActivity,
    RecommendActorActivity,
    RejectActorRecommendationActivity,
)
from vultron.wire.as2.vocab.activities.case import (
    AcceptCaseOwnershipTransferActivity,
    OfferCaseOwnershipTransferActivity,
    RejectCaseOwnershipTransferActivity,
    RmAcceptInviteToCaseActivity,
    RmInviteToCaseActivity,
    RmRejectInviteToCaseActivity,
)
from vultron.wire.as2.vocab.activities.embargo import (
    EmAcceptEmbargoActivity,
    EmProposeEmbargoActivity,
    EmRejectEmbargoActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmCloseReportActivity,
    RmInvalidateReportActivity,
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.activities.sync import (
    AnnounceLogEntryActivity,
    RejectLogEntryActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Person
from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

_ACTOR = as_Person(name="Alice")
_CASE = VulnerabilityCase(name="Test Case")
_REPORT = VulnerabilityReport(name="CVE-TEST-001")

_SUBMIT = RmSubmitReportActivity(actor=_ACTOR, object_=_REPORT)
_INVITE = RmInviteToCaseActivity(actor=_ACTOR, object_=_ACTOR, target=_CASE)
_PROPOSE = EmProposeEmbargoActivity(
    actor=_ACTOR,
    object_=EmbargoEvent(name="Embargo Event"),
    context=_CASE.id_,
)
_RECOMMEND = RecommendActorActivity(actor=_ACTOR, object_=_ACTOR, target=_CASE)
_OFFER_TRANSFER = OfferCaseOwnershipTransferActivity(
    actor=_ACTOR, object_=_CASE
)
_LOG_ENTRY = CaseLogEntry(
    case_id=_CASE.id_,
    log_object_id=_REPORT.id_,
    event_type="CREATE_REPORT",
)


class TestBareStringObjectRejected(unittest.TestCase):
    """Bare string IDs must be rejected at construction time (INLINE-OBJ-B)."""

    def _assert_string_rejected(self, cls, fake_id="urn:uuid:fake-id-1234"):
        with pytest.raises(ValidationError):
            cls(actor=_ACTOR.id_, object_=fake_id)

    def test_accept_actor_recommendation_rejects_string(self):
        self._assert_string_rejected(AcceptActorRecommendationActivity)

    def test_reject_actor_recommendation_rejects_string(self):
        self._assert_string_rejected(RejectActorRecommendationActivity)

    def test_accept_case_ownership_transfer_rejects_string(self):
        self._assert_string_rejected(AcceptCaseOwnershipTransferActivity)

    def test_reject_case_ownership_transfer_rejects_string(self):
        self._assert_string_rejected(RejectCaseOwnershipTransferActivity)

    def test_rm_accept_invite_rejects_string(self):
        self._assert_string_rejected(RmAcceptInviteToCaseActivity)

    def test_rm_reject_invite_rejects_string(self):
        self._assert_string_rejected(RmRejectInviteToCaseActivity)

    def test_em_accept_embargo_rejects_string(self):
        self._assert_string_rejected(EmAcceptEmbargoActivity)

    def test_em_reject_embargo_rejects_string(self):
        self._assert_string_rejected(EmRejectEmbargoActivity)

    def test_rm_validate_report_rejects_string(self):
        self._assert_string_rejected(RmValidateReportActivity)

    def test_rm_invalidate_report_rejects_string(self):
        self._assert_string_rejected(RmInvalidateReportActivity)

    def test_rm_close_report_rejects_string(self):
        self._assert_string_rejected(RmCloseReportActivity)

    def test_reject_log_entry_rejects_string(self):
        self._assert_string_rejected(RejectLogEntryActivity)


class TestInlineTypedObjectAccepted(unittest.TestCase):
    """Inline typed objects must be accepted at construction time (INLINE-OBJ-B)."""

    def test_accept_actor_recommendation_accepts_typed(self):
        obj = AcceptActorRecommendationActivity(
            actor=_ACTOR.id_, object_=_RECOMMEND
        )
        assert isinstance(obj.object_, RecommendActorActivity)

    def test_reject_actor_recommendation_accepts_typed(self):
        obj = RejectActorRecommendationActivity(
            actor=_ACTOR.id_, object_=_RECOMMEND
        )
        assert isinstance(obj.object_, RecommendActorActivity)

    def test_accept_case_ownership_transfer_accepts_typed(self):
        obj = AcceptCaseOwnershipTransferActivity(
            actor=_ACTOR.id_, object_=_OFFER_TRANSFER
        )
        assert isinstance(obj.object_, OfferCaseOwnershipTransferActivity)

    def test_reject_case_ownership_transfer_accepts_typed(self):
        obj = RejectCaseOwnershipTransferActivity(
            actor=_ACTOR.id_, object_=_OFFER_TRANSFER
        )
        assert isinstance(obj.object_, OfferCaseOwnershipTransferActivity)

    def test_rm_accept_invite_accepts_typed(self):
        obj = RmAcceptInviteToCaseActivity(actor=_ACTOR.id_, object_=_INVITE)
        assert isinstance(obj.object_, RmInviteToCaseActivity)

    def test_rm_reject_invite_accepts_typed(self):
        obj = RmRejectInviteToCaseActivity(actor=_ACTOR.id_, object_=_INVITE)
        assert isinstance(obj.object_, RmInviteToCaseActivity)

    def test_em_accept_embargo_accepts_typed(self):
        obj = EmAcceptEmbargoActivity(actor=_ACTOR.id_, object_=_PROPOSE)
        assert isinstance(obj.object_, EmProposeEmbargoActivity)

    def test_em_reject_embargo_accepts_typed(self):
        obj = EmRejectEmbargoActivity(actor=_ACTOR.id_, object_=_PROPOSE)
        assert isinstance(obj.object_, EmProposeEmbargoActivity)

    def test_rm_validate_report_accepts_typed(self):
        obj = RmValidateReportActivity(actor=_ACTOR.id_, object_=_SUBMIT)
        assert isinstance(obj.object_, RmSubmitReportActivity)

    def test_rm_invalidate_report_accepts_typed(self):
        obj = RmInvalidateReportActivity(actor=_ACTOR.id_, object_=_SUBMIT)
        assert isinstance(obj.object_, RmSubmitReportActivity)

    def test_rm_close_report_accepts_typed(self):
        obj = RmCloseReportActivity(actor=_ACTOR.id_, object_=_SUBMIT)
        assert isinstance(obj.object_, RmSubmitReportActivity)

    def test_reject_log_entry_accepts_typed(self):
        obj = RejectLogEntryActivity(actor=_ACTOR.id_, object_=_LOG_ENTRY)
        assert isinstance(obj.object_, CaseLogEntry)

    def test_announce_log_entry_still_accepts_typed(self):
        """AnnounceLogEntryActivity should still accept a CaseLogEntry."""
        obj = AnnounceLogEntryActivity(actor=_ACTOR.id_, object_=_LOG_ENTRY)
        assert isinstance(obj.object_, CaseLogEntry)


if __name__ == "__main__":
    unittest.main()
