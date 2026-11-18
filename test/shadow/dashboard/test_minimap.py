"""Each state on a small map of its state machine (#6674).

Each map is drawn from its machine's transition table in the core layer:
every state and every transition of the table is on the drawn map, and
nothing else is (AC-2).  A map marks the one state it is given, and every
state reads in words beside its map (AC-1, AC-3).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import pytest
from pydantic import ValidationError

from vultron.core.states.cs import CS, CS_d, CS_pxa, CS_vf
from vultron.core.states.cs.transitions import (
    _d_transitions,
    _pxa_transitions,
    _vf_transitions,
)
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM, EM_TRANSITIONS
from vultron.core.states.rm import RM, _transitions as _rm_transitions
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.sequences import (
    UnprojectableParticipant,
    UnprojectableReason,
)
from vultron.measure.standing import CaseStanding, ParticipantStanding
from vultron.shadow.analysis import analyse
from vultron.shadow.dashboard import minimap, view
from vultron.shadow.readers import VultronCaseReader

_NODE = re.compile(r'^"(?P<id>[^"]+)" \[label="(?P<label>[^"]*)"', re.M)
_ARROW = re.compile(
    r'^"(?P<source>[^"]+)" -> "(?P<dest>[^"]+)" \['
    r'(?:label="(?P<label>[^"]*)", )?tooltip="(?P<tooltip>[^"]*)"\];$',
    re.M,
)


def _nodes(dot: str) -> set[str]:
    return {m["id"] for m in _NODE.finditer(dot)}


def _arrows(dot: str) -> set[tuple[str, str, str]]:
    """Each drawn (trigger, source, dest), read back from the DOT source."""
    return {
        (trigger, m["source"], m["dest"])
        for m in _ARROW.finditer(dot)
        for trigger in m["tooltip"].split(", ")
    }


def _words(trigger) -> str:
    return str(trigger.value).replace("_", " ")


def _letter(trigger) -> str:
    return f"{trigger.name}: {_words(trigger)}"


def _rows(table: Iterable[dict], trigger_text) -> set[tuple[str, str, str]]:
    return {
        (trigger_text(t["trigger"]), t["source"].name, t["dest"].name)
        for t in table
    }


def _current(dot: str) -> list[str]:
    return re.findall(r'^"([^"]+)" \[[^\n]*peripheries=2', dot, re.M)


def test_the_rm_map_draws_every_state_and_transition_of_its_table():
    """AC-2: the RM table's states and transitions, both ways."""
    dot = minimap.RM_MAP.dot(RM.START.name)
    assert _nodes(dot) == {s.name for s in RM}
    assert _arrows(dot) == _rows(_rm_transitions, _words)


def test_the_em_map_draws_every_state_and_transition_of_its_table():
    """AC-2: the EM table's states and transitions, both ways, its several
    triggers between one pair of states on one arrow."""
    dot = minimap.EM_MAP.dot(EM.NONE.name)
    assert _nodes(dot) == {s.name for s in EM}
    assert _arrows(dot) == {
        (_words(trigger), source.name, dest.name)
        for trigger, moves in EM_TRANSITIONS.items()
        for source, dest in moves
    }
    assert '"REVISE" -> "REVISE" [tooltip="propose, reject, accept"];' in dot


def test_the_pxa_map_draws_every_state_and_transition_of_its_table():
    """AC-2: the PXA table's states and transitions, both ways, each arrow
    reading its event letter."""
    dot = minimap.PXA_MAP.dot(CS_pxa.pxa.name)
    assert _nodes(dot) == {s.name for s in CS_pxa}
    assert _arrows(dot) == _rows(_pxa_transitions, _letter)
    assert {m["label"] for m in _ARROW.finditer(dot)} == {"P", "X", "A"}


