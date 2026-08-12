#!/usr/bin/env python
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

"""Tests for `vultron.core.states.cs_invariants`.

The exhaustive tests here are the regression anchor for the re-expression of
the legacy `vultron.core.case_states` rules against the current enum models
(issue #2237, ADR-0060).  They compare the new implementation against the
legacy string-pattern implementation over the *whole* state space — 64
candidate states, 32x32 candidate transitions, and all 720 event
permutations — so any drift between the two is caught immediately, and the
legacy module can be retired only once these comparisons are deliberately
removed.
"""

from itertools import permutations

import pytest

from vultron.core.case_states.validations import (
    is_valid_history as legacy_is_valid_history,
    is_valid_state as legacy_is_valid_state,
    is_valid_transition as legacy_is_valid_transition,
)
from vultron.core.states.cs import (
    CS,
    CS_pxa,
    CS_vfd,
    PXA_Trigger,
    VFD_Trigger,
    is_vfd_vendor_aware,
)
from vultron.core.states.cs_invariants import (
    CS_EVENT_TO_PXA_TRIGGER,
    CS_EVENT_TO_VFD_TRIGGER,
    CS_EVENTS,
    CSEvent,
    PXA_EVENTS,
    VFD_EVENTS,
    apply_cs_event,
    cs_dimensions,
    cs_from_dimensions,
    cs_transition_event,
    ensure_valid_cs_history,
    ensure_valid_cs_transition,
    is_ephemeral_cs_state,
    is_valid_cs_history,
    is_valid_cs_history_prefix,
    is_valid_cs_transition,
    next_cs_states,
    replay_cs_history,
    required_next_cs_events,
    valid_cs_histories,
)
from vultron.errors import (
    ValidationError as LegacyValidationError,
    VultronInvalidStateTransitionError,
    VultronValidationError,
)

# --- helpers ---------------------------------------------------------------


def _all_candidate_state_strings() -> list[str]:
    """Every one of the 2**6 vfdpxa letter combinations, valid or not."""
    combos = []
    for i in range(2**6):
        bits = format(i, "06b")
        combos.append(
            "".join(
                letter.upper() if bit == "1" else letter
                for letter, bit in zip("vfdpxa", bits)
            )
        )
    return combos


def _legacy_valid_states() -> set[str]:
    valid = set()
    for candidate in _all_candidate_state_strings():
        try:
            legacy_is_valid_state(candidate)
        except LegacyValidationError:
            continue
        valid.add(candidate)
    return valid


def _legacy_valid_transitions() -> set[tuple[str, str]]:
    states = sorted(_legacy_valid_states())
    edges = set()
    for src in states:
        for dst in states:
            try:
                legacy_is_valid_transition(src, dst)
            except LegacyValidationError:
                continue
            edges.add((src, dst))
    return edges


def _legacy_valid_histories() -> set[str]:
    valid = set()
    for perm in permutations("VFDPXA"):
        history = "".join(perm)
        try:
            legacy_is_valid_history(history)
        except LegacyValidationError:
            continue
        valid.add(history)
    return valid


def _as_string(history) -> str:
    return "".join(event.value for event in history)


# --- CSEvent ---------------------------------------------------------------


def test_cs_events_are_canonical_order():
    assert _as_string(CS_EVENTS) == "VFDPXA"


def test_event_dimension_partition():
    assert VFD_EVENTS | PXA_EVENTS == set(CS_EVENTS)
    assert not VFD_EVENTS & PXA_EVENTS


def test_event_trigger_maps_cover_their_dimensions():
    assert set(CS_EVENT_TO_VFD_TRIGGER) == VFD_EVENTS
    assert set(CS_EVENT_TO_PXA_TRIGGER) == PXA_EVENTS
    assert set(CS_EVENT_TO_VFD_TRIGGER.values()) == set(VFD_Trigger)
    assert set(CS_EVENT_TO_PXA_TRIGGER.values()) == set(PXA_Trigger)


