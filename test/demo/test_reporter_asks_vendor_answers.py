"""The shared Reporter/Vendor note exchange puts both notes in the case.

Spec: DEMOMA-16-001.
"""

from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.helpers import notes


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
        failures = list(utils._demo_failures)
    finally:
        utils.reset_demo_failures()

    assert last is None
    add_note.assert_not_called()
    assert len(failures) == 1
    assert "replica holds the case" in failures[0]


@pytest.mark.spec("DEMOMA-22-001")
def test_reporter_asks_gates_on_the_reporter_replica_and_asks_first():
    reporter = _session("reporter")
    watching, case = MagicMock(), MagicMock()
    replies = _posts("vendor")

    with patch.object(notes, "gated_note_thread") as gated:
        last = notes.reporter_asks(
            reporter, watching, case, "Any workaround?", replies
        )

    assert last is gated.return_value
    kwargs = gated.call_args.kwargs
    assert kwargs["replica_client"] is reporter.client
    assert kwargs["watching_client"] is watching
    assert kwargs["case"] is case
    question, *rest = kwargs["posts"]
    assert question == notes.NotePost(
        reporter, "Question from Reporter", "Any workaround?"
    )
    assert rest == replies


@pytest.mark.parametrize(
    ("module", "posters"),
    [
        ("rccv_extension_demo", ["reporter", "c1", "c2", "vendor"]),
        ("rccv_handoff_demo", ["reporter", "c1", "c2", "vendor"]),
    ],
)
@pytest.mark.spec("DEMOMA-17-001")
def test_scenario_notes_exchange_is_one_thread(
    module: str, posters: list[str]
) -> None:
    """Each scenario's exchange posts one thread, in order, from each poster."""
    import importlib
    import inspect

    demo = importlib.import_module(f"vultron.demo.scenario.{module}")
    params = inspect.signature(demo._phase_notes_exchange).parameters
    kwargs = {name: MagicMock(name=name) for name in params}

    with patch.object(demo, "add_note_thread") as thread:
        demo._phase_notes_exchange(**kwargs)

    (_watching, case, posts), _ = thread.call_args
    assert case is kwargs["case"]
    assert [p.poster.client for p in posts] == [
        kwargs[f"{name}_client"] for name in posters
    ]
    assert [p.poster.actor for p in posts] == [
        kwargs[f"{name}_in_{name}"] for name in posters
    ]
    assert posts[0].name == "Question from Reporter"


@pytest.mark.parametrize(
    ("fragment", "posters"),
    [
        (
            "reporter_asks_about_the_timeline",
            ["reporter", "vendor", "coordinator"],
        ),
        ("reporter_asks_about_the_rejection", ["reporter", "coordinator"]),
    ],
)
@pytest.mark.spec("DEMOMA-17-001")
def test_a_story_fragment_posts_one_thread(
    fragment: str, posters: list[str]
) -> None:
    """The composed form of the check above (#5533).

    ``rcv`` and ``rcv-reject`` assemble their stories, so their note exchange
    is a fragment taking the story's state rather than a phase taking one
    keyword per actor.
    """
    from test.demo._helpers import mock_case, story_state
    from vultron.demo.helpers import coordinated_story

    state = story_state("reporter", "coordinator", "vendor", case=mock_case())

    with patch.object(coordinated_story, "add_note_thread") as thread:
        getattr(coordinated_story, fragment)(state)

    watching, case, posts = thread.call_args.args
    assert watching is state.client("coordinator")
    assert case is state.case
    assert [post.poster for post in posts] == [
        state.actor(name) for name in posters
    ]
    assert posts[0].name == "Question from Reporter"


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
