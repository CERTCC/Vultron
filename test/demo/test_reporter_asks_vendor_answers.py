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