@pytest.mark.parametrize(
    "event,trigger",
    [
        (CSEvent.V, VFD_Trigger.V),
        (CSEvent.F, VFD_Trigger.F),
        (CSEvent.D, VFD_Trigger.D),
    ],
)
def test_vfd_trigger_map_pairs_by_letter(event, trigger):
    assert CS_EVENT_TO_VFD_TRIGGER[event] is trigger


@pytest.mark.parametrize(
    "event,trigger",
    [
        (CSEvent.P, PXA_Trigger.P),
        (CSEvent.X, PXA_Trigger.X),
        (CSEvent.A, PXA_Trigger.A),
    ],
)
def test_pxa_trigger_map_pairs_by_letter(event, trigger):
    assert CS_EVENT_TO_PXA_TRIGGER[event] is trigger


# --- compound state validity ----------------------------------------------


def test_cs_enum_is_exactly_the_legacy_valid_state_set():
    """The 32 CS members are the legacy model's 32 valid states.

    This is the state-validity rule (`vF` and `fD` are impossible) expressed
    structurally: `CS_vfd` has only four members, so the impossible
    combinations cannot be constructed at all.
    """
    assert {state.name for state in CS} == _legacy_valid_states()


def test_cs_has_32_states():
    assert len(list(CS)) == 32


def test_impossible_vfd_combinations_are_not_constructible():
    """No CS_vfd member has F without V, or D without F."""
    for state in CS_vfd:
        vendor_aware, fix_ready, fix_deployed = (
            char.isupper() for char in state.name
        )
        assert not (fix_ready and not vendor_aware)
        assert not (fix_deployed and not fix_ready)


def test_dimension_round_trip():
    for state in CS:
        assert cs_from_dimensions(*cs_dimensions(state)) is state


def test_cs_from_dimensions_covers_the_full_cross_product():
    pairs = {
        cs_from_dimensions(vfd_state, pxa_state)
        for vfd_state in CS_vfd
        for pxa_state in CS_pxa
    }
    assert pairs == set(CS)


# --- ephemeral states -----------------------------------------------------


def test_ephemeral_states_are_the_twelve_vp_and_px_states():
    ephemeral = {state.name for state in CS if is_ephemeral_cs_state(state)}
    expected = {
        state.name
        for state in CS
        # vP: public aware, vendor unaware
        if (state.name[3] == "P" and state.name[0] == "v")
        # pX: exploit public, public unaware
        or (state.name[4] == "X" and state.name[3] == "p")
    }
    assert ephemeral == expected
    assert len(ephemeral) == 12


@pytest.mark.parametrize(
    "state,expected",
    [
        (CS.vfdPxa, {CSEvent.V}),
        (CS.vfdPXA, {CSEvent.V}),
        (CS.vfdpXa, {CSEvent.P}),
        (CS.VFDpXA, {CSEvent.P}),
        (CS.vfdpxa, set()),
        (CS.VfdPxa, set()),
        (CS.VFDPXA, set()),
    ],
)
def test_required_next_cs_events(state, expected):
    assert required_next_cs_events(state) == frozenset(expected)


def test_the_two_ephemeral_rules_are_mutually_exclusive():
    """vP requires P set; pX requires P unset — they cannot both apply."""
    for state in CS:
        required = required_next_cs_events(state)
        assert len(required) <= 1


def test_ephemeral_states_have_exactly_one_successor():
    for state in CS:
        if is_ephemeral_cs_state(state):
            assert len(next_cs_states(state)) == 1


# --- transition validity --------------------------------------------------


def test_transition_set_matches_legacy_exactly():
    """The re-expressed transition rule admits the legacy model's 58 edges."""
    new_edges = {
        (src.name, dst.name)
        for src in CS
        for dst in CS
        if is_valid_cs_transition(src, dst)
    }
    assert new_edges == _legacy_valid_transitions()


