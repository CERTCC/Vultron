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

"""Refusing the Case Owner's close while its embargo is in force (CM-23-011).

Two sides make the same refusal, after the shared check in
:func:`~vultron.core.behaviors.case.owner_close_embargo_guards.owner_close_not_blocked_by_embargo`:
the Case Owner's own ``leave-case`` call (TRIG-13-003) and the CASE_MANAGER's
receipt of its ``Leave(VulnerabilityCase)``.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.node_logger import node_logger
from vultron.errors import VultronInvalidStateTransitionError


class RefuseOwnerLeaveWhileEmbargoedNode(py_trees.behaviour.Behaviour):
    """Fail the ``leave-case`` trigger: the Case Owner must end the embargo first.

    The last child of the trigger's embargo guard Selector, reached only when
    the shared CM-23-011 check found the triggering actor is the Case Owner
    and its replica records an embargo in force.  It always returns FAILURE
    and writes a :class:`~vultron.errors.VultronInvalidStateTransitionError`
    to ``result_out["error"]``, which the trigger use case re-raises (HTTP
    409), so the pre-close call-out does not run and nothing is sent
    (TRIG-13-003).
    """

    def __init__(
        self,
        actor_id: str,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        """Initialize RefuseOwnerLeaveWhileEmbargoedNode.

        Args:
            actor_id: The Case Owner calling ``leave-case``.
            case_id: The case it asked to leave.
            result_out: Mutable dict that receives the domain error.
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.actor_id = actor_id
        self.case_id = case_id
        self._result_out = result_out

    def update(self) -> Status:
        """Record the refusal and fail.

        Returns:
            FAILURE, always, with ``result_out["error"]`` set.
        """
        error = VultronInvalidStateTransitionError(
            f"Case Owner '{self.actor_id}' cannot leave case"
            f" '{self.case_id}' while its embargo is active: terminate the"
            " embargo first (terminate-embargo), then call leave-case"
            " (CM-23-011, TRIG-13-003)"
        )
        self._result_out["error"] = error
        self.feedback_message = str(error)
        node_logger(self).info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class RefuseOwnerCloseWhileEmbargoedNode(py_trees.behaviour.Behaviour):
    """Refuse the Case Owner's received Leave: its embargo is in force.

    The last child of the close-case tree's embargo guard Selector at the
    CASE_MANAGER, reached only when the shared CM-23-011 check found the
    Leave's sender is the Case Owner and the case has an embargo in force.
    It always returns FAILURE, with the refusal in ``feedback_message``, so
    the close-case tree commits nothing, runs none of the CM-23-002 closure
    effects, and answers the owner with the standard refusal notice, a
    ``Refuse`` of the Leave whose ``summary`` is that reason (CLP-02-005,
    CLP-05-001, ADR-0196).  It is read-only.
    """

    def __init__(
        self, case_id: str, sender_actor_id: str, name: str | None = None
    ) -> None:
        """Initialize RefuseOwnerCloseWhileEmbargoedNode.

        Args:
            case_id: The case the Leave names.
            sender_actor_id: The Case Owner that sent the Leave.
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.sender_actor_id = sender_actor_id

    def update(self) -> Status:
        """Fail with the refusal reason.

        Returns:
            FAILURE, always.
        """
        self.feedback_message = (
            f"close of case '{self.case_id}' refused: its embargo is active;"
            f" the Case Owner '{self.sender_actor_id}' must terminate the"
            " embargo first, then send Leave again (CM-23-011)"
        )
        node_logger(self).info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
