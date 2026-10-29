#!/usr/bin/env python

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

"""Actor-domain trigger activity construction for TriggerActivityAdapter.

Covers actor invitations, recommendations, participant management, and
Case Actor / CASE_MANAGER delegation activities.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

from vultron.adapters.received_archive import (
    read_held_as_received,
    read_received_as_received,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    accept_case_participant_offer_activity,
    add_participant_to_case_activity,
    add_status_to_participant_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
    reject_case_participant_offer_activity,
    remove_participant_from_case_activity,
    rm_accept_full_case_invite_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_invite_to_full_case_activity,
    rm_reject_full_case_invite_activity,
    rm_tentative_reject_full_case_invite_activity,
)
from vultron.wire.as2.factories.case import (
    accept_case_ownership_transfer_activity,
    accept_case_participant_role_activity,
    offer_case_ownership_transfer_activity,
    offer_case_participant_role_activity,
    propose_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    reject_case_participant_role_activity,
    rm_reject_invite_to_case_activity,
    undo_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus

from ._base import (
    _addressing,
    _already_sealed,
    _case_for_wire,
    _create_and_seal,
    _seal,
    _stamped,
    _to_wire,
)

logger = logging.getLogger(__name__)


def _active_embargo_of(
    dl: CaseOutboxPersistence, case: VulnerabilityCase
) -> Any:
    """The case's active embargo as an object, whichever shape the field holds.

    ``active_embargo`` is id-or-object: a case seeded from a sealed Announce
    carries the ``EmbargoEvent`` inline (it is in the case's
    ``inline_required_refs``), a locally built one holds the id.  Only the id
    needs a store read.
    """
    active_embargo = case.active_embargo
    if isinstance(active_embargo, str):
        return dl.read(active_embargo)
    return active_embargo


def _held_actor(
    dl: CaseOutboxPersistence, actor_id: str
) -> as_Actor | CoreActor | str:
    """The actor *actor_id* as this sender holds it, else its URI.

    The factory carries a held profile as held and a URI as an actor
    reference (``carried_actor``, AKM-05-005, ADR-0159).
    """
    held = dl.read(actor_id)
    if isinstance(held, (as_Actor, CoreActor)):
        return held
    return actor_id


def _stored_case_invite(
    dl: CaseOutboxPersistence, invite_id: str
) -> as_Invite:
    """Read the received Invite as this invitee holds it, stub and all.

    The Invite is parsed from the body intake archived on arrival
    (:func:`read_received_as_received`), since the inbox never holds a stub
    Invite back for its case (PCR-06-005).  The parse resolves the inline
    stub to its own class, and the reply factory checks that it is a case
    Invite.  The Accept or Reject embeds the Invite as received, so its
    ``target`` stays the case stub (VAM-04-005, VAM-04-006): the CASE_MANAGER
    reads the case from the stub's ``caseId`` (CM-11-003), and the stub's
    ``type`` is what tells the reply apart from a reply to a full-case Invite
    (CM-11-013).

    Raises:
        VultronNotFoundError: when no activity with *invite_id* was received.
        VultronValidationError: when the activity received under *invite_id*
            is not an Invite.
    """
    held = read_received_as_received(dl, invite_id, "RmInviteToCaseActivity")
    if not isinstance(held, as_Invite):
        raise VultronValidationError(
            f"invite '{invite_id}' is held as {type(held).__name__},"
            " not as an Invite"
        )
    return held


class _ActorsMixin:
    """Trigger activity methods for actor invitations, recommendations,
    participant management, and CASE_MANAGER delegation.
    """

    _dl: CaseOutboxPersistence

    def invite_actor_to_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
        attributed_to: str | None = None,
        roles: list[str] | None = None,
        target: VulnerabilityCase | None = None,
        rsvp_deadline: datetime | None = None,
        published: datetime | None = None,
        in_reply_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Invite(Actor, CaseStub)`` activity.

        ``actor`` MUST be the CASE_MANAGER's ID (PCR-08-007); ``attributed_to``
        MAY carry the case owner's ID for attribution.  The Invite carries no
        ``cc`` (CM-17-006, ADR-0109).

        ``roles`` carries the intended CVD roles for the invitee (CM-17-003).
        ``target`` may be a core ``as_VulnerabilityCase`` (projected to an enriched
        stub by the factory), a pre-built ``as_VulnerabilityCaseStub``, or a bare
        URI string.  When ``None``, the case is read from the DataLayer by
        ``case_id`` and passed to the factory with any active embargo entity for
        CM-17-002 enrichment.
        """
        extra = _addressing(actor, to, id_)
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to
        if rsvp_deadline is not None:
            extra["end_time"] = rsvp_deadline
        if published is not None:
            extra["published"] = published
        if in_reply_to is not None:
            extra["in_reply_to"] = in_reply_to

        # Read case and embargo from DataLayer; factory handles projection.
        resolved: Any = target
        if resolved is None:
            resolved = self._dl.read(case_id)
            if not isinstance(resolved, VulnerabilityCase):
                resolved = case_id

        embargo_obj = (
            _active_embargo_of(self._dl, resolved)
            if isinstance(resolved, VulnerabilityCase)
            else None
        )

        activity = rm_invite_to_case_activity(
            invitee=_held_actor(self._dl, invitee_id),
            target=resolved,
            roles=roles,
            embargo_obj=embargo_obj,
            **extra,
        )
        activity = _stamped(self._dl, activity)
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            # A retry of the emit for the same request rebuilds the Invite
            # under its derived id (OX-06-002): expected, not a fault.
            logger.info(
                "invite_actor_to_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def accept_case_invite(
        self,
        invite_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Invite)`` activity.

        The ``to:`` field is derived from ``invite.actor`` (the original
        sender of the invitation) so that OX-08-001 is satisfied and the
        Accept is routable via the outbox handler.  ``_as_id`` is used to
        extract the URI whether the stored actor field is a plain string or a
        hydrated AS2 object; a ``VultronValidationError`` is raised if the
        invite carries no routable actor reference.
        """
        invite = _stored_case_invite(self._dl, invite_id)
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"accept_case_invite: invite '{invite_id}' has no routable"
                " actor field; cannot derive Accept recipient"
            )
        activity = rm_accept_invite_to_case_activity(
            invite=invite, actor=actor, to=[invite_actor_id]
        )
        return _create_and_seal(self._dl, activity, "accept_case_invite")

    def reject_case_invite(
        self,
        invite_id: str,
        actor: str,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Invite)`` activity.

        The ``to:`` field is derived from ``invite.actor`` (the original
        sender of the invitation) so that the Reject is routable via the
        outbox handler.  Mirrors ``accept_case_invite`` but uses
        ``rm_reject_invite_to_case_activity``.
        """
        invite = _stored_case_invite(self._dl, invite_id)
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"reject_case_invite: invite '{invite_id}' has no routable"
                " actor field; cannot derive Reject recipient"
            )
        activity = rm_reject_invite_to_case_activity(
            invite=invite, actor=actor, to=[invite_actor_id]
        )
        return _create_and_seal(self._dl, activity, "reject_case_invite")

    def invite_actor_to_full_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist the full-case ``Invite(Actor)[target=Case]``."""
        extra = _addressing(actor, to, id_)
        activity = rm_invite_to_full_case_activity(
            invitee=_held_actor(self._dl, invitee_id),
            case=case_id,
            ledger_tail=LedgerPosition(
                log_index=ledger_log_index, entry_hash=ledger_entry_hash
            ),
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "invite_actor_to_full_case"
        )

    def _full_case_reply(
        self,
        builder: Callable[..., Any],
        label: str,
        invite_id: str,
        actor: str,
        position: LedgerPosition,
    ) -> tuple[str, str]:
        """Persist the reply *builder* makes to the stored full-case Invite."""
        invite = _stored_case_invite(self._dl, invite_id)
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"{label}: invite '{invite_id}' has no routable actor field;"
                " cannot derive the reply's recipient"
            )
        activity = builder(
            invite=invite,
            ledger_tail=position,
            actor=actor,
            to=[invite_actor_id],
        )
        return _create_and_seal(self._dl, activity, label)

    def accept_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
    ) -> tuple[str, str]:
        """Create and persist ``Accept(full-case Invite)`` — RV."""
        return self._full_case_reply(
            rm_accept_full_case_invite_activity,
            "accept_full_case_invite",
            invite_id,
            actor,
            LedgerPosition(
                log_index=ledger_log_index, entry_hash=ledger_entry_hash
            ),
        )

    def tentative_reject_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
    ) -> tuple[str, str]:
        """Create and persist ``TentativeReject(full-case Invite)`` — RI."""
        return self._full_case_reply(
            rm_tentative_reject_full_case_invite_activity,
            "tentative_reject_full_case_invite",
            invite_id,
            actor,
            LedgerPosition(
                log_index=ledger_log_index, entry_hash=ledger_entry_hash
            ),
        )

    def reject_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
    ) -> tuple[str, str]:
        """Create and persist ``Reject(full-case Invite)`` — RC."""
        return self._full_case_reply(
            rm_reject_full_case_invite_activity,
            "reject_full_case_invite",
            invite_id,
            actor,
            LedgerPosition(
                log_index=ledger_log_index, entry_hash=ledger_entry_hash
            ),
        )

    def _answer_case_participant_offer(
        self,
        build: Callable[..., as_Accept | as_Reject],
        label: str,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None,
    ) -> tuple[str, str]:
        """Build, persist and seal the Case Owner's answer to a forwarded Offer.

        Shared by the Accept (CM-16-006) and the Reject (CM-16-007).  The
        Offer is read as received: parsed from the body intake archived,
        which holds the participant inline (#3763).  The answer embeds it
        verbatim, and addresses the case as the Offer did (AKM-02-002).
        """
        cp_offer = cast(
            as_Offer,
            read_received_as_received(
                self._dl, cp_offer_id, "Offer(CaseParticipant)"
            ),
        )
        target = _as_id(getattr(cp_offer, "target", None))
        activity = build(offer=cp_offer, actor=actor, to=to, target=target)
        return _create_and_seal(self._dl, activity, label)

    def accept_case_participant_offer(
        self,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer(CaseParticipant))`` activity.

        Sent by the Case Owner to the CaseActor after reviewing the
        Offer(CaseParticipant) forwarded per ADR-0026 (CM-16-006).
        The ``to:`` list should contain the CaseActor URI so the Accept routes
        back to CaseActor for processing.
        """
        return self._answer_case_participant_offer(
            accept_case_participant_offer_activity,
            "accept_case_participant_offer",
            cp_offer_id,
            actor,
            to,
        )

    def reject_case_participant_offer(
        self,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Offer(CaseParticipant))`` activity.

        Sent by the Case Owner to the CASE_MANAGER after reviewing the
        Offer(CaseParticipant) forwarded per ADR-0026 (CM-16-007).
        The ``to:`` list should contain the CASE_MANAGER URI so the Reject
        routes back to it for processing.
        """
        return self._answer_case_participant_offer(
            reject_case_participant_offer_activity,
            "reject_case_participant_offer",
            cp_offer_id,
            actor,
            to,
        )

    def suggest_actor_to_case(
        self,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
        roles: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Offer(Actor, Case)`` recommendation activity."""
        extra = _addressing(actor, to, id_)
        # The factory accepts a string for target (case ID).
        activity = recommend_actor_activity(
            recommended=_held_actor(self._dl, recommended_id),
            target=case_id,
            suggested_roles=roles,
            **extra,
        )
        return _create_and_seal(self._dl, activity, "suggest_actor_to_case")

    def offer_actor_to_case(
        self,
        recommender_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        origin: str | None = None,
        to: list[str] | None = None,
        id_: str | None = None,
        roles: list | None = None,
    ) -> tuple[str, str]:
        """Create and persist an Offer(as_CaseParticipant{actor, roles}, Case).

        Transforms the original Offer(Actor, Case) from a recommending
        participant into an Offer(as_CaseParticipant) addressed to the Case Owner.
        ``roles`` defaults to ``[CVDRole.VENDOR]`` when ``None`` (CM-16-003).
        ``origin`` carries the original Offer ID for causal traceability
        (CM-16-004).  An Offer already built under *id_* is returned as
        sealed, without storing a second inline participant.
        """
        if (built := _already_sealed(self._dl, id_)) is not None:
            return built
        extra = _addressing(actor, to, id_)
        if origin is not None:
            extra["origin"] = origin
        activity = offer_case_participant_activity(
            recommended=recommended_id,
            target=case_id,
            roles=roles,
            **extra,
        )
        # Save the inline CaseParticipant so dl.read() can expand it during
        # outbox delivery (AKM-03-003: dehydration stores object_ as a bare ID).
        if isinstance(activity.object_, as_CaseParticipant):
            try:
                self._dl.create(activity.object_)
            except ValueError:
                pass
        return _create_and_seal(self._dl, activity, "offer_actor_to_case")

    def _rebuilt_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
    ) -> as_Offer:
        """The recommender's ``Offer(Actor)``, rebuilt for the answer to embed.

        Built only from what this actor knows: the recommended actor as held
        (:func:`_held_actor`), and no ``published`` or ``updated``, which the
        recommender stated and this actor would otherwise read from its own
        clock (AKM-02-006).  So every rebuild under the same ids produces the
        same body (OX-06-002).
        """
        return recommend_actor_activity(
            recommended=_held_actor(self._dl, recommended_id),
            target=case_id,
            id_=recommendation_id,
            actor=recommender_id,
            published=None,
            updated=None,
        )

    def emit_accept_actor_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an AcceptActorRecommendation activity.

        Sent by the CaseActor to the recommender after the Case Owner accepts
        the Offer(as_CaseParticipant) (CM-16-006 step 3), or at once for an
        actor already invited or joined (CM-16-009).  ``inReplyTo`` names
        the recommendation it answers.
        """
        recommendation = self._rebuilt_recommendation(
            recommender_id, recommendation_id, recommended_id, case_id
        )
        extra = _addressing(actor, to or [recommender_id], id_)
        activity = accept_actor_recommendation_activity(
            offer=recommendation,
            target=case_id,
            in_reply_to=recommendation_id,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "emit_accept_actor_recommendation"
        )

    def emit_reject_actor_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a RejectActorRecommendation activity.

        Sent by the CaseActor to the recommender after the Case Owner rejects
        the Offer(as_CaseParticipant) (CM-16-007 step 3).  ``inReplyTo``
        names the recommendation it answers.
        """
        recommendation = self._rebuilt_recommendation(
            recommender_id, recommendation_id, recommended_id, case_id
        )
        extra = _addressing(actor, to or [recommender_id], id_)
        activity = reject_actor_recommendation_activity(
            offer=recommendation,
            target=case_id,
            in_reply_to=recommendation_id,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "emit_reject_actor_recommendation"
        )

    def add_participant_to_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Add(as_CaseParticipant, Case)`` activity.

        The participant goes inline as the store holds it, removal fact
        cleared.  Returns ``(activity_id, activity_blob)`` (CM-31-011).
        """
        participant = _to_wire(
            self._dl.read(participant_id), as_CaseParticipant
        )
        activity = add_participant_to_case_activity(
            participant=participant,
            target=case_id,
            actor=actor,
            to=to,
            attributed_to=attributed_to,
        )
        return _create_and_seal(self._dl, activity, "add_participant_to_case")

    def remove_participant_from_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        attributed_to: str,
        to: list[str],
    ) -> tuple[str, str]:
        """Create and persist the ``Remove(as_CaseParticipant, Case)`` notice.

        The participant goes inline as the store holds it, removal fact
        included.  Returns ``(activity_id, activity_blob)`` (CM-31-006).
        """
        participant = _to_wire(
            self._dl.read(participant_id), as_CaseParticipant
        )
        activity = remove_participant_from_case_activity(
            participant=participant,
            target=case_id,
            actor=actor,
            attributed_to=attributed_to,
            to=to,
        )
        return _create_and_seal(
            self._dl, activity, "remove_participant_from_case"
        )

    def add_participant_status_to_participant(
        self,
        status_id: str,
        participant_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Add(as_ParticipantStatus, as_CaseParticipant)`` activity."""
        raw = self._dl.read(status_id)
        if raw is None:
            raise VultronNotFoundError(
                "ParticipantStatus",
                f"status '{status_id}' not found",
            )
        # No conversion step: ``as_ParticipantStatus`` *is* ``ParticipantStatus``
        # (ARCH-25-003, ADR-0099), so the object read from the DataLayer is already the
        # class the activity slot wants.  This previously called
        # ``as_ParticipantStatus.from_core(raw)`` to make nested fields survive a
        # boundary that no longer exists; once the pair collapsed, that call raised
        # ``AttributeError: from_core`` and the use case reported "Activity
        # construction failed".
        activity = add_status_to_participant_activity(
            status=cast(as_ParticipantStatus, raw),
            target=participant_id,
            actor=actor,
            to=to,
        )
        activity = _stamped(self._dl, activity)
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "add_participant_status_to_participant: activity '%s' already"
                " exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)[0]

    def offer_case_participant_role(
        self,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        in_reply_to: str | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``.

        The canonical role-delegation wire format introduced by ADR-0039.
        *attributed_to* and *in_reply_to*, when given, make it the
        CASE_MANAGER's forward of a recorded Offer (CM-33-001); a given *id_*
        is kept so a retry rebuilds the same activity (OX-06-002).

        Returns ``(activity_id, activity_dict)``.
        """
        case = _case_for_wire(self._dl, case_id)
        target = _held_actor(self._dl, target_actor_id)
        extra: dict[str, Any] = _addressing(actor, to, id_)
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to
        if in_reply_to is not None:
            extra["in_reply_to"] = in_reply_to
        activity = offer_case_participant_role_activity(
            role=role,
            target_actor=target,
            case=case,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "offer_case_participant_role"
        )

    def _answer_case_participant_role(
        self,
        build: Callable[..., as_Accept | as_Reject],
        label: str,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None,
        id_: str | None,
    ) -> tuple[str, str]:
        """Build, persist and seal one answer to an ``Offer(CaseParticipantRole)``.

        Shared by the Accept and the Reject (ADR-0039): the Offer is rebuilt
        ephemerally so the answer's ``object_`` is a typed
        ``_OfferCaseParticipantRoleActivity``, and a caller-supplied ``id_``
        is kept so a retry rebuilds the same answer (OX-06-002).
        """
        target = _held_actor(self._dl, target_actor_id)
        case = _case_for_wire(self._dl, case_id)
        offer = offer_case_participant_role_activity(
            role=role,
            target_actor=target,
            case=case,
            id_=offer_id,
            actor=vendor_id,
        )
        activity = build(offer=offer, **_addressing(actor, to, id_))
        return _create_and_seal(self._dl, activity, label)

    def accept_case_participant_role(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(_OfferCaseParticipantRoleActivity)`` (ADR-0039)."""
        return self._answer_case_participant_role(
            accept_case_participant_role_activity,
            "accept_case_participant_role",
            offer_id=offer_id,
            case_id=case_id,
            role=role,
            target_actor_id=target_actor_id,
            vendor_id=vendor_id,
            actor=actor,
            to=to,
            id_=id_,
        )

    def reject_case_participant_role(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(_OfferCaseParticipantRoleActivity)`` (ADR-0039)."""
        return self._answer_case_participant_role(
            reject_case_participant_role_activity,
            "reject_case_participant_role",
            offer_id=offer_id,
            case_id=case_id,
            role=role,
            target_actor_id=target_actor_id,
            vendor_id=vendor_id,
            actor=actor,
            to=to,
            id_=id_,
        )

    def propose_case_ownership_transfer(
        self,
        case_id: str,
        transferee_id: str,
        actor: str,
        content: str | None = None,
        to: list[str] | None = None,
        end_time: datetime | None = None,
    ) -> tuple[str, str]:
        """Create and persist the owner's ``Offer(Offer(VulnerabilityCase))``.

        The proposal goes from ``actor`` to the CASE_MANAGER (*to*), which
        makes the inner Offer itself (ADR-0148, TRIG-11-001).  The inner
        Offer names the case by typed reference (ADR-0165), so its shape is
        the Offer the CASE_MANAGER will make, the transferee as its
        ``target`` and, when given, *end_time* as its deadline (CM-21-016).
        """
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if content is not None:
            extra["content"] = content
        activity = propose_case_ownership_transfer_activity(
            case_id,
            target=_held_actor(self._dl, transferee_id),
            end_time=end_time,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "propose_case_ownership_transfer"
        )

    def offer_case_ownership_transfer(
        self,
        case_id: str,
        transferee_id: str,
        actor: str,
        content: str | None = None,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        end_time: datetime | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Offer(VulnerabilityCase)`` ownership transfer.

        The CASE_MANAGER's Offer to ``transferee_id``, made from the owner's
        proposal (ADR-0148, CM-21-005).  The case travels as its typed
        reference (ADR-0165): the transferee is an active participant that
        holds it (CM-21-021), and the reference's ``type`` tells this from a
        ``SUBMIT_REPORT`` offer.  *end_time*, when given, is the Offer's
        deadline to answer (CM-21-016).  An Offer already built under *id_*
        is the earlier attempt's, and its sealed body is handed back
        (ID-04-004, OX-06-002).
        """
        if (built := _already_sealed(self._dl, id_)) is not None:
            return built
        extra: dict[str, Any] = _addressing(actor, to or [transferee_id], id_)
        if content is not None:
            extra["content"] = content
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to
        if end_time is not None:
            extra["end_time"] = end_time
        # The CASE_MANAGER ledgers the Offer it makes, and a ledger snapshot
        # names its case as ``context`` (CLP-07).
        activity = offer_case_ownership_transfer_activity(
            case=case_id,
            target=_held_actor(self._dl, transferee_id),
            context=case_id,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "offer_case_ownership_transfer"
        )

    def accept_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer(VulnerabilityCase))`` ownership transfer.

        See :meth:`_ownership_answer` (TRIG-11-002).
        """
        return self._ownership_answer(
            accept_case_ownership_transfer_activity,
            "accept_case_ownership_transfer",
            offer_id=offer_id,
            actor=actor,
            to=to,
        )

    def reject_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Offer(VulnerabilityCase))`` ownership transfer.

        See :meth:`_ownership_answer` (TRIG-11-005).
        """
        return self._ownership_answer(
            reject_case_ownership_transfer_activity,
            "reject_case_ownership_transfer",
            offer_id=offer_id,
            actor=actor,
            to=to,
        )

    def withdraw_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist the owner's ``Undo`` of its own proposal.

        *offer_id* names the ``Offer(Offer(VulnerabilityCase))`` this actor
        sent, held under its own id (TRIG-11-006, CM-21-015, ADR-0148).  The
        Undo goes to *to*, the CASE_MANAGER; there is no fallback, since the
        proposal's ``actor`` is this actor itself.
        """
        proposal = read_held_as_received(
            self._dl, offer_id, "Offer(Offer(VulnerabilityCase))"
        )
        activity = undo_case_ownership_transfer_activity(
            proposal=cast(as_Offer, proposal), actor=actor, to=to
        )
        return _create_and_seal(
            self._dl, activity, "withdraw_case_ownership_transfer"
        )

    def _ownership_answer(
        self,
        factory: Callable[..., as_Accept | as_Reject],
        label: str,
        offer_id: str,
        actor: str,
        to: list[str] | None,
    ) -> tuple[str, str]:
        """Build, persist and seal a reply to an ownership-transfer Offer.

        The reply is the transferee's answer (Accept or Reject).  Reads the
        offer as this actor received it (:func:`read_received_as_received`):
        the CASE_MANAGER's Offer parsed from the body the transferee's intake
        archived, never a record under the id its sender chose (DL-06-006,
        ADR-0148), so the reply embeds it verbatim (DL-06-004).  Derives
        the ``to:`` field from the offer's ``actor`` when not supplied, and
        persists the reply that *factory* builds from it.
        """
        raw = read_received_as_received(
            self._dl, offer_id, "Offer(VulnerabilityCase)"
        )
        offer = cast(as_Offer, raw)
        if to is None:
            # Last resort, used only when the emit node found no local case
            # or CASE_MANAGER to address.  The Offer's actor is the
            # CASE_MANAGER that made it (CM-21-006, CM-21-010).
            offer_actor_id = _as_id(getattr(offer, "actor", None))
            if offer_actor_id:
                to = [offer_actor_id]
        activity = factory(offer=offer, actor=actor, to=to)
        return _create_and_seal(self._dl, activity, label)
