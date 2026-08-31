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

"""Per-dimension EM/PXA filter guard nodes for AddCaseStatusToCase.

Three composable precondition guards (RSH-05, ADR-0061, ISSUE-2256):

1. ``FilterCsEmDimensionNode``  — adjudicates EM; initialises the tick
   accumulator; clears all per-tick BB keys (BT-17-003).
2. ``FilterCsPxaDimensionNode`` — adjudicates PXA; reads+updates the
   accumulator written by the EM node.
3. ``FinalizeCsFilterNode``     — combines results, checks whole-refusal,
   and publishes ``BB_CASE_STATUS_DIM_FILTER`` /
   ``BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE``.

Each dimension guard always returns SUCCESS; only ``FinalizeCsFilterNode``
can return FAILURE (whole-refusal — nothing new accepted).
"""

import logging
from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.lifecycle import (
    BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
)
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.cs import is_monotonic_pxa_forward
from vultron.core.states.em import is_valid_em_transition

logger = logging.getLogger(__name__)

#: Blackboard key carrying the per-dimension filter outcome for
#: :class:`AppendCaseStatusToCaseNode` downstream.  ``None`` when nothing
#: was filtered.
BB_CASE_STATUS_DIM_FILTER = "append_case_status_dim_filter"

#: Internal accumulator key shared between the three filter guard nodes
#: within a single tick.  Not for external consumption.
_BB_CS_FILTER_ACC = "cs_dim_filter_accumulator"


