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
"""CVE ID assignment behavior tree composition.

Implements :func:`create_assign_cve_id_tree`, which composes the full 21-node
CVE ID assignment workflow grounded in CNA Operational Rules v4.1.0.
(5 composites + 14 factory call-out leaves + 2 ProtocolInternal leaves.)

Tree structure::

    AssignVulID (Fallback / Selector)
    ├── IdAssigned                       — Retriever early-exit guard
    └── _AssignIdIfInScope (Sequence)
        ├── InScope                      — Evaluator
        └── _AssignOrRequestId (Fallback)
            ├── _AssignIdIfPossible (Sequence)
            │   ├── IsIDAssignmentAuthority   — ProtocolInternal
            │   ├── ProductInCNAScope         — Evaluator
            │   ├── IsMostAppropriateCNA      — Evaluator
            │   ├── IdAssignable (Sequence)   — 9 children, cheapest-first
            │   │   ├── IsNotMaliciousCode         — Evaluator
            │   │   ├── IsNotDependencyUpdate       — Evaluator
            │   │   ├── IsNotEOLStatusAlone         — Evaluator
            │   │   ├── IsNotDeliberatelyEducational — Evaluator
            │   │   ├── IsOrWillBePubliclyDisclosed  — ProtocolInternal
            │   │   ├── IsPubliclyAvailableProduct   — Evaluator
            │   │   ├── NoDuplicateCVE              — Evaluator
            │   │   ├── MeetsEvidenceBar            — Evaluator
            │   │   └── IsRealVulnerability         — Evaluator
            │   └── AssignId                  — Composer
            └── RequestId                    — Retriever

Call-out injection seams (ADR-0025 / BT-18-004)
------------------------------------------------
All call-out points are injected via :class:`AssignCveIdCallOutBundle`.
Two ProtocolInternal nodes (``IsIDAssignmentAuthority``,
``IsOrWillBePubliclyDisclosed``) are constructed inline — they read
deployment-time configuration or blackboard CS.P state with no external-system
call, so they have no factory seam.

References
----------
- Issue: #1817 / Source Idea: #1246
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
- Notes: ``notes/bt-fuzzer-rm-id-assignment.md``
"""

import logging
from typing import TYPE_CHECKING, Any

import py_trees
from py_trees.common import Access, Status

from vultron.enums.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.assign_cve_id import (
        AssignCveIdCallOutBundle,
    )

logger = logging.getLogger(__name__)

#: Blackboard key under which the participant's CVDRole list is stored.
#: Written by the setup phase of the CaseActor bootstrap and read by the
#: ``IsIDAssignmentAuthority`` ProtocolInternal node.
_ACTOR_ROLES_KEY = "actor_roles"

#: Blackboard key for the publication-intent flag (set by prior BT runs).
_PUBLICATION_INTENT_SET_KEY = "publication_intent_set"


class _IsIDAssignmentAuthorityNode(py_trees.behaviour.Behaviour):
    """ProtocolInternal: check whether this actor holds CNA role.

    Reads ``actor_roles`` from the blackboard (written by the BT setup phase)
    and returns SUCCESS when :attr:`CVDRole.CVE_NUMBERING_AUTHORITY` is
    present.  No external call; no factory seam (ProtocolInternal per
    ``notes/bt-fuzzer-rm-id-assignment.md``).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(key=_ACTOR_ROLES_KEY, access=Access.READ)

    def update(self) -> Status:
        if not self.blackboard.exists(_ACTOR_ROLES_KEY):
            self.logger.debug(
                "%s: %s not on blackboard — treating as non-CNA",
                self.name,
                _ACTOR_ROLES_KEY,
            )
            return Status.FAILURE

        roles = self.blackboard.get(_ACTOR_ROLES_KEY)
        if not isinstance(roles, list):
            self.logger.warning(
                "%s: %s is %s, not list — treating as non-CNA",
                self.name,
                _ACTOR_ROLES_KEY,
                type(roles).__name__,
            )
            return Status.FAILURE

        if CVDRole.CVE_NUMBERING_AUTHORITY in roles:
            self.logger.debug(
                "%s: actor holds CNA role — proceed to authority check",
                self.name,
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: actor lacks CNA role — skip direct-assignment path",
            self.name,
        )
        return Status.FAILURE


class _IsOrWillBePubliclyDisclosedNode(py_trees.behaviour.Behaviour):
    """ProtocolInternal: OR-gate for public disclosure status.

    Returns SUCCESS when ``publication_intent_set`` is truthy on the
    blackboard (vulnerability has a publication intent recorded by a prior
    BT run).  No external call; no factory seam (ProtocolInternal).

    Per ``notes/bt-fuzzer-rm-id-assignment.md`` § "IsOrWillBePubliclyDisclosed":
    the blackboard key is written by the publication-intent BT step before the
    CVE ID assignment step runs in the same tick sequence.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key=_PUBLICATION_INTENT_SET_KEY, access=Access.READ
        )

    def update(self) -> Status:
        if not self.blackboard.exists(_PUBLICATION_INTENT_SET_KEY):
            self.logger.debug(
                "%s: no publication intent on blackboard — FAILURE",
                self.name,
            )
            return Status.FAILURE

        intent_set = self.blackboard.get(_PUBLICATION_INTENT_SET_KEY)
        if intent_set:
            self.logger.debug(
                "%s: publication intent is set — SUCCESS", self.name
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: publication intent not set — FAILURE", self.name
        )
        return Status.FAILURE