def test_the_vfd_map_draws_the_vf_and_d_tables_over_the_four_vfd_states():
    """AC-2: every VF and D state and transition is on the VFD map, and
    every arrow is a VF or D transition with the other machine held."""
    dot = minimap.VFD_MAP.dot("vfd")
    nodes = _nodes(dot)
    assert nodes == {"vfd", "Vfd", "VFd", "VFD"}
    assert {n[:-1] for n in nodes} == {s.value for s in CS_vf}
    assert {n[-1] for n in nodes} == {s.value for s in CS_d}
    arrows = _arrows(dot)
    vf_rows = _rows(_vf_transitions, _letter)
    d_rows = _rows(_d_transitions, _letter)
    held_d = {(t, s[:-1], d[:-1]) for t, s, d in arrows if s[-1] == d[-1]}
    held_vf = {(t, s[-1], d[-1]) for t, s, d in arrows if s[:-1] == d[:-1]}
    assert held_d == vf_rows
    assert held_vf == d_rows
    assert len(arrows) == len(vf_rows) + len(d_rows)


def test_the_vfd_states_are_those_the_compound_states_allow():
    """A fix is deployed only once ready: four of the six pairs."""
    assert (
        (CS_vf.vf, CS_d.d),
        (CS_vf.Vf, CS_d.d),
        (CS_vf.VF, CS_d.d),
        (CS_vf.VF, CS_d.D),
    ) == minimap.VFD_STATES
    assert set(view.VFD_BADGES) == set(minimap.VFD_STATES)


@pytest.mark.parametrize(
    "machine",
    [minimap.RM_MAP, minimap.EM_MAP, minimap.PXA_MAP, minimap.VFD_MAP],
    ids=lambda m: m.name,
)
def test_a_map_marks_only_the_state_it_is_given(machine):
    """AC-1: each state, given, is the one marked."""
    for state in machine.states:
        assert _current(machine.dot(state.id)) == [state.id]


def test_a_map_refuses_a_state_it_does_not_have_or_none():
    with pytest.raises(ValueError, match=r"\['VFD'\] is not a RM state"):
        minimap.RM_MAP.dot("VFD")
    with pytest.raises(ValueError, match="no state is not a RM state"):
        minimap.RM_MAP.dot()


def _possible(dot: str) -> list[str]:
    return re.findall(r'^"([^"]+)" \[[^\n]*dashed', dot, re.M)


@pytest.mark.spec("CRD-02-005")
def test_an_unobservable_fix_path_event_marks_every_state_it_allows():
    """A source that cannot observe F and D (VINCE) leaves a vendor aware
    of the case anywhere from aware to deployed, never fix not ready."""
    unknown = {CSEvent.F, CSEvent.D}
    vfd = minimap.vfd_minimap(CS.VfdPxa, unknown)
    assert _current(vfd.dot) == []
    assert _possible(vfd.dot) == ["Vfd", "VFd", "VFD"]
    assert vfd.caption == "❔ Vendor aware, fix ready or fix deployed"
    # An unobservable event that no other state allows changes nothing.
    alone = minimap.vfd_minimap(CS.VfdPxa, {CSEvent.D})
    assert _current(alone.dot) == ["Vfd"]
    assert alone.caption == view.VFD_BADGES[(CS_vf.Vf, CS_d.d)]


@pytest.mark.spec("CRD-02-005")
def test_an_unobservable_public_event_reads_as_unknown_on_its_map():
    pxa = minimap.pxa_minimap(CS_pxa.Pxa, {CSEvent.A})
    assert _current(pxa.dot) == []
    assert _possible(pxa.dot) == ["Pxa", "PxA"]
    assert pxa.caption.endswith("❔ Attacks Observed unknown")
    case = CaseStanding(
        em=EM.NONE, pxa=CS_pxa.Pxa, unobservable=frozenset({CSEvent.A})
    )
    _, from_case = minimap.case_minimaps(case)
    assert from_case == pxa


def test_a_map_refuses_an_arrow_to_no_state_and_a_state_listed_twice():
    state = minimap.MapState(id="a", label="A", tooltip="a")
    with pytest.raises(ValidationError) as caught:
        minimap.MachineMap(
            name="M",
            title="M",
            states=(state, state),
            edges=(minimap.MapEdge(source="a", dest="b", triggers=("go",)),),
        )
    message = str(caught.value)
    assert "states listed twice: ['a']" in message
    assert "arrow end 'b' is not a state" in message


