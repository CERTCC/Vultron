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

"""The desiderata score of a complete case-state history.

A complete history scores ``1 - f_d`` for each of the twelve original
desiderata it meets, where ``f_d`` is the desideratum's exact chance
frequency from the six-event walk (:data:`vultron.measure.baselines.ORIGINAL`,
ADR-0182).  It is the score ``CVDmodel.score_hist`` gives, computed exactly
and without the legacy validation module that new code does not import
(``notes/case-state-model.md``).
"""

from collections.abc import Sequence
from fractions import Fraction

from vultron.core.states.cs_invariants import CSEvent, ensure_valid_cs_history
from vultron.measure.baselines import (
    ORIGINAL,
    Desideratum,
    baseline,
    case_state_query,
)


def _meets(desideratum: Desideratum, history: Sequence[CSEvent]) -> bool:
    """Whether the complete *history* meets every ordering of *desideratum*."""
    query = case_state_query(desideratum.query)
    return all(
        history.index(o.before) < history.index(o.after)
        for o in query.orderings
    )


def met_desiderata(
    history: Sequence[CSEvent | str],
) -> tuple[Desideratum, ...]:
    """The original desiderata the complete *history* meets, in catalog order.

    Raises:
        VultronValidationError, VultronInvalidStateTransitionError: *history*
            is not one of the 70 valid complete histories.
    """
    ensure_valid_cs_history(history)
    events = tuple(CSEvent(e) for e in history)
    return tuple(d for d in ORIGINAL if _meets(d, events))


def history_score(history: Sequence[CSEvent | str]) -> Fraction:
    """The desiderata score of the complete *history*.

    It is ``Σ (1 - f_d)`` over the original desiderata *history* meets.

    Raises:
        VultronValidationError, VultronInvalidStateTransitionError: *history*
            is not one of the 70 valid complete histories.
    """
    return sum((1 - baseline(d) for d in met_desiderata(history)), Fraction(0))
