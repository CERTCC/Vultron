"""Per-type builders for the objects a received activity carries.

Reports, cases, embargoes, participants, notes and ledger entries; each
returns the domain-field kwargs ``extract_intent`` passes to the event.
"""

import logging
from datetime import datetime
from typing import Any

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.note import VultronNote
from vultron.core.models.report import VulnerabilityReport
from vultron.wire.as2.errors import (
    VultronParseValidationError,
)
from vultron.wire.as2.extractor._builders.fields import (
    _get_id,
    _get_id_list,
    _get_timestamp,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Event

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
                published=_get_timestamp(obj, "published"),
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

    Prefers the wire model's own ``to_core()`` projection, which additionally
    carries ``participant_statuses`` across the boundary.  Hand-building the
    domain object drops them, and a ``CaseParticipant`` with no statuses
    validates to a default ``RM.START`` entry — so a received snapshot would
    silently report every participant as being at the start of the RM
    lifecycle regardless of the state it actually announced.
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

    roles = getattr(ref, "case_roles", [])
    attributed = getattr(ref, "attributed_to", None)
    context_id = _get_id(getattr(ref, "context", None))
    if roles is not None and attributed is not None and context_id:
        return CaseParticipant(
            id_=participant_id,
            attributed_to=str(attributed),
            context=context_id,
            name=getattr(ref, "name", None),
            case_roles=list(roles),
            published=_get_timestamp(ref, "published"),
            updated=_get_timestamp(ref, "updated"),
        )

    # Fallback: return as ID string only
    return participant_id


def _build_case_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    if object_id:
        # Every case has an owner (ARCH-10-001); the parse edge already
        # refuses one without (ADR-0032), so reaching here without is a fault.
        owner_id = _get_id(getattr(obj, "attributed_to", None))
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
                published=_get_timestamp(obj, "published"),
                updated=_get_timestamp(obj, "updated"),
                case_participants=participants,
                actor_participant_index=actor_participant_index,
                vulnerability_reports=vulnerability_reports,
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


def _build_embargo_event_object(
    obj: "as_Event | EmbargoEvent", context: object, target: object
) -> dict[str, Any]:
    end_time = getattr(obj, "end_time", None)
    object_id = _get_id(obj)
    embargo_context = (
        _get_id(getattr(obj, "context", None))
        or _get_id(context)
        or _get_id(target)
    )
    if isinstance(end_time, datetime) and embargo_context and object_id:
        if isinstance(obj, EmbargoEvent):
            # Already the core type (ADR-0099): keep every field it carries,
            # so the CASE_MANAGER stores the embargo its committed entry
            # carries and replicas that copy the entry match it (CM-23-016).
            return {"object_": obj.model_copy(deep=True)}
        return {
            "object_": EmbargoEvent(
                id_=object_id,
                name=getattr(obj, "name", None),
                start_time=_get_timestamp(obj, "start_time"),
                end_time=end_time,
                published=_get_timestamp(obj, "published"),
                updated=_get_timestamp(obj, "updated"),
                context=embargo_context,
            )
        }
    return {}


def proposed_embargo_from(carrier: object, *, activity_id: str) -> Any:
    """Return the proposed ``EmbargoEvent`` *carrier* holds, or ``None``.

    *carrier* is an ``Offer(VulnerabilityReport)`` (its ``proposed_embargo``,
    EP-04-004) or a ``CaseProposal`` (the same field on the Offer it carries in
    ``in_reply_to``, CP-01-008).  The parser has already expanded an inline
    ``EmbargoEvent`` dict to the core class, so an ``EmbargoEvent`` is passed
    through; an ``as_Event``-shaped object is projected the same way an
    ``Invite(EmbargoEvent)``'s object is.  A bare reference is *not* a
    proposal: the sender inlines what it introduces (ADR-0107), and a
    receiver that fetched terms nobody sent would be inventing them — so a
    string is logged and read as absent (receive side, Postel's maxim).
    """
    raw = getattr(carrier, "proposed_embargo", None)
    if raw is None:
        offer = getattr(carrier, "in_reply_to", None)
        raw = getattr(offer, "proposed_embargo", None)
    if raw is None:
        return None
    if isinstance(raw, EmbargoEvent):
        return raw
    if isinstance(raw, str):
        logger.warning(
            "extract_intent: activity '%s' names its proposed embargo by"
            " reference (%r) instead of inlining it; read as no proposal"
            " (EP-04-004, ADR-0107)",
            activity_id,
            raw,
        )
        return None
    built = _build_embargo_event_object(
        raw, getattr(raw, "context", None), None
    )
    return built.get("object_")


def _build_participant_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    attributed_to = _get_id(getattr(obj, "attributed_to", None))
    participant_context = _get_id(getattr(obj, "context", None))
    if object_id and attributed_to and participant_context:
        return {
            "object_": CaseParticipant(
                id_=object_id,
                name=getattr(obj, "name", None),
                attributed_to=attributed_to,
                context=participant_context,
                case_roles=list(getattr(obj, "case_roles", []) or []),
                participant_case_name=getattr(
                    obj, "participant_case_name", None
                ),
                published=_get_timestamp(obj, "published"),
                updated=_get_timestamp(obj, "updated"),
            )
        }
    return {}


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
                published=_get_timestamp(obj, "published"),
                updated=_get_timestamp(obj, "updated"),
            )
        }
    return {}


def _build_case_ledger_entry_object(obj: object) -> dict[str, Any]:
    object_id = _get_id(obj)
    case_id = getattr(obj, "case_id", None)
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
                case_id=case_id,
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