class FilterCsEmDimensionNode(DataLayerConditionWithPorts):
    """Adjudicates the EM dimension of a received CaseStatus (RSH-05, ISSUE-2256).

    Read-only precondition guard (CLP-10-006).  Initialises the per-tick
    accumulator and evaluates whether the asserted EM transition is acceptable.
    Refused EM is carried forward (current value); accepted EM passes through.

    Also clears ``BB_CASE_STATUS_DIM_FILTER`` and
    ``BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE`` unconditionally at tick start so
    that no prior execution's values leak into this tick (BT-17-003).

    Always returns SUCCESS — individual dimension refusal is not a tree failure;
    ``FinalizeCsFilterNode`` decides whole-refusal.

    Must run before ``FilterCsPxaDimensionNode`` and ``FinalizeCsFilterNode``
    in the precondition_guards sequence.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            _BB_CS_FILTER_ACC: PortInformation(
                data_type=object, required=False
            ),
            BB_CASE_STATUS_DIM_FILTER: PortInformation(
                data_type=object, required=False
            ),
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE: PortInformation(
                data_type=object, required=False
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            _BB_CS_FILTER_ACC: f"/{_BB_CS_FILTER_ACC}",
            BB_CASE_STATUS_DIM_FILTER: f"/{BB_CASE_STATUS_DIM_FILTER}",
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE: f"/{BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE}",
        }

    def _clear(self) -> None:
        self._set_output(_BB_CS_FILTER_ACC, None)
        self._set_output(BB_CASE_STATUS_DIM_FILTER, None)
        self._set_output(BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE, None)

    def _resolve_asserted(self) -> CaseStatus | None:
        assert self.datalayer is not None
        obj = self.datalayer.read(self.status_id)
        if isinstance(obj, CaseStatus):
            return obj
        obj = self.status_obj_fallback
        return obj if isinstance(obj, CaseStatus) else None

    def update(self) -> Status:
        self._clear()  # BT-17-003

        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS

        try:
            current = case.current_status
        except ValueError:
            return (
                Status.SUCCESS
            )  # first CaseStatus ever — no filtering needed

        asserted = self._resolve_asserted()
        if asserted is None:
            return Status.SUCCESS

        acc: dict[str, Any] = {
            "status_id": self.status_id,
            "refused": [],
            "update_fields": {},
            "current": current,
            "asserted": asserted,
        }

        current_em = current.em.state
        asserted_em = asserted.em.state
        if asserted_em != current_em and not is_valid_em_transition(
            current_em, asserted_em
        ):
            acc["refused"].append("em")
            acc["update_fields"]["em"] = EmDimension(state=current_em)
            self.logger.warning(
                "%s: refused EM %s → %s for case '%s'; carrying forward",
                self.name,
                current_em,
                asserted_em,
                self.case_id,
            )

        self._set_output(_BB_CS_FILTER_ACC, acc)
        return Status.SUCCESS


class FilterCsPxaDimensionNode(DataLayerConditionWithPorts):
    """Adjudicates the PXA dimension of a received CaseStatus (RSH-05, ISSUE-2256).

    Read-only precondition guard (CLP-10-006).  Reads the per-tick accumulator
    written by :class:`FilterCsEmDimensionNode`, evaluates whether the asserted
    PXA state is a monotone forward move, and updates the accumulator.

    Always returns SUCCESS.  Must run after ``FilterCsEmDimensionNode`` and
    before ``FinalizeCsFilterNode`` in the precondition_guards sequence.
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        return {
            **super().input_ports(),
            _BB_CS_FILTER_ACC: PortInformation(
                data_type=object, required=False
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            _BB_CS_FILTER_ACC: f"/{_BB_CS_FILTER_ACC}",
        }

    def update(self) -> Status:
        # The accumulator is a mutable dict stored by reference on the
        # blackboard.  Mutating it in-place propagates to FinalizeCsFilterNode
        # without requiring a separate output port (which py_trees forbids from
        # overlapping with input ports).
        acc = self._try_get_input(_BB_CS_FILTER_ACC)
        if not isinstance(acc, dict):
            return Status.SUCCESS

        current: CaseStatus = acc["current"]
        asserted: CaseStatus = acc["asserted"]

        current_pxa = current.pxa.state
        asserted_pxa = asserted.pxa.state
        # Received-side: intentionally uses the weaker monotone check (RSH-05).
        # A remote peer may have skipped steps between messages; strict
        # single-step adjacency (is_valid_pxa_transition) applies only to
        # local write nodes (CSB-16-002).
        if asserted_pxa != current_pxa and not is_monotonic_pxa_forward(
            current_pxa, asserted_pxa
        ):
            acc["refused"].append("pxa")
            acc["update_fields"]["pxa"] = PxaDimension(state=current_pxa)
            self.logger.warning(
                "%s: refused PXA %s → %s for case '%s'; carrying forward",
                self.name,
                current_pxa,
                asserted_pxa,
                acc.get("status_id", "?"),
            )

        return Status.SUCCESS


class FinalizeCsFilterNode(DataLayerConditionWithPorts):
    """Combines EM and PXA filter results and publishes the final filter outcome.

    Reads the per-tick accumulator written by :class:`FilterCsEmDimensionNode`
    and updated by :class:`FilterCsPxaDimensionNode`.  If at least one
    dimension was refused, it builds the filtered :class:`CaseStatus` and
    publishes ``BB_CASE_STATUS_DIM_FILTER`` for :class:`AppendCaseStatusToCaseNode`
    and ``BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE`` for the canonical ledger commit.

    Returns:
        SUCCESS when no dimensions were refused, or when at least one dimension
        was accepted and the filtered status carries new state.

        FAILURE when every dimension was refused *and* the filtered status is
        indistinguishable from the current state — the assertion carried no
        acceptable information (RSH-05-005).
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        return {
            **super().input_ports(),
            _BB_CS_FILTER_ACC: PortInformation(
                data_type=object, required=False
            ),
        }

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            BB_CASE_STATUS_DIM_FILTER: PortInformation(
                data_type=object, required=False
            ),
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE: PortInformation(
                data_type=object, required=False
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            _BB_CS_FILTER_ACC: f"/{_BB_CS_FILTER_ACC}",
            BB_CASE_STATUS_DIM_FILTER: f"/{BB_CASE_STATUS_DIM_FILTER}",
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE: f"/{BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE}",
        }

    def update(self) -> Status:
        acc = self._try_get_input(_BB_CS_FILTER_ACC)
        if not isinstance(acc, dict):
            return Status.SUCCESS  # no filtering in progress

        refused: list[str] = acc["refused"]
        if not refused:
            return (
                Status.SUCCESS
            )  # all dimensions accepted — no override needed

        current: CaseStatus = acc["current"]
        asserted: CaseStatus = acc["asserted"]
        status_id: str = acc["status_id"]
        update_fields: dict[str, Any] = acc["update_fields"]

        filtered = asserted.model_copy(update=update_fields)

        # RSH-05-005: if the filtered state is indistinguishable from current,
        # the assertion carried no new information — refuse in full.
        if (filtered.em.state, filtered.pxa.state) == (
            current.em.state,
            current.pxa.state,
        ):
            self.feedback_message = (
                f"Status '{status_id}' refused in full:"
                f" refused dimension(s) {', '.join(refused)}"
                " and no other dimension carries new state"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self._set_output(
            BB_CASE_STATUS_DIM_FILTER,
            {
                "status_id": status_id,
                "refused": refused,
                "filtered_status": filtered,
            },
        )
        self._set_output(
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
            {
                "object_id": status_id,
                "producer_type": self.__class__.__name__,
                "fields": {
                    "emState": filtered.em.state.name,
                    "pxaState": filtered.pxa.state.name,
                },
            },
        )
        self.logger.warning(
            "%s: partial accept for status '%s':" " refused %s, accepted %s",
            self.name,
            status_id,
            refused,
            [d for d in ("em", "pxa") if d not in refused],
        )
        return Status.SUCCESS
