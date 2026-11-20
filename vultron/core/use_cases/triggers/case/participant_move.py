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

"""Trigger use cases for the Case Owner's removal and reinstatement acts.

The Case Owner decides a removal or a reinstatement, so it sends the act
itself, to the case's CASE_MANAGER only (ADR-0199):

- ``remove-participant`` sends ``Remove(<Actor>, origin=<case>)``
  (CM-31-004);
- ``reinstate-participant`` sends ``Add(<Actor>, target=<case>)``
  (CM-31-011).

Each act names the actor as a typed reference, never its ``CaseParticipant``.
The trigger does not pre-judge the act: the CASE_MANAGER's received tree
refuses one from a sender that does not hold ``CASE_OWNER`` with no refusal
notice (CLP-05-006), refuses an Owner's act that breaks the rules with one,
or admits it as the move's ledger entry and announces it to the actor it names.  An Owner that
is also the CASE_MANAGER addresses the act to itself, and its own inbox
admits it under the same rules (OX-12-001).  The sender changes nothing on
its own replica: like every replica, it applies the move from the ledger
entry (CM-31-007, CM-31-045).
"""

import json
import logging
from typing import ClassVar, cast

import py_trees.behaviour

from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.use_cases.triggers._base import SvcActivityTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    ReinstateParticipantTriggerRequest,
    RemoveParticipantTriggerRequest,
)

logger = logging.getLogger(__name__)


class _SvcParticipantMoveUseCase(SvcActivityTriggerBase):
    """Shared frame: send the Case Owner's act naming an actor to the CASE_MANAGER.

    Subclasses name the act they log and the port method that builds it.
    """

    #: The act, in its own words, for the log line.
    _ACT: ClassVar[str]

    def _prepare(self) -> None:
        request = cast(
            RemoveParticipantTriggerRequest
            | ReinstateParticipantTriggerRequest,
            self._request,
        )
        self._actor_id = resolve_actor(request.actor_id, self._dl).id_
        self._case_id = resolve_case(request.case_id, self._dl).id_
        self._participant_actor_id = request.participant_actor_id

    def _build_act(
        self, factory: TriggerActivityPort, case_manager_id: str
    ) -> tuple[str, str]:
        """Build and persist the act through the port; subclasses pick it."""
        raise NotImplementedError

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            activity_id, activity_blob = self._build_act(
                self._factory, case_manager_id
            )
            self._captured["activity"] = json.loads(activity_blob)
            return [activity_id]

        # The act goes to the CASE_MANAGER or nowhere (PCR-08-011): the tree
        # fails before anything is built when the case names none.
        return sender_side_bt(
            case_id=self._case_id, activity_builder=_build_activities
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' sent the CASE_MANAGER %s naming '%s' in case '%s'"
            " (ADR-0199)",
            self._actor_id,
            self._ACT,
            self._participant_actor_id,
            self._case_id,
        )


class SvcRemoveParticipantUseCase(_SvcParticipantMoveUseCase):
    """The Case Owner removes an actor from active participation (CM-31-004).

    Sends ``Remove(<Actor>, origin=<case>)`` to the case's CASE_MANAGER
    only.  The CASE_MANAGER refuses it unless the sender holds
    ``CASE_OWNER`` and the actor is a participant that holds neither
    ``CASE_MANAGER`` nor ``CASE_OWNER``; it reports a removal of an
    already-removed participant as skipped (CM-31-022).
    """

    _ACT: ClassVar[str] = "Remove(<Actor>, origin=<case>)"

    def _build_act(
        self, factory: TriggerActivityPort, case_manager_id: str
    ) -> tuple[str, str]:
        return factory.remove_participant(
            removed_id=self._participant_actor_id,
            case_id=self._case_id,
            actor=self._actor_id,
            to=[case_manager_id],
            at=self._at,
        )


class SvcReinstateParticipantUseCase(_SvcParticipantMoveUseCase):
    """The Case Owner reinstates a removed actor (CM-31-011).

    Sends ``Add(<Actor>, target=<case>)`` to the case's CASE_MANAGER only.
    The CASE_MANAGER refuses it unless the sender holds ``CASE_OWNER``
    (CM-31-043) and the actor is a participant that joined, is removed, and
    holds neither ``CASE_MANAGER`` nor ``CASE_OWNER`` (CM-31-036).
    """

    _ACT: ClassVar[str] = "Add(<Actor>, target=<case>)"

    def _build_act(
        self, factory: TriggerActivityPort, case_manager_id: str
    ) -> tuple[str, str]:
        return factory.reinstate_participant(
            reinstated_id=self._participant_actor_id,
            case_id=self._case_id,
            actor=self._actor_id,
            to=[case_manager_id],
            at=self._at,
        )