def test_there_are_58_valid_transitions():
    count = sum(
        1 for src in CS for dst in CS if is_valid_cs_transition(src, dst)
    )
    assert count == 58


def test_every_transition_changes_exactly_one_dimension():
    for src in CS:
        for dst in next_cs_states(src):
            assert cs_transition_event(src, dst) is not None


def test_transitions_are_monotone():
    """No transition ever un-sets a bit; CS events are irreversible."""
    for src in CS:
        for dst in next_cs_states(src):
            for before, after in zip(src.name, dst.name):
                assert not (before.isupper() and after.islower())


def test_null_transition_rejected_by_default_and_allowed_when_asked():
    assert not is_valid_cs_transition(CS.Vfdpxa, CS.Vfdpxa)
    assert is_valid_cs_transition(CS.Vfdpxa, CS.Vfdpxa, allow_null=True)


def test_ensure_valid_cs_transition_allows_null_when_asked():
    ensure_valid_cs_transition(CS.Vfdpxa, CS.Vfdpxa, allow_null=True)


@pytest.mark.parametrize(
    "src,dst",
    [
        (CS.vfdpxa, CS.Vfdpxa),  # V
        (CS.Vfdpxa, CS.VFdpxa),  # F
        (CS.VFdpxa, CS.VFDpxa),  # D
        (CS.Vfdpxa, CS.VfdPxa),  # P
        (CS.VfdPxa, CS.VfdPXa),  # X
        (CS.VfdPxa, CS.VfdPxA),  # A
        (CS.vfdPxa, CS.VfdPxa),  # ephemeral vP resolved by V
        (CS.vfdpXa, CS.vfdPXa),  # ephemeral pX resolved by P
    ],
)
def test_valid_transitions(src, dst):
    assert is_valid_cs_transition(src, dst)
    ensure_valid_cs_transition(src, dst)


@pytest.mark.parametrize(
    "src,dst,reason",
    [
        (CS.Vfdpxa, CS.vfdpxa, "not monotone"),
        (CS.vfdpxa, CS.VfdPxa, "two dimensions change"),
        (CS.vfdpxa, CS.VFdpxa, "F requires V first"),
        (CS.Vfdpxa, CS.VFDpxa, "F and D cannot both fire at once"),
        (CS.vfdpxa, CS.VFDPXA, "everything changes at once"),
        (CS.vfdPxa, CS.vfdPxA, "vP requires V next"),
        (CS.vfdPxa, CS.vfdPXa, "vP requires V next"),
        (CS.vfdpXa, CS.vfdpXA, "pX requires P next"),
        (CS.VFDpXa, CS.VFDpXA, "pX requires P next"),
    ],
)
def test_invalid_transitions(src, dst, reason):
    assert not is_valid_cs_transition(
        src, dst
    ), f"{src.name} -> {dst.name} should be rejected: {reason}"
    with pytest.raises(VultronInvalidStateTransitionError):
        ensure_valid_cs_transition(src, dst)


def test_ephemeral_rejection_message_names_the_required_event():
    with pytest.raises(VultronInvalidStateTransitionError) as exc_info:
        ensure_valid_cs_transition(CS.vfdpXa, CS.vfdpXA)
    message = str(exc_info.value)
    assert "ephemeral" in message
    assert "'P'" in message


def test_terminal_state_has_no_successors():
    assert next_cs_states(CS.VFDPXA) == ()


def test_initial_state_successors():
    """From vfdpxa only V, P, X and A can fire — F and D need prerequisites."""
    events = {
        cs_transition_event(CS.vfdpxa, dst)
        for dst in next_cs_states(CS.vfdpxa)
    }
    assert events == {CSEvent.V, CSEvent.P, CSEvent.X, CSEvent.A}


