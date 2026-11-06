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

"""Recipients of case content and of one ledger entry's fan-out.

Only active participants whose closure is not recorded are sent case
content (CM-10-004, CM-23-004); a ledger entry also reaches each closed
participant it is about (CM-23-031).
"""

from collections.abc import Collection, Iterable

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.participants.recipients.roster import (
    _receives_case_content,
    _resolve_record,
    _select,
    _select_with_actor,
    listed_participant_record,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import (
    same_actor_id,
    snapshot_actor_id,
)
from vultron.enums.roles import CVDRole


def case_content_participants(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
) -> list[tuple[str, CaseParticipant]]:
    """Return ``(actor_id, record)`` for *case*'s case-content recipients.

    The same selection as :func:`case_content_recipients`, with the record
    each actor ID resolved to, for a caller that narrows the recipients
    further by a record field (a role, say).  Reading the record again
    would lose an inline-only record this selection already resolved.
    """
    return _select(
        case,
        dl,
        excluding,
        lambda p: _receives_case_content(case, p),
        "case-content",
    )


def case_content_recipients(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the actor IDs *case*'s content is sent to (CM-10-004, CM-23-004).

    The recipients of every case-content send — ledger fan-out, case
    announcements, case-update broadcasts and embargo announcements — minus
    *excluding* (typically the sender).  Roster order is kept.

    Only active participants (CM-10-004), and of those only the ones whose
    closure is not recorded: a participant at RM ``CLOSED`` has left and is
    sent nothing further (CM-23-004).  The one exception is the ledger
    entries that record its own closure, which
    :func:`ledger_entry_recipients` adds for the fan-out of exactly those
    entries.  A closed signatory is told of an embargo's early end directly
    instead (:func:`embargo_ending_notice_recipients`, CM-31-009).
    """
    return [
        actor_id
        for actor_id, _record in case_content_participants(
            case, dl, excluding=excluding
        )
    ]


def reporter_introduction_recipients(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the reporters the report receiver introduces the case to.

    The report receiver sends each of them its own
    ``Create(VulnerabilityCase)``, which names the CASE_MANAGER it delegated
    the case to (CBT-01-001, ADR-0132).  The message carries the
    whole case, so it is case content: only active participants qualify
    (CM-10-004), narrowed to the ``REPORTER`` role the case initialization
    seats the report submitter in.  *excluding* is typically
    the receiver itself and the CASE_MANAGER.  Roster order is kept.
    """
    return [
        actor_id
        for actor_id, record in case_content_participants(
            case, dl, excluding=excluding
        )
        if CVDRole.REPORTER in record.roles
    ]


_CLOSE_CASE_SEMANTIC_TYPE = MessageSemantics.CLOSE_CASE.value


_PARTICIPANT_STATUS_SEMANTIC_TYPE = (
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.value
)


def entry_records_own_closure(
    entry: CaseLedgerEntry, actor_id: str, record: CaseParticipant
) -> bool:
    """True when *entry* records the closure of *actor_id* itself (CM-23-001).

    The entries a leaving participant is still sent once it is at RM
    ``CLOSED`` (CM-23-004): the ``close_case`` entry that records its own
    ``Leave``, and the ``add_participant_status_to_participant`` entries
    whose status is one of its own — the closure steps the CASE_MANAGER
    writes for it.  The entry is identified by its subject being the
    recipient, never by the recipient's status, which is already
    ``CLOSED`` when the last of those entries is fanned out.

    A closed participant writes no status of its own (CM-23-001), so every
    status entry about it that is committed after its closure is one of
    those steps.
    """
    if entry.semantic_type == _CLOSE_CASE_SEMANTIC_TYPE:
        # The snapshot keeps the leaver's own spelling (OID-01-006).
        snapshot_actor = snapshot_actor_id(entry.payload_snapshot.get("actor"))
        return snapshot_actor is not None and same_actor_id(
            snapshot_actor, actor_id
        )
    if entry.semantic_type == _PARTICIPANT_STATUS_SEMANTIC_TYPE:
        return any(
            status.id_ == entry.log_object_id
            for status in record.participant_statuses
        )
    return False


def ledger_entry_recipients(
    case: VulnerabilityCase,
    dl: CasePersistence,
    entry: CaseLedgerEntry,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the actor IDs *entry*'s fan-out is sent to (CM-23-004).

    :func:`case_content_recipients`, plus each active participant at RM
    ``CLOSED`` whose own closure *entry* records
    (:func:`entry_records_own_closure`): a leaving participant receives the
    ``close_case`` entry and every status entry the CASE_MANAGER commits
    for its closure, the one that reaches ``CLOSED`` included, and nothing
    after them, the CASE_MANAGER's own closure included.  The exception
    never widens entitlement: an inert or removed participant is not sent
    these entries either (CM-10-004).  Roster order is kept, minus *excluding*.
    """
    return [
        actor_id
        for actor_id, _record in _select_with_actor(
            case,
            dl,
            excluding,
            lambda actor_id, p: (
                case.is_active_participant(p)
                and (
                    not p.rm_closed
                    or entry_records_own_closure(entry, actor_id, p)
                )
            ),
            "ledger fan-out",
        )
    ]


def closed_participant_ledger_cutoff(
    case: VulnerabilityCase,
    dl: CasePersistence,
    actor_id: str,
    entries: Iterable[CaseLedgerEntry],
) -> int | None:
    """Return the last ``log_index`` a closed *actor_id* may be sent.

    ``None`` when *actor_id* is not at RM ``CLOSED`` (or is not listed, or
    its record does not resolve): no closure cutoff applies.  For a closed
    participant, the index of the last entry in *entries* that records its
    own closure (:func:`entry_records_own_closure`), or ``-1`` when none
    does.  A replay answering a closed participant's
    ``Reject(CaseLedgerEntry)`` stops there, so the replay sends it no more
    than the fan-out does (CM-23-004).
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        return None
    record = _resolve_record(case, dl, participant_id)
    if record is None or not record.rm_closed:
        return None
    cutoff = -1
    for entry in entries:
        if entry_records_own_closure(entry, actor_id, record):
            cutoff = max(cutoff, entry.log_index)
    return cutoff


def is_case_content_recipient(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *actor_id* is an active participant of *case* (CM-10-004).

    For a send addressed to one actor named by the triggering message rather
    than chosen from the roster: the ledger replay a
    ``Reject(CaseLedgerEntry)`` asks for and the genesis case seed (#4042).
    The joiner's case copy and ledger backfill (#4048) gate on it too, and
    so does the sender guard of that ``Reject(CaseLedgerEntry)``
    (SYNC-03-005).  Every other sender guard asks :func:`may_act_on_case`
    instead (CM-23-018).

    It does not apply the RM ``CLOSED`` filter of
    :func:`case_content_recipients`: a closed participant may still be owed
    the entries that record its own closure, so the replay caps what it
    sends a closed peer with :func:`closed_participant_ledger_cutoff`
    instead (CM-23-004).
    """
    record = listed_participant_record(case, dl, actor_id)
    return record is not None and case.is_active_participant(record)
