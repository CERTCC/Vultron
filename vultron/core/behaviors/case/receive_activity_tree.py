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

"""Receive-side tree composition: the staged shared factory (ADR-0111, ADR-0135).

:func:`create_receive_activity_tree` is the one way to build a received-side
BT.
It fixes the stage order intake → door guards (post-close guard, addressee
check, closed-sender check, sender guard) → clock decisions → precondition
guards → guarded commit → protocol effects (CLP-10-006, CLP-10-010,
CLP-10-025, ADR-0115, CM-23-013, HP-01-005) and
supplies the shared intake node, the post-close write-boundary guard and the
addressee door guard itself (CLP-10-017, ADR-0131, HP-01-005), so no handler
opts out of recording what arrived, forgets the closed-case boundary or acts
on a copy that was not addressed to it.  A tree leaves a door guard out only
by naming a registered exemption (``post_close_exemption``,
``addressee_exemption``) that records why.
A tree whose CASE_MANAGER must record a decision from its own clock before
it judges the activity (an expiry) passes ``clock_decisions``: the factory
runs them at the CASE_MANAGER only, after the door guards, and a refused
commit there never ends the tree (CLP-10-025).  Every tree with a case and a
sender guard also takes the case-wide clock decisions (the embargo end-time
check, EMB-13-003) ahead of its own, with no argument.
A tree some of whose deliveries are answered by an act of the receiver's own
instead of a commit passes a ``Diversion`` among its precondition guards: the
factory builds its stage there, so the choice of arm is tree structure, never
the use case's (CLP-10-026, ADR-0135).
Every tree that commits to a case and has precondition guards answers their
refusal with the refusal notice, which the factory adds itself (CLP-02-005,
CLP-05-001); a tree goes without it only by naming a registered
``refusal_notice_exemption``.  A tree that owes the sender more feedback
passes ``refusal_effects``.  The factory runs both only on that refusal, at
the CASE_MANAGER, once per received activity, and the tree still fails
before the commit (CLP-10-022).

When ``sender_rule`` is provided, the factory composes the sender guard from
it and places it after the post-close guard and the addressee check and
before the caller's ``precondition_guards``; a
tree whose case is resolved at run time names the read-only steps that
resolve it (``case_resolution``), which run just before the guard.
A failed sender guard ends the tree with ``REFUSED`` and nothing is written
or sent (HP-01-006, HP-01-008, ADR-0115).  A tree cannot pass a guard of its
own: the factory is the only place a sender guard is composed (HP-01-007,
#4437).

The factory is also the one place a received tree acquires the CASE_MANAGER
gate (BT-17-008): it wraps ``manager_effects`` in
:func:`create_case_manager_gated_tree` after ``replica_effects``, and it
refuses an :class:`~vultron.core.behaviors.emit_capable.EmitCapable` node in
``replica_effects``, outside any gate, unless the tree names a registered
:class:`~vultron.core.behaviors.replica_emit_exemptions.ReplicaEmitExemption`
that covers it.
``test/architecture/test_received_tree_case_manager_gate.py`` ratchets that no
received tree calls the gate itself (and, since #4307 retired the legacy
``effect_nodes`` parameter, that no caller passes it).

:func:`create_guarded_commit_case_ledger_entry_tree` is the commit stage.  It
is called here and nowhere else: a tree factory that calls it directly forks
the chain (CLP-09-001) and is a CLP-10-006 ordering violation caught by
``test/architecture/test_receive_side_bt_commit_ordering.py``.

Split out of ``nodes/lifecycle.py`` when that module came within the
BTND-07-004 split window of its cap; ``lifecycle.py`` keeps the commit *node*, and this tree-factory module
sits at the area root as BTND-07-003 requires.
"""

import logging
from collections.abc import Sequence

import py_trees

from vultron.core.behaviors.act_transaction import (
    ActTransaction,
    OneActExemption,
    received_act_stage,
)
from vultron.core.behaviors.case.case_clock_decisions import (
    case_clock_decisions,
)
from vultron.core.behaviors.case.nodes.addressee import (
    ADDRESSEE_EXEMPTIONS,
    ActivityAddressedToReceiverNode,
    AddresseeExemption,
)
from vultron.core.behaviors.case.nodes.case_lookup import CaseResolving
from vultron.core.behaviors.case.nodes.clock_decision_stage import (
    create_clock_decision_gate,
)
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
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
    PostCloseExemption,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    RefusalNoticeExemption,
    refusal_effects_with_notice,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
    RefusalEffectsBestEffort,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.exemption_registry import require_registered
