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

"""The case narrative's hindsight marks as rows: icon, note and shade (#6672)."""

import pytest

from test.shadow.dashboard.view._support import NAMES, VENDOR, narrative_line
from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.rm import RM
from vultron.measure.advice import (
    BAND_COLOUR_MAPS,
    Band,
    HindsightMark,
    NarrativeMark,
)
from vultron.measure.advice.hindsight import DID_AS_WELL, NO_STATE_CHANGE
from vultron.measure.standing import CSMove, RMMove
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.view import marks

_RM_ACCEPT = RMMove(
    participant=VENDOR, source=RM.VALID, destination=RM.ACCEPTED
)
_PUBLISH = CSMove(
    participant=VENDOR,
    event=CSEvent.P,
    source=CS.Vfdpxa,
    destination=CS.VfdPxa,
)


def _marked(**fields) -> NarrativeMark:
    return NarrativeMark(**{"log_index": 0, **fields})


_SUB_OPTIMAL = _marked(
    mark=HindsightMark.SUB_OPTIMAL,
    move=_RM_ACCEPT,
    band=Band.TRADE_OFF,
    layer=2,
    deepest_layer=3,
    note=DID_AS_WELL,
)


def test_every_hindsight_mark_has_an_icon_of_its_own_shape():
    """The icons differ in shape, so a mark reads without its shade."""
    assert set(marks.HINDSIGHT_ICONS) == set(HindsightMark)
    assert len(set(marks.HINDSIGHT_ICONS.values())) == len(HindsightMark)
    assert marks.HINDSIGHT_ICONS[HindsightMark.BEST] == "⭐"
    assert marks.HINDSIGHT_ICONS[HindsightMark.CHANCE] == "🎲"
    assert marks.HINDSIGHT_ICONS[HindsightMark.NOT_A_MOVE] == "💬"


def test_a_marked_row_carries_its_mark_beside_its_log_index():
    (row,) = marks.marked_narrative_rows(
        [narrative_line()], NAMES, [_SUB_OPTIMAL]
    )
    assert list(row)[:2] == ["#", marks.HINDSIGHT_COLUMN]
    assert row[marks.HINDSIGHT_COLUMN] == "⚠️ sub-optimal"


def test_a_sub_optimal_line_a_harm_free_move_dominated_says_so():
    """AC-3: the dominated-by-harm-free note shows on the ⚠️ line."""
    (row,) = marks.marked_narrative_rows(
        [narrative_line()], NAMES, [_SUB_OPTIMAL]
    )
    note = row[marks.HINDSIGHT_NOTE_COLUMN]
    assert note == f"RM Accept (Vendor): {DID_AS_WELL}"


def test_a_case_wide_move_names_no_participant_in_its_note():
    """A publication moves the case's state, whoever's move it is."""
    mark = _marked(
        mark=HindsightMark.BEST,
        move=_PUBLISH,
        band=Band.HARM_FREE,
        layer=1,
        deepest_layer=1,
    )
    assert marks.mark_note(mark, NAMES) == "CS Public becomes aware"


def test_a_line_that_is_not_graded_says_why():
    mark = _marked(mark=HindsightMark.NOT_A_MOVE, note=NO_STATE_CHANGE)
    (row,) = marks.marked_narrative_rows([narrative_line()], NAMES, [mark])
    assert row[marks.HINDSIGHT_COLUMN] == "💬 not a move"
    assert row[marks.HINDSIGHT_NOTE_COLUMN] == NO_STATE_CHANGE


def test_a_marked_row_keeps_every_narrative_column_in_order():
    mark = _marked(mark=HindsightMark.NOT_A_MOVE, note=NO_STATE_CHANGE)
    (plain,) = view.narrative_rows([narrative_line()], NAMES)
    (row,) = marks.marked_narrative_rows([narrative_line()], NAMES, [mark])
    assert [c for c in row if not c.startswith("Hindsight")] == list(plain)
    assert list(row)[-1] == marks.HINDSIGHT_NOTE_COLUMN


def test_marks_that_are_not_one_per_line_are_refused():
    with pytest.raises(ValueError, match="one per narrative line"):
        marks.marked_narrative_rows(
            [narrative_line(), narrative_line(log_index=1)],
            NAMES,
            [_SUB_OPTIMAL],
        )


def test_a_shaded_mark_takes_its_layers_shade_on_its_bands_legend():
    """⭐, 👍 and ⚠️ take the shade their layer has on the legend of the
    advice they were graded by; no other mark is shaded."""
    best = _marked(
        mark=HindsightMark.BEST,
        move=_RM_ACCEPT,
        band=Band.HARM_FREE,
        layer=1,
        deepest_layer=3,
    )
    bad = _marked(mark=HindsightMark.BAD, move=_RM_ACCEPT, band=Band.UNHELPFUL)
    chance = _marked(mark=HindsightMark.CHANCE, note="by chance")
    shades = marks.mark_shades([best, _SUB_OPTIMAL, bad, chance])
    assert shades == (
        view.band_legend_shades(BAND_COLOUR_MAPS[Band.HARM_FREE], 3)[0],
        view.band_legend_shades(BAND_COLOUR_MAPS[Band.TRADE_OFF], 3)[1],
        None,
        None,
    )
