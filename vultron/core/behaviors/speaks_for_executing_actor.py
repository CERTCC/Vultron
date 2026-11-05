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

"""The marker a leaf guard carries when it is BT-17-008's second arm.

BT-17-008 gives a received tree's emit two guards to choose from: the
CASE_MANAGER gate, or a check that the executing actor *is* the actor the
emit speaks for.  The factory's walk
(:func:`~vultron.core.behaviors.case.receive_stages.effects.ungated_emitters`)
reads the first from the shape of the tree — a
:class:`~vultron.core.behaviors.case.nodes.role_gates.CaseManagerGate`, or a
manager-only :class:`~vultron.core.behaviors.case.nodes.path_branch.PathBranch`
— but it cannot read the second from a shape, because any leaf might be the
check.  This marker is how a leaf says it is.

A node carries it when its ``update()`` admits the executing actor alone:
it compares the blackboard ``actor_id`` with the one actor the message
names as the author of the answer (the Invite's invitee, the role Offer's
target), and ``FAILURE`` means "this is not that actor, so nothing is sent
from here".  A node that checks anything *else* about the receiver — that it
holds the case, that it holds a role, that a port is wired — does not carry
it: those say nothing about whom the emit would speak for, and #2667 is the
case in point, where a sender check was mistaken for one.

Two placements bound an emit, matching the two ways a behaviour tree makes
one node decide whether later ones run:

- a guard in a ``Sequence``, ahead of the emit — the emit runs only if the
  guard succeeded;
- the inverted first arm of a ``Selector`` — the later arms run only if the
  guard succeeded, which is the shape the CASE_MANAGER gate also uses.

An emit so bounded needs no
:class:`~vultron.core.behaviors.replica_emit_exemptions.ReplicaEmitExemption`:
the tree already states what the exemption would have recorded, and a
recorded waiver of a requirement the tree meets is a waiver of nothing
(ARCH-18-002).  ``test/core/behaviors/case/test_speaks_for_executing_actor.py``
pins both placements and the shapes that are *not* the second arm.
"""

__all__ = ["SpeaksForExecutingActor"]


class SpeaksForExecutingActor:
    """Marker mixin: this leaf admits the actor an emit speaks for (BT-17-008).

    Carries no behaviour.  Mix it into a condition node whose ``update()``
    succeeds only when the executing actor is the one actor the message makes
    the author of the answer, so the factory's walk can tell the emit behind
    it is already guarded.
    """
