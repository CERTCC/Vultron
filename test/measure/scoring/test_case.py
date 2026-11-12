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

"""A multi-party case's per-vendor scores, median and spread (#6069, ADR-0182)."""

from fractions import Fraction

import pytest
from pydantic import ValidationError

from test.measure.history.builders import (
    DEPLOYER,
    OWNER,
    VENDOR,
    VENDOR_2,
    Ledger,
    publish,
    seat_vendor,
    status,
)
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.history import read_case_event_histories
from vultron.measure.scoring import (
    AcrossVendors,
    CaseScoreSummary,
    VendorScore,
    score_case,
    score_prefix,
    score_sequence,
)
from vultron.measure.sequences import (
    CaseStateSequences,
    UnprojectableParticipant,
    UnprojectableReason,
    case_state_sequences,
)

_RECORDINGS = sorted(RECORDINGS_DIR.glob("*/case-actor.jsonl"))
_SCORES = ("expected", "best", "worst")


def _multi_party_ledger() -> Ledger:
    """A vendor that also deploys and fixes, a second vendor that does not,
    and a deployer with no Vendor role; then the case goes public."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    seat_vendor(ledger, VENDOR, "vf", deployer=True)
    ledger.add_status(
        VENDOR, status("v-V", VENDOR, "RECEIVED", vf="Vf", d="d")
    )
    seat_vendor(ledger, VENDOR_2, "Vf")
    ledger.add_status(
        VENDOR, status("v-F", VENDOR, "RECEIVED", vf="VF", d="d")
    )
    ledger.add_status(
        VENDOR, status("v-D", VENDOR, "RECEIVED", vf="VF", d="D")
    )
    ledger.add_status(
        DEPLOYER,
        status("dep-r", DEPLOYER, "RECEIVED", d="d", roles=("DEPLOYER",)),
    )
    ledger.add_status(
        DEPLOYER,
        status("dep-d", DEPLOYER, "RECEIVED", d="D", roles=("DEPLOYER",)),
    )
    publish(ledger, "Pxa")
    return ledger


def _two_party_ledger() -> Ledger:
    """One vendor, aware and fixed, and the case goes public."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add_status(VENDOR, status("v-F", VENDOR, "RECEIVED", vf="VF"))
    publish(ledger, "Pxa")
    return ledger


def _vendor(participant: str, prefix: str) -> VendorScore:
    return VendorScore(participant=participant, score=score_prefix(prefix))


# ---------------------------------------------------------------------------
# AC-1: each vendor's score, their median and spread, the unprojectable
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-05-001")
@pytest.mark.spec("CEH-05-006")
def test_each_vendor_is_scored_alone_by_the_sequence_scorer():
    sequences = case_state_sequences(_multi_party_ledger().history())
    summary = score_case(sequences)
    assert summary.case_id == sequences.case_id
    assert summary.vendors == tuple(
        score_sequence(s) for s in sequences.sequences
    )
    assert [v.participant for v in summary.vendors] == [VENDOR, VENDOR_2]
    assert ["".join(v.score.prefix) for v in summary.vendors] == [
        "VFDP",
        "VP",
    ]


@pytest.mark.parametrize("which", _SCORES)
def test_the_summary_reports_each_scores_median_and_spread(which):
    summary = score_case(case_state_sequences(_multi_party_ledger().history()))
    first, second = (getattr(v.score, which) for v in summary.vendors)
    across = getattr(summary, which)
    assert across is not None
    assert first != second
    assert across.median == (first + second) / 2
    assert across.lowest == min(first, second)
    assert across.highest == max(first, second)
    assert across.spread == abs(first - second)


@pytest.mark.spec("CEH-05-007")
def test_every_unprojectable_participant_is_listed_with_its_reason():
    sequences = case_state_sequences(_multi_party_ledger().history())
    summary = score_case(sequences)
    assert summary.unprojectable == tuple(sequences.unprojectable)
    (deployer,) = [
        u for u in summary.unprojectable if u.participant == DEPLOYER
    ]
    assert deployer.reason is UnprojectableReason.NO_VENDOR_AWARENESS
    assert summary.for_participant(DEPLOYER) is None
    assert summary.for_participant(VENDOR) == summary.vendors[0]


