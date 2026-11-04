"""Domain-event extraction from AS2 activities.

This module provides ``extract_intent``, the sole AS2 → domain translation
point for inbound activities.  It is called after pattern matching has
determined the ``MessageSemantics``; the caller supplies the matching
``event_class`` and ``include_activity`` flag from the registry entry.

For a single-call convenience wrapper that performs pattern matching and
registry lookup automatically, use ``vultron.semantic_registry.extract_event``.
"""

import logging
from datetime import timedelta
from typing import cast

from vultron.core.models.events import (
    AnyReceivedEvent,
    MessageSemantics,
    VultronEvent,
)
from vultron.core.models.rsvp_deadline import (
    DEFAULT_MIN_RSVP_WINDOW,
    DEFAULT_RSVP_WINDOW,
)
from vultron.enums.object_types import VultronObjectType as VOtype
from vultron.primitives import normalise_actor_id
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.extractor._builders import (
    proposed_embargo_from,
)
from vultron.wire.as2.extractor._builders.fields import (
    _get_id,
    _to_domain_obj,
)
from vultron.wire.as2.extractor._builders.object_kwargs import (
    _build_object_kwargs,
)
from vultron.wire.as2.extractor._builders.semantic_kwargs import (
    _activity_end_time,
    _content_kwargs,
    _deadline_kwargs,
    _effective_rsvp_deadline,
    _fault_kwargs,
    _proposer_profile,
    _unresolved_object_id,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
    case_reference,
)

logger = logging.getLogger(__name__)

#: The acts that name their case rather than carry it (ADR-0165): a
#: participant's ``Join``, ``Ignore`` and ``Leave`` of a case and the
#: ownership-transfer ``Offer``.  Their receiver holds the case and reads only
#: its id, so a full case another sender still carries is reduced to its
#: typed reference here, at the edge, and nothing else in it reaches core.
_ACTS_NAMING_THEIR_CASE: frozenset[MessageSemantics] = frozenset(
    {
        MessageSemantics.ENGAGE_CASE,
        MessageSemantics.DEFER_CASE,
        MessageSemantics.CLOSE_CASE,
        MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
    }
)


def _as_case_reference(value: object) -> object:
    """*value* reduced to its case reference when it is a case, else as is."""
    if isinstance(value, (as_VulnerabilityCaseReference, str)):
        return value
    if str(getattr(value, "type_", "")) != str(VOtype.VULNERABILITY_CASE):
        return value
    case_id = _get_id(value)
    return case_reference(case_id) if case_id is not None else value


def _named_case_only(semantics: MessageSemantics, obj: object) -> object:
    """The object an act that names its case is read with (ADR-0165).

    For one of :data:`_ACTS_NAMING_THEIR_CASE` the case is its typed
    reference.  The owner's proposal nests the Offer it asks for, whose case
    is reduced the same way.  Any other object is returned unchanged.
    """
    if semantics in _ACTS_NAMING_THEIR_CASE:
        return _as_case_reference(obj)
    if (
        semantics is MessageSemantics.PROPOSE_CASE_OWNERSHIP_TRANSFER
        and isinstance(obj, as_Activity)
    ):
        inner = getattr(obj, "object_", None)
        reduced = _as_case_reference(inner)
        if reduced is not inner:
            return obj.model_copy(update={"object_": reduced})
    return obj


