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

"""The CASE_MANAGER's own consent row for a proposal it adjudicates (EP-09-002).

The relay never invites the CASE_MANAGER (a container never mails an actor it
hosts, ADR-0109), so a manager that is also a participant with an embargo
stake would keep its proposal row at ``UNINVITED`` and stay unbound forever.
At the commit it answers on its own row directly, with no Invite:

- the manager is the proposer: ``AGREED``, already written by
  ``EmbargoLifecycle.propose_embargo`` (proposing is consenting, ADR-0093);
- the manager holds ``CVDRole.CASE_OWNER``: its consent is its decision as
  owner (EP-09-005) and is not pre-empted here;
- otherwise its policy call-out (``EvaluateEmbargoProposal``, EMB-15-001)
  decides: success writes ``AGREED``, failure ``DECLINED``.

The manager with no participant record on the case holds no stake and writes
nothing.  A row that has already left ``UNINVITED`` (a redelivered proposal) is
left alone.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EmbargoCallOutBundle,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.sender_entitlement import is_case_owner
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.enums.roles import CVDRole
from vultron.errors import BtNodePreconditionError, VultronWiringError

#: Roles of a case container that holds no embargo stake of its own: the
#: manager role, and the coordinator role a manager SHOULD also hold (CBT-01-003).
_CONTAINER_ROLES = frozenset({CVDRole.CASE_MANAGER, CVDRole.COORDINATOR})


class ManagerHoldsUndecidedEmbargoStakeNode(DataLayerConditionWithPorts):
    """Guard: the executing CASE_MANAGER has a stake in the proposal and no answer.

    SUCCESS only when the manager is a participant on the case holding a role
    besides the container roles ``CASE_MANAGER`` and ``COORDINATOR``, is neither
    the proposer (its row is written by the proposal, ADR-0093) nor the case
    owner (EP-09-005), and its row for the embargo is still ``UNINVITED``.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        proposer_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._proposer_id = proposer_id

    def _skip_reason(self) -> str | None:
        """Why the manager writes no row here, or ``None`` when it does.

        Raises on a missing DataLayer, actor or case: the role gate ran in the
        manager's own store, so an absent one is an anomaly that must not read
        as "no stake" (the skip arm fails toward admit, bt-pitfalls).
        """
        if (f := self._require_datalayer_and_actor()) is not None:
            raise VultronWiringError(self.feedback_message or str(f))
        assert self.datalayer is not None
        assert self.actor_id is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            raise BtNodePreconditionError(
                f"{self.name}: case '{self._case_id}' not found"
            )
        if self.actor_id == self._proposer_id:
            return "the manager is the proposer (ADR-0093)"
        participant_id = case.actor_participant_index.get(self.actor_id)
        participant = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if not isinstance(participant, CaseParticipant):
            return "the manager holds no embargo stake"
        stake_roles = set(participant.case_roles) - _CONTAINER_ROLES
        if not stake_roles:
            # The bare container (manager, usually with the coordinator
            # role, CBT-01-003) carries no stake of its own (EP-09-002).
            return "the manager holds only container roles"
        if CVDRole.CASE_OWNER in stake_roles or is_case_owner(
            case, self.actor_id
        ):
            return (
                "the manager is the case owner; its consent is its decision"
                " as owner (EP-09-005)"
            )
        state = participant.consent_for(self._embargo_id)
        if state != EmbargoConsentState.UNINVITED:
            return (
                f"the manager has already answered '{self._embargo_id}'"
                f" ({state})"
            )
        return None

    def update(self) -> Status:
        reason = self._skip_reason()
        if reason is not None:
            self.feedback_message = reason
            return Status.FAILURE
        return Status.SUCCESS


class RecordManagerEmbargoConsentNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Write the executing CASE_MANAGER's own consent row for the embargo.

    ``accept`` selects ``AGREE`` or ``DECLINE`` (CM-18-003): both are legal
    from ``UNINVITED``, which the guard
    :class:`ManagerHoldsUndecidedEmbargoStakeNode` ensures.  Writes through
    ``EmbargoLifecycle.record_participant_consent`` so the row change follows
    the one consent rule.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        accept: bool,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._accept = accept

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        trigger = PEC_Trigger.AGREE if self._accept else PEC_Trigger.DECLINE
        # Catches nothing: a failed write is an internal fault in the
        # manager's own store, not a DECLINE.  Returning FAILURE would let the
        # policy Selector fall through to the decline arm and record a refusal
        # nobody made.
        EmbargoLifecycle(
            persistence=self.datalayer
        ).record_participant_consent(
            case_id=self._case_id,
            actor_id=self.actor_id,
            embargo_id=self._embargo_id,
            pec_trigger=trigger,
        )
        self.feedback_message = (
            f"Recorded the manager's own {trigger.name} of embargo"
            f" '{self._embargo_id}' on case '{self._case_id}' (EP-09-002)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


def record_manager_embargo_consent_tree(
    *,
    case_id: str,
    embargo_id: str,
    proposer_id: str,
    call_out: EmbargoCallOutBundle = EMBARGO_DETERMINISTIC,
) -> py_trees.behaviour.Behaviour:
    """Build the subtree that writes the manager's own consent (EP-09-002).

    SUCCESS when the manager skips (no stake, the proposer, the owner, a row
    already there) or writes its row; the policy call-out picks ``AGREE`` or
    ``DECLINE``.  A failed write raises rather than failing the Selector into
    the decline arm.
    """
    return py_trees.composites.Selector(
        name="RecordManagerEmbargoConsent",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="ManagerHasNoUndecidedStake",
                child=ManagerHoldsUndecidedEmbargoStakeNode(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    proposer_id=proposer_id,
                ),
            ),
            py_trees.composites.Selector(
                name="ManagerPolicyDecides",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="ManagerAccepts",
                        memory=False,
                        children=[
                            call_out.evaluate_embargo_proposal_factory(
                                "EvaluateEmbargoProposalForManager"
                            ),
                            RecordManagerEmbargoConsentNode(
                                case_id=case_id,
                                embargo_id=embargo_id,
                                accept=True,
                                name="RecordManagerAccept",
                            ),
                        ],
                    ),
                    RecordManagerEmbargoConsentNode(
                        case_id=case_id,
                        embargo_id=embargo_id,
                        accept=False,
                        name="RecordManagerDecline",
                    ),
                ],
            ),
        ],
    )


__all__ = [
    "ManagerHoldsUndecidedEmbargoStakeNode",
    "RecordManagerEmbargoConsentNode",
    "record_manager_embargo_consent_tree",
]
