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
"""What both continuations of ``owner-keep-case`` act on.

:class:`Part`, the shared budget, the Reporter's part and the CaseActor
lookup the approval and the handover both make
(:mod:`vultron.demo.helpers.owner_decision_story`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
)
from vultron.demo.helpers.polling import (
    LATE_JOINER_TIMEOUT,
    find_case_actor_participant_id,
)
from vultron.demo.utils import DataLayerClient

logger = logging.getLogger(__name__)


#: Seconds a wait of either continuation may take.  Both reach their actors
#: through the CaseActor — a suggestion forwarded to the owner and approved,
#: or a transfer offered, accepted and fanned out — so every wait queues
#: behind the same outbox and takes the late-joiner budget, the widest either
#: scenario carried before the step was shared.  A budget only bounds how long
#: a wait may take, so taking the wider one refuses nothing the narrower one
#: admitted and moves no byte of a recording (DEMOCI-11-018).
OWNER_DECISION_TIMEOUT = LATE_JOINER_TIMEOUT


@dataclass(frozen=True, slots=True)
class Part:
    """One cast member a shared continuation acts on.

    The ``(state, name, label)`` pair every shared fragment of a family takes,
    bundled because these continuations act on three members at once and three
    loose pairs of strings beside each other are trivially swappable.

    Attributes:
        name: The name the story seats the member under, the key
            :meth:`~vultron.demo.helpers.story.StoryState.actor` reads.
        label: What this scenario calls it in step and gate labels — ``"C1"``
            in the two-coordinator pair, ``"Vendor1"`` in the vendor-first
            one.
    """

    name: str
    label: str


#: The Reporter's part, which every scenario of the tree so far seats under
#: that name: the default witness of a handover, being neither the old nor the
#: new owner (:func:`the_owner_hands_the_case_over`).
REPORTER_PART = Part(REPORTER, REPORTER_LABEL)


def case_actor_participant(client: DataLayerClient, case_id: str) -> str:
    """The CaseActor's actor URI, read off *client*'s replica of *case_id*.

    Both continuations need it: the approval routes the owner's
    ``Accept(Offer(CaseParticipant))`` back to the CaseActor (CM-16-006), and
    the handover's invite checks that the Invite the newcomer received was
    emitted *as* the CaseActor (PCR-08-008).  Read from a replica rather than
    assumed, so the check names the actor that actually holds CASE_MANAGER on
    this case.

    Takes the client rather than the story's state, so it is a polling-style
    helper like the one it wraps and not a story fragment: a fragment owns its
    own demo context (DEMOCI-01-011), and this one raises into the caller's
    gate exactly as ``find_case_actor_participant_id`` does.

    Raises:
        AssertionError: When the replica's participant index names no
            CaseActor, so neither the Accept nor the sender check has an
            address.  Both callers read it inside a ``demo_gate``, which
            records the failure and skips the dependents.
    """
    case_actor_id = find_case_actor_participant_id(client, case_id)
    if case_actor_id is None:
        raise AssertionError(
            "the case replica read names no CaseActor participant, so there"
            " is no CASE_MANAGER address to route the Accept to"
        )
    logger.info("CaseActor participant ID: %s", case_actor_id)
    return case_actor_id
