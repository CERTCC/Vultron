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
"""The shared recipient selection for messages about a case (CM-10-007).

Every send that addresses a case's participants picks its recipients here,
so the entitlement check cannot be forgotten at a send site.  Two audiences
exist, and they differ on purpose (ADR-0114 § "Inert and active"):

- :func:`case_content_recipients` — *case content*: ledger entries, case
  announcements, status broadcasts, embargo announcements.  Only **active**
  participants (:meth:`VulnerabilityCase.is_active_participant`, CM-10-004)
  whose closure is not recorded: a participant at RM ``CLOSED`` is sent no
  case content (CM-23-004).
- :func:`ledger_entry_recipients` — the recipients of one ledger entry's
  fan-out: :func:`case_content_recipients`, plus each closed participant the
  entry is *about* — the ``close_case`` entry and the status entries that
  record its own closure (CM-23-001, CM-23-004).
- :func:`inactive_joined_participants` — the joined participants that are
  not active, whose ledger streams are paused and backfilled on admission
  (CM-10-005, CM-10-006): the active embargo withholds them, or they were
  removed (CM-31-001).
- :func:`invitation_recipients` — an Invite addressed to a participant *so
  that* it can consent (the relayed embargo Invite, EP-09-002).  Every
  participant whose RM is not ``CLOSED`` and that is not removed, inert ones
  included (CM-10-007, CM-31-013).
- :func:`embargo_ending_notice_recipients` — the bound signatories the
  ledger fan-out no longer reaches, owed a direct notice when their embargo
  ends or shortens (CM-31-009).  Not case content (CM-10-007).
- :func:`reporter_introduction_recipients` — the reporters the report
  receiver introduces the CASE_MANAGER to with its own
  ``Create(VulnerabilityCase)`` (CBT-01-001, ADR-0132).  The case-content
  selection narrowed to the ``REPORTER`` role.

Each reads the roster (``actor_participant_index``) and resolves each entry to
its participant record.  A roster entry whose record cannot be read is not
provably entitled, so it is left out and logged at WARNING: leaking case
content to an actor the case cannot vouch for is the failure CM-10-004
exists to prevent.

Roster order is kept, and an unresolvable entry is named, which is why this
walks the index itself rather than :func:`iter_case_participants` (that yields
records only, in no fixed order, and skips what it cannot read silently).
Record precedence matches it: the stored record first, an inline copy only as
the fallback.

The report tree's own ``Create(Case)`` (``case_creation.CreateCaseActivity``)
does not come here: ``case_creation._collect_create_case_addressees``
builds its addressees from the actor, the report and the offer rather than
the roster, and every one of them is seated at case initialization.

The sender check reads the same records: :func:`may_act_on_case` is the one
predicate behind the ``ACTIVE_PARTICIPANT`` sender standing (CM-23-020), so a
sender may act on a case exactly when it would be sent its content;
:func:`why_may_not_act_on_case` names the ground a refusal by it cites.

This module is the one place in ``vultron/core/`` that lists roster actor
IDs for addressing; ``test/architecture/test_active_participant_recipient_selection.py``
holds every other module to that.
"""

import logging
from collections.abc import Callable, Collection, Iterable, Iterator

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import (
    same_actor_id,
    snapshot_actor_id,
)
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def _resolve_record(
    case: VulnerabilityCase, dl: CasePersistence, participant_id: str
) -> CaseParticipant | None:
    """Return the record *participant_id* names, or ``None`` if none resolves.

    The stored record wins over an inline copy the case carries, the same
    precedence as :func:`iter_case_participants`: the consent cascades and
    every other participant write save the stored record, so an inline copy
    can be stale.  The inline copy is the fallback for a case whose records
    are not stored yet (bootstrap).
    """
    stored = dl.read(participant_id)
    if isinstance(stored, CaseParticipant):
        return stored
    for entry in case.case_participants:
        if isinstance(entry, CaseParticipant) and entry.id_ == participant_id:
            return entry
    return None


def _roster_records(
    case: VulnerabilityCase, dl: CasePersistence
) -> Iterator[tuple[str, CaseParticipant | None]]:
    """Yield ``(actor_id, record)`` for every roster entry of *case*."""
    for actor_id, participant_id in case.actor_participant_index.items():
        yield actor_id, _resolve_record(case, dl, participant_id)


def _select(
    case: VulnerabilityCase,
    dl: CasePersistence,
    excluding: Collection[str],
    entitled: Callable[[CaseParticipant], bool],
    audience: str,
) -> list[tuple[str, CaseParticipant]]:
    return _select_with_actor(
        case, dl, excluding, lambda _actor_id, p: entitled(p), audience
    )


