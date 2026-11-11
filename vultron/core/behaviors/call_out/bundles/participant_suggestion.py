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
"""Call-out bundle for participant suggestion (ADR-0186, BT-24).

Provides :class:`ParticipantSuggestionCallOutBundle`, the pre-built core
DETERMINISTIC singleton :data:`PARTICIPANT_SUGGESTION_DETERMINISTIC`, and the
core backend that wraps the participant-suggestion service for a tree,
:class:`SuggestParticipantsRetriever`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.participant_suggestion.PARTICIPANT_SUGGESTION_STOCHASTIC`).

A deployment that has a
:class:`~vultron.core.ports.participant_suggestion.ParticipantSuggestionPort`
adapter wires it with :func:`suggest_participants_with`::

    bundle = ParticipantSuggestionCallOutBundle(
        suggest_participants_factory=suggest_participants_with(adapter, dl)
    )

Like every bundle field, the backend sits behind the time-bounded seam, so
it answers within the actor's call-out time budget (BT-18-015).  An adapter
too slow for that is for a Sentinel, which calls
:func:`~vultron.core.services.participant_suggestion.suggest_case_participants`
outside any tree (ADR-0186).

Ceiling/floor mapping (BT-23-002):

- ``suggest_participants_factory`` — SuggestParticipants (p=0.90) →
  AlwaysSucceed bound to the declaration, whose *yes* writes an empty list
  (BT-23-013): with no suggester wired, nobody is suggested.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.capabilities.participant_suggestion import (
    PARTICIPANT_SUGGESTIONS_KEY,
    SUGGESTION_CASE_ID_KEY,
    SuggestParticipantsCapability,
)
from vultron.core.behaviors.call_out.nodes import always_succeed_as
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.participant_suggestion import (
    ParticipantSuggestionPort,
)
from vultron.core.services.participant_suggestion import (
    suggest_participants_for_case_id,
)
from vultron.errors import VultronError


class SuggestParticipantsRetriever(SuggestParticipantsCapability):
    """The REAL backend of SuggestParticipants: asks the core service.

    Reads the case id from its input port and answers *yes* with what
    :func:`~vultron.core.services.participant_suggestion.suggest_participants_for_case_id`
    returns for it, an empty list included.  It never calls the port itself
    (BT-24-008).

    A case it cannot read, a reference the case names that *dl* lacks, or
    an adapter that cannot answer is *error*, not *no*: the backend did not
    decide that nobody is missing, it could not find out (ADR-0183).
    """

    def __init__(
        self,
        name: str = "",
        *,
        port: ParticipantSuggestionPort,
        dl: CasePersistence,
    ) -> None:
        super().__init__(name)
        self._port = port
        self._dl = dl

    def answer(self) -> CallOutAnswer:
        """Answer *yes* with the case's suggestions, or *error*."""
        case_id = str(self.get_input(SUGGESTION_CASE_ID_KEY))
        try:
            suggestions = suggest_participants_for_case_id(
                case_id, self._port, self._dl
            )
        except VultronError as exc:
            return CallOutAnswer.error(
                f"participant suggestion for case '{case_id}' failed: {exc}"
            )
        return CallOutAnswer.yes({PARTICIPANT_SUGGESTIONS_KEY: suggestions})


def suggest_participants_with(
    port: ParticipantSuggestionPort, dl: CasePersistence
) -> CallOutBackendFactory:
    """A factory whose backend asks *port* about cases in *dl*.

    The value of
    :attr:`ParticipantSuggestionCallOutBundle.suggest_participants_factory`
    for a deployment that wires an adapter.
    """

    def build(name: str) -> py_trees.behaviour.Behaviour:
        return SuggestParticipantsRetriever(name, port=port, dl=dl)

    return build


@dataclass(frozen=True)
class ParticipantSuggestionCallOutBundle(CallOutBundle):
    """Call-out backend bundle for participant suggestion (ADR-0186).

    The single field backs the Retriever call-out point that asks the
    participant-suggestion port, through the core service, who else should
    take part in a case.  No core tree places it yet; the report-to-others
    Sentinel (BT-20-003) reaches the same service from outside core.
    """

    suggest_participants_factory: CallOutBackendFactory = field(
        default=always_succeed_as(SuggestParticipantsCapability)  # type: ignore[assignment]
    )
    """SuggestParticipants (Retriever): p=0.90 → AlwaysSucceed (empty list).

    Store-held answer (BT-18-039): **cannot**.  The case file lists who is
    in the case, not who is missing from it, and the participants it lists
    already reach the suggester in the suggestion context.
    """


PARTICIPANT_SUGGESTION_DETERMINISTIC = ParticipantSuggestionCallOutBundle()
"""Deterministic bundle: no suggester wired, so an empty list (BT-23-013)."""

__all__ = [
    "PARTICIPANT_SUGGESTION_DETERMINISTIC",
    "ParticipantSuggestionCallOutBundle",
    "SuggestParticipantsRetriever",
    "suggest_participants_with",
]
