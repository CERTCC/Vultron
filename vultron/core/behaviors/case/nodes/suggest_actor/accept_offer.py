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

"""Case Owner owner-side Accept response for the suggest-actor workflow (CM-16).

Split from :mod:`vultron.core.behaviors.case.nodes.suggest_actor.emit` to keep
each leaf module under the BTND-07-004 line limit.  This module holds the
owner-side response node; ``emit`` retains the CaseActor-side forwarding and
notification nodes.
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.ports.case_persistence import CaseOutboxPersistence


class EmitAcceptCaseParticipantOfferNode(DataLayerAction):
    """Case Owner sends Accept(Offer(CaseParticipant)) back to the CaseActor.

    Triggered by the Case Owner after reviewing the Offer(CaseParticipant)
    forwarded per ADR-0026 (CM-16-006 owner-side response).  The Accept is
    addressed to the CaseActor so it can proceed with inviting the suggested
    actor.
    """

    def __init__(
        self,
        cp_offer_id: str,
        case_actor_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.cp_offer_id = cp_offer_id
        self.case_actor_id = case_actor_id
        self._captured = captured

    def _emit(self) -> tuple[str, dict]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.accept_case_participant_offer(
            cp_offer_id=self.cp_offer_id,
            actor=self.actor_id,
            to=[self.case_actor_id],
        )

    def update(self) -> Status:
        fail = self._require_datalayer_and_actor()
        if fail is not None:
            return fail
        fail = self._require_factory()
        if fail is not None:
            self.logger.error(self.feedback_message)
            return fail

        try:
            activity_id, activity_dict = self._emit()
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id  # type: ignore[arg-type]
            )
            if self._captured is not None:
                self._captured["activity"] = activity_dict
            self.logger.info(
                "Actor '%s' accepted Offer(CaseParticipant) '%s' → CaseActor '%s'",
                self.actor_id,
                self.cp_offer_id,
                self.case_actor_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.feedback_message = (
                f"EmitAcceptCaseParticipantOffer failed: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


__all__ = [
    "EmitAcceptCaseParticipantOfferNode",
]