from vultron.core.behaviors.note.case_manager_note import (
    _CommitCaseManagerNoteBase,
)
from vultron.core.behaviors.replica_emit_exemptions import (
    REPLICA_EMIT_EXEMPTIONS,
    ReplicaEmitExemption,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    LedgerActivityContext,
    SenderContext,
    closed_sender_door,
    compose_sender_guard,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes.chain import CreateLogEntryNode
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


def create_guarded_commit_case_ledger_entry_tree(
    case_id: str | None = None,
    case_may_be_absent: bool = False,
) -> py_trees.composites.Selector:
    """Create a guarded commit subtree for canonical case-ledger entries.

    The commit runs only when the executing actor holds ``CVDRole.CASE_MANAGER``
    for the case; see :func:`create_case_manager_gated_tree` for the gate's
    failure-mode semantics.

    Called internally by :func:`create_receive_activity_tree`.  Direct callers
    in tree-factory modules are a CLP-10-006 ordering violation; use
    ``create_receive_activity_tree`` instead.

    ``case_may_be_absent`` is passed to the gate; see
    :func:`create_receive_activity_tree`.
    """
    return create_case_manager_gated_tree(
        name="GuardedCommitCaseLedgerEntryBT",
        case_id=case_id,
        children=[CommitCaseLedgerEntryNode(case_id=case_id)],
        case_may_be_absent=case_may_be_absent,
    )


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


def _check_gate_arguments(
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


def _check_replica_effects(
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


def _addressee_stage(
    name: str, exemption: AddresseeExemption | None
) -> list[py_trees.behaviour.Behaviour]:
    """The addressee door guard, labelled with the tree's name (HP-01-005).

    Nothing for a tree that passes a registered exemption.

    Raises:
        VultronWiringError: *exemption* is not registered in
            ``ADDRESSEE_EXEMPTIONS``.
    """
    if exemption is None:
        return [ActivityAddressedToReceiverNode(label=name)]
    require_registered(
        exemption,
        ADDRESSEE_EXEMPTIONS,
        where=f"create_receive_activity_tree({name})",
        kind="addressee",
        registry_name="ADDRESSEE_EXEMPTIONS",
        spec_id="HP-01-005",
    )
    return []


def _manager_stage(
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


def _refusal_stage(
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


def _post_close_stage(
    name: str,
    intake: IntakeReceivedActivityNode,
    guard_case_id: str | None,
    exemption: PostCloseExemption | None,
    reply: list[py_trees.behaviour.Behaviour],
) -> list[py_trees.behaviour.Behaviour]:
    """The post-close write-boundary guard, with its optional reply.

    Returns the nodes to place directly after intake: nothing for an exempt
    tree, the bare :class:`CaseOpenToExternalWritesNode` when the tree owes
    no reply, or a refusal stage that runs *reply* only when the guard
    refuses (CM-23-013).

    Raises:
        VultronWiringError: an exempt tree passes a reply (the reply could
            never run), or a reply node is not emit-capable or writes state.
    """
    if exemption is not None:
        if reply:
            raise VultronWiringError(
                f"create_receive_activity_tree({name}): post_close_reply"
                f" needs the post-close guard, but the tree is exempt"
                f" ({exemption}) (CM-23-013)"
            )
        return []
    guard = CaseOpenToExternalWritesNode(
        case_id=guard_case_id, name="CaseOpenToExternalWrites"
    )
    if not reply:
        return [guard]
    return [
        _refusal_stage(
            name,
            intake,
            [guard],
            reply,
            guard_case_id,
            stage_name="PostCloseStage",
            guards_name="PostCloseGuard",
            gate_suffix="PostCloseReplyIfCaseManager",
            argument="post_close_reply",
        )
    ]


def _clock_decision_stage(
    name: str,
    case_id: str | None,
    decisions: list[py_trees.behaviour.Behaviour],
    *,
    sender_guarded: bool,
    post_close_exemption: PostCloseExemption | None,
) -> CaseManagerGate:
    """The tree's clock decisions, run only at the case's CASE_MANAGER.

    A clock decision commits only CASE_MANAGER-authored entries, one for each
    AS2 activity that expresses what it decided, and the changes they record,
    so it may hold neither the received activity's commit node nor the
    guarded-commit subtree around it (CLP-10-025): either would commit the
    activity's own assertion before the guards judge it.

    It writes, so both door guards must run first: the sender guard, so a
    sender with no standing never makes the CASE_MANAGER write (HP-01-006),
    and the post-close boundary, so nothing is recorded once the case is
    fully closed (CM-23-013).  A tree with no sender guard or with a
    post-close exemption cannot take clock decisions.

    The gate reads a case this store does not hold as "not the CASE_MANAGER"
    at ``debug`` level: a replica, or an invitee holding only a stub, never
    computes a clock decision (CM-28-014).

    Raises:
        VultronWiringError: *case_id* is ``None`` — there is no case whose
            CASE_MANAGER could take the decision — the tree has no sender
            guard or is exempt from the post-close boundary, or a decision
            holds the received activity's commit.
    """
    where = f"create_receive_activity_tree({name})"
    if case_id is None:
        raise VultronWiringError(
            f"{where}: clock_decisions need a case_id or manager_case_id,"
            " the case whose CASE_MANAGER takes them (CLP-10-025)"
        )
    if not sender_guarded:
        raise VultronWiringError(
            f"{where}: clock_decisions need a sender_rule, so the sender"
            " guard runs before the CASE_MANAGER writes (HP-01-006,"
            " CLP-10-025)"
        )
    if post_close_exemption is not None:
        raise VultronWiringError(
            f"{where}: clock_decisions cannot run on a tree exempt from the"
            f" post-close boundary ({post_close_exemption.name}); nothing is"
            " recorded once the case is fully closed (CM-23-013, CLP-10-025)"
        )
    activity_commits = sorted(
        {
            type(n).__name__
            for root in decisions
            for n in root.iterate()
            if isinstance(n, CommitCaseLedgerEntryNode)
        }
    )
    if activity_commits:
        raise VultronWiringError(
            f"{where}: a clock decision commits only its own entry, never"
            f" the received activity; found {activity_commits} (CLP-10-025)"
        )
    return create_clock_decision_gate(case_id, decisions)


def _case_and_tree_decisions(
    case_id: str | None,
    tree_decisions: list[py_trees.behaviour.Behaviour],
    *,
    sender_guarded: bool,
    post_close_exemption: PostCloseExemption | None,
) -> list[py_trees.behaviour.Behaviour]:
    """The case-wide clock decisions, then the tree's own.

    The case-wide decisions (the embargo end-time check, EMB-13-003) run on
    every tree that names a case, has a sender guard and keeps the
    post-close boundary, because both door guards must run before the
    CASE_MANAGER writes (HP-01-006, CM-23-013).  A tree with no sender guard
    takes them once it declares its sender rule (HP-01-008); a tree exempt
    from the post-close boundary never does.  The tree's own
    decisions are returned as given, so :func:`_clock_decision_stage`
    refuses them on a tree where they cannot run.
    """
    if case_id is None or not sender_guarded or post_close_exemption:
        return tree_decisions
    return [*case_clock_decisions(case_id), *tree_decisions]


def _node_types(
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


class ReceivedActivityTree(py_trees.composites.Sequence):
    """The one tree a received activity runs (CLP-10-005, ADR-0135).

    A plain ``Sequence`` that also remembers which of its children are the
    door guards (intake, the post-close guard, the addressee check and the
    sender guard, CLP-10-010), so a handler can ask whether the delivery got
    past them without knowing which guard the tree runs first, and which
    exemptions, if any, it was built with in place of the refusal notice
    (CLP-02-005) and of one act (CLP-07-015).
    """

    def __init__(
        self,
        name: str,
        children: list[py_trees.behaviour.Behaviour],
        door_guards: Sequence[py_trees.behaviour.Behaviour],
        refusal_notice_exemption: RefusalNoticeExemption | None = None,
        one_act_exemption: OneActExemption | None = None,
    ) -> None:
        super().__init__(name=name, memory=False, children=children)
        self.door_guards: tuple[py_trees.behaviour.Behaviour, ...] = tuple(
            door_guards
        )
        self.refusal_notice_exemption: RefusalNoticeExemption | None = (
            refusal_notice_exemption
        )
        self.one_act_exemption: OneActExemption | None = one_act_exemption

    @property
    def door_guards_admitted(self) -> bool:
        """True once every door guard ran and succeeded on the last tick."""
        return all(
            guard.status == py_trees.common.Status.SUCCESS
            for guard in self.door_guards
        )


def received_stages(
    tree: py_trees.behaviour.Behaviour,
) -> list[py_trees.behaviour.Behaviour]:
    """The stages *tree* runs, in order, with an act block opened in place.

    A tree that commits to a case holds its guarded commit and effects in
    one :class:`~vultron.core.behaviors.act_transaction.ActTransaction`
    child; its children stand in for it here, so a reader of the stage order
    (the commit-ordering and refusal-notice ratchets) sees the same stages
    with or without the block.
    """
    stages: list[py_trees.behaviour.Behaviour] = []
    for child in tree.children:
        if isinstance(child, ActTransaction):
            stages.extend(child.children)
        else:
            stages.append(child)
    return stages


def _case_manager_commit_types() -> tuple[type, ...]:
    """The node classes that commit a CASE_MANAGER-authored entry.

    ``CreateLogEntryNode`` commits an entry it mints in-tree, and
    ``_CommitCaseManagerActivityBase`` one activity it builds and commits;
    neither belongs in a ``RECEIVER`` diversion (CLP-10-026).
    """
    return (CreateLogEntryNode, _CommitCaseManagerActivityBase)


def _diversion_stage(
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
    if offenders := _node_types(
        condition, (EmitCapable, StateWriteCapable, CommitCaseLedgerEntryNode)
    ):
        raise VultronWiringError(
            f"{where}: its condition must be read-only; found {offenders}"
            " (CLP-10-026)"
        )
    effects = list(diversion.effects)
    if commits := _node_types(effects, CommitCaseLedgerEntryNode):
        raise VultronWiringError(
            f"{where}: a diverted delivery is never committed as received;"
            f" found {commits} (CLP-10-026)"
        )
    if diversion.gate is DiversionGate.RECEIVER:
        if writers := _node_types(effects, StateWriteCapable):
            raise VultronWiringError(
                f"{where}: a receiver's own answer writes no case state;"
                f" found {writers} (RSH-08-003, CLP-10-026)"
            )
        if commits := _node_types(effects, _case_manager_commit_types()):
            raise VultronWiringError(
                f"{where}: a diversion that commits runs only at the"
                f" CASE_MANAGER; found {commits} (CLP-10-026, BT-17-001)"
            )
        _check_replica_effects(name, effects, diversion.emit_exemption)
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


def _precondition_guards(
    name: str,
    guards: Sequence[py_trees.behaviour.Behaviour | Diversion],
    case_id: str | None,
) -> list[py_trees.behaviour.Behaviour]:
    """The tree's precondition guards, each :class:`Diversion` built in place.

    A diverted delivery is answered by its diversion, so the refusal stage
    that wraps these guards runs no refusal effect for it (CLP-10-026).
    """
    return [
        _diversion_stage(name, guard, case_id)
        if isinstance(guard, Diversion)
        else guard
        for guard in guards
    ]


def _sender_guard_stage(
    name: str,
    case_id: str | None,
    manager_case_id: str | None,
    sender_rule: SenderRule | None,
    sender_context: SenderContext | None,
) -> py_trees.behaviour.Behaviour | None:
    """The tree's sender guard, composed from the declared rule (HP-01-008).

    A tree that commits (``case_id`` set) must judge the sender against that
    case, and a tree that commits nothing but writes for a CASE_MANAGER
    (*manager_case_id*, the close-case tree) against that one; a tree with
    neither judges it against the case its *sender_context* names.  A
    :class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`
    reads the case from the activity at run time, so it is given only to a
    tree with no commit case at build time.
    """
    if sender_rule is None:
        if sender_context is not None:
            raise VultronWiringError(
                f"{name}: sender_context is given without a sender_rule"
            )
        return None
    if sender_context is None:
        raise VultronWiringError(
            f"{name}: sender_rule needs a sender_context (HP-01-008)"
        )
    if isinstance(sender_context, LedgerActivityContext):
        context_case, tree_case = None, case_id
    else:
        context_case = sender_context.case_id
        tree_case = case_id or manager_case_id
    if tree_case is not None and context_case != tree_case:
        raise VultronWiringError(
            f"{name}: sender_context names case {context_case!r}"
            f" but the tree's case is {tree_case!r} (HP-01-008)"
        )
    return compose_sender_guard(sender_rule, sender_context)


def _closed_sender_stage(
    name: str, case_id: str | None, check: ClosedSenderCheck
) -> py_trees.behaviour.Behaviour:
    """The closed-sender door guard on the tree's case (CM-23-018).

    Raises:
        VultronWiringError: The tree names no case to check the sender's
            closure on.
    """
    if case_id is None:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): closed_sender needs the"
            " tree's case_id or manager_case_id (CM-23-018)"
        )
    return closed_sender_door(case_id, check)


def _case_resolution_stage(
    name: str,
    steps: list[py_trees.behaviour.Behaviour],
    *,
    sender_guarded: bool,
) -> list[py_trees.behaviour.Behaviour]:
    """The steps that resolve the case the sender guard reads (HP-01-008).

    They run between the post-close guard and the sender guard, so they may
    only read: a sender with no standing must leave nothing behind
    (HP-01-006).  A step may publish what it resolved on the blackboard
    (``/case_id``), which is not a DataLayer write.  Not every writer carries
    a marker (a ledger commit, replication state), so a step is admitted by
    the :class:`~vultron.core.behaviors.case.nodes.case_lookup.CaseResolving`
    marker on each of its leaves, and refused if any node in it is also
    marked as a state writer or an emitter.

    Raises:
        VultronWiringError: steps are given without a sender guard to run
            them for, or a step holds a leaf without the ``CaseResolving``
            marker, a state writer or an emit-capable node.
    """
    if not steps:
        return []
    where = f"create_receive_activity_tree({name})"
    if not sender_guarded:
        raise VultronWiringError(
            f"{where}: case_resolution resolves the case the sender guard"
            " reads; pass it only with a sender_rule (HP-01-008)"
        )
    nodes = [n for root in steps for n in root.iterate()]
    refused = sorted(
        {
            type(n).__name__
            for n in nodes
            if isinstance(n, (StateWriteCapable, EmitCapable))
            or (not n.children and not isinstance(n, CaseResolving))
        }
    )
    if refused:
        raise VultronWiringError(
            f"{where}: case_resolution runs before the sender guard, so it"
            " may only read; each leaf must be a CaseResolving node that"
            f" writes no state and emits nothing; found {refused}"
            " (HP-01-006)"
        )
    return steps


def create_receive_activity_tree(
    name: str,
    case_id: str | None,
    precondition_guards: Sequence[py_trees.behaviour.Behaviour | Diversion],
    case_may_be_absent: bool = False,
    *,
    addressee_exemption: AddresseeExemption | None = None,
    closed_sender: ClosedSenderCheck | None = None,
    sender_rule: SenderRule | None = None,
    sender_context: SenderContext | None = None,
    case_resolution: list[py_trees.behaviour.Behaviour] | None = None,
    replica_effects: list[py_trees.behaviour.Behaviour] | None = None,
    replica_emit_exemption: ReplicaEmitExemption | None = None,
    manager_effects: list[py_trees.behaviour.Behaviour] | None = None,
    manager_case_id: str | None = None,
    manager_gate_name: str | None = None,
    manager_body_name: str | None = None,
    manager_case_may_be_absent: bool = False,
    one_act_exemption: OneActExemption | None = None,
    refusal_effects: list[py_trees.behaviour.Behaviour] | None = None,
    refusal_notice_exemption: RefusalNoticeExemption | None = None,
    post_close_exemption: PostCloseExemption | None = None,
    post_close_reply: list[py_trees.behaviour.Behaviour] | None = None,
    clock_decisions: list[py_trees.behaviour.Behaviour] | None = None,
) -> ReceivedActivityTree:
    """Compose a receive-side BT with the CLP-10-010 stages in order.

    Structurally enforces the receive-side ordering (ADR-0111, ADR-0115,
    ADR-0135, BT-17-008, CM-23-013)::

        Intake → CaseOpenToExternalWrites → ActivityAddressedToReceiver
            → [closed-sender check] → [*case_resolution]
            → [sender guard]
            → [CaseManagerGate[ClockDecisionStage[
                   *case_clock_decisions, *clock_decisions]]]
            → [*precondition_guards] → GuardedCommit
            → [*replica_effects] → CaseManagerGate[*manager_effects]

    In a tree that commits to ``case_id`` the last three stages are one
    :class:`~vultron.core.behaviors.act_transaction.ActTransaction`,
    ``ActTransaction[GuardedCommit, *replica_effects, CaseManagerGate]``,
    named ``{name}Act``: the act's own entry and every consequence a later
    node commits are written together or not at all, so a failure keeps
    nothing but intake's archive and a redelivery runs the act afresh
    (CLP-07-015, ADR-0146, ADR-0151).  A tree runs them outside one only by
    naming a registered ``one_act_exemption`` that records why.
    :func:`received_stages` lists a tree's stages either way.

    The addressee door guard,
    :class:`~vultron.core.behaviors.case.nodes.addressee.ActivityAddressedToReceiverNode`,
    follows the post-close guard in every received tree and refuses a copy
    not addressed to the receiver (HP-01-005), naming the tree in its
    reason.  Intake has archived the copy; nothing else runs (CLP-10-010,
    CLP-10-018).  A tree opts out only with ``addressee_exemption``, a
    registered
    :class:`~vultron.core.behaviors.case.nodes.addressee.AddresseeExemption`
    that records why (an ``Offer(Report)`` stores what it carried first and
    checks later, CM-15-002); no tree writes its own copy of the check.

    ``closed_sender`` places the closed-sender door guard
    (:func:`~vultron.core.behaviors.sender_guard.closed_sender_door`) on
    ``case_id`` (else ``manager_case_id``), after the addressee check: when
    the case records the sender's closure the tree stops there, with nothing
    committed or sent, and the handler asks
    :func:`~vultron.core.behaviors.sender_guard.closed_sender_turned_away`
    for the reason (CM-23-018).  Never run it as a tree of its own ahead of
    this one (CLP-10-005).

    A :class:`~vultron.core.behaviors.case.nodes.diversion_stage.Diversion`
    among ``precondition_guards`` becomes a
    :class:`~vultron.core.behaviors.case.nodes.diversion_stage.DiversionStage`
    at its place: when its read-only condition holds, its effects answer the
    delivery and the tree stops before the commit (CLP-10-026).  A
    ``CASE_MANAGER`` diversion runs only at the case's CASE_MANAGER, inside
    the gate on ``case_id`` (else ``manager_case_id``), and may commit its own
    entry; a ``RECEIVER`` diversion writes no case state and its emits need a
    registered exemption.  A diverted delivery has already been answered,
    so the refusal stage runs no refusal effect for it; the refusal notice
    and any ``refusal_effects`` answer only the refusals the guards make.

    ``clock_decisions`` are decisions the CASE_MANAGER takes from its own
    clock or local policy before it judges the activity, such as an expiry
    (CLP-10-025, CLP-07-013).  They run after the door guards, so a sender
    with no standing never makes the CASE_MANAGER write (HP-01-006), and
    before the precondition guards, because the decision is ledgered even
    when the activity is then admitted (CM-21-014).  The factory gates them
    on the CASE_MANAGER of ``case_id`` (else ``manager_case_id``) and wraps
    each in a :class:`~vultron.core.behaviors.case.nodes.clock_decision_stage.ClockDecision`:
    a decision with nothing to record succeeds, one whose commit the ledger
    refuses is logged at WARNING and the tree continues, and an internal
    error (a raised exception) ends the tree (ADR-0095).  A decision decides
    from the CASE_MANAGER's clock, policy and the case's ledger and file; the
    received activity may prompt it and name what it concerns, never be its
    evidence.  It commits only its own CASE_MANAGER-authored entries, one
    for each AS2 activity that expresses what it decided: one holding the
    received activity's commit is refused at construction, as is a tree with
    no ``sender_rule`` or with a ``post_close_exemption``, where a door guard
    would not run first.

    The case-wide decisions
    (:func:`~vultron.core.behaviors.case.case_clock_decisions.case_clock_decisions`,
    the embargo end-time check, EMB-13-003) run first in the stage of every
    tree that names a case, has a sender guard and keeps the post-close
    boundary; a tree without both door guards takes none of them.

    ``CaseOpenToExternalWrites`` is the post-close write boundary
    (CM-23-013, ADR-0085, ADR-0131): at the case's CASE_MANAGER, once the
    ledger holds its own ``RM.CLOSED`` status entry, it refuses the
    activity, so nothing is
    committed and no state changes; on any other store it passes.  Every
    received tree gets it from here.  Its case is ``case_id``, else
    ``manager_case_id``, else the case the received activity names.  A tree
    that must keep working after close passes ``post_close_exemption``.  A
    tree that answers a late activity passes ``post_close_reply``: emit-only
    nodes run, at the CASE_MANAGER, only when the guard refuses (the
    close-case tree's ``Reject(Leave)`` under ``PostCloseReply.REJECT``).
    Every other tree drops a late activity with no reply.

    With ``refusal_effects`` the guards are wrapped in a
    :class:`~vultron.core.behaviors.case.nodes.refusal_stage.PreconditionGuardStage`
    (CLP-10-022)::

        Intake → [sender guard]
            → PreconditionGuardStage
                ├─ PreconditionGuards[*precondition_guards]
                └─ RefusalEffects → CaseManagerGate[*refusal_effects]
            → GuardedCommit → …

    Intake is one shared :class:`IntakeReceivedActivityNode` that archives the
    received activity exactly as received, idempotently, and writes nothing
    else — in particular no core record from any object inlined in it, which
    an effect node writes from the event's copy after the guards
    (CLP-10-017).
    It runs first so a guard that refuses the assertion still leaves the
    receiver holding what arrived (CLP-10-018).

    The sender guard is placed immediately after intake and before the
    caller's ``precondition_guards``.
    When the case it checks the sender against is resolved at run time, the
    tree passes the read-only steps that resolve it as ``case_resolution``,
    and the factory runs them just before the guard: an activity about a
    case this store does not hold is refused as such, not as an unknown
    sender (#2255).  A ledger activity's tree passes a
    :class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`
    instead, whose nodes read the case from the entry the activity carries.
    It is the per-use-case sender-entitlement check declared via
    ``sender_entitlement`` on the use-case class (ADR-0115, HP-01-006): a
    failed guard ends the tree with ``REFUSED`` and nothing is written or sent.
    With ``sender_rule`` the factory composes the guard from the declared
    rule and ``sender_context``, for the receiver's addressee side
    (:func:`~vultron.core.behaviors.sender_guard.compose_sender_guard`,
    HP-01-008).  A tree has no way to pass a guard of its own; a sender
    check a tree places elsewhere must be on the allow-list in
    ``test/architecture/test_sender_entitlement_ratchet.py`` (HP-01-007,
    #4437).

    Precondition guards are read-only checks that may return FAILURE to abort
    the tree before any protocol effect.
    The guarded commit ledgers receipt of the triggering activity (which is on
    the blackboard before any node runs, placed there by
    ``BTBridge.execute_with_setup``).
    Effects perform state transitions, outbox enqueues, and participant
    mutations — all of which happen only after the receipt is recorded.

    Effects come in two kinds (BT-17-008).
    ``replica_effects`` run on every replica, ungated; an emit-capable node
    among them is refused at construction unless ``replica_emit_exemption``
    names a registered exemption.
    ``manager_effects`` run only at the case's CASE_MANAGER: the factory wraps
    them in :func:`create_case_manager_gated_tree` on ``manager_case_id``, a
    separate argument from ``case_id`` so a tree that omits the commit
    (``case_id=None``) can still gate its emits.
    A received-tree module does not call ``create_case_manager_gated_tree``
    itself.

    A tree that commits to ``case_id`` and has precondition guards answers
    their refusal with the refusal notice
    (:func:`~vultron.core.behaviors.case.nodes.refusal_notice.refusal_notice`,
    CLP-02-005, CLP-05-001): the factory places it first among the refusal
    effects, so no tree writes its own copy.  A tree whose refusals are
    answered otherwise names a registered ``refusal_notice_exemption`` that
    says how (the close-case tree's CM-23-011 decline).
    ``refusal_effects`` answer a refusal further — the RSH-06-004
    clarification note for a refused backward RM declaration is the case in
    point, sent alongside the notice.  Refusal effects run only when a
    precondition guard refuses, never on an
    accepted delivery, so no effect precedes the commit (CLP-10-006).  They
    do not run when the sender guard refuses: a sender not entitled to send
    the message is owed no answer about its content (HP-01-006), nor when a
    guard's failure is an idempotent repeat the handler reports ``SKIPPED``
    (``ReportsIdempotentRepeat``).  The factory
    gates them on the CASE_MANAGER of ``case_id`` (when it is ``None`` the
    gate resolves the case from the blackboard and skips without one), skips
    them on a redelivery that intake
    found already archived, and keeps the tree's result the guard's
    ``FAILURE``, so nothing is committed and the handler still reports
    ``REFUSED`` for the guard's reason.  Each refusal effect must be
    emit-capable and contain no state writer: a refusal commits nothing, so
    it may change no state.

    The pre-BT-17-008 ``effect_nodes`` parameter — ungated and unchecked — was
    retired in #4307 once the close-case tree, its last caller, moved its
    decline emit onto ``manager_effects`` (#3825).  Every received tree now
    passes ``replica_effects`` / ``manager_effects``.

    When ``case_id`` is ``None`` the commit step is omitted entirely,
    preserving behaviour for trees that receive no explicit case context;
    intake still runs.

    Set ``case_may_be_absent`` when the receiver legitimately holds no replica
    of the case yet — an invitee holds only the Invite's case stub
    (MV-10-004).
    The commit gate then skips at ``debug`` level for a case the receiver does
    not hold, instead of reporting it as an ADR-0087 Regime 1 anomaly.

    Args:
        name: Name for the root ``Sequence`` node.
        case_id: Case URI for the guarded-commit stage; ``None`` omits it.
        precondition_guards: Read-only guard nodes after the sender guard,
            and any diversions, in order.
        case_may_be_absent: Pass ``True`` when the receiver may not hold the
            case yet (e.g. an invitee seeing the first Invite).
        addressee_exemption: Why this tree carries no addressee door guard;
            ``None`` (the default) places it (HP-01-005).
        closed_sender: The sender whose recorded closure stops the tree, for
            a tree whose act may close its sender (CM-23-018).
        sender_rule: The use case's declared sender rule; the factory
            composes the guard from it (HP-01-008).
        sender_context: The sender and the records the rule's kinds are
            checked against; required with ``sender_rule``.  A
            :class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`
            reads the sender and the case from the received ledger activity
            at run time, for a tree with no ``case_id``.
        case_resolution: Read-only ``CaseResolving`` steps that resolve the
            case the sender guard reads, run just before it; requires
            ``sender_rule``.
        replica_effects: Ungated effects, run on every replica after the
            commit.
        replica_emit_exemption: The registered decision that lets an
            emit-capable node run in ``replica_effects``.
        manager_effects: Effects run only at the CASE_MANAGER, gated by the
            factory after ``replica_effects``.
        manager_case_id: Case whose CASE_MANAGER gates ``manager_effects``.
        manager_gate_name: Name of the gate Selector; defaults to
            ``{name}IfCaseManager``.
        manager_body_name: Name of the Sequence wrapping several
            ``manager_effects``; defaults to ``{manager_gate_name}Body``.
        manager_case_may_be_absent: Passed to the gate; see
            :class:`CheckIsCaseManagerNode`.
        one_act_exemption: Why this tree runs its guarded commit and
            effects outside one
            :class:`~vultron.core.behaviors.act_transaction.ActTransaction`;
            ``None`` (the default) runs them as one act whenever ``case_id``
            is given (CLP-07-015, ADR-0146).
        refusal_effects: Emit-capable nodes run only when a precondition
            guard refuses, at the CASE_MANAGER, once per received activity,
            after the refusal notice.
        refusal_notice_exemption: Why this tree sends no refusal notice;
            ``None`` (the default) adds it to a tree that commits to
            ``case_id`` and has precondition guards (CLP-02-005).
        post_close_exemption: Why this tree carries no post-close guard;
            ``None`` (the default) places it (CM-23-013).
        post_close_reply: Emit-capable nodes run only when the post-close
            guard refuses, at the CASE_MANAGER, once per received activity.
        clock_decisions: The CASE_MANAGER's own decisions from its clock or
            policy, run after the door guards and before the precondition
            guards, at the CASE_MANAGER only (CLP-10-025).

    Raises:
        VultronWiringError: ``manager_effects`` has no ``manager_case_id``, a
            gate argument is passed without ``manager_effects``, an exemption
            is unregistered, an emit-capable node sits in ``replica_effects``
            without one (BT-17-008), or a refusal effect is not emit-capable or
            holds a state writer (CLP-10-022), or a
            ``refusal_notice_exemption`` is unregistered or exempts a tree
            that would send no notice (CLP-02-005), or an exempt tree passes a
            ``post_close_reply`` (CM-23-013), or the sender arguments are
            inconsistent: an ``addressee_exemption`` is not registered
            (HP-01-005), ``sender_rule`` without ``sender_context``, a
            ``sender_context`` without ``sender_rule``, or a
            ``sender_context`` naming another case than ``case_id`` (else
            ``manager_case_id``), or a ``closed_sender`` check on a tree
            with no case, or a ``case_resolution`` without ``sender_rule``
            or holding a node that is not a read-only ``CaseResolving`` step
            (HP-01-008), or a
            diversion is ill-formed (CLP-10-026), or ``clock_decisions`` name no
            case, come without a ``sender_rule`` or with a
            ``post_close_exemption``, or hold the received activity's commit
            (CLP-10-025), or a ``one_act_exemption`` is unregistered or
            exempts a tree that commits to no case (CLP-07-015).

    Per ``specs/case-ledger-processing.yaml`` CLP-02-005, CLP-05-001,
    CLP-07-015,
    CLP-10-006, CLP-10-010, CLP-10-017, CLP-10-022, CLP-10-025, CLP-10-026,
    ``specs/behavior-tree-integration.yaml``
    BT-17-008 and ``specs/case-management.yaml`` CM-23-013.
    """
    replica = replica_effects or []
    manager = manager_effects or []
    _check_gate_arguments(
        name,
        gate_arguments_without_effects=not manager
        and (
            manager_case_id is not None
            or manager_gate_name is not None
            or manager_body_name is not None
            or manager_case_may_be_absent
        ),
    )
    _check_replica_effects(name, replica, replica_emit_exemption)

    intake = IntakeReceivedActivityNode()
    children: list[py_trees.behaviour.Behaviour] = [intake]
    children.extend(
        _post_close_stage(
            name,
            intake,
            case_id or manager_case_id,
            post_close_exemption,
            post_close_reply or [],
        )
    )
    children.extend(_addressee_stage(name, addressee_exemption))
    if closed_sender is not None:
        children.append(
            _closed_sender_stage(
                name, case_id or manager_case_id, closed_sender
            )
        )
    guard = _sender_guard_stage(
        name, case_id, manager_case_id, sender_rule, sender_context
    )
    children.extend(
        _case_resolution_stage(
            name, case_resolution or [], sender_guarded=guard is not None
        )
    )
    if guard is not None:
        children.append(guard)
    door_guards = list(children)
    decisions = _case_and_tree_decisions(
        case_id or manager_case_id,
        clock_decisions or [],
        sender_guarded=guard is not None,
        post_close_exemption=post_close_exemption,
    )
    if decisions:
        children.append(
            _clock_decision_stage(
                name,
                case_id or manager_case_id,
                decisions,
                sender_guarded=guard is not None,
                post_close_exemption=post_close_exemption,
            )
        )
    effects = refusal_effects_with_notice(
        name,
        case_id,
        precondition_guards,
        refusal_effects or [],
        refusal_notice_exemption,
    )
    guards = _precondition_guards(
        name,
        precondition_guards,
        case_id or manager_case_id,
    )
    if effects:
        children.append(
            _refusal_stage(
                name,
                intake,
                guards,
                effects,
                case_id,
            )
        )
    else:
        children.extend(guards)
    act: list[py_trees.behaviour.Behaviour] = []
    if case_id is not None:
        act.append(
            create_guarded_commit_case_ledger_entry_tree(
                case_id=case_id, case_may_be_absent=case_may_be_absent
            )
        )
    else:
        logger.debug(
            "create_receive_activity_tree(%s): case_id is None"
            " — commit step omitted",
            name,
        )
    act.extend(replica)
    if manager:
        act.append(
            _manager_stage(
                name,
                manager,
                manager_case_id,
                manager_gate_name,
                manager_body_name,
                manager_case_may_be_absent,
            )
        )
    # The act's own entry commits with its consequences, or none of them is
    # kept (CLP-07-015, ADR-0151).
    children.extend(received_act_stage(name, act, case_id, one_act_exemption))
    return ReceivedActivityTree(
        name=name,
        children=children,
        door_guards=door_guards,
        refusal_notice_exemption=refusal_notice_exemption,
        one_act_exemption=one_act_exemption,
    )
