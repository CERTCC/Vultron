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
    _AcceptActorRecommendationActivity,
    _RecommendActorActivity,
    _RejectActorRecommendationActivity,
)
from vultron.wire.as2.vocab.activities.case import (
    _AcceptCaseOwnershipTransferActivity,
    _AddNoteToCaseActivity,
    _AddReportToCaseActivity,
    _AddStatusToCaseActivity,
    _CreateCaseActivity,
    _CreateCaseStatusActivity,
    _OfferCaseOwnershipTransferActivity,
    _RejectCaseOwnershipTransferActivity,
    _RmAcceptInviteToCaseActivity,
    _RmCloseCaseActivity,
    _RmDeferCaseActivity,
    _RmEngageCaseActivity,
    _RmInviteToCaseActivity,
    _RmRejectInviteToCaseActivity,
    _UpdateCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddParticipantToCaseActivity,
    _AddStatusToParticipantActivity,
    _CreateParticipantActivity,
    _CreateStatusForParticipantActivity,
    _RemoveParticipantFromCaseActivity,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _ActivateEmbargoActivity,
    _AddEmbargoToCaseActivity,
    _AnnounceEmbargoActivity,
    _EmAcceptEmbargoActivity,
    _EmProposeEmbargoActivity,
    _EmRejectEmbargoActivity,
    _RemoveEmbargoFromCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    _RmCloseReportActivity,
    _RmCreateReportActivity,
    _RmInvalidateReportActivity,
    _RmReadReportActivity,
    _RmSubmitReportActivity,
    _RmValidateReportActivity,
)
from vultron.wire.as2.vocab.activities.sync import (
    _AnnounceLogEntryActivity,
    _RejectLogEntryActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Block,
    as_Create,
    as_Delete,
    as_Dislike,
    as_Flag,
    as_Follow,
    as_Ignore,
    as_Invite,
    as_Join,
    as_Leave,
    as_Like,
    as_Listen,
    as_Move,
    as_Offer,
    as_Read,
    as_Reject,
    as_Remove,
    as_TentativeAccept,
    as_TentativeReject,
    as_TransitiveActivity,
    as_Undo,
    as_Update,
    as_View,
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

_SUBMIT = _RmSubmitReportActivity(actor=_ACTOR, object_=_REPORT)
_STUB = VulnerabilityCaseStub(id_=_CASE.id_)
_INVITE = _RmInviteToCaseActivity(actor=_ACTOR, object_=_ACTOR, target=_STUB)
_PROPOSE = _EmProposeEmbargoActivity(
    actor=_ACTOR,
    object_=EmbargoEvent(name="Embargo Event"),
    context=_CASE.id_,
)
_RECOMMEND = _RecommendActorActivity(
    actor=_ACTOR, object_=_ACTOR, target=_CASE
)
_OFFER_TRANSFER = _OfferCaseOwnershipTransferActivity(
    actor=_ACTOR, object_=_CASE
)
_GENERIC_TRANSITIVE_CLASSES = (
    as_TransitiveActivity,
    as_Like,
    as_Ignore,
    as_Block,
    as_Offer,
    as_Invite,
    as_Flag,
    as_Remove,
    as_Undo,
    as_Create,
    as_Delete,
    as_Move,
    as_Add,
    as_Join,
    as_Update,
    as_Listen,
    as_Leave,
    as_Announce,
    as_Follow,
    as_Accept,
    as_TentativeAccept,
    as_View,
    as_Dislike,
    as_Reject,
    as_TentativeReject,
    as_Read,
)


class TestBareStringObjectRejected(unittest.TestCase):
    """Bare string IDs must be rejected at construction time (INLINE-OBJ-B)."""

    def _assert_string_rejected(self, cls, fake_id="urn:uuid:fake-id-1234"):
        with pytest.raises(ValidationError):
            cls(actor=_ACTOR.id_, object_=fake_id)

    def test_accept_actor_recommendation_rejects_string(self):
        self._assert_string_rejected(_AcceptActorRecommendationActivity)

    def test_reject_actor_recommendation_rejects_string(self):
        self._assert_string_rejected(_RejectActorRecommendationActivity)

    def test_accept_case_ownership_transfer_rejects_string(self):
        self._assert_string_rejected(_AcceptCaseOwnershipTransferActivity)

    def test_reject_case_ownership_transfer_rejects_string(self):
        self._assert_string_rejected(_RejectCaseOwnershipTransferActivity)

    def test_rm_accept_invite_rejects_string(self):
        self._assert_string_rejected(_RmAcceptInviteToCaseActivity)

    def test_rm_reject_invite_rejects_string(self):
        self._assert_string_rejected(_RmRejectInviteToCaseActivity)

    def test_em_accept_embargo_rejects_string(self):
        self._assert_string_rejected(_EmAcceptEmbargoActivity)

    def test_em_reject_embargo_rejects_string(self):
        self._assert_string_rejected(_EmRejectEmbargoActivity)

    def test_rm_validate_report_rejects_string(self):
        self._assert_string_rejected(_RmValidateReportActivity)

    def test_rm_invalidate_report_rejects_string(self):
        self._assert_string_rejected(_RmInvalidateReportActivity)

    def test_rm_close_report_rejects_string(self):
        self._assert_string_rejected(_RmCloseReportActivity)

    def test_reject_log_entry_rejects_string(self):
        self._assert_string_rejected(_RejectLogEntryActivity)


class TestInlineTypedObjectAccepted(unittest.TestCase):
    """Inline typed objects must be accepted at construction time (INLINE-OBJ-B)."""

    def test_accept_actor_recommendation_accepts_typed(self):
        obj = _AcceptActorRecommendationActivity(
            actor=_ACTOR.id_, object_=_RECOMMEND
        )
        assert isinstance(obj.object_, _RecommendActorActivity)

    def test_reject_actor_recommendation_accepts_typed(self):
        obj = _RejectActorRecommendationActivity(
            actor=_ACTOR.id_, object_=_RECOMMEND
        )
        assert isinstance(obj.object_, _RecommendActorActivity)

    def test_accept_case_ownership_transfer_accepts_typed(self):
        obj = _AcceptCaseOwnershipTransferActivity(
            actor=_ACTOR.id_, object_=_OFFER_TRANSFER
        )
        assert isinstance(obj.object_, _OfferCaseOwnershipTransferActivity)

    def test_reject_case_ownership_transfer_accepts_typed(self):
        obj = _RejectCaseOwnershipTransferActivity(
            actor=_ACTOR.id_, object_=_OFFER_TRANSFER
        )
        assert isinstance(obj.object_, _OfferCaseOwnershipTransferActivity)

    def test_rm_accept_invite_accepts_typed(self):
        obj = _RmAcceptInviteToCaseActivity(actor=_ACTOR.id_, object_=_INVITE)
        assert isinstance(obj.object_, _RmInviteToCaseActivity)

    def test_rm_reject_invite_accepts_typed(self):
        obj = _RmRejectInviteToCaseActivity(actor=_ACTOR.id_, object_=_INVITE)
        assert isinstance(obj.object_, _RmInviteToCaseActivity)

    def test_em_accept_embargo_accepts_typed(self):
        obj = _EmAcceptEmbargoActivity(actor=_ACTOR.id_, object_=_PROPOSE)
        assert isinstance(obj.object_, _EmProposeEmbargoActivity)

    def test_em_reject_embargo_accepts_typed(self):
        obj = _EmRejectEmbargoActivity(actor=_ACTOR.id_, object_=_PROPOSE)
        assert isinstance(obj.object_, _EmProposeEmbargoActivity)

    def test_rm_validate_report_accepts_typed(self):
        obj = _RmValidateReportActivity(actor=_ACTOR.id_, object_=_SUBMIT)
        assert isinstance(obj.object_, _RmSubmitReportActivity)

    def test_rm_invalidate_report_accepts_typed(self):
        obj = _RmInvalidateReportActivity(actor=_ACTOR.id_, object_=_SUBMIT)
        assert isinstance(obj.object_, _RmSubmitReportActivity)

    def test_rm_close_report_accepts_typed(self):
        obj = _RmCloseReportActivity(actor=_ACTOR.id_, object_=_SUBMIT)
        assert isinstance(obj.object_, _RmSubmitReportActivity)

    def test_reject_log_entry_accepts_typed(self):
        obj = _RejectLogEntryActivity(actor=_ACTOR.id_, object_=_LOG_ENTRY)
        assert isinstance(obj.object_, CaseLogEntry)

    def test_announce_log_entry_still_accepts_typed(self):
        """_AnnounceLogEntryActivity should still accept a CaseLogEntry."""
        obj = _AnnounceLogEntryActivity(actor=_ACTOR.id_, object_=_LOG_ENTRY)
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
        self._assert_none_rejected(_RmCreateReportActivity)

    def test_rm_create_report_rejects_missing(self):
        self._assert_missing_rejected(_RmCreateReportActivity)

    def test_rm_submit_report_rejects_none(self):
        self._assert_none_rejected(_RmSubmitReportActivity)

    def test_rm_submit_report_rejects_missing(self):
        self._assert_missing_rejected(_RmSubmitReportActivity)

    def test_rm_read_report_rejects_none(self):
        self._assert_none_rejected(_RmReadReportActivity)

    def test_rm_read_report_rejects_missing(self):
        self._assert_missing_rejected(_RmReadReportActivity)

    def test_rm_validate_report_rejects_none(self):
        self._assert_none_rejected(_RmValidateReportActivity)

    def test_rm_validate_report_rejects_missing(self):
        self._assert_missing_rejected(_RmValidateReportActivity)

    def test_rm_invalidate_report_rejects_none(self):
        self._assert_none_rejected(_RmInvalidateReportActivity)

    def test_rm_invalidate_report_rejects_missing(self):
        self._assert_missing_rejected(_RmInvalidateReportActivity)

    def test_rm_close_report_rejects_none(self):
        self._assert_none_rejected(_RmCloseReportActivity)

    def test_rm_close_report_rejects_missing(self):
        self._assert_missing_rejected(_RmCloseReportActivity)

    # --- case.py (14 classes, not _RmInviteToCaseActivity) ---

    def test_add_report_to_case_rejects_none(self):
        self._assert_none_rejected(_AddReportToCaseActivity)

    def test_add_report_to_case_rejects_missing(self):
        self._assert_missing_rejected(_AddReportToCaseActivity)

    def test_add_status_to_case_rejects_none(self):
        self._assert_none_rejected(_AddStatusToCaseActivity)

    def test_add_status_to_case_rejects_missing(self):
        self._assert_missing_rejected(_AddStatusToCaseActivity)

    def test_create_case_rejects_none(self):
        self._assert_none_rejected(_CreateCaseActivity)

    def test_create_case_rejects_missing(self):
        self._assert_missing_rejected(_CreateCaseActivity)

    def test_create_case_status_rejects_none(self):
        self._assert_none_rejected(_CreateCaseStatusActivity)

    def test_create_case_status_rejects_missing(self):
        self._assert_missing_rejected(_CreateCaseStatusActivity)

    def test_add_note_to_case_rejects_none(self):
        self._assert_none_rejected(_AddNoteToCaseActivity)

    def test_add_note_to_case_rejects_missing(self):
        self._assert_missing_rejected(_AddNoteToCaseActivity)

    def test_update_case_rejects_none(self):
        self._assert_none_rejected(_UpdateCaseActivity)

    def test_update_case_rejects_missing(self):
        self._assert_missing_rejected(_UpdateCaseActivity)

    def test_rm_engage_case_rejects_none(self):
        self._assert_none_rejected(_RmEngageCaseActivity)

    def test_rm_engage_case_rejects_missing(self):
        self._assert_missing_rejected(_RmEngageCaseActivity)

    def test_rm_defer_case_rejects_none(self):
        self._assert_none_rejected(_RmDeferCaseActivity)

    def test_rm_defer_case_rejects_missing(self):
        self._assert_missing_rejected(_RmDeferCaseActivity)

    def test_rm_close_case_rejects_none(self):
        self._assert_none_rejected(_RmCloseCaseActivity)

    def test_rm_close_case_rejects_missing(self):
        self._assert_missing_rejected(_RmCloseCaseActivity)

    def test_offer_case_ownership_transfer_rejects_none(self):
        self._assert_none_rejected(_OfferCaseOwnershipTransferActivity)

    def test_offer_case_ownership_transfer_rejects_missing(self):
        self._assert_missing_rejected(_OfferCaseOwnershipTransferActivity)

    def test_accept_case_ownership_transfer_rejects_none(self):
        self._assert_none_rejected(_AcceptCaseOwnershipTransferActivity)

    def test_accept_case_ownership_transfer_rejects_missing(self):
        self._assert_missing_rejected(_AcceptCaseOwnershipTransferActivity)

    def test_reject_case_ownership_transfer_rejects_none(self):
        self._assert_none_rejected(_RejectCaseOwnershipTransferActivity)

    def test_reject_case_ownership_transfer_rejects_missing(self):
        self._assert_missing_rejected(_RejectCaseOwnershipTransferActivity)

    def test_rm_accept_invite_rejects_none(self):
        self._assert_none_rejected(_RmAcceptInviteToCaseActivity)

    def test_rm_accept_invite_rejects_missing(self):
        self._assert_missing_rejected(_RmAcceptInviteToCaseActivity)

    def test_rm_reject_invite_rejects_none(self):
        self._assert_none_rejected(_RmRejectInviteToCaseActivity)

    def test_rm_reject_invite_rejects_missing(self):
        self._assert_missing_rejected(_RmRejectInviteToCaseActivity)

    # --- actor.py (3 classes) ---

    def test_recommend_actor_rejects_none(self):
        self._assert_none_rejected(_RecommendActorActivity)

    def test_recommend_actor_rejects_missing(self):
        self._assert_missing_rejected(_RecommendActorActivity)

    def test_accept_actor_recommendation_rejects_none(self):
        self._assert_none_rejected(_AcceptActorRecommendationActivity)

    def test_accept_actor_recommendation_rejects_missing(self):
        self._assert_missing_rejected(_AcceptActorRecommendationActivity)

    def test_reject_actor_recommendation_rejects_none(self):
        self._assert_none_rejected(_RejectActorRecommendationActivity)

    def test_reject_actor_recommendation_rejects_missing(self):
        self._assert_missing_rejected(_RejectActorRecommendationActivity)

    # --- embargo.py (7 classes) ---

    def test_em_propose_embargo_rejects_none(self):
        self._assert_none_rejected(_EmProposeEmbargoActivity)

    def test_em_propose_embargo_rejects_missing(self):
        self._assert_missing_rejected(_EmProposeEmbargoActivity)

    def test_em_accept_embargo_rejects_none(self):
        self._assert_none_rejected(_EmAcceptEmbargoActivity)

    def test_em_accept_embargo_rejects_missing(self):
        self._assert_missing_rejected(_EmAcceptEmbargoActivity)

    def test_em_reject_embargo_rejects_none(self):
        self._assert_none_rejected(_EmRejectEmbargoActivity)

    def test_em_reject_embargo_rejects_missing(self):
        self._assert_missing_rejected(_EmRejectEmbargoActivity)

    def test_activate_embargo_rejects_none(self):
        self._assert_none_rejected(_ActivateEmbargoActivity)

    def test_activate_embargo_rejects_missing(self):
        self._assert_missing_rejected(_ActivateEmbargoActivity)

    def test_add_embargo_to_case_rejects_none(self):
        self._assert_none_rejected(_AddEmbargoToCaseActivity)

    def test_add_embargo_to_case_rejects_missing(self):
        self._assert_missing_rejected(_AddEmbargoToCaseActivity)

    def test_announce_embargo_rejects_none(self):
        self._assert_none_rejected(_AnnounceEmbargoActivity)

    def test_announce_embargo_rejects_missing(self):
        self._assert_missing_rejected(_AnnounceEmbargoActivity)

    def test_remove_embargo_from_case_rejects_none(self):
        self._assert_none_rejected(_RemoveEmbargoFromCaseActivity)

    def test_remove_embargo_from_case_rejects_missing(self):
        self._assert_missing_rejected(_RemoveEmbargoFromCaseActivity)

    # --- case_participant.py (5 classes) ---

    def test_create_participant_rejects_none(self):
        self._assert_none_rejected(_CreateParticipantActivity)

    def test_create_participant_rejects_missing(self):
        self._assert_missing_rejected(_CreateParticipantActivity)

    def test_create_status_for_participant_rejects_none(self):
        self._assert_none_rejected(_CreateStatusForParticipantActivity)

    def test_create_status_for_participant_rejects_missing(self):
        self._assert_missing_rejected(_CreateStatusForParticipantActivity)

    def test_add_status_to_participant_rejects_none(self):
        self._assert_none_rejected(_AddStatusToParticipantActivity)

    def test_add_status_to_participant_rejects_missing(self):
        self._assert_missing_rejected(_AddStatusToParticipantActivity)

    def test_add_participant_to_case_rejects_none(self):
        self._assert_none_rejected(_AddParticipantToCaseActivity)

    def test_add_participant_to_case_rejects_missing(self):
        self._assert_missing_rejected(_AddParticipantToCaseActivity)

    def test_remove_participant_from_case_rejects_none(self):
        self._assert_none_rejected(_RemoveParticipantFromCaseActivity)

    def test_remove_participant_from_case_rejects_missing(self):
        self._assert_missing_rejected(_RemoveParticipantFromCaseActivity)

    # --- sync.py (2 classes) ---

    def test_announce_log_entry_rejects_none(self):
        self._assert_none_rejected(_AnnounceLogEntryActivity)

    def test_announce_log_entry_rejects_missing(self):
        self._assert_missing_rejected(_AnnounceLogEntryActivity)

    def test_reject_log_entry_rejects_none(self):
        self._assert_none_rejected(_RejectLogEntryActivity)

    def test_reject_log_entry_rejects_missing(self):
        self._assert_missing_rejected(_RejectLogEntryActivity)


class TestGenericTransitiveActivitiesRequireObject(unittest.TestCase):
    """All transitive AS2 activities must require object_ at construction."""

    def _assert_none_rejected(self, cls, **kwargs):
        with pytest.raises(ValidationError):
            cls(actor=_ACTOR.id_, object_=None, **kwargs)

    def _assert_missing_rejected(self, cls, **kwargs):
        with pytest.raises(ValidationError):
            cls(actor=_ACTOR.id_, **kwargs)

    def test_generic_transitive_classes_reject_none(self):
        for cls in _GENERIC_TRANSITIVE_CLASSES:
            with self.subTest(cls=cls.__name__):
                self._assert_none_rejected(cls)

    def test_generic_transitive_classes_reject_missing(self):
        for cls in _GENERIC_TRANSITIVE_CLASSES:
            with self.subTest(cls=cls.__name__):
                self._assert_missing_rejected(cls)

    def test_rm_invite_to_case_rejects_none(self):
        self._assert_none_rejected(_RmInviteToCaseActivity, target=_STUB)

    def test_rm_invite_to_case_rejects_missing(self):
        self._assert_missing_rejected(_RmInviteToCaseActivity, target=_STUB)


if __name__ == "__main__":
    unittest.main()
