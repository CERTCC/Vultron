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

"""Received-side ``Remove(EmbargoEvent)`` tree (protocol ET).

The type declares the manager and the participant-replica path, and the
factory branches each arm on the one answer the path stage gave (HP-01-038,
ADR-0153); a receiver that holds no replica of the case is refused there,
with the reason the stage composes (HP-01-039).  Each arm tears its own copy
down only when the embargo is in force, and only the CASE_MANAGER announces
(BT-17-008).  The package docstring draws the tree.
"""

import logging
from datetime import datetime

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.path_branch import OnPaths
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.admission_backfill_tree import (
    embargo_admission_backfill_nodes,
)
from vultron.core.behaviors.embargo.embargo_clock_decisions import (
    embargo_clock_decisions,
)
from vultron.core.behaviors.embargo.nodes import (
    AdoptRemovedEmbargoRevisionNode,
    AwaitsEmbargoEndingNoticeNode,
    ClearActiveEmbargoNode,
    HasEmbargoActiveNode,
    IsActiveEmbargoNode,
    SendAnnounceEmbargoEventNode,
    TerminationCauseIsAdmissibleNode,
    TerminationIsTimelyNode,
    ValidateCaseExistsNode,
    embargo_ending_notice_nodes,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderRule,
)
from vultron.core.behaviors.sender_guard import embargo_sender_context
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationCause,
)
from vultron.core.states.embargo_register import TerminationReason

logger = logging.getLogger(__name__)


def _teardown_if_active(
    case_id: str,
    embargo_id: str,
    termination: EmbargoTermination,
    terminated_at: datetime | None,
    *after_teardown: py_trees.behaviour.Behaviour,
    prefix: str = "",
    before_teardown: tuple[py_trees.behaviour.Behaviour, ...] = (),
) -> py_trees.composites.Selector:
    """Tear the active embargo down, then run *after_teardown*; skip if not active.

    Only the two "nothing to tear down" guards fall back: the embargo is not
    the active one, or the EM state is already EXITED.  A teardown step that
    fails fails the Selector, so the handler can report it instead of
    mistaking it for "was not active" (#2255).  The guards cannot be repeated
    after the teardown, which is why each role's arm builds the whole branch.

    *before_teardown* runs inside the active branch ahead of the clear, for a
    reading the write destroys — the CM-31-009 capture of the embargo in
    force (``CaptureActiveEmbargoNode``).
    """
    return py_trees.composites.Selector(
        name=f"{prefix}TeardownIfActive",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="EmbargoWasNotActive",
                child=IsActiveEmbargoNode(
                    case_id=case_id, embargo_id=embargo_id
                ),
            ),
            py_trees.decorators.Inverter(
                name="EmbargoAlreadyExited",
                child=HasEmbargoActiveNode(case_id=case_id),
            ),
            py_trees.composites.Sequence(
                name=f"{prefix}ActiveTeardown",
                memory=False,
                children=[
                    *before_teardown,
                    ClearActiveEmbargoNode(
                        case_id=case_id,
                        embargo_id=embargo_id,
                        termination=termination,
                        terminated_at=terminated_at,
                    ),
                    *after_teardown,
                ],
            ),
        ],
    )


