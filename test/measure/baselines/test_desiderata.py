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

"""Each extended desideratum has an exact baseline, and implied pairs are listed (#6067)."""

import ast
from fractions import Fraction
from pathlib import Path

import pytest

import vultron.measure.baselines as baselines_package
import vultron.measure.baselines.desiderata as desiderata_module
from vultron.measure.baselines import (
    EXTENDED,
    NEAR_EQUAL_RATIO,
    ONE_VENDOR_MODEL,
    Group,
    ModelName,
    baseline,
    frequency,
    implications,
    implies,
)
from vultron.measure.baselines.desiderata import _candidates
from vultron.measure.baselines.render import (
    _exact,
    extended_baseline_table,
    implication_table,
    original_baseline_table,
)
from vultron.measure.baselines.walk import OrderingQuery

_DOCS = (
    Path(__file__).resolve().parents[3] / "docs" / "topics" / "measuring_cvd"
)


def _named(notation: str):
    (found,) = [d for d in EXTENDED if d.notation == notation]
    return found


@pytest.mark.parametrize("desideratum", EXTENDED, ids=lambda d: d.notation)
def test_each_extended_desideratum_has_an_exact_baseline(desideratum):
    f_d = baseline(desideratum)
    assert isinstance(f_d, Fraction)
    # A desideratum that chance always meets or never meets measures nothing.
    assert 0 < f_d < 1


def test_only_the_desideratum_relating_two_vendors_uses_two():
    two = [d for d in EXTENDED if d.model is ModelName.TWO_VENDOR]
    assert [d.notation for d in two] == [r"$\evV_i \prec \evF_j$"]
    assert all(
        d.model is ModelName.ONE_VENDOR for d in EXTENDED if d not in two
    )


def test_the_couplings_move_a_baseline_off_the_six_event_value():
    # F ≺ P is 1/9 over six events; a fix needing the report accepted first
    # makes it rarer by chance.
    assert baseline(_named(r"$\evF_i \prec \evP$")) == Fraction(1, 24)


def test_no_baseline_comes_from_sampling():
    root = Path(baselines_package.__file__).parent
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(
                n.split(".")[0] in {"random", "numpy", "scipy"}
                or n.endswith(".random")
                for n in names
            ), f"{path.name} imports {names}"


def _pairs() -> set[tuple[str, str]]:
    return {(i.stronger.notation, i.weaker.notation) for i in implications()}


@pytest.mark.parametrize(
    ("stronger", "weaker"),
    [
        # process_model_desiderata.md § "The desiderata are not independent".
        (r"$\evAc_i \prec \evP$", r"$\evV \prec \evP$"),
        (r"$\evAc_i \prec \evP$", r"$\evVa_i \prec \evP$"),
        # The page's compound: in the model ExOwn ≺ P holds whenever ExOwn
        # occurs, so F_i ≺ ExOwn alone implies F_i ≺ P.
        (r"$\evF_i \prec \evExOwn$", r"$\evF_i \prec \evP$"),
    ],
)
def test_the_pages_implications_are_found(stronger, weaker):
    assert (stronger, weaker) in _pairs()


def test_each_listed_implication_holds_by_its_frequencies():
    queries = dict((d.notation, q) for d, q in _candidates())
    assert implications()
    for item in implications():
        strong = queries[item.stronger.notation]
        weak = queries[item.weaker.notation]
        both = OrderingQuery(
            strong.orderings + weak.orderings, strong.given | weak.given
        )
        alone = OrderingQuery(strong.orderings, strong.given | weak.given)
        assert frequency(ONE_VENDOR_MODEL, both) == frequency(
            ONE_VENDOR_MODEL, alone
        )


def test_a_non_implication_is_not_listed():
    pairs = _pairs()
    assert (r"$\evAc_i \prec \evA$", r"$\evAc_i \prec \evP$") not in pairs
    assert (r"$\evE \prec \evP$", r"$\evExOwn \prec \evP$") not in pairs


@pytest.mark.parametrize("signal", ["X", "A"])
def test_the_threat_signals_make_three_embargo_desiderata_one(signal):
    # No embargo is active beside P, X or A (CSB-18-002 to CSB-18-004), so an
    # embargo that starts, or ends on its own terms, does so before all three.
    flagged = {
        (i.stronger.notation, i.weaker.notation)
        for i in implications()
        if i.equivalent and i.counts_twice
    }
    for event in (r"\evE", r"\evExOwn"):
        assert (
            rf"${event} \prec \evP$",
            rf"${event} \prec \ev{signal}$",
        ) in flagged


