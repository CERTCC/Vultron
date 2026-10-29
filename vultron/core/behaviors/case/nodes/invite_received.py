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

"""Invitee-side effect nodes for a received ``Invite(Actor, CaseStub)``.

The invitee holds only the Invite's case stub until the CASE_MANAGER announces
the case (MV-10-003, MV-10-004), so it records two things and creates no case:
the narrative milestone (SL-04-006) and the trust anchor that lets it admit the
inviting CASE_MANAGER's later ``Announce`` before its replica exists
(PCR-03-004).  Composed by ``create_invite_actor_to_case_received_tree``
behind ``create_participant_replica_gated_tree`` (BTND-07-003).

:class:`FixInviteTrustAnchorNode` closes the anchor's life cycle from the
invitee's own Accept: ``accept_case_invite_trigger_bt`` runs it once the
Accept is queued, after which the anchor can no longer be replaced.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.narrative_log import log_invite_received
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.predicates.addressing import same_actor_id

logger = logging.getLogger(__name__)


class LogInviteReceivedNode(DataLayerAction):
    """Log the invitee's receipt of a case invitation at INFO (SL-04-006)."""

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        sender_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id
        self.sender_id = sender_id

    def update(self) -> Status:
        log_invite_received(
            logger, self.invitee_id, self.case_id, self.sender_id
        )
        logger.debug(
            "%s: invite holds case stub '%s'. Awaiting"
            " AnnounceVulnerabilityCase before creating the case (MV-10-004)",
            self.name,
            self.case_id,
        )
        return Status.SUCCESS


