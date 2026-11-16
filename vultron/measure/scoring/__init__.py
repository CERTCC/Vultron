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

"""Desiderata scores of case-state sequences, complete or not (ADR-0182).

The first measure that reads the per-vendor sequences
(:mod:`vultron.measure.sequences`), which score nothing themselves
(CEH-05-008).  It takes chance only from :mod:`vultron.measure.baselines`,
never from a second walk, and validates through
:mod:`vultron.core.states.cs_invariants`, never the legacy
``vultron.core.case_states`` package.

* :mod:`~vultron.measure.scoring.complete` — the desiderata score of a
  complete history, :func:`history_score`.
* :mod:`~vultron.measure.scoring.model` — the scored prefix with its weighted
  completions and its expected, best and worst scores, and one vendor's.
* :mod:`~vultron.measure.scoring.score` — :func:`score_prefix`, and the
  refusal of a sequence that is not a prefix.
* :mod:`~vultron.measure.scoring.record` — the case event history read as
  the joint models' events: when each first occurred, and the joint state
  the case stands in.
* :mod:`~vultron.measure.scoring.extended` — the extended desiderata of
  ``process_model_desiderata.md``, scored in their scopes: each vendor, the
  embargo group and the multi-party group (ADR-0200 rule 2).
* :mod:`~vultron.measure.scoring.case` — :func:`score_case`, every scope of
  a case, with the vendors' unweighted median and spread.
"""

from vultron.measure.scoring.case import (
    AcrossVendors,
    CaseScoreSummary,
    score_case,
)
from vultron.measure.scoring.complete import history_score, met_desiderata
from vultron.measure.scoring.extended import (
    EMBARGO_DESIDERATA,
    MULTI_PARTY_DESIDERATA,
    VENDOR_DESIDERATA,
    embargo_scope,
    multi_party_scope,
    vendor_scope,
)
from vultron.measure.scoring.model import (
    Completion,
    ScopeScore,
    SequenceScore,
    TermScore,
    UnscoredScope,
    VendorScore,
    WalkScore,
)
from vultron.measure.scoring.record import (
    CaseRecord,
    NotAJointStateError,
    exit_end,
)
from vultron.measure.scoring.score import (
    NotAHistoryPrefixError,
    score_prefix,
)

__all__ = [
    "EMBARGO_DESIDERATA",
    "MULTI_PARTY_DESIDERATA",
    "VENDOR_DESIDERATA",
    "AcrossVendors",
    "CaseRecord",
    "CaseScoreSummary",
    "Completion",
    "NotAHistoryPrefixError",
    "NotAJointStateError",
    "ScopeScore",
    "SequenceScore",
    "TermScore",
    "UnscoredScope",
    "VendorScore",
    "WalkScore",
    "embargo_scope",
    "exit_end",
    "history_score",
    "met_desiderata",
    "multi_party_scope",
    "score_case",
    "score_prefix",
    "vendor_scope",
]
