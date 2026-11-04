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

"""Sender standing: who may act on a case (CM-23-018, CM-23-054).

:func:`may_act_on_case` is the one predicate behind the
``ACTIVE_PARTICIPANT`` sender standing, so a sender may act on a case exactly
when it would be sent its content.
"""

from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.recipients.roster import (
    _receives_case_content,
    listed_participant_record,
)
from vultron.core.ports.case_persistence import CasePersistence


# ---------------------------------------------------------------------------
# Sender standing: who may act on a case (CM-23-018)
# ---------------------------------------------------------------------------
def may_act_on_case(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *actor_id* may act on *case* as a sender (CM-23-018).

    The one predicate behind the ``ACTIVE_PARTICIPANT`` sender standing
    (HP-01-009): every guard for that standing asks it.  The guards
    themselves stay in the sender-entitlement module (HP-01-007); the
    predicate lives here, beside the recipient test it shares, so a sender
    may act exactly when it would be sent the case's content.  The
    sender is an active participant (CM-10-004) whose closure is not
    recorded, the same test :func:`case_content_recipients` applies to a
    recipient (:func:`_receives_case_content`).  No actor acts on content it
    may not see: an inert or removed participant is refused, and so is a
    participant at RM ``CLOSED``, which has left the case.

    Two kinds of act stay open to a closed sender, and neither asks this
    predicate.  Its ``Reject(CaseLedgerEntry)`` is checked with
    :func:`is_case_content_recipient` (SYNC-03-005) and answered with a
    replay capped by :func:`closed_participant_ledger_cutoff`.  A repeat of
    an act that would close it (a ``Leave(VulnerabilityCase)``, a ``Reject``
    of its Invite) is ``SKIPPED`` by effect before any sender guard runs
    (:func:`closure_recorded`, ID-05-003).  A
    ``Reject(Offer(VulnerabilityReport))`` closes no one on a case: every
    sender's is refused (CM-23-019).

    An actor the case does not list, or whose record does not resolve, may
    not act: the case cannot vouch for it.
    """
    record = listed_participant_record(case, dl, actor_id)
    return record is not None and _receives_case_content(case, record)


def why_may_not_act_on_case(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> str | None:
    """Why *actor_id* fails :func:`may_act_on_case`, or ``None`` if it passes.

    For a refusal that names its ground.  The verdict is
    :func:`may_act_on_case`'s, so the two cannot disagree; the reason only
    describes the first condition the actor's record misses.  The ownership
    transfer checks it for the transferee, which the Offer sends the case to
    and which then acts as its owner (CM-21-021, CM-21-022).
    """
    if may_act_on_case(case, dl, actor_id):
        return None
    if actor_id not in case.actor_participant_index:
        return "is not a participant of the case"
    record = listed_participant_record(case, dl, actor_id)
    if record is None:
        return "has no participant record the case can resolve"
    if not record.joined:
        return "has not joined the case (its invitation is not accepted)"
    if record.removed:
        return "was removed from the case (CM-31-001)"
    if record.rm_closed:
        return "has left the case (RM CLOSED, CM-23-004)"
    return (
        f"has not agreed to the active embargo '{case.active_embargo_id}'"
        " (CM-18-001)"
    )
