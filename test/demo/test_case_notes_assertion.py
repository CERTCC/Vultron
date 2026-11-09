"""``_assert_case_notes`` takes both note ids or neither (#5643)."""

from types import SimpleNamespace

import pytest

from vultron.demo.helpers.verification.states import _assert_case_notes

Q = "https://example.org/notes/q"
R = "https://example.org/notes/r"


def _case(*note_ids: str) -> SimpleNamespace:
    return SimpleNamespace(notes=list(note_ids))


def test_both_none_is_skipped() -> None:
    _assert_case_notes(_case(), None, None)  # type: ignore[arg-type]


def test_both_present_passes() -> None:
    _assert_case_notes(_case(Q, R), Q, R)  # type: ignore[arg-type]


def test_both_given_one_missing_raises() -> None:
    with pytest.raises(AssertionError, match="Reply note"):
        _assert_case_notes(_case(Q), Q, R)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("question", "reply", "missing"),
    [(None, R, "question_note_id"), (Q, None, "reply_note_id")],
)
def test_exactly_one_none_raises_naming_missing(
    question: str | None, reply: str | None, missing: str
) -> None:
    # The case holds the given note, so only the guard can reject the call.
    case = _case(*(i for i in (question, reply) if i))
    with pytest.raises(AssertionError, match=missing) as exc:
        _assert_case_notes(case, question, reply)  # type: ignore[arg-type]
    assert "both" in str(exc.value)