class RecordInviteTrustAnchorNode(DataLayerAction):
    """Record the inviting CASE_MANAGER as the case's expected Announce sender.

    Writes a :class:`VultronPendingCaseInbox` so
    ``AnnounceVulnerabilityCaseReceivedUseCase`` admits a later Announce from
    the same actor before the local case replica exists (PCR-03-004 path b).

    Trust rules (PCR-03-004, issue #4185):

    - **AC-1**: Refuses when the Invite's ``object`` (``invitee_id``) is not
      the receiving actor (``self.actor_id``); no record is written.
    - **AC-2**: The anchor is bound to the Invite's ``actor`` id
      (``case_actor_id``); the transport-level delivering sender is never
      consulted — the caller must supply the Invite's own ``actor`` field.
    - **AC-3**: A later Invite for the same case naming a *different*
      CaseActor replaces the anchor while the invitee has not accepted the
      Invite that set it, and is REFUSED once it has (``invite_accepted``,
      set by :class:`FixInviteTrustAnchorNode`): the fixed anchor is
      unchanged and a WARNING names both ids.  A forged Invite therefore
      cannot lock out the real CASE_MANAGER's Invite, though it can still
      win if the invitee accepts it first (#2841).

    Idempotent on an exact duplicate (same ``case_actor_id``); a re-Invite
    from the same CaseActor that no Accept has fixed moves
    ``anchor_invite_id`` to the newer Invite.  A record no Invite has
    anchored yet — created by the pre-bootstrap queue for an earlier
    activity, whose sender it records but does not trust — takes the Invite's CaseActor in place of that sender: it
    is not a second Invite (#4931).  Every record the node writes or confirms
    is marked ``invite_anchored``, so the anchored CASE_MANAGER check trusts
    it and the pre-bootstrap queue's expiry keeps it (PCR-03-004,
    CBT-03-003).

    Note: whether the named CaseActor is genuine cannot be verified until
    actor identity and signatures are in place (#2841).
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        case_actor_id: str,
        invite_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id
        self.case_actor_id = case_actor_id
        self.invite_id = invite_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        # AC-1: The Invite's object must be the receiving actor.
        if not same_actor_id(self.invitee_id, self.actor_id or ""):
            self.feedback_message = (
                f"Invite object '{self.invitee_id}' is not the receiving"
                f" actor '{self.actor_id}' — refusing trust anchor"
                f" (PCR-03-004 path b)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        existing = self.datalayer.read(
            VultronPendingCaseInbox.build_id(self.case_id)
        )
        if not isinstance(existing, VultronPendingCaseInbox):
            # First Invite for this case: write the anchor.
            self.datalayer.save(
                VultronPendingCaseInbox(
                    case_id=self.case_id,
                    case_actor_id=self.case_actor_id,
                    invite_anchored=True,
                    anchor_invite_id=self.invite_id,
                )
            )
            self.logger.info(
                "%s: trust anchor recorded for case '%s' (CaseActor '%s')",
                self.name,
                self.case_id,
                self.case_actor_id,
            )
        elif existing.invite_anchored and self._names_this_case_actor(
            existing
        ):
            self._repeat_from_anchored_case_actor(existing)
        elif existing.invite_anchored and existing.invite_accepted:
            # AC-3: the invitee accepted the anchoring Invite — refuse.
            self.feedback_message = (
                f"Trust anchor conflict for case '{self.case_id}':"
                f" existing CaseActor '{existing.case_actor_id}', whose"
                f" Invite was accepted, new Invite's actor"
                f" '{self.case_actor_id}' — refusing (PCR-03-004 path b)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        else:
            self._replace_unfixed_anchor(existing)

        return Status.SUCCESS

    def _names_this_case_actor(self, record: VultronPendingCaseInbox) -> bool:
        return record.case_actor_id is not None and same_actor_id(
            record.case_actor_id, self.case_actor_id
        )

    def _repeat_from_anchored_case_actor(
        self, existing: VultronPendingCaseInbox
    ) -> None:
        """Keep the anchor; follow a newer Invite no Accept has fixed yet."""
        assert self.datalayer is not None
        if existing.invite_accepted or existing.anchor_invite_id in (
            None,
            self.invite_id,
        ):
            # Idempotent re-delivery, or the anchor is already fixed.
            self.logger.debug(
                "%s: trust anchor already set for case '%s' (idempotent)",
                self.name,
                self.case_id,
            )
            return
        self.datalayer.save(
            existing.model_copy(update={"anchor_invite_id": self.invite_id})
        )
        self.logger.debug(
            "%s: trust anchor for case '%s' now awaits the Accept of Invite"
            " '%s' (CaseActor '%s')",
            self.name,
            self.case_id,
            self.invite_id,
            self.case_actor_id,
        )

    def _replace_unfixed_anchor(
        self, existing: VultronPendingCaseInbox
    ) -> None:
        """Anchor this Invite in place of a sender no Accept has fixed.

        The record was written by the pre-bootstrap queue, whose sender is no
        anchor (#4931), or by an Invite the invitee has not accepted, which a
        later Invite replaces (PCR-03-004).
        """
        assert self.datalayer is not None
        self.datalayer.save(
            existing.model_copy(
                update={
                    "case_actor_id": self.case_actor_id,
                    "invite_anchored": True,
                    "anchor_invite_id": self.invite_id,
                    "invite_accepted": False,
                }
            )
        )
        if existing.invite_anchored:
            self.logger.info(
                "%s: trust anchor for case '%s' replaced: Invite from"
                " CaseActor '%s' supersedes unaccepted Invite from '%s'"
                " (PCR-03-004)",
                self.name,
                self.case_id,
                self.case_actor_id,
                existing.case_actor_id,
            )
        elif existing.case_actor_id is None:
            self.logger.info(
                "%s: trust anchor recorded for case '%s' (CaseActor '%s')",
                self.name,
                self.case_id,
                self.case_actor_id,
            )
        elif self._names_this_case_actor(existing):
            self.logger.info(
                "%s: queue's sender for case '%s' confirmed as trust"
                " anchor (CaseActor '%s')",
                self.name,
                self.case_id,
                self.case_actor_id,
            )
        else:
            self.logger.info(
                "%s: trust anchor recorded for case '%s' (CaseActor"
                " '%s'), replacing queue-recorded sender '%s'",
                self.name,
                self.case_id,
                self.case_actor_id,
                existing.case_actor_id,
            )


class FixInviteTrustAnchorNode(DataLayerAction):
    """Fix the trust anchor an accepted stub Invite set (PCR-03-004 path b).

    Runs after the invitee's ``Accept(Invite)`` is queued.  The anchor record
    whose ``anchor_invite_id`` is the accepted Invite is marked
    ``invite_accepted``, after which a later Invite naming another CaseActor
    is refused instead of replacing it (:class:`RecordInviteTrustAnchorNode`).
    An Invite that anchors nothing — superseded by a later Invite, or its
    record already removed by the case bootstrap — fixes nothing.
    """

    def __init__(self, invite_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invite_id = invite_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        for record in self.datalayer.list_objects("PendingCaseInbox"):
            if not (
                isinstance(record, VultronPendingCaseInbox)
                and record.invite_anchored
                and record.anchor_invite_id == self.invite_id
            ):
                continue
            if not record.invite_accepted:
                self.datalayer.save(
                    record.model_copy(update={"invite_accepted": True})
                )
                self.logger.info(
                    "%s: trust anchor for case '%s' fixed by the Accept of"
                    " Invite '%s' (CaseActor '%s')",
                    self.name,
                    record.case_id,
                    self.invite_id,
                    record.case_actor_id,
                )
            return Status.SUCCESS

        self.logger.debug(
            "%s: Invite '%s' anchors no pending case record — nothing to fix",
            self.name,
            self.invite_id,
        )
        return Status.SUCCESS
