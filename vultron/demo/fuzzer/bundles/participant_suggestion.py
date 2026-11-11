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
"""STOCHASTIC call-out bundle for participant suggestion (ADR-0186).

Provides the simulation-layer :data:`PARTICIPANT_SUGGESTION_STOCHASTIC`
singleton, which wires the probabilistic fuzzer node into the core-owned
:class:`~vultron.core.behaviors.call_out.bundles.participant_suggestion.ParticipantSuggestionCallOutBundle`.
The bundle dataclass and the DETERMINISTIC default are core concerns and are
re-exported here, as every simulation bundle module does.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``suggest_participants_factory`` — SuggestParticipants (p=0.90) →
  AlwaysSucceed
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.participant_suggestion import (
    PARTICIPANT_SUGGESTION_DETERMINISTIC,
    ParticipantSuggestionCallOutBundle,
)
from vultron.demo.fuzzer.participant_suggestion import SuggestParticipants


def _stochastic_suggest_participants(
    name: str,
) -> py_trees.behaviour.Behaviour:
    return SuggestParticipants(name)


PARTICIPANT_SUGGESTION_STOCHASTIC = ParticipantSuggestionCallOutBundle(
    suggest_participants_factory=_stochastic_suggest_participants,  # type: ignore[arg-type]
)
"""Stochastic bundle: suggestion uses the probabilistic fuzzer class."""

__all__ = [
    "PARTICIPANT_SUGGESTION_DETERMINISTIC",
    "PARTICIPANT_SUGGESTION_STOCHASTIC",
    "ParticipantSuggestionCallOutBundle",
]
