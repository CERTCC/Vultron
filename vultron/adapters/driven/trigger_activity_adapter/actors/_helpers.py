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


"""Store reads the actor-domain trigger activity mixins share."""

from typing import Any

from vultron.adapters.received_archive import (
    read_received_as_received,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import (
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor


def _active_embargo_of(
    dl: CaseOutboxPersistence, case: VulnerabilityCase
) -> Any:
    """The case's active embargo as an object, whichever shape the field holds.

    ``active_embargo`` is id-or-object: a case seeded from a sealed Announce
    carries the ``EmbargoEvent`` inline (it is in the case's
    ``inline_required_refs``), a locally built one holds the id.  Only the id
    needs a store read.
    """
    active_embargo = case.active_embargo
    if isinstance(active_embargo, str):
        return dl.read(active_embargo)
    return active_embargo


def _held_actor(
    dl: CaseOutboxPersistence, actor_id: str
) -> as_Actor | CoreActor | str:
    """The actor *actor_id* as this sender holds it, else its URI.

    The factory carries a held profile as held and a URI as an actor
    reference (``carried_actor``, AKM-05-005, AKM-05-017,
    ADR-0159).
    """
    held = dl.read(actor_id)
    if isinstance(held, (as_Actor, CoreActor)):
        return held
    return actor_id


def _stored_case_invite(
    dl: CaseOutboxPersistence, invite_id: str
) -> as_Invite:
    """Read the received Invite as this invitee holds it, stub and all.

    The Invite is parsed from the body intake archived on arrival
    (:func:`read_received_as_received`), since the inbox never holds a stub
    Invite back for its case (PCR-06-005).  The parse resolves the inline
    stub to its own class, and the reply factory checks that it is a case
    Invite.  The Accept or Reject embeds the Invite as received, so its
    ``target`` stays the case stub (VAM-04-005, VAM-04-006): the CASE_MANAGER
    reads the case from the stub's ``caseId`` (CM-11-003), and the stub's
    ``type`` is what tells the reply apart from a reply to a full-case Invite
    (CM-11-013).

    Raises:
        VultronNotFoundError: when no activity with *invite_id* was received.
        VultronValidationError: when the activity received under *invite_id*
            is not an Invite.
    """
    held = read_received_as_received(dl, invite_id, "RmInviteToCaseActivity")
    if not isinstance(held, as_Invite):
        raise VultronValidationError(
            f"invite '{invite_id}' is held as {type(held).__name__},"
            " not as an Invite"
        )
    return held
