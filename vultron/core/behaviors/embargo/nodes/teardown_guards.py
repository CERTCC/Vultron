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

"""Guards a received embargo removal passes before its teardown commits.

:class:`HasEmbargoActiveNode` asks whether teardown is still owed, and
:class:`TerminationIsTimelyNode` refuses a termination claimed before the
embargo in force may end.  The teardown nodes themselves are in
:mod:`~vultron.core.behaviors.embargo.nodes.teardown`.
"""

from datetime import datetime
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
    optional_act_value,
)
from vultron.core.behaviors.act_keys import (
    CASE_ID,
    EMBARGO,
    EMBARGO_ID,
    TERMINATED_AT,
)
from vultron.core.behaviors.embargo.copy_commit import (
    read_embargo_case_file,
    trial_apply,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.ending_notice_replica import (
    adopted_revision_timing_violations,
)
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import (
    decide_termination,
    termination_timing_violations,
)
from vultron.core.states.em import EM
from vultron.errors import (
    INTERNAL_FAULTS,
    BtNodePreconditionError,
    VultronEntryRefusedError,
    VultronError,
    VultronInvalidStateTransitionError,
)


class HasEmbargoActiveNode(DataLayerConditionWithPorts):
    """Condition: EM state is ACTIVE or REVISE (embargo is active).

    Returns SUCCESS when ``case.em_state`` is not EXITED
    (i.e., the embargo is still active and teardown has not been applied).
    Returns FAILURE when EM is EXITED (teardown already done — idempotent
    guard) or when the case is not found.

    Uses ``ReadEmStateNode`` to read EM state (AC-1 of issue #1554).  The
    case is read from ``/case_id`` (BTND-01-008).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        **act_key_ports(CASE_ID),
    }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(CASE_ID)

    def initialise(self) -> None:
        super().initialise()
        self.case_id: str = act_value(self, CASE_ID, str)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            em_state = read_case_em_state(self.datalayer, self.case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if em_state == EM.EXITED:
            self.feedback_message = f"Case '{self.case_id}' EM already EXITED — teardown not needed"
            return Status.FAILURE

        return Status.SUCCESS


class TerminationIsTimelyNode(DataLayerConditionWithPorts):
    """Guard: a received termination may end the embargo in force now.

    FAILURE when *termination*'s cause is ``END_TIME_REACHED`` claimed at
    *terminated_at* before the end time of the case's embargo in force, or
    carries no time (EMB-13-008); SUCCESS otherwise, an early termination
    or a case with no embargo in force included.  It runs among the received
    tree's precondition guards, so a refused termination is never committed
    (CLP-10-006).  An embargo that cannot be read fails closed (EMB-18-003).

    With *embargo_id* (the embargo the ``Remove`` names) in force, the
    ``TERMINATE`` step is also trial-applied through the one apply function
    (ADR-0124): a step it refuses refuses the act before the guarded commit of its
    entry, so no entry is ledgered for a change that cannot be applied.

    At a paused signatory's replica (CM-31-010), a named revision it has not
    activated is adopted ahead of the teardown (CM-31-042), so the claim is
    judged against that revision's own end time: the stored record, else
    *embargo*, the ``Remove``'s inline copy (EMB-18-003).

    The case is read from ``/case_id`` (BTND-01-008), *terminated_at* from
    ``/terminated_at``, *embargo_id* from ``/embargo_id`` and *embargo* from
    ``/embargo``.  The last three are optional ports, and an unseeded one
    reads whatever its key already holds rather than ``None``.
    ``ReadEmbargoIdNode`` publishes ``/embargo_id`` elsewhere, so a tree that
    runs this guard seeds ``/embargo_id`` for it from the ``Remove``.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        **act_key_ports(CASE_ID, TERMINATED_AT, EMBARGO_ID, EMBARGO),
    }

    def __init__(
        self,
        termination: EmbargoTermination,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._termination = termination

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(CASE_ID, TERMINATED_AT, EMBARGO_ID, EMBARGO)

    def initialise(self) -> None:
        super().initialise()
        self.case_id: str = act_value(self, CASE_ID, str)
        self._terminated_at = optional_act_value(self, TERMINATED_AT, datetime)
        self._embargo_id = optional_act_value(self, EMBARGO_ID, str)
        self._embargo = optional_act_value(self, EMBARGO, EmbargoEvent)

    def _violations(self, case: VulnerabilityCase) -> list[str]:
        dl = cast(CasePersistence, self.datalayer)
        adopted = adopted_revision_timing_violations(
            dl,
            case,
            self.actor_id,
            self._embargo_id,
            self._embargo,
            self._termination,
            self._terminated_at,
        )
        if adopted is not None:
            return adopted
        if (
            self._embargo_id is None
            or case.active_embargo_id != self._embargo_id
        ):
            return termination_timing_violations(
                dl, case, self._termination, self._terminated_at
            )
        try:
            step = decide_termination(
                dl, case, self._termination, self._terminated_at
            )
            trial_apply(read_embargo_case_file(dl, self.case_id), [step])
        except (
            VultronInvalidStateTransitionError,
            VultronEntryRefusedError,
        ) as exc:
            return [str(exc)]
        return []

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        try:
            violations = self._violations(case)
        except INTERNAL_FAULTS:
            raise  # never a refusal, so never answered (ADR-0095)
        except VultronError as exc:
            violations = [str(exc)]
        if not violations:
            return Status.SUCCESS
        self.feedback_message = (
            f"Refused termination on case '{self.case_id}': "
            + "; ".join(violations)
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
