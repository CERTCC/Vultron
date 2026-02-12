"""
Maps Message Semantics to their appropriate handlers
"""

from vultron.api.v2.backend import handlers as h
from vultron.enums import MessageSemantics
from vultron.types import BehaviorHandler


SEMANTICS_HANDLERS: dict[MessageSemantics, BehaviorHandler] = {
    MessageSemantics.CREATE_REPORT: h.create_report,
    MessageSemantics.SUBMIT_REPORT: h.submit_report,
    MessageSemantics.VALIDATE_REPORT: h.validate_report,
    MessageSemantics.INVALIDATE_REPORT: h.invalidate_report,
    MessageSemantics.ACK_REPORT: h.ack_report,
    MessageSemantics.CLOSE_REPORT: h.close_report,
    MessageSemantics.CREATE_CASE: h.create_case,
    MessageSemantics.ADD_REPORT_TO_CASE: h.add_report_to_case,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: h.suggest_actor_to_case,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: h.accept_suggest_actor_to_case,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: h.reject_suggest_actor_to_case,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: h.offer_case_ownership_transfer,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: h.accept_case_ownership_transfer,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: h.reject_case_ownership_transfer,
    MessageSemantics.INVITE_ACTOR_TO_CASE: h.invite_actor_to_case,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: h.accept_invite_actor_to_case,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: h.reject_invite_actor_to_case,
    MessageSemantics.CREATE_EMBARGO_EVENT: h.create_embargo_event,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: h.add_embargo_event_to_case,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: h.remove_embargo_event_from_case,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: h.announce_embargo_event_to_case,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: h.invite_to_embargo_on_case,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: h.accept_invite_to_embargo_on_case,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: h.reject_invite_to_embargo_on_case,
    MessageSemantics.CLOSE_CASE: h.close_case,
    MessageSemantics.CREATE_CASE_PARTICIPANT: h.create_case_participant,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: h.add_case_participant_to_case,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: h.remove_case_participant_from_case,
    MessageSemantics.CREATE_NOTE: h.create_note,
    MessageSemantics.ADD_NOTE_TO_CASE: h.add_note_to_case,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: h.remove_note_from_case,
    MessageSemantics.CREATE_CASE_STATUS: h.create_case_status,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: h.add_case_status_to_case,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: h.create_participant_status,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: h.add_participant_status_to_participant,
    MessageSemantics.UNKNOWN: h.unknown,
}