def create_assign_cve_id_tree(
    case_id: str,
    call_out: "AssignCveIdCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the CVE ID assignment workflow.

    Composes the full 21-node tree grounded in CNA Operational Rules v4.1.0.
    (5 composites + 14 factory call-out leaves + 2 ProtocolInternal leaves.)
    All 14 Evaluator/Retriever/Composer call-out points are injected via
    :class:`~vultron.core.behaviors.call_out.bundles.assign_cve_id.AssignCveIdCallOutBundle`.
    The two ProtocolInternal nodes (``IsIDAssignmentAuthority``,
    ``IsOrWillBePubliclyDisclosed``) are constructed inline.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.assign_cve_id.ASSIGN_CVE_ID_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the ``AssignVulID`` Fallback behavior tree.
    """
    from vultron.core.behaviors.call_out.bundles.assign_cve_id import (
        ASSIGN_CVE_ID_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else ASSIGN_CVE_ID_DETERMINISTIC

    # -- IdAssignable subtree (9 children, cheapest-first) -------------------
    id_assignable_seq = py_trees.composites.Sequence(
        name="IdAssignable",
        memory=False,
        children=[
            bundle.is_not_malicious_code_factory("IsNotMaliciousCode"),
            bundle.is_not_dependency_update_factory("IsNotDependencyUpdate"),
            bundle.is_not_eol_status_alone_factory("IsNotEOLStatusAlone"),
            bundle.is_not_deliberately_educational_factory(
                "IsNotDeliberatelyEducational"
            ),
            _IsOrWillBePubliclyDisclosedNode("IsOrWillBePubliclyDisclosed"),
            bundle.is_publicly_available_product_factory(
                "IsPubliclyAvailableProduct"
            ),
            bundle.no_duplicate_cve_factory("NoDuplicateCVE"),
            bundle.meets_evidence_bar_factory("MeetsEvidenceBar"),
            bundle.is_real_vulnerability_factory("IsRealVulnerability"),
        ],
    )

    # -- _AssignIdIfPossible (CNA direct-assignment path) --------------------
    assign_if_possible_seq = py_trees.composites.Sequence(
        name="_AssignIdIfPossible",
        memory=False,
        children=[
            _IsIDAssignmentAuthorityNode("IsIDAssignmentAuthority"),
            bundle.product_in_cna_scope_factory("ProductInCNAScope"),
            bundle.is_most_appropriate_cna_factory("IsMostAppropriateCNA"),
            id_assignable_seq,
            bundle.assign_id_factory("AssignId"),
        ],
    )

    # -- _AssignOrRequestId (Fallback: try direct, else request) -------------
    assign_or_request_fallback = py_trees.composites.Selector(
        name="_AssignOrRequestId",
        memory=False,
        children=[
            assign_if_possible_seq,
            bundle.request_id_factory("RequestId"),
        ],
    )

    # -- _AssignIdIfInScope (Sequence: scope gate + assign-or-request) -------
    assign_if_in_scope_seq = py_trees.composites.Sequence(
        name="_AssignIdIfInScope",
        memory=False,
        children=[
            bundle.in_scope_factory("InScope"),
            assign_or_request_fallback,
        ],
    )

    # -- AssignVulID root (Fallback: early-exit if already assigned) ---------
    root = py_trees.composites.Selector(
        name="AssignVulID",
        memory=False,
        children=[
            bundle.id_assigned_factory("IdAssigned"),
            assign_if_in_scope_seq,
        ],
    )

    logger.info("Created AssignVulID BT for case=%s", case_id)
    return root
