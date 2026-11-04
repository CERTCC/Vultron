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
``receive_activity_tree.py`` (CS-18-005).
"""

import py_trees

from vultron.core.behaviors.case.nodes.path_branch import PathBranch
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
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
from vultron.core.behaviors.speaks_for_executing_actor import (
    SpeaksForExecutingActor,
)
from vultron.errors import VultronWiringError

#: The declaration that gates a branch on the CASE_MANAGER, as a set.
_MANAGER_PATH_ONLY = frozenset({ReceivedPath.CASE_MANAGER})


def _runs_at_the_manager_alone(node: py_trees.behaviour.Behaviour) -> bool:
    """True when *node* is a path branch on the manager path alone."""
    return isinstance(node, PathBranch) and node.paths == _MANAGER_PATH_ONLY


def _skips_unless_the_subject(node: py_trees.behaviour.Behaviour) -> bool:
    """True when *node* is a Selector arm that skips all the later arms.

    The gate shape, read for BT-17-008's second arm: an ``Inverter`` round a
    :class:`SpeaksForExecutingActor` leaf succeeds at every *other* actor, so
    the Selector stops there and no later arm runs.  The ``Inverter`` is
    accepted bare or wrapped in a one-child ``Sequence``, which is how
    :func:`~vultron.core.behaviors.case.nodes.role_gates.create_case_manager_gated_tree`
    spells its own skip arm.
    """
    if (
        isinstance(node, py_trees.composites.Sequence)
        and len(node.children) == 1
    ):
        node = node.children[0]
    return isinstance(node, py_trees.decorators.Inverter) and isinstance(
        node.decorated, SpeaksForExecutingActor
    )


def _subject_guard_cut(
    parent: py_trees.behaviour.Behaviour | None,
    children: list[py_trees.behaviour.Behaviour],
) -> int:
    """How many of *children* BT-17-008's second arm does not already bound.

    ``len(children)`` when none of them is that arm, so the walk is
    unchanged wherever no leaf claims to be it.  *parent* is the composite
    whose children these are, or ``None`` for the effect list a tree passed,
    which the factory runs in order like a ``Sequence``.
    """
    if parent is None or isinstance(parent, py_trees.composites.Sequence):
        for index, child in enumerate(children):
            if isinstance(child, SpeaksForExecutingActor):
                return index
    if isinstance(parent, py_trees.composites.Selector) and (
        children and _skips_unless_the_subject(children[0])
    ):
        return 1
    return len(children)


def _walk(
    parent: py_trees.behaviour.Behaviour | None,
    nodes: list[py_trees.behaviour.Behaviour],
    marker: type,
    *,
    second_arm_bounds: bool,
) -> list[py_trees.behaviour.Behaviour]:
    """The recursion both walks share; see :func:`ungated_nodes`."""
    if second_arm_bounds:
        nodes = nodes[: _subject_guard_cut(parent, nodes)]
    found: list[py_trees.behaviour.Behaviour] = []
    for node in nodes:
        if isinstance(node, CaseManagerGate) or _runs_at_the_manager_alone(
            node
        ):
            continue
        if isinstance(node, marker):
            found.append(node)
        found.extend(
            _walk(
                node,
                list(node.children),
                marker,
                second_arm_bounds=second_arm_bounds,
            )
        )
    return found


def ungated_nodes(
    roots: list[py_trees.behaviour.Behaviour],
    marker: type,
) -> list[py_trees.behaviour.Behaviour]:
    """Every *marker* instance in *roots* outside a CASE_MANAGER gate.

    The walk does not descend into a :class:`CaseManagerGate`: whatever runs
    there runs only at the CASE_MANAGER (BT-17-001).  Nor into a
    :class:`~vultron.core.behaviors.case.nodes.path_branch.PathBranch` that
    names the manager path alone, which is the same statement made as a
    declared branch (HP-01-038).  Any other composite is walked, the
    participant-replica gate and a branch off the manager path among them: a
    branch that runs at a replica holds ungated nodes, so an emit inside it
    needs its exemption (BT-17-008).

    Whom the node speaks for is not read here.  The state-write ratchet
    (RSH-08-003) walks with this function, and RSH-08-003 asks a different
    question of a write than BT-17-008 asks of an emit: a received-side
    write belongs to the CASE_MANAGER whoever the write is *about*
    (``notes/bt-pitfalls.md``).  Only :func:`ungated_emitters` reads the
    second arm.
    """
    return _walk(None, list(roots), marker, second_arm_bounds=False)


def ungated_emitters(
    roots: list[py_trees.behaviour.Behaviour],
) -> list[py_trees.behaviour.Behaviour]:
    """Every :class:`EmitCapable` node in *roots* that BT-17-008 leaves bare.

    :func:`ungated_nodes`' walk, plus BT-17-008's second arm: an emit behind
    a :class:`SpeaksForExecutingActor` leaf is already guarded, so it is not
    reported and needs no exemption.  The two placements that bound it are in
    :mod:`vultron.core.behaviors.speaks_for_executing_actor`.
    """
    return _walk(None, list(roots), EmitCapable, second_arm_bounds=True)


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
