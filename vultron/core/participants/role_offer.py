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

"""The role Offers the CASE_MANAGER recorded in the case ledger (CM-33).

A role Offer is ``Offer(CaseParticipantRole)`` (ADR-0039).  The CASE_MANAGER
commits each one it admits as an ``offer_case_participant_role`` entry before
it forwards the Offer to the target (CM-33-001), so the ledger is the record
of which Offers it holds (CLP-11-001).
"""

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CasePersistence

#: The ``event_type`` of the entry that records an admitted role Offer.
OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE = "offer_case_participant_role"


def recorded_role_offer_entries(
    dl: CasePersistence, case_id: str
) -> list[CaseLedgerEntry]:
    """The case's ``offer_case_participant_role`` entries, oldest first."""
    entries = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
        and obj.case_id == case_id
        and obj.event_type == OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE
    ]
    entries.sort(key=lambda entry: entry.log_index)
    return entries


def is_recorded_role_offer(
    dl: CasePersistence, case_id: str, offer_id: str
) -> bool:
    """Return ``True`` when *offer_id* is already ledgered as a role Offer.

    A role Offer the ledger already records is a redelivery, not a new Offer
    (HP-01-003): it is neither committed nor forwarded again.
    """
    return any(
        entry.log_object_id == offer_id
        for entry in recorded_role_offer_entries(dl, case_id)
    )


__all__ = [
    "OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE",
    "is_recorded_role_offer",
    "recorded_role_offer_entries",
]
