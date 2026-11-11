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

"""Exact chance baselines for the CVD desiderata (ADR-0182).

Each desideratum takes its chance frequency ``f_d`` from the indifference walk
over the smallest model that holds its events, solved exactly with no
sampling.  The package reads :mod:`vultron.core.states` and nothing else of
the protocol, and writes nothing (CEH-01-001, CEH-01-002).

* :mod:`~vultron.measure.baselines.walk` — the walk as an absorbing Markov
  chain: :func:`frequency` for one query, :func:`implies` for whether one
  query implies another.
* :mod:`~vultron.measure.baselines.case_state` — the six-event case-state
  model, with per-history and from-a-prefix probabilities for scoring an
  incomplete sequence.
* :mod:`~vultron.measure.baselines.joint` — the one-vendor and two-vendor
  joint models, built from the RM, CS and EM tables and the composite
  invariants.
* :mod:`~vultron.measure.baselines.desiderata` — every desideratum with its
  model, its baseline, and the implication pairs.
* :mod:`~vultron.measure.baselines.render` — the Markdown tables the
  Measuring CVD pages print.
"""

from vultron.measure.baselines.case_state import (
    CASE_STATE_MODEL,
    CaseStateModel,
    completion_probabilities,
    history_probability,
    prefix_probability,
    step_probability,
)
from vultron.measure.baselines.desiderata import (
    EXTENDED,
    NEAR_EQUAL_RATIO,
    ORIGINAL,
    Desideratum,
    Group,
    Implication,
    ModelName,
    baseline,
    implications,
)
from vultron.measure.baselines.joint import (
    ONE_VENDOR_MODEL,
    TWO_VENDOR_MODEL,
    EmbargoEnd,
    Event,
    EventKind,
    JointModel,
    JointState,
    VendorPath,
)
from vultron.measure.baselines.walk import (
    ChanceModel,
    Ordering,
    OrderingQuery,
    Step,
    WalkNeverEndsError,
    frequency,
    implies,
    ordering,
)

__all__ = [
    "CASE_STATE_MODEL",
    "EXTENDED",
    "NEAR_EQUAL_RATIO",
    "ONE_VENDOR_MODEL",
    "ORIGINAL",
    "TWO_VENDOR_MODEL",
    "CaseStateModel",
    "ChanceModel",
    "Desideratum",
    "EmbargoEnd",
    "Event",
    "EventKind",
    "Group",
    "Implication",
    "JointModel",
    "JointState",
    "ModelName",
    "Ordering",
    "OrderingQuery",
    "Step",
    "VendorPath",
    "WalkNeverEndsError",
    "baseline",
    "completion_probabilities",
    "frequency",
    "history_probability",
    "implies",
    "implications",
    "ordering",
    "prefix_probability",
    "step_probability",
]
