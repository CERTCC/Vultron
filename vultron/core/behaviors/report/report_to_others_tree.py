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
"""Report-to-others behavior tree composition (Production Collapse 3).

Implements ADR-0029 / BT-20-003: replaces the ``InjectParticipant``/
``InjectVendor``/``InjectCoordinator``/``InjectOther`` Actuator nodes with
calls to the ``suggest-actor-to-case`` trigger, while retaining the outer
loop structure (typed sub-loops, party-identification Retrievers,
effort-gate Evaluators).

Tree structure::

    ReportToOthersBT (Sequence, memory=False)
    ├── AllPartiesKnown            (Evaluator factory)
    ├── TotalEffortLimitMet        (Evaluator factory)
    ├── VendorSubLoop              (Selector, memory=False)
    │   ├── Inverter(MoreVendors)  — skip arm when queue empty
    │   └── Sequence(MoreVendors, WriteVendorRoles, SuggestVendorTrigger)
    ├── CoordinatorSubLoop         (Selector, memory=False)
    │   ├── Inverter(MoreCoordinators)
    │   └── Sequence(MoreCoordinators, WriteCoordinatorRoles, SuggestCoordinatorTrigger)
    └── OtherSubLoop               (Selector, memory=False)
        ├── Inverter(MoreOthers)
        └── Sequence(MoreOthers, WriteOtherRoles, SuggestOtherTrigger)

Each sub-loop follows the BTND-08-001 positive-precondition pattern: the
``More*`` guard appears in both the Sequence (execute arm) and the Inverter
(skip arm).  When the queue is empty, ``MoreX`` returns FAILURE →
``Inverter(MoreX)`` returns SUCCESS → arm is a graceful no-op.  When the
queue is non-empty, the Sequence executes ``WriteXRoles`` then the trigger.

``WriteXRolesNode`` is a ProtocolInternal node (BTND-03-004) that writes
``suggested_roles_{case_id_segment}`` to the blackboard so the downstream
``suggest-actor-to-case`` trigger carries the correct ``CVDRole`` when the
CaseActor processes the received Offer(Actor, Case).

The Evaluator call-out points from Phase 1 (``RecipientEffortExceeded``,
``PolicyCompatible``) are removed from the outer Sequence; effort-gating
and policy checks are handled per-recipient inside the sub-loops by the
production trigger rather than as outer-loop guards (BT-20-003 collapse
decision).  ``AllPartiesKnown`` and ``TotalEffortLimitMet`` remain as outer
guards per the simulator structure.

References
----------
- ADR-0029: ``docs/adr/0029-notification-loop-suggest-actor.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-20-003
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
  § "Production Collapse 3: Notification loop"
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import py_trees
from py_trees.common import Access, Status

from vultron.core.behaviors.call_out_point import CallOutBackendFactory
from vultron.enums.roles import CVDRole

if TYPE_CHECKING:
    from vultron.demo.fuzzer.bundles.report_to_others import (
        ReportToOthersCallOutBundle,
    )

logger = logging.getLogger(__name__)


class _WriteRolesNode(py_trees.behaviour.Behaviour):
    """ProtocolInternal: write ``suggested_roles_{case_id_segment}`` to the blackboard.

    Written before each sub-loop's ``suggest-actor-to-case`` trigger so the
    downstream CaseActor receive path carries the correct CVD role when
    forwarding ``Offer(CaseParticipant)`` to the Case Owner (AC-2, BTND-03-004).

    This node is constructed directly by the tree builder (not via a factory)
    because it is a ProtocolInternal handoff write — not a call-out point to
    an external system (ADR-0025).
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(
        self,
        roles: list[CVDRole],
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.roles = roles
        self.case_id = case_id
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard = self.attach_blackboard_client(name=self.name)
        id_segment = self.case_id.split("/")[-1]
        self.blackboard_key = f"suggested_roles_{id_segment}"
        self.blackboard.register_key(
            key=self.blackboard_key, access=Access.WRITE
        )

    def update(self) -> Status:
        setattr(self.blackboard, self.blackboard_key, list(self.roles))
        self.logger.debug(
            "%s: wrote suggested_roles %s for case '%s'",
            self.name,
            self.roles,
            self.case_id,
        )
        return Status.SUCCESS


# ---------------------------------------------------------------------------
def _make_role_sub_loop(
    loop_name: str,
    more_factory: CallOutBackendFactory,
    more_node_name: str,
    roles: list[CVDRole],
    suggest_factory: CallOutBackendFactory,
    suggest_node_name: str,
    case_id: str,
    write_roles_node_name: str,
) -> py_trees.behaviour.Behaviour:
    """Build one typed sub-loop arm (vendor, coordinator, or other).

    Shape (positive-precondition with Inverter skip, per BTND-08-001)::

        Selector(loop_name, memory=False)
        ├── Inverter(MoreX)   — SUCCESS no-op when queue empty
        └── Sequence(MoreX, WriteXRoles, SuggestXTrigger)  — execute path

    When the role queue is empty, ``MoreX`` returns FAILURE →
    ``Inverter(MoreX)`` returns SUCCESS → graceful no-op.
    When non-empty: Sequence executes ``WriteXRoles`` then the trigger.
    """
    more_guard_exec = more_factory(more_node_name)
    more_guard_skip = more_factory(f"{more_node_name}Skip")

    execute_seq = py_trees.composites.Sequence(
        name=f"Do{loop_name}",
        memory=False,
        children=[
            more_guard_exec,
            _WriteRolesNode(
                roles=roles,
                case_id=case_id,
                name=write_roles_node_name,
            ),
            suggest_factory(suggest_node_name),
        ],
    )
    skip_if_empty = py_trees.decorators.Inverter(
        name=f"Skip{loop_name}IfEmpty",
        child=more_guard_skip,
    )
    return py_trees.composites.Selector(
        name=loop_name,
        memory=False,
        children=[skip_if_empty, execute_seq],
    )


def create_report_to_others_tree(
    case_id: str,
    call_out: "ReportToOthersCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create the notification loop behavior tree (Production Collapse 3).

    Replaces the ``InjectParticipant`` family with ``suggest-actor-to-case``
    trigger calls per ADR-0029 / BT-20-003.  Three typed sub-loops iterate
    over identified vendors, coordinators, and other parties; each sub-loop
    writes the appropriate ``CVDRole`` to the blackboard before invoking its
    trigger factory (AC-2).

    Args:
        case_id: ID of the VulnerabilityCase being processed.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to :data:`~vultron.demo.fuzzer.bundles.report_to_others.REPORT_TO_OTHERS_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root Sequence node of the notification-loop behavior tree.
    """
    from vultron.demo.fuzzer.bundles.report_to_others import (
        REPORT_TO_OTHERS_DETERMINISTIC,
    )

    bundle = (
        call_out if call_out is not None else REPORT_TO_OTHERS_DETERMINISTIC
    )
    vendor_sub_loop = _make_role_sub_loop(
        loop_name="VendorSubLoop",
        more_factory=bundle.more_vendors_factory,
        more_node_name="MoreVendors",
        roles=[CVDRole.VENDOR],
        suggest_factory=bundle.suggest_vendor_factory,
        suggest_node_name="SuggestVendor",
        case_id=case_id,
        write_roles_node_name="WriteVendorRoles",
    )
    coordinator_sub_loop = _make_role_sub_loop(
        loop_name="CoordinatorSubLoop",
        more_factory=bundle.more_coordinators_factory,
        more_node_name="MoreCoordinators",
        roles=[CVDRole.COORDINATOR],
        suggest_factory=bundle.suggest_coordinator_factory,
        suggest_node_name="SuggestCoordinator",
        case_id=case_id,
        write_roles_node_name="WriteCoordinatorRoles",
    )
    other_sub_loop = _make_role_sub_loop(
        loop_name="OtherSubLoop",
        more_factory=bundle.more_others_factory,
        more_node_name="MoreOthers",
        roles=[CVDRole.OTHER],
        suggest_factory=bundle.suggest_other_factory,
        suggest_node_name="SuggestOther",
        case_id=case_id,
        write_roles_node_name="WriteOtherRoles",
    )
    root = py_trees.composites.Sequence(
        name="ReportToOthersBT",
        memory=False,
        children=[
            bundle.all_parties_known_factory("AllPartiesKnown"),
            bundle.total_effort_limit_factory("TotalEffortLimitMet"),
            vendor_sub_loop,
            coordinator_sub_loop,
            other_sub_loop,
        ],
    )
    logger.info(
        "Created ReportToOthersBT (Production Collapse 3) for case=%s", case_id
    )
    return root
