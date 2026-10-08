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

"""Receive-side tree composition: the four-stage shared factory (ADR-0111).

:func:`create_receive_activity_tree` is the one way to build a received-side
BT.
It fixes the stage order intake → sender guard → precondition guards →
guarded commit → protocol effects (CLP-10-006, CLP-10-010, ADR-0115) and
supplies the shared intake node itself (CLP-10-017), so no handler opts out
of recording what arrived.
A tree that owes the sender feedback when its guards refuse passes
``refusal_effects``: the factory runs them only on that refusal, at the
CASE_MANAGER, once per received activity, and the tree still fails before
the commit (CLP-10-022).

When ``sender_guard`` is provided, the factory places it immediately after
intake and before the caller's ``precondition_guards``.
A failed sender guard ends the tree with ``REFUSED`` and nothing is written
or sent (HP-01-006, ADR-0115).

The factory is also the one place a received tree acquires the CASE_MANAGER
gate (BT-17-008): it wraps ``manager_effects`` in
:func:`create_case_manager_gated_tree` after ``replica_effects``, and it
refuses an :class:`~vultron.core.behaviors.emit_capable.EmitCapable` node in
``replica_effects``, outside any gate, unless the tree names a registered
:class:`~vultron.core.behaviors.replica_emit_exemptions.ReplicaEmitExemption`
that covers it.
``test/architecture/test_received_tree_case_manager_gate.py`` ratchets the
received trees that still call the gate themselves or still pass the
unchecked legacy ``effect_nodes``.

:func:`create_guarded_commit_case_ledger_entry_tree` is the commit stage.  It
is called here and nowhere else: a tree factory that calls it directly forks
the chain (CLP-09-001) and is a CLP-10-006 ordering violation caught by
``test/architecture/test_receive_side_bt_commit_ordering.py``.

Split out of ``nodes/lifecycle.py`` when that module came within the
BTND-07-004 split window of its cap; ``lifecycle.py`` keeps the commit *node*, and this tree-factory module
sits at the area root as BTND-07-003 requires.
"""

import logging

import py_trees

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
    CaseManagerGate,
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.replica_emit_exemptions import (
    REPLICA_EMIT_EXEMPTIONS,
    ReplicaEmitExemption,
)
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


def _check_effect_arguments(
    name: str,
    *,
    legacy: bool,
    new_kinds: bool,
    gate_arguments_without_effects: bool,
) -> None:
    """Refuse effect arguments that would be silently ignored or mixed.

    Raises:
        VultronWiringError: legacy ``effect_nodes`` is combined with
            ``replica_effects``, ``manager_effects`` or an exemption, or a
            gate argument is passed without ``manager_effects`` (BT-17-008).
    """
    where = f"create_receive_activity_tree({name})"
    if legacy and new_kinds:
        raise VultronWiringError(
            f"{where}: effect_nodes cannot be combined with replica_effects,"
            " manager_effects or replica_emit_exemption (BT-17-008)"
        )
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
    if exemption is None:
        covered: frozenset[str] = frozenset()
    elif REPLICA_EMIT_EXEMPTIONS.get(exemption.name) != exemption:
        raise VultronWiringError(
            f"{where}: replica emit exemption {exemption.name!r} is not"
            " registered in REPLICA_EMIT_EXEMPTIONS (BT-17-008)"
        )
    elif not emitted & exemption.covers:
        raise VultronWiringError(
            f"{where}: replica emit exemption {exemption.name!r} covers"
            " none of the tree's ungated emitters; drop it (BT-17-008)"
        )
    else:
        covered = exemption.covers
    if uncovered := sorted(emitted - covered):
        raise VultronWiringError(
            f"{where}: emit-capable node(s) {uncovered} in replica_effects"
            " would run on every replica; pass them as manager_effects so"
            " the factory gates them on the CASE_MANAGER, or name a"
            " ReplicaEmitExemption that covers them (BT-17-008)"
        )


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
    refusal_case_id: str | None,
) -> PreconditionGuardStage:
    """Wrap the guards so *refusal_effects* run only when they refuse.

    The refusal effects sit inside the CASE_MANAGER gate on
    *refusal_case_id*: the CASE_MANAGER adjudicates, so only it answers a
    refusal (BT-17-008).  The gate reads a case this store does not hold as
    "not the CASE_MANAGER" at ``debug`` level, because the guard that refused
    an unknown case has already reported it.

    Raises:
        VultronWiringError: a refusal effect is not emit-capable.  A refusal
            commits nothing, so a refusal effect may only speak to the
            sender; a state write here would change state the ledger never
            records (CLP-10-022).
    """
    if not_emitters := [
        type(n).__name__
        for n in refusal_effects
        if not isinstance(n, EmitCapable)
    ]:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): refusal_effects"
            f" {not_emitters} are not emit-capable; a refusal commits"
            " nothing, so its effects may only emit (CLP-10-022)"
        )
    gate = create_case_manager_gated_tree(
        name=f"{name}RefusalIfCaseManager",
        case_id=refusal_case_id,
        children=refusal_effects,
        case_may_be_absent=True,
    )
    return PreconditionGuardStage(
        name="PreconditionGuardStage",
        guards=py_trees.composites.Sequence(
            name="PreconditionGuards",
            memory=False,
            children=precondition_guards,
        ),
        refusal=RefusalEffectsBestEffort(name="RefusalEffects", child=gate),
        intake=intake,
    )


