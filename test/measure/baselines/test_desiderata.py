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
from vultron.measure.baselines import (
    EXTENDED,
    NEAR_EQUAL_RATIO,
    ONE_VENDOR_MODEL,
    Group,
    ModelName,
    baseline,
    frequency,
    implications,
)
from vultron.measure.baselines.desiderata import _candidates
from vultron.measure.baselines.render import (
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
                n == "random" or n.endswith(".random") or n == "numpy"
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


def test_a_flag_marks_a_share_at_or_above_the_threshold():
    for item in implications():
        assert item.counts_twice == (item.share >= NEAR_EQUAL_RATIO)
        assert 0 < item.share <= 1


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
