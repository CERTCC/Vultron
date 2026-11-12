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

"""Scoring a case-state sequence through its valid completions (#6068, ADR-0182)."""

import ast
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from test.measure.history.builders import VENDOR, Ledger, publish, seat_vendor
from vultron.core.case_states.hypercube import CVDmodel
from vultron.core.states.cs_invariants import (
    CS_EVENTS,
    CSEvent,
    valid_cs_histories,
)
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.measure import scoring
from vultron.measure.baselines import (
    ORIGINAL,
    baseline,
    history_probability,
    prefix_probability,
)
from vultron.measure.history import read_case_event_histories
from vultron.measure.scoring import (
    Completion,
    NotAHistoryPrefixError,
    SequenceScore,
    complete,
    history_score,
    met_desiderata,
    model,
    score,
    score_prefix,
    score_sequence,
)
from vultron.measure.sequences import Placement, case_state_sequences

_HISTORIES = valid_cs_histories()

#: Every accepted prefix: each is a prefix of some valid history (CSB-17-011).
_PREFIXES = sorted(
    {h[:n] for h in _HISTORIES for n in range(len(CS_EVENTS) + 1)}
)


def _label(events) -> str:
    return "".join(events) or "empty"


@pytest.fixture(scope="module")
def legacy_model() -> CVDmodel:
    return CVDmodel()


# ---------------------------------------------------------------------------
# AC-1: exactly the valid completions
# ---------------------------------------------------------------------------


@pytest.mark.spec("CSB-17-011")
@pytest.mark.spec("CSB-17-004")
@pytest.mark.parametrize("prefix", _PREFIXES, ids=_label)
def test_a_prefix_is_scored_through_exactly_its_valid_completions(prefix):
    scored = score_prefix(prefix)
    expected = sorted(h for h in _HISTORIES if h[: len(prefix)] == prefix)
    assert expected, "every accepted prefix has a valid completion"
    assert [c.history for c in scored.completions] == expected
    assert scored.prefix == prefix


@pytest.mark.spec("CSB-17-010")
def test_the_empty_prefix_is_completed_by_all_70_histories():
    assert len(score_prefix(()).completions) == len(_HISTORIES) == 70


def test_a_prefix_may_be_given_as_a_string():
    assert score_prefix("VF") == score_prefix((CSEvent.V, CSEvent.F))


# ---------------------------------------------------------------------------
# AC-2: weighted by the walk from the prefix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", _PREFIXES, ids=_label)
def test_each_completion_is_weighted_by_the_walk_from_the_prefix(prefix):
    scored = score_prefix(prefix)
    for completion in scored.completions:
        assert completion.probability == history_probability(
            completion.history
        ) / prefix_probability(prefix)
    assert sum(c.probability for c in scored.completions) == 1


def test_weights_differ_where_the_walk_is_not_uniform():
    """The walk weights completions, not the count of them: ``V`` leaves
    some completions likelier than others."""
    weights = {c.probability for c in score_prefix("V").completions}
    assert len(weights) > 1


# ---------------------------------------------------------------------------
# AC-3: expected, best and worst; a complete history scores itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("history", _HISTORIES, ids=_label)
def test_a_complete_history_scores_its_existing_score_three_times(
    history, legacy_model
):
    scored = score_prefix(history)
    assert scored.is_complete
    assert [c.history for c in scored.completions] == [history]
    assert scored.expected == scored.best == scored.worst
    assert scored.expected == history_score(history)
    assert float(scored.expected) == pytest.approx(
        legacy_model.score_hist("".join(history))
    )


def test_the_complete_score_sums_one_minus_the_baseline_of_each_met_desideratum():
    history = (
        CSEvent.V,
        CSEvent.F,
        CSEvent.D,
        CSEvent.P,
        CSEvent.X,
        CSEvent.A,
    )
    assert met_desiderata(history) == ORIGINAL
    assert history_score(history) == sum(1 - baseline(d) for d in ORIGINAL)


def test_a_history_meeting_no_desideratum_scores_zero():
    """Attacks, then the exploit, then public awareness, and the vendor
    last: every original desideratum fails."""
    history = "AXPVFD"
    assert met_desiderata(history) == ()
    assert history_score(history) == 0


@pytest.mark.parametrize("bad", ["VF", "FVDPXA", "VFDPXX"])
def test_only_a_complete_history_has_a_complete_score(bad):
    with pytest.raises(
        (VultronValidationError, VultronInvalidStateTransitionError)
    ):
        history_score(bad)


@pytest.mark.parametrize("prefix", _PREFIXES, ids=_label)
def test_expected_is_the_weighted_mean_between_worst_and_best(prefix):
    scored = score_prefix(prefix)
    scores = [history_score(c.history) for c in scored.completions]
    assert scored.best == max(scores)
    assert scored.worst == min(scores)
    assert scored.expected == sum(
        c.probability * s
        for c, s in zip(scored.completions, scores, strict=True)
    )
    assert scored.worst <= scored.expected <= scored.best


def test_an_open_case_reports_a_range():
    scored = score_prefix("VF")
    assert not scored.is_complete
    assert scored.worst < scored.expected < scored.best


def test_the_scores_serialize_exactly():
    dumped = score_prefix("VFDPX").model_dump(mode="json")
    assert set(dumped) == {
        "prefix",
        "completions",
        "expected",
        "best",
        "worst",
    }
    assert Fraction(dumped["expected"]) == score_prefix("VFDPX").expected