def create_receive_activity_tree(
    name: str,
    case_id: str | None,
    precondition_guards: list[py_trees.behaviour.Behaviour],
    effect_nodes: list[py_trees.behaviour.Behaviour] | None = None,
    case_may_be_absent: bool = False,
    *,
    sender_guard: "py_trees.behaviour.Behaviour | None" = None,
    replica_effects: list[py_trees.behaviour.Behaviour] | None = None,
    replica_emit_exemption: ReplicaEmitExemption | None = None,
    manager_effects: list[py_trees.behaviour.Behaviour] | None = None,
    manager_case_id: str | None = None,
    manager_gate_name: str | None = None,
    manager_body_name: str | None = None,
    manager_case_may_be_absent: bool = False,
    refusal_effects: list[py_trees.behaviour.Behaviour] | None = None,
    refusal_case_id: str | None = None,
) -> py_trees.composites.Sequence:
    """Compose a receive-side BT with the four CLP-10-010 stages in order.

    Structurally enforces the receive-side ordering (ADR-0111, ADR-0115,
    BT-17-008)::

        Intake → [sender_guard] → [*precondition_guards] → GuardedCommit
            → [*replica_effects] → CaseManagerGate[*manager_effects]

    With ``refusal_effects`` the guards are wrapped in a
    :class:`~vultron.core.behaviors.case.nodes.refusal_stage.PreconditionGuardStage`
    (CLP-10-022)::

        Intake → [sender_guard]
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

    When ``sender_guard`` is provided it is placed immediately after intake
    and before the caller's ``precondition_guards``.
    The sender guard is the per-use-case sender-entitlement check declared via
    ``sender_entitlement`` on the use-case class (ADR-0115, HP-01-006): a
    failed guard ends the tree with ``REFUSED`` and nothing is written or sent.

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

    ``refusal_effects`` answer a refusal in the moment — the RSH-06-004
    clarification note for a refused backward RM declaration is the case in
    point.  They run only when a precondition guard refuses, never on an
    accepted delivery, so no effect precedes the commit (CLP-10-006).  They
    do not run when the sender guard refuses: a sender not entitled to send
    the message is owed no answer about its content (HP-01-006).  The factory
    gates them on the CASE_MANAGER of ``refusal_case_id`` (default
    ``case_id``; when both are ``None`` the gate resolves the case from the
    blackboard and skips without one), skips them on a redelivery that intake
    found already archived, and keeps the tree's result the guard's
    ``FAILURE``, so nothing is committed and the handler still reports
    ``REFUSED`` for the guard's reason.  Each refusal effect must be
    emit-capable and contain no state writer: a refusal commits nothing, so
    it may change no state.

    ``effect_nodes`` is the pre-BT-17-008 form, kept until the last received
    trees migrate (#4307): it runs ungated where ``replica_effects`` would,
    unchecked.  It cannot be combined with the two new kinds.

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
        precondition_guards: Read-only guard nodes after the sender guard.
        effect_nodes: Legacy ungated effects, unchecked; migrating away.
        case_may_be_absent: Pass ``True`` when the receiver may not hold the
            case yet (e.g. an invitee seeing the first Invite).
        sender_guard: Optional sender-entitlement condition node, placed
            immediately after intake (HP-01-006, ADR-0115).
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
        refusal_effects: Emit-capable nodes run only when a precondition
            guard refuses, at the CASE_MANAGER, once per received activity.
        refusal_case_id: Case whose CASE_MANAGER gates ``refusal_effects``;
            defaults to ``case_id``.

    Raises:
        VultronWiringError: ``effect_nodes`` is mixed with the new effect
            kinds, ``manager_effects`` has no ``manager_case_id``, an
            exemption is unregistered, an emit-capable node sits in
            ``replica_effects`` without one (BT-17-008), or a refusal effect
            is not emit-capable (CLP-10-022).

    Per ``specs/case-ledger-processing.yaml`` CLP-10-006, CLP-10-010,
    CLP-10-017, CLP-10-022 and ``specs/behavior-tree-integration.yaml`` BT-17-008.
    """
    replica = replica_effects or []
    manager = manager_effects or []
    _check_effect_arguments(
        name,
        legacy=bool(effect_nodes),
        new_kinds=bool(replica or manager or replica_emit_exemption),
        gate_arguments_without_effects=not manager
        and (
            manager_case_id is not None
            or manager_gate_name is not None
            or manager_body_name is not None
            or manager_case_may_be_absent
        ),
    )
    _check_replica_effects(name, replica, replica_emit_exemption)
    if refusal_case_id is not None and not refusal_effects:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): refusal_case_id"
            " configures the gate around refusal_effects; pass it only"
            " with refusal_effects (CLP-10-022)"
        )

    intake = IntakeReceivedActivityNode()
    children: list[py_trees.behaviour.Behaviour] = [intake]
    if sender_guard is not None:
        children.append(sender_guard)
    if refusal_effects:
        children.append(
            _refusal_stage(
                name,
                intake,
                precondition_guards,
                refusal_effects,
                refusal_case_id if refusal_case_id is not None else case_id,
            )
        )
    else:
        children.extend(precondition_guards)
    if case_id is not None:
        children.append(
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
    children.extend(effect_nodes or [])
    children.extend(replica)
    if manager:
        children.append(
            _manager_stage(
                name,
                manager,
                manager_case_id,
                manager_gate_name,
                manager_body_name,
                manager_case_may_be_absent,
            )
        )
    return py_trees.composites.Sequence(
        name=name,
        memory=False,
        children=children,
    )
