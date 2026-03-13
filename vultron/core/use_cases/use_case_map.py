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

"""Routing table mapping ``MessageSemantics`` to core use-case callables.

This is domain knowledge — the mapping from a semantic intent to the use case
that handles it belongs in the core layer, not in the adapter layer.

``USE_CASE_MAP`` is the authoritative routing table.
``SEMANTICS_HANDLERS`` is a backward-compat alias used by
``vultron/api/v2/backend/handler_map.py``.
"""

from vultron.core.models.events import MessageSemantics
import vultron.core.use_cases.actor as _actor
import vultron.core.use_cases.case as _case
import vultron.core.use_cases.case_participant as _case_participant
import vultron.core.use_cases.embargo as _embargo
import vultron.core.use_cases.note as _note
import vultron.core.use_cases.report as _report
import vultron.core.use_cases.status as _status
import vultron.core.use_cases.unknown as _unknown

USE_CASE_MAP: dict = {
    MessageSemantics.CREATE_REPORT: _report.create_report,
    MessageSemantics.SUBMIT_REPORT: _report.submit_report,
    MessageSemantics.VALIDATE_REPORT: _report.validate_report,
    MessageSemantics.INVALIDATE_REPORT: _report.invalidate_report,
    MessageSemantics.ACK_REPORT: _report.ack_report,
    MessageSemantics.CLOSE_REPORT: _report.close_report,
    MessageSemantics.CREATE_CASE: _case.create_case,
    MessageSemantics.UPDATE_CASE: _case.update_case,
    MessageSemantics.ENGAGE_CASE: _case.engage_case,
    MessageSemantics.DEFER_CASE: _case.defer_case,
    MessageSemantics.ADD_REPORT_TO_CASE: _case.add_report_to_case,
    MessageSemantics.CLOSE_CASE: _case.close_case,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: _actor.suggest_actor_to_case,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: _actor.accept_suggest_actor_to_case,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: _actor.reject_suggest_actor_to_case,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: _actor.offer_case_ownership_transfer,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: _actor.accept_case_ownership_transfer,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: _actor.reject_case_ownership_transfer,
    MessageSemantics.INVITE_ACTOR_TO_CASE: _actor.invite_actor_to_case,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: _actor.accept_invite_actor_to_case,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: _actor.reject_invite_actor_to_case,
    MessageSemantics.CREATE_EMBARGO_EVENT: _embargo.create_embargo_event,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: _embargo.add_embargo_event_to_case,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: _embargo.remove_embargo_event_from_case,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: _embargo.announce_embargo_event_to_case,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: _embargo.invite_to_embargo_on_case,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: _embargo.accept_invite_to_embargo_on_case,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: _embargo.reject_invite_to_embargo_on_case,
    MessageSemantics.CREATE_CASE_PARTICIPANT: _case_participant.create_case_participant,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: _case_participant.add_case_participant_to_case,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: _case_participant.remove_case_participant_from_case,
    MessageSemantics.CREATE_NOTE: _note.create_note,
    MessageSemantics.ADD_NOTE_TO_CASE: _note.add_note_to_case,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: _note.remove_note_from_case,
    MessageSemantics.CREATE_CASE_STATUS: _status.create_case_status,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: _status.add_case_status_to_case,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: _status.create_participant_status,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: _status.add_participant_status_to_participant,
    MessageSemantics.UNKNOWN: _unknown.unknown,
}

# Backward-compat alias (adapter layer handler_map.py re-exports this).
SEMANTICS_HANDLERS = USE_CASE_MAP
