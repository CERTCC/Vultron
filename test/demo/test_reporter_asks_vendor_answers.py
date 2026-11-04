"""The shared Reporter/Vendor note exchange puts both notes in the case.

Spec: DEMOMA-16-001.
"""

from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.helpers import notes
from vultron.demo.helpers.coordinated_story import (
    continuations as coordinated_continuations,
    opening as coordinated_opening,
)
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note


@pytest.mark.spec("DEMOMA-16-001")
def test_the_vendor_answer_replies_to_the_reporter_question():
    reporter, vendor = MagicMock(), MagicMock()
    watching, case = MagicMock(), MagicMock()
    question = MagicMock(id_="urn:note:question")

    with patch.object(
        notes, "participant_adds_note_to_case", side_effect=[question, None]
    ) as add_note:
        notes.reporter_asks_vendor_answers(reporter, vendor, watching, case)

    first, second = add_note.call_args_list
    assert first.kwargs["posting_client"] is reporter.client
    assert first.kwargs["poster"] is reporter.actor
    assert second.kwargs["posting_client"] is vendor.client
    assert second.kwargs["poster"] is vendor.actor
    assert second.kwargs["in_reply_to"] == "urn:note:question"
    assert first.kwargs["watching_client"] is watching
    assert second.kwargs["watching_client"] is watching


@pytest.mark.spec("DEMOMA-16-001")
def test_a_failed_question_leaves_the_reply_unthreaded():
    with patch.object(
        notes, "participant_adds_note_to_case", return_value=None
    ) as add_note:
        notes.reporter_asks_vendor_answers(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )

    assert add_note.call_args_list[1].kwargs["in_reply_to"] is None


def _session(name: str) -> MagicMock:
    session = MagicMock(name=name)
    session.client = MagicMock(name=f"{name}-client")
    session.actor = MagicMock(name=f"{name}-actor")
    return session


def _posts(*names: str) -> list[notes.NotePost]:
    return [
        notes.NotePost(_session(n), f"{n} note", f"{n} text") for n in names
    ]


def test_a_posted_thread_returns_one_entry_per_post_in_order():
    """``post_note_thread`` names every note, not only the last (#5536).

    The vendor-first family keeps the Reporter's question and the Vendor's
    answer as separate story props — ``rv``'s final case check names both —
    so the list form is what the family composes against and the threading is
    read off it: the first note replies to *in_reply_to* and each later one to
    the note before (DEMOCI-11-017).
    """
    first, second = MagicMock(id_="urn:note:1"), MagicMock(id_="urn:note:2")
    start = MagicMock(id_="urn:note:0")

    with patch.object(
        notes, "participant_adds_note_to_case", side_effect=[first, second]
    ) as add_note:
        posted = notes.post_note_thread(
            MagicMock(), MagicMock(), _posts("a", "b"), in_reply_to=start
        )

    assert posted == [first, second], (
        "every note must come back in posting order, so a caller can keep more"
        f" than one of them as a prop; got {posted!r}"
    )
    assert [c.kwargs["in_reply_to"] for c in add_note.call_args_list] == [
        "urn:note:0",
        "urn:note:1",
    ], "each note threads onto the one before it, the first onto in_reply_to"


def test_a_posted_thread_reports_the_post_that_failed_in_place():
    """A failed post is ``None`` *at its own index*, not dropped.

    A caller pairs the list with the posts it asked for, so a dropped entry
    would silently shift every prop after it onto the wrong note.
    """
    second = MagicMock(id_="urn:note:2")

    with patch.object(
        notes, "participant_adds_note_to_case", side_effect=[None, second]
    ):
        posted = notes.post_note_thread(
            MagicMock(), MagicMock(), _posts("a", "b")
        )

    assert posted == [None, second], (
        "the failed post must hold its place in the list, or the caller's"
        f" props would shift onto the wrong notes; got {posted!r}"
    )


def test_a_note_thread_replies_to_the_note_before():
    first, second = MagicMock(id_="urn:note:1"), MagicMock(id_="urn:note:2")
    start = MagicMock(id_="urn:note:0")

    with patch.object(
        notes, "participant_adds_note_to_case", side_effect=[first, second]
    ) as add_note:
        last = notes.add_note_thread(
            MagicMock(), MagicMock(), _posts("a", "b"), in_reply_to=start
        )

    assert last is second
    assert [c.kwargs["in_reply_to"] for c in add_note.call_args_list] == [
        "urn:note:0",
        "urn:note:1",
    ]


