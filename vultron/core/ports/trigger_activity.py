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

"""Driven port for creating and storing trigger-related wire activities.

:class:`TriggerActivityPort` is the interface core trigger use cases and BT
nodes use to create, store, and queue outbound ActivityStreams activities.
Defining the port here keeps ``vultron/core/`` completely free of wire-layer
imports (ARCH-01-001).

Methods return ``(activity_id, activity_dict)`` so callers can:

1. Queue the ``activity_id`` to the actor's outbox.
2. Include the ``activity_dict`` in the HTTP response.

Methods that create domain objects (notes, reports, cases) return
``(object_id, object_dict)`` using the same convention.

Methods only used for outbox queueing (no response body needed) return
``str`` (the activity ID alone).

Port direction: **outbound (driven)** — core constructs trigger requests and
the adapter handles wire-format construction, DataLayer persistence, and
returns the serialized result.

See also:
    - ``vultron/adapters/driven/trigger_activity_adapter.py`` — adapter
    - ``specs/architecture.yaml`` ARCH-01-001, ARCH-01-004
    - ``vultron/wire/as2/factories/AGENTS.md``
"""

from typing import Any, Protocol

from vultron.core.models.case import VulnerabilityCase


class TriggerActivityPort(Protocol):
    """Driven port for trigger-related outbound wire activity construction.

    Core trigger use cases and BT nodes call these methods with domain-level
    parameters (string IDs, primitive types) and receive activity IDs and
    serialized dictionaries in return.  The adapter handles all wire-format
    construction and DataLayer persistence.

    All methods that create an activity persist it to the DataLayer and return
    at minimum the activity's ID.  Methods whose results are included in HTTP
    responses also return a serialized ``dict``.
    """

    # -----------------------------------------------------------------------
    # Notes
    # -----------------------------------------------------------------------

    def create_note(
        self,
        name: str,
        content: str,
        context_id: str,
        attributed_to: str,
        in_reply_to: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a Note object; return ``(note_id, note_dict)``."""
        ...

    def create_note_activity(
        self,
        actor: str,
        note_id: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist a ``Create(Note)`` activity; return activity_id."""
        ...

    def add_note_to_case(
        self,
        note_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Add(Note, Case)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    # -----------------------------------------------------------------------
    # Reports
    # -----------------------------------------------------------------------

    def submit_report(
        self,
        report_id: str,
        actor: str,
        to: str,
        target: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Offer(VulnerabilityReport)`` activity.

        Returns ``(offer_id, offer_dict)``.
        """
        ...

    def close_report(
        self,
        offer_id: str,
        report_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Reject(Offer)`` close-report activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def invalidate_report(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``TentativeReject(Offer)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def validate_report(
        self,
        offer_id: str,
        report_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Offer)`` validate-report activity.

        Returns ``(activity_id, activity_dict)``.
        Per ADR-0021 CLP-10-001: routes the activity to the Case Actor.
        """
        ...

    def ack_report(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Read(Offer(Report))`` ack-report activity.

        Per ADR-0021 CLP-10-001: routes the activity to the Case Actor so the
        CaseActor can commit a canonical ledger entry for this event.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    # -----------------------------------------------------------------------
    # Cases
    # -----------------------------------------------------------------------

    def create_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Create(VulnerabilityCase)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def close_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Leave(VulnerabilityCase)`` close-case activity.

        Per ADR-0021 CLP-10-001: routes the activity to the Case Actor so the
        CaseActor can commit a canonical ledger entry.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def engage_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(VulnerabilityCase)`` engage activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def defer_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``TentativeReject(VulnerabilityCase)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def add_object_to_case(
        self,
        actor: str,
        object_id: str,
        case_id: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Add(object, Case)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def create_case_proposal(
        self,
        actor: str,
        report_id: str,
        case_actor_id: str,
        summary: str | None = None,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Create(as_CaseProposal)`` activity.

        Builds an ``as_CaseProposal`` from the ``VulnerabilityReport``
        identified by ``report_id``, addressed to the case-actor service at
        ``case_actor_id``, and persists ``Create(as_CaseProposal)`` to the
        DataLayer.

        Per ``specs/case-proposal.yaml`` CP-04-001, CP-04-002.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    # -----------------------------------------------------------------------
    # Actors (invitations, recommendations)
    # -----------------------------------------------------------------------

    def invite_actor_to_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        cc: list[str] | None = None,
        id_: str | None = None,
        attributed_to: str | None = None,
        roles: list[str] | None = None,
        target: VulnerabilityCase | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Invite(Actor, Case)`` activity.

        ``actor`` SHOULD be the Case Actor ID (PCR-08-007); ``attributed_to``
        MAY carry the case owner's ID for attribution.
        ``cc`` MAY carry the Case Actor's own ID for self-archival (CLP-10-001).
        ``id_`` allows callers to supply a deterministic ID for idempotency.
        ``roles`` carries the intended CVD roles for the invitee (CM-17-003).
        ``target`` may be a core ``VulnerabilityCase`` (the adapter projects it
        to an enriched stub including ``end_time`` when ``em_state == EM.ACTIVE``),
        a pre-built stub, or a bare URI string.  When ``None``, the adapter reads
        the case from the DataLayer by ``case_id`` (CM-17-002).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_case_invite(
        self,
        invite_id: str,
        actor: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Invite)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_case_participant_offer(
        self,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Offer(CaseParticipant))`` activity.

        Sent by the Case Owner to the CaseActor after reviewing the
        Offer(CaseParticipant) forwarded per ADR-0026 (CM-16-006).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def suggest_actor_to_case(
        self,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Offer(Actor, Case)`` recommendation activity.

        ``id_`` allows callers to supply a deterministic ID for idempotency.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def offer_actor_to_case(
        self,
        recommender_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        origin: str | None = None,
        to: list[str] | None = None,
        id_: str | None = None,
        roles: list[Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Offer(CaseParticipant, Case)`` activity.

        Transforms the original ``Offer(Actor, Case)`` into an
        ``Offer(CaseParticipant{actor, roles}, Case)`` addressed to the
        Case Owner.  ``roles`` defaults to ``[CVDRole.VENDOR]`` when
        ``None`` (CM-16-003).  ``origin`` carries the original recommender
        Offer ID so the Case Owner can trace the causal chain (CM-16-004).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def emit_accept_actor_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``AcceptActorRecommendation`` activity.

        Sent by the CaseActor to the original recommender after the Case Owner
        accepts the Offer(CaseParticipant) (CM-16-006 step 3).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def emit_reject_actor_recommendation(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``RejectActorRecommendation`` activity.

        Sent by the CaseActor to the original recommender after the Case Owner
        rejects the Offer(CaseParticipant) (CM-16-007 step 3).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_actor_recommendation(
        self,
        recommended_id: str,
        recommender_id: str,
        recommendation_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Offer)`` actor-recommendation activity.

        The recommendation offer is reconstructed ephemerally from
        ``recommended_id``, ``recommender_id``, ``recommendation_id``, and
        ``case_id``; it does not need to already exist in the DataLayer.
        ``id_`` allows callers to supply a deterministic ID for idempotency.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def add_participant_to_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Add(CaseParticipant, Case)`` activity.

        Returns the activity ID (callers only need the ID for outbox queueing).
        """
        ...

    def add_participant_status_to_participant(
        self,
        status_id: str,
        participant_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Add(ParticipantStatus, CaseParticipant)`` activity.

        Returns the activity ID (callers only need the ID for outbox queueing).
        """
        ...

    # -----------------------------------------------------------------------
    # Case Actor / CASE_MANAGER delegation
    # -----------------------------------------------------------------------

    def offer_case_manager_role(
        self,
        case_id: str,
        participant_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Offer(VulnerabilityCase, target=CaseParticipant)``
        CASE_MANAGER delegation activity.

        ``participant_id`` must refer to an existing ``CaseParticipant`` with
        ``CASE_MANAGER`` role (the Case Actor participant).

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_case_manager_role(
        self,
        offer_id: str,
        case_id: str,
        participant_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(_OfferCaseManagerRoleActivity)``.

        Ephemerally reconstructs the original Offer (using ``offer_id``,
        ``case_id``, ``participant_id``, and ``vendor_id``) before building
        the Accept so that ``Accept.object_`` is a typed
        ``_OfferCaseManagerRoleActivity``, not a bare string IRI.

        Returns ``(activity_id, activity_dict)`` where ``activity_dict`` is
        the full inline serialization of the Accept (with nested Offer
        inlined), suitable for use as a canonical payload snapshot.
        """
        ...

    def reject_case_manager_role(
        self,
        offer_id: str,
        case_id: str,
        participant_id: str,
        vendor_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist a ``Reject(_OfferCaseManagerRoleActivity)``.

        Ephemerally reconstructs the original Offer (using ``offer_id``,
        ``case_id``, ``participant_id``, and ``vendor_id``) before building
        the Reject so that ``Reject.object_`` is a typed
        ``_OfferCaseManagerRoleActivity``, not a bare string IRI.

        Returns the activity ID.
        """
        ...

    # -----------------------------------------------------------------------
    # Embargo
    # -----------------------------------------------------------------------

    def propose_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Invite(EmbargoEvent, Case)`` proposal.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Invite)`` embargo-accept activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def reject_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Reject(Invite)`` embargo-reject activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def announce_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Announce(EmbargoEvent)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def terminate_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Remove(EmbargoEvent, origin=case)`` ET activity.

        Corresponds to the ET (Embargo Termination) protocol message.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def offer_case_ownership_transfer(
        self,
        case_id: str,
        transferee_id: str,
        actor: str,
        content: str | None = None,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Offer(VulnerabilityCase)`` ownership-transfer activity.

        Returns ``(activity_id, activity_dict)`` (TRIG-11-001).
        """
        ...

    def accept_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Offer(VulnerabilityCase))`` ownership-transfer activity.

        Returns ``(activity_id, activity_dict)`` (TRIG-11-002).
        """
        ...

    def announce_vulnerability_case(
        self,
        case_id: str,
        actor: str,
        context_id: str,
        to: list[str],
    ) -> str:
        """Create and persist an ``Announce(VulnerabilityCase)`` activity.

        Sent by the case owner to a newly accepted participant after their
        embargo consent is resolved (MV-10-003).  The full case object is
        sent inline so the recipient can seed their local DataLayer.

        Returns the activity ID.
        """
        ...
