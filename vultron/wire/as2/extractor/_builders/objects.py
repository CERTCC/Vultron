"""Per-type builders for the objects a received activity carries.

Reports, cases, embargoes, participants, notes and ledger entries; each
returns the domain-field kwargs ``extract_intent`` passes to the event.
"""

import logging
from typing import Any, TypeVar

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.note import VultronNote
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_item import VulnerabilityItem
from vultron.primitives import normalise_actor_id
from vultron.wire.as2.errors import (
    VultronParseValidationError,
)
from vultron.wire.as2.extractor._builders.fields import (
    _get_id,
    _get_id_list,
    _get_timestamp,
    _required_published,
)
from vultron.wire.as2.typed_reference import as_TypedReference

logger = logging.getLogger(__name__)


def _build_report_object(obj: object) -> dict[str, Any]:
    content = getattr(obj, "content", None)
    object_id = _get_id(obj)
    if isinstance(content, str) and content and object_id:
        return {
            "object_": VulnerabilityReport(
                id_=object_id,
                name=getattr(obj, "name", None),
                summary=getattr(obj, "summary", None),
                content=content,
                url=_get_id(getattr(obj, "url", None)),
                media_type=getattr(obj, "media_type", None),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                context=_get_id(getattr(obj, "context", None)),
                published=_required_published(obj),
                updated=_get_timestamp(obj, "updated"),
                # Carried as received, so the stored report keeps the
                # documents it came with, a CSAF document among them
                # (CSAF-01-001, VM-08-002).
                attachment=getattr(obj, "attachment", None),
            )
        }
    return {}


def _participant_ref_to_domain(ref: object) -> str | CaseParticipant | None:
    """Convert a wire-layer participant ref to a core domain object or ID string.

    Returns a ``CaseParticipant`` if ``ref`` has ``case_roles`` (duck-type),
    a plain string if it is a URI reference, or ``None`` if the ref is
    unusable.  This preserves participant metadata — including role lists —
    across the wire→domain extraction boundary so bootstrap trust logic can
    inspect ``CVDRole.CASE_MANAGER`` on the extracted case (CBT-01-014).

    Under ARCH-25-003 (ADR-0099) a parsed participant already *is* the core
    class, so it is returned as received, with its own statuses.  Any other
    ref goes through its ``to_core()`` projection, or reduces to its id: it is
    never hand-built, since a rebuild drops the statuses and the core model
    then seeds a ``START`` status nobody sent (AKM-02-006, #5265).
    """
    if isinstance(ref, str):
        return ref if ref else None

    participant_id = _get_id(ref)
    if not participant_id:
        return None

    # Core CaseParticipant objects are already in the canonical shape —
    # return them directly to preserve participant_statuses (including RM state).
    if isinstance(ref, CaseParticipant):
        return ref

    to_core = getattr(ref, "to_core", None)
    if callable(to_core):
        try:
            converted = to_core()
        except Exception:
            logger.warning(
                "participant_ref_to_domain: to_core() failed for '%s'; "
                "falling back to partial projection",
                participant_id,
                exc_info=True,
            )
        else:
            if isinstance(converted, CaseParticipant):
                return converted

    return participant_id


_RefT = TypeVar("_RefT")


def _carried_refs(raw: object, core_cls: type[_RefT]) -> list[str | _RefT]:
    """Keep each inline *core_cls* object, and reduce any other entry to its id."""
    carried: list[str | _RefT] = []
    for entry in raw or []:  # type: ignore[attr-defined]
        if isinstance(entry, core_cls):
            carried.append(entry)
        elif entry_id := _get_id(entry):
            carried.append(entry_id)
    return carried


def _actor_id(value: object) -> str | None:
    """The id of an actor reference, in its canonical spelling (OID-01-006).

    The extractor is where a peer's actor id becomes one core acts on, so it
    is normalised here: the record built from it, and the roster key built
    from the record, then share one spelling (#5919).
    """
    actor_id = _get_id(value)
    return normalise_actor_id(actor_id) if actor_id else None


