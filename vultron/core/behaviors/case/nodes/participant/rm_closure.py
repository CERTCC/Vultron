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

from vultron.core.behaviors.case.nodes.participant.common import (
    report_unshaped_status,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
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

    A failed step stops the walk.  The steps already written stay: each is a
    legal transition on its own, and a retry continues the path from the state
    the actor has reached.

    The closing actor is an argument of :meth:`close`, not of the writer, so
    one writer serves every actor its owner closes (the ledger fan-out closes
    whichever actor each entry names) and no call inherits the previous
    call's actor.
    """

    def __init__(self, name: str) -> None:
        """Pre-build one status writer for every state a closure path writes.

        Args:
            name: Prefix for the writer node names.
        """
        self._writers: dict[RM, CreateParticipantStatusNode] = {
            rung: CreateParticipantStatusNode(
                actor_id="",
                rm_state=rung,
                vf_state=None,
                d_state=None,
                pxa_state=None,
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

        Returns:
            ``SUCCESS`` once the participant is at ``RM.CLOSED`` (at once when
            it already is); ``FAILURE`` when its RM state cannot be read or a
            step is refused.
        """
        from vultron.core.behaviors.bridge import BTBridge

        try:
            current_rm, _, _ = resolve_participant_state_from_dl(
                datalayer, participant_id
            )
        except VultronValidationError as exc:
            return report_unshaped_status(node, participant_id, exc)

        for rung in rm_closure_path(current_rm):
            writer = self._writers[rung]
            writer._actor_id = actor_id
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
                node.logger.warning(f"{node.name}: {node.feedback_message}")
                return Status.FAILURE
            current_rm = rung
        return Status.SUCCESS
