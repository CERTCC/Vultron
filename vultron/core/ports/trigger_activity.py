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
    - ``notes/activity-factories.md``
"""

from typing import Any, Protocol


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

    # -----------------------------------------------------------------------
    # Cases
    # -----------------------------------------------------------------------

    def create_case(
        self,
        case_id: str,
        actor: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Create(VulnerabilityCase)`` activity.

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

    # -----------------------------------------------------------------------
    # Actors (invitations, recommendations)
    # -----------------------------------------------------------------------

    def invite_actor_to_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Invite(Actor, Case)`` activity.

        ``id_`` allows callers to supply a deterministic ID for idempotency.
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

    def suggest_actor_to_case(
        self,
        recommended_id: str,
        case_id: str,
        actor: str,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Offer(Actor, Case)`` recommendation activity.

        ``id_`` allows callers to supply a deterministic ID for idempotency.
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
