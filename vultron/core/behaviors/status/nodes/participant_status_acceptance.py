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

"""Whole accept or reject for a received ParticipantStatus (RSH-09, ADR-0107).

An inbound ``Add(ParticipantStatus, CaseParticipant)`` states the sender's whole
status, so the CASE_MANAGER accepts it as sent or refuses all of it
(RSH-09-001).  It never records a status the sender did not send: a status
rewritten before it is recorded is one nobody asserted, and the ledger exists
to record what was asserted (ADR-0107, CLP-07-013).

:func:`participant_status_refusals` applies each dimension's acceptance rule
and the cross-machine entailments to the status as received, and reports every
dimension that fails (RSH-09-002, RSH-09-003, EH-07-001).
:class:`CheckParticipantStatusAcceptableNode` is the read-only precondition
guard that runs it before ``GuardedCommit`` (CLP-10-006): any refusal fails the
guard, so nothing is committed, written or appended, and the refusal notice
carries the reasons to the sender (CLP-05-001).

Per specs/received-status-handling.yaml RSH-09.
"""

import logging
from typing import NamedTuple

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.status.nodes.rm_rule import (
    BB_RM_ANOMALY,
    rm_anomaly,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.predicates.roles import has_deployer_role, has_vendor_role
from vultron.core.states.composite_state_invariants import (
    composite_state_violations,
)
from vultron.core.states.cs import (
    is_monotonic_d_forward,
    is_monotonic_vf_forward,
    is_pxa_assertion_acceptable,
)
from vultron.core.states.rm import RM, RMDeclaration, classify_rm_declaration
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class DimensionRefusal(NamedTuple):
    """One dimension of a received status that its acceptance rule refuses."""

    dimension: str
    reason: str


def _rm_refusal(current: RM, asserted: RM) -> DimensionRefusal | None:
    """Return the refusal of the asserted RM state, or ``None`` to accept it.

    ``RM.CLOSED`` is terminal: once a participant has closed, no status it
    sends can be accepted, a restated ``CLOSED`` included (RSH-09-003).
    Otherwise the received-side RM rule decides, shared with the
    activity-typed RM handlers (RSH-06-006): a confirmation, an adjacent move
    and a non-adjacent forward move are accepted, a regression is refused
    (RSH-06-001, RSH-06-002).
    """
    if current is RM.CLOSED:
        return DimensionRefusal(
            "rm",
            f"the participant is already at {RM.CLOSED.name}, which is"
            " terminal",
        )
    if classify_rm_declaration(current, asserted) is RMDeclaration.REGRESSION:
        return DimensionRefusal(
            "rm",
            f"{current.name} → {asserted.name} moves RM backwards",
        )
    return None


def _path_refusals(
    current: ParticipantStatus,
    asserted: ParticipantStatus,
    roles: list[CVDRole] | None,
) -> list[DimensionRefusal]:
    """Return the refusals of the asserted fix-readiness and deployment states.

    A ``vf`` value needs the VENDOR role and a ``d`` value the DEPLOYER role
    (ADR-0075, #2965); either must confirm or advance the participant's current
    value, non-adjacent advances included (CSB-16-001).  A dimension the
    sender omits is absent from the status it sent, not a claim to refuse
    (ADR-0075); a first observation has nothing to regress from.
    """
    refusals: list[DimensionRefusal] = []
    current_vf = None if current.vf is None else current.vf.state
    asserted_vf = None if asserted.vf is None else asserted.vf.state
    if asserted_vf is not None:
        if roles is not None and not has_vendor_role(roles):
            refusals.append(
                DimensionRefusal(
                    "vf", "the sender does not hold the VENDOR role"
                )
            )
        elif (
            current_vf is not None
            and asserted_vf != current_vf
            and not is_monotonic_vf_forward(current_vf, asserted_vf)
        ):
            refusals.append(
                DimensionRefusal(
                    "vf",
                    f"{current_vf.name} → {asserted_vf.name} is not a forward"
                    " move",
                )
            )
    current_d = None if current.d is None else current.d.state
    asserted_d = None if asserted.d is None else asserted.d.state
    if asserted_d is not None:
        if roles is not None and not has_deployer_role(roles):
            refusals.append(
                DimensionRefusal(
                    "d", "the sender does not hold the DEPLOYER role"
                )
            )
        elif (
            current_d is not None
            and asserted_d != current_d
            and not is_monotonic_d_forward(current_d, asserted_d)
        ):
            refusals.append(
                DimensionRefusal(
                    "d",
                    f"{current_d.name} → {asserted_d.name} is not a forward"
                    " move",
                )
            )
    return refusals


def _pxa_refusal(
    current: ParticipantStatus, asserted: ParticipantStatus
) -> DimensionRefusal | None:
    """Return the refusal of the asserted P/X/A state, or ``None``.

    The embedded ``case_status`` must confirm or advance the participant's
    last reported P/X/A (RSH-09-003).  An omitted ``case_status`` asserts
    nothing about the case, and a first one has nothing to regress from.  Its
    ``em`` is not judged here: EM is derived from the embargo register, and
    the report's P/X/A reaches the case only through the adoption gate
    (RSH-01-003).
    """
    if current.case_status is None or asserted.case_status is None:
        return None
    current_pxa = current.case_status.pxa.state
    asserted_pxa = asserted.case_status.pxa.state
    if is_pxa_assertion_acceptable(current_pxa, asserted_pxa):
        return None
    return DimensionRefusal(
        "pxa",
        f"{current_pxa.name} → {asserted_pxa.name} is not a forward move",
    )


def participant_status_refusals(
    current: ParticipantStatus,
    asserted: ParticipantStatus,
    roles: list[CVDRole] | None = None,
) -> list[DimensionRefusal]:
    """Return every refusal of *asserted* against the participant's *current*.

    An empty list means the status is accepted as sent (RSH-09-001).  Every
    failing rule is reported, not the first (EH-07-001), so the sender learns
    everything that is wrong with the update in one answer (RSH-09-002).

    The cross-machine entailments (RM↔VF, RM↔D per CSB-18-001, VF↔D per
    CSB-17-001) are evaluated on the status as received, with the evaluator
    the emit path uses (RSH-09-004): an update describing a state no sequence
    of events could produce is refused whole, whichever dimension moved.
    """
    refusals: list[DimensionRefusal] = []
    if (rm := _rm_refusal(current.rm.state, asserted.rm.state)) is not None:
        refusals.append(rm)
    refusals.extend(_path_refusals(current, asserted, roles))
    refusals.extend(
        DimensionRefusal(violation.dimension, violation.message)
        for violation in composite_state_violations(
            asserted.rm.state,
            None if asserted.vf is None else asserted.vf.state,
            None if asserted.d is None else asserted.d.state,
        )
    )
    if (pxa := _pxa_refusal(current, asserted)) is not None:
        refusals.append(pxa)
    return refusals


class CheckParticipantStatusAcceptableNode(DataLayerConditionWithPorts):
    """Accept or refuse a received ParticipantStatus as a whole (RSH-09-001).

    Read-only precondition guard (CLP-10-006): reads the participant and the
    asserted status and writes only ``BB_RM_ANOMALY`` to the blackboard, on
    every tick — ``None`` when there is no anomaly — so a previous
    execution's record never leaks into this one (BT-17-003).

    Returns:
        SUCCESS when there is nothing to judge against (no participant, no
        current status, no resolvable assertion), on an idempotent
        re-delivery, and when every rule accepts the status.

        FAILURE when any rule refuses it; ``feedback_message`` names every
        refused dimension and why, and becomes the refusal notice's reason
        (RSH-09-002, CLP-05-001).
    """

    def __init__(
        self,
        participant_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    OUTPUT_PORTS: dict[str, PortInformation] = {
        BB_RM_ANOMALY: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {BB_RM_ANOMALY: f"/{BB_RM_ANOMALY}"}

    def _resolve_asserted(self) -> ParticipantStatus | None:
        """Return the asserted status, DataLayer first, else ``None``."""
        assert self.datalayer is not None
        from_dl = (
            self.datalayer.read(self.status_id) if self.status_id else None
        )
        status = from_dl if from_dl is not None else self.status_obj_fallback
        return status if isinstance(status, ParticipantStatus) else None

    def update(self) -> Status:
        # Clear first, unconditionally, so no early return below inherits a
        # previous execution's anomaly (BT-17-003/004).
        self._set_output(BB_RM_ANOMALY, None)

        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        participant = self.datalayer.read(self.participant_id)
        if not isinstance(participant, CaseParticipant):
            # LoadParticipantNode reports the missing participant.
            return Status.SUCCESS

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if self.status_id and self.status_id in existing_ids:
            # Idempotent re-delivery: the append subtree short-circuits.
            return Status.SUCCESS

        current = participant.participant_status
        asserted = self._resolve_asserted()
        if not isinstance(current, ParticipantStatus) or asserted is None:
            return Status.SUCCESS

        anomaly = rm_anomaly(
            current.rm.state,
            asserted.rm.state,
            sender_actor_id=_as_id(participant.attributed_to)
            or self.participant_id,
            log=self.logger,
            node_name=self.name,
        )
        # Published whether or not the status is accepted: a refused
        # regression owes the sender the RSH-06-004 note too (CLP-10-022).
        self._set_output(BB_RM_ANOMALY, anomaly)

        refusals = participant_status_refusals(
            current, asserted, roles=list(participant.case_roles)
        )
        if not refusals:
            return Status.SUCCESS

        self.feedback_message = (
            f"ParticipantStatus '{self.status_id}' refused for participant"
            f" '{self.participant_id}': "
            + "; ".join(f"{r.dimension}: {r.reason}" for r in refusals)
        )
        self.logger.warning(
            "%s: %s (RSH-09-001)", self.name, self.feedback_message
        )
        return Status.FAILURE
