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

import json
import logging
from collections.abc import Mapping
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.ownership_transfer_offer_record import (
    VultronOwnershipTransferOfferRecord,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases._helpers import read_received_activity
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
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.factories.case import (
    accept_case_ownership_transfer_activity,
    accept_case_participant_role_activity,
    offer_case_ownership_transfer_activity,
    offer_case_participant_role_activity,
    reject_case_participant_role_activity,
    rm_reject_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
    as_Offer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from ._base import _case_for_wire, _seal, _to_wire

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


def _stored_invite_by_case_uri(
    dl: CaseOutboxPersistence, invite_id: str
) -> as_Invite:
    """Read the received Invite with its ``target`` reduced to the case URI.

    The Invite is read as this invitee holds it (``read_received_activity``):
    archived by intake, or held by the inbox while it waits for the case
    bootstrap.  The reply factory checks that it is a case Invite.  The Accept
    or Reject that embeds the Invite goes to the CASE_MANAGER, which holds the
    case, so the embedded Invite addresses it by URI (AKM-02-003) rather than
    carrying the stub or a reconstruction of it (VM-08-003).

    The held record is validated into ``as_Invite`` here, at the adapter
    edge (ADR-0032): intake archives the activity as the event carried it,
    a core activity the wire factories cannot name (ARCH-22-001).

    Raises:
        VultronNotFoundError: when no activity with *invite_id* was received.
        VultronValidationError: when the stored record is not a model, its
            inline ``target`` carries no id, or it does not validate as an
            Invite.
    """
    held = read_received_activity(dl, invite_id, "RmInviteToCaseActivity")
    if not isinstance(held, BaseModel):
        raise VultronValidationError(
            f"invite '{invite_id}' is held as {type(held).__name__},"
            " not as an activity model"
        )
    # The protocol's ``model_copy`` returns the protocol; read it as the model.
    invite = cast(BaseModel, held)
    target = getattr(invite, "target", None)
    # Read back from the archive, an inline target may be a plain mapping
    # rather than a model, so its id is taken from either form.
    if isinstance(target, Mapping):
        target_id = target.get("id")
    else:
        target_id = _as_id(target)
    if target is not None and not isinstance(target, str):
        if not target_id:
            raise VultronValidationError(
                f"invite '{invite_id}' names its case with no id;"
                " cannot address the reply to the case"
            )
        invite = invite.model_copy(update={"target": target_id})
    if isinstance(invite, as_Invite):
        return invite
    try:
        return as_Invite.model_validate(
            json.loads(
                invite.model_dump_json(by_alias=True, serialize_as_any=True)
            )
        )
    except ValidationError as exc:
        raise VultronValidationError(
            f"invite '{invite_id}' does not validate as an Invite"
        ) from exc


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
    ) -> tuple[str, str]:
        """Create and persist an ``Invite(Actor, Case)`` activity.

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
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if id_ is not None:
            extra["id_"] = id_
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to

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
            invitee=invitee_id,
            target=resolved,
            roles=roles,
            embargo_obj=embargo_obj,
            **extra,
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
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
        invite = _stored_invite_by_case_uri(self._dl, invite_id)
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"accept_case_invite: invite '{invite_id}' has no routable"
                " actor field; cannot derive Accept recipient"
            )
        activity = rm_accept_invite_to_case_activity(
            invite=invite, actor=actor, to=[invite_actor_id]
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "accept_case_invite: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

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
        invite = _stored_invite_by_case_uri(self._dl, invite_id)
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"reject_case_invite: invite '{invite_id}' has no routable"
                " actor field; cannot derive Reject recipient"
            )
        activity = rm_reject_invite_to_case_activity(
            invite=invite, actor=actor, to=[invite_actor_id]
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "reject_case_invite: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

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
        raw = self._dl.read(cp_offer_id)
        if raw is None:
            raise VultronNotFoundError("Offer(CaseParticipant)", cp_offer_id)
        cp_offer = cast(as_Offer, raw)
        # Read-back rehydrates the offer's ``target`` into the full stored
        # case; the Accept addresses the case by URI, as the Offer did on the
        # wire (AKM-02-002, VM-08-003).
        target = _as_id(getattr(cp_offer, "target", None))
        if target is not None:
            # The embedded Offer carries the same reconstruction one level
            # down; it addressed the case by URI on the wire too.
            cp_offer = cp_offer.model_copy(update={"target": target})
        activity = accept_case_participant_offer_activity(
            offer=cp_offer, actor=actor, to=to, target=target
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "accept_case_participant_offer: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

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
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if id_ is not None:
            extra["id_"] = id_
        # The factory accepts a string for target (case ID).
        activity = recommend_actor_activity(
            recommended=recommended_id,
            target=case_id,
            suggested_roles=roles,
            **extra,
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "suggest_actor_to_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

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
        (CM-16-004).
        """
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if id_ is not None:
            extra["id_"] = id_
        if origin is not None:
            extra["origin"] = origin
        activity = offer_case_participant_activity(
            recommended=recommended_id,
            target=case_id,
            roles=roles,
            **extra,
        )
        # Save the inline CaseParticipant so dl.read() can expand it during
        # outbox delivery (AKM-03-001: dehydration stores object_ as a bare ID).
        if isinstance(activity.object_, as_CaseParticipant):
            try:
                self._dl.create(activity.object_)
            except ValueError:
                pass
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "offer_actor_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

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
        the Offer(as_CaseParticipant) (CM-16-006 step 3).
        """
        recommendation = recommend_actor_activity(
            recommended=recommended_id,
            target=case_id,
            id_=recommendation_id,
            actor=recommender_id,
        )
        extra: dict[str, Any] = {"actor": actor, "to": to or [recommender_id]}
        if id_ is not None:
            extra["id_"] = id_
        activity = accept_actor_recommendation_activity(
            offer=recommendation, target=case_id, **extra
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "emit_accept_actor_recommendation: activity '%s' already"
                " exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

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
        the Offer(as_CaseParticipant) (CM-16-007 step 3).
        """
        recommendation = recommend_actor_activity(
            recommended=recommended_id,
            target=case_id,
            id_=recommendation_id,
            actor=recommender_id,
        )
        extra: dict[str, Any] = {"actor": actor, "to": to or [recommender_id]}
        if id_ is not None:
            extra["id_"] = id_
        activity = reject_actor_recommendation_activity(
            offer=recommendation, target=case_id, **extra
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "emit_reject_actor_recommendation: activity '%s' already"
                " exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def accept_actor_recommendation(
        self,
        recommended_id: str,
        recommender_id: str,
        recommendation_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer)`` actor-recommendation activity.

        The recommendation offer is reconstructed ephemerally (not read from
        DataLayer) to allow callers that never stored the offer to still
        accept it, provided they know its deterministic ID.
        """
        recommendation = recommend_actor_activity(
            recommended=recommended_id,
            target=case_id,
            id_=recommendation_id,
            actor=recommender_id,
        )
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if id_ is not None:
            extra["id_"] = id_
        activity = accept_actor_recommendation_activity(
            offer=recommendation, target=case_id, **extra
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "accept_actor_recommendation: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def add_participant_to_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Add(as_CaseParticipant, Case)`` activity.

        Returns ``(activity_id, activity_blob)``; the blob is what the emitting
        node records as the ledger ``payloadSnapshot`` (VM-08-003).
        """
        participant = _to_wire(
            self._dl.read(participant_id), as_CaseParticipant
        )
        activity = add_participant_to_case_activity(
            participant=participant, target=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "add_participant_to_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

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
        # (ADR-0099 detail 3), so the object read from the DataLayer is already the
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
    ) -> tuple[str, str]:
        """Create and persist ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``.

        The canonical role-delegation wire format introduced by ADR-0039.
        Replaces the deprecated :meth:`offer_case_manager_role` for new senders.

        Returns ``(activity_id, activity_dict)``.
        """
        case = _case_for_wire(self._dl, case_id)
        target = as_Actor(id_=target_actor_id)
        activity = offer_case_participant_role_activity(
            role=role,
            target_actor=target,
            case=case,
            actor=actor,
            to=to,
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "offer_case_participant_role: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def accept_case_participant_role(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(_OfferCaseParticipantRoleActivity)`` (ADR-0039)."""
        target = as_Actor(id_=target_actor_id)
        case = _case_for_wire(self._dl, case_id)
        offer = offer_case_participant_role_activity(
            role=role,
            target_actor=target,
            case=case,
            id_=offer_id,
            actor=vendor_id,
        )
        activity = accept_case_participant_role_activity(
            offer=offer, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "accept_case_participant_role: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def reject_case_participant_role(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(_OfferCaseParticipantRoleActivity)`` (ADR-0039)."""
        target = as_Actor(id_=target_actor_id)
        case = _case_for_wire(self._dl, case_id)
        offer = offer_case_participant_role_activity(
            role=role,
            target_actor=target,
            case=case,
            id_=offer_id,
            actor=vendor_id,
        )
        activity = reject_case_participant_role_activity(
            offer=offer, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "reject_case_participant_role: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def offer_case_ownership_transfer(
        self,
        case_id: str,
        transferee_id: str,
        actor: str,
        content: str | None = None,
        to: list[str] | None = None,
        attributed_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Offer(VulnerabilityCase)`` ownership transfer.

        Emits the offer from ``actor`` to ``transferee_id``.  The case is read
        from the DataLayer and passed inline so the recipient can distinguish
        this from a ``SUBMIT_REPORT`` offer (TRIG-11-001).
        """
        case = _case_for_wire(self._dl, case_id)
        extra: dict[str, Any] = {
            "actor": actor,
            "to": to or [transferee_id],
        }
        if content is not None:
            extra["content"] = content
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to
        activity = offer_case_ownership_transfer_activity(
            case=case,
            target=transferee_id,
            **extra,
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "offer_case_ownership_transfer: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def accept_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer(VulnerabilityCase))`` ownership transfer.

        Reads the stored offer from the DataLayer, derives the ``to:`` field
        from the offer's ``actor`` when not supplied, and persists the Accept
        (TRIG-11-002).

        On a replica whose only source for the Offer was the replicated
        ``offer_case_ownership_transfer`` ledger entry, what is stored at
        ``offer_id`` is a core ``VultronOwnershipTransferOfferRecord`` rather
        than the wire activity — the SYNC path cannot construct wire objects
        (ARCH-03-001).  Rebuild the wire Offer from that record here, where wire
        imports are allowed, so both delivery paths converge on the same Accept
        (#2225, ADR-0035 DL-06-002).
        """
        raw = self._dl.read(offer_id)
        if raw is None:
            raise VultronNotFoundError("Offer(VulnerabilityCase)", offer_id)
        if isinstance(raw, VultronOwnershipTransferOfferRecord):
            raw = self._offer_from_core_record(raw)
        offer = cast(as_Offer, raw)
        if to is None:
            offer_actor_id = _as_id(getattr(offer, "actor", None))
            if offer_actor_id:
                to = [offer_actor_id]
        activity = accept_case_ownership_transfer_activity(
            offer=offer, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "accept_case_ownership_transfer: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def _offer_from_core_record(
        self, record: "VultronOwnershipTransferOfferRecord"
    ) -> Any:
        """Rebuild the wire ownership-transfer Offer from its core record.

        ``_OfferCaseOwnershipTransferActivity.object_`` MUST be an inline
        ``as_VulnerabilityCase`` — a bare URI is rejected at construction and
        would also make the activity indistinguishable from a SUBMIT_REPORT
        Offer during semantic dispatch.  The case itself is already on the
        replica (the SYNC path seeds it before the offer entry is applied), so
        read it and project it to its wire form.
        """
        case = self._dl.read(record.case_id)
        if case is None:
            raise VultronNotFoundError("VulnerabilityCase", record.case_id)
        if not isinstance(case, as_VulnerabilityCase):
            raise VultronValidationError(
                f"Record '{record.case_id}' is a {type(case).__name__},"
                " not a VulnerabilityCase"
            )
        wire_case = case
        # Reuse the same factory the offering side calls, so the rebuilt Offer
        # is constructed exactly the way the wire path would have built it
        # (test/architecture/test_activity_factory_imports.py forbids adapters
        # from reaching into vultron.wire.as2.vocab.activities directly).
        return offer_case_ownership_transfer_activity(
            case=wire_case,
            target=record.target_id,
            id_=record.offer_id,
            actor=record.actor_id,
        )
