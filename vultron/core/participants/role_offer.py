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

from vultron.core.models._helpers import _as_id
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import same_actor_id
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.enums.roles import CVDRole

#: The ``event_type`` of the entry that records an admitted role Offer.
OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE = "offer_case_participant_role"


def recorded_role_offer_entries(
    dl: CasePersistence, case_id: str
) -> list[CaseLedgerEntry]:
    """The case's ``offer_case_participant_role`` entries, oldest first."""
    return [
        entry
        for entry in recorded_entries_for_case(case_id=case_id, dl=dl)
        if entry.event_type == OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE
    ]


def recorded_role_offer(
    dl: CasePersistence, case_id: str, offer_id: str
) -> CaseLedgerEntry | None:
    """The entry that records the role Offer *offer_id*, or ``None``.

    A role Offer the ledger already records is a redelivery, not a new Offer
    (HP-01-003), when the entry names the same role and target
    (:func:`entry_names_role_offer`).
    """
    return next(
        (
            entry
            for entry in recorded_role_offer_entries(dl, case_id)
            if entry.log_object_id == offer_id
        ),
        None,
    )


def entry_names_role_offer(
    entry: CaseLedgerEntry, role: CVDRole, target_actor_id: str | None
) -> bool:
    """Return ``True`` when *entry* records an Offer of *role* to the target.

    An Offer that reuses a recorded Offer's id but names another role or
    target is not a redelivery of it (ID-02-001).
    """
    role_obj = entry.payload_snapshot.get("object")
    recorded_role = (
        role_obj.get("role") if isinstance(role_obj, dict) else None
    )
    recorded_target = _as_id(entry.payload_snapshot.get("target"))
    return (
        recorded_role == role.value
        and target_actor_id is not None
        and recorded_target is not None
        and same_actor_id(recorded_target, target_actor_id)
    )


def role_offer_forward_id(
    case_manager_id: str, case_id: str, offer_id: str
) -> str:
    """The id of the CASE_MANAGER's forward of the role Offer *offer_id*.

    Derived from the recorded Offer (ID-04-004, OX-06-002), so a redelivery
    of the Offer rebuilds the same forward, which the outbox does not queue
    twice while it is pending.
    """
    return derived_activity_id(
        "forward_case_participant_role", case_manager_id, case_id, offer_id
    )


__all__ = [
    "OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE",
    "entry_names_role_offer",
    "recorded_role_offer",
    "recorded_role_offer_entries",
    "role_offer_forward_id",
]
