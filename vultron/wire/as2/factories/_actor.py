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

"""How a factory carries an actor it is handed (AKM-05-005, ADR-0159).

A factory that names an actor in an activity is given either the actor's
profile as the sender holds it, or only the actor's URI.  The profile travels
as held; a URI travels as an actor reference, an inline object with exactly
an ``id`` and a ``type``.  Neither path adds a value the sender does not know
(AKM-02-006).
"""

from vultron.core.models.actor import CoreActor
from vultron.wire.as2.vocab.base.objects.actors import (
    actor_reference,
    as_Actor,
)


def carried_actor(actor: as_Actor | CoreActor | str) -> as_Actor | CoreActor:
    """Return *actor* as an activity carries it inline.

    A held profile (a wire actor, or the core record the sender's store
    holds) is returned unchanged, so it travels as held; an actor URI becomes
    its :func:`actor_reference`.  So does a record of the abstract
    ``CoreActor`` class, the minimal peer recorded when only the URI was
    known: its type names no wire actor a receiver could route by, so it
    holds nothing more than the URI.
    """
    if isinstance(actor, str):
        return actor_reference(actor)
    if type(actor) is CoreActor:
        return actor_reference(actor.id_)
    return actor