def _build_case_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    if object_id:
        # Every case has an owner (ARCH-10-001); the parse edge already
        # refuses one without (ADR-0032), so reaching here without is a fault.
        owner_id = _actor_id(getattr(obj, "attributed_to", None))
        if owner_id is None:
            raise VultronParseValidationError(
                f"VulnerabilityCase {object_id!r} names no owner: its"
                " `attributedTo` is missing (CLP-08-002)"
            )
        # The parse edge refuses a case naming no position (SYNC-16-019),
        # so, like a missing owner, reaching here without one is a fault.
        ledger_position = getattr(obj, "ledger_position", None)
        if not isinstance(ledger_position, LedgerPosition):
            raise VultronParseValidationError(
                f"VulnerabilityCase {object_id!r} names no ledger position:"
                " its `ledgerPosition` is missing (SYNC-16-005)"
            )
        raw_participants = getattr(obj, "case_participants", []) or []
        participants: list[str | CaseParticipant] = []
        for ref in raw_participants:
            converted = _participant_ref_to_domain(ref)
            if converted is not None:
                participants.append(converted)
        raw_index = getattr(obj, "actor_participant_index", None)
        actor_participant_index: dict[str, str] = (
            {str(k): str(v) for k, v in raw_index.items()}
            if isinstance(raw_index, dict)
            else {}
        )
        # Carried as received: EM and the active embargo are reads of it.
        embargo_register = list(getattr(obj, "embargo_register", None) or [])
        # The reports the case answers, by id (the case holds ids only).  A
        # report receiver relays the case to the reporter, and that
        # introduction must name the submitted report (CBT-01-001, CBT-01-005).
        # The field parses from ``vulnerabilityReports``, where a sender
        # carries each report it holds inline (AKM-02-004, #6046).
        vulnerability_reports: list[str | VulnerabilityReport] = list(
            _get_id_list(getattr(obj, "vulnerability_reports", None)) or []
        )
        # The case's items and references: an inline object is kept, any
        # other entry reduces to its id (CM-05-021).
        vulnerability_items = _carried_refs(
            getattr(obj, "vulnerability_items", None), VulnerabilityItem
        )
        case_references = _carried_refs(
            getattr(obj, "case_references", None), CaseReference
        )
        raw_statuses = getattr(obj, "case_statuses", []) or []
        case_statuses: list[str | CaseStatus] = []
        for cs in raw_statuses:
            # Under ARCH-25-003 (ADR-0099) the parsed status already *is* the core
            # class; reducing it to its id would drop the status it carries.
            if isinstance(cs, CaseStatus):
                case_statuses.append(cs)
            elif hasattr(cs, "to_core"):
                case_statuses.append(cs.to_core())
            else:
                cs_id = _get_id(cs)
                if cs_id:
                    case_statuses.append(cs_id)
        return {
            "object_": VulnerabilityCase(
                id_=object_id,
                name=getattr(obj, "name", None),
                summary=getattr(obj, "summary", None),
                content=getattr(obj, "content", None),
                url=_get_id(getattr(obj, "url", None)),
                attributed_to=owner_id,
                published=_required_published(obj),
                updated=_get_timestamp(obj, "updated"),
                case_participants=participants,
                actor_participant_index=actor_participant_index,
                vulnerability_reports=vulnerability_reports,
                vulnerability_items=vulnerability_items,
                case_references=case_references,
                embargo_register=embargo_register,
                case_statuses=case_statuses if case_statuses else [],
                # Carried, not recomputed: core would otherwise rederive it
                # from ``published`` (CLP-08-002), which a received case
                # need not carry.
                genesis_hash=getattr(obj, "genesis_hash", "") or "",
                # Carried as received, like the genesis hash: core would
                # otherwise start an owned case at its empty ledger, and a
                # replica judges the copy by this position (SYNC-16-005,
                # SYNC-16-006).
                ledger_position=ledger_position,
            )
        }
    return {}


def _build_embargo_event_object(obj: EmbargoEvent) -> dict[str, Any]:
    """The received embargo *obj*, kept whole.

    Only an ``EmbargoEvent`` is an embargo; a plain AS2 ``Event`` is not
    read as one (ADR-0201).  The parsed object is already the core type
    (ADR-0099), whose ``id`` and ``context`` validated at construction, so
    every field it carries is kept: the CASE_MANAGER stores the embargo its
    committed entry carries, and replicas that copy the entry match it
    (CM-23-016).
    """
    return {"object_": obj.model_copy(deep=True)}