def test_a_failed_note_leaves_the_next_unthreaded_not_skipped():
    second = MagicMock(id_="urn:note:2")

    with patch.object(
        notes, "participant_adds_note_to_case", side_effect=[None, second]
    ) as add_note:
        last = notes.add_note_thread(
            MagicMock(), MagicMock(), _posts("a", "b")
        )

    assert last is second
    assert add_note.call_count == 2
    assert add_note.call_args_list[1].kwargs["in_reply_to"] is None


def test_an_empty_thread_returns_the_note_it_was_handed():
    """``add_note_thread`` with no posts is the note already in hand.

    It is the one-note form of ``post_note_thread``, so "the last note of the
    thread" with nothing posted is whatever the thread was told to reply to:
    returning ``None`` instead would read as a failed post and a continuation
    answering the thread would stop.
    """
    start = MagicMock(id_="urn:note:0")

    with patch.object(notes, "participant_adds_note_to_case") as add_note:
        last = notes.add_note_thread(
            MagicMock(), MagicMock(), [], in_reply_to=start
        )

    assert last is start
    add_note.assert_not_called()


def test_an_empty_thread_with_nothing_in_hand_returns_none():
    """No posts and no note to reply to is no note (``add_note_thread``)."""
    with patch.object(notes, "participant_adds_note_to_case"):
        assert notes.add_note_thread(MagicMock(), MagicMock(), []) is None


@pytest.mark.spec("DEMOMA-22-001")
def test_a_gated_thread_waits_on_the_named_replica_first():
    replica, case = MagicMock(), MagicMock(id_="urn:case")
    order = MagicMock()
    order.participant_adds_note_to_case.return_value = MagicMock(id_="n")

    with (
        patch.object(
            notes,
            "wait_for_case_on_container",
            order.wait_for_case_on_container,
        ),
        patch.object(
            notes,
            "participant_adds_note_to_case",
            order.participant_adds_note_to_case,
        ),
    ):
        notes.gated_note_thread(
            gate="replica holds the case",
            replica_client=replica,
            watching_client=MagicMock(),
            case=case,
            posts=_posts("a"),
        )

    assert [name for name, _a, _k in order.mock_calls] == [
        "wait_for_case_on_container",
        "participant_adds_note_to_case",
    ]
    assert order.wait_for_case_on_container.call_args.kwargs == {
        "client": replica,
        "case_id": "urn:case",
    }


@pytest.mark.spec("DEMOMA-22-001")
def test_a_failed_gate_posts_nothing_and_records_the_failure():
    from vultron.demo import utils
    from vultron.demo.utils.failures import _demo_failures

    utils.reset_demo_failures()
    try:
        with (
            patch.object(
                notes,
                "wait_for_case_on_container",
                side_effect=TimeoutError("no replica"),
            ),
            patch.object(notes, "participant_adds_note_to_case") as add_note,
        ):
            last = notes.gated_note_thread(
                gate="replica holds the case",
                replica_client=MagicMock(),
                watching_client=MagicMock(),
                case=MagicMock(),
                posts=_posts("a", "b"),
            )
        failures = list(_demo_failures)
    finally:
        utils.reset_demo_failures()

    assert last is None
    add_note.assert_not_called()
    assert len(failures) == 1
    assert "replica holds the case" in failures[0]


@pytest.mark.spec("DEMOMA-22-001")
def test_a_failed_gate_returns_an_empty_list_from_the_posting_form():
    """``gated_note_posts`` posts nothing and names nothing (#5536).

    The list form must say "no notes" rather than one ``None`` per post: a
    caller keeps each entry as a story prop, and a prop kept as ``None``
    raises at ``keep`` while an absent one lets the dependent fragment stop
    with the gate's own failure as the cause (``StoryState.keep``).
    """
    from vultron.demo import utils
    from vultron.demo.utils.failures import _demo_failures

    utils.reset_demo_failures()
    try:
        with (
            patch.object(
                notes,
                "wait_for_case_on_container",
                side_effect=TimeoutError("no replica"),
            ),
            patch.object(notes, "participant_adds_note_to_case") as add_note,
        ):
            posted = notes.gated_note_posts(
                gate="replica holds the case",
                replica_client=MagicMock(),
                watching_client=MagicMock(),
                case=MagicMock(),
                posts=_posts("a", "b"),
            )
            last = notes.gated_note_thread(
                gate="replica holds the case",
                replica_client=MagicMock(),
                watching_client=MagicMock(),
                case=MagicMock(),
                posts=_posts("a", "b"),
            )
        failures = list(_demo_failures)
    finally:
        utils.reset_demo_failures()

    assert posted == [], (
        "a failed gate must name no notes at all, so a caller keeps no prop;"
        f" got {posted!r}"
    )
    assert last is None, "the one-note form of the same failure is None"
    add_note.assert_not_called()
    assert len(failures) == 2, (
        "each failed gate records its own failure (DEMOCI-01-003); the"
        f" accumulator holds {failures!r}"
    )


