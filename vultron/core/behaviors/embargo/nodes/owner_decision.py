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

"""The case owner's decision on an embargo proposal (ADR-0122).

``Accept(EmbargoEvent, target=Case)`` activates a proposal and
``Reject(EmbargoEvent, target=Case)`` rejects it.  These are the owner's
decisions for the case and have activities of their own, so
``Accept``/``Reject(Invite(EmbargoEvent))`` is always the sender's consent and
no node branches on the sender to know what a message means.

- :class:`IsOpenEmbargoProposalNode`, :class:`OwnerMayActivateEmbargoNode`
  — read-only guards ahead of the commit: the decision names an open
  proposal, and nothing refuses its activation (CLP-10-009).
- :class:`ActivateEmbargoLifecycleNode` / :class:`RejectEmbargoProposalLifecycleNode`
  — the ``STRICT`` register write, as the CASE_MANAGER (EP-09-008).
- :class:`SendOwnerEmbargoDecisionNode` — the owner's replica queues its
  decision to the CASE_MANAGER (PCR-08-001).
"""

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.invite_answer import (
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    _EmbargoLifecycleNode,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.predicates.embargo import pxa_is_embargo_eligible
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
    owner_declined_embargo,
)


class IsOpenEmbargoProposalNode(DataLayerConditionWithPorts):
    """Guard: the owner's decision names an open proposal of the case.

    SUCCESS when ``embargo_id`` is a ``PROPOSED`` entry of the case's embargo
    register.  Anything else — the embargo in force, a proposal already
    decided or cancelled, an embargo the case never saw — has nothing left to
    decide, so the decision is refused before the commit and no replica is
    sent an entry it cannot replay (CLP-10-009, SYNC-12-001).  Read-only.
    """

    def __init__(
        self, case_id: str, embargo_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        if self._embargo_id in case.proposed_embargo_ids:
            return Status.SUCCESS
        self.feedback_message = (
            f"embargo '{self._embargo_id}' is not an open proposal of case"
            f" '{self._case_id}' — nothing for the owner to decide"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class OwnerMayActivateEmbargoNode(DataLayerConditionWithPorts):
    """Guard: nothing refuses the owner's activation of this proposal.

    FAILURE when CS is public, exploited or attacked (EMB-02-002: no embargo
    is activated then) or when the owner's row for the proposal is
    ``DECLINED`` (ADR-0122: the owner is invited again before it can
    activate what it declined).  Read-only and ahead of the commit, so a
    refused activation is never ledgered: a replica replays the entry in
    ``OBSERVED`` mode, which does not re-check P/X/A (CLP-10-009,
    SYNC-12-001).
    """

    def __init__(
        self, case_id: str, embargo_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        if not pxa_is_embargo_eligible(case.current_status.pxa.state):
            self.feedback_message = (
                f"case '{self._case_id}' is public, exploited or attacked:"
                f" embargo '{self._embargo_id}' is not activated (EMB-02-002)"
            )
        elif owner_declined_embargo(self.datalayer, case, self._embargo_id):
            self.feedback_message = (
                f"the case owner declined embargo '{self._embargo_id}' on"
                f" case '{self._case_id}': it is invited again before it can"
                " activate it (ADR-0122)"
            )
        else:
            return Status.SUCCESS
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class ActivateEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Apply the owner's ``STRICT`` activation of a proposal (ADR-0122).

    ``EmbargoLifecycle.activate_embargo``: ``ACTIVATE`` the proposal,
    ``SUPERSEDE`` any embargo in force, record the owner's agreement and
    carry signatories over to a revision that ends no later (EP-05-001).
    Refused with P/X/A set (EMB-02-002) or when the owner had declined it.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id_value = case_id
        self._embargo_id = embargo_id

    def _case_id(self) -> str:
        return self._case_id_value

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
    ) -> EmbargoLifecycleResult:
        return lifecycle.activate_embargo(
            case_id=self._case_id_value,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )


class RejectEmbargoProposalLifecycleNode(_EmbargoLifecycleNode):
    """Apply the owner's ``STRICT`` rejection of a proposal (ADR-0122).

    ``EmbargoLifecycle.reject_embargo_proposal``: ``REJECT`` the proposal's
    register entry and write no consent.  Refused when it would return the
    case to the prior terms with P/X/A set (EMB-04-002).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id_value = case_id
        self._embargo_id = embargo_id

    def _case_id(self) -> str:
        return self._case_id_value

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
    ) -> EmbargoLifecycleResult:
        return lifecycle.reject_embargo_proposal(
            case_id=self._case_id_value,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )


class SendOwnerEmbargoDecisionNode(SendEmbargoInviteAnswerNode):
    """Queue the case owner's decision on a proposal to the CASE_MANAGER.

    The owner's answer to an embargo Invite is its decision for the case, so
    it is sent as ``Accept`` or ``Reject`` of the ``EmbargoEvent`` with the
    case as ``target`` (ADR-0122), never of the Invite.  Addressing and the
    raise-on-failure contract are :class:`SendEmbargoInviteAnswerNode`'s:
    the node is an arm's action in the EMB-15 response Selector, so a
    FAILURE must never fall through to the opposite answer.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        *,
        accept: bool,
        name: str | None = None,
    ) -> None:
        # The base addresses the factory by the id it resolves first; for
        # the owner's decision that is the embargo, not an Invite.
        super().__init__(
            case_id=case_id, invite_id=embargo_id, accept=accept, name=name
        )

    @property
    def _verb(self) -> str:
        return "Activate" if self._accept else "RejectProposal"

    def _call_factory(
        self, actor_id: str, embargo_id: str, case_manager_id: str
    ) -> tuple[str, object]:
        assert self.trigger_activity_factory is not None
        build = (
            self.trigger_activity_factory.activate_embargo
            if self._accept
            else self.trigger_activity_factory.reject_embargo_proposal
        )
        return build(
            embargo_id=embargo_id,
            case_id=self._case_id,
            actor=actor_id,
            to=[case_manager_id],
        )


__all__ = [
    "ActivateEmbargoLifecycleNode",
    "IsOpenEmbargoProposalNode",
    "OwnerMayActivateEmbargoNode",
    "RejectEmbargoProposalLifecycleNode",
    "SendOwnerEmbargoDecisionNode",
]
