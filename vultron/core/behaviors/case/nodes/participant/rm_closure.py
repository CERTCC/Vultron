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

"""Write an RM closure as ordinary RM transitions (RMB-14-005, CM-23-012).

A ``Leave(VulnerabilityCase)`` closes the leaving actor's RM state from
whatever rung it holds.  The RM transition function has a close edge from
*Received*, *Invalid*, *Accepted* and *Deferred*, but not from *Valid*
(VP-02-004), so a closure from *Valid* is two transitions, ``V → D → C``.
:func:`~vultron.core.states.rm.rm_closure_path` names the transitions;
:class:`RMClosureWriter` writes them, one ``ParticipantStatus`` per step,
through the sole status writer with RM adjacency validation in force.  No
closure path overrides the transition table (ADR-0114).
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant.common import (
    report_unshaped_status,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.rm import RM, RM_CLOSURE_RUNGS, rm_closure_path
from vultron.errors import VultronValidationError


class RMClosureWriter:
    """Advance one actor's RM state to ``RM.CLOSED`` by ordinary transitions.

    Owned by a closure node, which builds it in its own ``__init__`` so the
    status writers are pre-built rather than constructed in ``update()``
    (BTND-10-004).  :meth:`close` reads the actor's current RM state, then runs
    the writer for each state on :func:`~vultron.core.states.rm.rm_closure_path`
    through ``BTBridge.execute_with_setup`` (ADR-0089).  Every write keeps the
    full rule set of the shared evaluator, RM adjacency included (BTND-10-002,
    RMB-15-001).

    A failed step stops the walk and fails the act, which keeps none of the
    steps already written, so the store never holds a step the ledger lacks
    (CLP-07-013, CLP-07-015).

    The closing actor is an argument of :meth:`close`, not of the writer, so
    one writer serves every actor its owner closes and no call inherits the
    previous call's actor.

    Only the CASE_MANAGER walks a closure path (CM-23-001, CM-23-016).  A
    replica never builds one of these: the path starts from the writer's own
    stored RM state, so a replica holding an older status for the actor would
    write a step no ledger entry backs (#4091).  The CASE_MANAGER commits each
    status this writer reports through ``steps_out`` as its own ledger entry,
    and a replica applies those entries (``CommitRMClosureEntriesNode``).
    """

    def __init__(self, name: str) -> None:
        """Pre-build one status writer for every state a closure path writes.

        Args:
            name: Prefix for the writer node names.
        """
        # One result dict per writer: each run reports the id of the status
        # it wrote there, which close() hands to the caller in path order.
        self._results: dict[RM, dict[str, object]] = {
            rung: {} for rung in RM_CLOSURE_RUNGS
        }
        self._writers: dict[RM, CreateParticipantStatusNode] = {
            rung: CreateParticipantStatusNode(
                actor_id="",
                rm_state=rung,
                vf_state=None,
                d_state=None,
                pxa_state=None,
                result_out=self._results[rung],
                name=f"{name}.CreateParticipantStatus.{rung.name}",
            )
            for rung in RM_CLOSURE_RUNGS
        }

    def close(
        self,
        node: py_trees.behaviour.Behaviour,
        datalayer: CasePersistence,
        participant_id: str,
        case_id: str,
        actor_id: str,
        steps_out: list[str],
    ) -> Status:
        """Write the closure path from the participant's current RM state.

        A participant whose latest status is not core-shaped has no readable
        RM state (ARCH-15-001).  That is reported on *node* as ``FAILURE``,
        the way :func:`~vultron.core.behaviors.case.nodes.participant.common\
        .resolve_transition_context_or_report` reports it, because a BT node
        cannot let the exception escape ``update()``.

        Args:
            node: The closure node calling this; failures are reported on its
                ``feedback_message``, and a refused step is logged on its
                logger.
            datalayer: The store holding the case and the participant record.
            participant_id: The participant record of the closing actor.
            case_id: The case the participant belongs to.
            actor_id: The closing actor; every write is attributed to it.
            steps_out: Receives the id of each status written, in path order,
                so the caller can commit one ledger entry per step (CM-23-001).
                A step written before a refused one stays in it.

        Returns:
            ``SUCCESS`` once the participant is at ``RM.CLOSED`` (at once when
            it already is); ``FAILURE`` when its RM state cannot be read or a
            step is refused.
        """
        try:
            current_rm, _, _ = resolve_participant_state_from_dl(
                datalayer, participant_id
            )
        except VultronValidationError as exc:
            return report_unshaped_status(node, participant_id, exc)

        for rung in rm_closure_path(current_rm):
            writer = self._writers[rung]
            writer._actor_id = actor_id
            result_out = self._results[rung]
            result_out.clear()
            # Run as the DataLayer's own actor so BTBridge does not clone an
            # empty store for the closing actor.  The write is attributed to
            # the closing actor through the writer's actor id (ADR-0089).
            result = BTBridge(datalayer=datalayer).execute_with_setup(
                tree=writer,
                actor_id=datalayer.actor_id,
                case_id=case_id,
            )
            if result.status != Status.SUCCESS:
                node.feedback_message = (
                    f"RM {current_rm.name} -> {rung.name} refused for"
                    f" participant '{participant_id}': {writer.feedback_message}"
                )
                log = node_logger(node)
                log.warning("%s: %s", node.name, node.feedback_message)
                return Status.FAILURE
            status_id = result_out.get("status_id")
            if not isinstance(status_id, str):
                # A write the caller cannot name is a step no ledger entry
                # will record (CM-23-001): report it, never drop it silently.
                node.feedback_message = (
                    f"RM {current_rm.name} -> {rung.name} for participant"
                    f" '{participant_id}' reported no status id"
                )
                node_logger(node).warning(
                    "%s: %s", node.name, node.feedback_message
                )
                return Status.FAILURE
            steps_out.append(status_id)
            current_rm = rung
        return Status.SUCCESS