def _select_with_actor(
    case: VulnerabilityCase,
    dl: CasePersistence,
    excluding: Collection[str],
    entitled: Callable[[str, CaseParticipant], bool],
    audience: str,
) -> list[tuple[str, CaseParticipant]]:
    recipients: list[tuple[str, CaseParticipant]] = []
    for actor_id, record in _roster_records(case, dl):
        if actor_id in excluding:
            continue
        if record is None:
            logger.warning(
                "case '%s': no participant record for roster actor '%s'"
                " — left out of the %s recipients (CM-10-004)",
                case.id_,
                actor_id,
                audience,
            )
            continue
        if entitled(actor_id, record):
            recipients.append((actor_id, record))
        else:
            logger.debug(
                "case '%s': '%s' is not among the %s recipients (ADR-0114)",
                case.id_,
                actor_id,
                audience,
            )
    return recipients


def _receives_case_content(
    case: VulnerabilityCase, record: CaseParticipant
) -> bool:
    """True when *record* is sent case content (CM-10-004, CM-23-004).

    Active, and its closure not recorded: a participant at RM ``CLOSED``
    has left and is sent nothing further.
    """
    return case.is_active_participant(record) and not record.rm_closed


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
    the case to (CBT-01-001, CM-12-003, ADR-0132).  The message carries the
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


