"""The :class:`ActorSession` that combines every trigger verb family."""

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

from dataclasses import dataclass

from vultron.demo.actor_session.case_triggers import CaseTriggers
from vultron.demo.actor_session.progress_triggers import ProgressTriggers


@dataclass(frozen=True)
class ActorSession(CaseTriggers, ProgressTriggers):
    """A frozen ``(client, actor, case?)`` binding for demo trigger calls.

    Args:
        client: Client connected to the container that hosts *actor*.
        actor: The actor on whose behalf triggers are posted.
        case_id: The ID of the case trigger verbs operate on.  ``None`` at
            construction; set a copy with :meth:`with_case` once the case
            exists.  Only the ID is kept: a trigger names its case by ID, so a
            caller holding just the ID need not build a case to bind it.
        narrate: When ``True`` (default), each verb logs an INFO banner naming
            the action and actor.  :meth:`quiet` returns a silent copy for calls
            that already sit inside a scenario ``demo_step`` banner.
    """