def test_a_label_with_a_quote_is_escaped():
    machine = minimap.MachineMap(
        name='say "hi"',
        title="M",
        states=(minimap.MapState(id="a", label='"A"\\', tooltip="a"),),
        edges=(),
    )
    dot = machine.dot("a")
    assert dot.startswith('digraph "say \\"hi\\"" {')
    assert '"a" [label="\\"A\\"\\\\", tooltip="a"' in dot


def test_each_minimap_reads_its_state_in_words():
    """AC-1, AC-3: the state is marked on its map and named in words,
    never by its enum name."""
    rm = minimap.rm_minimap(RM.ACCEPTED)
    assert (rm.title, rm.caption) == (
        "Report management",
        view.RM_BADGES[RM.ACCEPTED],
    )
    assert _current(rm.dot) == ["ACCEPTED"]
    em = minimap.em_minimap(EM.REVISE)
    assert (em.title, em.caption) == (
        "Embargo management",
        view.EM_BADGES[EM.REVISE],
    )
    assert _current(em.dot) == ["REVISE"]
    pxa = minimap.pxa_minimap(CS_pxa.PXa)
    assert pxa.title == "Public state"
    assert pxa.caption == " · ".join(view.public_badges(CS_pxa.PXa))
    assert _current(pxa.dot) == ["PXa"]
    vfd = minimap.vfd_minimap(CS.VFdPXa)
    assert (vfd.title, vfd.caption) == ("Vendor fix path", "🩹 Fix ready")
    assert _current(vfd.dot) == ["VFd"]
    for state_map in (rm, em, pxa, vfd):
        assert not re.search(
            r"\b[vV][fF][dD]|[pP][xX][aA]\b", state_map.caption
        )


def test_the_case_minimaps_are_its_em_and_public_state():
    case = CaseStanding(em=EM.ACTIVE, pxa=CS_pxa.Pxa)
    em, pxa = minimap.case_minimaps(case)
    assert _current(em.dot) == ["ACTIVE"]
    assert _current(pxa.dot) == ["Pxa"]


VENDOR = "https://vendor.example/actors/vendor"
OTHER_VENDOR = "https://other.example/actors/vendor"


def _unscored(participant: str) -> ParticipantStanding:
    return ParticipantStanding(
        participant=participant,
        rm=RM.RECEIVED,
        case=CaseStanding(em=EM.NONE, pxa=CS_pxa.pxa),
        unscored=UnprojectableParticipant(
            participant=participant,
            reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
            detail="it has no event of its own",
        ),
    )


def test_a_participant_with_no_case_state_history_has_no_fix_path_map():
    (maps,) = minimap.participant_minimaps([_unscored(VENDOR)], {})
    assert maps.label == "Vendor"
    assert _current(maps.rm.dot) == ["RECEIVED"]
    assert maps.vfd is None


def test_two_participants_with_one_name_are_told_apart_by_actor():
    first, second = minimap.participant_minimaps(
        [_unscored(VENDOR), _unscored(OTHER_VENDOR)], {}
    )
    assert first.label == f"Vendor ({VENDOR})"
    assert second.label == f"Vendor ({OTHER_VENDOR})"


def test_a_recorded_vendor_has_its_fix_path_on_its_map():
    """AC-1: a recorded case's vendor's RM and VFD, each marked."""
    path = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"
    analysis = analyse(
        VultronCaseReader(root=RECORDINGS_DIR).read_case(str(path))
    )
    assert analysis.standing is not None
    maps = minimap.participant_minimaps(
        analysis.standing.participants, analysis.actor_names
    )
    vendor = next(m for m in maps if m.label == "Vendor")
    assert _current(vendor.rm.dot) == ["CLOSED"]
    assert vendor.vfd is not None
    assert _current(vendor.vfd.dot) == ["VFd"]
    assert any(m.vfd is None for m in maps)