def inert_participants(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Return the roster actor IDs of *case* that are sent no case content.

    The complement of :func:`case_content_recipients` over the roster, for a
    caller that reports whom a send withheld content from: the participants
    that are not active (CM-10-004) and those at RM ``CLOSED`` (CM-23-004).
    """
    active = set(case_content_recipients(case, dl))
    return set(case.actor_participant_index) - active


def inactive_joined_participants(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the actor IDs of the joined participants that are not active.

    A joined participant that is not active: it is not a signatory to the
    active embargo (CM-10-004), or it carries the removal fact (CM-31-001).
    These are the participants whose ledger stream is paused and backfilled
    on admission (CM-10-005, CM-10-006); a removed participant is admitted
    when the fact is cleared (CM-31-011).  A participant that has not joined
    is left out: it is inert whatever the embargo, and its case copy and
    ledger arrive through the join path (ADR-0114).  A participant at RM
    ``CLOSED`` is left out too: it has left, so it is sent nothing further
    and has no stream to pause or backfill (CM-23-004).  A roster entry
    whose record cannot be read is left out as well;
    :func:`case_content_recipients` already names it.  Roster order is
    kept, minus *excluding*.
    """
    withheld: list[str] = []
    for actor_id, record in _roster_records(case, dl):
        if actor_id in excluding or record is None or not record.joined:
            continue
        if record.rm_closed:
            continue
        if not case.is_active_participant(record):
            withheld.append(actor_id)
    return withheld


def invitation_recipients(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the actor IDs a consent Invite on *case* is addressed to.

    Every participant whose RM is not ``CLOSED``, active or inert, minus
    *excluding* (EP-09-002, CM-10-007).  An Invite asks the participant to
    consent; an inert participant is exactly the one that needs asking, so
    the active check does not apply.  A participant that never joined is
    included: it is not ``CLOSED``.  A removed participant is not: the Case
    Owner took it out, and asking it to vote on embargo terms would undo that
    decision (CM-31-013, ADR-0116).  The embargo-ending notices it is still
    owed (CM-31-009) are not Invites and do not come here.
    """
    return [
        actor_id
        for actor_id, _record in _select(
            case,
            dl,
            excluding,
            lambda p: not p.rm_closed and not p.removed,
            "invitation",
        )
    ]


def _beyond_fan_out(record: CaseParticipant) -> bool:
    """True when the ledger fan-out no longer reaches *record* (CM-31-009).

    It was removed (CM-31-001), or it left the case and CM-23-004 skips it
    at RM ``CLOSED``.
    """
    return record.removed or record.rm_closed


def embargo_ending_notice_recipients(
    case: VulnerabilityCase,
    dl: CasePersistence,
    embargo_id: str,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the actor IDs owed a direct notice that *embargo_id* ended.

    A joined participant that is a signatory to *embargo_id* — its row
    for it is ``AGREED`` — and that the ledger fan-out no longer reaches:
    removed (CM-31-001), or at RM ``CLOSED`` (CM-23-004).  Such a
    participant stays bound (CM-31-008) and cannot learn from the ledger
    that the embargo was terminated or shortened, so the CASE_MANAGER tells
    it directly (CM-31-009).  A participant that declined, or an invitee
    that never joined, is not bound and is not sent anything.

    *embargo_id* is the embargo that is ending: the one terminated, or the
    one a shorter revision replaces.  Consent rows outlive both moves
    (MSM-07-006, EP-05-001), so the selection is the same before and after
    the EM write.  The notice is not case content (CM-10-007), so the active
    check does not apply.  Roster order is kept, minus *excluding*.

    An *embargo_id* the register does not hold has no signatories to notify:
    every participant's rows cover the register's entries (ADR-0122), so
    ``is_signatory`` would have no row to read.  Return nothing rather than
    reading a row that cannot exist.
    """
    if case.embargo_register_entry(embargo_id) is None:
        return []
    return [
        actor_id
        for actor_id, _record in _select(
            case,
            dl,
            excluding,
            lambda p: _owed_ending_notice(p, embargo_id),
            "embargo-ending notice",
        )
    ]


def _owed_ending_notice(record: CaseParticipant, embargo_id: str) -> bool:
    """True when *record* is owed a CM-31-009 notice that *embargo_id* ended.

    Joined, a signatory to *embargo_id*, and beyond the ledger fan-out.
    The one rule both sides read: the CASE_MANAGER to pick the recipients,
    the paused replica to decide whether a notice is one it can be owed.
    """
    return (
        record.joined
        and record.is_signatory(embargo_id)
        and _beyond_fan_out(record)
    )


def awaits_embargo_ending_notice(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *actor_id* can be owed a CM-31-009 notice on *case*.

    Read in the participant's own replica, about itself (CM-31-010): it is
    joined and a signatory of the embargo its replica has in force, and the
    ledger fan-out no longer reaches it (removed, or at RM ``CLOSED``).
    This is :func:`embargo_ending_notice_recipients` seen from the receiver,
    so a replica applies only a notice the CASE_MANAGER would send it.  A
    participant withheld under CM-10-005 is paused too
    (:func:`ledger_stream_paused`) but is never a signatory of the embargo
    in force, so no notice is owed to it: an ``Announce(EmbargoEvent)`` it
    receives is the teardown announcement, not a shorter revision.  An
    actor the case does not list, whose record does not resolve, or a case
    with no embargo in force, awaits nothing.
    """
    embargo_id = case.active_embargo_id
    participant_id = case.actor_participant_index.get(actor_id)
    if embargo_id is None or participant_id is None:
        return False
    record = _resolve_record(case, dl, participant_id)
    return record is not None and _owed_ending_notice(record, embargo_id)


def ledger_stream_paused(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *actor_id*'s ledger stream on *case* is paused (CM-31-010).

    A participant is paused when it is not active (CM-10-005, CM-31-001) or
    when it is at RM ``CLOSED`` (CM-23-004): the ledger no longer brings it
    the case's changes.  Read in the participant's own replica, about
    itself, to decide whether a direct embargo-ending notice from the
    CASE_MANAGER is its only channel.  An actor the case does not list, or
    whose record does not resolve, is not a paused participant.
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        return False
    record = _resolve_record(case, dl, participant_id)
    if record is None:
        return False
    return record.rm_closed or not case.is_active_participant(record)


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
    (:func:`closure_recorded`, ID-05-003).  A ``Close(Report)`` closes no one
    on a case: every sender's is refused (CM-23-019).

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
    and which then acts as its owner (CM-21-021).
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


def listed_participant_record(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> CaseParticipant | None:
    """The record *case*'s roster lists for *actor_id*, or ``None``.

    ``None`` when the roster does not list the actor or its record does not
    resolve (:func:`_resolve_record`: the stored record first, an inline copy
    as the fallback).  The one lookup behind :func:`may_act_on_case`, so a
    writer that must change the record an entitlement check admitted reads it
    here too (CM-21-021).
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        return None
    return _resolve_record(case, dl, participant_id)


def closure_recorded(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *case* records the closure of *actor_id* (CM-23-018).

    The roster lists the actor and its record is at RM ``CLOSED``.  An act
    that would close such a participant again changes nothing: it is the
    repeat CM-23-018 reports ``SKIPPED``, whatever its activity id
    (ID-05-003).  An actor the case does not list, or whose record does not
    resolve, has no recorded closure.
    """
    record = listed_participant_record(case, dl, actor_id)
    return record is not None and record.rm_closed