def test_cs_transition_event_returns_none_for_non_unit_diffs():
    assert cs_transition_event(CS.vfdpxa, CS.vfdpxa) is None
    assert cs_transition_event(CS.vfdpxa, CS.VfdPxa) is None


def test_cs_transition_event_identifies_the_changed_dimension():
    assert cs_transition_event(CS.vfdpxa, CS.Vfdpxa) is CSEvent.V
    assert cs_transition_event(CS.vfdpxa, CS.vfdpxA) is CSEvent.A


# --- apply_cs_event -------------------------------------------------------


def test_apply_cs_event_advances_the_state():
    assert apply_cs_event(CS.vfdpxa, CSEvent.V) is CS.Vfdpxa
    assert apply_cs_event(CS.Vfdpxa, CSEvent.F) is CS.VFdpxa
    assert apply_cs_event(CS.vfdpXa, CSEvent.P) is CS.vfdPXa


def test_apply_cs_event_agrees_with_the_transition_predicate():
    for state in CS:
        for event in CS_EVENTS:
            try:
                result = apply_cs_event(state, event)
            except VultronInvalidStateTransitionError:
                assert not any(
                    cs_transition_event(state, dst) is event
                    for dst in next_cs_states(state)
                )
                continue
            assert is_valid_cs_transition(state, result)
            assert cs_transition_event(state, result) is event


def test_apply_cs_event_rejects_a_repeated_event():
    with pytest.raises(VultronInvalidStateTransitionError, match="already"):
        apply_cs_event(CS.Vfdpxa, CSEvent.V)


def test_apply_cs_event_rejects_an_unmet_prerequisite():
    with pytest.raises(
        VultronInvalidStateTransitionError, match="prerequisite"
    ):
        apply_cs_event(CS.vfdpxa, CSEvent.F)


def test_apply_cs_event_rejects_a_violated_ephemeral_rule():
    with pytest.raises(VultronInvalidStateTransitionError, match="ephemeral"):
        apply_cs_event(CS.vfdpXa, CSEvent.A)


def test_apply_cs_event_reports_the_nearest_blocker_when_several_apply():
    """F from vfdpXa is blocked twice over: pX is ephemeral *and* V is unmet.

    The message names the ephemeral rule, because that is the constraint the
    caller has to satisfy first.
    """
    with pytest.raises(VultronInvalidStateTransitionError) as excinfo:
        apply_cs_event(CS.vfdpXa, CSEvent.F)

    message = str(excinfo.value)
    assert "ephemeral" in message
    assert "prerequisite" not in message
    # Both blockers really are live, so this is a precedence choice, not luck.
    assert required_next_cs_events(CS.vfdpXa) == frozenset({CSEvent.P})
    assert not is_vfd_vendor_aware(cs_dimensions(CS.vfdpXa)[0])


# --- history validity -----------------------------------------------------


def test_valid_histories_match_legacy_exactly():
    """The causal replay admits exactly the legacy model's 70 histories.

    This is the equivalence proof for `is_valid_history`: the legacy
    permutation-ordering formulation and the replay-through-transitions
    formulation accept the same set.
    """
    new = {_as_string(history) for history in valid_cs_histories()}
    assert new == _legacy_valid_histories()


def test_there_are_70_valid_histories():
    assert len(valid_cs_histories()) == 70


def test_valid_histories_are_distinct():
    histories = valid_cs_histories()
    assert len(set(histories)) == len(histories)


def test_is_valid_cs_history_agrees_with_legacy_on_every_permutation():
    legacy = _legacy_valid_histories()
    for perm in permutations(CS_EVENTS):
        assert is_valid_cs_history(list(perm)) == (_as_string(perm) in legacy)


def test_is_valid_cs_history_agrees_with_valid_cs_histories():
    enumerated = set(valid_cs_histories())
    for perm in permutations(CS_EVENTS):
        assert is_valid_cs_history(list(perm)) == (perm in enumerated)


