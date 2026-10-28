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

"""Precondition guards, diversions and the refusal stage (CLP-10-022/026).

Split out of ``receive_activity_tree.py`` (CS-18-001).
"""

from collections.abc import Sequence

import py_trees

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.nodes.diversion_stage import (
    Diversion,
    DiversionGate,
    DiversionStage,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
    RefusalEffectsBestEffort,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.case.receive_stages.effects import (
    check_replica_effects,
    node_types,
)
from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.note.case_manager_note import (
    _CommitCaseManagerNoteBase,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes.chain import CreateLogEntryNode
from vultron.errors import VultronWiringError


def refusal_stage(
    name: str,
    intake: IntakeReceivedActivityNode,
    precondition_guards: list[py_trees.behaviour.Behaviour],
    refusal_effects: list[py_trees.behaviour.Behaviour],
    case_id: str | None,
    *,
    stage_name: str = "PreconditionGuardStage",
    guards_name: str = "PreconditionGuards",
    gate_suffix: str = "RefusalIfCaseManager",
    argument: str = "refusal_effects",
) -> PreconditionGuardStage:
    """Wrap the guards so *refusal_effects* run only when they refuse.

    Builds both refusal stages: the precondition-guard stage
    (``refusal_effects``) and the post-close stage (``post_close_reply``),
    which differ only in their names and the guards they wrap.

    The refusal effects sit inside the CASE_MANAGER gate on *case_id*, the
    case the guards judged: the CASE_MANAGER adjudicates, so only it answers a
    refusal (BT-17-008).  The gate reads a case this store does not hold as
    "not the CASE_MANAGER" at ``debug`` level, because the guard that refused
    an unknown case has already reported it.  Each effect is best-effort on
    its own, so one that fails (a refusal notice that cannot be built) does
    not keep the next (the RSH-06-004 note) from running.

    Raises:
        VultronWiringError: a refusal effect is not emit-capable, or
            contains a state writer.  A refusal commits nothing for the
            refused assertion, so a refusal effect may only speak to the
            sender; a state write here would change state the ledger never
            records (CLP-10-022).  The one writer admitted is the
            CASE_MANAGER's own note (RSH-06-004), which commits its own
            ``add_note_to_case`` entry before it attaches the note.
    """
    not_emitters = [
        type(n).__name__
        for n in refusal_effects
        if not isinstance(n, EmitCapable)
    ]
    writers = sorted(
        {
            type(n).__name__
            for root in refusal_effects
            for n in root.iterate()
            if isinstance(n, StateWriteCapable)
            and not isinstance(n, _CommitCaseManagerNoteBase)
        }
    )
    if not_emitters or writers:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): {argument} must"
            f" emit and write no case state; not emit-capable:"
            f" {not_emitters}, state writers: {writers} (CLP-10-022)"
        )
    gate = create_case_manager_gated_tree(
        name=f"{name}{gate_suffix}",
        case_id=case_id,
        children=[
            RefusalEffectsBestEffort(
                name=f"{effect.name}BestEffort", child=effect
            )
            for effect in refusal_effects
        ],
        case_may_be_absent=True,
    )
    return PreconditionGuardStage(
        name=stage_name,
        guards=py_trees.composites.Sequence(
            name=guards_name,
            memory=False,
            children=precondition_guards,
        ),
        refusal=RefusalEffectsBestEffort(name="RefusalEffects", child=gate),
        intake=intake,
    )


def case_manager_commit_types() -> tuple[type, ...]:
    """The node classes that commit a CASE_MANAGER-authored entry.

    ``CreateLogEntryNode`` commits an entry it mints in-tree, and
    ``_CommitCaseManagerActivityBase`` one activity it builds and commits;
    neither belongs in a ``RECEIVER`` diversion (CLP-10-026).
    """
    return (CreateLogEntryNode, _CommitCaseManagerActivityBase)


def diversion_stage(
    name: str, diversion: Diversion, case_id: str | None
) -> DiversionStage:
    """Build the stage for one :class:`Diversion` (CLP-10-026).

    A ``CASE_MANAGER`` diversion checks the role before its condition and
    runs its effects inside the CASE_MANAGER gate on *case_id* (BT-17-001).
    A ``RECEIVER`` diversion is the receiver's own answer: its emits must be
    covered by its registered exemption and it may write no case state
    (BT-17-008, RSH-08-003).

    Raises:
        VultronWiringError: the condition emits, writes state or commits; an
            effect holds the received activity's commit, which a diverted
            delivery never makes; a ``CASE_MANAGER`` diversion names no
            case; or a ``RECEIVER`` diversion writes case state or has an
            uncovered emit or commits an entry.
    """
    where = f"create_receive_activity_tree({name}): diversion {diversion.name}"
    condition = [diversion.condition]
    if offenders := node_types(
        condition, (EmitCapable, StateWriteCapable, CommitCaseLedgerEntryNode)
    ):
        raise VultronWiringError(
            f"{where}: its condition must be read-only; found {offenders}"
            " (CLP-10-026)"
        )
    effects = list(diversion.effects)
    if commits := node_types(effects, CommitCaseLedgerEntryNode):
        raise VultronWiringError(
            f"{where}: a diverted delivery is never committed as received;"
            f" found {commits} (CLP-10-026)"
        )
    if diversion.gate is DiversionGate.RECEIVER:
        if writers := node_types(effects, StateWriteCapable):
            raise VultronWiringError(
                f"{where}: a receiver's own answer writes no case state;"
                f" found {writers} (RSH-08-003, CLP-10-026)"
            )
        if commits := node_types(effects, case_manager_commit_types()):
            raise VultronWiringError(
                f"{where}: a diversion that commits runs only at the"
                f" CASE_MANAGER; found {commits} (CLP-10-026, BT-17-001)"
            )
        check_replica_effects(name, effects, diversion.emit_exemption)
        body: py_trees.behaviour.Behaviour = py_trees.composites.Sequence(
            name=f"{diversion.name}Answer", memory=False, children=effects
        )
        return DiversionStage(diversion.name, diversion.condition, body)
    if case_id is None:
        raise VultronWiringError(
            f"{where}: a CASE_MANAGER diversion needs the tree's case_id or"
            " manager_case_id (BT-17-001)"
        )
    if diversion.emit_exemption is not None:
        raise VultronWiringError(
            f"{where}: a CASE_MANAGER diversion's emits are gated; drop its"
            " emit exemption (BT-17-008)"
        )
    gated_condition = py_trees.composites.Sequence(
        name=f"{diversion.name}IfCaseManager",
        memory=False,
        children=[
            CheckIsCaseManagerNode(case_id=case_id, case_may_be_absent=True),
            diversion.condition,
        ],
    )
    return DiversionStage(
        diversion.name,
        gated_condition,
        create_case_manager_gated_tree(
            name=f"{diversion.name}Answer",
            case_id=case_id,
            children=effects,
        ),
    )


def precondition_guard_nodes(
    name: str,
    guards: Sequence[py_trees.behaviour.Behaviour | Diversion],
    case_id: str | None,
) -> list[py_trees.behaviour.Behaviour]:
    """The tree's precondition guards, each :class:`Diversion` built in place.

    A diverted delivery is answered by its diversion, so the refusal stage
    that wraps these guards runs no refusal effect for it (CLP-10-026).
    """
    return [
        diversion_stage(name, guard, case_id)
        if isinstance(guard, Diversion)
        else guard
        for guard in guards
    ]
