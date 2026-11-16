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

"""How small the shifts are that decide a band, and how deep the layers go (#6450).

ADR-0200's sign test is strict.  These tests record which bands rest on very
small parts: counting each part of at most a small threshold as zero
changes the band of publication now and of ending the embargo on its own
terms, and of no other move.  The research page
``docs/topics/measuring_cvd/move_bands.md`` reports the sizes.
"""

from fractions import Fraction

import pytest

from test.measure.advice.cases import CASES, Case
from test.measure.advice.pathologies import ALL_CASES
from vultron.measure.advice import Band, band, layers, move_shifts

THRESHOLDS = (Fraction(1, 100), Fraction(1, 20))
"""Small thresholds against shifts whose largest parts are near 2."""


def _changed(case: Case, threshold: Fraction) -> dict[str, tuple[Band, Band]]:
    shifts = move_shifts(case.prefix, case.moves)
    return {
        str(m.event): (band(s), band(s, threshold))
        for m, s in shifts.items()
        if band(s) is not band(s, threshold)
    }


@pytest.mark.parametrize("threshold", THRESHOLDS, ids=str)
@pytest.mark.parametrize("case", CASES, ids=str)
def test_only_publication_and_an_own_terms_end_change_band(
    case: Case, threshold: Fraction
):
    assert set(_changed(case, threshold)) <= {"P", "ExOwn"}


def test_publication_now_changes_band_under_a_small_threshold():
    changed = {
        case.name: _changed(case, Fraction(1, 20)).get("P") for case in CASES
    }
    # With no unaware vendor, publication now loses its small gain for the
    # ready vendor and is unhelpful; with one, it loses the small losses and
    # is harm-free.
    assert changed == {
        "ready-unready embargo": (Band.TRADE_OFF, Band.UNHELPFUL),
        "ready-unready no-embargo": (Band.TRADE_OFF, Band.UNHELPFUL),
        "unready-unready embargo": None,
        "unready-unready no-embargo": None,
        "ready-unready-unaware embargo": (Band.TRADE_OFF, Band.HARM_FREE),
        "ready-unready-unaware no-embargo": (Band.TRADE_OFF, Band.HARM_FREE),
        "deployed-ready-unready-unaware embargo": (
            Band.TRADE_OFF,
            Band.HARM_FREE,
        ),
        "deployed-ready-unready-unaware no-embargo": (
            Band.TRADE_OFF,
            Band.HARM_FREE,
        ),
    }


def test_the_layers_are_three_to_five_deep():
    depth = {
        case.name: max(layers(move_shifts(case.prefix, case.moves)).values())
        for case in ALL_CASES
    }
    assert depth == {
        "ready-unready embargo": 3,
        "ready-unready no-embargo": 3,
        "unready-unready embargo": 5,
        "unready-unready no-embargo": 4,
        "ready-unready-unaware embargo": 3,
        "ready-unready-unaware no-embargo": 3,
        "deployed-ready-unready-unaware embargo": 3,
        "deployed-ready-unready-unaware no-embargo": 3,
        "ready-unready embargo, three coordinator moves": 2,
    }