@pytest.mark.spec("DEMOMA-22-001")
def test_reporter_asks_gates_on_the_reporter_replica_and_asks_first():
    reporter = _session("reporter")
    watching, case = MagicMock(), MagicMock()
    replies = _posts("vendor")

    with patch.object(notes, "gated_note_posts") as gated:
        posted = notes.reporter_asks(
            reporter, watching, case, "Any workaround?", replies
        )

    assert posted is gated.return_value
    kwargs = gated.call_args.kwargs
    assert kwargs["replica_client"] is reporter.client
    assert kwargs["watching_client"] is watching
    assert kwargs["case"] is case
    question, *rest = kwargs["posts"]
    assert question == notes.NotePost(
        reporter, "Question from Reporter", "Any workaround?"
    )
    assert rest == replies


@pytest.mark.spec("DEMOMA-22-001")
def test_reporter_asks_returns_the_question_and_each_reply_in_order():
    """Every note of the thread, question first (#5536).

    The vendor-first family keeps the Reporter's question and the Vendor's
    answer as separate props, so the question cannot be collapsed into the
    answer the way the one-note form did: ``rv``'s final case check names both
    notes and its siblings reply to the answer (DEMOCI-11-017).
    """
    reporter, vendor = _session("reporter"), _session("vendor")
    question = MagicMock(id_="urn:note:question")
    answer = MagicMock(id_="urn:note:answer")

    with (
        patch.object(notes, "wait_for_case_on_container"),
        patch.object(
            notes,
            "participant_adds_note_to_case",
            side_effect=[question, answer],
        ) as add_note,
    ):
        posted = notes.reporter_asks(
            reporter,
            MagicMock(),
            MagicMock(id_="urn:case"),
            notes.WORKAROUND_QUESTION,
            [notes.vendor_answers_workaround(vendor)],
        )

    assert posted == [question, answer], (
        "the question and each reply must come back in posting order, so each"
        f" can be kept as its own prop; got {posted!r}"
    )
    asked, answered = add_note.call_args_list
    assert asked.kwargs["poster"] is reporter.actor
    assert asked.kwargs["note_name"] == "Question from Reporter"
    assert asked.kwargs["note_content"] == notes.WORKAROUND_QUESTION
    assert answered.kwargs["poster"] is vendor.actor
    assert answered.kwargs["in_reply_to"] == "urn:note:question"


@pytest.mark.spec("DEMOMA-22-001")
def test_reporter_asks_returns_nothing_when_its_replica_gate_fails():
    """A Reporter with no replica cannot post, so the thread names no note.

    The Reporter posts the question from its own replica, so that replica
    holding the case is the thread's cause (DEMOMA-22-001): the gate records
    the timeout and the caller keeps no prop, which is how the fragments that
    read one stop the story instead of answering a note that was never
    posted.
    """
    from vultron.demo import utils
    from vultron.demo.utils.failures import _demo_failures

    utils.reset_demo_failures()
    try:
        with (
            patch.object(
                notes,
                "wait_for_case_on_container",
                side_effect=TimeoutError("no replica"),
            ),
            patch.object(notes, "participant_adds_note_to_case") as add_note,
        ):
            posted = notes.reporter_asks(
                _session("reporter"),
                MagicMock(),
                MagicMock(),
                "Any workaround?",
                _posts("vendor"),
            )
        failures = list(_demo_failures)
    finally:
        utils.reset_demo_failures()

    assert posted == [], f"a failed gate names no notes; got {posted!r}"
    add_note.assert_not_called()
    assert failures and "Reporter's replica" in failures[0], (
        "the gate's own label must be what is recorded, so the cause reads as"
        f" the Reporter's missing replica; it recorded {failures!r}"
    )


