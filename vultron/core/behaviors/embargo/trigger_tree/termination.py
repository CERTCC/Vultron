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

"""Trigger trees that terminate an embargo or abandon proposed terms.

Covers the voluntary and threat-signal termination (EMB-19-001), the
termination of an embargo that outlives disclosure (EMB-04-002), and the
abandonment of proposed terms once P/X/A is set (EMB-16-002).
"""

from datetime import datetime

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.embargo.nodes import (
    AbandonEmbargoProposalsLifecycleNode,
    CommitAndApplyEmbargoTerminationNode,
    EmbargoActivityBuilder,
    EmbargoOutlivesDisclosureNode,
    HasActiveEmbargoNode,
    IsProposedEmbargoNode,
    LeaveAbandonmentToCaseManagerNode,
    ReadEmbargoIdNode,
    ReadEmStateNode,
    ReadOpenEmbargoProposalsNode,
    ask_case_manager_to_terminate_once,
    embargo_ending_notice_nodes,
)
from vultron.core.behaviors.embargo.nodes.chosen_cause import (
    ChosenTermination,
)
from vultron.core.behaviors.embargo.trigger_tree._arms import (
    ABANDONMENT_LEFT_TO_CASE_MANAGER,
    _asserting,
    _by_role,
    _make_emit_node,
)
from vultron.core.behaviors.sender.nodes import (
    ConstructActivitiesNode,
    QueueToOutboxNode,
    ResolveCaseManagerNode,
)
from vultron.core.models.embargo_termination import (
    TerminationRequest,
    ThreatSignalTermination,
)


def reject_proposed_embargo_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
) -> py_trees.behaviour.Behaviour:
    """Shared BT for abandoning the open embargo proposals (EMB-16-001).

    Used through ``pxa_embargo_teardown_bt`` (``ThreatTerminationBranchNode``)
    when CS.P/X/A fires while the case EM state is PROPOSED: no proposal can be accepted any more
    (EMB-02-002), so every open one is abandoned.  Mirrors the routing-guard
    ordering of :func:`terminate_embargo_bt`:

    1. ``ReadEmStateNode`` / ``IsProposedEmbargoNode`` — EM must be PROPOSED.
    2. ``ResolveCaseManagerNode`` — routing guard; FAILURE = no state change.
    3. As the CASE_MANAGER (EP-09-008): ``ReadOpenEmbargoProposalsNode``
       maps each open proposal to the readable Invite that proposed it
       (FAILURE before anything moves when one has none),
       ``AbandonEmbargoProposalsLifecycleNode`` then, per proposal, commits
       its ``Reject`` of the proposal it received, or its ``Undo`` of the
       one it sent itself, which carries the ``CANCEL``, then its ``Undo``
       of each Invite it relayed for the proposal (ADR-0152), each
       addressed to nobody (CLP-10-001) and replayed by the replica's
       abandonment slots (EP-09-007), and only then cancels that proposal,
       so EM reaches ``NONE`` with the last one (CLP-07-013); then the
       ``Add(CaseStatus)`` declaration.
    4. As any other participant: no EM write and no ask (EMB-16-002,
       #4148).  The manager has the P/X/A signal from the status
       declaration and abandons on its own detection; a ``Reject`` sent on
       the case's behalf would read as this participant's DECLINE.  A
       proposal, Invite or revision the participant *receives* while the
       case is at P/X/A is a different matter: it answers that with its
       own ``Reject`` of the Invite (EMB-01-002) on the received path, not here.
    """
    return py_trees.composites.Sequence(
        name="RejectProposedEmbargoBT",
        memory=True,
        children=[
            ReadEmStateNode(case_id=case_id, result_out=result_out),
            IsProposedEmbargoNode(case_id=case_id, result_out=result_out),
            ResolveCaseManagerNode(case_id=case_id),
            *_by_role(
                "AbandonProposedEmbargo",
                case_id,
                as_case_manager=[
                    ReadOpenEmbargoProposalsNode(case_id=case_id),
                    AbandonEmbargoProposalsLifecycleNode(
                        case_id=case_id, result_out=result_out
                    ),
                    _make_emit_node(case_id),
                ],
                otherwise=[LeaveAbandonmentToCaseManagerNode(case_id=case_id)],
                otherwise_suffix=ABANDONMENT_LEFT_TO_CASE_MANAGER,
            ),
        ],
    )