def test_the_summary_serializes_its_medians_and_spreads():
    summary = score_case(case_state_sequences(_multi_party_ledger().history()))
    dumped = summary.model_dump()
    for which in _SCORES:
        assert set(dumped[which]) == {"median", "lowest", "highest", "spread"}
    assert {u["participant"] for u in dumped["unprojectable"]} >= {DEPLOYER}


# ---------------------------------------------------------------------------
# AC-2: a two-party case reduces to its one vendor's score
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("which", _SCORES)
def test_a_two_party_case_is_its_one_vendors_score_with_zero_spread(which):
    sequences = case_state_sequences(_two_party_ledger().history())
    summary = score_case(sequences)
    (only,) = sequences.sequences
    assert summary.vendors == (score_sequence(only),)
    value = getattr(summary.vendors[0].score, which)
    across = getattr(summary, which)
    assert across == AcrossVendors(median=value, lowest=value, highest=value)
    assert across.spread == 0


# ---------------------------------------------------------------------------
# The median and spread themselves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scores", "median", "spread"),
    [
        ([Fraction(3)], Fraction(3), Fraction(0)),
        ([Fraction(5), Fraction(1), Fraction(2)], Fraction(2), Fraction(4)),
        (
            [Fraction(1), Fraction(4), Fraction(2), Fraction(9)],
            Fraction(3),
            Fraction(8),
        ),
        ([Fraction(1, 3), Fraction(1, 2)], Fraction(5, 12), Fraction(1, 6)),
    ],
)
def test_the_median_is_unweighted_and_the_spread_is_the_range(
    scores, median, spread
):
    across = AcrossVendors.of(scores)
    assert across.median == median
    assert across.spread == spread
    assert isinstance(across.median, Fraction)


def test_a_median_of_no_vendors_is_refused():
    with pytest.raises(ValueError, match="at least one vendor"):
        AcrossVendors.of([])


def test_a_median_outside_the_range_is_refused():
    with pytest.raises(ValidationError, match="not between"):
        AcrossVendors(
            median=Fraction(5), lowest=Fraction(1), highest=Fraction(2)
        )


def test_a_case_with_no_vendor_lists_its_participants_and_has_no_median():
    unscored = UnprojectableParticipant(
        participant=DEPLOYER,
        reason=UnprojectableReason.NO_VENDOR_AWARENESS,
        detail="D at log index 3 with no vendor awareness",
    )
    summary = score_case(
        CaseStateSequences(case_id="urn:uuid:case-1", unprojectable=[unscored])
    )
    assert summary.vendors == ()
    assert summary.unprojectable == (unscored,)
    assert (summary.expected, summary.best, summary.worst) == (
        None,
        None,
        None,
    )


# ---------------------------------------------------------------------------
# One answer per participant
# ---------------------------------------------------------------------------


def test_a_vendor_scored_twice_is_refused():
    with pytest.raises(ValidationError, match="scored twice"):
        CaseScoreSummary(
            case_id="urn:uuid:case-1",
            vendors=(_vendor(VENDOR, "V"), _vendor(VENDOR, "VF")),
        )


def test_a_participant_both_scored_and_unprojectable_is_refused():
    with pytest.raises(
        ValidationError,
        match="both scored and reported unprojectable",
    ):
        CaseScoreSummary(
            case_id="urn:uuid:case-1",
            vendors=(_vendor(VENDOR, "V"),),
            unprojectable=(
                UnprojectableParticipant(
                    participant=VENDOR,
                    reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
                    detail="no events",
                ),
            ),
        )


def test_the_summary_holds_no_case_wide_sequence():
    """Several vendors' sequences are never combined (CEH-05-006)."""
    fields = set(CaseScoreSummary.model_fields) | set(
        CaseScoreSummary.model_computed_fields
    )
    assert fields == {
        "case_id",
        "vendors",
        "unprojectable",
        "expected",
        "best",
        "worst",
    }


# ---------------------------------------------------------------------------
# Every committed recording
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.parent.name)
def test_every_recording_summarizes_each_vendor_once(path):
    (history,) = read_case_event_histories([path]).histories.values()
    sequences = case_state_sequences(history)
    summary = score_case(sequences)
    assert [v.participant for v in summary.vendors] == [
        s.participant for s in sequences.sequences
    ]
    assert len(summary.unprojectable) == len(sequences.unprojectable)
    if summary.vendors:
        assert summary.expected is not None
        assert summary.expected.lowest <= summary.expected.median