def proposed_embargo_from(carrier: object, *, activity_id: str) -> Any:
    """Return the proposed ``EmbargoEvent`` *carrier* holds, or ``None``.

    *carrier* is an ``Offer(VulnerabilityReport)`` (its ``proposed_embargo``,
    EP-04-004) or a ``CaseProposal`` (the same field on the Offer it carries in
    ``in_reply_to``, CP-01-008).  The parser has already expanded an inline
    ``EmbargoEvent`` dict to the core class, so an ``EmbargoEvent`` is passed
    through.  Anything else is not one: a plain AS2 ``Event`` is no embargo
    (ADR-0201), so it is logged and read as no proposal.  A bare reference
    is *not* a
    proposal: the sender inlines what it introduces (ADR-0107), and a
    receiver that fetched terms nobody sent would be inventing them — so a
    string, or a typed reference, is logged and read as absent (receive
    side, Postel's maxim).
    """
    raw = getattr(carrier, "proposed_embargo", None)
    if raw is None:
        offer = getattr(carrier, "in_reply_to", None)
        raw = getattr(offer, "proposed_embargo", None)
    if raw is None:
        return None
    if isinstance(raw, EmbargoEvent):
        return raw
    if isinstance(raw, as_TypedReference):
        # A typed reference claims no terms (MV-10-011): read as its id.
        raw = raw.id_
    if isinstance(raw, str):
        logger.warning(
            "extract_intent: activity '%s' names its proposed embargo by"
            " reference (%r) instead of inlining it; read as no proposal"
            " (EP-04-004, ADR-0107)",
            activity_id,
            raw,
        )
        return None
    logger.warning(
        "extract_intent: activity '%s' carries a proposed embargo of type"
        " %r, not an EmbargoEvent; read as no proposal (EP-04-004, ADR-0201)",
        activity_id,
        getattr(raw, "type_", type(raw).__name__),
    )
    return None


def _build_participant_object(obj: object) -> dict[str, Any]:
    """The received participant *obj*, as received (AKM-02-006, #5265).

    Under ARCH-25-003 (ADR-0099) the parsed or held participant already *is*
    the core class, so it is kept whole: its statuses, membership, consent
    rows and removal fact.  It is never rebuilt from a few fields: a rebuild
    dropped them, and the core model then minted a fresh ``START`` status
    and a ``joined`` flag no sender asserted.  Anything else yields no
    object.
    """
    if not isinstance(obj, CaseParticipant):
        return {}
    if not (
        _get_id(obj) and _actor_id(obj.attributed_to) and _get_id(obj.context)
    ):
        return {}
    return {"object_": obj.model_copy(deep=True)}


def _build_note_object(obj: object) -> dict[str, Any]:
    content = getattr(obj, "content", None)
    object_id = _get_id(obj)
    if isinstance(content, str) and content and object_id:
        return {
            "object_": VultronNote(
                id_=object_id,
                name=getattr(obj, "name", None),
                summary=getattr(obj, "summary", None),
                content=content,
                url=_get_id(getattr(obj, "url", None)),
                attributed_to=_get_id(getattr(obj, "attributed_to", None)),
                context=_get_id(getattr(obj, "context", None)),
                in_reply_to=_get_id(getattr(obj, "in_reply_to", None)),
                published=_required_published(obj),
                updated=_get_timestamp(obj, "updated"),
            )
        }
    return {}


def _build_case_ledger_entry_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    case_id = _get_id(getattr(obj, "context", None))
    log_index = getattr(obj, "log_index", -1)
    log_object_id = getattr(obj, "log_object_id", None) or getattr(
        obj, "logObjectId", None
    )
    semantic_type = getattr(obj, "semantic_type", None)
    # Both stamps are the CaseActor's and are required on the wire
    # (CLP-14-002, CLP-02-008), so a parsed entry always has them; a replica
    # keeps them rather than stamping its own — ``received_at`` is hashed.
    received_at = _get_timestamp(obj, "received_at")
    published = _get_timestamp(obj, "published")
    if (
        object_id
        and case_id
        and log_object_id
        and semantic_type
        and received_at is not None
        and published is not None
    ):
        return {
            "object_": CaseLedgerEntry(
                id_=object_id,
                context=case_id,
                log_index=log_index,
                term=getattr(obj, "term", None),
                log_object_id=log_object_id,
                semantic_type=semantic_type,
                payload_snapshot=getattr(obj, "payload_snapshot", {})
                or getattr(obj, "payloadSnapshot", {}),
                prev_log_hash=getattr(obj, "prev_log_hash", None)
                or getattr(obj, "prevLogHash", None)
                or "",
                entry_hash=getattr(obj, "entry_hash", None)
                or getattr(obj, "entryHash", None)
                or "",
                received_at=received_at,
                published=published,
                updated=_get_timestamp(obj, "updated"),
            )
        }
    return {}