@pytest.mark.parametrize(
    "history",
    [
        "VFDPXA",
        "VPFXDA",
        "PVFDXA",  # V immediately follows P
        "VFXPDA",  # P immediately follows X
        "AVFDPX",
    ],
)
def test_accepted_histories(history):
    events = [CSEvent(char) for char in history]
    assert is_valid_cs_history(events)
    ensure_valid_cs_history(events)


@pytest.mark.parametrize(
    "history,reason",
    [
        ("FVDPXA", "V must precede F"),
        ("VDFPXA", "F must precede D"),
        ("VFDXAP", "P must precede X or immediately follow it"),
        ("PAVFDX", "V must precede P or immediately follow it"),
        ("XAPVFD", "P must immediately follow X"),
    ],
)
def test_rejected_histories(history, reason):
    events = [CSEvent(char) for char in history]
    assert not is_valid_cs_history(
        events
    ), f"{history} should be rejected: {reason}"
    with pytest.raises(
        (VultronValidationError, VultronInvalidStateTransitionError)
    ):
        ensure_valid_cs_history(events)


def test_every_valid_history_reaches_the_terminal_state():
    for history in valid_cs_histories():
        assert replay_cs_history(history) is CS.VFDPXA


def test_is_valid_cs_history_rejects_incomplete_and_repeated_sequences():
    assert not is_valid_cs_history([CSEvent.V, CSEvent.F])
    assert not is_valid_cs_history([CSEvent.V] * 6)


def test_ensure_valid_cs_history_reports_missing_events():
    with pytest.raises(VultronValidationError, match="missing"):
        ensure_valid_cs_history([CSEvent.V, CSEvent.F, CSEvent.D])


def test_ensure_valid_cs_history_reports_repeated_events():
    with pytest.raises(VultronValidationError, match="more than once"):
        ensure_valid_cs_history([CSEvent.V, CSEvent.V])


# --- history prefixes -----------------------------------------------------


def test_empty_prefix_is_valid():
    assert is_valid_cs_history_prefix([])


def test_every_prefix_of_every_valid_history_is_valid():
    for history in valid_cs_histories():
        for length in range(len(history) + 1):
            assert is_valid_cs_history_prefix(history[:length])


@pytest.mark.parametrize(
    "prefix",
    [
        [CSEvent.V],
        [CSEvent.V, CSEvent.F],
        [CSEvent.X],  # ends in ephemeral pX — nothing has come next yet
        [CSEvent.P],  # ends in ephemeral vP
        [CSEvent.A, CSEvent.V],
    ],
)
def test_accepted_prefixes(prefix):
    assert is_valid_cs_history_prefix(prefix)


@pytest.mark.parametrize(
    "prefix",
    [
        [CSEvent.F],  # F before V
        [CSEvent.D],  # D before F
        [CSEvent.X, CSEvent.A],  # pX requires P next
        [CSEvent.P, CSEvent.A],  # vP requires V next
        [CSEvent.V, CSEvent.V],  # repeated event
    ],
)
def test_rejected_prefixes(prefix):
    assert not is_valid_cs_history_prefix(prefix)


def test_prefix_can_start_from_a_non_initial_state():
    assert is_valid_cs_history_prefix([CSEvent.F], start=CS.Vfdpxa)
    assert not is_valid_cs_history_prefix([CSEvent.V], start=CS.Vfdpxa)


def test_replay_from_a_non_initial_state():
    assert replay_cs_history([CSEvent.F], start=CS.Vfdpxa) is CS.VFdpxa


def test_replay_rejects_repeated_events():
    with pytest.raises(VultronValidationError, match="more than once"):
        replay_cs_history([CSEvent.V, CSEvent.P, CSEvent.V])


def test_replay_of_empty_sequence_returns_the_start_state():
    assert replay_cs_history([]) is CS.vfdpxa
    assert replay_cs_history([], start=CS.VFdPxa) is CS.VFdPxa