def terminate_embargo_bt(
    *,
    case_id: str,
    result_out: dict[str, object],
    termination: TerminationRequest | ChosenTermination,
    activity_builder: EmbargoActivityBuilder | None = None,
    requested_by: str | None = None,
    actor_config: ActorConfig | None = None,
    terminated_at: datetime | None = None,
) -> py_trees.behaviour.Behaviour:
    """Shared BT for terminating the active embargo (BT-19-001, EP-09-008).

    *termination* is how the embargo ends (ADR-0122): ``EARLY`` with the
    cause the requester names, or none, for a participant's own decision;
    :class:`ThreatSignalTermination` for the CS ``P``/``X``/``A`` cascades
    (``EARLY``, caused by the signals the case carries at the write);
    :class:`ChosenTermination` for an actor's voluntary termination, whose
    reason call-out chose the cause earlier in the same run (EMB-14-001); and
    ``END_TIME_REACHED``, with no cause, for the end-time paths, claimed at
    *terminated_at* and refused before the embargo's end time.  The
    CASE_MANAGER's ``Remove`` carries the what in ``content`` and the cause
    its ``TERMINATED`` entry records as ``terminationCause`` (EMB-13-005).
    A participant's ask carries the what and any cause it may name
    (``participant_cause``): only the CASE_MANAGER may name a
    ``THREAT_SIGNAL`` cause, and it learns the signals from the case status
    update instead.

    Satisfies the routing-gated state-mutation ordering:

    1. ``HasActiveEmbargoNode`` / ``ReadEmbargoIdNode`` — read embargo_id
       from the case; FAILURE if absent.
    2. ``ResolveCaseManagerNode`` — routing guard; FAILURE = no state change.
    3. As the CASE_MANAGER: ``CommitAndApplyEmbargoTerminationNode`` decides
       the ``TERMINATE`` step, commits the ``Remove(EmbargoEvent)`` that
       carries it as the canonical entry the ``EmbargoTeardown`` slot copies,
       addressed to every other participant and never to the manager
       (EMB-19-001, CLP-10-001, #4112), and only then applies the step
       through the one apply function (ADR-0124), so a failed commit writes
       nothing; then the ``Add(CaseStatus)`` declaration, then a direct
       ``Remove(EmbargoEvent)`` to each bound signatory the ledger no longer
       reaches (CM-31-009), crediting *requested_by* when another actor
       asked for the end.
    4. As any other participant: no EM write; the ``Remove`` is queued to the
       CASE_MANAGER as a request (PCR-08-001) and recorded as a pending
       assertion keyed by the ended embargo (EP-09-008, SYNC-11-002) — by
       the use case on the trigger path, by the ask subtree on the cascades.

    With ``activity_builder`` (the trigger path) the use case builds the
    activity; with ``None`` (the CS.P/X/A and threat cascades) the nodes read
    ``/embargo_id`` and the factory from the blackboard.  Every path MUST use
    this factory so routing prerequisites are verified before the DataLayer
    state change is committed (BT-19-002).

    *actor_config* sets the RSVP window of the stub Invites the CASE_MANAGER
    re-issues once the embargo ends; ``None`` applies the ``ActorConfig``
    defaults.
    """
    if activity_builder is not None:
        ask: py_trees.behaviour.Behaviour = py_trees.composites.Sequence(
            name="QueueToCaseManager",
            memory=False,
            children=[
                ConstructActivitiesNode(
                    activity_builder=_asserting(activity_builder, result_out)
                ),
                QueueToOutboxNode(),
            ],
        )
    else:
        # The ask carries the what and any cause a participant may name.  A
        # threat-signal termination is EARLY and its ask names no cause: a
        # THREAT_SIGNAL cause from anyone but the CASE_MANAGER is refused
        # (EMB-13-005).
        ask = ask_case_manager_to_terminate_once(
            case_id,
            termination.reason,
            termination
            if isinstance(termination, ChosenTermination)
            else termination.participant_cause,
            # The end-time paths hold this act's instant and pass it as
            # *terminated_at*; the cascades hold none and the ask subtree
            # reads one as it is built (#5591, #5650).
            at=terminated_at,
        )
    capture, notices = embargo_ending_notice_nodes(
        case_id, requested_by=requested_by
    )

    return py_trees.composites.Sequence(
        name="TerminateEmbargoBT",
        memory=True,
        children=[
            HasActiveEmbargoNode(case_id=case_id, result_out=result_out),
            ReadEmbargoIdNode(case_id=case_id),
            ResolveCaseManagerNode(case_id=case_id),
            *_by_role(
                "TerminateEmbargo",
                case_id,
                as_case_manager=[
                    capture,
                    # Decide, commit the Remove, then apply it (ADR-0124).
                    CommitAndApplyEmbargoTerminationNode(
                        case_id=case_id,
                        result_out=result_out,
                        termination=termination,
                        terminated_at=terminated_at,
                        builder=activity_builder,
                    ),
                    _make_emit_node(case_id),
                    notices,
                    # Termination changes the terms of every stub Invite still
                    # outstanding (CM-11-016).
                    ReissueStubInvitesNode(
                        case_id=case_id, actor_config=actor_config
                    ),
                ],
                otherwise=[ask],
            ),
        ],
    )


