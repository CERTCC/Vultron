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

"""Ledger event types for the CASE_MANAGER's own changes to a participant record.

Every state change the CASE_MANAGER makes emits a message (ADR-0114, ADR-0124).
Sending a stub Invite changes the case in two ways, and each is its own
entry: the Invite (a message to the invitee) and the creation of the inert
participant record that tracks the invitee.  Accepting the Invite changes the
record again, and each change is again its own entry.

- :data:`CREATE_CASE_PARTICIPANT_EVENT_TYPE` -- ``Create(CaseParticipant)``:
  the CASE_MANAGER created the record.  The entry carries the whole record
  (roles, statuses with their ids and times, ``joined``, consent rows).
- :data:`UPDATE_CASE_PARTICIPANT_EVENT_TYPE` -- ``Update(CaseParticipant)``:
  the CASE_MANAGER changed the record's ``joined`` mark or its consent rows.
  The entry carries the record as the CASE_MANAGER now holds it.
- a new ``ParticipantStatus`` (a vendor's VF, an RM closure) is the existing
  ``add_participant_status_to_participant`` entry.

A replica stores what the entry carries, as received (ADR-0103, CLP-15-007),
and derives nothing.
"""

from vultron.core.models.events.base import MessageSemantics

#: ``Create(CaseParticipant)`` -- the CASE_MANAGER created a participant record.
CREATE_CASE_PARTICIPANT_EVENT_TYPE = (
    MessageSemantics.CREATE_CASE_PARTICIPANT.value
)

#: ``Update(CaseParticipant)`` -- the CASE_MANAGER changed ``joined`` or consent.
UPDATE_CASE_PARTICIPANT_EVENT_TYPE = "update_case_participant"

__all__ = [
    "CREATE_CASE_PARTICIPANT_EVENT_TYPE",
    "UPDATE_CASE_PARTICIPANT_EVENT_TYPE",
]