def extract_intent(
    activity: as_Activity,
    semantics: MessageSemantics,
    event_class: type[VultronEvent],
    include_activity: bool = False,
    min_rsvp_window: timedelta = DEFAULT_MIN_RSVP_WINDOW,
    default_rsvp_window: timedelta = DEFAULT_RSVP_WINDOW,
) -> AnyReceivedEvent:
    """Extract domain fields from an AS2 activity given pre-computed semantics.

    This function is the sole AS2 → domain translation point.  It is called
    after pattern matching has already determined the ``semantics``; the
    caller must supply the matching ``event_class`` and ``include_activity``
    flag from the registry entry.

    For a single-call convenience wrapper that performs pattern matching and
    registry lookup automatically, use ``vultron.semantic_registry.extract_event``.

    Args:
        activity: The AS2 activity to extract fields from.
        semantics: Pre-matched ``MessageSemantics`` value.
        event_class: Concrete ``VultronEvent`` subclass to instantiate.
        include_activity: When ``True``, populate ``event.activity`` with a
            summarised ``VultronActivity`` snapshot of the outer activity.
        min_rsvp_window: Minimum RSVP window for an inbound embargo invite
            (EP-07-002, EP-07-003); 72 h by default (EP-07-010).  Pass
            ``ActorConfig.min_rsvp_window`` to apply the configured floor.
        default_rsvp_window: Policy window used when an inbound embargo
            invite names no deadline (EP-07-001, EP-07-009, CM-18-023); 7 days by
            default.  Pass ``ActorConfig.default_rsvp_window``.

    Returns:
        A concrete VultronEvent subclass discriminated by MessageSemantics.
    """
    # The sender id as written, for the activity snapshot: the stored
    # activity and the ledger postmark keep the sender's spelling.  The event
    # gets the normalised id (OID-01-006, OID-01-007).
    actor_id = _get_id(getattr(activity, "actor", None)) or ""
    sender_id = normalise_actor_id(actor_id)
    obj = _named_case_only(semantics, getattr(activity, "object_", None))
    target = getattr(activity, "target", None)
    context = getattr(activity, "context", None)
    origin = getattr(activity, "origin", None)

    # Nested fields from activity.object_ (for Accept/Reject wrapping another activity)
    inner_obj = inner_target = inner_context = None
    if obj is not None and not isinstance(obj, str):
        inner_obj = getattr(obj, "object_", None)
        inner_target = getattr(obj, "target", None)
        inner_context = getattr(obj, "context", None)

    _obj_type = str(getattr(obj, "type_", "")) if obj is not None else ""
    carries_deadline = "answer_deadline" in event_class.model_fields
    proposed_embargo = None
    carries_terms = "proposed_embargo" in event_class.model_fields
    terms_on_activity = _obj_type != str(VOtype.CASE_PROPOSAL)
    if carries_terms:
        # Offer(VulnerabilityReport) carries it itself; Create(CaseProposal)
        # carries it on the Offer inlined in the proposal (EP-04-004,
        # CP-01-008).  Surfaced here so no use case re-reads the wire
        # activity for it (ADR-0035).
        proposed_embargo = proposed_embargo_from(
            activity if terms_on_activity else obj, activity_id=activity.id_
        )
    extra_kwargs = _build_object_kwargs(
        obj,
        _obj_type,
        context,
        target,
        include_activity,
        activity,
        actor_id,
        origin,
        # Carried as received on the activity the entry records (CS-13-005,
        # CLP-07-011); core reads it back through ``parse_published``.
        activity_end_time=(
            _activity_end_time(activity) if carries_deadline else None
        ),
        # Terms the activity carries itself are part of the Offer the
        # receiver archives and inlines in its case proposal (CP-01-008).
        activity_proposed_embargo=(
            proposed_embargo if terms_on_activity else None
        ),
    )

    if "rsvp_deadline" in event_class.model_fields:
        extra_kwargs["rsvp_deadline"] = _effective_rsvp_deadline(
            activity, actor_id, obj, min_rsvp_window, default_rsvp_window
        )
    extra_kwargs.update(_deadline_kwargs(activity, obj, event_class))
    if carries_terms:
        extra_kwargs["proposed_embargo"] = proposed_embargo

    extra_kwargs.update(_content_kwargs(activity, event_class))

    if "proposer_profile" in event_class.model_fields:
        extra_kwargs["proposer_profile"] = _proposer_profile(activity)

    if "proposer_case_roles" in event_class.model_fields:
        # The proposer's own roles ride on the proposal (CP-01-011, ADR-0133):
        # the CASE_MANAGER has no other way to learn them.  as_CaseProposal
        # refused a CASE_MANAGER claim when it was parsed (CP-01-012).  Any
        # other object is refused rather than read as "no roles", which would
        # seat the owner as CASE_OWNER alone without a sound.
        if not isinstance(obj, as_CaseProposal):
            raise VultronParseValidationError(
                f"Create(CaseProposal) {activity.id_!r} carries no parsed"
                f" CaseProposal (got {type(obj).__name__}); its"
                " proposerCaseRoles cannot be read (CP-01-011)"
            )
        extra_kwargs["proposer_case_roles"] = list(obj.proposer_case_roles)

    extra_kwargs.update(_fault_kwargs(activity, obj, event_class))

    if "unresolved_object_id" in event_class.model_fields:
        extra_kwargs["unresolved_object_id"] = _unresolved_object_id(activity)

    return cast(
        AnyReceivedEvent,
        event_class(
            semantic_type=semantics,
            activity_id=activity.id_,
            activity_type=str(activity.type_) if activity.type_ else None,
            actor_id=sender_id,
            # object_ comes from extra_kwargs if a typed domain object was built;
            # otherwise fall back to a minimal CoreObject wrapper.
            object_=extra_kwargs.pop("object_", None) or _to_domain_obj(obj),
            target=_to_domain_obj(target),
            context=_to_domain_obj(context),
            origin=_to_domain_obj(origin),
            inner_object=_to_domain_obj(inner_obj),
            inner_target=_to_domain_obj(inner_target),
            inner_context=_to_domain_obj(inner_context),
            in_reply_to=_get_id(getattr(activity, "in_reply_to", None)),
            # Carried, never re-derived: core records it in the ledger as
            # received (VM-08-002, CLP-07-011, ADR-0107).
            received_evidence=activity.received_evidence_json,
            **extra_kwargs,
        ),
    )
