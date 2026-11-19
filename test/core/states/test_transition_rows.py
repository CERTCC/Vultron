"""Each core transition table read as typed rows (#6674).

A tool that draws a machine reads its table through these accessors, never
its private list; each holds every row of its table, in table order.
"""

import pytest

from vultron.core.states.cs import (
    d_transition_rows,
    pxa_transition_rows,
    vf_transition_rows,
)
from vultron.core.states.cs.transitions import (
    _d_transitions,
    _pxa_transitions,
    _vf_transitions,
)
from vultron.core.states.rm import _transitions, rm_transition_rows


@pytest.mark.parametrize(
    ("rows", "table"),
    [
        (rm_transition_rows, _transitions),
        (vf_transition_rows, _vf_transitions),
        (d_transition_rows, _d_transitions),
        (pxa_transition_rows, _pxa_transitions),
    ],
    ids=["rm", "vf", "d", "pxa"],
)
def test_the_rows_are_the_table_in_order(rows, table):
    assert [row.model_dump() for row in rows()] == table