def remove_embargo_from_case_tree(
    case_id: str,
    embargo_id: str,
    sender_actor_id: str,
    termination_reason: TerminationReason,
    terminated_at: datetime | None,
    actor_config: ActorConfig | None = None,
    *,
    sender_rule: SenderRule,
    termination_cause: TerminationCause | None = None,
    embargo: EmbargoEvent | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for receiver-side embargo removal (protocol ET).

    Handles receipt of a ``Remove(EmbargoEvent)`` activity.  If the embargo
    is the active one, its register entry is terminated and every open
    proposal cancelled in one step, so EM derives ``EXITED`` (ADR-0122); no
    participant consent is written, since with no embargo in force nobody is
    bound (ADR-0118).  A ``Remove`` naming an embargo that is not in force
    changes nothing: the register cancels a proposal only with a
    termination or on a threat signal.  The one exception is a paused
    signatory's replica, where a ``Remove`` naming a revision it has not
    activated means that revision replaced the replica's embargo (its
    ``Announce`` notice is late, or none was owed for a longer revision):
    the replica activates the revision, then tears it down (SYNC-19-001,
    CM-31-042).
    Always commits a canonical ledger entry when the executing actor holds
    the ``CASE_MANAGER`` role (via the guarded commit subtree).

    The teardown runs in one of two mutually exclusive declared path
    branches (HP-01-038).  The
    CASE_MANAGER's arm, in ``manager_effects``, tears down the canonical
    case, announces the teardown to every other active participant and
    backfills any participant the end of the embargo admits (CM-10-006),
    re-issuing any outstanding stub Invite that carries the old terms
    (CM-11-016).
    A participant replica's arm is an ``OnPaths.off_case_manager``
    declaration among ``replica_effects``; it tears down
    its own copy and sends nothing: the teardown is the CASE_MANAGER's act, so
    re-announcing it would speak for another actor (BT-17-008).  Each arm
    skips when there is nothing to tear down, and a failed teardown step
    fails the tree (#2255).

    BT returns SUCCESS when the outer Sequence completes (including when no
    teardown was needed).  BT returns FAILURE when the case is not found or a
    teardown step fails.

    Args:
        case_id: ID of the VulnerabilityCase to update.
        embargo_id: ID of the EmbargoEvent being removed.
        sender_actor_id: Sender of the ``Remove``; the Case Owner (or the
            CASE_MANAGER) at the CASE_MANAGER, the CASE_MANAGER elsewhere
            (ADR-0115, EP-09-005, PCR-03-001).
        termination_reason: The what the ``Remove`` carries in ``content``,
            recorded on the ``TERMINATED`` entry (ADR-0122).
        termination_cause: The why the ``Remove`` carries as
            ``terminationCause``, or ``None`` when it names none; recorded on
            the ``TERMINATED`` entry as given (EMB-13-005).  A
            ``THREAT_SIGNAL`` cause from anyone but the CASE_MANAGER is
            refused before the commit (``TerminationCauseIsAdmissibleNode``).
        terminated_at: The ``Remove``'s ``published`` time.  An
            ``END_TIME_REACHED`` claimed before the embargo's end time is
            refused before the commit (``TerminationIsTimelyNode``).
        actor_config: The CASE_MANAGER's configuration; its RSVP windows set
            the deadline of a re-issued stub Invite.  ``None`` applies the
            ``ActorConfig`` defaults.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).
        embargo: The ``EmbargoEvent`` the ``Remove`` carries inline, or
            ``None``; a paused replica stores it when it activates a
            revision it has not seen (EMB-18-003).

    Returns:
        Root node of the ``RemoveEmbargoFromCaseBT`` Sequence.
    """
    # The Case Owner asked for the teardown, so the notices credit it
    # (CM-24-002); the CASE_MANAGER's own Remove credits nobody else.  Both
    # run only in the CASE_MANAGER arm: a replica sends no notice.
    capture, notices = embargo_ending_notice_nodes(
        case_id, requested_by=sender_actor_id
    )
    # The Remove carries the what and, when its sender names one, the why
    # (EMB-13-005); the TERMINATED entry records both as given.
    termination = EmbargoTermination.from_reason(
        termination_reason, termination_cause
    )
    root = create_receive_activity_tree(
        name="RemoveEmbargoFromCaseBT",
        case_id=case_id,
        # The teardown does protocol work on both paths, so the type declares
        # a branch for each (HP-01-038, ADR-0153): the CASE_MANAGER tears the
        # canonical case down and announces it, a participant replica tears
        # its own copy down when the ledger no longer reaches it.  A store
        # that holds no replica of the case is refused at the path stage.
        paths={ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
        sender_rule=sender_rule,
        sender_context=embargo_sender_context(sender_actor_id, case_id),
        # Every overdue invitation expires first (CM-28-028).
        clock_decisions=embargo_clock_decisions(case_id),
        precondition_guards=[
            ValidateCaseExistsNode(case_id=case_id),
            # A threat signal arrives as a case status update, never on a
            # case owner's Remove (EMB-13-005).
            TerminationCauseIsAdmissibleNode(
                case_id=case_id,
                sender_actor_id=sender_actor_id,
                termination=termination,
            ),
            TerminationIsTimelyNode(
                case_id=case_id,
                termination=termination,
                terminated_at=terminated_at,
                embargo_id=embargo_id,
            ),
        ],
        # RSH-08-003/CM-31-010: an active replica takes the teardown from the
        # ledger (EmbargoTeardown slot), so it writes nothing here (#3814).
        # The one exception is a signatory the ledger no longer reaches — a
        # replica removed, withheld, or at RM ``CLOSED`` — for which the
        # CASE_MANAGER's direct ``Remove(EmbargoEvent)`` is the only channel;
        # that paused replica, and only it, applies its own teardown through
        # the one apply function (CM-31-010, ADR-0124), gated by
        # ``AwaitsEmbargoEndingNoticeNode``.  It tears down only and sends
        # nothing, so it carries no capture/notice.
        replica_effects=[
            OnPaths.off_case_manager(
                "TeardownOnReplica",
                py_trees.composites.Selector(
                    name="ReplicaTeardownIfEndingNoticeAwaited",
                    memory=False,
                    children=[
                        py_trees.decorators.Inverter(
                            name="SkipUnlessEndingNoticeAwaited",
                            child=AwaitsEmbargoEndingNoticeNode(
                                case_id=case_id
                            ),
                        ),
                        py_trees.composites.Sequence(
                            name="ReplicaApplyEndingNotice",
                            memory=False,
                            children=[
                                # The CASE_MANAGER terminates only the
                                # embargo in force, so a named revision this
                                # replica has not activated replaced its
                                # embargo (a late Announce, or none owed for
                                # a longer revision): activate it first, so
                                # either order ends the same (SYNC-19-001,
                                # SYNC-19-003, CM-31-042).
                                AdoptRemovedEmbargoRevisionNode(
                                    case_id=case_id,
                                    embargo_id=embargo_id,
                                    embargo=embargo,
                                ),
                                _teardown_if_active(
                                    case_id,
                                    embargo_id,
                                    termination,
                                    terminated_at,
                                    prefix="Replica",
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        ],
        # The CASE_MANAGER arm captures the embargo in force ahead of the
        # clear, then announces the teardown, sends the CM-31-009 ending
        # notices to the signatories the ledger no longer reaches, and
        # backfills what the end of the embargo admits (CM-10-006, CM-11-016).
        manager_effects=[
            _teardown_if_active(
                case_id,
                embargo_id,
                termination,
                terminated_at,
                SendAnnounceEmbargoEventNode(
                    case_id=case_id, embargo_id=embargo_id
                ),
                notices,
                *embargo_admission_backfill_nodes(case_id, actor_config),
                before_teardown=(capture,),
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="TeardownAndAnnounceIfCaseManager",
    )
    logger.info(
        "Created RemoveEmbargoFromCaseBT for case=%s embargo=%s",
        case_id,
        embargo_id,
    )
    return root
