"""The point picker's points, labels and notes (#6671)."""

import pytest

from test.shadow.dashboard.view._support import narrative_line
from vultron.shadow.dashboard import view

_POINTS = (
    narrative_line(log_index=0, phrase="Case Actor created the case"),
    narrative_line(log_index=1, phrase="Vendor accepted the embargo"),
    narrative_line(log_index=3, phrase="Vendor closed the report"),
)


def test_the_points_are_now_then_each_line_in_ledger_order():
    assert view.point_options(_POINTS) == [view.LATEST_POINT, 0, 1, 3]
    assert view.point_options(()) == [view.LATEST_POINT]


def test_a_point_reads_as_its_line_and_now_reads_as_now():
    """A line reads by its activity, which names its actor (DRPT-03-009)."""
    assert view.point_label(1, _POINTS) == "#1 · Vendor accepted the embargo"
    assert view.point_label(view.LATEST_POINT, _POINTS) == (
        view.LATEST_POINT_LABEL
    )
    with pytest.raises(ValueError, match="no line at 2"):
        view.point_label(2, _POINTS)


def test_the_point_note_names_the_entry_and_how_many_entries_it_reads():
    """Entry #3 follows a hole, so it is the third entry of three."""
    note = view.point_note(1, _POINTS)
    assert "just after entry #1" in note
    assert "first 2 of 3 entries only" in note
    assert "first 3 of 3 entries only" in view.point_note(3, _POINTS)
