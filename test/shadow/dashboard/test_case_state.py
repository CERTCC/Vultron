"""The case state's two small machines, in notation and in words (#6674).

A fix path reads as words, never as its compound state's name (AC-3), and
an event the source cannot observe reads as unknown, never as false
(CRD-02-005).
"""

import pytest

from vultron.core.states.cs import CS, CS_d, CS_vf
from vultron.core.states.cs_invariants import CSEvent
from vultron.shadow.dashboard import case_state

_PXA = ["pxa", "Pxa", "pxA", "PxA", "pXa", "PXa", "pXA", "PXA"]


def test_the_notation_spells_the_core_events_in_order():
    assert case_state.VFD_NOTATION == (CSEvent.V, CSEvent.F, CSEvent.D)
    assert case_state.PXA_NOTATION == (CSEvent.P, CSEvent.X, CSEvent.A)


def test_each_vendor_fix_path_state_reads_in_words():
    """AC-3: a fix path reads as words, never as its compound state's
    name."""
    assert set(case_state.VFD_WORDS) == set(case_state.VFD_STATES)
    assert case_state.vfd_badge(CS.VFdPXa) == "🩹 Fix ready"
    assert case_state.vfd_badge(CS.vfdpxa) == "⚪ Vendor unaware"
    assert case_state.vfd_name(CS_vf.VF, CS_d.d) == "VFd"
    for state in CS:
        assert state.name not in case_state.vfd_badge(state)


@pytest.mark.spec("CRD-02-005")
def test_an_unobservable_fix_path_event_names_each_state_it_allows():
    assert case_state.vfd_badge(CS.VfdPxa, {CSEvent.F, CSEvent.D}) == (
        "❔ Vendor aware, fix ready or fix deployed"
    )
    assert case_state.vfd_badge(CS.vfdpxa, {CSEvent.V}) == (
        "❔ Vendor unaware or vendor aware"
    )
    # D unseen, but no fix path deploys a fix that is not ready.
    assert case_state.vfd_badge(CS.VfdPxa, {CSEvent.D}) == "👀 Vendor aware"


@pytest.mark.spec("CRD-02-005")
def test_only_an_event_not_yet_read_as_happened_may_have_happened_unseen():
    """An unobservable event the reading spells upper-case stays happened:
    nothing the reading states is read as possibly false."""
    events = case_state.PXA_NOTATION
    assert case_state.possible_states("pxa", _PXA, events, {CSEvent.A}) == (
        "pxa",
        "pxA",
    )
    assert case_state.possible_states("PXa", _PXA, events, {CSEvent.P}) == (
        "PXa",
    )
    assert case_state.possible_states("pxa", _PXA, events, ()) == ("pxa",)
