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

"""Reject-proposed-embargo BT nodes (EMB-16-001).

Handles the cascade arm triggered when CS.P/X/A fires while EM is PROPOSED:
abandon the proposed embargo via reject_embargo_invite() and queue an ER
activity to the Case Manager.

Extracted from lifecycle.py to keep that module under the BTND-07-004
500-line limit.
"""

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.models._helpers import _as_id
from vultron.core.predicates.embargo import pxa_is_embargo_eligible
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.services.embargo_ordering import (
    earliest_expiring_embargo_id,
)
from vultron.core.states.em import EM
from vultron.errors import BtNodePreconditionError, VultronError


class RejectProposedEmbargoLifecycleNode(DataLayerActionWithPorts):
    """Apply STRICT reject-invite transition reading embargo_id from the blackboard.

    Cascade-path variant of :class:`RejectEmbargoLifecycleNode` used by
    :func:`~vultron.core.behaviors.embargo.trigger_tree.reject_proposed_embargo_bt`.

    Reads ``embargo_id`` written by ``ReadProposedEmbargoIdNode`` so the
    transition uses the correct proposed embargo rather than a
    construction-time value.

    EMB-16-001: abandons a proposed embargo when P/X/A fires while EM is PROPOSED.
    """

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id_value = case_id
        self._result_out = result_out

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "embargo_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"embargo_id": "/embargo_id"}

    def initialise(self) -> None:
        super().initialise()
        self.embargo_id: str = self.get_input("embargo_id")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        embargo_id = self.embargo_id

        try:
            em_before = read_case_em_state(
                self.datalayer, self._case_id_value, self._result_out
            )
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            result = lifecycle.reject_embargo_invite(
                case_id=self._case_id_value,
                embargo_id=embargo_id,
                actor_id=self.actor_id,
                transition_mode=TransitionMode.STRICT,
                em_before=em_before,
            )
        except VultronError as exc:
            self._result_out["error"] = exc
            self.feedback_message = str(exc)
            return Status.FAILURE

        self._result_out["lifecycle_result"] = result
        self._result_out["em_after"] = result.em_after

        return Status.SUCCESS


