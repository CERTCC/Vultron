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

"""The effect stages of a received tree, and the checks on them (BT-17-008).

``replica_effects`` run on every replica, ungated; ``manager_effects`` run
inside the CASE_MANAGER gate the factory builds here.  Split out of
``receive_activity_tree.py`` (CS-18-001).
"""

import py_trees

from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.exemption_registry import require_registered
from vultron.core.behaviors.replica_emit_exemptions import (
    REPLICA_EMIT_EXEMPTIONS,
    ReplicaEmitExemption,
)
from vultron.errors import VultronWiringError


def ungated_nodes(
    roots: list[py_trees.behaviour.Behaviour],
    marker: type,
) -> list[py_trees.behaviour.Behaviour]:
    """Every *marker* instance in *roots* outside a CASE_MANAGER gate.

    The walk does not descend into a :class:`CaseManagerGate`: whatever runs
    there runs only at the CASE_MANAGER (BT-17-001).  Any other composite,
    including the participant-replica gate, is walked.
    """
    found: list[py_trees.behaviour.Behaviour] = []
    for root in roots:
        if isinstance(root, CaseManagerGate):
            continue
        if isinstance(root, marker):
            found.append(root)
        found.extend(ungated_nodes(list(root.children), marker))
    return found


def ungated_emitters(
    roots: list[py_trees.behaviour.Behaviour],
) -> list[py_trees.behaviour.Behaviour]:
    """Every :class:`EmitCapable` node in *roots* outside a CASE_MANAGER gate.

    See :func:`ungated_nodes`; the state-write ratchet walks the same way for
    :class:`~vultron.core.behaviors.state_write_capable.StateWriteCapable`
    (RSH-08-003).
    """
    return ungated_nodes(roots, EmitCapable)


def check_gate_arguments(
    name: str,
    *,
    gate_arguments_without_effects: bool,
) -> None:
    """Refuse gate arguments that would be silently ignored.

    Raises:
        VultronWiringError: a gate argument is passed without
            ``manager_effects`` (BT-17-008).
    """
    where = f"create_receive_activity_tree({name})"
    if gate_arguments_without_effects:
        raise VultronWiringError(
            f"{where}: manager_case_id, manager_gate_name,"
            " manager_body_name and manager_case_may_be_absent configure"
            " the gate around manager_effects; pass them only with"
            " manager_effects"
            " (BT-17-008)"
        )


def check_replica_effects(
    name: str,
    replica_effects: list[py_trees.behaviour.Behaviour],
    exemption: ReplicaEmitExemption | None,
) -> None:
    """Refuse an ungated emit the tree's named exemption does not cover.

    Raises:
        VultronWiringError: *exemption* is not registered, covers none of the
            ungated emitters (a stale exemption), or an ungated emitter in
            *replica_effects* is not covered (BT-17-008).
    """
    where = f"create_receive_activity_tree({name})"
    emitted = {type(n).__name__ for n in ungated_emitters(replica_effects)}
    covered: frozenset[str] = frozenset()
    if exemption is not None:
        require_registered(
            exemption,
            REPLICA_EMIT_EXEMPTIONS,
            where=where,
            kind="replica emit",
            registry_name="REPLICA_EMIT_EXEMPTIONS",
            spec_id="BT-17-008",
        )
        if not emitted & exemption.covers:
            raise VultronWiringError(
                f"{where}: replica emit exemption {exemption.name!r} covers"
                " none of the tree's ungated emitters; drop it (BT-17-008)"
            )
        covered = exemption.covers
    if uncovered := sorted(emitted - covered):
        raise VultronWiringError(
            f"{where}: emit-capable node(s) {uncovered} in replica_effects"
            " would run on every replica; pass them as manager_effects so"
            " the factory gates them on the CASE_MANAGER, or name a"
            " ReplicaEmitExemption that covers them (BT-17-008)"
        )


def manager_stage(
    name: str,
    manager_effects: list[py_trees.behaviour.Behaviour],
    manager_case_id: str | None,
    manager_gate_name: str | None,
    manager_body_name: str | None,
    manager_case_may_be_absent: bool,
) -> CaseManagerGate:
    """Wrap *manager_effects* in the CASE_MANAGER gate.

    Raises:
        VultronWiringError: *manager_case_id* is ``None`` — there is no case
            whose CASE_MANAGER could gate the effects.
    """
    if manager_case_id is None:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): manager_effects need"
            " manager_case_id, the case whose CASE_MANAGER gates them"
            " (BT-17-008)"
        )
    return create_case_manager_gated_tree(
        name=manager_gate_name or f"{name}IfCaseManager",
        case_id=manager_case_id,
        children=manager_effects,
        body_name=manager_body_name,
        case_may_be_absent=manager_case_may_be_absent,
    )


def node_types(
    roots: list[py_trees.behaviour.Behaviour],
    marker: type | tuple[type, ...],
) -> list[str]:
    """Sorted class names of every *marker* node in *roots*, gated or not."""
    return sorted(
        {
            type(n).__name__
            for root in roots
            for n in root.iterate()
            if isinstance(n, marker)
        }
    )
