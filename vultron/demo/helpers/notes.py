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

Provides :func:`participant_adds_note_to_case`, which posts a note to a case
through the ``add-note-to-case`` trigger.  The trigger sends one
``Add(Note)`` that names the case as its ``target`` and carries the note
inline; the CASE_MANAGER attaches the note and commits an
``add_note_to_case`` ledger entry.

:func:`add_note_thread` posts a sequence of notes, each replying to the one
before, and :func:`gated_note_thread` does so only once a named replica holds
the case: a poster acts from its own replica, so that replica is the cause the
first note waits on (DEMOMA-22-001).  :func:`reporter_asks` is the thread a
Reporter opens, gated on the Reporter's replica.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    wait_for_case_on_container,
    wait_for_note_in_case,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_gate,
    demo_step,
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
    in_reply_to: str | None = None,
) -> as_Note | None:
    """Participant adds a note to a case via the ``add-note-to-case`` trigger.

    The posting actor uses their own container's trigger endpoint, which
    sends one ``Add(Note)`` naming the case as its ``target`` and carrying
    the note inline, so the note flows through the poster's outbox to the
    case host's inbox — reflecting real deployment behavior
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
        confirmed delivery, or ``None`` when the trigger or delivery check
        fails (failures are recorded in the demo accumulator via
        ``demo_step``/``demo_gate``).
    """
    session = ActorSession(client=posting_client, actor=poster).with_case(case)
    note_id: str | None = None
    with demo_step(f"Participant adds note '{note_name}' to case"):
        result = session.quiet().add_note_to_case(
            note_name=note_name,
            note_content=note_content,
            in_reply_to=in_reply_to,
        )
        note_id = (result.note or {}).get("id")
        if note_id is None:
            raise AssertionError(
                "add-note-to-case trigger did not return a note ID"
            )

    if note_id is None:
        return None

    note: as_Note | None = None
    with demo_gate("Note delivered to watching container"):
        wait_for_note_in_case(watching_client, case.id_, note_id)
        verify_object_stored(watching_client, note_id)
        logger.info("Note added to case: %s", note_id)
        note_data = watching_client.get(watching_client.dl_path(note_id))
        note = as_Note(**note_data)

    return note


@dataclass(frozen=True, slots=True)
class NotePost:
    """One note of a thread: who posts it, its subject and its text."""

    #: The posting actor, in its own container.
    poster: ActorSession
    #: Short name / subject for the note.
    name: str
    #: Full text content of the note.
    content: str


def add_note_thread(
    watching_client: DataLayerClient,
    case: as_VulnerabilityCase,
    posts: Sequence[NotePost],
    in_reply_to: as_Note | None = None,
) -> as_Note | None:
    """Post *posts* in order, each replying to the note before it.

    A note that fails is recorded by :func:`participant_adds_note_to_case`,
    and the next note is then posted unthreaded rather than skipped.

    Args:
        watching_client: Client where delivery of each note is verified
            (typically the case owner's container).
        case: The case the notes belong to.
        posts: The notes, in posting order.
        in_reply_to: The note the first post replies to, if any.

    Returns:
        The last note posted, or ``None`` when it failed.
    """
    previous = in_reply_to
    for post in posts:
        previous = participant_adds_note_to_case(
            posting_client=post.poster.client,
            watching_client=watching_client,
            poster=post.poster.actor,
            case=case,
            note_name=post.name,
            note_content=post.content,
            in_reply_to=previous.id_ if previous is not None else None,
        )
    return previous


def gated_note_thread(
    *,
    gate: str,
    replica_client: DataLayerClient,
    watching_client: DataLayerClient,
    case: as_VulnerabilityCase,
    posts: Sequence[NotePost],
    in_reply_to: as_Note | None = None,
) -> as_Note | None:
    """Post *posts* once *replica_client*'s replica holds the case.

    The wait is a causal gate (DEMOMA-22-001): the first poster acts from its
    own replica, so a thread whose poster has no replica is skipped and the
    gate failure recorded, rather than posting a note that cannot succeed.

    Args:
        gate: The ``demo_gate`` label naming the precondition.
        replica_client: The container whose replica must hold the case.
        watching_client: As :func:`add_note_thread`.
        case: As :func:`add_note_thread`.
        posts: As :func:`add_note_thread`.
        in_reply_to: As :func:`add_note_thread`.

    Returns:
        The last note posted, or ``None`` when it failed or the gate did.
    """
    last: as_Note | None = None
    with demo_gate(gate):
        wait_for_case_on_container(client=replica_client, case_id=case.id_)
        last = add_note_thread(watching_client, case, posts, in_reply_to)
    return last


#: The Reporter's opening question in the rvcv, rccv and rcvcv scenarios.
WORKAROUND_QUESTION = (
    "Is there a workaround available while the patch is being developed?"
)


def reporter_asks(
    reporter: ActorSession,
    watching_client: DataLayerClient,
    case: as_VulnerabilityCase,
    question: str,
    replies: Sequence[NotePost],
) -> as_Note | None:
    """The Reporter asks *question* from its replica; *replies* answer it.

    A :func:`gated_note_thread` on the Reporter's replica: the Reporter posts
    from it, so the thread waits until that replica holds the case
    (DEMOMA-22-001).

    Args:
        reporter: Session in the Reporter's container; posts the question.
        watching_client: As :func:`add_note_thread`.
        case: As :func:`add_note_thread`.
        question: Text of the Reporter's question.
        replies: The notes that answer it, in posting order.

    Returns:
        The last reply, or ``None`` when it failed or the gate did.
    """
    return gated_note_thread(
        gate="Reporter's replica holds the case before it asks",
        replica_client=reporter.client,
        watching_client=watching_client,
        case=case,
        posts=[
            NotePost(reporter, "Question from Reporter", question),
            *replies,
        ],
    )


def reporter_asks_vendor_answers(
    reporter: ActorSession,
    vendor: ActorSession,
    watching_client: DataLayerClient,
    case: as_VulnerabilityCase,
) -> as_Note | None:
    """The Reporter asks about the revised embargo and the Vendor answers.

    The shared note exchange of the embargo scenarios; it puts
    ``add_note_to_case`` in the case ledger (DEMOMA-16-001).  It runs after
    the Reporter's embargo proposal phase, so the Vendor's next decision on
    the scenario tree follows it (``notes/demo-scenario-registry.md``).  Failures
    are recorded by :func:`participant_adds_note_to_case`.

    Args:
        reporter: Session in the Reporter's container; posts the question.
        vendor: Session in the Vendor's container; posts the reply.
        watching_client: Client where delivery of each note is verified
            (typically the Coordinator, who hosts the case).
        case: The case the notes belong to.

    Returns:
        The Vendor's reply, or ``None`` when it failed.
    """
    return add_note_thread(
        watching_client,
        case,
        [
            NotePost(
                reporter,
                "Question from Reporter",
                "Does the revised embargo leave enough time for a fix?",
            ),
            NotePost(
                vendor,
                "Vendor Status Update",
                "A fix is in progress; we will confirm the timeline.",
            ),
        ],
    )
