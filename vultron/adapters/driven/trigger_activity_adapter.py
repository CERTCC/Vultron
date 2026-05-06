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

"""Adapter implementing
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Reads persisted objects from the DataLayer, calls the appropriate wire-layer
factory functions to construct outbound ActivityStreams activities, persists
the activities, and returns ``(activity_id, activity_dict)`` or
``activity_id`` to callers.

This adapter is the **sole** location where trigger-related domain→wire
translation occurs for activity construction, keeping ``vultron/core/`` free
of wire-layer factory imports (ARCH-01-001).

See also:
    - ``vultron/core/ports/trigger_activity.py`` — port Protocol
    - ``vultron/wire/as2/factories/`` — factory functions
    - ``notes/activity-factories.md``
"""

import logging
from typing import Any, cast

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    add_note_to_case_activity,
    add_participant_to_case_activity,
    announce_embargo_activity,
    create_case_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    recommend_actor_activity,
    rm_accept_invite_to_case_activity,
    rm_close_report_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    rm_invalidate_report_activity,
    rm_invite_to_case_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseStub,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

logger = logging.getLogger(__name__)

_DUMP_KWARGS: dict[str, Any] = {"by_alias": True, "exclude_none": True}


class TriggerActivityAdapter:
    """Driven adapter for constructing and persisting outbound wire activities.

    Instantiate once per request with the DataLayer for that request; pass to
    :class:`~vultron.core.use_cases.triggers.service.TriggerService` as
    ``trigger_activity``.

    Args:
        dl: The DataLayer for reading persisted objects and creating activities.
    """

    def __init__(self, dl: CaseOutboxPersistence) -> None:
        self._dl = dl

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
        note = as_Note(
            name=name,
            content=content,
            context=context_id,
            attributed_to=attributed_to,
            in_reply_to=in_reply_to,
        )
        try:
            self._dl.create(note)
        except ValueError:
            logger.warning(
                "create_note: note '%s' already exists — skipping", note.id_
            )
        return note.id_, note.model_dump(**_DUMP_KWARGS)

    def create_note_activity(
        self,
        actor: str,
        note_id: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist a ``Create(Note)`` activity; return activity_id."""
        note = cast(as_Note, self._dl.read(note_id))
        activity = as_Create(actor=actor, object_=note, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "create_note_activity: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_

    def add_note_to_case(
        self,
        note_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Add(Note, Case)`` activity."""
        note = cast(as_Note, self._dl.read(note_id))
        activity = add_note_to_case_activity(
            note=note, target=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_note_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

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
        """Create and persist an ``Offer(VulnerabilityReport)`` activity."""
        report = cast(VulnerabilityReport, self._dl.read(report_id))
        activity = rm_submit_report_activity(
            report=report, to=to, actor=actor, target=target
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "submit_report: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def close_report(
        self,
        offer_id: str,
        report_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Reject(Offer)`` close-report activity."""
        offer = cast(Any, self._dl.read(offer_id))
        activity = rm_close_report_activity(offer=offer, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "close_report: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def invalidate_report(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``TentativeReject(Offer)`` activity."""
        offer = cast(Any, self._dl.read(offer_id))
        activity = rm_invalidate_report_activity(
            offer=offer, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "invalidate_report: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    # -----------------------------------------------------------------------
    # Cases
    # -----------------------------------------------------------------------

    def create_case(
        self,
        case_id: str,
        actor: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Create(VulnerabilityCase)`` activity."""
        case = cast(VulnerabilityCase, self._dl.read(case_id))
        activity = create_case_activity(case=case, actor=actor)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "create_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def engage_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(VulnerabilityCase)`` engage activity."""
        case = cast(VulnerabilityCase, self._dl.read(case_id))
        activity = rm_engage_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "engage_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def defer_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``TentativeReject(VulnerabilityCase)`` activity."""
        case = cast(VulnerabilityCase, self._dl.read(case_id))
        activity = rm_defer_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "defer_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def add_object_to_case(
        self,
        actor: str,
        object_id: str,
        case_id: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Add(object, Case)`` activity."""
        case = cast(Any, self._dl.read(case_id))
        obj = cast(Any, self._dl.read(object_id))
        activity = as_Add(actor=actor, object_=obj, target=case)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_object_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

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
        """Create and persist an ``Invite(Actor, Case)`` activity."""
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if id_ is not None:
            extra["id_"] = id_
        activity = rm_invite_to_case_activity(
            invitee=as_Actor(id_=invitee_id),
            target=VulnerabilityCaseStub(id_=case_id),
            **extra,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "invite_actor_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def accept_case_invite(
        self,
        invite_id: str,
        actor: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Invite)`` activity."""
        invite = cast(Any, self._dl.read(invite_id))
        activity = rm_accept_invite_to_case_activity(
            invite=invite, actor=actor
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "accept_case_invite: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def suggest_actor_to_case(
        self,
        recommended_id: str,
        case_id: str,
        actor: str,
        id_: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Offer(Actor, Case)`` recommendation activity."""
        extra: dict[str, Any] = {"actor": actor}
        if id_ is not None:
            extra["id_"] = id_
        # The factory accepts a string for target (case ID).
        activity = recommend_actor_activity(
            recommended=as_Actor(id_=recommended_id),
            target=case_id,
            **extra,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "suggest_actor_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

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

        The recommendation offer is reconstructed ephemerally (not read from
        DataLayer) to allow callers that never stored the offer to still
        accept it, provided they know its deterministic ID.
        """
        recommendation = recommend_actor_activity(
            recommended=as_Actor(id_=recommended_id),
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
        except ValueError:
            logger.warning(
                "accept_actor_recommendation: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def add_participant_to_case(
        self,
        participant_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Add(CaseParticipant, Case)`` activity."""
        participant = cast(CaseParticipant, self._dl.read(participant_id))
        activity = add_participant_to_case_activity(
            participant=participant, target=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_participant_to_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_

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
        """Create and persist an ``Invite(EmbargoEvent, Case)`` proposal."""
        embargo = cast(EmbargoEvent, self._dl.read(embargo_id))
        activity = em_propose_embargo_activity(
            embargo=embargo, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "propose_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def accept_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Invite)`` embargo-accept activity."""
        proposal = cast(Any, self._dl.read(proposal_id))
        activity = em_accept_embargo_activity(
            proposal=proposal, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "accept_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def reject_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Reject(Invite)`` embargo-reject activity."""
        proposal = cast(Any, self._dl.read(proposal_id))
        activity = em_reject_embargo_activity(
            proposal=proposal, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "reject_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def announce_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Announce(EmbargoEvent)`` activity."""
        embargo = cast(EmbargoEvent, self._dl.read(embargo_id))
        activity = announce_embargo_activity(
            embargo=embargo, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "announce_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)
