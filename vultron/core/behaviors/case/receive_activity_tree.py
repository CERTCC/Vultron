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

"""Receive-side tree composition: the staged shared factory (ADR-0135, ADR-0154).

:func:`create_receive_activity_tree` is the one way to build a received-side
BT.
It fixes the stage order door guards (addressee check, seen-before door,
path stage, post-close guard, closed-sender check, sender guard) → intake →
clock decisions → precondition guards → guarded commit → protocol effects
(CLP-10-006, CLP-10-010, CLP-10-025, ADR-0115, CM-23-013, HP-01-005) and
supplies the door guards and the shared intake node itself (CLP-10-017,
ADR-0131, HP-01-005), so no handler acts on a copy that was not addressed to
it, re-runs a resend, forgets the closed-case boundary or opts out of
recording what arrived.  Each door can end the run, and nothing is written
before the last one admits the message (ADR-0154).  A tree leaves a door guard out only
by naming a registered exemption (``post_close_exemption``,
``addressee_exemption``) that records why.

A tree that declares its ``paths`` also gets the path door stage (ADR-0153):
one role question picks the manager, participant-replica or no-case path, the
sender guard's ``at_case_manager`` and ``at_participant`` arms are selected
from that answer rather than asking again, and a path the message type did
not declare is refused there, with a reason composed in one place from the
resolved path and the declaration (HP-01-005, HP-01-012, HP-01-039).
A tree whose CASE_MANAGER must record a decision from its own clock before
it judges the activity (an expiry) passes ``clock_decisions``: the factory
runs them at the CASE_MANAGER only, after the door guards, and a refused
commit there never ends the tree (CLP-10-025).  Every tree with a case and a
sender guard also takes the case-wide clock decisions (the embargo end-time
check, EMB-13-003) ahead of its own, with no argument.
Every tree whose sender guard names a case also answers the ledger position
the received activity stamps, at the CASE_MANAGER, without letting the answer
decide the act (SYNC-18-004, SYNC-18-005, SYNC-18-007).
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
it and places it last among the door guards, before intake and the caller's
``precondition_guards``; a
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

This tree-factory module sits at the area root as BTND-07-003 requires and
holds the factory alone; the stage builders it composes live in
``case/receive_stages/``, grouped by concern (CS-18-005), and the public names
among them are re-exported here.
"""

import logging
from collections.abc import Collection, Sequence

import py_trees

