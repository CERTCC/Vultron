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

"""The one marker every emit-capable BT node carries (BT-17-008).

A node is *emit-capable* when its ``update()`` can put an activity in the
executing actor's outbox: the ``_EmitSingleActivityBase`` family, the embargo
send and relay nodes, the case-update broadcast, ``QueueToOutboxNode`` and
``UpdateActorOutbox``, and the few hand-rolled emitters that call the outbox
seam themselves.

``create_receive_activity_tree`` refuses a marked node among a received tree's
``replica_effects``, outside any CASE_MANAGER gate, unless the tree names a
:class:`~vultron.core.behaviors.replica_emit_exemptions.ReplicaEmitExemption`
that covers it, so an emit cannot run on every replica by omission.
``test/architecture/test_received_tree_case_manager_gate.py`` checks that every
class reaching the outbox seam carries the marker.
"""

__all__ = ["EmitCapable"]


class EmitCapable:
    """Marker mixin: this node can enqueue an outbound activity (BT-17-008).

    Carries no behaviour.  Mix it into the node class (or its domain base) so
    an ``isinstance`` check finds every emitter, however it reaches the outbox.
    """
