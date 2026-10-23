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

"""Ledger semantic types for the CASE_MANAGER's own changes to the case roster.

The ledger holds the wire messages exchanged (ADR-0114).  Most changes to a
participant record are the effect of a message that already has its entry: the
invitee's ``Accept(Invite(stub))`` is the entry for the consent it signs and
the ``joined`` mark, and its ``Reject(Invite(stub))`` the entry for ``DECLINED``.
Creating the inert record is the CASE_MANAGER's own act, with no wire message
of its own, so it is the one new entry on the stub path:

- :data:`CREATE_CASE_PARTICIPANT_SEMANTIC_TYPE` -- ``Create(CaseParticipant)``:
  the CASE_MANAGER created the record.  The entry carries the whole record
  (roles, statuses with their ids and times, ``joined``, consent rows), and a
  replica stores it as received (ADR-0103, CLP-15-007).
- a new ``ParticipantStatus`` (a vendor's VF, an RM closure) is the existing
  ``add_participant_status_to_participant`` entry.

An ownership transfer is a received ``Accept`` whose consequences the
CASE_MANAGER records as its own entries after it (CLP-07-013, ADR-0124):

- :data:`UPDATE_CASE_PARTICIPANT_SEMANTIC_TYPE` -- ``Update(CaseParticipant)``:
  the CASE_MANAGER changed a participant record, such as a ``CASE_OWNER``
  role moving (CM-21-002, CM-21-003).  The entry carries the whole record as
  the CASE_MANAGER stored it, and a replica stores that copy.
- :data:`UPDATE_CASE_OWNER_SEMANTIC_TYPE` -- ``Update(VulnerabilityCase)``: the
  CASE_MANAGER changed the case's ``attributed_to`` to the new owner
  (CM-21-002).  The entry carries the case, and a replica copies its
  ``attributed_to``.

Each is a ``MessageSemantics`` member, so the registry labels the entry's
payload with it (ADR-0140); these names are its string values.
"""

from vultron.core.models.events.base import MessageSemantics

#: ``Create(CaseParticipant)`` -- the CASE_MANAGER created a participant record.
#: The registry recognizes it, but no received use case handles it (ADR-0140).
CREATE_CASE_PARTICIPANT_SEMANTIC_TYPE = (
    MessageSemantics.CREATE_CASE_PARTICIPANT.value
)

#: ``Update(CaseParticipant)`` -- the CASE_MANAGER changed a participant record.
#: The registry recognizes it, but no received use case handles it.
UPDATE_CASE_PARTICIPANT_SEMANTIC_TYPE = (
    MessageSemantics.UPDATE_CASE_PARTICIPANT.value
)

#: ``Update(VulnerabilityCase)`` -- the CASE_MANAGER named a new Case Owner in
#: the case's ``attributed_to``.  The registry recognizes it, but no received
#: use case handles it.
UPDATE_CASE_OWNER_SEMANTIC_TYPE = MessageSemantics.UPDATE_CASE_OWNER.value

__all__ = [
    "CREATE_CASE_PARTICIPANT_SEMANTIC_TYPE",
    "UPDATE_CASE_OWNER_SEMANTIC_TYPE",
    "UPDATE_CASE_PARTICIPANT_SEMANTIC_TYPE",
]