# The phase-form of this check covered ``rccv-extension`` and
# ``rccv-handoff``, which are now written as composition (#5535): their one
# thread is asserted by ``TestFourWayNoteThread`` in
# ``test/demo/test_two_coordinator_story.py``, which owns the shared half of
# the thread, and by each scenario's own ``TestTheFourExchangeNotes``.  The
# composed form below is the shape every scenario's check now takes.


@pytest.mark.spec("DEMOMA-17-001")
def test_the_rejection_fragment_posts_one_thread() -> None:
    """The composed form of the check above (#5533).

    ``rcv-reject`` assembles its story, so its note exchange is a fragment
    taking the story's state rather than a phase taking one keyword per actor.
    The Vendor declined, so nothing gates the thread on its replica and the
    posts go straight to ``add_note_thread``.
    """
    from test.demo._helpers import mock_case, story_state
    from vultron.demo.helpers import coordinated_story

    state = story_state("reporter", "coordinator", "vendor", case=mock_case())

    with patch.object(coordinated_continuations, "add_note_thread") as thread:
        coordinated_story.reporter_asks_about_the_rejection(state)

    watching, case, posts = thread.call_args.args
    assert watching is state.client("coordinator")
    assert case is state.case
    assert [post.poster for post in posts] == [
        state.actor(name) for name in ("reporter", "coordinator")
    ]
    assert posts[0].name == "Question from Reporter"


@pytest.mark.spec("DEMOMA-17-001")
@pytest.mark.spec("DEMOMA-22-001")
def test_the_timeline_fragment_gates_its_thread_on_the_vendors_replica() -> (
    None
):
    """The ask-vendor thread waits for the Vendor's replica, then posts (#5534).

    The Vendor posts the middle note from its own container, so that replica
    holding the case is the thread's cause: the fragment goes through
    ``gated_note_thread`` rather than posting straight away, and the
    Coordinator's closing note is kept for a continuation to answer
    (``rcvcv``'s late joiners reply to it).
    """
    from test.demo._helpers import mock_case, story_state
    from vultron.demo.helpers import coordinated_story

    state = story_state("reporter", "coordinator", "vendor", case=mock_case())
    answer = as_Note(name="Coordinator Summary", content="x")

    with patch.object(
        coordinated_opening, "gated_note_thread", return_value=answer
    ) as thread:
        coordinated_story.reporter_asks_about_the_timeline(state)

    kwargs = thread.call_args.kwargs
    assert kwargs["replica_client"] is state.client("vendor")
    assert kwargs["watching_client"] is state.client("coordinator")
    assert kwargs["case"] is state.case
    assert [post.poster for post in kwargs["posts"]] == [
        state.actor(name) for name in ("reporter", "vendor", "coordinator")
    ]
    assert kwargs["posts"][0].name == "Question from Reporter"
    assert state.kept(coordinated_story.TIMELINE_ANSWER) is answer


@pytest.mark.spec("DEMOMA-17-001")
def test_the_timeline_fragment_keeps_nothing_when_its_thread_fails() -> None:
    """A continuation that answers the thread then stops rather than guessing."""
    from test.demo._helpers import mock_case, story_state
    from vultron.demo.helpers import coordinated_story

    state = story_state("reporter", "coordinator", "vendor", case=mock_case())

    with patch.object(
        coordinated_opening, "gated_note_thread", return_value=None
    ):
        coordinated_story.reporter_asks_about_the_timeline(state)

    with pytest.raises(DemoStoryError):
        state.kept(coordinated_story.TIMELINE_ANSWER)


def test_the_timeline_thread_asks_then_the_vendor_and_coordinator_answer():
    """The ask-vendor thread every sibling posts before C's decision (#4727)."""
    reporter, vendor, coordinator = (
        _session("reporter"),
        _session("vendor"),
        _session("coordinator"),
    )

    posts = notes.reporter_asks_vendor_timeline(reporter, vendor, coordinator)

    assert [post.poster for post in posts] == [reporter, vendor, coordinator]
    assert [post.name for post in posts] == [
        "Question from Reporter",
        "Vendor Status Update",
        "Coordinator Summary",
    ]


def test_the_workaround_answer_is_the_vendors_shared_reply():
    vendor = _session("vendor")

    assert notes.vendor_answers_workaround(vendor) == notes.NotePost(
        vendor, notes.WORKAROUND_ANSWER_NAME, notes.WORKAROUND_ANSWER
    )
