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

"""Note-exchange helpers for demo workflows.

Provides :func:`participant_adds_note_to_case` as a generic ``Add(Note)``
action wrapper.  Using the AS2 ``Add`` verb (rather than HTTP "post") keeps
the naming aligned with the ActivityStreams wire format.
"""

import logging
from typing import Optional

from vultron.demo.helpers.polling import wait_for_note_in_case
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_step,
    post_to_trigger,
    verify_object_stored,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def participant_adds_note_to_case(
    posting_client: DataLayerClient,
    watching_client: DataLayerClient,
    poster: as_Actor,
    case: as_VulnerabilityCase,
    note_name: str,
    note_content: str,
    in_reply_to: Optional[str] = None,
) -> as_Note:
    """Participant adds a note to a case via the ``add-note-to-case`` trigger.

    Models the AS2 ``Add(Note)`` action: the posting actor uses their own
    container's trigger endpoint so the note flows through the poster's outbox
    to the case host's inbox — reflecting real deployment behavior
    (D5-7-DEMONOTECLEAN-1).

    Args:
        posting_client: Client connected to the posting actor's container.
        watching_client: Client connected to the container where note delivery
            should be verified (typically the case host or coordinator).
        poster: The ``as_Actor`` adding the note.
        case: The ``as_VulnerabilityCase`` the note belongs to.
        note_name: Short name / subject for the note.
        note_content: Full text content of the note.
        in_reply_to: Optional ID of the note being replied to.

    Returns:
        The ``as_Note`` fetched from the *watching_client* DataLayer after
        confirmed delivery.

    Raises:
        AssertionError: If the trigger does not return a note ID, or if the
            note does not appear in the case within the polling timeout.
    """
    body: dict[str, object] = {
        "case_id": case.id_,
        "note_name": note_name,
        "note_content": note_content,
    }
    if in_reply_to is not None:
        body["in_reply_to"] = in_reply_to

    with demo_step(f"Participant adds note '{note_name}' to case"):
        result = post_to_trigger(
            client=posting_client,
            actor_id=poster.id_,
            behavior="add-note-to-case",
            body=body,
            path_prefix="demo",
        )

    note_id = result.get("note", {}).get("id")
    if note_id is None:
        raise AssertionError(
            "add-note-to-case trigger did not return a note ID"
        )

    with demo_check("Note delivered to watching container"):
        wait_for_note_in_case(watching_client, case.id_, note_id)
        verify_object_stored(watching_client, note_id)

    logger.info("Note added to case: %s", note_id)

    note_data = watching_client.get(f"/datalayer/{note_id}")
    return as_Note(**note_data)