from vultron.core.behaviors.act_transaction import (
    OneActExemption,
    received_act_stage,
)
from vultron.core.behaviors.case.nodes.addressee import (
    AddresseeExemption,
)
from vultron.core.behaviors.case.nodes.diversion_stage import (
    Diversion,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.path_branch import (
    OnPaths,
    resolve_path_branches,
)
from vultron.core.behaviors.case.nodes.post_close import (
    PostCloseExemption,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    RefusalNoticeExemption,
    refusal_effects_with_notice,
)
from vultron.core.behaviors.case.receive_stages.decisions import (
    case_and_tree_decisions,
    clock_decision_stage,
    ledger_position_stage,
    sender_sequence_stage,
)
from vultron.core.behaviors.case.receive_stages.doors import (
    addressee_stage,
    case_resolution_stage,
    check_nested,
    closed_sender_stage,
    path_stage_case_id,
    post_close_stage,
    received_path_stage,
    seen_before_stage,
    sender_guard_stage,
)
from vultron.core.behaviors.case.receive_stages.effects import (
    check_gate_arguments,
    check_replica_effects,
    manager_stage,
    ungated_emitters,
    ungated_nodes,
)
from vultron.core.behaviors.case.receive_stages.guards import (
    precondition_guard_nodes,
    refusal_stage,
)
from vultron.core.behaviors.case.receive_stages.tree import (
    ReceivedActivityTree,
    create_guarded_commit_case_ledger_entry_tree,
    received_stages,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.replica_emit_exemptions import (
    ReplicaEmitExemption,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    SenderContext,
)
from vultron.core.behaviors.sync.nodes.ledger_position import (
    LedgerPositionExemption,
)
from vultron.core.behaviors.sync.nodes.sender_sequence import (
    SenderSequenceExemption,
)

logger = logging.getLogger(__name__)


def create_receive_activity_tree(
    name: str,
    case_id: str | None,
    precondition_guards: Sequence[
        py_trees.behaviour.Behaviour | Diversion | OnPaths
    ],
    case_may_be_absent: bool = False,
    *,
    addressee_exemption: AddresseeExemption | None = None,
    paths: Collection[ReceivedPath] | None = None,
    closed_sender: ClosedSenderCheck | None = None,
    sender_rule: SenderRule | None = None,
    sender_context: SenderContext | None = None,
    case_resolution: list[py_trees.behaviour.Behaviour] | None = None,
    replica_effects: Sequence[py_trees.behaviour.Behaviour | OnPaths]
    | None = None,
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
    ledger_position_exemption: LedgerPositionExemption | None = None,
    sender_sequence_exemption: SenderSequenceExemption | None = None,
    nested: bool = False,
) -> ReceivedActivityTree:
    """Compose a receive-side BT with the CLP-10-010 stages in order.

    Structurally enforces the receive-side ordering (ADR-0115, ADR-0135,
    ADR-0154, BT-17-008, CM-23-013)::

        ActivityAddressedToReceiver → ActivityNotSeenBefore → [ReceivedPath]
            → CaseOpenToExternalWrites → [closed-sender check]
            → [*case_resolution] → [sender guard]
            → Intake
            → [CaseManagerGate[LedgerPositionAnswer]]
            → [CaseManagerGate[SenderSequenceOrder]]
            → [CaseManagerGate[ClockDecisionStage[
                   *case_clock_decisions, *clock_decisions]]]
            → [*precondition_guards] → GuardedCommit
            → [*replica_effects] → CaseManagerGate[*manager_effects]

    In a tree that commits to ``case_id`` the last three stages are one
    :class:`~vultron.core.behaviors.act_transaction.ActTransaction`,
    ``ActTransaction[GuardedCommit, *replica_effects, CaseManagerGate]``,
    named ``{name}Act``: the act's own entry and every consequence a later
    node commits are written together or not at all, so a failure keeps
    nothing but intake's record, in holding, and a redelivery runs the act
    afresh (CLP-07-015, ADR-0146, ADR-0151, CLP-10-074).  A tree runs them
    outside one only by naming a registered ``one_act_exemption`` that
    records why.
    :func:`received_stages` lists a tree's stages either way.

    The addressee door guard,
    :class:`~vultron.core.behaviors.case.nodes.addressee.ActivityAddressedToReceiverNode`,
    is the first door of every received tree and refuses a copy not
    addressed to the receiver (HP-01-005), naming the tree in its reason.
    Nothing has been written and nothing else runs; the inbox's outcome stage
    leaves the receipt stub (CLP-10-010, CLP-10-018).

    The seen-before door,
    :class:`~vultron.core.behaviors.case.nodes.seen_before.ActivityNotSeenBeforeNode`,
    follows it in every received tree, with no exemption: a delivery the
    receiver holds a record for is answered from that record's stage and the
    run ends there, so a resend re-runs nothing and no refusal notice goes
    out again (ADR-0154).  A receipt stub is ``REFUSED`` again with its
    reason, an archive and a record owed a replay are ``SKIPPED``, and a
    ``HELD`` or ``HANDLED`` record owing nothing passes: a run that ended with
    no verdict runs again (CLP-10-074).

    ``nested`` builds a received tree that runs inside another received tree
    for the same delivery (the close-case tree's close arm).  It has no
    seen-before door and no intake of its own: the enclosing tree's door
    answered the delivery and its intake recorded it, so a second intake
    would meet that record and read the first run as a re-run (ADR-0154).
    Every other stage is built as usual.

    The addressee check opts out only with ``addressee_exemption``, a
    registered
    :class:`~vultron.core.behaviors.case.nodes.addressee.AddresseeExemption`
    that records why (a subtree whose enclosing tree already runs the
    check); no tree writes its own copy of the check.

    ``paths`` is the message type's declaration of the paths it handles,
    made once, here (HP-01-038, HP-01-007).  The factory places the
    path door stage
    (:class:`~vultron.core.behaviors.case.nodes.received_path.ReceivedPathNode`)
    after the seen-before door and before the sender guard, on ``case_id``
    (else ``manager_case_id``, else the case the ``sender_context`` names, so
    a tree that commits nothing still asks about the case the activity is
    about): it asks
    :func:`~vultron.core.participants.role_predicate.has_role` once and the
    answer is the *manager*, *participant replica* or *no case yet* path
    (CM-02-011).  A tree that does real work on both the manager and the
    participant path declares a branch for each; a delivery on a path the
    declaration omits is ``REFUSED`` there, with
    :func:`~vultron.core.behaviors.case.nodes.received_path.undeclared_path_reason`,
    composed in that one place from the resolved path and the declaration, so
    every message type words it the same way and no handler maps a gate
    failure to a verdict after the run (HP-01-005, HP-01-039).  A case-scoped
    type never reaches the no-case path: the inbox's defer check holds its
    delivery until the case is known (IO-02-001), so only a type that starts
    a case declares the no-case branch and takes it (HP-01-041).  A tree that
    omits ``paths`` has no path stage, so it may carry only a sender rule
    whose sides all name the same kinds (HP-01-036).

    Work that belongs to some of the declared paths rather than to all of
    them is passed as an
    :class:`~vultron.core.behaviors.case.nodes.path_branch.OnPaths`
    declaration, among ``precondition_guards`` or ``replica_effects``, and
    the factory builds a
    :class:`~vultron.core.behaviors.case.nodes.path_branch.PathBranch` at
    that spot (HP-01-038): the CASE_MANAGER's adjudication guards with
    ``OnPaths.at_case_manager``, and the work no CASE_MANAGER does with
    ``OnPaths.off_case_manager``, the replacement for the
    participant-replica gate a received tree used to build for itself.  The
    branch reads the path the stage resolved and asks no role question of
    its own (HP-01-036).  A tree with no ``paths`` cannot carry one.

    ``closed_sender`` places the closed-sender door guard
    (:func:`~vultron.core.behaviors.sender_guard.closed_sender_door`) on
    ``case_id`` (else ``manager_case_id``), after the post-close guard: when
    the case records the sender's closure the tree stops there, with nothing
    committed or sent, and the handler asks
    :func:`~vultron.core.behaviors.sender_guard.closed_sender_turned_away`
    for the reason (CM-23-018).  Never run it as a tree of its own ahead of
    this one (CLP-10-005).

    A :class:`~vultron.core.behaviors.case.nodes.diversion_stage.Diversion`
    among ``precondition_guards`` becomes a
    :class:`~vultron.core.behaviors.case.nodes.diversion_stage.DiversionStage`
    at its place: when its read-only condition holds, its effects answer the
    delivery and the tree stops before the commit (CLP-10-063).  Where it may
    run is the tree's path declaration and nothing beside it (HP-01-038): in a
    tree that declares the manager path alone it runs at the CASE_MANAGER the
    path stage already established, and may commit its own entry; in a tree
    that also declares a non-manager path it is the receiver's own answer,
    writes no case state and its emits need a registered exemption.
    A diverted delivery has already been answered,
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

    Every tree whose sender guard names its sender and case (a
    :class:`~vultron.core.behaviors.sender_guard.SenderCheckContext` with a
    ``case_id``) answers the ledger position the received activity stamps,
    after the door guards and before anything judges the act
    (:func:`~vultron.core.behaviors.sync.ledger_position_stage.create_ledger_position_stage`,
    SYNC-18-004, SYNC-18-005, SYNC-18-007).  At the case's CASE_MANAGER a
    held position from an active participant is recorded and the entries
    after it replayed, and a split one is logged at ERROR and an active
    participant re-seeded; nothing it does changes the act's outcome.  A
    tree that answers the position itself names a registered
    ``ledger_position_exemption`` (``Read(CaseLedgerEntry)``, SYNC-17-005).

    The same trees judge the ``senderSequence`` the activity's sender
    numbers it with, next
    (:func:`~vultron.core.behaviors.sync.sender_sequence_stage.create_sender_sequence_stage`,
    SYNC-21-008): at the case's CASE_MANAGER an activity numbered past a gap
    is held, and a late, reused or missing number refused with a notice,
    before anything judges the act; every other activity goes on in its
    sender's order.  A tree whose activity takes no number names a
    registered ``sender_sequence_exemption`` (``Read(CaseLedgerEntry)``,
    SYNC-21-001).

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

        [door guards] → Intake
            → PreconditionGuardStage
                ├─ PreconditionGuards[*precondition_guards]
                └─ RefusalEffects → CaseManagerGate[*refusal_effects]
            → GuardedCommit → …

    Intake is one shared :class:`IntakeReceivedActivityNode` that records the
    received activity exactly as received, as its ``HELD`` record, and writes
    nothing else — in particular no core record from any object inlined in
    it, which an effect node writes from the event's copy after the guards
    (CLP-10-017).
    It runs right after the door guards, so a door's refusal writes nothing
    and a precondition guard's leaves the body for the refusal notice and
    the outcome stage (CLP-10-018, CLP-10-073).

    The sender guard is the last door, before intake and the caller's
    ``precondition_guards``.
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
    HP-01-025).  A tree has no way to pass a guard of its own; a sender
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
    gate resolves the case from the blackboard and skips without one), never
    reaches them on a resend, which the seen-before door answered, and keeps
    the tree's result the guard's
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
    the doors and intake still run.

    Set ``case_may_be_absent`` when the receiver legitimately holds no replica
    of the case yet — an invitee holds only the Invite's case stub
    (MV-10-004).
    The commit gate then skips at ``debug`` level for a case the receiver does
    not hold, instead of reporting it as an ADR-0087 Regime 1 anomaly.

    Args:
        name: Name for the root ``Sequence`` node.
        case_id: Case URI for the guarded-commit stage; ``None`` omits it.
        precondition_guards: Read-only guard nodes after the sender guard,
            and any diversions or path branches, in order.
        case_may_be_absent: Pass ``True`` when the receiver may not hold the
            case yet (e.g. an invitee seeing the first Invite).
        addressee_exemption: Why this tree carries no addressee door guard;
            ``None`` (the default) places it (HP-01-005).
        paths: The paths this message type handles, declared once
            (ADR-0153); ``None`` places no path stage.
        closed_sender: The sender whose recorded closure stops the tree, for
            a tree whose act may close its sender (CM-23-018).
        sender_rule: The use case's declared sender rule; the factory
            composes the guard from it (HP-01-025).
        sender_context: The sender and the records the rule's kinds are
            checked against; required with ``sender_rule``.  A
            :class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`
            reads the sender and the case from the received ledger activity
            at run time, for a tree with no ``case_id``.
        case_resolution: Read-only ``CaseResolving`` steps that resolve the
            case the sender guard reads, run just before it; requires
            ``sender_rule``.
        replica_effects: Ungated effects, run on every replica after the
            commit, and any path branches among them.
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
        ledger_position_exemption: Why this tree runs no answer to the
            stamped ledger position; ``None`` (the default) places it in a
            tree whose sender guard names a case (SYNC-18-007).
        sender_sequence_exemption: Why this tree judges no
            ``senderSequence``; ``None`` (the default) places the sender
            sequence stage in a tree whose sender guard names a case
            (SYNC-21-008).

    Raises:
        VultronWiringError: ``manager_effects`` has no ``manager_case_id``, a
            gate argument is passed without ``manager_effects``, an exemption
            is unregistered, an emit-capable node sits in ``replica_effects``
            without one (BT-17-008), or a refusal effect is not emit-capable or
            holds a state writer (CLP-10-048), or a
            ``refusal_notice_exemption`` is unregistered or exempts a tree
            that would send no notice (CLP-02-005), or an exempt tree passes a
            ``post_close_reply`` (CM-23-040), or the sender arguments are
            inconsistent: an ``addressee_exemption`` is not registered
            (HP-01-005), ``sender_rule`` without ``sender_context``, a
            ``sender_context`` without ``sender_rule``, or a
            ``sender_context`` naming another case than ``case_id`` (else
            ``manager_case_id``), or a ``closed_sender`` check on a tree
            with no case, or a ``case_resolution`` without ``sender_rule``
            or holding a node that is not a read-only ``CaseResolving`` step
            (HP-01-008), or a
            ``paths`` names no path (ADR-0153), or an ``OnPaths`` branch
            names no declared path, every declared path, or sits in a tree
            that declared none (HP-01-038), or a
            diversion is ill-formed (CLP-10-026), or ``clock_decisions`` name no
            case, come without a ``sender_rule`` or with a
            ``post_close_exemption``, or hold the received activity's commit
            (CLP-10-025), or a ``one_act_exemption`` is unregistered or
            exempts a tree that commits to no case (CLP-07-024), or a
            ``ledger_position_exemption`` is unregistered (SYNC-18-007).

    Per ``specs/case-ledger-processing.yaml`` CLP-02-005, CLP-05-001,
    CLP-07-015,
    CLP-10-006, CLP-10-010, CLP-10-017, CLP-10-022, CLP-10-025, CLP-10-026,
    ``specs/behavior-tree-integration.yaml``
    BT-17-008 and ``specs/case-management.yaml`` CM-23-013.
    """
    where = f"create_receive_activity_tree({name})"
    manager = manager_effects or []
    check_gate_arguments(
        name,
        gate_arguments_without_effects=not manager
        and (
            manager_case_id is not None
            or manager_gate_name is not None
            or manager_body_name is not None
            or manager_case_may_be_absent
        ),
    )

    # The doors, in the order of ADR-0154's questions: addressed to me?
    # seen before? which path? open to writes, and the sender entitled?
    # Each answer can end the run, and nothing is written before the last
    # of them (CLP-10-010).
    children: list[py_trees.behaviour.Behaviour] = list(
        addressee_stage(name, addressee_exemption)
    )
    if nested:
        check_nested(
            name,
            addressee_exemption=addressee_exemption,
            post_close_exemption=post_close_exemption,
            has_sender_rule=sender_rule is not None,
        )
    children.extend(seen_before_stage(name, nested=nested))
    stage_case_id = path_stage_case_id(
        case_id, manager_case_id, sender_context
    )
    path_stage = received_path_stage(
        name,
        stage_case_id,
        paths,
        case_resolved_at_run_time=bool(case_resolution),
        sender_rule=sender_rule,
    )
    if path_stage is not None:
        children.append(with_case_id(path_stage, stage_case_id))
    # Every path branch the tree declared, built from the stage's answer
    # before anything checks what the branches hold (HP-01-038).
    replica = resolve_path_branches(where, replica_effects or [], path_stage)
    check_replica_effects(name, replica, replica_emit_exemption)
    children.extend(
        post_close_stage(
            name,
            case_id or manager_case_id,
            post_close_exemption,
            post_close_reply or [],
        )
    )
    if closed_sender is not None:
        children.append(
            closed_sender_stage(
                name, case_id or manager_case_id, closed_sender
            )
        )
    guard = sender_guard_stage(
        name,
        case_id,
        manager_case_id,
        sender_rule,
        sender_context,
        path_stage,
    )
    children.extend(
        case_resolution_stage(
            name, case_resolution or [], sender_guarded=guard is not None
        )
    )
    if guard is not None:
        children.append(guard)
    door_guards = list(children)
    # Intake records the message only once every door has admitted it, so a
    # message a door turns away is never held in full (CLP-10-017,
    # CLP-10-018).
    # A nested tree's enclosing tree recorded the message (ADR-0154).
    children.extend([] if nested else [IntakeReceivedActivityNode()])
    if guard is not None:
        children.extend(
            ledger_position_stage(
                name, sender_context, ledger_position_exemption
            )
        )
        children.extend(
            sender_sequence_stage(
                name, sender_context, sender_sequence_exemption
            )
        )
    decisions = case_and_tree_decisions(
        case_id or manager_case_id,
        clock_decisions or [],
        sender_guarded=guard is not None,
        post_close_exemption=post_close_exemption,
    )
    if decisions:
        children.append(
            clock_decision_stage(
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
    guards = precondition_guard_nodes(
        name,
        precondition_guards,
        case_id or manager_case_id,
        path_stage,
    )
    if effects:
        children.append(
            refusal_stage(
                name,
                guards,
                effects,
                case_id,
                intake_ran=True,
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
            manager_stage(
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
        nested=nested,
    )


# The stage builders moved to ``receive_stages`` (CS-18-005); the public
# names stay importable from here.
__all__ = [
    "ReceivedActivityTree",
    "create_guarded_commit_case_ledger_entry_tree",
    "create_receive_activity_tree",
    "received_stages",
    "ungated_emitters",
    "ungated_nodes",
]
