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


"""TriggerParticipantsPort: the participants part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Participant offers, actor recommendations, participant membership and status.
"""

from datetime import datetime
from typing import Any, Protocol


class TriggerParticipantsPort(Protocol):
    """Participant offers, actor recommendations, participant membership and status."""

    def accept_case_participant_offer(
        self,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer(CaseParticipant))`` activity.

        Sent by the Case Owner to the CaseActor after reviewing the
        Offer(CaseParticipant) forwarded per ADR-0026 (CM-16-006).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def reject_case_participant_offer(
        self,
        cp_offer_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Offer(CaseParticipant))`` activity.

        Sent by the Case Owner to the CASE_MANAGER after reviewing the
        Offer(CaseParticipant) forwarded per ADR-0026 (CM-16-007).
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
        roles: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Offer(Actor)[target=VulnerabilityCase]``
        recommendation activity.

        ``id_`` allows callers to supply a deterministic ID for idempotency.
        ``roles`` carries serialized CVD role strings into the wire object so
        the CaseActor can use them in place of the hardcoded VENDOR default.
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
        content: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Offer(CaseParticipant)[target=VulnerabilityCase]`` activity.

        Transforms the original ``Offer(Actor)[target=VulnerabilityCase]`` into an
        ``Offer(CaseParticipant)[target=VulnerabilityCase]`` naming the actor and
        its roles, addressed to the Case Owner.  ``roles`` defaults to
        ``[CVDRole.VENDOR]`` when ``None`` (CM-16-003).  ``origin`` carries the
        original recommender Offer ID so the Case Owner can trace the causal
        chain (CM-16-004).  ``content`` carries the recommender's reason text
        from its ``Offer(Actor)`` so the Case Owner can decide on the
        suggestion with its evidence (CM-16-020).
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
        *,
        at: datetime,
    ) -> tuple[str, str]:
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
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``RejectActorRecommendation`` activity.

        Sent by the CaseActor to the original recommender after the Case Owner
        rejects the Offer(CaseParticipant) (CM-16-007 step 3).
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def add_participant_to_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Add(CaseParticipant)[target=VulnerabilityCase]`` activity.

        The CASE_MANAGER's direct notice to a reinstated participant
        (CM-31-011): ``actor`` is the CASE_MANAGER and ``attributed_to`` the
        Case Owner who asked for the reinstatement (CM-24-001, CM-24-002).
        The notice is delivery, not a record, so the caller does not ledger
        it.

        Returns ``(activity_id, activity_blob)``.
        """
        ...

    def remove_participant_from_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        attributed_to: str,
        to: list[str],
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Remove(CaseParticipant)[target=VulnerabilityCase]`` notice.

        The CASE_MANAGER's direct notice to a removed participant (CM-31-006):
        ``actor`` is the CASE_MANAGER and ``attributed_to`` the Case Owner who
        asked for the removal (CM-24-001, CM-24-002).  The notice is delivery,
        not a record, so the caller does not ledger it.

        Returns ``(activity_id, activity_blob)``.
        """
        ...

    def add_participant_status_to_participant(
        self,
        status_id: str,
        participant_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> str:
        """Create and persist an ``Add(ParticipantStatus)[target=CaseParticipant]`` activity.

        Returns the activity ID (callers only need the ID for outbox queueing).
        """
        ...