def end_embargo_outliving_disclosure_bt(
    *,
    case_id: str,
    otherwise: list[py_trees.behaviour.Behaviour],
    requested_by: str | None = None,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """After the owner's ``REJECT``, end an embargo that outlived disclosure.

    The owner's rejection of the last open revision while CS is public,
    exploited or attacked returns the case to the prior terms, which no act
    may end in (EMB-04-002).  The CASE_MANAGER records the ``REJECT`` step
    as decided and then, in the same act, terminates the embargo through
    the shared :func:`terminate_embargo_bt` (BT-19-002), with the threat
    signals the case carries as the cause its ``Remove`` carries
    (EMB-13-005), so the revision ends ``REJECTED`` and the embargo
    ``TERMINATED`` as two entries a replica copies in order (MSM-07-032).
    Any other rejection runs *otherwise*.

    The arms are exclusive on the case state the ``REJECT`` left, so a
    failed termination is never answered by *otherwise*: it fails this node,
    and the enclosing act keeps none of its writes (ADR-0146, ADR-0151).
    The tree runs behind the CASE_MANAGER gate, so the ask arm inside
    ``terminate_embargo_bt`` never runs here.  *requested_by* is credited
    on the ending notices (CM-31-009).
    """
    return py_trees.composites.Selector(
        name="EndEmbargoOutlivingDisclosure",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="TerminateOutlivingEmbargo",
                memory=False,
                children=[
                    EmbargoOutlivesDisclosureNode(case_id=case_id),
                    terminate_embargo_bt(
                        case_id=case_id,
                        result_out={},
                        requested_by=requested_by,
                        termination=ThreatSignalTermination(),
                        actor_config=actor_config,
                    ),
                ],
            ),
            py_trees.composites.Sequence(
                name="PriorTermsAllowed",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="UnlessOutlivingDisclosure",
                        child=EmbargoOutlivesDisclosureNode(
                            case_id=case_id,
                            name="CheckEmbargoOutlivesDisclosure",
                        ),
                    ),
                    *otherwise,
                ],
            ),
        ],
    )
