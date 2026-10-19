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

"""The stub Invite the Case Owner's Accept sends, from the recorded Offer.

CM-16-006 step 4: once the Case Owner accepts an ``Offer(CaseParticipant)``,
the CASE_MANAGER invites the recommended actor and seats its inert record
(ADR-0114, CM-11-006).  The invitee and its roles are the recorded Offer's,
never the Accept's copy (ISSUE-1745, CM-16-019), so both nodes here read the
:class:`~vultron.core.behaviors.case.nodes.suggest_actor.recorded_offer.RecordedOfferAnswer`
that ``RequireRecordedOfferAnswerNode`` published for the Accept.

Classes: :class:`EmitRecordedInviteNode`, :class:`SeatRecordedInviteeNode`.
"""

from vultron.core.behaviors.case.nodes.invite_actor_emit import (
    _StubInviteEmitBase,
)
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    _SeatInertInviteeBase,
    validated_invitee_roles,
)
from vultron.core.behaviors.case.nodes.suggest_actor.recorded_offer import (
    RecordedOfferAnswerInputMixin,
    recorded_offer_answer_key,
)
from vultron.enums.roles import CVDRole


class EmitRecordedInviteNode(
    RecordedOfferAnswerInputMixin, _StubInviteEmitBase
):
    """Send the stub Invite to the invitee of the Offer the Case Owner accepted.

    The Invite offers the recorded Offer's roles (none when it carries none)
    and its id derives from the recommendation it answers, so a retry of the
    tree for one recommendation rebuilds one Invite (OX-06-002).
    """

    def __init__(
        self, answer_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._answer_key = recorded_offer_answer_key(answer_id)

    def _invitee(self) -> str:
        return self._recorded_answer().invitee_id

    def _read_suggested_roles(self) -> list[str] | None:
        return list(self._recorded_answer().roles) or None

    def _answered_request(self) -> str | None:
        return self._recorded_answer().recommendation_id


class SeatRecordedInviteeNode(
    RecordedOfferAnswerInputMixin, _SeatInertInviteeBase
):
    """Seat the inert record of the invitee of the Offer the Case Owner accepted.

    Its roles are the recorded Offer's; an Offer that carries none seats
    nothing and fails (CM-11-019).
    """

    def __init__(
        self, answer_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._answer_key = recorded_offer_answer_key(answer_id)

    def _invitee(self) -> str:
        return self._recorded_answer().invitee_id

    def _resolve_roles(self) -> list[CVDRole]:
        return validated_invitee_roles(self._recorded_answer().roles)


__all__ = ["EmitRecordedInviteNode", "SeatRecordedInviteeNode"]
