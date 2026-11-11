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

"""The baseline tables, as Markdown, for the Measuring CVD pages.

The pages print these from ``markdown-exec`` blocks, so the published numbers
are always the ones this package computes, never a hand-copied table.
"""

from collections.abc import Iterable
from fractions import Fraction

from vultron.measure.baselines.desiderata import (
    EXTENDED,
    NEAR_EQUAL_RATIO,
    ORIGINAL,
    Desideratum,
    baseline,
    implications,
)

_SHORT_DENOMINATOR = 10_000


def _decimal(value: Fraction) -> str:
    return f"{float(value):.3f}"


def _exact(value: Fraction) -> str:
    """The fraction itself when it is short enough to read, else a dash."""
    if value.denominator == 1:
        return str(value.numerator)
    if value.denominator < _SHORT_DENOMINATOR:
        return f"{value.numerator}/{value.denominator}"
    return "—"


def _table(header: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    head = list(header)
    lines = [
        "| " + " | ".join(head) + " |",
        "|" + "|".join("---" for _ in head) + "|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _scope(desideratum: Desideratum) -> str:
    return desideratum.scope or "every case"


def extended_baseline_table() -> str:
    """The extended desiderata, each with its model and exact baseline."""
    return _table(
        ("Group", "Desideratum", "Measured over", "Model", "$f_d$", "Exact"),
        (
            (
                d.group.value,
                d.notation,
                _scope(d),
                d.model.value,
                _decimal(baseline(d)),
                _exact(baseline(d)),
            )
            for d in EXTENDED
        ),
    )


def original_baseline_table() -> str:
    """The twelve original desiderata with the exact baselines of the six-event walk."""
    return _table(
        ("Desideratum", "$f_d$", "Exact"),
        (
            (d.notation, _decimal(baseline(d)), _exact(baseline(d)))
            for d in ORIGINAL
        ),
    )


def implication_table() -> str:
    """Every implication pair, with both frequencies in one scope and the near-equal flag."""
    flag = f"{float(NEAR_EQUAL_RATIO):.0%}"
    return _table(
        (
            "Stronger",
            "Weaker",
            "$f$ stronger",
            "$f$ weaker",
            "Share",
            f"Counts twice (share ≥ {flag})",
        ),
        (
            (
                i.stronger.notation,
                i.weaker.notation + (" (equivalent)" if i.equivalent else ""),
                _decimal(i.stronger_frequency),
                _decimal(i.weaker_frequency),
                _decimal(i.share),
                "**yes**" if i.counts_twice else "no",
            )
            for i in implications()
        ),
    )