def test_only_the_equivalent_pairs_count_twice():
    flagged = [i for i in implications() if i.counts_twice]
    assert flagged
    assert all(i.equivalent and i.share == 1 for i in flagged)
    # The largest share of a strict implication is well under the threshold.
    strict = [i.share for i in implications() if not i.equivalent]
    assert max(strict) < NEAR_EQUAL_RATIO


def test_a_stronger_frequency_never_exceeds_the_weaker():
    for item in implications():
        assert item.stronger_frequency <= item.weaker_frequency


def _implication(stronger: str, weaker: str):
    (item,) = [
        i
        for i in implications()
        if (i.stronger.notation, i.weaker.notation) == (stronger, weaker)
    ]
    return item


def test_the_frequencies_are_taken_in_the_scope_of_both():
    # Va_i ≺ P is scoped to vendors whose report reaches Valid, so F_i ≺ P is
    # taken there too, and falls below its own baseline of 1/24.
    item = _implication(r"$\evF_i \prec \evP$", r"$\evVa_i \prec \evP$")
    assert baseline(item.stronger) == Fraction(1, 24)
    assert (item.stronger_frequency, item.weaker_frequency) == (
        Fraction(1, 36),
        Fraction(1, 6),
    )
    assert item.share == Fraction(1, 6)


def test_the_frequencies_are_taken_in_the_one_vendor_model():
    # F ≺ X is an original desideratum (1/3 in the six-event model); in the
    # one-vendor model its frequency is 5/27.
    item = _implication(r"$\evF_i \prec \evP$", r"$\evF \prec \evX$")
    assert baseline(item.weaker) == Fraction(1, 3)
    assert item.weaker_frequency == Fraction(5, 27)
    assert item.share == Fraction(1, 24) / Fraction(5, 27)


def test_a_pair_whose_weaker_never_holds_in_scope_is_left_out(monkeypatch):
    # No share is defined when the weaker never holds; such a pair is skipped
    # rather than divided by zero.
    monkeypatch.setattr(
        desiderata_module, "_frequency", lambda *_: Fraction(0)
    )
    assert desiderata_module.implications.__wrapped__() == ()


def test_an_equivalent_pair_is_listed_once():
    pairs = _pairs()
    assert (r"$\evE \prec \evP$", r"$\evE \prec \evX$") in pairs
    assert (r"$\evE \prec \evX$", r"$\evE \prec \evP$") not in pairs


def test_a_pair_whose_weaker_always_holds_in_scope_is_left_out():
    # Among cases whose embargo ends on its own terms an embargo always
    # started, so F_i ≺ ExOwn implying E ≺ P says nothing about skill.
    queries = dict((d.notation, q) for d, q in _candidates())
    strong = queries[r"$\evF_i \prec \evExOwn$"]
    weak = queries[r"$\evE \prec \evP$"]
    assert implies(ONE_VENDOR_MODEL, strong, weak)
    assert (r"$\evF_i \prec \evExOwn$", r"$\evE \prec \evP$") not in _pairs()


def test_the_tables_print_every_desideratum():
    table = extended_baseline_table()
    for d in EXTENDED:
        assert d.notation in table
    assert original_baseline_table().count("\n") == 12 + 2
    assert implication_table().count("\n") == len(implications()) + 2


def test_the_groups_are_the_pages_groups():
    assert {d.group for d in EXTENDED} == {
        Group.EMBARGO,
        Group.REPORT_HANDLING,
        Group.MULTI_PARTY,
    }


@pytest.mark.parametrize(
    ("page", "renderer"),
    [
        ("process_model_desiderata.md", "extended_baseline_table"),
        ("process_model_desiderata.md", "implication_table"),
        ("random_walk.md", "original_baseline_table"),
    ],
)
def test_the_pages_print_the_computed_tables(page, renderer):
    text = (_DOCS / page).read_text(encoding="utf-8")
    assert f"print({renderer}())" in text


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (Fraction(1), "1"),
        (Fraction(2, 23), "2/23"),
        (Fraction(1, 10_007), "—"),
    ],
)
def test_a_baseline_prints_as_a_fraction_only_when_short(value, shown):
    assert _exact(value) == shown
