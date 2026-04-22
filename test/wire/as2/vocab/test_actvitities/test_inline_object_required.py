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
    AddNoteToCaseActivity,
    AddReportToCaseActivity,
    AddStatusToCaseActivity,
    CreateCaseActivity,
    CreateCaseStatusActivity,
    OfferCaseOwnershipTransferActivity,
    RejectCaseOwnershipTransferActivity,
    RmAcceptInviteToCaseActivity,
    RmCloseCaseActivity,
    RmDeferCaseActivity,
    RmEngageCaseActivity,
    RmInviteToCaseActivity,
    RmRejectInviteToCaseActivity,
    UpdateCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
    AddStatusToParticipantActivity,
    CreateParticipantActivity,
    CreateStatusForParticipantActivity,
    RemoveParticipantFromCaseActivity,
)
from vultron.wire.as2.vocab.activities.embargo import (
    ActivateEmbargoActivity,
    AddEmbargoToCaseActivity,
    AnnounceEmbargoActivity,
    EmAcceptEmbargoActivity,
    EmProposeEmbargoActivity,
    EmRejectEmbargoActivity,
    RemoveEmbargoFromCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmCloseReportActivity,
    RmCreateReportActivity,
    RmInvalidateReportActivity,
    RmReadReportActivity,
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.activities.sync import (
    AnnounceLogEntryActivity,
    RejectLogEntryActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Person
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseStub,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

_ACTOR = as_Person(name="Alice")
_CASE = VulnerabilityCase(name="Test Case")
_REPORT = VulnerabilityReport(name="CVE-TEST-001")
_NOTE = as_Note(name="Test Note")
_STATUS = CaseStatus()
_PARTICIPANT_STATUS = ParticipantStatus(context=_CASE.id_)
_EMBARGO = EmbargoEvent(name="Embargo Event")
_PARTICIPANT = CaseParticipant(attributed_to=_ACTOR.id_)
_LOG_ENTRY = CaseLogEntry(
    case_id=_CASE.id_,
    log_object_id=_REPORT.id_,
    event_type="CREATE_REPORT",
)

_SUBMIT = RmSubmitReportActivity(actor=_ACTOR, object_=_REPORT)
_STUB = VulnerabilityCaseStub(id_=_CASE.id_)
_INVITE = RmInviteToCaseActivity(actor=_ACTOR, object_=_ACTOR, target=_STUB)
_PROPOSE = EmProposeEmbargoActivity(
    actor=_ACTOR,
    object_=EmbargoEvent(name="Embargo Event"),
    context=_CASE.id_,
)
_RECOMMEND = RecommendActorActivity(actor=_ACTOR, object_=_ACTOR, target=_CASE)
_OFFER_TRANSFER = OfferCaseOwnershipTransferActivity(
    actor=_ACTOR, object_=_CASE
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


class TestNoneObjectRejected(unittest.TestCase):
    """None and missing object_ must be rejected for all 37 INLINE-OBJ-C classes.

    These classes require ``object_`` at construction time (no ``None`` default)
    so that ``ActivityPattern._match_field`` can always inspect ``object_.type``
    for semantic dispatch (MV-09-003).
    """

    def _assert_none_rejected(self, cls, **kwargs):
        with pytest.raises(ValidationError):
            cls(actor=_ACTOR.id_, object_=None, **kwargs)

    def _assert_missing_rejected(self, cls, **kwargs):
        with pytest.raises(ValidationError):
            cls(actor=_ACTOR.id_, **kwargs)

    # --- report.py (6 classes) ---

    def test_rm_create_report_rejects_none(self):
        self._assert_none_rejected(RmCreateReportActivity)

    def test_rm_create_report_rejects_missing(self):
        self._assert_missing_rejected(RmCreateReportActivity)

    def test_rm_submit_report_rejects_none(self):
        self._assert_none_rejected(RmSubmitReportActivity)

    def test_rm_submit_report_rejects_missing(self):
        self._assert_missing_rejected(RmSubmitReportActivity)

    def test_rm_read_report_rejects_none(self):
        self._assert_none_rejected(RmReadReportActivity)

    def test_rm_read_report_rejects_missing(self):
        self._assert_missing_rejected(RmReadReportActivity)

    def test_rm_validate_report_rejects_none(self):
        self._assert_none_rejected(RmValidateReportActivity)

    def test_rm_validate_report_rejects_missing(self):
        self._assert_missing_rejected(RmValidateReportActivity)

    def test_rm_invalidate_report_rejects_none(self):
        self._assert_none_rejected(RmInvalidateReportActivity)

    def test_rm_invalidate_report_rejects_missing(self):
        self._assert_missing_rejected(RmInvalidateReportActivity)

    def test_rm_close_report_rejects_none(self):
        self._assert_none_rejected(RmCloseReportActivity)

    def test_rm_close_report_rejects_missing(self):
        self._assert_missing_rejected(RmCloseReportActivity)

    # --- case.py (14 classes, not RmInviteToCaseActivity) ---

    def test_add_report_to_case_rejects_none(self):
        self._assert_none_rejected(AddReportToCaseActivity)

    def test_add_report_to_case_rejects_missing(self):
        self._assert_missing_rejected(AddReportToCaseActivity)

    def test_add_status_to_case_rejects_none(self):
        self._assert_none_rejected(AddStatusToCaseActivity)

    def test_add_status_to_case_rejects_missing(self):
        self._assert_missing_rejected(AddStatusToCaseActivity)

    def test_create_case_rejects_none(self):
        self._assert_none_rejected(CreateCaseActivity)

    def test_create_case_rejects_missing(self):
        self._assert_missing_rejected(CreateCaseActivity)

    def test_create_case_status_rejects_none(self):
        self._assert_none_rejected(CreateCaseStatusActivity)

    def test_create_case_status_rejects_missing(self):
        self._assert_missing_rejected(CreateCaseStatusActivity)

    def test_add_note_to_case_rejects_none(self):
        self._assert_none_rejected(AddNoteToCaseActivity)

    def test_add_note_to_case_rejects_missing(self):
        self._assert_missing_rejected(AddNoteToCaseActivity)

    def test_update_case_rejects_none(self):
        self._assert_none_rejected(UpdateCaseActivity)

    def test_update_case_rejects_missing(self):
        self._assert_missing_rejected(UpdateCaseActivity)

    def test_rm_engage_case_rejects_none(self):
        self._assert_none_rejected(RmEngageCaseActivity)

    def test_rm_engage_case_rejects_missing(self):
        self._assert_missing_rejected(RmEngageCaseActivity)

    def test_rm_defer_case_rejects_none(self):
        self._assert_none_rejected(RmDeferCaseActivity)

    def test_rm_defer_case_rejects_missing(self):
        self._assert_missing_rejected(RmDeferCaseActivity)

    def test_rm_close_case_rejects_none(self):
        self._assert_none_rejected(RmCloseCaseActivity)

    def test_rm_close_case_rejects_missing(self):
        self._assert_missing_rejected(RmCloseCaseActivity)

    def test_offer_case_ownership_transfer_rejects_none(self):
        self._assert_none_rejected(OfferCaseOwnershipTransferActivity)

    def test_offer_case_ownership_transfer_rejects_missing(self):
        self._assert_missing_rejected(OfferCaseOwnershipTransferActivity)

    def test_accept_case_ownership_transfer_rejects_none(self):
        self._assert_none_rejected(AcceptCaseOwnershipTransferActivity)

    def test_accept_case_ownership_transfer_rejects_missing(self):
        self._assert_missing_rejected(AcceptCaseOwnershipTransferActivity)

    def test_reject_case_ownership_transfer_rejects_none(self):
        self._assert_none_rejected(RejectCaseOwnershipTransferActivity)

    def test_reject_case_ownership_transfer_rejects_missing(self):
        self._assert_missing_rejected(RejectCaseOwnershipTransferActivity)

    def test_rm_accept_invite_rejects_none(self):
        self._assert_none_rejected(RmAcceptInviteToCaseActivity)

    def test_rm_accept_invite_rejects_missing(self):
        self._assert_missing_rejected(RmAcceptInviteToCaseActivity)

    def test_rm_reject_invite_rejects_none(self):
        self._assert_none_rejected(RmRejectInviteToCaseActivity)

    def test_rm_reject_invite_rejects_missing(self):
        self._assert_missing_rejected(RmRejectInviteToCaseActivity)

    # --- actor.py (3 classes) ---

    def test_recommend_actor_rejects_none(self):
        self._assert_none_rejected(RecommendActorActivity)

    def test_recommend_actor_rejects_missing(self):
        self._assert_missing_rejected(RecommendActorActivity)

    def test_accept_actor_recommendation_rejects_none(self):
        self._assert_none_rejected(AcceptActorRecommendationActivity)

    def test_accept_actor_recommendation_rejects_missing(self):
        self._assert_missing_rejected(AcceptActorRecommendationActivity)

    def test_reject_actor_recommendation_rejects_none(self):
        self._assert_none_rejected(RejectActorRecommendationActivity)

    def test_reject_actor_recommendation_rejects_missing(self):
        self._assert_missing_rejected(RejectActorRecommendationActivity)

    # --- embargo.py (7 classes) ---

    def test_em_propose_embargo_rejects_none(self):
        self._assert_none_rejected(EmProposeEmbargoActivity)

    def test_em_propose_embargo_rejects_missing(self):
        self._assert_missing_rejected(EmProposeEmbargoActivity)

    def test_em_accept_embargo_rejects_none(self):
        self._assert_none_rejected(EmAcceptEmbargoActivity)

    def test_em_accept_embargo_rejects_missing(self):
        self._assert_missing_rejected(EmAcceptEmbargoActivity)

    def test_em_reject_embargo_rejects_none(self):
        self._assert_none_rejected(EmRejectEmbargoActivity)

    def test_em_reject_embargo_rejects_missing(self):
        self._assert_missing_rejected(EmRejectEmbargoActivity)

    def test_activate_embargo_rejects_none(self):
        self._assert_none_rejected(ActivateEmbargoActivity)

    def test_activate_embargo_rejects_missing(self):
        self._assert_missing_rejected(ActivateEmbargoActivity)

    def test_add_embargo_to_case_rejects_none(self):
        self._assert_none_rejected(AddEmbargoToCaseActivity)

    def test_add_embargo_to_case_rejects_missing(self):
        self._assert_missing_rejected(AddEmbargoToCaseActivity)

    def test_announce_embargo_rejects_none(self):
        self._assert_none_rejected(AnnounceEmbargoActivity)

    def test_announce_embargo_rejects_missing(self):
        self._assert_missing_rejected(AnnounceEmbargoActivity)

    def test_remove_embargo_from_case_rejects_none(self):
        self._assert_none_rejected(RemoveEmbargoFromCaseActivity)

    def test_remove_embargo_from_case_rejects_missing(self):
        self._assert_missing_rejected(RemoveEmbargoFromCaseActivity)

    # --- case_participant.py (5 classes) ---

    def test_create_participant_rejects_none(self):
        self._assert_none_rejected(CreateParticipantActivity)

    def test_create_participant_rejects_missing(self):
        self._assert_missing_rejected(CreateParticipantActivity)

    def test_create_status_for_participant_rejects_none(self):
        self._assert_none_rejected(CreateStatusForParticipantActivity)

    def test_create_status_for_participant_rejects_missing(self):
        self._assert_missing_rejected(CreateStatusForParticipantActivity)

    def test_add_status_to_participant_rejects_none(self):
        self._assert_none_rejected(AddStatusToParticipantActivity)

    def test_add_status_to_participant_rejects_missing(self):
        self._assert_missing_rejected(AddStatusToParticipantActivity)

    def test_add_participant_to_case_rejects_none(self):
        self._assert_none_rejected(AddParticipantToCaseActivity)

    def test_add_participant_to_case_rejects_missing(self):
        self._assert_missing_rejected(AddParticipantToCaseActivity)

    def test_remove_participant_from_case_rejects_none(self):
        self._assert_none_rejected(RemoveParticipantFromCaseActivity)

    def test_remove_participant_from_case_rejects_missing(self):
        self._assert_missing_rejected(RemoveParticipantFromCaseActivity)

    # --- sync.py (2 classes) ---

    def test_announce_log_entry_rejects_none(self):
        self._assert_none_rejected(AnnounceLogEntryActivity)

    def test_announce_log_entry_rejects_missing(self):
        self._assert_missing_rejected(AnnounceLogEntryActivity)

    def test_reject_log_entry_rejects_none(self):
        self._assert_none_rejected(RejectLogEntryActivity)

    def test_reject_log_entry_rejects_missing(self):
        self._assert_missing_rejected(RejectLogEntryActivity)


if __name__ == "__main__":
    unittest.main()