class DecideRejectedEmbargoProposalNode(DataLayerActionWithPorts):
    """Apply the case owner's Reject of an open proposal (ER / EJ, EP-08-003).

    Only the owner's answer decides a proposal; a participant's Reject is
    consent, which :class:`RecordParticipantRejectionNode` records.  When
    ``rejecting_actor_id`` is the owner and ``embargo_id`` is still an open
    proposal of the case, this node calls
    ``EmbargoLifecycle.reject_embargo_invite`` for the owner, which drives
    ``PROPOSED → NONE`` or ``REVISE → ACTIVE`` and forgets the proposal
    together (EMB-18-001) — or, while another proposal stays open, only
    forgets this one (EP-08-001).  It leaves the consent record alone:
    :class:`RecordParticipantRejectionNode` runs before it on both paths.  The received path runs it ``STRICT`` in the
    CASE_MANAGER's store; the ledger replay runs it ``OBSERVED`` (EP-09-007).

    Returns SUCCESS and changes nothing when the rejecting actor is not the
    owner, or when the embargo is no longer an open proposal (already
    decided, or the active embargo — a withdrawal, which moves no EM state),
    so a repeated Reject is idempotent.  Returns FAILURE when the case cannot
    be read or the lifecycle refuses the transition (for example ``STRICT``
    EJ with P/X/A set, EMB-04-002).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
        *,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.rejecting_actor_id = rejecting_actor_id
        self.transition_mode = transition_mode

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        if _as_id(case.attributed_to) != self.rejecting_actor_id:
            self.feedback_message = (
                f"'{self.rejecting_actor_id}' is not the owner of case"
                f" '{self.case_id}': its Reject is consent and decides nothing"
            )
            return Status.SUCCESS
        if self.embargo_id not in case.proposed_embargo_ids:
            self.feedback_message = (
                f"Embargo '{self.embargo_id}' is not an open proposal of case"
                f" '{self.case_id}' — nothing to decide"
            )
            return Status.SUCCESS

        try:
            em_before = read_case_em_state(self.datalayer, self.case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).reject_embargo_invite(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=self.rejecting_actor_id,
                transition_mode=self.transition_mode,
                em_before=em_before,
                # RecordParticipantRejectionNode runs first on both paths and
                # has already applied the owner's consent effect (MSM-07-004).
                record_consent=False,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        log_em_transition(
            self.logger,
            self.rejecting_actor_id,
            self.case_id,
            result.em_before,
            result.em_after,
        )
        self.feedback_message = (
            f"Owner rejected embargo '{self.embargo_id}' on case"
            f" '{self.case_id}' (EM {result.em_before} → {result.em_after})"
        )
        return Status.SUCCESS


class OwnerRejectsRevisionAfterDisclosureNode(DataLayerConditionWithPorts):
    """True when the owner's Reject must end the embargo, not keep it (EMB-04-002).

    SUCCESS when ``rejecting_actor_id`` is the case owner, the case is in
    ``REVISE``, ``embargo_id`` is the last open proposal (so the Reject would
    decide the revision, EP-08-001) and CS is already public, exploited or
    attacked.  Returning to the prior terms is then not allowed: the EJ must
    be answered with ET.  FAILURE in every other case, so the owner's Reject
    is decided by :class:`DecideRejectedEmbargoProposalNode` as usual.
    Read-only.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.rejecting_actor_id = rejecting_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        if (
            _as_id(case.attributed_to) == self.rejecting_actor_id
            and case.current_status.em.state == EM.REVISE
            and case.proposed_embargo_ids == [self.embargo_id]
            and not pxa_is_embargo_eligible(case.current_status.pxa.state)
        ):
            self.feedback_message = (
                f"Owner rejected revision '{self.embargo_id}' of case"
                f" '{self.case_id}' with P/X/A set: the embargo ends (ET)"
                " rather than returning to its prior terms (EMB-04-002)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        return Status.FAILURE


class ReadProposedEmbargoIdNode(DataLayerActionWithPorts):
    """Read the earliest-expiring proposed embargo ID and write it to the blackboard.

    Used by the EM PROPOSED cascade arm of ``PublicDisclosureBranchNode``
    (EMB-16-001): when public disclosure fires while EM is PROPOSED we must
    reject the proposed embargo.  Unlike ``ReadEmbargoIdNode`` (which reads
    ``active_embargo``), this node selects from ``proposed_embargoes`` — by
    earliest ``end_time``, never by position (EP-08-002, ADR-0100), since a
    counter-proposal sits *after* the terms it replaced.

    Returns FAILURE when the case is not found, has no proposed embargoes, an
    entry cannot be ordered (a new, deliberate failure path — see the comment
    in ``update``), or the DataLayer is unavailable.  Returns SUCCESS and
    writes ``embargo_id`` to the blackboard on success.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "embargo_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"embargo_id": "/embargo_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        proposed_ids = case.proposed_embargo_ids
        if not proposed_ids:
            self.feedback_message = (
                f"No proposed embargoes on case '{self._case_id}'"
            )
            return Status.FAILURE
        # Failing closed here is deliberate (EP-08-002): before #3470 the node
        # read ``proposed[0]`` and could not fail this way, so an unorderable
        # record now leaves EM at PROPOSED after publication rather than
        # rejecting whichever proposal happened to be readable.
        try:
            embargo_id = earliest_expiring_embargo_id(
                self.datalayer, proposed_ids
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Cannot order the proposed embargoes of case"
                f" '{self._case_id}': {exc}"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE

        self._set_output("embargo_id", embargo_id)
        return Status.SUCCESS


class SendRejectEmbargoActivityNode(_SendEmbargoActivityBase):
    """Build and queue a ``Reject(EmbargoEvent)`` activity.

    Used as the emit step in the EM PROPOSED cascade arm
    (EMB-16-001): reads ``embargo_id`` and ``case_manager_id`` from the
    blackboard and constructs the outbound ER activity via
    ``trigger_activity_factory.reject_embargo``.

    Returns FAILURE (BT-14-001) when the factory is unavailable, a required
    blackboard key is missing, or dispatch raises an exception.
    Returns SUCCESS when the activity is created and queued.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(case_id=case_id, name=name)

    INPUT_PORTS: dict[str, PortInformation] = {
        **_SendEmbargoActivityBase.INPUT_PORTS,
        "embargo_id": PortInformation(data_type=str, required=True),
        "case_manager_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "embargo_id": "/embargo_id",
            "case_manager_id": "/case_manager_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.embargo_id: str = self.get_input("embargo_id")
        self.case_manager_id: str = self.get_input("case_manager_id")

    def _on_factory_unavailable(self) -> Status:
        self.feedback_message = (
            "trigger_activity_factory not available"
            " — reject embargo broadcast FAILURE (BT-14-001)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        return self.embargo_id, self.case_manager_id

    def _call_factory(
        self, actor_id: str, embargo_id: str, case_manager_id: str
    ) -> tuple[str, object]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.reject_embargo(
            proposal_id=embargo_id,
            case_id=self._case_id,
            actor=actor_id,
            to=[case_manager_id],
        )

    def _on_outbox_write_failure(
        self, activity_id: str, exc: Exception
    ) -> Status:
        self.feedback_message = (
            f"Outbox write failed for Reject(EmbargoEvent)"
            f" '{activity_id}': {exc}"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