# ---------------------------------------------------------------------------
# AC-4: a sequence that is not a prefix is refused with its reason
# ---------------------------------------------------------------------------


@pytest.mark.spec("CSB-17-005")
@pytest.mark.parametrize(
    ("events", "why"),
    [
        ("FV", "'F' cannot fire"),
        ("XA", "ephemeral"),
        ("VV", "more than once"),
        ("VQ", "not a CS event"),
        ((CSEvent.V, 3), "not a CS event"),
    ],
)
def test_a_sequence_that_is_not_a_prefix_is_refused_with_its_reason(
    events, why
):
    with pytest.raises(NotAHistoryPrefixError) as caught:
        score_prefix(events)
    assert why in caught.value.reason
    assert caught.value.events == tuple(events)
    assert caught.value.reason in str(caught.value)


def test_a_one_shot_iterable_is_read_once():
    assert score_prefix(iter("VF")) == score_prefix("VF")


def test_a_sequence_score_names_every_problem_at_once():
    """EH-07-001: a missing completion and a short total both reported."""
    with pytest.raises(ValidationError) as caught:
        SequenceScore(
            prefix=(CSEvent.V, CSEvent.F, CSEvent.D, CSEvent.P),
            completions=(_completion("VFDPAX", Fraction(1, 2)),),
        )
    message = str(caught.value)
    assert "sum to 1/2" in message
    assert "VFDPXA is missing" in message


# ---------------------------------------------------------------------------
# The result model refuses an inconsistent score
# ---------------------------------------------------------------------------


_VFDPXA = tuple(CS_EVENTS)


@pytest.mark.parametrize(
    ("history", "probability"),
    [
        (("V", "F"), Fraction(1)),
        (_VFDPXA, Fraction(0)),
        (_VFDPXA, Fraction(3, 2)),
    ],
)
def test_a_completion_must_be_a_valid_history_with_a_probability(
    history, probability
):
    with pytest.raises(ValidationError):
        Completion(history=history, probability=probability)


def _completion(history, probability=Fraction(1)) -> Completion:
    return Completion(history=tuple(history), probability=probability)


@pytest.mark.parametrize(
    ("prefix", "completions", "problem"),
    [
        ("VFDPXA", [], "at least 1"),
        ("VFX", [_completion("VFDPXA")], "does not extend"),
        (
            "VFDP",
            [
                _completion("VFDPXA", Fraction(1, 2)),
                _completion("VFDPXA", Fraction(1, 2)),
            ],
            "more than once",
        ),
        (
            "VFDP",
            [
                _completion("VFDPXA", Fraction(1, 2)),
                _completion("VFDPAX", Fraction(1, 2)),
            ],
            "not ordered",
        ),
        ("VFDP", [_completion("VFDPAX", Fraction(1, 2))], "sum to 1/2"),
        ("VFDP", [_completion("VFDPXA")], "VFDPAX is missing"),
        (
            "VFDP",
            [
                _completion("VFDPAX", Fraction(1, 4)),
                _completion("VFDPXA", Fraction(3, 4)),
            ],
            "the walk gives 1/2",
        ),
        ("FV", [_completion("VFDPXA")], "FV is not a valid prefix"),
    ],
)
def test_a_sequence_score_refuses_inconsistent_completions(
    prefix, completions, problem
):
    with pytest.raises(ValidationError, match=problem):
        SequenceScore(
            prefix=tuple(CSEvent(e) for e in prefix),
            completions=tuple(completions),
        )


# ---------------------------------------------------------------------------
# Per-vendor sequences
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-05-005")
@pytest.mark.spec("CEH-05-009")
def test_a_vendor_sequence_is_scored_with_its_implied_events():
    """Recorded ``V, X, A``: ``pX`` forces ``P``, so the projection implies
    it and the score is that of ``VXPA``."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    publish(ledger, "pXa")
    publish(ledger, "pXA")
    (sequence,) = case_state_sequences(ledger.history()).sequences
    assert Placement.IMPLIED in {m.placement for m in sequence.events}

    scored = score_sequence(sequence)
    assert scored.participant == VENDOR
    assert scored.score == score_prefix("VXPA")


_RECORDINGS = sorted(RECORDINGS_DIR.glob("*/case-actor.jsonl"))


@pytest.mark.spec("CEH-05-005")
@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.parent.name)
def test_every_vendor_of_a_recording_gets_a_score_and_a_range(path):
    (history,) = read_case_event_histories([path]).histories.values()
    for sequence in case_state_sequences(history).sequences:
        scored = score_sequence(sequence)
        assert scored.participant == sequence.participant
        assert scored.score.prefix == sequence.kinds
        assert scored.score.worst <= scored.score.expected <= scored.score.best


def test_some_recording_has_a_vendor_to_score():
    assert any(
        case_state_sequences(h).sequences
        for path in _RECORDINGS
        for h in read_case_event_histories([path]).histories.values()
    )


# ---------------------------------------------------------------------------
# The scorer never reaches the legacy case-state package
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module", [scoring, complete, model, score], ids=lambda m: m.__name__
)
def test_the_scorer_imports_no_legacy_case_state_module(module):
    """``notes/case-state-model.md``: new code validates through
    ``vultron.core.states.cs_invariants``, never ``vultron.core.case_states``.

    The check reads the scorer's own imports: ``vultron.core.states`` itself
    still loads the legacy module, which is not the scorer's to change.
    """
    tree = ast.parse(Path(module.__file__).read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported
    assert not any(
        name == "vultron.core.case_states"
        or name.startswith("vultron.core.case_states.")
        for name in imported
    )
